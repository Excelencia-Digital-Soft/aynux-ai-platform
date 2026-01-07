"""
Pharmacy Fallback Handler

Handles unknown intents, errors, cancellations, and out-of-scope messages.
Refactored to use PromptRegistry for type-safe prompt references.
"""

from __future__ import annotations

from typing import Any

from app.prompts.registry import PromptRegistry

from .base_handler import BasePharmacyHandler


class FallbackHandler(BasePharmacyHandler):
    """
    Handle fallback scenarios for pharmacy domain.

    Handles:
    - Unknown/unrecognized intents
    - Out-of-scope messages
    - Processing errors
    - User cancellations
    """

    async def handle_unknown(
        self,
        message: str,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Handle unknown/out-of-scope message.

        Args:
            message: Original user message
            state: Current state dictionary

        Returns:
            State updates with fallback response
        """
        state = state or {}
        pharmacy_phone = state.get("pharmacy_phone", "la farmacia")

        try:
            response = await self.prompt_manager.get_prompt(
                PromptRegistry.PHARMACY_RESPONSE_OUT_OF_SCOPE,
                variables={"pharmacy_phone": pharmacy_phone},
            )
        except ValueError:
            response = self._get_inline_fallback(pharmacy_phone)

        self.logger.info(f"Handling unknown intent for message: '{message[:30]}...'")

        return self._format_state_update(
            message=response,
            intent_type="unknown",
            workflow_step="fallback",
            state=state,
            is_out_of_scope=True,
        )

    async def handle_out_of_scope(
        self,
        message: str,
        suggested_response: str | None = None,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Handle message that is clearly out of scope.

        Args:
            message: Original user message
            suggested_response: Optional suggested response from intent analyzer
            state: Current state dictionary

        Returns:
            State updates with out-of-scope response
        """
        state = state or {}
        pharmacy_phone = state.get("pharmacy_phone", "la farmacia")

        if suggested_response:
            response = suggested_response
        else:
            try:
                response = await self.prompt_manager.get_prompt(
                    PromptRegistry.PHARMACY_RESPONSE_OUT_OF_SCOPE,
                    variables={"pharmacy_phone": pharmacy_phone},
                )
            except ValueError:
                response = self._get_inline_fallback(pharmacy_phone)

        self.logger.info(f"Out of scope message: '{message[:30]}...'")

        return self._format_state_update(
            message=response,
            intent_type="out_of_scope",
            workflow_step="fallback",
            state=state,
            is_out_of_scope=True,
        )

    async def handle_error(
        self,
        error: str | Exception,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Handle processing error gracefully.

        Args:
            error: Error message or exception
            state: Current state dictionary

        Returns:
            State updates with error response
        """
        state = state or {}

        try:
            response = await self.prompt_manager.get_prompt(
                PromptRegistry.PHARMACY_RESPONSE_ERROR
            )
        except ValueError:
            response = "Disculpa, tuve un problema. Por favor intenta de nuevo."

        self.logger.error(f"Pharmacy error: {error}")

        return self._format_state_update(
            message=response,
            intent_type="error",
            workflow_step="error",
            state=state,
            error_count=state.get("error_count", 0) + 1,
        )

    async def handle_cancelled(
        self,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Handle user cancellation/rejection.

        Args:
            state: Current state dictionary

        Returns:
            State updates with cancellation response
        """
        try:
            response = await self.prompt_manager.get_prompt(
                PromptRegistry.PHARMACY_RESPONSE_DEBT_REJECTED
            )
        except ValueError:
            response = "Entendido. La operación ha sido cancelada.\n\n" "¿Hay algo más en que pueda ayudarte?"

        return self._format_state_update(
            message=response,
            intent_type="cancelled",
            workflow_step="cancelled",
            state=state,
            is_complete=True,
            awaiting_confirmation=False,
            debt_status="cancelled",
        )

    def _get_inline_fallback(self, pharmacy_phone: str = "la farmacia") -> str:
        """Get inline fallback response when template is unavailable."""
        return f"""*Para mejor atencion*
Actualmente solo manejo consultas de deuda y envio de links de pago.
Para otros asuntos, te recomiendo contactar a nuestros canales especializados:
• *Pedidos y entregas*: {pharmacy_phone}
• *Consultas medicas/recetas*: {pharmacy_phone}
• *Horarios y sucursales*: {pharmacy_phone}"""

    async def handle_farewell(
        self,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Handle farewell/goodbye message.

        Args:
            state: Current state dictionary

        Returns:
            State updates with farewell response
        """
        state = state or {}
        pharmacy_name = state.get("pharmacy_name") or "la farmacia"
        pharmacy_phone = state.get("pharmacy_phone") or "la farmacia"

        try:
            response = await self.prompt_manager.get_prompt(
                PromptRegistry.PHARMACY_RESPONSE_FAREWELL,
                variables={
                    "pharmacy_name": pharmacy_name,
                    "pharmacy_phone": pharmacy_phone,
                },
            )
        except ValueError:
            response = f"""Gracias por contactar a {pharmacy_name}.
Recuerda que para:
• Deudas: puedes escribirme directamente
• Otros temas: {pharmacy_phone}
¡Que tengas un excelente dia!"""

        return self._format_state_update(
            message=response,
            intent_type="farewell",
            workflow_step="farewell",
            state=state,
            is_complete=True,
        )

    async def handle_thanks(
        self,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Handle thanks/gratitude message.

        Args:
            state: Current state dictionary

        Returns:
            State updates with thanks response
        """
        try:
            response = await self.prompt_manager.get_prompt(
                PromptRegistry.PHARMACY_RESPONSE_THANKS
            )
        except ValueError:
            response = """¡De nada! Es un placer poder ayudarte.
No dudes en escribirme nuevamente si necesitas consultar tu deuda o solicitar el link de pago.
¡Cuidate mucho!"""

        return self._format_state_update(
            message=response,
            intent_type="thanks",
            workflow_step="thanks",
            state=state,
            is_complete=False,  # Allow continued conversation
        )
