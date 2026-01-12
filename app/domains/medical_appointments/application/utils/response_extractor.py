# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Utility for extracting data from ExternalResponse consistently
# ============================================================================
"""Response extraction utility.

Provides consistent patterns for extracting data from ExternalResponse objects,
eliminating DRY violations across use cases and nodes.
"""

from typing import Any


class ResponseExtractor:
    """Utility for extracting data from ExternalResponse consistently.

    Centralizes the common patterns for extracting dict/list data from
    API responses, reducing code duplication across the domain.

    Example:
        >>> response = await client.buscar_paciente_dni(dni)
        >>> data = ResponseExtractor.as_dict(response.data)
        >>> patient_id = ResponseExtractor.get_field(data, "idPaciente", "IdPaciente")
    """

    @staticmethod
    def as_dict(data: Any) -> dict[str, Any]:
        """Extract a dictionary from response data.

        Handles various response formats consistently:
        - If data is dict: returns it directly
        - If data is list: returns first item if dict, else empty dict
        - Otherwise: returns empty dict

        Args:
            data: The response.data value to extract from.

        Returns:
            A dictionary (never None).
        """
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data:
            first_item = data[0]
            return first_item if isinstance(first_item, dict) else {}
        return {}

    @staticmethod
    def as_list(data: Any) -> list[dict[str, Any]]:
        """Extract a list of dictionaries from response data.

        Handles various response formats consistently:
        - If data is list: returns it directly
        - If data is dict: wraps it in a list
        - Otherwise: returns empty list

        Args:
            data: The response.data value to extract from.

        Returns:
            A list of dictionaries (never None).
        """
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            return [data]
        return []

    @staticmethod
    def get_field(data: dict[str, Any], *keys: str, default: str = "") -> str:
        """Get a field value trying multiple keys (fallback pattern).

        Useful when external API returns inconsistent field names
        (e.g., "idPaciente" vs "IdPaciente" vs "id").

        Args:
            data: Dictionary to extract from.
            *keys: Field names to try in order.
            default: Value to return if no key is found.

        Returns:
            The first found value as string, or default.

        Example:
            >>> get_field(data, "idPaciente", "IdPaciente", "id")
            "12345"
        """
        for key in keys:
            value = data.get(key)
            if value is not None and value != "":
                return str(value)
        return default

    @staticmethod
    def get_nested(
        data: dict[str, Any],
        *path: str,
        default: Any = None,
    ) -> Any:
        """Get a nested value from a dictionary.

        Args:
            data: Dictionary to extract from.
            *path: Keys forming the path to the value.
            default: Value to return if path is not found.

        Returns:
            The nested value or default.

        Example:
            >>> get_nested(data, "patient", "address", "city")
            "San Juan"
        """
        current = data
        for key in path:
            if not isinstance(current, dict):
                return default
            current = current.get(key)
            if current is None:
                return default
        return current

    @staticmethod
    def extract_items(
        data: Any,
        *possible_keys: str,
    ) -> list[dict[str, Any]]:
        """Extract a list of items from nested response data.

        Useful when API wraps lists in different container keys.

        Args:
            data: Response data (dict or list).
            *possible_keys: Keys that might contain the list.

        Returns:
            List of dictionaries.

        Example:
            >>> extract_items(data, "especialidades", "items", "datos")
            [{"id": 1, "nombre": "Gastro"}, ...]
        """
        # If already a list, return it
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]

        # If dict, try to find the list in known keys
        if isinstance(data, dict):
            for key in possible_keys:
                if key in data:
                    value = data[key]
                    if isinstance(value, list):
                        return [item for item in value if isinstance(item, dict)]
                    if isinstance(value, dict):
                        return [value]
            # No key found, return the dict as single-item list
            return [data]

        return []
