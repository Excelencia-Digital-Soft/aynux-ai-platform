"""
Credit Domain State Schema

TypedDict-based state schema for the credit domain LangGraph.
Handles credit accounts, payments, schedules, and collections.
"""

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def add_agent_responses(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reducer for agent responses."""
    return left + right


def merge_retrieved_data(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Reducer for retrieved data."""
    return {**left, **right}


def add_agent_history(left: list[str], right: list[str]) -> list[str]:
    """Reducer for agent history."""
    return left + right


class CreditState(TypedDict):
    """
    Credit domain state for LangGraph.

    Specialized state schema for handling credit inquiries, payments,
    schedules, and collection management.
    """

    # Core messages with LangGraph reducer
    messages: Annotated[list[BaseMessage], add_messages]

    # Customer context
    customer: dict[str, Any] | None

    # Credit specific context
    credit_account: dict[str, Any] | None  # Current credit account
    credit_account_id: str | None
    account_status: str | None  # active, delinquent, closed, etc.

    # Intent and routing
    current_intent: dict[str, Any] | None
    credit_intent_type: str | None  # balance, payment, schedule, collections

    # Agent flow state
    current_agent: str | None
    next_agent: str | None
    agent_history: Annotated[list[str], add_agent_history]

    # Responses and data
    agent_responses: Annotated[list[dict[str, Any]], add_agent_responses]
    retrieved_data: Annotated[dict[str, Any], merge_retrieved_data]

    # Balance specific
    credit_balance: dict[str, Any] | None
    credit_limit: float | None
    used_credit: float | None
    available_credit: float | None

    # Payment specific
    payment_info: dict[str, Any] | None
    pending_payments: list[dict[str, Any]] | None
    payment_history: list[dict[str, Any]] | None

    # Schedule specific
    payment_schedule: list[dict[str, Any]] | None
    next_payment: dict[str, Any] | None

    # Collections specific
    collection_status: str | None
    overdue_amount: float | None
    days_overdue: int | None

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


# =============================================================================
# Domain State Registry Interface
# =============================================================================
# These module-level constants and functions enable auto-discovery by
# DomainStateRegistry for generic state management.

DOMAIN_KEY = "credit"
"""Domain key for registry discovery."""

STATE_CLASS = CreditState
"""State TypedDict class for this domain."""


def get_state_defaults() -> dict[str, Any]:
    """
    Return default values for all credit state fields.

    Used by DomainStateRegistry for generic state initialization.
    """
    return {
        # Core messages
        "messages": [],
        # Customer context
        "customer": None,
        # Credit specific context
        "credit_account": None,
        "credit_account_id": None,
        "account_status": None,
        # Intent and routing
        "current_intent": None,
        "credit_intent_type": None,
        # Agent flow state
        "current_agent": None,
        "next_agent": None,
        "agent_history": [],
        # Responses and data
        "agent_responses": [],
        "retrieved_data": {},
        # Balance specific
        "credit_balance": None,
        "credit_limit": None,
        "used_credit": None,
        "available_credit": None,
        # Payment specific
        "payment_info": None,
        "pending_payments": None,
        "payment_history": None,
        # Schedule specific
        "payment_schedule": None,
        "next_payment": None,
        # Collections specific
        "collection_status": None,
        "overdue_amount": None,
        "days_overdue": None,
        # Control flow
        "is_complete": False,
        "error_count": 0,
        "max_errors": 3,
        "requires_human": False,
        # Routing decisions
        "routing_decision": None,
        # Conversation metadata
        "conversation_id": None,
        "timestamp": None,
    }


# Alias for compatibility
CreditDomainState = CreditState
