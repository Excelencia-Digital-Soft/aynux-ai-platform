"""
Circuit breaker resiliente para servicios externos como vLLM
"""

import asyncio
import logging
import time
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, Union

from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"  # Funcionando normalmente
    OPEN = "open"  # Bloqueando llamadas por errores
    HALF_OPEN = "half_open"  # Probando si el servicio se recuperó


class CircuitBreakerError(Exception):
    """Excepción lanzada cuando el circuit breaker está abierto"""

    pass


class CircuitBreaker:
    """
    Circuit breaker para servicios externos con backoff exponencial y métricas.

    Basado en el patrón de Martin Fowler para prevenir llamadas a servicios fallos.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception,
        name: str = "default",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name

        # Estado interno
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._next_attempt_time = 0

        # Métricas
        self._stats: Dict[str, Union[int, List[Dict[str, Any]]]] = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "circuit_opens": 0,
            "circuit_half_opens": 0,
            "state_changes": [],
        }

        logger.info(
            f"CircuitBreaker '{name}' initialized - threshold: {failure_threshold}, timeout: {recovery_timeout}s"
        )

    @property
    def state(self) -> CircuitState:
        """Estado actual del circuit breaker"""
        return self._state

    @property
    def is_open(self) -> bool:
        """True si el circuit breaker está abierto (bloqueando llamadas)"""
        return self._state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """True si el circuit breaker está cerrado (funcionando normalmente)"""
        return self._state == CircuitState.CLOSED

    def _should_attempt_reset(self) -> bool:
        """Verificar si es momento de intentar resetear el circuit"""
        if self._state != CircuitState.OPEN:
            return False

        return time.time() >= self._next_attempt_time

    def _change_state(self, new_state: CircuitState, reason: str = ""):
        """Cambiar estado del circuit breaker con logging"""
        if new_state != self._state:
            old_state = self._state
            self._state = new_state

            # Registrar cambio de estado
            change_record = {
                "timestamp": time.time(),
                "from_state": old_state.value,
                "to_state": new_state.value,
                "reason": reason,
                "failure_count": self._failure_count,
            }
            state_changes = self._stats["state_changes"]
            assert isinstance(state_changes, list)
            state_changes.append(change_record)

            # Mantener solo los últimos 50 cambios
            if len(state_changes) > 50:
                self._stats["state_changes"] = state_changes[-50:]

            logger.warning(
                f"CircuitBreaker '{self.name}' state change: {old_state.value} -> {new_state.value} ({reason})"
            )

            # Actualizar métricas específicas
            if new_state == CircuitState.OPEN:
                opens = self._stats["circuit_opens"]
                assert isinstance(opens, int)
                self._stats["circuit_opens"] = opens + 1
            elif new_state == CircuitState.HALF_OPEN:
                half_opens = self._stats["circuit_half_opens"]
                assert isinstance(half_opens, int)
                self._stats["circuit_half_opens"] = half_opens + 1

    def record_success(self):
        """Registrar una llamada exitosa"""
        total = self._stats["total_calls"]
        assert isinstance(total, int)
        self._stats["total_calls"] = total + 1

        successful = self._stats["successful_calls"]
        assert isinstance(successful, int)
        self._stats["successful_calls"] = successful + 1

        if self._state == CircuitState.HALF_OPEN:
            # Éxito en half-open: cerrar el circuit
            self._failure_count = 0
            self._change_state(CircuitState.CLOSED, "successful call in half-open")
        elif self._state == CircuitState.CLOSED:
            # Reset failure count en estado normal
            self._failure_count = 0

    def record_failure(self, exception: Optional[Exception] = None):
        """Registrar una llamada fallida"""
        total = self._stats["total_calls"]
        assert isinstance(total, int)
        self._stats["total_calls"] = total + 1

        failed = self._stats["failed_calls"]
        assert isinstance(failed, int)
        self._stats["failed_calls"] = failed + 1

        self._failure_count += 1
        self._last_failure_time = time.time()

        exception_name = type(exception).__name__ if exception else "Unknown"
        logger.warning(f"CircuitBreaker '{self.name}' recorded failure #{self._failure_count}: {exception_name}")

        if self._state == CircuitState.HALF_OPEN:
            # Fallo en half-open: volver a abrir inmediatamente
            self._next_attempt_time = time.time() + self.recovery_timeout
            self._change_state(CircuitState.OPEN, f"failure in half-open: {exception_name}")
        elif self._state == CircuitState.CLOSED and self._failure_count >= self.failure_threshold:
            # Demasiados fallos: abrir el circuit
            self._next_attempt_time = time.time() + self.recovery_timeout
            self._change_state(CircuitState.OPEN, f"failure threshold reached: {self._failure_count}")

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Ejecutar función a través del circuit breaker.

        Args:
            func: Función a ejecutar (puede ser async o sync)
            *args, **kwargs: Argumentos para la función

        Returns:
            Resultado de la función

        Raises:
            CircuitBreakerError: Si el circuit está abierto
            Exception: Cualquier excepción de la función original
        """
        # Verificar estado del circuit
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._change_state(CircuitState.HALF_OPEN, "attempting recovery")
            else:
                remaining_time = self._next_attempt_time - time.time()
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is OPEN. Next attempt in {remaining_time:.1f}s"
                )

        # Ejecutar función
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            self.record_success()
            return result

        except self.expected_exception as e:
            self.record_failure(e)
            raise
        except Exception as e:
            # Excepción no esperada - no afecta el circuit breaker
            logger.debug(f"CircuitBreaker '{self.name}' - unexpected exception (not counted): {type(e).__name__}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del circuit breaker"""
        total_calls = self._stats["total_calls"]
        assert isinstance(total_calls, int)
        successful_calls = self._stats["successful_calls"]
        assert isinstance(successful_calls, int)

        success_rate = 0
        if total_calls > 0:
            success_rate = (successful_calls / total_calls) * 100

        state_changes = self._stats["state_changes"]
        assert isinstance(state_changes, list)

        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self._last_failure_time,
            "next_attempt_time": self._next_attempt_time if self._state == CircuitState.OPEN else None,
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "failed_calls": self._stats["failed_calls"],
            "success_rate": f"{success_rate:.1f}%",
            "circuit_opens": self._stats["circuit_opens"],
            "circuit_half_opens": self._stats["circuit_half_opens"],
            "recent_state_changes": state_changes[-5:],  # Últimos 5 cambios
        }

    def reset(self):
        """Resetear manualmente el circuit breaker"""
        logger.info(f"Manually resetting CircuitBreaker '{self.name}'")
        self._failure_count = 0
        self._last_failure_time = None
        self._next_attempt_time = 0
        self._change_state(CircuitState.CLOSED, "manual reset")


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: type = Exception,
    name: Optional[str] = None,
):
    """
    Decorador para aplicar circuit breaker a funciones.

    Args:
        failure_threshold: Número de fallos antes de abrir el circuit
        recovery_timeout: Tiempo en segundos antes de intentar recovery
        expected_exception: Tipo de excepción que cuenta como fallo
        name: Nombre del circuit breaker
    """

    def decorator(func):
        circuit_name = name or f"{func.__module__}.{func.__name__}"
        cb = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            name=circuit_name,
        )

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await cb.call(func, *args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(cb.call(func, *args, **kwargs))

        # Agregar métodos de control al wrapper
        wrapper = async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        # Type ignore for dynamic attributes - pyright doesn't understand we're adding attributes
        wrapper.circuit_breaker = cb  # type: ignore
        wrapper.get_stats = cb.get_stats  # type: ignore
        wrapper.reset = cb.reset  # type: ignore

        return wrapper

    return decorator


class ResilientLLMService:
    """
    Servicio LLM resiliente con circuit breaker y reintentos.

    Implementa las mejores prácticas del langgraph.md para servicios externos.
    """

    def __init__(self, llm_client, max_retries: int = 3, base_delay: float = 1.0):
        self.llm = llm_client
        self.max_retries = max_retries
        self.base_delay = base_delay

        # Circuit breaker específico para LLM
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30,
            expected_exception=Exception,  # Cualquier excepción cuenta
            name="llm_service",
        )

        # Prompt manager for health check prompts
        self.prompt_manager = PromptManager()

        logger.info(f"ResilientLLMService initialized - max_retries: {max_retries}, base_delay: {base_delay}s")

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        **kwargs,
    ) -> str:
        """
        Generar respuesta con circuit breaker y reintentos exponenciales.

        Args:
            system_prompt: Prompt del sistema
            user_prompt: Prompt del usuario
            model: Modelo a usar
            temperature: Temperatura para la generación
            **kwargs: Argumentos adicionales

        Returns:
            Respuesta generada por el LLM

        Raises:
            CircuitBreakerError: Si el circuit breaker está abierto
            Exception: Errores del LLM después de todos los reintentos
        """

        async def _make_llm_call():
            """Función interna para la llamada al LLM"""
            for attempt in range(self.max_retries):
                try:
                    # Calcular delay exponencial
                    if attempt > 0:
                        delay = self.base_delay * (2 ** (attempt - 1))
                        logger.debug(f"Retrying LLM call in {delay}s (attempt {attempt + 1}/{self.max_retries})")
                        await asyncio.sleep(delay)

                    # Hacer la llamada al LLM
                    response = await self.llm.generate_response(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        model=model,
                        temperature=temperature,
                        **kwargs,
                    )

                    return response

                except Exception as e:
                    logger.warning(f"LLM call attempt {attempt + 1} failed: {type(e).__name__}: {e}")

                    # Si es el último intento, re-lanzar la excepción
                    if attempt == self.max_retries - 1:
                        raise

            # Nunca debería llegar aquí, pero por seguridad
            raise Exception("All LLM retry attempts failed")

        # Ejecutar a través del circuit breaker
        return await self.circuit_breaker.call(_make_llm_call)

    def get_health_status(self) -> Dict[str, Any]:
        """Obtener estado de salud del servicio LLM"""
        circuit_stats = self.circuit_breaker.get_stats()

        # Determinar estado de salud general
        health_status = "healthy"
        if circuit_stats["state"] == "open":
            health_status = "unhealthy"
        elif circuit_stats["state"] == "half_open":
            health_status = "recovering"
        elif circuit_stats["success_rate"] != "0.0%" and float(circuit_stats["success_rate"].rstrip("%")) < 50:
            health_status = "degraded"

        return {
            "service": "llm",
            "status": health_status,
            "circuit_breaker": circuit_stats,
            "retry_config": {"max_retries": self.max_retries, "base_delay": self.base_delay},
        }

    async def health_check(self) -> bool:
        """Realizar health check básico"""
        try:
            # Load prompts from YAML
            system_prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.CORE_CIRCUIT_BREAKER_HEALTH_CHECK_SYSTEM,
            )
            user_prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.CORE_CIRCUIT_BREAKER_HEALTH_CHECK_USER,
            )

            # Intentar una llamada simple para verificar conectividad
            await self.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.0,
            )
            return True
        except Exception:
            return False
