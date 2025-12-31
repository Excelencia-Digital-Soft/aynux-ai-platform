"""
Ticket Handler

Handles support ticket creation for incidents and feedback.
Single responsibility: create tickets and generate confirmation messages.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.database.async_db import get_async_db_context

from .base_handler import BaseExcelenciaHandler

logger = logging.getLogger(__name__)


@dataclass
class TicketResult:
    """Result of ticket creation."""

    success: bool
    ticket_id: str
    confirmation_message: str
    error: str | None = None


class TicketHandler(BaseExcelenciaHandler):
    """
    Handles support ticket creation for incidents and feedback.

    Creates tickets via use case and generates confirmation messages.
    """

    async def create_ticket(
        self,
        user_phone: str,
        ticket_type: str,
        description: str,
        category: str | None = None,
        module: str | None = None,
        conversation_id: str | None = None,
    ) -> TicketResult:
        """
        Create a support ticket and return result with confirmation.

        Args:
            user_phone: WhatsApp phone number
            ticket_type: Type of ticket ("incident" or "feedback")
            description: Full description from user message
            category: Optional category
            module: Optional affected module
            conversation_id: Optional conversation link

        Returns:
            TicketResult with success status, ticket ID, and confirmation message
        """
        try:
            from app.core.container import DependencyContainer

            async with get_async_db_context() as db:
                container = DependencyContainer()
                use_case = container.create_support_ticket_use_case(db)
                ticket = await use_case.execute(
                    user_phone=user_phone,
                    ticket_type=ticket_type,
                    description=description,
                    category=category,
                    module=module,
                    conversation_id=conversation_id,
                )

            confirmation = self._generate_confirmation(ticket, ticket_type)
            ticket_id = ticket.get("ticket_id_short", ticket.get("id", "")[:8].upper())

            return TicketResult(
                success=True,
                ticket_id=ticket_id,
                confirmation_message=confirmation,
            )

        except Exception as e:
            self.logger.error(f"Error creating support ticket: {e}")
            return TicketResult(
                success=False,
                ticket_id="ERROR",
                confirmation_message=self._generate_error_message(),
                error=str(e),
            )

    def _generate_confirmation(self, ticket: dict[str, Any], ticket_type: str) -> str:
        """
        Generate confirmation message for created ticket.

        Args:
            ticket: Ticket info dict from use case
            ticket_type: Type of ticket ("incident" or "feedback")

        Returns:
            Formatted confirmation message
        """
        ticket_id = ticket.get("ticket_id_short", ticket.get("id", "")[:8].upper())
        status = ticket.get("status", "open")

        if status == "failed":
            return self._generate_error_message()

        if ticket_type == "incident":
            category = ticket.get("category", "general")
            return (
                f"🎫 **Incidencia Registrada**\n\n"
                f"Tu reporte ha sido creado con el folio: **{ticket_id}**\n\n"
                f"- Categoria: {category}\n"
                f"- Estado: Abierto\n\n"
                f"Nuestro equipo de soporte lo revisara y te contactara pronto.\n"
                f"Hay algo mas en lo que pueda ayudarte?"
            )

        # feedback
        return (
            f"💬 **Gracias por tu Feedback**\n\n"
            f"Tu comentario ha sido registrado (Ref: {ticket_id}).\n\n"
            f"Valoramos mucho tu opinion para mejorar nuestros servicios.\n"
            f"Hay algo mas que quieras compartir?"
        )

    def _generate_error_message(self) -> str:
        """Generate error message for failed ticket creation."""
        return (
            "Lo siento, hubo un problema al registrar tu solicitud. "
            "Por favor, contacta directamente a soporte tecnico o intenta nuevamente. "
            "Hay algo mas en lo que pueda ayudarte?"
        )
