"""
Custom assertions and verification helpers for tests.

Provides reusable assertion functions for common testing patterns.
"""

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock


def assert_product_valid(product: Dict[str, Any]) -> None:
    """
    Assert that a product dictionary has all required fields.

    Args:
        product: Product dictionary to validate

    Raises:
        AssertionError: If product is invalid
    """
    required_fields = ["id", "name", "price", "stock"]
    for field in required_fields:
        assert field in product, f"Product missing required field: {field}"

    assert isinstance(product["id"], int), "Product ID must be an integer"
    assert isinstance(product["name"], str), "Product name must be a string"
    assert isinstance(product["price"], (int, float)), "Product price must be numeric"
    assert isinstance(product["stock"], int), "Product stock must be an integer"
    assert product["price"] >= 0, "Product price must be non-negative"
    assert product["stock"] >= 0, "Product stock must be non-negative"


def assert_customer_valid(customer: Dict[str, Any]) -> None:
    """
    Assert that a customer dictionary has all required fields.

    Args:
        customer: Customer dictionary to validate

    Raises:
        AssertionError: If customer is invalid
    """
    required_fields = ["id", "phone", "name"]
    for field in required_fields:
        assert field in customer, f"Customer missing required field: {field}"

    assert isinstance(customer["id"], int), "Customer ID must be an integer"
    assert isinstance(customer["phone"], str), "Customer phone must be a string"
    assert isinstance(customer["name"], str), "Customer name must be a string"
    assert customer["phone"].startswith("+"), "Phone must start with country code"


def assert_agent_state_valid(state: Dict[str, Any]) -> None:
    """
    Assert that an agent state dictionary has all required fields.

    Args:
        state: Agent state dictionary to validate

    Raises:
        AssertionError: If state is invalid
    """
    required_fields = ["messages", "phone", "flow_control"]
    for field in required_fields:
        assert field in state, f"State missing required field: {field}"

    assert isinstance(state["messages"], list), "Messages must be a list"
    assert isinstance(state["phone"], str), "Phone must be a string"
    assert isinstance(state["flow_control"], dict), "Flow control must be a dict"

    flow_control = state["flow_control"]
    assert "should_end" in flow_control, "Flow control must have should_end field"
    assert isinstance(flow_control["should_end"], bool), "should_end must be boolean"


def assert_repository_called_with(
    mock_repo: Mock,
    method_name: str,
    *args,
    **kwargs,
) -> None:
    """
    Assert that a repository method was called with specific arguments.

    Args:
        mock_repo: Mock repository object
        method_name: Name of the method to check
        *args: Expected positional arguments
        **kwargs: Expected keyword arguments

    Raises:
        AssertionError: If method was not called correctly
    """
    method = getattr(mock_repo, method_name)
    assert method.called, f"Repository method '{method_name}' was not called"

    if args or kwargs:
        method.assert_called_with(*args, **kwargs)


def assert_llm_called(
    mock_llm: AsyncMock,
    expected_calls: Optional[int] = None,
) -> None:
    """
    Assert that an LLM was called the expected number of times.

    Args:
        mock_llm: Mock LLM object
        expected_calls: Expected number of calls (None = at least once)

    Raises:
        AssertionError: If LLM was not called correctly
    """
    if expected_calls is None:
        assert mock_llm.ainvoke.called or mock_llm.invoke.called, "LLM was not called"
    else:
        actual_calls = mock_llm.ainvoke.call_count + mock_llm.invoke.call_count
        assert actual_calls == expected_calls, (
            f"Expected {expected_calls} LLM calls, got {actual_calls}"
        )


def assert_messages_contain(
    messages: List[Dict[str, Any]],
    content: str,
    role: Optional[str] = None,
) -> None:
    """
    Assert that messages contain specific content.

    Args:
        messages: List of message dictionaries
        content: Content to search for
        role: Optional role to filter by

    Raises:
        AssertionError: If content not found in messages
    """
    for msg in messages:
        if role and msg.get("role") != role:
            continue

        if content in msg.get("content", ""):
            return

    role_desc = f" with role '{role}'" if role else ""
    raise AssertionError(
        f"Content '{content}' not found in messages{role_desc}"
    )


def assert_routing_to_domain(
    state: Dict[str, Any],
    expected_domain: str,
) -> None:
    """
    Assert that state routing is configured for a specific domain.

    Args:
        state: Agent state dictionary
        expected_domain: Expected domain name

    Raises:
        AssertionError: If routing is not configured correctly
    """
    assert "routing" in state, "State must have routing information"
    routing = state["routing"]

    assert "detected_domain" in routing, "Routing must have detected_domain"
    actual_domain = routing["detected_domain"]

    assert actual_domain == expected_domain, (
        f"Expected domain '{expected_domain}', got '{actual_domain}'"
    )


def assert_intent_detected(
    state: Dict[str, Any],
    expected_intent: str,
) -> None:
    """
    Assert that the correct intent was detected.

    Args:
        state: Agent state dictionary
        expected_intent: Expected intent value

    Raises:
        AssertionError: If intent is not correct
    """
    assert "intent" in state, "State must have intent field"
    actual_intent = state["intent"]

    assert actual_intent == expected_intent, (
        f"Expected intent '{expected_intent}', got '{actual_intent}'"
    )


def assert_flow_should_end(state: Dict[str, Any]) -> None:
    """
    Assert that the conversation flow should end.

    Args:
        state: Agent state dictionary

    Raises:
        AssertionError: If flow is not set to end
    """
    assert "flow_control" in state, "State must have flow_control"
    flow_control = state["flow_control"]

    assert flow_control.get("should_end") is True, "Flow should be set to end"


def assert_flow_should_continue(state: Dict[str, Any]) -> None:
    """
    Assert that the conversation flow should continue.

    Args:
        state: Agent state dictionary

    Raises:
        AssertionError: If flow is set to end
    """
    assert "flow_control" in state, "State must have flow_control"
    flow_control = state["flow_control"]

    assert flow_control.get("should_end") is not True, "Flow should continue"


def assert_next_node(
    state: Dict[str, Any],
    expected_node: str,
) -> None:
    """
    Assert that the next node is set correctly.

    Args:
        state: Agent state dictionary
        expected_node: Expected next node

    Raises:
        AssertionError: If next node is not correct
    """
    assert "flow_control" in state, "State must have flow_control"
    flow_control = state["flow_control"]

    actual_node = flow_control.get("next_node")
    assert actual_node == expected_node, (
        f"Expected next node '{expected_node}', got '{actual_node}'"
    )


def assert_has_response_message(state: Dict[str, Any]) -> None:
    """
    Assert that state contains at least one assistant response message.

    Args:
        state: Agent state dictionary

    Raises:
        AssertionError: If no response message found
    """
    assert "messages" in state, "State must have messages"
    messages = state["messages"]

    assistant_messages = [
        msg for msg in messages
        if msg.get("role") == "assistant"
    ]

    assert len(assistant_messages) > 0, "No assistant response message found"


def assert_data_contains(
    state: Dict[str, Any],
    key: str,
    value: Optional[Any] = None,
) -> None:
    """
    Assert that state data contains a specific key and optionally value.

    Args:
        state: Agent state dictionary
        key: Key to check for
        value: Optional expected value

    Raises:
        AssertionError: If data doesn't contain key or value
    """
    assert "data" in state, "State must have data field"
    data = state["data"]

    assert key in data, f"Data must contain key '{key}'"

    if value is not None:
        actual_value = data[key]
        assert actual_value == value, (
            f"Expected data['{key}'] to be '{value}', got '{actual_value}'"
        )
