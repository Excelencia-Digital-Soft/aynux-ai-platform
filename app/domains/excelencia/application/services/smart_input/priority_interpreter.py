"""
Priority interpreter with LLM fallback.

Interprets user priority selection from numbers or natural language.
"""

import logging

from app.integrations.llm import OllamaLLM

from .base import BaseInterpreter, InterpretationResult
from .constants import PRIORITY_DIRECT_MAP, PRIORITY_DISPLAY

logger = logging.getLogger(__name__)


class PriorityInterpreter(BaseInterpreter):
    """Interprets priority selection with direct mapping and LLM fallback."""

    async def interpret(
        self,
        message: str,
        llm: OllamaLLM | None = None,
    ) -> InterpretationResult:
        """
        Interpret priority selection.

        Flow:
        1. Normalize input
        2. Search direct mapping
        3. If no match -> LLM fallback
        """
        normalized = message.lower().strip()

        # 1. Direct mapping (fast)
        if normalized in PRIORITY_DIRECT_MAP:
            return InterpretationResult(
                success=True,
                value=PRIORITY_DIRECT_MAP[normalized],
                confidence=1.0,
                method="direct",
            )

        # 2. Search keyword in the message
        for keyword, priority in PRIORITY_DIRECT_MAP.items():
            if keyword in normalized:
                return InterpretationResult(
                    success=True,
                    value=priority,
                    confidence=0.9,
                    method="direct",
                )

        # 3. LLM fallback (only if necessary)
        if llm is None:
            return InterpretationResult(success=False, method="direct")

        return await self._llm_interpret(message, llm)

    async def _llm_interpret(
        self,
        message: str,
        llm: OllamaLLM,
    ) -> InterpretationResult:
        """LLM fallback for priority interpretation."""
        prompt = f"""Analiza el siguiente mensaje del usuario e identifica la prioridad que indica.

Mensaje: "{message}"

Opciones de prioridad:
- critical: Sistema caido, urgente, bloqueante, critico
- high: Importante, afecta trabajo, serio
- medium: Molestia, inconveniente, puede esperar
- low: Menor, baja importancia, cuando puedas

Responde SOLO con una de estas palabras: critical, high, medium, low, unknown

Si no puedes determinar la prioridad, responde: unknown"""

        result = await self._invoke_llm(prompt, llm)

        if result is None:
            return InterpretationResult(success=False, method="llm")

        # Clean response
        result = result.replace(".", "").replace(",", "").strip()

        valid_priorities = {"critical", "high", "medium", "low"}
        if result in valid_priorities:
            logger.info(f"LLM interpreted priority: '{message}' -> {result}")
            return InterpretationResult(
                success=True,
                value=result,
                confidence=0.8,
                method="llm",
            )

        logger.warning(f"LLM could not determine priority for: '{message}' (got: {result})")
        return InterpretationResult(success=False, method="llm")

    def get_display_name(self, priority_value: str) -> str:
        """Get display name for a priority value."""
        return PRIORITY_DISPLAY.get(priority_value, priority_value.title())
