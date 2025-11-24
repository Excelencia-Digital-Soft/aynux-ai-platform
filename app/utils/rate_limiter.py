"""
Rate Limiter para APIs externas
Responsabilidad: Controlar la frecuencia de requests para respetar límites de APIs
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


class RateLimiter:
    """
    Rate limiter genérico que controla la frecuencia de operaciones
    """

    def __init__(self, min_interval_seconds: float):
        """
        Inicializa el rate limiter

        Args:
            min_interval_seconds: Intervalo mínimo entre operaciones en segundos
        """
        self.min_interval = min_interval_seconds
        self.last_request_time: Optional[float] = None
        self._lock = asyncio.Lock()

    async def wait_if_needed(self) -> float:
        """
        Espera si es necesario para respetar el rate limit

        Returns:
            float: Tiempo de espera en segundos (0 si no hubo espera)
        """
        async with self._lock:
            current_time = time.time()

            if self.last_request_time is None:
                self.last_request_time = current_time
                return 0.0

            time_since_last = current_time - self.last_request_time

            if time_since_last < self.min_interval:
                wait_time = self.min_interval - time_since_last
                await asyncio.sleep(wait_time)
                # Actualizar DESPUÉS de dormir para asegurar tiempo exacto
                self.last_request_time = time.time()
                return wait_time
            else:
                self.last_request_time = current_time
                return 0.0

    def mark_request_completed(self):
        """Marca el momento en que se completó un request"""
        self.last_request_time = time.time()

    def get_time_until_next_allowed(self) -> float:
        """
        Obtiene el tiempo restante hasta que se permita la próxima operación

        Returns:
            float: Segundos hasta la próxima operación permitida (0 si ya es posible)
        """
        if self.last_request_time is None:
            return 0.0

        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_interval:
            return self.min_interval - time_since_last
        else:
            return 0.0

    def reset(self):
        """Resetea el rate limiter"""
        self.last_request_time = None


class DuxApiRateLimiter:
    """
    Rate limiter específico para la API DUX con límite de 5 segundos
    """

    def __init__(self):
        """Inicializa el rate limiter para DUX con 5 segundos de intervalo"""
        self.rate_limiter = RateLimiter(min_interval_seconds=5.0)
        self.request_count = 0
        self.start_time = time.time()

    async def wait_for_next_request(self) -> Dict[str, float]:
        """
        Espera el tiempo necesario antes de la próxima request a DUX

        Returns:
            Dict con información sobre la espera
        """
        wait_time = await self.rate_limiter.wait_if_needed()
        self.request_count += 1

        return {
            "wait_time_seconds": wait_time,
            "total_requests": self.request_count,
            "elapsed_time_seconds": time.time() - self.start_time,
        }

    def get_stats(self) -> Dict[str, float]:
        """
        Obtiene estadísticas del rate limiter

        Returns:
            Dict con estadísticas
        """
        elapsed = time.time() - self.start_time
        requests_per_minute = (self.request_count / elapsed) * 60 if elapsed > 0 else 0

        return {
            "total_requests": self.request_count,
            "elapsed_time_seconds": elapsed,
            "requests_per_minute": requests_per_minute,
            "time_until_next_allowed": self.rate_limiter.get_time_until_next_allowed(),
        }

    def reset_stats(self):
        """Resetea las estadísticas pero mantiene el rate limiting"""
        self.request_count = 0
        self.start_time = time.time()


class BatchRateLimiter:
    """
    Rate limiter para procesamiento por lotes con control de tiempo total
    """

    def __init__(self, min_interval_seconds: float, max_batch_duration_minutes: Optional[int] = None):
        """
        Inicializa el batch rate limiter

        Args:
            min_interval_seconds: Intervalo mínimo entre requests
            max_batch_duration_minutes: Duración máxima del lote en minutos
        """
        self.rate_limiter = RateLimiter(min_interval_seconds)
        self.max_duration = timedelta(minutes=max_batch_duration_minutes) if max_batch_duration_minutes else None
        self.batch_start_time = datetime.now()
        self.batch_request_count = 0

    async def wait_for_batch_request(self) -> Dict[str, Any]:
        """
        Espera para la próxima request del lote

        Returns:
            Dict con información sobre la espera y el estado del lote
        """
        # Verificar si se excedió el tiempo máximo del lote
        if self.max_duration:
            elapsed = datetime.now() - self.batch_start_time
            if elapsed > self.max_duration:
                return {
                    "should_stop_batch": True,
                    "reason": "max_duration_exceeded",
                    "elapsed_minutes": elapsed.total_seconds() / 60,
                    "max_duration_minutes": self.max_duration.total_seconds() / 60,
                }

        # Aplicar rate limiting
        wait_time = await self.rate_limiter.wait_if_needed()
        self.batch_request_count += 1

        elapsed = datetime.now() - self.batch_start_time

        return {
            "should_stop_batch": False,
            "wait_time_seconds": wait_time,
            "batch_request_count": self.batch_request_count,
            "batch_elapsed_minutes": elapsed.total_seconds() / 60,
            "requests_per_minute": (
                (self.batch_request_count / elapsed.total_seconds()) * 60 if elapsed.total_seconds() > 0 else 0
            ),
        }

    def start_new_batch(self):
        """Inicia un nuevo lote"""
        self.batch_start_time = datetime.now()
        self.batch_request_count = 0
        self.rate_limiter.reset()


# Instancia global del rate limiter para DUX
dux_rate_limiter = DuxApiRateLimiter()


async def retry_with_rate_limit(
    func, max_retries: int = 3, backoff_factor: float = 2.0, logger: Optional[logging.Logger] = None
):
    """
    Retry a function with exponential backoff for rate limit errors

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for backoff time
        logger: Optional logger for retry messages

    Returns:
        Result of the successful function call

    Raises:
        Last exception if all retries fail
    """
    from app.models.dux import DuxApiError

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except DuxApiError as e:
            if e.error_code == "RATE_LIMIT" and attempt < max_retries:
                wait_time = backoff_factor**attempt
                if logger:
                    logger.info(
                        f"Rate limit hit, retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries + 1})"
                    )
                await asyncio.sleep(wait_time)
                continue
            raise
        except Exception as e:
            if attempt < max_retries and "rate limit" in str(e).lower():
                wait_time = backoff_factor**attempt
                if logger:
                    logger.info(
                        f"Possible rate limit error, retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries + 1})"
                    )
                await asyncio.sleep(wait_time)
                continue
            raise
