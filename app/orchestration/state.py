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


def merge_domain_states(
    left: dict[str, dict[str, Any]],
    right: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Reducer for domain states - deep merge per domain.

    Merges domain-specific state dictionaries, preserving existing
    state while updating with new values per domain.
    """
    result = {**left}
    for domain_key, state in right.items():
        if domain_key in result:
            # Merge existing domain state with updates
            result[domain_key] = {**result[domain_key], **state}
        else:
            # Add new domain state
            result[domain_key] = state
    return result


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

    # =========================================================================
    # GENERIC DOMAIN STATE CONTAINER
    # =========================================================================
    # Stores domain-specific state for any domain (pharmacy, ecommerce, etc.)
    # Replaces hardcoded domain fields with a generic container.
    # Each domain's state is stored under its domain_key.
    # Example: {"pharmacy": {...}, "ecommerce": {...}}
    domain_states: Annotated[dict[str, dict[str, Any]], merge_domain_states]

    # Multi-tenant context (shared across all domains)
    organization_id: str | None


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
    domain_key: str | None = None,
    organization_id: str | None = None,
) -> dict[str, Any]:
    """
    Create initial orchestration state.

    Args:
        message: Initial user message
        customer: Customer context
        conversation_id: Conversation identifier
        domain_key: Optional domain to pre-initialize state for
        organization_id: Organization UUID for multi-tenant context

    Returns:
        Initial state dictionary
    """
    from datetime import datetime

    from langchain_core.messages import HumanMessage

    from app.orchestration.domain_state_registry import DomainStateRegistry

    # Initialize domain_states with requested domain (or empty)
    domain_states: dict[str, dict[str, Any]] = {}
    if domain_key:
        domain_states[domain_key] = DomainStateRegistry.get_defaults(domain_key)
        # Set whatsapp_phone in pharmacy domain state if customer has phone
        if domain_key == "pharmacy" and customer and customer.get("phone"):
            domain_states[domain_key]["whatsapp_phone"] = customer.get("phone")

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
        # Generic domain state container
        "domain_states": domain_states,
        # Multi-tenant context
        "organization_id": organization_id,
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


# =============================================================================
# Domain State Helper Functions
# =============================================================================


def get_domain_state(state: dict[str, Any], domain_key: str) -> dict[str, Any]:
    """
    Extract domain-specific state from orchestration state.

    Args:
        state: Orchestration state dictionary
        domain_key: Domain identifier (e.g., 'pharmacy', 'ecommerce')

    Returns:
        Domain-specific state dictionary, or empty dict if not found
    """
    domain_states = state.get("domain_states", {})
    return domain_states.get(domain_key, {})


def update_domain_state(
    state: dict[str, Any],
    domain_key: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """
    Create state updates for a specific domain.

    Returns a dictionary that can be merged with the orchestration state
    to update domain-specific fields.

    Args:
        state: Current orchestration state
        domain_key: Domain identifier
        updates: Fields to update in the domain state

    Returns:
        State update dictionary with domain_states key
    """
    current_domain_state = get_domain_state(state, domain_key)
    return {
        "domain_states": {
            domain_key: {**current_domain_state, **updates}
        }
    }


def ensure_domain_initialized(
    state: dict[str, Any],
    domain_key: str,
) -> dict[str, Any]:
    """
    Ensure domain state is initialized with defaults.

    If the domain state doesn't exist, initializes it with default values
    from the DomainStateRegistry.

    Args:
        state: Current orchestration state
        domain_key: Domain identifier

    Returns:
        State update dictionary with initialized domain_states
    """
    from app.orchestration.domain_state_registry import DomainStateRegistry

    domain_states = state.get("domain_states", {})

    if domain_key not in domain_states:
        domain_states = {
            **domain_states,
            domain_key: DomainStateRegistry.get_defaults(domain_key),
        }

    return {"domain_states": domain_states}


def extract_domain_fields_from_result(
    result: dict[str, Any],
    domain_key: str,
) -> dict[str, Any]:
    """
    Extract domain-specific fields from a subgraph result.

    Uses the DomainStateRegistry to identify which fields belong
    to the domain's state schema.

    Args:
        result: Result dictionary from subgraph execution
        domain_key: Domain identifier

    Returns:
        Dictionary containing only domain-specific fields
    """
    from app.orchestration.domain_state_registry import DomainStateRegistry

    field_names = DomainStateRegistry.get_field_names(domain_key)
    domain_fields: dict[str, Any] = {}

    for field in field_names:
        # Skip 'messages' as it's handled separately by the reducer
        if field in result and field != "messages":
            domain_fields[field] = result[field]

    return domain_fields
