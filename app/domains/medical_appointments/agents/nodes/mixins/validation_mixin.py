# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Validation mixin for LangGraph nodes.
# ============================================================================
"""Validation Mixin.

Provides input validation helpers for LangGraph nodes.
Single Responsibility: Validate and extract user input.
"""

import re


class ValidationMixin:
    """Mixin providing input validation helpers.

    Usage:
        class MyNode(BaseNode, ValidationMixin):
            async def process(self, state):
                message = self._get_message(state)
                if self._is_confirmation(message):
                    ...
    """

    def _is_confirmation(self, message: str) -> bool:
        """Check if message is a confirmation.

        Args:
            message: User message.

        Returns:
            True if message indicates confirmation.
        """
        confirmations = ["sí", "si", "yes", "confirmo", "confirmar", "ok", "dale", "1"]
        message_lower = message.lower().strip()
        return any(c in message_lower for c in confirmations)

    def _is_cancellation(self, message: str) -> bool:
        """Check if message is a cancellation.

        Args:
            message: User message.

        Returns:
            True if message indicates cancellation.
        """
        cancellations = ["no", "cancelar", "cancel", "salir", "volver", "2"]
        message_lower = message.lower().strip()
        return any(c in message_lower for c in cancellations)

    def _is_valid_document(self, message: str) -> bool:
        """Check if message is a valid DNI (7-8 digits).

        Args:
            message: User message.

        Returns:
            True if message contains a valid document number.
        """
        cleaned = message.replace(".", "").replace(" ", "").strip()
        return bool(re.match(r"^\d{7,8}$", cleaned))

    def _extract_document(self, message: str) -> str:
        """Extract document number from message.

        Args:
            message: User message.

        Returns:
            Extracted document number or empty string.
        """
        cleaned = message.replace(".", "").replace(" ", "").strip()
        match = re.search(r"\d{7,8}", cleaned)
        return match.group() if match else ""
