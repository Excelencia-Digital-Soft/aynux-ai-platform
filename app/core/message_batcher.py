"""
Sistema de batching inteligente para optimizar procesamiento de mensajes de WhatsApp
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class BatchMessage:
    """Mensaje individual en un batch"""

    user_id: str
    message_id: str
    content: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: int = 1  # 1=normal, 2=high, 3=urgent


@dataclass
class BatchStats:
    """Estadísticas de procesamiento de batch"""

    batch_id: str
    batch_size: int
    processing_time: float
    success_count: int
    error_count: int
    user_count: int
    start_time: float
    end_time: float


class WhatsAppMessageBatcher:
    """
    Sistema de batching inteligente para mensajes de WhatsApp.

    Características:
    - Agrupamiento por usuario para mantener contexto
    - Batching adaptativo basado en carga
    - Priorización de mensajes
    - Métricas detalladas de rendimiento
    - Backpressure handling
    """

    def __init__(
        self, batch_size: int = 5, batch_timeout: float = 0.5, max_queue_size: int = 10000, priority_batch_size: int = 3
    ):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.max_queue_size = max_queue_size
        self.priority_batch_size = priority_batch_size

        # Colas de mensajes
        self.message_queue = asyncio.Queue(maxsize=max_queue_size)
        self.priority_queue = asyncio.Queue()

        # Estado interno
        self._processing = False
        self._worker_task = None
        self._batch_counter = 0

        # Estadísticas
        self._stats: Dict[str, Union[int, float, None]] = {
            "total_batches": 0,
            "total_messages": 0,
            "avg_batch_size": 0.0,
            "avg_processing_time": 0.0,
            "total_processing_time": 0.0,
            "messages_per_second": 0.0,
            "queue_size": 0,
            "backpressure_events": 0,
            "last_batch_time": None,
        }

        # Historial de batches (mantener últimos 100)
        self._batch_history = deque(maxlen=100)

        logger.info(f"WhatsAppMessageBatcher initialized - batch_size: {batch_size}, timeout: {batch_timeout}s")

    async def enqueue_message(
        self,
        user_id: str,
        message_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        priority: int = 1,
    ) -> bool:
        """
        Encolar mensaje para procesamiento en batch.

        Args:
            user_id: ID del usuario
            message_id: ID único del mensaje
            content: Contenido del mensaje
            metadata: Metadatos adicionales
            priority: Prioridad (1=normal, 2=high, 3=urgent)

        Returns:
            True si se encoló exitosamente, False si la cola está llena
        """
        message = BatchMessage(
            user_id=user_id,
            message_id=message_id,
            content=content,
            timestamp=time.time(),
            metadata=metadata or {},
            priority=priority,
        )

        try:
            # Mensajes de alta prioridad van a cola especial
            if priority >= 2:
                await self.priority_queue.put(message)
                logger.debug(f"High priority message queued: {message_id} (priority: {priority})")
            else:
                await self.message_queue.put(message)
                logger.debug(f"Message queued: {message_id}")

            # Actualizar estadísticas de cola
            self._stats["queue_size"] = self.message_queue.qsize() + self.priority_queue.qsize()

            return True

        except asyncio.QueueFull:
            backpressure = self._stats["backpressure_events"]
            assert isinstance(backpressure, int)
            self._stats["backpressure_events"] = backpressure + 1
            logger.warning(f"Message queue full - dropping message {message_id}")
            return False

    async def start_processing(self, processor_func: Callable):
        """
        Iniciar el procesamiento de batches.

        Args:
            processor_func: Función async que procesa un batch de mensajes
                           Signature: async def process_batch(batch: List[BatchMessage]) -> List[Any]
        """
        if self._processing:
            logger.warning("Message batcher is already processing")
            return

        self._processing = True
        self._worker_task = asyncio.create_task(self._batch_worker(processor_func))
        logger.info("Message batch processing started")

    async def stop_processing(self):
        """Detener el procesamiento de batches"""
        if not self._processing:
            return

        self._processing = False

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        logger.info("Message batch processing stopped")

    async def _batch_worker(self, processor_func: Callable):
        """Worker principal que procesa batches"""
        logger.info("Batch worker started")

        while self._processing:
            try:
                # Recolectar batch de mensajes
                batch = await self._collect_batch()

                if not batch:
                    # Sin mensajes - pequeña pausa
                    await asyncio.sleep(0.1)
                    continue

                # Procesar batch
                await self._process_batch(batch, processor_func)

            except Exception as e:
                logger.error(f"Error in batch worker: {e}")
                await asyncio.sleep(1)  # Pausa en caso de error

    async def _collect_batch(self) -> List[BatchMessage]:
        """Recolectar mensajes para formar un batch"""
        batch = []

        # Primero, procesar mensajes de alta prioridad
        priority_batch = await self._collect_priority_batch()
        if priority_batch:
            return priority_batch

        # Recolectar mensajes normales
        try:
            while len(batch) < self.batch_size:
                timeout = self.batch_timeout if batch else None

                try:
                    message = await asyncio.wait_for(self.message_queue.get(), timeout=timeout)
                    batch.append(message)

                except asyncio.TimeoutError:
                    if not batch:
                        continue
                    break

        except Exception as e:
            logger.error(f"Error collecting batch: {e}")

        return batch

    async def _collect_priority_batch(self) -> Optional[List[BatchMessage]]:
        """Recolectar batch de mensajes de alta prioridad"""
        priority_batch = []

        # Recolectar hasta priority_batch_size mensajes o hasta que se agote la cola
        while len(priority_batch) < self.priority_batch_size:
            try:
                message = self.priority_queue.get_nowait()
                priority_batch.append(message)
            except asyncio.QueueEmpty:
                break

        return priority_batch if priority_batch else None

    async def _process_batch(self, batch: List[BatchMessage], processor_func: Callable):
        """Procesar un batch de mensajes"""
        batch_id = f"batch_{self._batch_counter:06d}"
        self._batch_counter += 1

        start_time = time.time()
        user_groups = self._group_by_user(batch)

        logger.info(f"Processing {batch_id}: {len(batch)} messages from {len(user_groups)} users")

        # Procesar en paralelo por usuario para mantener contexto
        tasks = []
        for user_id, user_messages in user_groups.items():
            task = self._process_user_batch(user_id, user_messages, processor_func)
            tasks.append(task)

        # Esperar resultados
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Contar éxitos y errores
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        error_count = len(results) - success_count

        # Registrar estadísticas del batch
        end_time = time.time()
        processing_time = end_time - start_time

        batch_stats = BatchStats(
            batch_id=batch_id,
            batch_size=len(batch),
            processing_time=processing_time,
            success_count=success_count,
            error_count=error_count,
            user_count=len(user_groups),
            start_time=start_time,
            end_time=end_time,
        )

        self._update_stats(batch_stats)
        self._batch_history.append(batch_stats)

        logger.info(
            f"Batch {batch_id} completed - "
            f"time: {processing_time:.3f}s, "
            f"success: {success_count}, "
            f"errors: {error_count}"
        )

    def _group_by_user(self, batch: List[BatchMessage]) -> Dict[str, List[BatchMessage]]:
        """Agrupar mensajes por usuario"""
        user_groups = defaultdict(list)
        for message in batch:
            user_groups[message.user_id].append(message)
        return dict(user_groups)

    async def _process_user_batch(self, user_id: str, messages: List[BatchMessage], processor_func: Callable) -> Any:
        """Procesar batch de mensajes de un usuario específico"""
        try:
            # Ordenar mensajes por timestamp para mantener orden
            messages.sort(key=lambda m: m.timestamp)

            result = await processor_func(user_id, messages)
            return result

        except Exception as e:
            logger.error(f"Error processing user batch for {user_id}: {e}")
            raise

    def _update_stats(self, batch_stats: BatchStats):
        """Actualizar estadísticas globales"""
        total_batches = self._stats["total_batches"]
        assert isinstance(total_batches, int)
        self._stats["total_batches"] = total_batches + 1

        total_messages = self._stats["total_messages"]
        assert isinstance(total_messages, int)
        self._stats["total_messages"] = total_messages + batch_stats.batch_size

        total_proc_time = self._stats["total_processing_time"]
        assert isinstance(total_proc_time, float)
        self._stats["total_processing_time"] = total_proc_time + batch_stats.processing_time

        # Calcular promedios
        new_total_batches = self._stats["total_batches"]
        assert isinstance(new_total_batches, int)
        new_total_messages = self._stats["total_messages"]
        assert isinstance(new_total_messages, int)
        new_total_proc_time = self._stats["total_processing_time"]
        assert isinstance(new_total_proc_time, float)

        self._stats["avg_batch_size"] = new_total_messages / new_total_batches
        self._stats["avg_processing_time"] = new_total_proc_time / new_total_batches

        # Calcular mensajes por segundo (ventana deslizante de últimos 10 batches)
        recent_batches = list(self._batch_history)[-10:]
        if len(recent_batches) >= 2:
            total_messages = sum(b.batch_size for b in recent_batches)
            time_span = recent_batches[-1].end_time - recent_batches[0].start_time
            if time_span > 0:
                self._stats["messages_per_second"] = total_messages / time_span

        self._stats["last_batch_time"] = batch_stats.end_time
        self._stats["queue_size"] = self.message_queue.qsize() + self.priority_queue.qsize()

    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del batcher"""
        recent_batches = list(self._batch_history)[-5:]  # Últimos 5 batches

        return {
            "configuration": {
                "batch_size": self.batch_size,
                "batch_timeout": self.batch_timeout,
                "max_queue_size": self.max_queue_size,
                "priority_batch_size": self.priority_batch_size,
            },
            "status": {
                "processing": self._processing,
                "queue_size": self._stats["queue_size"],
                "priority_queue_size": self.priority_queue.qsize(),
                "normal_queue_size": self.message_queue.qsize(),
            },
            "performance": {
                "total_batches": self._stats["total_batches"],
                "total_messages": self._stats["total_messages"],
                "avg_batch_size": f"{self._stats['avg_batch_size']:.1f}",
                "avg_processing_time": f"{self._stats['avg_processing_time']:.3f}s",
                "messages_per_second": f"{self._stats['messages_per_second']:.1f}",
                "backpressure_events": self._stats["backpressure_events"],
            },
            "recent_batches": [
                {
                    "batch_id": b.batch_id,
                    "size": b.batch_size,
                    "processing_time": f"{b.processing_time:.3f}s",
                    "success_rate": f"{(b.success_count / b.batch_size * 100):.1f}%",
                    "user_count": b.user_count,
                }
                for b in recent_batches
            ],
        }

    async def get_queue_info(self) -> Dict[str, Any]:
        """Obtener información detallada de las colas"""
        return {
            "normal_queue": {
                "size": self.message_queue.qsize(),
                "max_size": self.max_queue_size,
                "utilization": f"{(self.message_queue.qsize() / self.max_queue_size * 100):.1f}%",
            },
            "priority_queue": {"size": self.priority_queue.qsize(), "unlimited": True},
            "total_queued": self.message_queue.qsize() + self.priority_queue.qsize(),
            "backpressure_active": self.message_queue.qsize() >= self.max_queue_size * 0.9,
        }

    async def clear_queues(self):
        """Limpiar todas las colas (útil para testing o reset)"""
        cleared_count = 0

        # Limpiar cola normal
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
                cleared_count += 1
            except asyncio.QueueEmpty:
                break

        # Limpiar cola de prioridad
        while not self.priority_queue.empty():
            try:
                self.priority_queue.get_nowait()
                cleared_count += 1
            except asyncio.QueueEmpty:
                break

        logger.info(f"Cleared {cleared_count} messages from queues")
        self._stats["queue_size"] = 0

        return cleared_count

