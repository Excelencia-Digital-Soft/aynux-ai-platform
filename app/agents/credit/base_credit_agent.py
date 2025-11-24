"""
Base Credit Agent
"""

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, Dict

from app.agents.credit.schemas import CreditState, UserRole

logger = logging.getLogger(__name__)


class BaseCreditAgent(ABC):
    """Base class for all credit agents"""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")

    async def process(self, state: CreditState) -> Dict[str, Any]:
        """Process state and return updated state"""
        try:
            self.logger.info(f"Processing with {self.name}")

            # Check user permissions
            if not self._check_permissions(state):
                return self._unauthorized_response(state)

            # Process the request
            result = await self._process_internal(state)

            # Update state with result
            updated_state = self._update_state(state, result)

            return updated_state

        except Exception as e:
            self.logger.error(f"Error in {self.name}: {str(e)}")
            return self._error_response(state, str(e))

    @abstractmethod
    async def _process_internal(self, state: CreditState) -> Dict[str, Any]:
        """Internal processing logic to be implemented by subclasses"""
        pass

    def _check_permissions(self, state: CreditState) -> bool:
        """Check if user has permissions for this operation"""
        user_role = UserRole(state.get("user_role", UserRole.CUSTOMER))

        # Define permissions for each agent type
        # This is a simplified version - in production, use a proper permission system
        if self.name in ["credit_balance", "statement", "payment"]:
            # Customers can access their own data
            return True
        elif self.name in ["credit_application", "product_credit"]:
            # Customers can apply, analysts and above can process
            return True
        elif self.name in ["risk_assessment", "compliance"]:
            # Only analysts and above
            return user_role in [UserRole.CREDIT_ANALYST, UserRole.MANAGER, UserRole.ADMIN]
        elif self.name in ["portfolio_analytics", "reporting"]:
            # Only managers and above
            return user_role in [UserRole.MANAGER, UserRole.ADMIN]
        elif self.name in ["collection"]:
            # Collection agents and above
            return user_role in [UserRole.COLLECTION_AGENT, UserRole.MANAGER, UserRole.ADMIN]

        return False

    def _update_state(self, state: CreditState, result: Dict[str, Any]) -> Dict[str, Any]:
        """Update state with processing result"""
        updated_state = dict(state)

        # Add response message
        response_message = {
            "role": "assistant",
            "content": result.get("message", ""),
            "timestamp": datetime.now(UTC).isoformat(),
            "metadata": {"agent": self.name, "data": result.get("data")},
        }

        # Ensure messages is a list and append
        messages = updated_state.get("messages", [])
        if isinstance(messages, list):
            messages.append(response_message)
            updated_state["messages"] = messages
        updated_state["last_update"] = datetime.now(UTC).isoformat()

        # Update any specific state fields
        if "credit_limit" in result:
            updated_state["credit_limit"] = result["credit_limit"]
        if "available_credit" in result:
            updated_state["available_credit"] = result["available_credit"]
        if "risk_score" in result:
            updated_state["risk_score"] = result["risk_score"]

        return updated_state

    def _unauthorized_response(self, state: CreditState) -> Dict[str, Any]:
        """Return unauthorized response"""
        updated_state = dict(state)

        # Ensure messages is a list and append
        messages = updated_state.get("messages", [])
        if isinstance(messages, list):
            messages.append(
                {
                    "role": "assistant",
                    "content": "No tienes permisos para realizar esta operación.",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "metadata": {"agent": self.name, "error": "unauthorized"},
                }
            )
            updated_state["messages"] = messages
        return updated_state

    def _error_response(self, state: CreditState, error: str) -> Dict[str, Any]:
        """Return error response"""
        updated_state = dict(state)

        # Ensure messages is a list and append
        messages = updated_state.get("messages", [])
        if isinstance(messages, list):
            messages.append(
                {
                    "role": "assistant",
                    "content": f"Lo siento, ocurrió un error al procesar tu solicitud: {error}",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "metadata": {"agent": self.name, "error": error},
                }
            )
            updated_state["messages"] = messages
        return updated_state

    def _get_last_user_message(self, state: CreditState) -> str:
        """Get the last user message from state"""
        for message in reversed(state["messages"]):
            if message.get("role") == "user":
                return message.get("content", "")
        return ""
