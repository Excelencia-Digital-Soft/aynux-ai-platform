"""
Confirmation interpreter with LLM fallback.

Interprets user confirmation responses and detects edit targets.
"""

import logging

from app.integrations.llm import OllamaLLM

from .base import BaseInterpreter, InterpretationResult
from .constants import (
    CONFIRMATION_CANCEL,
    CONFIRMATION_NO,
    CONFIRMATION_YES,
    EDIT_TARGET_DESCRIPTION,
    EDIT_TARGET_PRIORITY,
)

logger = logging.getLogger(__name__)


class ConfirmationInterpreter(BaseInterpreter):
    """Interprets confirmation responses with edit target detection."""

    async def interpret(
        self,
        message: str,
        llm: OllamaLLM | None = None,
    ) -> InterpretationResult:
        """
        Interpret user confirmation.

        Returns:
            InterpretationResult with:
            - value: "yes" | "no" | "cancel"
            - edit_request: "description" | "priority" (if user wants to edit)
        """
        normalized = message.lower().strip()

        # 1. Direct mapping YES
        if any(word in normalized for word in CONFIRMATION_YES):
            return InterpretationResult(
                success=True,
                value="yes",
                confidence=1.0,
                method="direct",
            )

        # 2. Direct mapping NO (with edit target detection)
        if any(word in normalized for word in CONFIRMATION_NO):
            edit_request = self._detect_edit_target(normalized)
            return InterpretationResult(
                success=True,
                value="no",
                confidence=1.0,
                method="direct",
                edit_request=edit_request,
            )

        # 3. Direct mapping CANCEL
        if any(word in normalized for word in CONFIRMATION_CANCEL):
            return InterpretationResult(
                success=True,
                value="cancel",
                confidence=1.0,
                method="direct",
            )

        # 4. LLM fallback
        if llm is None:
            return InterpretationResult(success=False, method="direct")

        return await self._llm_interpret(message, llm)

    def _detect_edit_target(self, message: str) -> str | None:
        """Detect which field the user wants to edit."""
        if any(w in message for w in EDIT_TARGET_DESCRIPTION):
            return "description"
        if any(w in message for w in EDIT_TARGET_PRIORITY):
            return "priority"
        return None

    async def _llm_interpret(
        self,
        message: str,
        llm: OllamaLLM,
    ) -> InterpretationResult:
        """LLM fallback for confirmation interpretation."""
        prompt = f"""Analiza el siguiente mensaje y determina la intencion del usuario.

Mensaje: "{message}"

Contexto: El usuario esta confirmando si quiere crear una incidencia de soporte.

Opciones:
- yes: El usuario confirma que SI quiere crear la incidencia
- no: El usuario quiere corregir o cambiar algo
- cancel: El usuario quiere cancelar todo el proceso

Responde en formato: INTENCION|CAMPO_A_EDITAR
- Si es "yes" o "cancel": responde solo la intencion (ej: "yes")
- Si es "no" y menciona que quiere cambiar: responde "no|description" o "no|priority"
- Si es "no" sin especificar: responde "no"

Ejemplos:
- "si perfecto" -> yes
- "quiero cambiar la prioridad" -> no|priority
- "no, la descripcion esta mal" -> no|description
- "olvidalo" -> cancel

Responde SOLO con el formato indicado."""

        result = await self._invoke_llm(prompt, llm)

        if result is None:
            return InterpretationResult(success=False, method="llm")

        # Parse response
        parts = result.split("|")
        intention = parts[0].strip()
        edit_target = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None

        if intention in {"yes", "no", "cancel"}:
            logger.info(
                f"LLM interpreted confirmation: '{message}' -> {intention}"
                f" (edit_target: {edit_target})"
            )
            return InterpretationResult(
                success=True,
                value=intention,
                confidence=0.8,
                method="llm",
                edit_request=edit_target,
            )

        logger.warning(f"LLM could not determine confirmation for: '{message}'")
        return InterpretationResult(success=False, method="llm")
