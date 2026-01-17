# ============================================================================
# SCOPE: MULTI-TENANT
# Description: LangGraph node for debt management operations.
#              REFACTORED: Extracted utilities into utils/debt/.
# Tenant-Aware: Yes - organization context for config and patterns.
# ============================================================================
"""
Debt Manager Node - V2 Debt Check and Management Node.

Simplified debt management for pharmacy V2 graph.
Handles PLEX debt lookup, formatting, and payment options.

REFACTORED: Extracted responsibilities into utils/debt/:
- organization_resolver.py: UUID normalization
- debt_data_preparer.py: Fetch and prepare debt data
- invoice_handler.py: Invoice selection and aggregation
- payment_amount_extractor.py: Payment amount extraction
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenancy.pharmacy_config_service import PharmacyConfig, PharmacyConfigService
from app.database.async_db import get_async_db_context
from app.domains.pharmacy.agents.utils.debt import (
    DebtDataPreparer,
    InvoiceHandler,
    OrganizationResolver,
    PaymentAmountExtractor,
)
from app.domains.pharmacy.agents.utils.debt_formatter_service import DebtFormatterService
from app.domains.pharmacy.agents.utils.message_extractor import MessageExtractor
from app.domains.pharmacy.agents.utils.plex_debt_mapper import PlexDebtMapper
from app.domains.pharmacy.agents.utils.response_helper import generate_response as _generate_response
from app.domains.pharmacy.domain.services.auth_level_service import AuthLevelService

if TYPE_CHECKING:
    from app.clients.plex_client import PlexClient
    from app.domains.pharmacy.agents.state_v2 import PharmacyStateV2

logger = logging.getLogger(__name__)


class DebtManagerService:
    """
    Service for debt management operations.

    Responsibilities:
    - PLEX balance lookup
    - Debt mapping and formatting
    - Pharmacy config loading
    """

    def __init__(self, plex_client: "PlexClient | None" = None):
        self._plex_client = plex_client
        self._pharmacy_config: PharmacyConfig | None = None

    def _get_plex_client(self) -> "PlexClient":
        """Get or create Plex client."""
        if self._plex_client is None:
            from app.clients.plex_client import PlexClient

            self._plex_client = PlexClient()
        return self._plex_client

    async def get_customer_debt(
        self,
        plex_customer_id: int,
        customer_name: str,
    ) -> dict[str, Any] | None:
        """
        Fetch customer debt from PLEX.

        Args:
            plex_customer_id: PLEX customer ID
            customer_name: Customer name for formatting

        Returns:
            Debt data dict or None if no debt
        """
        try:
            plex_client = self._get_plex_client()

            async with plex_client:
                balance_data = await plex_client.get_customer_balance(
                    customer_id=plex_customer_id,
                    detailed=True,
                )

            if not balance_data:
                return None

            total = balance_data.get("saldo", 0)
            if total <= 0:
                return None

            debt = PlexDebtMapper.map_balance_to_debt(
                balance_data,
                plex_customer_id,
                customer_name,
            )

            return {
                "debt_id": str(balance_data.get("id", plex_customer_id)),
                "total_debt": float(debt.total_debt),
                "debt_status": debt.status.value,
                "debt_items": [item.to_dict() for item in debt.items],
                "debt": debt,
                "raw_balance": balance_data,
            }

        except Exception as e:
            logger.error(f"Error fetching debt from PLEX: {e}")
            return None

    async def load_pharmacy_config(
        self,
        organization_id: str | UUID | None,
    ) -> PharmacyConfig | None:
        """Load pharmacy configuration from database."""
        if self._pharmacy_config is not None:
            return self._pharmacy_config

        if not organization_id:
            return None

        try:
            org_uuid = OrganizationResolver.resolve_safe(organization_id)

            async with get_async_db_context() as db:
                config_service = PharmacyConfigService(db)
                self._pharmacy_config = await config_service.get_config(org_uuid)
                return self._pharmacy_config

        except Exception as e:
            logger.error(f"Failed to load pharmacy config: {e}")
            return None



# =============================================================================
# LangGraph Node Entry Point
# =============================================================================


async def debt_manager_node(
    state: "PharmacyStateV2",
    _config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """
    Debt manager node - handles debt lookup and display.

    Routes based on intent:
    - debt_query/check_debt: SHOW_DEBT flow
    - pay_debt_menu: PAY_DEBT_MENU flow
    - view_invoice_detail: INVOICE_DETAIL flow

    Args:
        state: Current conversation state
        _config: Optional configuration (unused)

    Returns:
        State updates with debt information
    """
    service = DebtManagerService()
    organization_id = OrganizationResolver.resolve_safe(state.get("organization_id"))

    async with get_async_db_context() as db:
        plex_user_id = state.get("plex_user_id")
        if not plex_user_id:
            logger.warning("No plex_user_id in state for debt check")
            return await _handle_not_authenticated(db, organization_id, dict(state))

        customer_name = state.get("customer_name") or state.get("plex_customer", {}).get("nombre", "Cliente")
        intent = state.get("intent", "debt_query")

        logger.info(f"Debt manager handling intent: {intent} for PLEX customer: {plex_user_id}")

        # Intent routing
        if intent == "view_invoice_detail":
            return await _handle_invoice_detail(db, organization_id, state, service, plex_user_id, customer_name)
        elif intent == "pay_debt_menu":
            return await _handle_pay_debt_menu(db, organization_id, state, service, plex_user_id, customer_name)
        else:
            return await _handle_show_debt(db, organization_id, state, service, plex_user_id, customer_name)


# =============================================================================
# Intent Handlers
# =============================================================================


async def _handle_show_debt(
    db: AsyncSession,
    organization_id: UUID,
    state: "PharmacyStateV2",
    service: DebtManagerService,
    plex_user_id: int,
    customer_name: str,
) -> dict[str, Any]:
    """SHOW_DEBT flow - full debt with invoice details."""
    org_id_raw = state.get("organization_id")

    # Prepare debt data
    preparer = DebtDataPreparer(service)
    prepared = await preparer.prepare(plex_user_id, customer_name, org_id_raw)

    if not prepared:
        return await _handle_no_debt(db, organization_id, customer_name, dict(state))

    # Determine auth level
    auth_level = AuthLevelService.determine_level(state)

    # Check for payment amount in message
    message = MessageExtractor.extract_last_human_message(state) or ""
    extracted_amount = await PaymentAmountExtractor.extract(db, organization_id, message)

    # If amount specified, go to payment confirmation
    if extracted_amount and extracted_amount > 0:
        return _build_payment_ready_response(prepared, extracted_amount, auth_level)

    # Format debt response with options
    response_text = DebtFormatterService.format_smart_debt_response(
        prepared.debt,
        prepared.payment_options,
        prepared.pharmacy_config,
        auth_level,
    )

    return _build_debt_response(prepared, response_text, auth_level)


async def _handle_pay_debt_menu(
    db: AsyncSession,
    organization_id: UUID,
    state: "PharmacyStateV2",
    service: DebtManagerService,
    plex_user_id: int,
    customer_name: str,
) -> dict[str, Any]:
    """PAY_DEBT_MENU flow - debt summary with payment options."""
    org_id_raw = state.get("organization_id")

    preparer = DebtDataPreparer(service)
    prepared = await preparer.prepare(plex_user_id, customer_name, org_id_raw)

    if not prepared:
        return await _handle_no_debt(db, organization_id, customer_name, dict(state))

    response_text = DebtFormatterService.format_pay_debt_menu_response(
        prepared.debt,
        prepared.payment_options,
        prepared.pharmacy_config,
    )

    return {
        "messages": [{"role": "assistant", "content": response_text}],
        "current_node": "debt_manager",
        "agent_history": ["debt_manager"],
        "debt_id": prepared.debt_id,
        "total_debt": prepared.total_debt,
        "debt_items": prepared.debt_items,
        "has_debt": True,
        "debt_fetched_at": datetime.now(UTC).isoformat(),
        "awaiting_input": "pay_debt_action",
        "next_node": "response_formatter",
        "is_complete": False,
    }


async def _handle_invoice_detail(
    db: AsyncSession,
    organization_id: UUID,
    state: "PharmacyStateV2",
    service: DebtManagerService,
    plex_user_id: int,
    customer_name: str,
) -> dict[str, Any]:
    """INVOICE_DETAIL flow - single invoice detail."""
    org_id_raw = state.get("organization_id")
    debt_items = state.get("debt_items")

    # Prepare debt data (use cached if available)
    preparer = DebtDataPreparer(service)
    prepared = await preparer.prepare_or_cached(plex_user_id, customer_name, org_id_raw, debt_items)

    if not prepared:
        return await _handle_no_debt(db, organization_id, customer_name, dict(state))

    # Select invoice
    message = MessageExtractor.extract_last_human_message(state) or ""
    invoice_num = InvoiceHandler.select_invoice(state, prepared.debt_items, message)

    if not invoice_num:
        no_invoice_msg = "No hay facturas para mostrar. Volviendo a la consulta de deuda..."
        return {
            "messages": [{"role": "assistant", "content": no_invoice_msg}],
            "intent": "debt_query",
            "next_node": "debt_manager",
            "is_complete": False,
        }

    # Aggregate invoice amounts
    invoice_data = InvoiceHandler.aggregate_invoice_amounts(prepared.debt_items, invoice_num)

    # Format response
    response_text = DebtFormatterService.format_invoice_detail_response(
        invoice_number=invoice_data.invoice_number,
        invoice_date=invoice_data.invoice_date,
        invoice_amount=invoice_data.invoice_total,
        pharmacy_config=prepared.pharmacy_config,
    )

    return {
        "messages": [{"role": "assistant", "content": response_text}],
        "current_node": "debt_manager",
        "agent_history": ["debt_manager"],
        "selected_invoice_number": invoice_num,
        "awaiting_input": "invoice_detail_action",
        "next_node": "response_formatter",
        "is_complete": False,
    }


# =============================================================================
# Edge Case Handlers
# =============================================================================


async def _handle_not_authenticated(
    db: AsyncSession,
    organization_id: UUID,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Handle unauthenticated customer case."""
    content = await _generate_response(db, organization_id, "debt_not_authenticated", state)
    return {
        "messages": [{"role": "assistant", "content": content}],
        "current_node": "debt_manager",
        "awaiting_input": "dni",
        "next_node": "auth_plex",
        "has_debt": False,
    }


async def _handle_no_debt(
    db: AsyncSession,
    organization_id: UUID,
    customer_name: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Handle no-debt case."""
    if not state.get("is_authenticated"):
        logger.warning("_handle_no_debt called without authentication - redirecting")
        return await _handle_not_authenticated(db, organization_id, state)

    state_ctx = dict(state)
    state_ctx["customer_name"] = customer_name
    state_ctx["pharmacy_name"] = state.get("pharmacy_name") or "Farmacia"

    content = await _generate_response(db, organization_id, "debt_no_debt", state_ctx)
    return {
        "messages": [{"role": "assistant", "content": content}],
        "current_node": "debt_manager",
        "has_debt": False,
        "is_complete": True,
    }


# =============================================================================
# Response Builders
# =============================================================================


def _build_debt_response(
    prepared: "DebtDataPreparer",
    response_text: str,
    auth_level: str,
) -> dict[str, Any]:
    """Build standard debt response."""
    from app.domains.pharmacy.agents.utils.debt import PreparedDebtData

    if isinstance(prepared, PreparedDebtData):
        return {
            "messages": [{"role": "assistant", "content": response_text}],
            "current_node": "debt_manager",
            "agent_history": ["debt_manager"],
            "debt_id": prepared.debt_id,
            "total_debt": prepared.total_debt,
            "debt_items": prepared.debt_items,
            "has_debt": True,
            "debt_fetched_at": datetime.now(UTC).isoformat(),
            "auth_level": auth_level,
            "awaiting_input": "debt_action",
            "next_node": "response_formatter",
            "is_complete": False,
        }
    return {"messages": [], "has_debt": False}


def _build_payment_ready_response(
    prepared: "DebtDataPreparer",
    extracted_amount: float,
    auth_level: str,
) -> dict[str, Any]:
    """Build payment-ready response when amount extracted."""
    from app.domains.pharmacy.agents.utils.debt import PreparedDebtData

    if isinstance(prepared, PreparedDebtData):
        response_text = DebtFormatterService.format_payment_ready_response(
            prepared.debt,
            extracted_amount,
        )
        return {
            "messages": [{"role": "assistant", "content": response_text}],
            "current_node": "debt_manager",
            "agent_history": ["debt_manager"],
            "debt_id": prepared.debt_id,
            "total_debt": prepared.total_debt,
            "debt_items": prepared.debt_items,
            "has_debt": True,
            "debt_fetched_at": datetime.now(UTC).isoformat(),
            "payment_amount": min(extracted_amount, prepared.total_debt),
            "is_partial_payment": extracted_amount < prepared.total_debt,
            "awaiting_payment_confirmation": True,
            "awaiting_input": "payment_confirmation",
            "auth_level": auth_level,
            "next_node": "payment_processor",
            "is_complete": False,
        }
    return {"messages": [], "has_debt": False}


__all__ = ["debt_manager_node", "DebtManagerService"]
