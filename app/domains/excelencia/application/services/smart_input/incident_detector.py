"""
Incident intent detector with LLM fallback.

Detects if user wants to create a support incident.
"""

import logging
from typing import TYPE_CHECKING

from app.integrations.llm import OllamaLLM

from .base import BaseInterpreter, InterpretationResult
from .constants import INCIDENT_INTENT_KEYWORDS

if TYPE_CHECKING:
    from app.domains.excelencia.application.services.query_type_detector import (
        CompositeQueryTypeDetector,
    )

logger = logging.getLogger(__name__)


class IncidentIntentDetector(BaseInterpreter):
    """Detects incident creation intent."""

    async def detect(
        self,
        message: str,
        query_type_detector: "CompositeQueryTypeDetector",
        llm: OllamaLLM | None = None,
    ) -> InterpretationResult:
        """
        Detect if the user wants to create an incident.

        Uses the existing detector as first step, LLM as fallback.
        """
        # 1. Use existing detector (fuzzy + keywords)
        match = query_type_detector.detect(message)

        if match.query_type == "incident" and match.confidence >= 0.8:
            return InterpretationResult(
                success=True,
                value="incident",
                confidence=match.confidence,
                method="direct",
            )

        # 2. Additional keywords not covered by detector
        normalized = message.lower()
        for keyword in INCIDENT_INTENT_KEYWORDS:
            if keyword in normalized:
                return InterpretationResult(
                    success=True,
                    value="incident",
                    confidence=0.9,
                    method="direct",
                )

        # 3. LLM fallback for ambiguous phrases
        if llm and match.confidence < 0.6:
            return await self._llm_detect(message, llm)

        return InterpretationResult(
            success=False,
            value=match.query_type,
            confidence=match.confidence,
            method="direct",
        )

    async def _llm_detect(
        self,
        message: str,
        llm: OllamaLLM,
    ) -> InterpretationResult:
        """LLM fallback for incident intent detection."""
        prompt = f"""Determina si el usuario quiere reportar un problema tecnico o incidencia.

Mensaje: "{message}"

Indicadores de incidencia:
- Reporta un problema, bug, error o falla
- Algo no funciona como deberia
- El sistema esta caido o lento
- Quiere registrar un ticket de soporte

Responde SOLO: yes o no

Ejemplos:
- "oye, el sistema esta muy lento hoy" -> yes
- "como exporto un reporte?" -> no
- "la facturacion no me deja timbrar" -> yes
- "necesito capacitacion" -> no"""

        result = await self._invoke_llm(prompt, llm)

        if result is None:
            return InterpretationResult(success=False, method="llm")

        if result == "yes":
            logger.info(f"LLM detected incident intent: '{message[:50]}...'")
            return InterpretationResult(
                success=True,
                value="incident",
                confidence=0.75,
                method="llm",
            )

        return InterpretationResult(
            success=False,
            value="general",
            confidence=0.75,
            method="llm",
        )
