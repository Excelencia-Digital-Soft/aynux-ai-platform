"""
Pharmacy Domain State Schema

TypedDict-based state schema for the pharmacy domain LangGraph.
Handles debt queries, confirmations, and invoice generation.
"""

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def merge_retrieved_data(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Reducer for retrieved data."""
    return {**left, **right}


def add_agent_history(left: list[str], right: list[str]) -> list[str]:
    """Reducer for agent history."""
    return left + right


class PharmacyState(TypedDict):
    """
    Pharmacy domain state for LangGraph.

    Specialized state schema for handling pharmacy debt workflows:
    - Debt checking (consulta deuda)
    - Confirmation (confirmar)
    - Invoice generation (generar factura)
    """

    # Core messages with LangGraph reducer
    messages: Annotated[list[BaseMessage], add_messages]

    # Customer context
    customer_id: str | None  # Phone number or ERP ID
    customer_name: str | None

    # Debt context
    debt_id: str | None  # Current debt being processed
    debt_data: dict[str, Any] | None  # Full debt information
    debt_status: str | None  # pending, confirmed, invoiced
    total_debt: float | None
    has_debt: bool

    # Invoice context
    invoice_id: str | None
    invoice_number: str | None
    pdf_url: str | None

    # Workflow state (for transactional flow)
    workflow_step: str | None  # check_debt, confirmation, invoice
    awaiting_confirmation: bool  # Waiting for user to confirm
    confirmation_received: bool  # User confirmed

    # Intent and routing
    current_intent: dict[str, Any] | None
    pharmacy_intent_type: str | None  # debt_query, confirm, invoice

    # Agent flow state
    current_agent: str | None
    next_agent: str | None
    agent_history: Annotated[list[str], add_agent_history]

    # Retrieved data
    retrieved_data: Annotated[dict[str, Any], merge_retrieved_data]

    # Control flow
    is_complete: bool
    error_count: int
    max_errors: int
    requires_human: bool

    # Routing decisions
    routing_decision: dict[str, Any] | None

    # Conversation metadata
    conversation_id: str | None
    timestamp: str | None

    # Bypass indicator (set by routing)
    is_bypass_route: bool  # True if came via bypass routing


# Alias for compatibility
PharmacyDomainState = PharmacyState
