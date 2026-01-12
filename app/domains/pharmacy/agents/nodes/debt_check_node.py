"""
Debt Check Node

Pharmacy domain node for checking customer debt via Plex ERP.
Uses PharmacyResponseGenerator for LLM-driven responses with fallback templates.
Supports Smart Debt Negotiation with pre-calculated payment options.
Implements context-based ofuscation based on authentication level.

Implements CASO 3 from docs/pharmacy_flujo_mejorado_v2.md:
- Show debt with invoice details (date, invoice number, amount)
- Post-debt action menu (pagar/detalles/volver)
- Invoice detail viewing with full product list

Refactored to follow Single Responsibility Principle:
- Node: Orchestration only
- Handlers: Specialized flow handling
- Services: Business logic
- Formatters: Presentation logic
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.agents import BaseAgent
from app.core.tenancy.pharmacy_config_service import PharmacyConfig, PharmacyConfigService
from app.domains.pharmacy.agents.nodes.handlers.debt_action_handler import (
    DebtActionHandler,
)
from app.domains.pharmacy.agents.nodes.handlers.payment_amount_handler import (
    PaymentAmountHandler,
)
from app.domains.pharmacy.agents.nodes.handlers.payment_confirmation_handler import (
    PaymentConfirmationHandler,
)
from app.domains.pharmacy.agents.nodes.handlers.payment_option_handler import (
    PaymentOptionHandler,
)
from app.domains.pharmacy.agents.utils.db_helpers import generate_response, get_current_task
from app.tasks import TaskRegistry
from app.domains.pharmacy.agents.utils.debt_formatter_service import DebtFormatterService
from app.domains.pharmacy.agents.utils.plex_debt_mapper import PlexDebtMapper
from app.domains.pharmacy.agents.utils.response_generator import (
    PharmacyResponseGenerator,
    get_response_generator,
)
from app.domains.pharmacy.domain.services.auth_level_service import AuthLevelService
from app.domains.pharmacy.domain.services.payment_options_service import (
    PaymentOptionsService,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.clients.plex_client import PlexClient

logger = logging.getLogger(__name__)


class DebtCheckNode(BaseAgent):
    """
    Pharmacy node specialized in debt checking (Consulta Deuda).

    Uses PlexClient to query customer balance via the Plex ERP API.
    Requires that the customer has already been identified (plex_customer_id in state).
    Uses PharmacyResponseGenerator for LLM-driven responses with fallback templates.

    Responsibility: ONLY orchestration of debt check flow.
    Delegates to specialized handlers for different states.
    """

    def __init__(
        self,
        plex_client: PlexClient | None = None,
        config: dict[str, Any] | None = None,
        response_generator: PharmacyResponseGenerator | None = None,
        db_session: AsyncSession | None = None,
        # Handlers (lazy initialization)
        debt_action_handler: DebtActionHandler | None = None,
        payment_option_handler: PaymentOptionHandler | None = None,
        payment_amount_handler: PaymentAmountHandler | None = None,
        payment_confirmation_handler: PaymentConfirmationHandler | None = None,
    ):
        """
        Initialize debt check node.

        Args:
            plex_client: PlexClient instance for API calls
            config: Node configuration
            response_generator: PharmacyResponseGenerator for LLM-driven responses
            db_session: Database session for loading pharmacy config
            debt_action_handler: Handler for CASO 3 menu
            payment_option_handler: Handler for legacy payment options
            payment_amount_handler: Handler for custom amount input
            payment_confirmation_handler: Handler for YES/NO confirmations
        """
        super().__init__("debt_check_node", config or {})
        self._plex_client = plex_client
        self._response_generator = response_generator
        self._db_session = db_session
        self._pharmacy_config: PharmacyConfig | None = None

        # Handlers (lazy initialization)
        self._debt_action_handler = debt_action_handler
        self._payment_option_handler = payment_option_handler
        self._payment_amount_handler = payment_amount_handler
        self._payment_confirmation_handler = payment_confirmation_handler

    # =========================================================================
    # Dependency Getters (Lazy Initialization)
    # =========================================================================

    def _get_response_generator(self) -> PharmacyResponseGenerator:
        """Get or create response generator."""
        if self._response_generator is None:
            self._response_generator = get_response_generator()
        return self._response_generator

    def _get_plex_client(self) -> PlexClient:
        """Get or create Plex client."""
        if self._plex_client is None:
            from app.clients.plex_client import PlexClient
            self._plex_client = PlexClient()
        return self._plex_client

    async def _get_db_session(self) -> AsyncSession:
        """Get or create database session."""
        if self._db_session is None:
            from app.database.async_db import create_async_session

            self._db_session = await create_async_session()
        return self._db_session

    def _get_debt_action_handler(self) -> DebtActionHandler:
        """Get or create debt action handler."""
        if self._debt_action_handler is None:
            self._debt_action_handler = DebtActionHandler()
        return self._debt_action_handler

    def _get_payment_option_handler(self) -> PaymentOptionHandler:
        """Get or create payment option handler."""
        if self._payment_option_handler is None:
            self._payment_option_handler = PaymentOptionHandler()
        return self._payment_option_handler

    def _get_payment_amount_handler(self) -> PaymentAmountHandler:
        """Get or create payment amount handler."""
        if self._payment_amount_handler is None:
            self._payment_amount_handler = PaymentAmountHandler()
        return self._payment_amount_handler

    def _get_payment_confirmation_handler(self) -> PaymentConfirmationHandler:
        """Get or create payment confirmation handler."""
        if self._payment_confirmation_handler is None:
            self._payment_confirmation_handler = PaymentConfirmationHandler()
        return self._payment_confirmation_handler

    async def _get_pharmacy_config(self, state_dict: dict[str, Any]) -> PharmacyConfig | None:
        """
        Get pharmacy configuration from database.

        Args:
            state_dict: Current state with organization_id

        Returns:
            PharmacyConfig or None if not found
        """
        if self._pharmacy_config is not None:
            return self._pharmacy_config

        org_id_str = state_dict.get("organization_id")
        if not org_id_str:
            logger.warning("No organization_id in state for pharmacy config lookup")
            return None

        try:
            org_id = UUID(str(org_id_str)) if not isinstance(org_id_str, UUID) else org_id_str
            db = await self._get_db_session()
            config_service = PharmacyConfigService(db)
            self._pharmacy_config = await config_service.get_config(org_id)
            return self._pharmacy_config
        except Exception as e:
            logger.error(f"Failed to load pharmacy config: {e}")
            return None

    # =========================================================================
    # Main Processing Logic
    # =========================================================================

    async def _process_internal(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process debt check queries and route to appropriate handlers.

        Flow states:
        1. Initial debt query → show debt, ask action
        2. awaiting_debt_action → DebtActionHandler (CASO 3)
        3. awaiting_payment_option_selection → PaymentOptionHandler (legacy)
        4. awaiting_payment_amount_input → PaymentAmountHandler
        5. awaiting_partial_payment_question → PaymentConfirmationHandler
        6. awaiting_confirmation → PaymentConfirmationHandler

        Args:
            message: User message
            state_dict: Current state dictionary

        Returns:
            State updates
        """
        try:
            # Route to handlers based on state
            if state_dict.get("awaiting_debt_action"):
                handler = self._get_debt_action_handler()
                return await handler.handle(message, state_dict)

            if state_dict.get("awaiting_payment_option_selection"):
                handler = self._get_payment_option_handler()
                return await handler.handle(message, state_dict)

            if state_dict.get("awaiting_payment_amount_input"):
                handler = self._get_payment_amount_handler()
                return await handler.handle(message, state_dict)

            if state_dict.get("awaiting_partial_payment_question"):
                handler = self._get_payment_confirmation_handler()
                return await handler.handle_partial_payment(message, state_dict)

            if state_dict.get("awaiting_confirmation") and state_dict.get("has_debt"):
                handler = self._get_payment_confirmation_handler()
                return await handler.handle_confirmation(message, state_dict)

            # Initial debt query
            return await self._process_initial_debt_query(message, state_dict)

        except Exception as e:
            logger.error(f"Error in debt check node: {e!s}", exc_info=True)
            return await self._handle_error(str(e), state_dict)

    async def _process_initial_debt_query(
        self,
        _message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process initial debt query - fetch and display debt.

        Args:
            message: User message
            state_dict: Current state

        Returns:
            State updates with debt information
        """
        # Get Plex customer ID from state
        plex_customer_id = state_dict.get("plex_customer_id")

        if not plex_customer_id:
            logger.warning("No plex_customer_id in state for debt check")
            return await self._handle_no_customer()

        # Get customer name for personalized response
        customer_name = (
            state_dict.get("customer_name")
            or state_dict.get("plex_customer", {}).get("nombre", "Cliente")
        )

        logger.info(f"Checking debt for Plex customer: {plex_customer_id}")

        plex_client = self._get_plex_client()

        async with plex_client:
            balance_data = await plex_client.get_customer_balance(
                customer_id=plex_customer_id,
                detailed=True,
            )

        if not balance_data:
            return await self._handle_no_debt(customer_name)

        # Check if there's actual debt
        total_debt = balance_data.get("saldo", 0)
        if total_debt <= 0:
            return await self._handle_no_debt(customer_name)

        # Transform Plex response to domain entity
        debt = PlexDebtMapper.map_balance_to_debt(
            balance_data,
            plex_customer_id,
            customer_name,
        )

        # Determine authentication level for ofuscation
        auth_level = AuthLevelService.determine_level(state_dict)
        logger.debug(f"Auth level for debt display: {auth_level}")

        # Load pharmacy config for payment options
        pharmacy_config = await self._get_pharmacy_config(state_dict)

        # Calculate payment options from config
        total_debt_float = float(debt.total_debt)
        payment_options = PaymentOptionsService.calculate_options(
            total_debt_float, pharmacy_config
        )
        logger.info(f"Payment options: {payment_options}")

        # Get minimum payment from pharmacy config
        min_payment = PaymentOptionsService.get_minimum_payment(pharmacy_config)

        # Check for payment amount from various sources
        extracted_entities = state_dict.get("extracted_entities", {})
        # Check payment_amount from multiple sources:
        # 1. Directly in state (from PersonResolutionNode extraction)
        # 2. In extracted_entities (from router)
        payment_amount = state_dict.get("payment_amount") or extracted_entities.get("amount")

        # If user specified a payment amount (e.g., "quiero pagar 3000"),
        # proceed directly to payment confirmation instead of showing menu
        if payment_amount and payment_amount > 0:
            response_text = DebtFormatterService.format_payment_ready_response(
                debt, payment_amount
            )
            # Direct proceed to payment with specified amount
            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "debt_id": str(balance_data.get("id", plex_customer_id)),
                "debt_data": debt.to_dict(),
                "debt_status": debt.status.value,
                "total_debt": total_debt_float,
                "has_debt": True,
                "workflow_step": "debt_checked",
                "awaiting_confirmation": True,
                "is_complete": False,
                "minimum_payment_amount": min_payment,
                "auth_level": auth_level,
                "payment_amount": min(payment_amount, total_debt_float),
                "is_partial_payment": payment_amount < total_debt_float,
            }

        # Smart Debt Negotiation: Show debt with payment options
        response_text = DebtFormatterService.format_smart_debt_response(
            debt, payment_options, pharmacy_config, auth_level
        )

        # Store debt items for detail viewing
        debt_fetched_at = datetime.now(UTC).isoformat()

        return {
            "messages": [{"role": "assistant", "content": response_text}],
            "current_agent": self.name,
            "agent_history": [self.name],
            "debt_id": str(balance_data.get("id", plex_customer_id)),
            "debt_data": debt.to_dict(),
            "debt_status": debt.status.value,
            "total_debt": total_debt_float,
            "has_debt": True,
            "workflow_step": "debt_checked",
            # CASO 3: Use awaiting_debt_action for post-debt menu
            "awaiting_debt_action": True,
            "awaiting_payment_option_selection": False,
            "is_complete": False,
            "minimum_payment_amount": min_payment,
            # Smart Debt Negotiation fields
            "auth_level": auth_level,
            "payment_options_map": payment_options,
            # Store items for detail viewing
            "debt_items": [item.to_dict() for item in debt.items],
            "debt_fetched_at": debt_fetched_at,
        }

    # =========================================================================
    # Error & Edge Case Handlers
    # =========================================================================

    async def _handle_no_customer(self) -> dict[str, Any]:
        """Handle missing customer identification."""
        response_content = await generate_response(
            state={},
            intent="no_customer",
            user_message="",
            current_task=await get_current_task(TaskRegistry.PHARMACY_IDENTIFICATION_NOT_IDENTIFIED),
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "current_agent": self.name,
            "awaiting_document_input": True,
            "has_debt": False,
        }

    async def _handle_no_debt(self, customer_name: str) -> dict[str, Any]:
        """Handle no debt found."""
        response_content = await generate_response(
            state={"customer_name": customer_name},
            intent="no_debt",
            user_message="",
            current_task=await get_current_task(TaskRegistry.PHARMACY_DEBT_NO_DEBT),
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "current_agent": self.name,
            "has_debt": False,
            "is_complete": True,
        }

    async def _handle_error(self, error: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Handle processing error."""
        logger.error(f"Debt check error: {error}")

        response_content = await generate_response(
            state=state_dict,
            intent="generic_error",
            user_message="",
            current_task=await get_current_task(TaskRegistry.PHARMACY_DEBT_ERROR),
        )

        return {
            "messages": [{"role": "assistant", "content": response_content}],
            "current_agent": self.name,
            "error_count": state_dict.get("error_count", 0) + 1,
        }
