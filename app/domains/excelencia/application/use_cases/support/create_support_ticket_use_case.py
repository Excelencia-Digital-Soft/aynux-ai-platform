"""
Create Support Ticket Use Case.

Creates support tickets (incidents, feedback, questions) from chat interactions.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.support_ticket import SupportTicket

logger = logging.getLogger(__name__)


class CreateSupportTicketUseCase:
    """
    Use Case: Create Support Ticket

    Creates a new support ticket from a user's chat interaction.
    Handles incidents, feedback, questions, and suggestions.

    Responsibilities:
    - Validate ticket data
    - Create ticket in database
    - Return ticket info for confirmation message

    Follows SRP: Single responsibility for ticket creation logic
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize create use case with database session.

        Args:
            db: Async database session
        """
        self.db = db

    async def execute(
        self,
        user_phone: str,
        ticket_type: str,
        description: str,
        subject: str | None = None,
        category: str | None = None,
        module: str | None = None,
        conversation_id: str | UUID | None = None,
        user_name: str | None = None,
        priority: str = "medium",
        meta_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a new support ticket.

        Args:
            user_phone: WhatsApp phone number of the user
            ticket_type: Type of ticket (incident, feedback, question, suggestion)
            description: Full description of the issue/feedback
            subject: Brief subject/title (auto-generated from description if not provided)
            category: Category (tecnico, facturacion, capacitacion, etc.)
            module: Affected module if applicable
            conversation_id: Link to the conversation where ticket was created
            user_name: Name of the user (if known)
            priority: Ticket priority (low, medium, high, critical)
            meta_data: Additional context from chat

        Returns:
            Dictionary with created ticket info

        Raises:
            ValueError: If validation fails

        Example:
            use_case = CreateSupportTicketUseCase(db)
            result = await use_case.execute(
                user_phone="+521234567890",
                ticket_type="incident",
                description="El sistema no me permite facturar...",
                category="facturacion",
                module="facturacion",
            )
        """
        try:
            # Validate required fields
            if not user_phone:
                raise ValueError("User phone is required")
            if not ticket_type:
                raise ValueError("Ticket type is required")
            if ticket_type not in ("incident", "feedback", "question", "suggestion"):
                raise ValueError(
                    f"Invalid ticket type: {ticket_type}. "
                    "Must be one of: incident, feedback, question, suggestion"
                )
            if not description:
                raise ValueError("Description is required")

            # Validate priority
            if priority not in ("low", "medium", "high", "critical"):
                priority = "medium"

            # Auto-generate subject if not provided
            if not subject:
                # Take first 100 chars, truncate at word boundary
                subject = description[:100]
                if len(description) > 100:
                    last_space = subject.rfind(" ")
                    if last_space > 50:
                        subject = subject[:last_space]
                    subject += "..."

            # Convert conversation_id to UUID if string
            conv_id = None
            if conversation_id:
                if isinstance(conversation_id, str):
                    try:
                        conv_id = UUID(conversation_id)
                    except ValueError:
                        logger.warning(f"Invalid conversation_id format: {conversation_id}")
                else:
                    conv_id = conversation_id

            # Create ticket
            ticket = SupportTicket(
                user_phone=user_phone,
                user_name=user_name,
                conversation_id=conv_id,
                ticket_type=ticket_type,
                category=category or self._infer_category(description, ticket_type),
                module=module,
                subject=subject,
                description=description,
                status="open",
                priority=priority,
                meta_data=meta_data or {},
            )

            self.db.add(ticket)
            await self.db.commit()
            await self.db.refresh(ticket)

            result = {
                "id": str(ticket.id),
                "ticket_id_short": ticket.ticket_id_short,
                "ticket_type": ticket.ticket_type,
                "subject": ticket.subject,
                "status": ticket.status,
                "priority": ticket.priority,
                "category": ticket.category,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            }

            logger.info(
                f"Created support ticket: {ticket.id} "
                f"(type={ticket_type}, category={ticket.category})"
            )
            return result

        except ValueError:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating support ticket: {e}")
            raise

    def _infer_category(self, description: str, ticket_type: str) -> str:
        """
        Infer category from description content.

        Args:
            description: Ticket description
            ticket_type: Type of ticket

        Returns:
            Inferred category string
        """
        description_lower = description.lower()

        # Technical keywords
        if any(kw in description_lower for kw in [
            "error", "falla", "bug", "no funciona", "problema técnico",
            "se cae", "lento", "no carga", "pantalla", "mensaje de error"
        ]):
            return "tecnico"

        # Billing/invoicing keywords
        if any(kw in description_lower for kw in [
            "factura", "cfdi", "timbrado", "sat", "cancelar factura",
            "folio", "comprobante", "impuesto"
        ]):
            return "facturacion"

        # Training keywords
        if any(kw in description_lower for kw in [
            "capacitación", "curso", "aprender", "manual", "tutorial",
            "entrenamiento", "formación", "cómo usar"
        ]):
            return "capacitacion"

        # Module-specific keywords
        if any(kw in description_lower for kw in [
            "inventario", "almacén", "stock", "existencias"
        ]):
            return "inventario"

        if any(kw in description_lower for kw in [
            "nómina", "empleado", "sueldo", "pago", "trabajador"
        ]):
            return "nomina"

        if any(kw in description_lower for kw in [
            "contabilidad", "balance", "póliza", "cuenta contable"
        ]):
            return "contabilidad"

        # Default based on ticket type
        if ticket_type == "feedback":
            return "sugerencias"
        if ticket_type == "question":
            return "consultas"

        return "general"
