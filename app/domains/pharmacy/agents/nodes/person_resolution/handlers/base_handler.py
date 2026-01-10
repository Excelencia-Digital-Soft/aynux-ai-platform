"""Base handler for PersonResolution flow handlers."""

from __future__ import annotations

import logging
from typing import Any

from app.domains.pharmacy.agents.nodes.handlers.base_handler import BasePharmacyHandler


class PersonResolutionBaseHandler(BasePharmacyHandler):
    """
    Base handler for person resolution flow steps.

    Extends BasePharmacyHandler with:
    - Common state update formatting
    - Pharmacy config preservation
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def _preserve_pharmacy_config(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Extract pharmacy config fields to preserve across state updates.

        Args:
            state_dict: Current state dictionary

        Returns:
            Dictionary with pharmacy config fields
        """
        return {
            "pharmacy_id": state_dict.get("pharmacy_id"),
            "pharmacy_name": state_dict.get("pharmacy_name"),
            "pharmacy_phone": state_dict.get("pharmacy_phone"),
        }


__all__ = ["PersonResolutionBaseHandler"]
