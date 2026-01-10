# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Base class for LangGraph nodes.
# ============================================================================
"""Base Node Class.

Abstract base class for all LangGraph nodes in the medical appointments flow.
Composes mixins for response generation, state extraction, and validation.

Components:
- ResponseMixin: Response generation helpers
- StateMixin: State extraction helpers
- ValidationMixin: Input validation helpers
"""

import logging
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from ..config import NodeConfig

if TYPE_CHECKING:
    from ...application.ports import IMedicalSystemClient, INotificationService
    from ..state import MedicalAppointmentsState

from .mixins import ResponseMixin, StateMixin, ValidationMixin

logger = logging.getLogger(__name__)


class BaseNode(ABC, ResponseMixin, StateMixin, ValidationMixin):
    """Base class for LangGraph nodes.

    Combines mixins for common functionality:
    - ResponseMixin: _text_response, _error_response, _list_response
    - StateMixin: _get_message, _get_selection, _get_*_id
    - ValidationMixin: _is_confirmation, _is_cancellation, _is_valid_document

    Subclasses must implement process() method.
    """

    def __init__(
        self,
        medical_client: "IMedicalSystemClient",
        notification_service: "INotificationService | None" = None,
        config: dict[str, Any] | NodeConfig | None = None,
    ) -> None:
        """Initialize node.

        Args:
            medical_client: Medical system client (DIP - abstractions).
            notification_service: Optional notification service (DIP).
            config: Configuration - accepts NodeConfig or dict (backward compatible).
        """
        self._medical = medical_client
        self._notification = notification_service

        # Support both NodeConfig and dict for backward compatibility
        if isinstance(config, NodeConfig):
            self._node_config = config
            self._config = config.to_dict()
        elif isinstance(config, dict):
            # Try to parse as NodeConfig, fallback to raw dict
            try:
                self._node_config = NodeConfig.from_dict(config)
                self._config = config
            except ValueError:
                # Missing required fields - use raw dict
                self._node_config = None
                self._config = config
        else:
            self._node_config = None
            self._config = {}

    @property
    def config(self) -> NodeConfig | None:
        """Get typed configuration (if available).

        Returns:
            NodeConfig if configuration is complete, None otherwise.
        """
        return self._node_config

    @property
    def institution(self) -> str:
        """Get institution key from config.

        Returns:
            Institution key or empty string.
        """
        if self._node_config:
            return self._node_config.institution
        return self._config.get("institution", "")

    @property
    def institution_name(self) -> str:
        """Get institution name from config.

        Returns:
            Institution name or empty string.
        """
        if self._node_config:
            return self._node_config.institution_name
        return self._config.get("institution_name", "")

    @property
    def node_name(self) -> str:
        """Get the node name (class name without 'Node' suffix)."""
        name = self.__class__.__name__
        if name.endswith("Node"):
            name = name[:-4]
        return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()

    @abstractmethod
    async def process(self, state: "MedicalAppointmentsState") -> dict[str, Any]:
        """Process the node.

        Args:
            state: Current conversation state.

        Returns:
            Dictionary with state updates.
        """
        ...

    async def __call__(self, state: "MedicalAppointmentsState") -> dict[str, Any]:
        """Make node callable for LangGraph.

        Args:
            state: Current conversation state.

        Returns:
            Dictionary with state updates including current_node.
        """
        logger.debug(f"Processing node: {self.node_name}")
        try:
            result = await self.process(state)
            result["current_node"] = self.node_name
            return result
        except Exception as e:
            logger.error(f"Error in node {self.node_name}: {e}", exc_info=True)
            return self._error_response(str(e))

    # =========================================================================
    # WhatsApp Interactive Message Helpers
    # =========================================================================

    async def _send_interactive_list(
        self,
        phone: str,
        title: str,
        items: list[dict[str, Any]],
        button_text: str = "Ver opciones",
    ) -> dict[str, Any] | None:
        """Send WhatsApp interactive list via INotificationService.

        Args:
            phone: Recipient phone number.
            title: List title/body text.
            items: List items with "id" and "title" keys.
            button_text: Button text.

        Returns:
            API response or None if notification service unavailable.
        """
        if not self._notification:
            return None

        formatted_items = [
            {
                "id": str(item.get("id") or item.get("codigo") or i),
                "title": str(item.get("nombre") or item.get("title", ""))[:24],
                "description": str(item.get("descripcion") or "")[:72],
            }
            for i, item in enumerate(items[:10])
        ]

        try:
            return await self._notification.send_interactive_list(
                phone=phone,
                title=title,
                items=formatted_items,
                button_text=button_text,
            )
        except Exception as e:
            logger.warning(f"Failed to send interactive list: {e}")
            return None

    async def _send_interactive_buttons(
        self,
        phone: str,
        body: str,
        buttons: list[dict[str, str]],
    ) -> dict[str, Any] | None:
        """Send WhatsApp interactive buttons via INotificationService.

        Args:
            phone: Recipient phone number.
            body: Message body text.
            buttons: List of buttons with "id" and "title" keys.

        Returns:
            API response or None if notification service unavailable.
        """
        if not self._notification:
            return None

        try:
            return await self._notification.send_interactive_buttons(
                phone=phone,
                body=body,
                buttons=buttons[:3],
            )
        except Exception as e:
            logger.warning(f"Failed to send interactive buttons: {e}")
            return None
