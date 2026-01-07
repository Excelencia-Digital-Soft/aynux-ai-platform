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

    # Day name mappings for friendly display
    DAY_NAMES = {
        # Full Spanish names
        "lunes": "Lunes",
        "martes": "Martes",
        "miercoles": "Miércoles",
        "miércoles": "Miércoles",
        "jueves": "Jueves",
        "viernes": "Viernes",
        "sabado": "Sábado",
        "sábado": "Sábado",
        "domingo": "Domingo",
        # Abbreviations
        "lun": "Lunes",
        "mar": "Martes",
        "mie": "Miércoles",
        "jue": "Jueves",
        "vie": "Viernes",
        "sab": "Sábado",
        "dom": "Domingo",
        # English
        "monday": "Lunes",
        "tuesday": "Martes",
        "wednesday": "Miércoles",
        "thursday": "Jueves",
        "friday": "Viernes",
        "saturday": "Sábado",
        "sunday": "Domingo",
        "mon": "Lunes",
        "tue": "Martes",
        "wed": "Miércoles",
        "thu": "Jueves",
        "fri": "Viernes",
        "sat": "Sábado",
        "sun": "Domingo",
    }

    # Ordered days for grouping
    DAY_ORDER = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

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

    def _normalize_day(self, day: str) -> str:
        """Normalize day name to Spanish full name."""
        day_lower = day.lower().strip()
        return self.DAY_NAMES.get(day_lower, day.capitalize())

    def _format_hours_dict(self, hours: dict[str, str]) -> str:
        """
        Format hours dictionary into readable string.

        Handles special formats like "lun-vie" for day ranges and
        groups consecutive days with same hours.

        Args:
            hours: Dict mapping days to time ranges

        Returns:
            Formatted hours string
        """
        # Expand day ranges and normalize
        expanded_hours: dict[str, str] = {}

        for day_key, time_range in hours.items():
            day_lower = day_key.lower().strip()

            # Handle range format like "lun-vie" or "lunes-viernes"
            if "-" in day_lower and not self._is_time_format(day_lower):
                start_day, end_day = day_lower.split("-", 1)
                start_normalized = self._normalize_day(start_day)
                end_normalized = self._normalize_day(end_day)

                # Get range of days
                if start_normalized in self.DAY_ORDER and end_normalized in self.DAY_ORDER:
                    start_idx = self.DAY_ORDER.index(start_normalized)
                    end_idx = self.DAY_ORDER.index(end_normalized)
                    for i in range(start_idx, end_idx + 1):
                        expanded_hours[self.DAY_ORDER[i]] = time_range
                else:
                    # Can't expand, use as label
                    label = f"{start_normalized} a {end_normalized}"
                    expanded_hours[label] = time_range
            else:
                # Single day or unknown format
                normalized = self._normalize_day(day_key)
                # Skip generic keys like "dia_3"
                if not day_key.startswith("dia_"):
                    expanded_hours[normalized] = time_range

        if not expanded_hours:
            return self.NOT_AVAILABLE

        # Group consecutive days with same hours
        return self._group_days_with_same_hours(expanded_hours)

    def _is_time_format(self, s: str) -> bool:
        """Check if string looks like a time (e.g., '08:00-20:00')."""
        return ":" in s

    def _group_days_with_same_hours(self, hours: dict[str, str]) -> str:
        """
        Group consecutive days that have the same hours.

        Args:
            hours: Dict of day -> hours

        Returns:
            Formatted string with grouped days
        """
        # Sort by day order
        ordered_days = []
        for day in self.DAY_ORDER:
            if day in hours:
                ordered_days.append((day, hours[day]))

        # Add any days not in standard order
        for day, time in hours.items():
            if day not in self.DAY_ORDER:
                ordered_days.append((day, time))

        if not ordered_days:
            return self.NOT_AVAILABLE

        # Group consecutive days with same hours
        groups: list[tuple[list[str], str]] = []
        current_days: list[str] = [ordered_days[0][0]]
        current_hours = ordered_days[0][1]

        for day, time in ordered_days[1:]:
            if time == current_hours:
                current_days.append(day)
            else:
                groups.append((current_days, current_hours))
                current_days = [day]
                current_hours = time

        groups.append((current_days, current_hours))

        # Format groups
        lines = []
        for days, time in groups:
            time_formatted = self._format_time(time)

            if len(days) == 1:
                lines.append(f"• {days[0]}: {time_formatted}")
            elif len(days) == 2:
                lines.append(f"• {days[0]} y {days[1]}: {time_formatted}")
            else:
                lines.append(f"• {days[0]} a {days[-1]}: {time_formatted}")

        return "\n".join(lines)

    def _format_time(self, time_range: str) -> str:
        """Format time range for display."""
        time_lower = time_range.lower().strip()

        if time_lower in ("cerrado", "closed", "-"):
            return "Cerrado"

        # Clean up format: "08:00-20:00" -> "08:00 a 20:00"
        if "-" in time_range and ":" in time_range:
            parts = time_range.split("-")
            if len(parts) == 2:
                return f"{parts[0].strip()} a {parts[1].strip()}"

        return time_range

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
