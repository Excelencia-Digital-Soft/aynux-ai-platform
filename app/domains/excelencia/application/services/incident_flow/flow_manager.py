"""
Incident flow manager.

Orchestrates the multi-step incident creation flow.
"""

import logging
from typing import TYPE_CHECKING, Any

from app.database.async_db import get_async_db_context
from app.domains.excelencia.application.services.smart_input import SmartInputInterpreter
from app.domains.excelencia.application.use_cases.support import CreateIncidentUseCase
from app.integrations.llm import OllamaLLM
from app.prompts.manager import PromptManager

from .flow_prompts import FlowPromptService
from .step_handlers import (
    ConfirmationStepHandler,
    DescriptionStepHandler,
    FlowContext,
    PriorityStepHandler,
)

if TYPE_CHECKING:
    from app.models.db.soporte import PendingTicket

logger = logging.getLogger(__name__)


class IncidentFlowManager:
    """Manages the multi-step incident creation flow."""

    def __init__(
        self,
        ollama: OllamaLLM | None = None,
        prompt_manager: PromptManager | None = None,
        input_interpreter: SmartInputInterpreter | None = None,
    ):
        """Initialize the flow manager."""
        self._ollama = ollama or OllamaLLM()
        self._prompts = FlowPromptService(prompt_manager)
        self._interpreter = input_interpreter or SmartInputInterpreter()

        self._handlers = {
            "description": DescriptionStepHandler(),
            "priority": PriorityStepHandler(),
            "confirmation": ConfirmationStepHandler(),
        }

    async def get_active_flow(self, state_dict: dict[str, Any]) -> "PendingTicket | None":
        """Check if there's an active incident creation flow."""
        try:
            conversation_id = state_dict.get("conversation_id")
            user_phone = state_dict.get("user_phone", state_dict.get("sender"))

            if not conversation_id and not user_phone:
                return None

            async with get_async_db_context() as db:
                from app.core.container import DependencyContainer

                container = DependencyContainer()
                use_case = container.get_pending_ticket_use_case(db)

                if conversation_id:
                    return await use_case.execute(str(conversation_id))
                elif user_phone:
                    return await use_case.execute_by_phone(user_phone)

            return None
        except Exception as e:
            logger.error(f"Error checking active incident flow: {e}")
            return None

    async def start_flow(self, state_dict: dict[str, Any]) -> str:
        """Start the incident creation flow."""
        try:
            conversation_id = state_dict.get("conversation_id")
            if not conversation_id:
                logger.error("No conversation_id in state_dict")
                return await self._prompts.get_error_message()

            user_phone = state_dict.get("user_phone", state_dict.get("sender", "unknown"))

            async with get_async_db_context() as db:
                from app.core.container import DependencyContainer

                container = DependencyContainer()
                use_case = container.save_pending_ticket_use_case(db)

                await use_case.create(
                    conversation_id=str(conversation_id),
                    user_phone=user_phone,
                    current_step="description",
                )

            return await self._prompts.get_flow_start()

        except Exception as e:
            logger.error(f"Error starting incident flow: {e}")
            return await self._prompts.get_error_message()

    async def handle_step(
        self,
        message: str,
        pending_ticket: "PendingTicket",
        state_dict: dict[str, Any],
    ) -> str:
        """Route to appropriate handler based on current step."""
        step = str(pending_ticket.current_step)
        handler = self._handlers.get(step)

        if not handler:
            await self.cancel_flow(state_dict)
            return "Hubo un error en el proceso. Por favor, di 'quiero reportar una incidencia' para comenzar de nuevo."

        context = FlowContext(
            state_dict=state_dict,
            prompts=self._prompts,
            interpreter=self._interpreter,
            ollama=self._ollama,
        )

        result = await handler.handle(message, pending_ticket, context)

        # Handle confirmation step actions
        if isinstance(result, tuple):
            _, action = result
            if action == "create":
                return await self._create_incident(pending_ticket, state_dict)
            elif action == "reset_priority":
                return await self.reset_flow(pending_ticket, "priority")
            elif action == "reset_description":
                return await self.reset_flow(pending_ticket, "description")
            elif action == "cancel":
                return await self.cancel_flow(state_dict)
            # Fallback for unknown action
            return await self.cancel_flow(state_dict)

        return result

    async def _create_incident(
        self,
        pending_ticket: "PendingTicket",
        state_dict: dict[str, Any],
    ) -> str:
        """Create the actual incident from pending ticket data."""
        try:
            collected_data = pending_ticket.collected_data or {}
            description = collected_data.get("description", "")
            priority = collected_data.get("priority", "medium")

            category_code = CreateIncidentUseCase.infer_category_code(description)

            async with get_async_db_context() as db:
                from app.core.container import DependencyContainer

                container = DependencyContainer()

                create_use_case = container.create_incident_use_case(db)
                incident = await create_use_case.execute(
                    user_phone=str(pending_ticket.user_phone),
                    description=description,
                    priority=priority,
                    category_code=category_code,
                    conversation_id=str(pending_ticket.conversation_id),
                    user_name=state_dict.get("user_name"),
                    incident_type="incident",
                )

                save_use_case = container.save_pending_ticket_use_case(db)
                await save_use_case.deactivate(str(pending_ticket.conversation_id))

            folio = incident.get("folio", incident.get("id", "")[:8].upper())
            priority_display = incident.get("priority_display", priority)

            return await self._prompts.get_created_success(folio, priority_display)

        except Exception as e:
            logger.error(f"Error creating incident: {e}")
            await self.cancel_flow(state_dict)
            return await self._prompts.get_error_message()

    async def reset_flow(self, pending_ticket: "PendingTicket", target_step: str) -> str:
        """Reset flow to a specific step."""
        try:
            conversation_id = str(pending_ticket.conversation_id)

            async with get_async_db_context() as db:
                from app.core.container import DependencyContainer

                container = DependencyContainer()
                use_case = container.save_pending_ticket_use_case(db)

                if target_step == "priority":
                    await use_case.reset_to_priority(conversation_id)
                else:
                    await use_case.reset_to_description(conversation_id)

            return await self._prompts.get_reset_message(target_step)

        except Exception as e:
            logger.error(f"Error resetting flow: {e}")
            return await self._prompts.get_error_message()

    async def cancel_flow(self, state_dict: dict[str, Any]) -> str:
        """Cancel the incident creation flow."""
        try:
            conversation_id = state_dict.get("conversation_id")
            if not conversation_id:
                return await self._prompts.get_cancelled()

            async with get_async_db_context() as db:
                from app.core.container import DependencyContainer

                container = DependencyContainer()
                use_case = container.save_pending_ticket_use_case(db)
                await use_case.deactivate(str(conversation_id))

            return await self._prompts.get_cancelled()

        except Exception as e:
            logger.error(f"Error cancelling flow: {e}")
            return "Incidencia cancelada.\n\nHay algo mas en lo que pueda ayudarte?"
