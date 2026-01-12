# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: External system response type.
# ============================================================================
"""External Response Type.

Contains the ExternalResponse dataclass used by all ports.
This is in a separate file to avoid circular imports.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ExternalResponse:
    """Structured response from external systems.

    Provides a consistent interface for handling responses from
    different medical system backends (SOAP, REST, etc.).
    """

    success: bool
    data: dict[str, Any] | list[Any] | None = None
    error_code: str | None = None
    error_message: str | None = None

    @classmethod
    def ok(cls, data: dict[str, Any] | list[Any] | None = None) -> "ExternalResponse":
        """Factory for successful response."""
        return cls(success=True, data=data)

    @classmethod
    def error(cls, code: str, message: str) -> "ExternalResponse":
        """Factory for error response."""
        return cls(success=False, error_code=code, error_message=message)

    def get_dict(self) -> dict[str, Any]:
        """Get data as dict, handling list responses (returns first item).

        Returns:
            Data as dictionary, or empty dict if data is None/empty list.
        """
        if isinstance(self.data, dict):
            return self.data
        if isinstance(self.data, list) and len(self.data) > 0:
            first = self.data[0]
            if isinstance(first, dict):
                return first
        return {}

    def get_list(self) -> list[Any]:
        """Get data as list.

        Returns:
            Data as list, wrapping dict in list if needed.
        """
        if isinstance(self.data, list):
            return self.data
        if isinstance(self.data, dict):
            return [self.data]
        return []

    def get_value(self, key: str, default: Any = None) -> Any:
        """Safely get a value from data dict.

        Args:
            key: Key to look up.
            default: Default value if key not found.

        Returns:
            Value for key or default.
        """
        data = self.get_dict()
        return data.get(key, default)
