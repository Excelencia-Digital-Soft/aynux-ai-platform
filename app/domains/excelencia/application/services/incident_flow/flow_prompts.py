"""
Flow prompt service for incident creation flow.

Provides typed access to all incident flow prompts via PromptRegistry.
"""

import logging

from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry

logger = logging.getLogger(__name__)


class FlowPromptService:
    """Service for incident flow prompts."""

    def __init__(self, prompt_manager: PromptManager | None = None):
        """Initialize with optional prompt manager."""
        self._pm = prompt_manager or PromptManager()

    async def get_flow_start(self) -> str:
        """Get prompt for starting the incident flow."""
        return await self._pm.get_prompt(PromptRegistry.EXCELENCIA_INCIDENT_FLOW_START)

    async def get_ask_priority(self) -> str:
        """Get prompt for asking priority selection."""
        return await self._pm.get_prompt(PromptRegistry.EXCELENCIA_INCIDENT_ASK_PRIORITY)

    async def get_confirmation(self, description: str, priority: str) -> str:
        """Get prompt for confirming incident details."""
        return await self._pm.get_prompt(
            PromptRegistry.EXCELENCIA_INCIDENT_CONFIRMATION,
            variables={"description": description, "priority": priority},
        )

    async def get_created_success(self, folio: str, priority: str) -> str:
        """Get prompt for successful incident creation."""
        return await self._pm.get_prompt(
            PromptRegistry.EXCELENCIA_INCIDENT_CREATED,
            variables={"folio": folio, "priority": priority},
        )

    async def get_cancelled(self) -> str:
        """Get prompt for cancelled incident flow."""
        return await self._pm.get_prompt(PromptRegistry.EXCELENCIA_INCIDENT_CANCELLED)

    async def get_invalid_selection(self, options_reminder: str) -> str:
        """Get prompt for invalid user selection."""
        return await self._pm.get_prompt(
            PromptRegistry.EXCELENCIA_INCIDENT_INVALID_SELECTION,
            variables={"options_reminder": options_reminder},
        )

    async def get_reset_message(self, target_step: str) -> str:
        """Get prompt for reset confirmation."""
        if target_step == "priority":
            return "Entendido, vamos a corregir la prioridad.\n\n" + await self.get_ask_priority()
        else:
            return "Entendido, vamos a corregir los datos.\n\n" + await self.get_flow_start()

    async def get_error_message(self) -> str:
        """Get error message for ticket creation failure."""
        return await self._pm.get_prompt(PromptRegistry.EXCELENCIA_INCIDENT_ERROR_CREATION)
