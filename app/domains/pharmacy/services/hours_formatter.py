"""
Pharmacy Hours Formatter

Formats pharmacy operating hours for display.
Single responsibility: hours formatting.
"""

from __future__ import annotations

from typing import Any


class PharmacyHoursFormatter:
    """
    Formats pharmacy operating hours for user-friendly display.

    Responsibility: Transform hours data into readable string format.
    """

    NOT_AVAILABLE = "No disponible"
    OPEN_24H_MESSAGE = "Abierto 24 horas, todos los días"

    def format(self, pharmacy_info: dict[str, Any] | None) -> str:
        """
        Format operating hours for display.

        Args:
            pharmacy_info: Pharmacy info dict containing hours and is_24h

        Returns:
            Formatted hours string
        """
        if not pharmacy_info:
            return self.NOT_AVAILABLE

        # Check if pharmacy is 24 hours
        if pharmacy_info.get("is_24h"):
            return self.OPEN_24H_MESSAGE

        hours = pharmacy_info.get("hours")
        if not hours or not isinstance(hours, dict):
            return self.NOT_AVAILABLE

        return self._format_hours_dict(hours)

    def _format_hours_dict(self, hours: dict[str, str]) -> str:
        """
        Format hours dictionary into readable string.

        Args:
            hours: Dict mapping days to time ranges

        Returns:
            Formatted hours string
        """
        lines = []
        for day, time_range in hours.items():
            lines.append(f"  - {day}: {time_range}")

        return "\n".join(lines) if lines else self.NOT_AVAILABLE

    def format_compact(self, pharmacy_info: dict[str, Any] | None) -> str:
        """
        Format hours in a more compact single-line format.

        Args:
            pharmacy_info: Pharmacy info dict

        Returns:
            Compact hours string
        """
        if not pharmacy_info:
            return self.NOT_AVAILABLE

        if pharmacy_info.get("is_24h"):
            return "24 horas"

        hours = pharmacy_info.get("hours")
        if not hours or not isinstance(hours, dict):
            return self.NOT_AVAILABLE

        # Try to create a compact format
        unique_times = set(hours.values())
        if len(unique_times) == 1:
            # All days have the same hours
            time_range = next(iter(unique_times))
            return f"Todos los días: {time_range}"

        # Different hours on different days - return detailed format
        return self.format(pharmacy_info)

    def is_open_24h(self, pharmacy_info: dict[str, Any] | None) -> bool:
        """
        Check if pharmacy is open 24 hours.

        Args:
            pharmacy_info: Pharmacy info dict

        Returns:
            True if pharmacy is open 24 hours
        """
        if not pharmacy_info:
            return False
        return bool(pharmacy_info.get("is_24h"))
