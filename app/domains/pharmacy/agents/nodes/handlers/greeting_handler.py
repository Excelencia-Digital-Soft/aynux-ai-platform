"""
Pharmacy Greeting Handler

Handles greeting messages using LLM for natural responses.
"""

from __future__ import annotations

from typing import Any

from app.integrations.llm import ModelComplexity

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

        try:
            capabilities = await self.prompt_manager.get_prompt("pharmacy.response.capabilities")
            greeting = await self._generate_greeting_with_llm(
                user_message=message,
                customer_name=customer_name,
                capabilities=capabilities,
            )
        except Exception as e:
            self.logger.warning(f"LLM greeting failed, using fallback: {e}")
            greeting = self._get_inline_greeting(customer_name)

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
        capabilities: str,
    ) -> str:
        """
        Generate natural greeting using LLM.

        Args:
            user_message: Original user greeting message
            customer_name: Customer name if identified
            capabilities: Bot capabilities text

        Returns:
            Generated greeting text
        """
        response = await self._generate_llm_response(
            template_key="pharmacy.greeting.generate",
            variables={
                "user_message": user_message,
                "customer_name": customer_name or "Cliente",
                "capabilities": capabilities,
            },
            complexity=ModelComplexity.SIMPLE,
            temperature=GREETING_LLM_TEMPERATURE,
        )

        if response:
            return response

        self.logger.warning("LLM response empty, using fallback")
        return self._get_inline_greeting(customer_name)

    def _get_inline_greeting(self, customer_name: str = "") -> str:
        """Get inline greeting response when template is unavailable."""
        name_part = f" {customer_name}" if customer_name else ""
        return f"""¡Hola{name_part}!

Puedo ayudarte con:
- Consultar tu deuda/saldo pendiente
- Confirmar deuda para pago
- Generar recibo/factura
- Registrarte como cliente nuevo

¿En qué puedo ayudarte?"""
