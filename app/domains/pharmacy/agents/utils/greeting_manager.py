"""
Greeting Manager

Manages greeting state tracking and greeting message formatting.
Single responsibility: greeting state management for identification flow.
"""

from __future__ import annotations

from datetime import date
from typing import Any


class GreetingManager:
    """
    Manager for greeting state tracking.

    Single responsibility: Track whether customer has been greeted today
    and format personalized greeting messages.
    """

    def should_greet(self, state: dict[str, Any]) -> bool:
        """
        Check if customer should be greeted (not greeted today).

        Args:
            state: Current state dictionary

        Returns:
            True if customer should receive a greeting
        """
        if state.get("greeted_today"):
            last_date = state.get("last_greeting_date")
            if last_date == date.today().isoformat():
                return False  # Already greeted today
        return True  # Should greet

    def get_greeting_state_update(self) -> dict[str, Any]:
        """
        Return state updates for greeting tracking.

        Returns:
            Dictionary with greeted_today and last_greeting_date
        """
        return {
            "greeted_today": True,
            "last_greeting_date": date.today().isoformat(),
        }

    def format_greeting(
        self,
        customer_name: str,
        pharmacy_name: str,
        greeting_type: str = "welcome",
    ) -> str:
        """
        Format personalized greeting message with bot identity and capabilities.

        Args:
            customer_name: Customer display name
            pharmacy_name: Pharmacy name
            greeting_type: Type of greeting (welcome, found, selected)

        Returns:
            Formatted greeting message with bot identity and capabilities
        """
        # Greeting opener based on type
        if greeting_type == "found":
            opener = f"¡Te encontré, {customer_name}!"
        elif greeting_type == "selected":
            opener = f"¡Perfecto, {customer_name}!"
        else:  # welcome (default)
            opener = f"¡Hola {customer_name}!"

        # Bot identity and capabilities (consistent across all types)
        return f"""{opener} Soy el asistente virtual de {pharmacy_name}.

Actualmente puedo ayudarte con:
• Consulta de deuda en cuenta corriente
• Envío de link de pago

Para otros asuntos, te indicaré los canales adecuados.
¿En qué puedo asistirte?"""

    def apply_greeting_if_needed(
        self,
        result: dict[str, Any],
        customer_name: str,
        pharmacy_name: str,
        state: dict[str, Any],
        greeting_type: str = "welcome",
    ) -> dict[str, Any]:
        """
        Apply greeting to result if customer should be greeted.

        Args:
            result: Result dictionary to modify
            customer_name: Customer display name
            pharmacy_name: Pharmacy name
            state: Current state dictionary
            greeting_type: Type of greeting

        Returns:
            Modified result with greeting state if applicable
        """
        if self.should_greet(state):
            greeting = self.format_greeting(customer_name, pharmacy_name, greeting_type)
            result["pending_greeting"] = greeting
            result.update(self.get_greeting_state_update())
        return result
