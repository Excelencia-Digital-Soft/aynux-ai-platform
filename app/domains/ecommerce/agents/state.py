"""
E-commerce Domain State Schema

TypedDict-based state schema for the e-commerce domain LangGraph.
Follows the same pattern as the main LangGraphState but specialized for e-commerce.
"""

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def add_agent_responses(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reducer for agent responses."""
    return left + right


def merge_retrieved_data(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Reducer for retrieved data (merge dictionaries)."""
    return {**left, **right}


def add_agent_history(left: list[str], right: list[str]) -> list[str]:
    """Reducer for agent history."""
    return left + right


class EcommerceState(TypedDict):
    """
    E-commerce domain state for LangGraph.

    Specialized state schema for handling product queries, orders,
    promotions, tracking, and billing in the e-commerce domain.
    """

    # Core messages with LangGraph reducer
    messages: Annotated[list[BaseMessage], add_messages]

    # Customer context
    customer: dict[str, Any] | None

    # E-commerce specific context
    cart: dict[str, Any] | None  # Shopping cart state
    current_order: dict[str, Any] | None  # Active order being discussed
    product_context: dict[str, Any] | None  # Current product(s) in focus

    # Intent and routing
    current_intent: dict[str, Any] | None
    ecommerce_intent_type: str | None  # product_search, order_tracking, billing, promotions, etc.

    # Agent flow state
    current_agent: str | None
    next_agent: str | None
    agent_history: Annotated[list[str], add_agent_history]

    # Responses and data
    agent_responses: Annotated[list[dict[str, Any]], add_agent_responses]
    retrieved_data: Annotated[dict[str, Any], merge_retrieved_data]

    # Product search specific
    search_results: list[dict[str, Any]] | None
    search_metadata: dict[str, Any] | None
    selected_products: list[dict[str, Any]] | None

    # Order tracking specific
    tracking_info: dict[str, Any] | None

    # Promotions specific
    active_promotions: list[dict[str, Any]] | None
    applied_coupons: list[str] | None

    # Billing/Invoice specific
    invoice_info: dict[str, Any] | None
    payment_status: str | None

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
EcommerceDomainState = EcommerceState
