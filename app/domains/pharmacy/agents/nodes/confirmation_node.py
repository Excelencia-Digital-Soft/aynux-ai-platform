"""
Confirmation Node

Pharmacy domain node for confirming customer debt.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.agents import BaseAgent
from app.domains.pharmacy.agents.intent_analyzer import get_pharmacy_intent_analyzer
from app.domains.pharmacy.agents.utils.db_helpers import generate_response, get_current_task
from app.tasks import TaskRegistry
from app.domains.pharmacy.agents.utils.response_generator import (
    PharmacyResponseGenerator,
    get_response_generator,
)

if TYPE_CHECKING:
    from app.clients.plex_client import PlexClient

logger = logging.getLogger(__name__)

# Out-of-scope intents that should bypass confirmation flow
OUT_OF_SCOPE_INTENTS = frozenset({"out_of_scope", "info_query", "farewell", "thanks", "unknown"})


class ConfirmationNode(BaseAgent):
    """
    Pharmacy node specialized in debt confirmation.

    This node handles user confirmation of their debt before proceeding
    to payment/receipt generation.
    """

    def __init__(
        self,
        plex_client: PlexClient | None = None,
        config: dict[str, Any] | None = None,
        response_generator: PharmacyResponseGenerator | None = None,
    ):
        """
        Initialize confirmation node.

        Args:
            plex_client: PlexClient instance (for future use)
            config: Node configuration
            response_generator: PharmacyResponseGenerator for LLM-driven responses
        """
        super().__init__("confirmation_node", config or {})
        self._plex_client = plex_client
        self._intent_analyzer = get_pharmacy_intent_analyzer()
        self._response_generator = response_generator

    def _get_response_generator(self) -> PharmacyResponseGenerator:
        """Get or create response generator."""
        if self._response_generator is None:
            self._response_generator = get_response_generator()
        return self._response_generator

    def _get_organization_id(self, state_dict: dict[str, Any]) -> UUID | None:
        """Extract organization_id from state for multi-tenant intent analysis."""
        org_id = state_dict.get("organization_id")
        if org_id is None:
            return None
        if isinstance(org_id, UUID):
            return org_id
        try:
            return UUID(str(org_id))
        except (ValueError, TypeError):
            logger.warning(f"Invalid organization_id in state: {org_id}")
            return None

    async def _process_internal(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process debt confirmation.

        Args:
            message: User message
            state_dict: Current state dictionary

        Returns:
            State updates
        """
        try:
            # Check intent first - allow out-of-scope messages while awaiting confirmation
            # This prevents users from getting stuck if they ask a question instead of SI/NO
            org_id = self._get_organization_id(state_dict)
            intent_result = await self._intent_analyzer.analyze(
                message, {}, organization_id=org_id
            )
            if intent_result.intent in OUT_OF_SCOPE_INTENTS or intent_result.is_out_of_scope:
                logger.info(f"Out-of-scope detected while awaiting confirmation: {intent_result.intent}")
                return {
                    "awaiting_confirmation": False,  # Reset state
                    "awaiting_payment": False,
                    "next_agent": "router",  # Route back to router for proper handling
                }

            debt_id = state_dict.get("debt_id")
            plex_customer_id = state_dict.get("plex_customer_id")

            if not debt_id:
                return await self._handle_no_debt_id(state_dict)

            if not plex_customer_id:
                return await self._handle_no_customer()

            # Parse user response
            message_clean = message.strip().upper()

            if message_clean in ["SI", "SÍ", "YES", "S", "CONFIRMO", "CONFIRMAR"]:
                return self._confirm_debt(state_dict)
            elif message_clean in ["NO", "N", "CANCELAR"]:
                return await self._cancel_confirmation()
            else:
                return await self._request_clear_response()

        except Exception as e:
            logger.error(f"Error in confirmation node: {e!s}", exc_info=True)
            return await self._handle_error(str(e), state_dict)

    def _confirm_debt(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Handle debt confirmation (full or partial payment) - auto-proceed to payment link."""
        # Extract critical state fields to propagate
        debt_id = state_dict.get("debt_id")
        plex_customer_id = state_dict.get("plex_customer_id")
        debt_data = state_dict.get("debt_data")

        total_debt = state_dict.get("total_debt", 0) or 0
        payment_amount = state_dict.get("payment_amount") or total_debt
        is_partial = state_dict.get("is_partial_payment", False)
        customer_name = state_dict.get("customer_name", "Cliente")

        # Calculate remaining balance for partial payments
        remaining_balance = total_debt - payment_amount if is_partial else 0

        if is_partial:
            logger.info(
                f"Partial payment confirmed: customer={customer_name}, "
                f"payment=${payment_amount}, total_debt=${total_debt}, remaining=${remaining_balance}"
            )
            message = (
                f"Tu pago parcial de **${payment_amount:,.2f}** ha sido confirmado.\n\n"
                f"**Resumen:**\n"
                f"- Deuda total: ${total_debt:,.2f}\n"
                f"- Monto a pagar: ${payment_amount:,.2f}\n"
                f"- Saldo pendiente: ${remaining_balance:,.2f}\n\n"
                "Generando link de pago..."
            )
        else:
            logger.info(f"Full debt confirmed: customer={customer_name}, amount=${total_debt}")
            message = (
                f"Tu deuda de **${total_debt:,.2f}** ha sido confirmada.\n\n"
                "Generando link de pago..."
            )

        result = {
            "messages": [{"role": "assistant", "content": message}],
            "current_agent": self.name,
            "agent_history": [self.name],
            "debt_status": "confirmed",
            "awaiting_confirmation": False,
            "confirmation_received": True,
            "workflow_step": "confirmed",
            "remaining_balance": remaining_balance,
            # Propagate critical state fields for downstream nodes
            "debt_id": debt_id,
            "plex_customer_id": plex_customer_id,
            "total_debt": total_debt,
            "debt_data": debt_data,
            "payment_amount": payment_amount,
            "is_partial_payment": is_partial,
            "customer_name": customer_name,
        }

        # Auto-proceed to payment link generation
        # Always go to payment_link_node after confirmation
        result["next_agent"] = "payment_link_node"
        result["is_complete"] = False

        return result

    async def _cancel_confirmation(self) -> dict[str, Any]:
        """Handle confirmation cancellation."""
        response_content = await generate_response(

            state={},

            intent="confirmation_cancelled",

            user_message="",

            current_task=await get_current_task(TaskRegistry.PHARMACY_CONFIRMATION_CANCELLED),

        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "current_agent": self.name,
            "awaiting_confirmation": False,
            "is_complete": True,
        }

    async def _request_clear_response(self) -> dict[str, Any]:
        """Request clear yes/no response."""
        response_content = await generate_response(

            state={},

            intent="request_clear_confirmation",

            user_message="",

            current_task=await get_current_task(TaskRegistry.PHARMACY_CONFIRMATION_REQUEST),

        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "current_agent": self.name,
            "awaiting_confirmation": True,
            "confirmation_received": False,
            "is_complete": False,
        }

    def _get_plex_client(self) -> PlexClient:
        """Get or create Plex client."""
        if self._plex_client is None:
            from app.clients.plex_client import PlexClient

            self._plex_client = PlexClient()
        return self._plex_client

    async def _handle_no_debt_id(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Handle missing debt ID - auto-fetch debt after sending intermediate message."""
        from app.database.async_db import get_async_db_context
        from app.domains.pharmacy.infrastructure.services import PharmacyNotificationService

        plex_customer_id = state_dict.get("plex_customer_id")
        customer_phone = state_dict.get("customer_id")  # WhatsApp phone
        did = state_dict.get("did")
        customer_name = state_dict.get("customer_name", "Cliente")

        # If no customer identified, cannot auto-fetch
        if not plex_customer_id or not customer_phone:
            return await self._handle_no_customer()

        try:
            # 1. Get wait message using ResponseGenerator
            response_content = await generate_response(

                state={},

                intent="auto_fetching_debt",

                user_message="",

                current_task=await get_current_task(TaskRegistry.PHARMACY_CONFIRMATION_CONSULTING_DEBT),

            )
            wait_message = response_content

            # 2. Send intermediate message and wait for HTTP 200
            async with get_async_db_context() as db:
                notif_service = PharmacyNotificationService(db=db, did=did)
                try:
                    result = await notif_service.send_message(
                        phone=customer_phone,
                        message=wait_message,
                    )
                    if result.get("status") != "ok":
                        logger.warning(f"Intermediate message may not have been delivered: {result}")
                except Exception as e:
                    logger.warning(f"Failed to send intermediate message: {e}")
                finally:
                    await notif_service.close()

            # 3. Query debt via Plex (HTTP 200 already confirmed)
            plex_client = self._get_plex_client()
            async with plex_client:
                balance_data = await plex_client.get_customer_balance(
                    customer_id=plex_customer_id,
                    detailed=True,
                )

            if not balance_data or balance_data.get("saldo", 0) <= 0:
                # No debt found
                return await self._handle_no_debt_found(customer_name)

            # 4. Format and return debt (same pattern as debt_check_node)
            total_debt = balance_data.get("saldo", 0)
            debt_id = str(balance_data.get("id", plex_customer_id))

            response_text = (
                f"**Tu deuda pendiente**\n\n"
                f"Hola {customer_name}, tu saldo es de **${total_debt:,.2f}**\n\n"
                f"Para confirmar y proceder al pago, responde *SI*.\n"
                f"Para cancelar, responde *NO*."
            )

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "debt_id": debt_id,
                "debt_data": balance_data,
                "debt_status": "pending",
                "total_debt": float(total_debt),
                "has_debt": True,
                "awaiting_confirmation": True,
                "is_complete": False,
            }

        except Exception as e:
            logger.error(f"Error auto-fetching debt: {e}", exc_info=True)
            # Fallback: ask user to write DEUDA
            return await self._handle_auto_fetch_error()

    async def _handle_no_debt_found(self, customer_name: str) -> dict[str, Any]:
        """Handle when customer has no debt."""
        content = (
            f"Hola {customer_name}, no tienes deudas pendientes. "
            "¿Hay algo más en que pueda ayudarte?"
        )
        return {
            "messages": [{"role": "assistant", "content": content}],
            "current_agent": self.name,
            "has_debt": False,
            "is_complete": True,
        }

    async def _handle_auto_fetch_error(self) -> dict[str, Any]:
        """Handle error during auto-fetch - fallback to manual."""
        response_content = await generate_response(

            state={},

            intent="generic_error",

            user_message="",

            current_task=await get_current_task(TaskRegistry.PHARMACY_CONFIRMATION_ERROR),

        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "current_agent": self.name,
            "is_complete": True,
        }

    async def _handle_no_customer(self) -> dict[str, Any]:
        """Handle missing customer identification."""
        response_content = await generate_response(

            state={},

            intent="confirmation_no_customer",

            user_message="",

            current_task=await get_current_task(TaskRegistry.PHARMACY_CONFIRMATION_NOT_IDENTIFIED),

        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "current_agent": self.name,
            "is_complete": True,
        }

    async def _handle_error(self, error: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Handle processing error."""
        logger.error(f"Confirmation node error: {error}")

        response_content = await generate_response(


            state=state_dict,


            intent="confirmation_error",


            user_message="",


            current_task=await get_current_task(TaskRegistry.PHARMACY_ERROR_RETRY),


        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "current_agent": self.name,
            "error_count": state_dict.get("error_count", 0) + 1,
        }
