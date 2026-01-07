"""
Pharmacy Greeting Handler

Handles greeting messages using LLM for natural responses.
Refactored to use PromptRegistry for type-safe prompt references.
"""

from __future__ import annotations

from typing import Any

from app.integrations.llm import ModelComplexity
from app.prompts.registry import PromptRegistry

from .base_handler import BasePharmacyHandler

# LLM configuration
GREETING_LLM_TEMPERATURE = 0.7


class GreetingHandler(BasePharmacyHandler):
    """
    Handle greeting messages for pharmacy domain.

    Uses LLM to generate natural, personalized greeting responses
    with fallback to inline templates.
    """

    async def handle(
        self,
        message: str,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Handle greeting message.

        Args:
            message: User greeting message
            state: Current state dictionary

        Returns:
            State updates with greeting response
        """
        state = state or {}
        customer_name = state.get("customer_name", "")
        pharmacy_name = state.get("pharmacy_name", "la farmacia")

        try:
            capabilities = await self.prompt_manager.get_prompt(
                PromptRegistry.PHARMACY_RESPONSE_CAPABILITIES
            )
            greeting = await self._generate_greeting_with_llm(
                user_message=message,
                customer_name=customer_name,
                pharmacy_name=pharmacy_name,
                capabilities=capabilities,
            )
        except Exception as e:
            self.logger.warning(f"LLM greeting failed, using fallback: {e}")
            greeting = self._get_inline_greeting(customer_name, pharmacy_name)

        return self._format_state_update(
            message=greeting,
            intent_type="greeting",
            workflow_step="greeted",
            state=state,
        )

    async def _generate_greeting_with_llm(
        self,
        user_message: str,
        customer_name: str,
        pharmacy_name: str,
        capabilities: str,
    ) -> str:
        """
        Generate natural greeting using LLM.

        Args:
            user_message: Original user greeting message
            customer_name: Customer name if identified
            pharmacy_name: Pharmacy name for personalization
            capabilities: Bot capabilities text

        Returns:
            Generated greeting text
        """
        response = await self._generate_llm_response(
            template_key=PromptRegistry.PHARMACY_GREETING_GENERATE,
            variables={
                "user_message": user_message,
                "customer_name": customer_name or "Cliente",
                "pharmacy_name": pharmacy_name,
                "capabilities": capabilities,
            },
            complexity=ModelComplexity.SIMPLE,
            temperature=GREETING_LLM_TEMPERATURE,
        )

        if response:
            return response

        self.logger.warning("LLM response empty, using fallback")
        return self._get_inline_greeting(customer_name, pharmacy_name)

    def _get_inline_greeting(
        self, customer_name: str = "", pharmacy_name: str = "la farmacia"
    ) -> str:
        """Get inline greeting response when template is unavailable."""
        name_part = f" {customer_name}" if customer_name else ""
        greeting_start = f"¡Hola{name_part}!" if name_part else "¡Hola!"
        return f"""{greeting_start} Soy el asistente virtual de {pharmacy_name}.

Actualmente puedo ayudarte con:
• Consulta de deuda en cuenta corriente
• Envio de link de pago

Para otros asuntos, te indicare los canales adecuados.
¿En que puedo asistirte?"""
