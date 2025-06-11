"""
Sistema de monitoreo completo para el sistema multi-agente
"""
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from opentelemetry import metrics, trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.metrics import get_meter_provider, set_meter_provider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import get_tracer_provider, set_tracer_provider

logger = logging.getLogger(__name__)


class MonitoringSystem:
    """Sistema completo de monitoreo para métricas, trazas y logs"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Configurar logging estructurado
        self._setup_structured_logging()
        
        # Configurar OpenTelemetry
        self._setup_telemetry()
        
        # Configurar métricas
        self._setup_metrics()
        
        # Estado del monitoreo
        self.active_sessions = {}
        self.performance_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_response_time": 0.0,
            "agent_usage": {}
        }
        
        logger.info("Monitoring system initialized")
    
    def _setup_structured_logging(self):
        """Configura logging estructurado con structlog"""
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        # Configurar logging de OpenTelemetry
        LoggingInstrumentor().instrument(set_logging_format=True)
    
    def _setup_telemetry(self):
        """Configura OpenTelemetry para trazas y métricas"""
        # Configurar TracerProvider
        tracer_provider = TracerProvider()
        set_tracer_provider(tracer_provider)
        
        # Configurar MeterProvider con exportador Prometheus
        metric_reader = PrometheusMetricReader()
        meter_provider = MeterProvider(metric_readers=[metric_reader])
        set_meter_provider(meter_provider)
        
        # Obtener tracer y meter
        self.tracer = trace.get_tracer(__name__)
        self.meter = metrics.get_meter(__name__)
    
    def _setup_metrics(self):
        """Configura métricas específicas del sistema"""
        # Contadores
        self.request_counter = self.meter.create_counter(
            "assistant_requests_total",
            description="Total number of requests processed"
        )
        
        self.error_counter = self.meter.create_counter(
            "assistant_errors_total", 
            description="Total number of errors"
        )
        
        self.agent_invocation_counter = self.meter.create_counter(
            "agent_invocations_total",
            description="Total number of agent invocations"
        )
        
        # Histogramas
        self.response_time_histogram = self.meter.create_histogram(
            "assistant_response_time_seconds",
            description="Response time in seconds"
        )
        
        self.agent_processing_time = self.meter.create_histogram(
            "agent_processing_time_seconds",
            description="Agent processing time in seconds"
        )
        
        # Gauges
        self.active_sessions_gauge = self.meter.create_up_down_counter(
            "assistant_active_sessions",
            description="Number of active sessions"
        )
        
        self.memory_usage_gauge = self.meter.create_gauge(
            "assistant_memory_usage_bytes",
            description="Memory usage in bytes"
        )
    
    def start_session(self, conversation_id: str, customer_data: Dict[str, Any]) -> str:
        """
        Inicia una sesión de monitoreo
        
        Args:
            conversation_id: ID de la conversación
            customer_data: Datos del cliente
        
        Returns:
            Session ID para tracking
        """
        session_id = f"session_{conversation_id}_{int(time.time())}"
        
        session_info = {
            "session_id": session_id,
            "conversation_id": conversation_id,
            "customer_id": customer_data.get("customer_id"),
            "customer_tier": customer_data.get("tier", "basic"),
            "start_time": datetime.now(),
            "agents_used": [],
            "total_processing_time": 0.0,
            "error_count": 0,
            "request_count": 0
        }
        
        self.active_sessions[session_id] = session_info
        self.active_sessions_gauge.add(1)
        
        # Log estructurado
        self.get_logger().info(
            "session_started",
            session_id=session_id,
            conversation_id=conversation_id,
            customer_id=customer_data.get("customer_id")
        )
        
        return session_id
    
    def track_request(
        self,
        session_id: str,
        message: str,
        intent: Optional[str] = None
    ) -> str:
        """
        Rastrea una nueva request
        
        Args:
            session_id: ID de la sesión
            message: Mensaje del usuario
            intent: Intención detectada
        
        Returns:
            Request ID para tracking
        """
        request_id = f"req_{session_id}_{int(time.time() * 1000)}"
        
        # Actualizar estadísticas de sesión
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["request_count"] += 1
        
        # Actualizar estadísticas globales
        self.performance_stats["total_requests"] += 1
        
        # Métricas
        self.request_counter.add(1, {
            "session_id": session_id,
            "intent": intent or "unknown"
        })
        
        # Log estructurado
        self.get_logger().info(
            "request_started",
            request_id=request_id,
            session_id=session_id,
            message_length=len(message),
            intent=intent
        )
        
        return request_id
    
    def track_agent_invocation(
        self,
        session_id: str,
        agent_name: str,
        start_time: datetime
    ) -> str:
        """
        Rastrea la invocación de un agente
        
        Args:
            session_id: ID de la sesión
            agent_name: Nombre del agente
            start_time: Tiempo de inicio
        
        Returns:
            Span ID para tracking
        """
        span_id = f"span_{agent_name}_{int(time.time() * 1000)}"
        
        # Crear span de OpenTelemetry
        with self.tracer.start_as_current_span(f"agent_{agent_name}") as span:
            span.set_attribute("agent.name", agent_name)
            span.set_attribute("session.id", session_id)
            
            # Actualizar estadísticas de sesión
            if session_id in self.active_sessions:
                session = self.active_sessions[session_id]
                if agent_name not in session["agents_used"]:
                    session["agents_used"].append(agent_name)
            
            # Actualizar estadísticas de agente
            if agent_name not in self.performance_stats["agent_usage"]:
                self.performance_stats["agent_usage"][agent_name] = {
                    "total_invocations": 0,
                    "total_processing_time": 0.0,
                    "success_count": 0,
                    "error_count": 0
                }
            
            self.performance_stats["agent_usage"][agent_name]["total_invocations"] += 1
            
            # Métricas
            self.agent_invocation_counter.add(1, {"agent": agent_name})
            
            # Log estructurado
            self.get_logger().info(
                "agent_invocation_started",
                span_id=span_id,
                session_id=session_id,
                agent_name=agent_name
            )
        
        return span_id
    
    def track_agent_completion(
        self,
        session_id: str,
        agent_name: str,
        start_time: datetime,
        success: bool,
        processing_time_ms: float,
        error: Optional[str] = None
    ):
        """
        Rastrea la finalización de un agente
        
        Args:
            session_id: ID de la sesión
            agent_name: Nombre del agente
            start_time: Tiempo de inicio
            success: Si fue exitoso
            processing_time_ms: Tiempo de procesamiento en ms
            error: Error si hubo
        """
        processing_time_sec = processing_time_ms / 1000.0
        
        # Actualizar estadísticas de sesión
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["total_processing_time"] += processing_time_sec
            if not success:
                self.active_sessions[session_id]["error_count"] += 1
        
        # Actualizar estadísticas de agente
        if agent_name in self.performance_stats["agent_usage"]:
            agent_stats = self.performance_stats["agent_usage"][agent_name]
            agent_stats["total_processing_time"] += processing_time_sec
            
            if success:
                agent_stats["success_count"] += 1
            else:
                agent_stats["error_count"] += 1
        
        # Métricas
        self.agent_processing_time.record(
            processing_time_sec,
            {"agent": agent_name, "success": str(success)}
        )
        
        if not success:
            self.error_counter.add(1, {
                "agent": agent_name,
                "error_type": type(error).__name__ if error else "unknown"
            })
        
        # Log estructurado
        self.get_logger().info(
            "agent_invocation_completed",
            session_id=session_id,
            agent_name=agent_name,
            success=success,
            processing_time_ms=processing_time_ms,
            error=error
        )
    
    def track_request_completion(
        self,
        session_id: str,
        request_id: str,
        start_time: datetime,
        success: bool,
        response_length: int,
        error: Optional[str] = None
    ):
        """
        Rastrea la finalización de una request
        
        Args:
            session_id: ID de la sesión
            request_id: ID de la request
            start_time: Tiempo de inicio
            success: Si fue exitoso
            response_length: Longitud de la respuesta
            error: Error si hubo
        """
        response_time = (datetime.now() - start_time).total_seconds()
        
        # Actualizar estadísticas globales
        if success:
            self.performance_stats["successful_requests"] += 1
        else:
            self.performance_stats["failed_requests"] += 1
        
        # Calcular promedio de tiempo de respuesta
        total_requests = self.performance_stats["total_requests"]
        current_avg = self.performance_stats["average_response_time"]
        
        new_avg = ((current_avg * (total_requests - 1)) + response_time) / total_requests
        self.performance_stats["average_response_time"] = new_avg
        
        # Métricas
        self.response_time_histogram.record(
            response_time,
            {"success": str(success)}
        )
        
        # Log estructurado
        self.get_logger().info(
            "request_completed",
            request_id=request_id,
            session_id=session_id,
            success=success,
            response_time_seconds=response_time,
            response_length=response_length,
            error=error
        )
    
    def end_session(self, session_id: str):
        """
        Finaliza una sesión de monitoreo
        
        Args:
            session_id: ID de la sesión
        """
        if session_id not in self.active_sessions:
            return
        
        session = self.active_sessions[session_id]
        session_duration = (datetime.now() - session["start_time"]).total_seconds()
        
        # Log estructurado
        self.get_logger().info(
            "session_ended",
            session_id=session_id,
            conversation_id=session["conversation_id"],
            duration_seconds=session_duration,
            total_requests=session["request_count"],
            agents_used=session["agents_used"],
            error_count=session["error_count"]
        )
        
        # Limpiar sesión
        del self.active_sessions[session_id]
        self.active_sessions_gauge.add(-1)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Obtiene métricas de rendimiento actuales
        
        Returns:
            Diccionario con métricas
        """
        return {
            "summary": {
                "total_requests": self.performance_stats["total_requests"],
                "successful_requests": self.performance_stats["successful_requests"],
                "failed_requests": self.performance_stats["failed_requests"],
                "success_rate": (
                    self.performance_stats["successful_requests"] / 
                    max(self.performance_stats["total_requests"], 1)
                ) * 100,
                "average_response_time": self.performance_stats["average_response_time"],
                "active_sessions": len(self.active_sessions)
            },
            "agent_performance": self._calculate_agent_performance(),
            "current_sessions": self._get_session_summaries(),
            "timestamp": datetime.now().isoformat()
        }
    
    def _calculate_agent_performance(self) -> Dict[str, Any]:
        """Calcula métricas de rendimiento por agente"""
        agent_metrics = {}
        
        for agent_name, stats in self.performance_stats["agent_usage"].items():
            total_invocations = stats["total_invocations"]
            
            if total_invocations > 0:
                agent_metrics[agent_name] = {
                    "total_invocations": total_invocations,
                    "success_rate": (stats["success_count"] / total_invocations) * 100,
                    "average_processing_time": stats["total_processing_time"] / total_invocations,
                    "error_count": stats["error_count"]
                }
        
        return agent_metrics
    
    def _get_session_summaries(self) -> List[Dict[str, Any]]:
        """Obtiene resúmenes de sesiones activas"""
        summaries = []
        
        for session_id, session in self.active_sessions.items():
            duration = (datetime.now() - session["start_time"]).total_seconds()
            
            summaries.append({
                "session_id": session_id,
                "conversation_id": session["conversation_id"],
                "customer_id": session["customer_id"],
                "customer_tier": session["customer_tier"],
                "duration_seconds": duration,
                "request_count": session["request_count"],
                "agents_used": session["agents_used"],
                "error_count": session["error_count"]
            })
        
        return summaries
    
    def get_logger(self) -> structlog.BoundLogger:
        """
        Obtiene un logger estructurado
        
        Returns:
            Logger estructurado configurado
        """
        return structlog.get_logger()
    
    def create_dashboard_data(self) -> Dict[str, Any]:
        """
        Crea datos para dashboard de monitoreo
        
        Returns:
            Datos formateados para dashboard
        """
        metrics = self.get_performance_metrics()
        
        return {
            "overview": {
                "total_requests": metrics["summary"]["total_requests"],
                "success_rate": f"{metrics['summary']['success_rate']:.1f}%",
                "avg_response_time": f"{metrics['summary']['average_response_time']:.2f}s",
                "active_sessions": metrics["summary"]["active_sessions"]
            },
            "agents": [
                {
                    "name": agent,
                    "invocations": stats["total_invocations"],
                    "success_rate": f"{stats['success_rate']:.1f}%",
                    "avg_time": f"{stats['average_processing_time']:.3f}s"
                }
                for agent, stats in metrics["agent_performance"].items()
            ],
            "recent_activity": metrics["current_sessions"][-10:],  # Últimas 10 sesiones
            "alerts": self._generate_alerts()
        }
    
    def _generate_alerts(self) -> List[Dict[str, Any]]:
        """Genera alertas basadas en métricas"""
        alerts = []
        
        # Alert por tasa de error alta
        if self.performance_stats["total_requests"] > 100:
            error_rate = (
                self.performance_stats["failed_requests"] / 
                self.performance_stats["total_requests"]
            ) * 100
            
            if error_rate > 10:  # Más del 10% de errores
                alerts.append({
                    "level": "warning",
                    "message": f"High error rate: {error_rate:.1f}%",
                    "timestamp": datetime.now().isoformat()
                })
        
        # Alert por tiempo de respuesta alto
        avg_response_time = self.performance_stats["average_response_time"]
        if avg_response_time > 5.0:  # Más de 5 segundos
            alerts.append({
                "level": "warning",
                "message": f"High response time: {avg_response_time:.2f}s",
                "timestamp": datetime.now().isoformat()
            })
        
        # Alert por muchas sesiones activas
        active_sessions = len(self.active_sessions)
        if active_sessions > 100:
            alerts.append({
                "level": "info",
                "message": f"High load: {active_sessions} active sessions",
                "timestamp": datetime.now().isoformat()
            })
        
        return alerts