"""
Step handlers for incident creation flow.

Each handler processes a specific step in the multi-step flow.
"""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.database.async_db import get_async_db_context
from app.domains.excelencia.application.services.smart_input import SmartInputInterpreter
from app.integrations.llm import OllamaLLM

from .flow_prompts import FlowPromptService

if TYPE_CHECKING:
    from app.models.db.soporte import PendingTicket

logger = logging.getLogger(__name__)


@dataclass
class FlowContext:
    """Context passed to step handlers."""

    state_dict: dict[str, Any]
    prompts: FlowPromptService
    interpreter: SmartInputInterpreter
    ollama: OllamaLLM


class DescriptionStepHandler:
    """Handles the description step."""

    async def handle(
        self,
        message: str,
        pending_ticket: "PendingTicket",
        context: FlowContext,
    ) -> str:
        """Validate description quality and save if acceptable."""
        # Check description quality
        is_acceptable, suggestion = await context.interpreter.check_description_quality(
            message,
            context.ollama,
        )

        if not is_acceptable and suggestion:
            return (
                f"{suggestion}\n\n"
                "Cuanta mas informacion proporciones, mejor podremos ayudarte."
            )

        # Save description and move to priority step
        conversation_id = str(pending_ticket.conversation_id)

        async with get_async_db_context() as db:
            from app.core.container import DependencyContainer

            container = DependencyContainer()
            use_case = container.save_pending_ticket_use_case(db)
            await use_case.set_description(conversation_id, message)

        return await context.prompts.get_ask_priority()


class PriorityStepHandler:
    """Handles the priority step."""

    async def handle(
        self,
        message: str,
        pending_ticket: "PendingTicket",
        context: FlowContext,
    ) -> str:
        """Interpret priority and move to confirmation step."""
        # Use smart interpretation
        result = await context.interpreter.interpret_priority(message, llm=context.ollama)

        if not result.success:
            return await context.prompts.get_invalid_selection(
                "Por favor responde con un numero (1-4) o describe la urgencia "
                "(ej: 'es urgente', 'puede esperar')."
            )

        priority_value = result.value or "medium"
        priority_display = context.interpreter.get_priority_display(priority_value)

        if result.method == "llm":
            logger.info(
                f"Priority interpreted via LLM: '{message}' -> {priority_value} "
                f"(confidence: {result.confidence})"
            )

        # Save priority
        conversation_id = str(pending_ticket.conversation_id)

        async with get_async_db_context() as db:
            from app.core.container import DependencyContainer

            container = DependencyContainer()
            use_case = container.save_pending_ticket_use_case(db)
            await use_case.set_priority(conversation_id, priority_value)

        # Build confirmation
        description = pending_ticket.collected_data.get("description", "")
        description_preview = description[:150] + "..." if len(description) > 150 else description

        return await context.prompts.get_confirmation(description_preview, priority_display)


class ConfirmationStepHandler:
    """Handles the confirmation step."""

    async def handle(
        self,
        message: str,
        pending_ticket: "PendingTicket",
        context: FlowContext,
    ) -> str | tuple[str, str]:
        """
        Interpret confirmation response.

        Returns:
            str: Response message, or
            tuple[str, action]: (response, action) where action is "create", "reset_priority",
                               "reset_description", or "cancel"
        """
        result = await context.interpreter.interpret_confirmation(message, llm=context.ollama)

        if not result.success:
            return await context.prompts.get_invalid_selection(
                "Por favor confirma: SI para crear, NO para corregir, o CANCELAR para descartar."
            )

        if result.method == "llm":
            logger.info(
                f"Confirmation interpreted via LLM: '{message}' -> {result.value} "
                f"(confidence: {result.confidence}, edit_request: {result.edit_request})"
            )

        # Return action for flow manager to handle
        if result.value == "yes":
            return ("", "create")
        elif result.value == "no":
            if result.edit_request == "priority":
                return ("", "reset_priority")
            return ("", "reset_description")
        elif result.value == "cancel":
            return ("", "cancel")

        return ("", "cancel")
