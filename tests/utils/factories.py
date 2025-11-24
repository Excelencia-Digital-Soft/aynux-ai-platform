"""
Mock factories for creating test objects quickly.

Provides simple functions to create mock objects without the builder pattern
when you just need default values.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional


def create_mock_product(
    product_id: int = 1,
    name: str = "Test Product",
    price: float = 99.99,
    stock: int = 10,
    **kwargs,
) -> Dict[str, Any]:
    """
    Create a mock product with default values.

    Args:
        product_id: Product ID
        name: Product name
        price: Product price
        stock: Stock quantity
        **kwargs: Additional product fields

    Returns:
        Dictionary representing a product
    """
    product = {
        "id": product_id,
        "name": name,
        "description": f"Description for {name}",
        "price": price,
        "stock": stock,
        "category_id": 1,
        "sku": f"SKU-{product_id:03d}",
        "active": True,
        "created_at": datetime.now(),
    }
    product.update(kwargs)
    return product


def create_mock_customer(
    customer_id: int = 1,
    phone: str = "+5491234567890",
    name: str = "Test Customer",
    **kwargs,
) -> Dict[str, Any]:
    """
    Create a mock customer with default values.

    Args:
        customer_id: Customer ID
        phone: Phone number
        name: Customer name
        **kwargs: Additional customer fields

    Returns:
        Dictionary representing a customer
    """
    customer = {
        "id": customer_id,
        "phone": phone,
        "name": name,
        "email": f"customer{customer_id}@example.com",
        "active": True,
        "created_at": datetime.now(),
    }
    customer.update(kwargs)
    return customer


def create_mock_conversation(
    conv_id: str = "conv-123",
    phone: str = "+5491234567890",
    customer_id: int = 1,
    messages: Optional[List[Dict]] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Create a mock conversation with default values.

    Args:
        conv_id: Conversation ID
        phone: Phone number
        customer_id: Customer ID
        messages: List of messages
        **kwargs: Additional conversation fields

    Returns:
        Dictionary representing a conversation
    """
    conversation = {
        "id": conv_id,
        "phone": phone,
        "customer_id": customer_id,
        "messages": messages or [],
        "status": "active",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }
    conversation.update(kwargs)
    return conversation


def create_mock_order(
    order_id: int = 1,
    customer_id: int = 1,
    total: float = 199.98,
    items: Optional[List[Dict]] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Create a mock order with default values.

    Args:
        order_id: Order ID
        customer_id: Customer ID
        total: Order total
        items: List of order items
        **kwargs: Additional order fields

    Returns:
        Dictionary representing an order
    """
    order = {
        "id": order_id,
        "customer_id": customer_id,
        "total": total,
        "status": "pending",
        "items": items or [
            {"product_id": 1, "quantity": 2, "price": 99.99}
        ],
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }
    order.update(kwargs)
    return order


def create_mock_agent_state(
    phone: str = "+5491234567890",
    customer_name: str = "Test User",
    intent: Optional[str] = None,
    messages: Optional[List[Dict]] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Create a mock agent state with default values.

    Args:
        phone: Phone number
        customer_name: Customer name
        intent: Detected intent
        messages: List of messages
        **kwargs: Additional state fields

    Returns:
        Dictionary representing agent state
    """
    state = {
        "messages": messages or [],
        "phone": phone,
        "customer_name": customer_name,
        "intent": intent,
        "routing": {},
        "data": {},
        "flow_control": {
            "next_node": None,
            "should_end": False,
        },
        "metadata": {
            "timestamp": datetime.now().isoformat(),
        },
    }
    state.update(kwargs)
    return state


def create_mock_message(
    role: str = "user",
    content: str = "Test message",
    **kwargs,
) -> Dict[str, Any]:
    """
    Create a mock message.

    Args:
        role: Message role (user, assistant, system)
        content: Message content
        **kwargs: Additional message fields

    Returns:
        Dictionary representing a message
    """
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }
    message.update(kwargs)
    return message


def create_mock_webhook_payload(
    phone: str = "+5491234567890",
    message: str = "Hello",
    name: str = "Test User",
) -> Dict[str, Any]:
    """
    Create a mock WhatsApp webhook payload.

    Args:
        phone: Sender phone number
        message: Message text
        name: Sender name

    Returns:
        Dictionary representing WhatsApp webhook payload
    """
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "123456789",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": name},
                                    "wa_id": phone.lstrip("+"),
                                }
                            ],
                            "messages": [
                                {
                                    "from": phone.lstrip("+"),
                                    "id": f"wamid.test{datetime.now().timestamp()}",
                                    "timestamp": str(int(datetime.now().timestamp())),
                                    "text": {"body": message},
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


def create_mock_llm_response(
    content: str = "Mocked LLM response",
    **kwargs,
) -> Dict[str, Any]:
    """
    Create a mock LLM response.

    Args:
        content: Response content
        **kwargs: Additional response fields

    Returns:
        Dictionary representing LLM response
    """
    response = {
        "message": {
            "content": content,
            "role": "assistant",
        },
        "model": "test-model",
        "created_at": datetime.now().isoformat(),
    }
    response.update(kwargs)
    return response


def create_mock_embedding(
    dimensions: int = 1024,
    value: float = 0.1,
) -> List[float]:
    """
    Create a mock embedding vector.

    Args:
        dimensions: Number of dimensions
        value: Default value for each dimension

    Returns:
        List of floats representing embedding
    """
    return [value] * dimensions
