"""
Test data builders using the Builder pattern.

Provides fluent interfaces for constructing test objects with sensible defaults.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional


class ProductBuilder:
    """Builder for creating product test data."""

    def __init__(self):
        self._data = {
            "id": 1,
            "name": "Test Product",
            "description": "A test product",
            "price": 99.99,
            "stock": 10,
            "category_id": 1,
            "sku": "TEST-001",
            "active": True,
            "created_at": datetime.now(),
        }

    def with_id(self, product_id: int) -> "ProductBuilder":
        """Set product ID."""
        self._data["id"] = product_id
        return self

    def with_name(self, name: str) -> "ProductBuilder":
        """Set product name."""
        self._data["name"] = name
        return self

    def with_description(self, description: str) -> "ProductBuilder":
        """Set product description."""
        self._data["description"] = description
        return self

    def with_price(self, price: float) -> "ProductBuilder":
        """Set product price."""
        self._data["price"] = price
        return self

    def with_stock(self, stock: int) -> "ProductBuilder":
        """Set product stock."""
        self._data["stock"] = stock
        return self

    def with_category(self, category_id: int) -> "ProductBuilder":
        """Set category ID."""
        self._data["category_id"] = category_id
        return self

    def with_sku(self, sku: str) -> "ProductBuilder":
        """Set SKU."""
        self._data["sku"] = sku
        return self

    def inactive(self) -> "ProductBuilder":
        """Mark product as inactive."""
        self._data["active"] = False
        return self

    def out_of_stock(self) -> "ProductBuilder":
        """Set stock to 0."""
        self._data["stock"] = 0
        return self

    def build(self) -> Dict[str, Any]:
        """Build and return the product data."""
        return self._data.copy()


class CustomerBuilder:
    """Builder for creating customer test data."""

    def __init__(self):
        self._data = {
            "id": 1,
            "phone": "+5491234567890",
            "name": "Test Customer",
            "email": "test@example.com",
            "created_at": datetime.now(),
            "active": True,
        }

    def with_id(self, customer_id: int) -> "CustomerBuilder":
        """Set customer ID."""
        self._data["id"] = customer_id
        return self

    def with_phone(self, phone: str) -> "CustomerBuilder":
        """Set phone number."""
        self._data["phone"] = phone
        return self

    def with_name(self, name: str) -> "CustomerBuilder":
        """Set customer name."""
        self._data["name"] = name
        return self

    def with_email(self, email: str) -> "CustomerBuilder":
        """Set email."""
        self._data["email"] = email
        return self

    def inactive(self) -> "CustomerBuilder":
        """Mark customer as inactive."""
        self._data["active"] = False
        return self

    def build(self) -> Dict[str, Any]:
        """Build and return the customer data."""
        return self._data.copy()


class ConversationBuilder:
    """Builder for creating conversation test data."""

    def __init__(self):
        self._data = {
            "id": "conv-123",
            "phone": "+5491234567890",
            "customer_id": 1,
            "messages": [],
            "status": "active",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

    def with_id(self, conv_id: str) -> "ConversationBuilder":
        """Set conversation ID."""
        self._data["id"] = conv_id
        return self

    def with_phone(self, phone: str) -> "ConversationBuilder":
        """Set phone number."""
        self._data["phone"] = phone
        return self

    def with_customer(self, customer_id: int) -> "ConversationBuilder":
        """Set customer ID."""
        self._data["customer_id"] = customer_id
        return self

    def with_messages(self, messages: List[Dict]) -> "ConversationBuilder":
        """Set messages."""
        self._data["messages"] = messages
        return self

    def add_message(self, message: Dict) -> "ConversationBuilder":
        """Add a single message."""
        self._data["messages"].append(message)
        return self

    def with_status(self, status: str) -> "ConversationBuilder":
        """Set conversation status."""
        self._data["status"] = status
        return self

    def closed(self) -> "ConversationBuilder":
        """Mark conversation as closed."""
        self._data["status"] = "closed"
        return self

    def build(self) -> Dict[str, Any]:
        """Build and return the conversation data."""
        return self._data.copy()


class OrderBuilder:
    """Builder for creating order test data."""

    def __init__(self):
        self._data = {
            "id": 1,
            "customer_id": 1,
            "total": 99.99,
            "status": "pending",
            "items": [],
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

    def with_id(self, order_id: int) -> "OrderBuilder":
        """Set order ID."""
        self._data["id"] = order_id
        return self

    def with_customer(self, customer_id: int) -> "OrderBuilder":
        """Set customer ID."""
        self._data["customer_id"] = customer_id
        return self

    def with_total(self, total: float) -> "OrderBuilder":
        """Set order total."""
        self._data["total"] = total
        return self

    def with_status(self, status: str) -> "OrderBuilder":
        """Set order status."""
        self._data["status"] = status
        return self

    def add_item(
        self,
        product_id: int,
        quantity: int = 1,
        price: float = 99.99,
    ) -> "OrderBuilder":
        """Add an item to the order."""
        self._data["items"].append({
            "product_id": product_id,
            "quantity": quantity,
            "price": price,
        })
        return self

    def completed(self) -> "OrderBuilder":
        """Mark order as completed."""
        self._data["status"] = "completed"
        return self

    def cancelled(self) -> "OrderBuilder":
        """Mark order as cancelled."""
        self._data["status"] = "cancelled"
        return self

    def build(self) -> Dict[str, Any]:
        """Build and return the order data."""
        return self._data.copy()


class AgentStateBuilder:
    """Builder for creating agent state test data."""

    def __init__(self):
        self._data = {
            "messages": [],
            "phone": "+5491234567890",
            "customer_name": "Test User",
            "intent": None,
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

    def with_phone(self, phone: str) -> "AgentStateBuilder":
        """Set phone number."""
        self._data["phone"] = phone
        return self

    def with_customer_name(self, name: str) -> "AgentStateBuilder":
        """Set customer name."""
        self._data["customer_name"] = name
        return self

    def with_intent(self, intent: str) -> "AgentStateBuilder":
        """Set detected intent."""
        self._data["intent"] = intent
        return self

    def with_message(self, role: str, content: str) -> "AgentStateBuilder":
        """Add a message."""
        self._data["messages"].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        return self

    def with_routing(self, routing: Dict) -> "AgentStateBuilder":
        """Set routing information."""
        self._data["routing"] = routing
        return self

    def with_data(self, data: Dict) -> "AgentStateBuilder":
        """Set data dictionary."""
        self._data["data"] = data
        return self

    def should_end(self) -> "AgentStateBuilder":
        """Mark that the conversation should end."""
        self._data["flow_control"]["should_end"] = True
        return self

    def with_next_node(self, node: str) -> "AgentStateBuilder":
        """Set the next node to route to."""
        self._data["flow_control"]["next_node"] = node
        return self

    def build(self) -> Dict[str, Any]:
        """Build and return the agent state."""
        return self._data.copy()
