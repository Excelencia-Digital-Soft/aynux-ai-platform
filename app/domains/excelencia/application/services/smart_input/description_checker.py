"""
Description quality checker with LLM fallback.

Validates problem descriptions for sufficient detail.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.integrations.llm import VllmLLM
from app.prompts import PromptRegistry

from .base import BaseInterpreter

if TYPE_CHECKING:
    from app.prompts import PromptManager

logger = logging.getLogger(__name__)


class DescriptionQualityChecker(BaseInterpreter):
    """Checks quality of problem descriptions."""

    async def check(
        self,
        description: str,
        llm: VllmLLM,
        prompt_manager: "PromptManager | None" = None,
    ) -> tuple[bool, str | None]:
        """
        Evaluate the quality of the problem description.

        Args:
            description: The problem description to evaluate
            llm: VllmLLM instance for LLM calls
            prompt_manager: Optional PromptManager for YAML templates

        Returns:
            (is_acceptable, improvement_suggestion)
        """
        # 1. Basic validation (no LLM)
        word_count = len(description.split())

        if word_count < 3:
            return (
                False,
                "Tu descripcion es muy corta. ¿Podrias dar mas detalles sobre el problema?",
            )

        if word_count < 8:
            # LLM to evaluate if sufficient
            return await self._llm_check(description, llm, prompt_manager)

        # Description is long enough
        return True, None

    async def _llm_check(
        self,
        description: str,
        llm: VllmLLM,
        prompt_manager: "PromptManager | None" = None,
    ) -> tuple[bool, str | None]:
        """Evaluate description with LLM."""
        fallback_prompt = f"""Evalua si la siguiente descripcion de un problema tecnico es suficientemente clara.

Descripcion: "{description}"

Criterios de calidad:
1. Describe que paso o que error ocurre
2. Da contexto sobre cuando o donde ocurre
3. Tiene suficiente informacion para que soporte pueda investigar

Responde en formato: ACEPTABLE|SUGERENCIA
- Si es aceptable: "yes|"
- Si necesita mejora: "no|[sugerencia breve de que agregar]"

Ejemplos:
- "no funciona" -> no|Podrias indicar que parte del sistema no funciona y que mensaje de error ves?
- "El modulo de facturacion da error al generar CFDI" -> yes|
- "pantalla azul" -> no|Podrias describir cuando aparece el problema y que estabas haciendo?"""

        prompt = await self._get_prompt_from_yaml(
            prompt_manager,
            PromptRegistry.EXCELENCIA_SMART_INPUT_DESCRIPTION_CHECK,
            {"description": description},
            fallback_prompt,
        )

        result = await self._invoke_llm(prompt, llm, temperature=0.3)

        if result is None:
            # On error, accept the description
            return True, None

        parts = result.split("|", 1)
        is_acceptable = parts[0].strip().lower() == "yes"
        suggestion = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None

        if not is_acceptable and not suggestion:
            suggestion = "¿Podrias agregar mas detalles sobre el problema?"

        logger.info(
            f"LLM evaluated description: acceptable={is_acceptable}, "
            f"suggestion={suggestion[:50] if suggestion else 'None'}..."
        )
        return is_acceptable, suggestion
