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


# Alias for compatibility
CreditDomainState = CreditState
