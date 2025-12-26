"""
Excelencia Domain State Schema

TypedDict-based state schema for the Excelencia domain LangGraph.
Handles ERP information, demos, modules, support, and corporate queries via RAG.
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


class ExcelenciaState(TypedDict):
    """
    Excelencia domain state for LangGraph.

    Specialized state schema for handling Software Excelencia queries:
    - Module information
    - Demo requests
    - Training and support
    - Corporate information (via RAG)
    """

    # Core messages with LangGraph reducer
    messages: Annotated[list[BaseMessage], add_messages]

    # Customer context
    customer: dict[str, Any] | None

    # Excelencia specific context
    query_type: str | None  # demo, modules, training, support, products, corporate, general
    mentioned_modules: list[str] | None
    requires_demo: bool | None

    # Intent and routing
    current_intent: dict[str, Any] | None
    excelencia_intent_type: str | None

    # Agent flow state
    current_agent: str | None
    next_agent: str | None
    agent_history: Annotated[list[str], add_agent_history]

    # Responses and data
    agent_responses: Annotated[list[dict[str, Any]], add_agent_responses]
    retrieved_data: Annotated[dict[str, Any], merge_retrieved_data]

    # RAG context
    rag_context: str | None
    knowledge_results: list[dict[str, Any]] | None

    # Module information
    module_info: dict[str, Any] | None

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
ExcelenciaDomainState = ExcelenciaState
