"""
Orchestration State

Shared state schema for the super orchestrator.
"""

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def add_domain_history(left: list[str], right: list[str]) -> list[str]:
    """Reducer for domain history."""
    return left + right


def merge_context(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Reducer for context (merge dictionaries)."""
    return {**left, **right}


def add_routing_decisions(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Reducer for routing decisions history."""
    return left + right


class OrchestrationState(TypedDict):
    """
    State schema for the super orchestrator.

    Manages cross-domain routing, context sharing, and conversation flow.
    """

    # Core messages with LangGraph reducer
    messages: Annotated[list[BaseMessage], add_messages]

    # Customer/User context
    customer: dict[str, Any] | None
    customer_id: int | None
    phone: str | None

    # Domain routing
    current_domain: str | None  # ecommerce, healthcare, credit, excelencia
    target_domain: str | None
    domain_history: Annotated[list[str], add_domain_history]

    # Intent analysis
    current_intent: dict[str, Any] | None
    intent_type: str | None
    intent_confidence: float

    # Routing decisions
    routing_decision: dict[str, Any] | None
    routing_history: Annotated[list[dict[str, Any]], add_routing_decisions]

    # Shared context across domains
    shared_context: Annotated[dict[str, Any], merge_context]

    # Domain-specific context (populated by domain services)
    ecommerce_context: dict[str, Any] | None
    healthcare_context: dict[str, Any] | None
    credit_context: dict[str, Any] | None
    excelencia_context: dict[str, Any] | None

    # Response from domain service
    domain_response: dict[str, Any] | None
    final_response: str | None

    # Control flow
    is_complete: bool
    error_count: int
    max_errors: int
    requires_human: bool
    is_emergency: bool

    # Conversation metadata
    conversation_id: str | None
    thread_id: str | None
    timestamp: str | None
    language: str


class DomainContext(TypedDict, total=False):
    """Common context shared between domains."""

    # Customer information
    customer_id: int
    customer_name: str
    customer_phone: str
    customer_email: str

    # Conversation context
    conversation_summary: str
    previous_intents: list[str]
    last_domain: str

    # Session information
    session_start: str
    messages_count: int

    # Business context
    active_orders: list[dict[str, Any]]
    active_appointments: list[dict[str, Any]]
    active_accounts: list[dict[str, Any]]


def create_initial_state(
    message: str | None = None,
    customer: dict[str, Any] | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """
    Create initial orchestration state.

    Args:
        message: Initial user message
        customer: Customer context
        conversation_id: Conversation identifier

    Returns:
        Initial state dictionary
    """
    from datetime import datetime
    from langchain_core.messages import HumanMessage

    state: dict[str, Any] = {
        "messages": [],
        "customer": customer,
        "customer_id": customer.get("id") if customer else None,
        "phone": customer.get("phone") if customer else None,
        "current_domain": None,
        "target_domain": None,
        "domain_history": [],
        "current_intent": None,
        "intent_type": None,
        "intent_confidence": 0.0,
        "routing_decision": None,
        "routing_history": [],
        "shared_context": {},
        "ecommerce_context": None,
        "healthcare_context": None,
        "credit_context": None,
        "excelencia_context": None,
        "domain_response": None,
        "final_response": None,
        "is_complete": False,
        "error_count": 0,
        "max_errors": 3,
        "requires_human": False,
        "is_emergency": False,
        "conversation_id": conversation_id,
        "thread_id": conversation_id,
        "timestamp": datetime.now().isoformat(),
        "language": "es",
    }

    if message:
        state["messages"] = [HumanMessage(content=message)]

    return state


def extract_domain_context(
    state: dict[str, Any],
    domain: str,
) -> dict[str, Any]:
    """
    Extract domain-specific context from orchestration state.

    Args:
        state: Orchestration state
        domain: Target domain

    Returns:
        Domain-specific context dictionary
    """
    base_context = {
        "customer": state.get("customer"),
        "customer_id": state.get("customer_id"),
        "phone": state.get("phone"),
        "conversation_id": state.get("conversation_id"),
        "language": state.get("language", "es"),
        "shared_context": state.get("shared_context", {}),
    }

    # Add domain-specific context if available
    domain_key = f"{domain}_context"
    if state.get(domain_key):
        base_context[domain_key] = state[domain_key]

    return base_context


def update_state_after_domain(
    state: dict[str, Any],
    domain: str,
    response: dict[str, Any],
) -> dict[str, Any]:
    """
    Update orchestration state after domain processing.

    Args:
        state: Current state
        domain: Domain that processed the request
        response: Response from domain service

    Returns:
        Updated state dictionary
    """
    updates: dict[str, Any] = {
        "domain_response": response,
        "domain_history": [domain],
        "current_domain": domain,
    }

    # Extract final response if available
    if response.get("response"):
        updates["final_response"] = response["response"]

    # Update domain-specific context if returned
    domain_key = f"{domain}_context"
    if response.get("context"):
        updates[domain_key] = response["context"]

    # Update shared context
    if response.get("shared_context"):
        updates["shared_context"] = response["shared_context"]

    # Check completion status
    if response.get("is_complete"):
        updates["is_complete"] = True

    return updates
