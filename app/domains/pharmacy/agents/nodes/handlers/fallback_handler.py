"""
Pharmacy Fallback Handler

Handles unknown intents, errors, cancellations, and out-of-scope messages.
"""

from __future__ import annotations

from typing import Any

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
        try:
            response = await self.prompt_manager.get_prompt("pharmacy.response.fallback")
        except ValueError:
            response = self._get_inline_fallback()

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
        if suggested_response:
            response = suggested_response
        else:
            try:
                response = await self.prompt_manager.get_prompt("pharmacy.response.fallback")
            except ValueError:
                response = self._get_inline_fallback()

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
            response = await self.prompt_manager.get_prompt("pharmacy.response.error")
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
            response = await self.prompt_manager.get_prompt("pharmacy.response.debt_rejected")
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

    def _get_inline_fallback(self) -> str:
        """Get inline fallback response when template is unavailable."""
        return """No entendí tu mensaje.

Puedo ayudarte con:
- Consultar tu deuda - "¿cuánto debo?"
- Confirmar deuda - "sí, confirmo"
- Generar recibo - "quiero pagar"
- Registrarte si eres cliente nuevo

¿En qué puedo ayudarte?"""
