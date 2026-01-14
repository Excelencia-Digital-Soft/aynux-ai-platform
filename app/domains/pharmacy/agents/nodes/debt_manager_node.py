"""
Debt Manager Node - V2 Debt Check and Management Node.

Simplified debt management for pharmacy V2 graph.
Handles PLEX debt lookup, formatting, and payment options.

Migrated from debt_check_node.py with simplified state management.
Uses V2 state fields: total_debt, debt_items, has_debt, etc.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache.domain_intent_cache import domain_intent_cache
from app.core.tenancy.pharmacy_config_service import PharmacyConfig, PharmacyConfigService
from app.database.async_db import get_async_db_context
from app.domains.pharmacy.agents.utils.debt_formatter_service import DebtFormatterService
from app.domains.pharmacy.agents.utils.message_extractor import MessageExtractor
from app.domains.pharmacy.agents.utils.plex_debt_mapper import PlexDebtMapper
from app.domains.pharmacy.domain.services.auth_level_service import AuthLevelService
from app.domains.pharmacy.domain.services.payment_options_service import PaymentOptionsService

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
    - Payment options calculation
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

            # Map to domain entity
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
                "debt": debt,  # Full debt object for formatting
                "raw_balance": balance_data,  # Raw data for reference
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
            org_uuid = UUID(str(organization_id)) if not isinstance(organization_id, UUID) else organization_id

            from app.database.async_db import get_async_db_context

            async with get_async_db_context() as db:
                config_service = PharmacyConfigService(db)
                self._pharmacy_config = await config_service.get_config(org_uuid)
                return self._pharmacy_config

        except Exception as e:
            logger.error(f"Failed to load pharmacy config: {e}")
            return None


# =============================================================================
# Database-Driven Response Generation
# =============================================================================


async def _generate_response(
    db: AsyncSession,
    organization_id: UUID,
    intent: str,
    state: dict[str, Any] | Any,
) -> str:
    """
    Generate response using PharmacyResponseGenerator.

    Falls back to template-based response if generator fails.

    Args:
        db: Database session
        organization_id: Organization UUID for multi-tenant support
        intent: Intent key for response config lookup
        state: State dict (can be PharmacyStateV2 or plain dict)
    """
    from app.domains.pharmacy.agents.utils.response import get_response_generator

    try:
        generator = get_response_generator()
        response = await generator.generate(
            db=db,
            organization_id=organization_id,
            intent=intent,
            state=state,
            user_message="",
        )
        return response.content
    except Exception as e:
        logger.error(f"Error generating response for intent {intent}: {e}", exc_info=True)
        return "Disculpa, tuve un problema. Por favor intenta de nuevo."


async def debt_manager_node(
    state: "PharmacyStateV2",
    _config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """
    Debt manager node - handles debt lookup and display.

    Routes based on intent:
    - debt_query/check_debt: SHOW_DEBT flow (full debt with invoice details)
    - pay_debt_menu: PAY_DEBT_MENU flow (debt summary with payment options only)
    - view_invoice_detail: INVOICE_DETAIL flow (single invoice detail)

    Args:
        state: Current conversation state
        _config: Optional configuration (unused)

    Returns:
        State updates with debt information
    """
    service = DebtManagerService()

    # Get organization context for multi-tenant support
    org_id_raw = state.get("organization_id")
    if not org_id_raw:
        logger.warning("No organization_id in state, using default")
        organization_id = UUID("00000000-0000-0000-0000-000000000000")
    elif isinstance(org_id_raw, str):
        organization_id = UUID(org_id_raw)
    else:
        organization_id = org_id_raw

    # Get database session for pattern/config lookups
    async with get_async_db_context() as db:
        # Check authentication
        plex_user_id = state.get("plex_user_id")
        if not plex_user_id:
            logger.warning("No plex_user_id in state for debt check")
            return await _handle_not_authenticated(db, organization_id, dict(state))

        # Get customer info
        customer_name = state.get("customer_name") or state.get("plex_customer", {}).get("nombre", "Cliente")

        # Determine which flow to execute based on intent
        intent = state.get("intent", "debt_query")
        logger.info(f"Debt manager handling intent: {intent} for PLEX customer: {plex_user_id}")

        # Route to appropriate flow handler
        if intent == "view_invoice_detail":
            return await _handle_invoice_detail(
                db, organization_id, state, service, plex_user_id, customer_name
            )
        elif intent == "pay_debt_menu":
            return await _handle_pay_debt_menu(
                db, organization_id, state, service, plex_user_id, customer_name
            )
        else:
            # Default: SHOW_DEBT flow (debt_query, check_debt, or any other)
            return await _handle_show_debt(
                db, organization_id, state, service, plex_user_id, customer_name
            )


async def _handle_show_debt(
    db: AsyncSession,
    organization_id: UUID,
    state: "PharmacyStateV2",
    service: DebtManagerService,
    plex_user_id: int,
    customer_name: str,
) -> dict[str, Any]:
    """
    SHOW_DEBT flow (Flujo 1: Consultar deuda).

    Shows full debt with invoice details and 4-option action menu.
    """
    org_id_raw = state.get("organization_id")

    # Fetch debt
    debt_data = await service.get_customer_debt(plex_user_id, customer_name)

    if not debt_data:
        return await _handle_no_debt(db, organization_id, customer_name, dict(state))

    # Load pharmacy config for payment options
    pharmacy_config = await service.load_pharmacy_config(org_id_raw)

    # Calculate payment options
    total_debt = debt_data["total_debt"]
    payment_options = PaymentOptionsService.calculate_options(total_debt, pharmacy_config)

    # Determine auth level for obfuscation
    auth_level = AuthLevelService.determine_level(state)
    logger.debug(f"Auth level for debt display: {auth_level}")

    # Check if payment amount was specified in message
    message = MessageExtractor.extract_last_human_message(state) or ""
    extracted_amount = await _extract_payment_amount(db, organization_id, message)

    # If user specified amount, go directly to payment confirmation
    if extracted_amount and extracted_amount > 0:
        response_text = DebtFormatterService.format_payment_ready_response(debt_data["debt"], extracted_amount)
        return {
            "messages": [{"role": "assistant", "content": response_text}],
            "current_node": "debt_manager",
            "agent_history": ["debt_manager"],
            # Debt data
            "debt_id": debt_data["debt_id"],
            "total_debt": total_debt,
            "debt_items": debt_data["debt_items"],
            "has_debt": True,
            "debt_fetched_at": datetime.now(UTC).isoformat(),
            # Payment data
            "payment_amount": min(extracted_amount, total_debt),
            "is_partial_payment": extracted_amount < total_debt,
            "awaiting_payment_confirmation": True,
            "awaiting_input": "payment_confirmation",
            # Config
            "auth_level": auth_level,
            "next_node": "payment_processor",
            "is_complete": False,
        }

    # Format debt response with payment options (SHOW_DEBT with 4-option menu)
    response_text = DebtFormatterService.format_smart_debt_response(
        debt_data["debt"],
        payment_options,
        pharmacy_config,
        auth_level,
    )

    return {
        "messages": [{"role": "assistant", "content": response_text}],
        "current_node": "debt_manager",
        "agent_history": ["debt_manager"],
        # Debt data
        "debt_id": debt_data["debt_id"],
        "total_debt": total_debt,
        "debt_items": debt_data["debt_items"],
        "has_debt": True,
        "debt_fetched_at": datetime.now(UTC).isoformat(),
        # Config
        "auth_level": auth_level,
        # Await action selection (debt_action for 4-option menu)
        "awaiting_input": "debt_action",
        "next_node": "response_formatter",
        "is_complete": False,
    }


async def _handle_pay_debt_menu(
    db: AsyncSession,
    organization_id: UUID,
    state: "PharmacyStateV2",
    service: DebtManagerService,
    plex_user_id: int,
    customer_name: str,
) -> dict[str, Any]:
    """
    PAY_DEBT_MENU flow (Flujo 2: Pagar deuda directo).

    Shows debt summary without invoice details, focused on payment options.
    """
    org_id_raw = state.get("organization_id")

    # Fetch debt
    debt_data = await service.get_customer_debt(plex_user_id, customer_name)

    if not debt_data:
        return await _handle_no_debt(db, organization_id, customer_name, dict(state))

    # Load pharmacy config
    pharmacy_config = await service.load_pharmacy_config(org_id_raw)

    # Calculate payment options
    total_debt = debt_data["total_debt"]
    payment_options = PaymentOptionsService.calculate_options(total_debt, pharmacy_config)

    # Format PAY_DEBT_MENU response (debt summary + 3 payment options)
    response_text = DebtFormatterService.format_pay_debt_menu_response(
        debt_data["debt"],
        payment_options,
        pharmacy_config,
    )

    return {
        "messages": [{"role": "assistant", "content": response_text}],
        "current_node": "debt_manager",
        "agent_history": ["debt_manager"],
        # Debt data
        "debt_id": debt_data["debt_id"],
        "total_debt": total_debt,
        "debt_items": debt_data["debt_items"],
        "has_debt": True,
        "debt_fetched_at": datetime.now(UTC).isoformat(),
        # Await payment menu selection (pay_debt_action for 3-option menu)
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
    """
    INVOICE_DETAIL flow (Ver detalle de factura).

    Shows single invoice detail WITHOUT medications (privacy rule).
    User must have selected an invoice via button or message.
    """
    org_id_raw = state.get("organization_id")

    # Check if we have debt data cached, otherwise fetch it
    debt_items = state.get("debt_items")
    if not debt_items:
        debt_data = await service.get_customer_debt(plex_user_id, customer_name)
        if not debt_data:
            return await _handle_no_debt(db, organization_id, customer_name, dict(state))
        debt_items = debt_data["debt_items"]

    # Get selected invoice from state or message
    selected_invoice = state.get("selected_invoice_number")
    message = MessageExtractor.extract_last_human_message(state) or ""

    # Try to extract invoice number from message if not in state
    if not selected_invoice and message:
        # Simple pattern to find invoice number in message
        import re
        invoice_match = re.search(r"(?:factura|comprobante)\s*(?:n[°o]?)?\s*(\w+)", message.lower())
        if invoice_match:
            selected_invoice = invoice_match.group(1).upper()

    # If still no invoice selected, show first invoice from debt items
    if not selected_invoice and debt_items:
        first_item = debt_items[0] if isinstance(debt_items[0], dict) else debt_items[0]
        selected_invoice = first_item.get("invoice_number") if isinstance(first_item, dict) else getattr(first_item, "invoice_number", None)

    if not selected_invoice:
        # No invoice to show, return to debt view
        return {
            "messages": [{"role": "assistant", "content": "No hay facturas para mostrar. Volviendo a la consulta de deuda..."}],
            "intent": "debt_query",
            "next_node": "debt_manager",
            "is_complete": False,
        }

    # Find the invoice data
    invoice_total = 0.0
    invoice_date = ""

    for item in debt_items:
        item_dict = item if isinstance(item, dict) else item
        item_invoice = item_dict.get("invoice_number") if isinstance(item_dict, dict) else getattr(item_dict, "invoice_number", None)
        if item_invoice == selected_invoice:
            amount_raw = item_dict.get("amount") if isinstance(item_dict, dict) else getattr(item_dict, "amount", 0)
            invoice_total += float(amount_raw or 0)
            if not invoice_date:
                date_raw = item_dict.get("invoice_date") if isinstance(item_dict, dict) else getattr(item_dict, "invoice_date", "")
                invoice_date = str(date_raw) if date_raw else ""

    # Load pharmacy config
    pharmacy_config = await service.load_pharmacy_config(org_id_raw)

    # Format INVOICE_DETAIL response (NO medications shown - privacy rule)
    response_text = DebtFormatterService.format_invoice_detail_response(
        invoice_number=selected_invoice,
        invoice_date=invoice_date,
        invoice_amount=invoice_total,
        pharmacy_config=pharmacy_config,
    )

    return {
        "messages": [{"role": "assistant", "content": response_text}],
        "current_node": "debt_manager",
        "agent_history": ["debt_manager"],
        "selected_invoice_number": selected_invoice,
        # Await invoice detail action (3-option menu)
        "awaiting_input": "invoice_detail_action",
        "next_node": "response_formatter",
        "is_complete": False,
    }


async def _handle_not_authenticated(
    db: AsyncSession,
    organization_id: UUID,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Handle case when customer is not authenticated."""
    content = await _generate_response(
        db=db,
        organization_id=organization_id,
        intent="debt_not_authenticated",
        state=state,
    )
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
    """Handle case when customer has no debt."""
    # Ensure customer_name and pharmacy_name are in state for template rendering
    state_ctx = dict(state) if hasattr(state, "items") else {}
    state_ctx["customer_name"] = customer_name
    state_ctx["pharmacy_name"] = state.get("pharmacy_name") or "Farmacia"

    content = await _generate_response(
        db=db,
        organization_id=organization_id,
        intent="debt_no_debt",
        state=state_ctx,
    )
    return {
        "messages": [{"role": "assistant", "content": content}],
        "current_node": "debt_manager",
        "has_debt": False,
        "is_complete": True,
    }


async def _extract_payment_amount(
    db: AsyncSession | None,
    organization_id: UUID,
    message: str,
) -> float | None:
    """
    Extract payment amount from user message using database-driven patterns.

    Looks for patterns like:
    - "quiero pagar 3000"
    - "pagar $3.000"
    - "3000 pesos"

    Args:
        db: Database session (optional - uses fallback if None)
        organization_id: Organization UUID for multi-tenant support
        message: User message to extract amount from

    Returns:
        Extracted amount as float, or None if no amount found
    """
    # Remove common formatting
    text = message.lower().replace(".", "").replace(",", "")

    # Fallback patterns for resilience
    fallback_patterns = [
        r"pagar\s*\$?\s*(\d+)",
        r"(\d+)\s*(?:pesos?|pe)",
        r"\$\s*(\d+)",
        r"monto\s*(?:de\s*)?\s*(\d+)",
    ]

    # Try to get patterns from database
    regex_patterns: list[str] = []
    try:
        patterns = await domain_intent_cache.get_patterns(db, organization_id, "pharmacy")

        # Look for payment_amount intent patterns
        payment_amount_intent = patterns.get("intents", {}).get("payment_amount", {})
        db_phrases = payment_amount_intent.get("phrases", [])

        # Extract regex patterns from phrases
        for phrase_obj in db_phrases:
            if isinstance(phrase_obj, dict):
                phrase = phrase_obj.get("phrase", "")
                match_type = phrase_obj.get("match_type", "")
                # Only use patterns marked as regex
                if phrase and match_type == "regex":
                    regex_patterns.append(phrase)

        # If no patterns from DB, use fallback
        if not regex_patterns:
            logger.debug("No payment_amount patterns in DB, using fallback patterns")
            regex_patterns = fallback_patterns

    except Exception as e:
        logger.warning(f"Failed to load payment patterns from DB: {e}")
        regex_patterns = fallback_patterns

    # Apply patterns
    for pattern in regex_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                amount = float(match.group(1))
                if amount > 0:
                    return amount
            except (ValueError, IndexError):
                continue

    return None


__all__ = ["debt_manager_node", "DebtManagerService"]
