"""
Sistema de monitoreo y métricas de performance para el chatbot de WhatsApp
"""

import asyncio
import logging
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, DefaultDict, Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Tipos de métricas soportadas"""

    COUNTER = "counter"
    HISTOGRAM = "histogram"
    GAUGE = "gauge"
    TIMER = "timer"


@dataclass
class MetricData:
    """Datos de una métrica individual"""

    name: str
    type: MetricType
    value: float
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)
    unit: str = ""


@dataclass
class OperationTrace:
    """Traza de una operación completa"""

    trace_id: str
    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    success: bool = True
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    checkpoints: List[Dict[str, Any]] = field(default_factory=list)


class PerformanceMonitor:
    """
    Monitor de rendimiento con métricas detalladas y traces distribuidos.

    Implementa las mejores prácticas del langgraph.md para monitoring comprehensivo.
    """

    def __init__(self, buffer_size: int = 10000, flush_interval: int = 60):
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval

        # Almacenamiento de métricas
        self._metrics_buffer = deque(maxlen=buffer_size)
        self._active_traces = {}
        self._completed_traces = deque(maxlen=1000)  # Últimas 1000 operaciones

        # Agregaciones en tiempo real
        self._counters: DefaultDict[str, float] = defaultdict(float)
        self._gauges: DefaultDict[str, float] = defaultdict(float)
        self._histograms: DefaultDict[str, List[float]] = defaultdict(list)
        self._timers: DefaultDict[str, List[float]] = defaultdict(list)

        # Métricas específicas del sistema
        self._system_metrics: Dict[str, Any] = {
            "message_processing": {
                "total_messages": 0,
                "successful_messages": 0,
                "failed_messages": 0,
                "avg_response_time": 0.0,
                "messages_per_second": 0.0,
            },
            "agent_performance": defaultdict(
                lambda: {"invocations": 0, "success_rate": 0.0, "avg_response_time": 0.0, "error_count": 0}
            ),
            "cache_performance": {"hit_rate": 0.0, "total_requests": 0, "memory_usage_mb": 0.0},
        }

        # Worker para flush periódico
        self._flush_task = None
        self._running = False

        logger.info(f"PerformanceMonitor initialized - buffer: {buffer_size}, flush: {flush_interval}s")

    async def start(self):
        """Iniciar el monitor de performance"""
        if self._running:
            return

        self._running = True
        self._flush_task = asyncio.create_task(self._periodic_flush())
        logger.info("Performance monitoring started")

    async def stop(self):
        """Detener el monitor de performance"""
        if not self._running:
            return

        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Flush final
        await self._flush_metrics()
        logger.info("Performance monitoring stopped")

    def record_counter(self, name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None):
        """Registrar métrica tipo contador"""
        metric = MetricData(name=name, type=MetricType.COUNTER, value=value, timestamp=time.time(), tags=tags or {})

        self._metrics_buffer.append(metric)
        self._counters[name] += value

    def record_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Registrar métrica tipo gauge (valor actual)"""
        metric = MetricData(name=name, type=MetricType.GAUGE, value=value, timestamp=time.time(), tags=tags or {})

        self._metrics_buffer.append(metric)
        self._gauges[name] = value

    def record_histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Registrar métrica tipo histograma (distribución de valores)"""
        metric = MetricData(name=name, type=MetricType.HISTOGRAM, value=value, timestamp=time.time(), tags=tags or {})

        self._metrics_buffer.append(metric)
        self._histograms[name].append(value)

        # Mantener solo últimos 1000 valores
        if len(self._histograms[name]) > 1000:
            self._histograms[name] = self._histograms[name][-1000:]

    @asynccontextmanager
    async def track_operation(self, operation_name: str, tags: Optional[Dict[str, str]] = None):
        """
        Context manager para tracking automático de operaciones.

        Args:
            operation_name: Nombre de la operación
            tags: Tags adicionales para la traza

        Yields:
            trace_id: ID de la traza para checkpoints adicionales
        """
        trace_id = str(uuid.uuid4())
        start_time = time.time()

        trace = OperationTrace(trace_id=trace_id, operation_name=operation_name, start_time=start_time, tags=tags or {})

        self._active_traces[trace_id] = trace

        try:
            yield trace_id

            # Operación exitosa
            end_time = time.time()
            duration = end_time - start_time

            trace.end_time = end_time
            trace.duration = duration
            trace.success = True

            # Registrar métricas
            self.record_histogram(f"operation.{operation_name}.duration", duration)
            self.record_counter(f"operation.{operation_name}.success", tags=tags)

        except Exception as e:
            # Operación fallida
            end_time = time.time()
            duration = end_time - start_time

            trace.end_time = end_time
            trace.duration = duration
            trace.success = False
            trace.error_type = type(e).__name__
            trace.error_message = str(e)

            # Registrar métricas de error
            error_tags = {**(tags or {}), "error_type": type(e).__name__}
            self.record_counter(f"operation.{operation_name}.error", tags=error_tags)
            self.record_histogram(f"operation.{operation_name}.duration", duration)

            raise

        finally:
            # Mover a completadas y limpiar
            if trace_id in self._active_traces:
                completed_trace = self._active_traces.pop(trace_id)
                self._completed_traces.append(completed_trace)

    def add_checkpoint(self, trace_id: str, checkpoint_name: str, data: Optional[Dict[str, Any]] = None):
        """
        Agregar checkpoint a una traza activa.

        Args:
            trace_id: ID de la traza
            checkpoint_name: Nombre del checkpoint
            data: Datos adicionales del checkpoint
        """
        if trace_id in self._active_traces:
            checkpoint = {"name": checkpoint_name, "timestamp": time.time(), "data": data or {}}
            self._active_traces[trace_id].checkpoints.append(checkpoint)

    def record_message_processed(
        self,
        success: bool,
        response_time: float,
        agent_used: Optional[str] = None,
        error_type: Optional[str] = None,
    ):
        """Registrar procesamiento de mensaje específico para chatbot"""
        # Métricas generales
        msg_processing = self._system_metrics["message_processing"]
        assert isinstance(msg_processing, dict)

        total_msg = msg_processing["total_messages"]
        assert isinstance(total_msg, int)
        msg_processing["total_messages"] = total_msg + 1

        if success:
            success_msg = msg_processing["successful_messages"]
            assert isinstance(success_msg, int)
            msg_processing["successful_messages"] = success_msg + 1
        else:
            failed_msg = msg_processing["failed_messages"]
            assert isinstance(failed_msg, int)
            msg_processing["failed_messages"] = failed_msg + 1

        # Actualizar tiempo promedio de respuesta
        total = msg_processing["total_messages"]
        assert isinstance(total, int)
        current_avg = msg_processing["avg_response_time"]
        assert isinstance(current_avg, float)
        new_avg = ((current_avg * (total - 1)) + response_time) / total
        msg_processing["avg_response_time"] = new_avg

        # Métricas por agente
        if agent_used:
            agent_performance = self._system_metrics["agent_performance"]
            assert isinstance(agent_performance, dict)
            agent_stats = agent_performance[agent_used]
            assert isinstance(agent_stats, dict)

            invocations = agent_stats["invocations"]
            assert isinstance(invocations, (int, float))
            agent_stats["invocations"] = int(invocations) + 1

            if success:
                error_count = agent_stats["error_count"]
                assert isinstance(error_count, (int, float))
                success_count = agent_stats["invocations"] - error_count
                assert isinstance(agent_stats["invocations"], (int, float))
                agent_stats["success_rate"] = (success_count / agent_stats["invocations"]) * 100
            else:
                error_count = agent_stats["error_count"]
                assert isinstance(error_count, (int, float))
                agent_stats["error_count"] = int(error_count) + 1
                invoc = agent_stats["invocations"]
                err = agent_stats["error_count"]
                assert isinstance(invoc, (int, float))
                assert isinstance(err, (int, float))
                agent_stats["success_rate"] = ((invoc - err) / invoc) * 100

            # Actualizar tiempo promedio del agente
            current_agent_avg = agent_stats["avg_response_time"]
            assert isinstance(current_agent_avg, float)
            invoc_count = agent_stats["invocations"]
            assert isinstance(invoc_count, (int, float))
            new_agent_avg = ((current_agent_avg * (invoc_count - 1)) + response_time) / invoc_count
            agent_stats["avg_response_time"] = new_agent_avg

        # Registrar métricas granulares
        tags = {"agent": agent_used} if agent_used else {}
        if error_type:
            tags["error_type"] = error_type

        self.record_histogram("message.response_time", response_time, tags)
        self.record_counter("message.total", tags=tags)

        if success:
            self.record_counter("message.success", tags=tags)
        else:
            self.record_counter("message.error", tags=tags)

    def update_cache_metrics(self, hit_rate: float, total_requests: int, memory_usage_mb: float):
        """Actualizar métricas del sistema de caché"""
        cache_perf = self._system_metrics["cache_performance"]
        assert isinstance(cache_perf, dict)

        cache_perf["hit_rate"] = hit_rate
        cache_perf["total_requests"] = total_requests
        cache_perf["memory_usage_mb"] = memory_usage_mb

        # Registrar como métricas granulares
        self.record_gauge("cache.hit_rate", hit_rate)
        self.record_gauge("cache.memory_usage_mb", memory_usage_mb)
        self.record_counter("cache.requests", float(total_requests))

    def get_real_time_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas en tiempo real"""
        # Calcular mensajes por segundo (últimos 60 segundos)
        current_time = time.time()
        recent_traces = [t for t in self._completed_traces if t.end_time and (current_time - t.end_time) <= 60]

        messages_last_minute = len([t for t in recent_traces if t.operation_name == "message_processing"])
        messages_per_second = messages_last_minute / 60.0 if messages_last_minute > 0 else 0.0

        msg_processing = self._system_metrics["message_processing"]
        assert isinstance(msg_processing, dict)
        msg_processing["messages_per_second"] = messages_per_second

        # Estadísticas de histogramas (percentiles)
        histogram_stats = {}
        for name, values in self._histograms.items():
            if values:
                sorted_values = sorted(values)
                histogram_stats[name] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "p50": sorted_values[len(sorted_values) // 2],
                    "p95": sorted_values[int(len(sorted_values) * 0.95)]
                    if len(sorted_values) > 20
                    else sorted_values[-1],
                    "p99": sorted_values[int(len(sorted_values) * 0.99)]
                    if len(sorted_values) > 100
                    else sorted_values[-1],
                }

        return {
            "system_metrics": dict(self._system_metrics),
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": histogram_stats,
            "active_traces": len(self._active_traces),
            "completed_traces": len(self._completed_traces),
            "buffer_usage": f"{len(self._metrics_buffer)}/{self.buffer_size}",
        }

    def get_agent_performance(self) -> Dict[str, Any]:
        """Obtener métricas de performance por agente"""
        agent_performance = {}

        agent_perf_data = self._system_metrics["agent_performance"]
        assert isinstance(agent_perf_data, dict)

        for agent_name, stats in agent_perf_data.items():
            assert isinstance(stats, dict)
            success_rate = stats["success_rate"]
            assert isinstance(success_rate, float)
            avg_time = stats["avg_response_time"]
            assert isinstance(avg_time, float)
            error_count = stats["error_count"]
            assert isinstance(error_count, (int, float))
            invocations = stats["invocations"]
            assert isinstance(invocations, (int, float))

            agent_performance[agent_name] = {
                **stats,
                "success_rate": f"{success_rate:.1f}%",
                "avg_response_time": f"{avg_time:.3f}s",
                "error_rate": f"{(error_count / max(invocations, 1) * 100):.1f}%",
            }

        return agent_performance

    def get_trace_summary(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Obtener resumen de las últimas trazas"""
        recent_traces = list(self._completed_traces)[-limit:]

        summary = []
        for trace in reversed(recent_traces):  # Más recientes primero
            summary.append(
                {
                    "trace_id": trace.trace_id,
                    "operation": trace.operation_name,
                    "duration": f"{trace.duration:.3f}s" if trace.duration else "N/A",
                    "success": trace.success,
                    "error_type": trace.error_type,
                    "checkpoints": len(trace.checkpoints),
                    "timestamp": datetime.fromtimestamp(trace.start_time).strftime("%H:%M:%S"),
                }
            )

        return summary

    def get_health_status(self) -> Dict[str, Any]:
        """Evaluar estado de salud basado en métricas"""
        health: Dict[str, Any] = {"status": "healthy", "issues": [], "score": 100}

        msg_stats = self._system_metrics["message_processing"]
        assert isinstance(msg_stats, dict)

        # Verificar tasa de éxito de mensajes
        total_messages = msg_stats["total_messages"]
        assert isinstance(total_messages, int)
        if total_messages > 0:
            successful_messages = msg_stats["successful_messages"]
            assert isinstance(successful_messages, int)
            success_rate = (successful_messages / total_messages) * 100
            if success_rate < 95:
                issues = health["issues"]
                assert isinstance(issues, list)
                issues.append(f"Message success rate low: {success_rate:.1f}%")
                score = health["score"]
                assert isinstance(score, int)
                health["score"] = score - 20

        # Verificar tiempo de respuesta promedio
        avg_response_time = msg_stats["avg_response_time"]
        assert isinstance(avg_response_time, float)
        if avg_response_time > 5.0:  # > 5 segundos
            issues = health["issues"]
            assert isinstance(issues, list)
            issues.append(f"Average response time high: {avg_response_time:.1f}s")
            score = health["score"]
            assert isinstance(score, int)
            health["score"] = score - 15

        # Verificar rendimiento de agentes
        agent_perf = self._system_metrics["agent_performance"]
        assert isinstance(agent_perf, dict)
        for agent_name, agent_stats in agent_perf.items():
            assert isinstance(agent_stats, dict)
            agent_success_rate = agent_stats["success_rate"]
            assert isinstance(agent_success_rate, float)
            if agent_success_rate < 90:
                issues = health["issues"]
                assert isinstance(issues, list)
                issues.append(f"Agent {agent_name} success rate low: {agent_success_rate:.1f}%")
                score = health["score"]
                assert isinstance(score, int)
                health["score"] = score - 10

        # Verificar caché
        cache_stats = self._system_metrics["cache_performance"]
        assert isinstance(cache_stats, dict)
        hit_rate = cache_stats["hit_rate"]
        assert isinstance(hit_rate, float)
        if hit_rate < 20:  # Hit rate muy bajo
            issues = health["issues"]
            assert isinstance(issues, list)
            issues.append(f"Cache hit rate low: {hit_rate:.1f}%")
            score = health["score"]
            assert isinstance(score, int)
            health["score"] = score - 5

        # Verificar buffer usage
        buffer_usage = len(self._metrics_buffer) / self.buffer_size
        if buffer_usage > 0.9:
            issues = health["issues"]
            assert isinstance(issues, list)
            issues.append(f"Metrics buffer near full: {buffer_usage:.1%}")
            score = health["score"]
            assert isinstance(score, int)
            health["score"] = score - 5

        # Determinar status final
        final_score = health["score"]
        assert isinstance(final_score, int)
        if final_score >= 90:
            health["status"] = "healthy"
        elif final_score >= 70:
            health["status"] = "degraded"
        else:
            health["status"] = "unhealthy"

        return health

    async def _periodic_flush(self):
        """Worker para flush periódico de métricas"""
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self._flush_metrics()
            except Exception as e:
                logger.error(f"Error in periodic flush: {e}")

    async def _flush_metrics(self):
        """Flush métricas a almacenamiento persistente (implementar según necesidades)"""
        if not self._metrics_buffer:
            return

        # Por ahora solo loguear estadísticas
        metrics_count = len(self._metrics_buffer)
        logger.info(f"Flushing {metrics_count} metrics to storage")

        # Aquí se implementaría el envío a sistemas como Prometheus, InfluxDB, etc.
        # Para este ejemplo, solo limpiamos el buffer
        self._metrics_buffer.clear()

    def export_prometheus_format(self) -> str:
        """Exportar métricas en formato Prometheus"""
        lines = []

        # Contadores
        for name, value in self._counters.items():
            metric_name = name.replace(".", "_")
            lines.append(f"# TYPE {metric_name} counter")
            lines.append(f"{metric_name} {value}")

        # Gauges
        for name, value in self._gauges.items():
            metric_name = name.replace(".", "_")
            lines.append(f"# TYPE {metric_name} gauge")
            lines.append(f"{metric_name} {value}")

        # Histogramas (simplificado)
        for name, values in self._histograms.items():
            if values:
                metric_name = name.replace(".", "_")
                lines.append(f"# TYPE {metric_name} histogram")
                lines.append(f"{metric_name}_count {len(values)}")
                lines.append(f"{metric_name}_sum {sum(values)}")

        return "\n".join(lines)

