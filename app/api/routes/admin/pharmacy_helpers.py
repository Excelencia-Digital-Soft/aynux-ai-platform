# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Helper functions for Pharmacy Admin API.
# ============================================================================
"""
Pharmacy Helpers - Message serialization and graph visualization.

Provides helper functions for LangChain message serialization/deserialization
and graph node definitions for the pharmacy agent visualization.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.api.routes.admin.pharmacy_models import (
    GraphDataResponse,
    PharmacySessionState,
    SerializedMessage,
)

# ============================================================
# MESSAGE SERIALIZATION
# ============================================================


def serialize_messages(messages: list[BaseMessage]) -> list[SerializedMessage]:
    """
    Convert LangChain messages to serializable format.

    Args:
        messages: List of LangChain BaseMessage objects

    Returns:
        List of SerializedMessage objects suitable for Redis storage
    """
    result: list[SerializedMessage] = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            result.append(
                SerializedMessage(
                    role="human",
                    content=str(msg.content),
                    timestamp=datetime.now().isoformat(),
                )
            )
        elif isinstance(msg, AIMessage):
            result.append(
                SerializedMessage(
                    role="ai",
                    content=str(msg.content),
                    timestamp=datetime.now().isoformat(),
                )
            )
    return result


def deserialize_messages(messages: list[SerializedMessage]) -> list[BaseMessage]:
    """
    Convert serialized messages back to LangChain format.

    Args:
        messages: List of SerializedMessage objects

    Returns:
        List of LangChain BaseMessage objects
    """
    result: list[BaseMessage] = []
    for msg in messages:
        if msg.role == "human":
            result.append(HumanMessage(content=msg.content))
        elif msg.role == "ai":
            result.append(AIMessage(content=msg.content))
    return result


def extract_bot_response(result: dict[str, Any]) -> str:
    """
    Extract the last AIMessage content from graph result.

    Args:
        result: Graph execution result dictionary

    Returns:
        The content of the last AI message, or default message if none found
    """
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return str(msg.content)
    return "[Sin respuesta generada]"


def extract_interactive_data(result: dict[str, Any]) -> dict[str, Any]:
    """
    Extract interactive message data (buttons/list) from graph result.

    Args:
        result: Graph execution result dictionary

    Returns:
        Dictionary with response_type, response_buttons, and response_list_items
    """
    response_type = result.get("response_type", "text")
    response_buttons = result.get("response_buttons")
    response_list_items = result.get("response_list_items")

    # Convert to proper format if present
    formatted_buttons = None
    formatted_list_items = None

    if response_buttons:
        formatted_buttons = [
            {"id": btn.get("id", f"btn_{i}"), "titulo": btn.get("titulo", "")}
            for i, btn in enumerate(response_buttons)
        ]

    if response_list_items:
        formatted_list_items = [
            {
                "id": item.get("id", f"item_{i}"),
                "titulo": item.get("titulo", ""),
                "descripcion": item.get("descripcion"),
            }
            for i, item in enumerate(response_list_items)
        ]

    return {
        "response_type": response_type,
        "response_buttons": formatted_buttons,
        "response_list_items": formatted_list_items,
    }


# ============================================================
# STATE BUILDERS
# ============================================================


def build_graph_state(
    session: PharmacySessionState,
    organization_id: str,
    pharmacy_id: str,
    previous_messages: list[BaseMessage],
    new_message: HumanMessage,
) -> dict[str, Any]:
    """
    Build the graph state dictionary for PharmacyGraph invocation.

    Args:
        session: Current session state
        organization_id: Organization UUID string
        pharmacy_id: Pharmacy config ID (unique per pharmacy)
        previous_messages: List of previous LangChain messages
        new_message: New human message to process

    Returns:
        Dictionary ready for graph.app.ainvoke()
    """
    all_messages = list(previous_messages) + [new_message]

    return {
        "messages": all_messages,
        "customer_id": session.customer_id,
        "organization_id": organization_id,
        "pharmacy_id": pharmacy_id,
        # Pharmacy configuration (CRITICAL for multi-turn)
        "pharmacy_name": session.pharmacy_name,
        "pharmacy_phone": session.pharmacy_phone,
        "is_bypass_route": True,
        "is_complete": False,
        "error_count": session.error_count,
        "has_debt": session.has_debt,
        "awaiting_confirmation": session.awaiting_confirmation,
        "customer_identified": session.customer_identified,
        # Restore state for multi-turn
        "plex_customer_id": session.plex_customer_id,
        "plex_customer": session.plex_customer,
        "total_debt": session.total_debt,
        "debt_data": session.debt_data,
        "debt_status": session.debt_status,
        "debt_id": session.debt_id,
        "confirmation_received": session.confirmation_received,
        "workflow_step": session.workflow_step,
        "mp_preference_id": session.mp_preference_id,
        "mp_init_point": session.mp_init_point,
        "mp_payment_status": session.mp_payment_status,
        "mp_external_reference": session.mp_external_reference,
        "awaiting_payment": session.awaiting_payment,
        "payment_amount": session.payment_amount,
        "is_partial_payment": session.is_partial_payment,
        "awaiting_registration_data": session.awaiting_registration_data,
        "registration_step": session.registration_step,
        # Person resolution state (CRITICAL for multi-turn identification)
        "identification_step": session.identification_step,
        "plex_customer_to_confirm": session.plex_customer_to_confirm,
        "name_mismatch_count": session.name_mismatch_count,
        "awaiting_own_or_other": session.awaiting_own_or_other,
        "validation_step": session.validation_step,
        # Account selection state
        "registered_accounts_for_selection": session.registered_accounts_for_selection,
        "account_count": session.account_count,
    }


def update_session_from_result(
    session: PharmacySessionState,
    result: dict[str, Any],
) -> None:
    """
    Update session state from graph execution result.

    Args:
        session: Session state to update (modified in place)
        result: Graph execution result dictionary
    """
    session.messages = serialize_messages(result.get("messages", []))
    # Pharmacy configuration (preserve for multi-turn)
    if result.get("pharmacy_name"):
        session.pharmacy_name = result.get("pharmacy_name")
    if result.get("pharmacy_phone"):
        session.pharmacy_phone = result.get("pharmacy_phone")
    session.customer_identified = result.get("customer_identified", False)
    session.plex_customer_id = result.get("plex_customer_id")
    session.plex_customer = result.get("plex_customer")
    session.has_debt = result.get("has_debt", False)
    session.total_debt = result.get("total_debt")
    session.debt_data = result.get("debt_data")
    session.debt_status = result.get("debt_status")
    session.debt_id = result.get("debt_id")
    session.awaiting_confirmation = result.get("awaiting_confirmation", False)
    session.confirmation_received = result.get("confirmation_received", False)
    session.workflow_step = result.get("workflow_step")
    session.is_complete = result.get("is_complete", False)
    session.error_count = result.get("error_count", 0)
    session.mp_preference_id = result.get("mp_preference_id")
    session.mp_init_point = result.get("mp_init_point")
    session.mp_payment_status = result.get("mp_payment_status")
    session.mp_external_reference = result.get("mp_external_reference")
    session.awaiting_payment = result.get("awaiting_payment", False)
    session.payment_amount = result.get("payment_amount")
    session.is_partial_payment = result.get("is_partial_payment", False)
    session.awaiting_registration_data = result.get("awaiting_registration_data", False)
    session.registration_step = result.get("registration_step")
    # Person resolution state (CRITICAL for multi-turn identification)
    session.identification_step = result.get("identification_step")
    session.plex_customer_to_confirm = result.get("plex_customer_to_confirm")
    session.name_mismatch_count = result.get("name_mismatch_count", 0)
    session.awaiting_own_or_other = result.get("awaiting_own_or_other", False)
    session.validation_step = result.get("validation_step")
    # Account selection state
    session.registered_accounts_for_selection = result.get("registered_accounts_for_selection")
    session.account_count = result.get("account_count")


# ============================================================
# GRAPH VISUALIZATION
# ============================================================


def get_pharmacy_graph_data(session: PharmacySessionState) -> GraphDataResponse:
    """
    Get pharmacy graph visualization data for a session.

    Args:
        session: Current session state

    Returns:
        GraphDataResponse with nodes and edges for visualization
    """
    nodes = [
        {"id": "customer_identification_node", "label": "Identificacion", "type": "entry"},
        {"id": "customer_registration_node", "label": "Registro", "type": "registration"},
        {"id": "pharmacy_router", "label": "Router", "type": "router"},
        {"id": "debt_check_node", "label": "Consulta Deuda", "type": "operation"},
        {"id": "confirmation_node", "label": "Confirmacion", "type": "operation"},
        {"id": "invoice_generation_node", "label": "Recibo", "type": "operation"},
        {"id": "payment_link_node", "label": "Link de Pago", "type": "operation"},
    ]

    edges = [
        {"from": "customer_identification_node", "to": "pharmacy_router"},
        {"from": "customer_identification_node", "to": "customer_registration_node"},
        {"from": "customer_registration_node", "to": "pharmacy_router"},
        {"from": "pharmacy_router", "to": "debt_check_node"},
        {"from": "pharmacy_router", "to": "confirmation_node"},
        {"from": "pharmacy_router", "to": "invoice_generation_node"},
        {"from": "pharmacy_router", "to": "payment_link_node"},
        {"from": "debt_check_node", "to": "pharmacy_router"},
        {"from": "confirmation_node", "to": "pharmacy_router"},
        {"from": "confirmation_node", "to": "payment_link_node"},
    ]

    return GraphDataResponse(
        session_id=session.session_id,
        nodes=nodes,
        edges=edges,
        current_node=session.workflow_step,
        visited_nodes=[],  # Could track this in session if needed
    )


def build_session_graph_state(session: PharmacySessionState) -> dict[str, Any]:
    """
    Build graph state dictionary from session for API responses.

    Args:
        session: Current session state

    Returns:
        Dictionary with key graph state values
    """
    return {
        "customer_identified": session.customer_identified,
        "has_debt": session.has_debt,
        "total_debt": session.total_debt,
        "debt_status": session.debt_status,
        "workflow_step": session.workflow_step,
        "awaiting_confirmation": session.awaiting_confirmation,
        "is_complete": session.is_complete,
        "awaiting_payment": session.awaiting_payment,
        "mp_init_point": session.mp_init_point,
    }
