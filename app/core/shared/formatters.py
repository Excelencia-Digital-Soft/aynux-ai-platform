"""
Shared Formatters

Common formatting utilities for the application.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any


class DateFormatter:
    """Date and time formatting utilities."""

    # Common formats
    DATE_ISO = "%Y-%m-%d"
    DATE_AR = "%d/%m/%Y"
    DATE_FULL = "%A, %d de %B de %Y"
    TIME_24H = "%H:%M"
    TIME_12H = "%I:%M %p"
    DATETIME_ISO = "%Y-%m-%dT%H:%M:%S"
    DATETIME_AR = "%d/%m/%Y %H:%M"

    # Spanish day names
    DAYS_ES = {
        "Monday": "Lunes",
        "Tuesday": "Martes",
        "Wednesday": "Miercoles",
        "Thursday": "Jueves",
        "Friday": "Viernes",
        "Saturday": "Sabado",
        "Sunday": "Domingo",
    }

    # Spanish month names
    MONTHS_ES = {
        "January": "Enero",
        "February": "Febrero",
        "March": "Marzo",
        "April": "Abril",
        "May": "Mayo",
        "June": "Junio",
        "July": "Julio",
        "August": "Agosto",
        "September": "Septiembre",
        "October": "Octubre",
        "November": "Noviembre",
        "December": "Diciembre",
    }

    @classmethod
    def format_date(cls, d: date | datetime, fmt: str = DATE_AR) -> str:
        """Format date with specified format."""
        if d is None:
            return ""
        return d.strftime(fmt)

    @classmethod
    def format_date_spanish(cls, d: date | datetime) -> str:
        """Format date in Spanish (e.g., 'Lunes, 15 de Enero de 2024')."""
        if d is None:
            return ""

        formatted = d.strftime(cls.DATE_FULL)

        # Replace English day/month names with Spanish
        for eng, spa in cls.DAYS_ES.items():
            formatted = formatted.replace(eng, spa)
        for eng, spa in cls.MONTHS_ES.items():
            formatted = formatted.replace(eng, spa)

        return formatted

    @classmethod
    def format_time(cls, t: time | datetime, fmt: str = TIME_24H) -> str:
        """Format time."""
        if t is None:
            return ""
        return t.strftime(fmt)

    @classmethod
    def format_datetime(cls, dt: datetime, fmt: str = DATETIME_AR) -> str:
        """Format datetime."""
        if dt is None:
            return ""
        return dt.strftime(fmt)

    @classmethod
    def format_relative(cls, dt: datetime) -> str:
        """Format datetime as relative time (e.g., 'hace 2 horas')."""
        if dt is None:
            return ""

        now = datetime.now()
        diff = now - dt

        seconds = diff.total_seconds()

        if seconds < 60:
            return "hace un momento"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"hace {minutes} minuto{'s' if minutes > 1 else ''}"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"hace {hours} hora{'s' if hours > 1 else ''}"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"hace {days} dia{'s' if days > 1 else ''}"
        else:
            return cls.format_date(dt)


class NumberFormatter:
    """Number formatting utilities."""

    @classmethod
    def format_currency(
        cls,
        amount: float | Decimal,
        currency: str = "ARS",
        symbol: str = "$",
        decimal_places: int = 2,
    ) -> str:
        """Format amount as currency."""
        if amount is None:
            return ""

        # Format with thousand separators and decimal places
        formatted = f"{float(amount):,.{decimal_places}f}"

        # Replace separators for Argentine format (. for thousands, , for decimals)
        formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")

        return f"{symbol} {formatted}"

    @classmethod
    def format_decimal(
        cls,
        value: float | Decimal,
        decimal_places: int = 2,
    ) -> str:
        """Format decimal number."""
        if value is None:
            return ""
        return f"{float(value):,.{decimal_places}f}"

    @classmethod
    def format_percentage(
        cls,
        value: float,
        decimal_places: int = 1,
    ) -> str:
        """Format as percentage."""
        if value is None:
            return ""
        return f"{value * 100:.{decimal_places}f}%"

    @classmethod
    def format_integer(cls, value: int) -> str:
        """Format integer with thousand separators."""
        if value is None:
            return ""
        formatted = f"{value:,}"
        return formatted.replace(",", ".")


class TextFormatter:
    """Text formatting utilities."""

    @classmethod
    def truncate(cls, text: str, max_length: int, suffix: str = "...") -> str:
        """Truncate text to max length."""
        if not text or len(text) <= max_length:
            return text
        return text[: max_length - len(suffix)] + suffix

    @classmethod
    def title_case(cls, text: str) -> str:
        """Convert to title case."""
        if not text:
            return ""
        return text.title()

    @classmethod
    def capitalize_first(cls, text: str) -> str:
        """Capitalize first letter only."""
        if not text:
            return ""
        return text[0].upper() + text[1:]

    @classmethod
    def slug(cls, text: str) -> str:
        """Convert to URL-friendly slug."""
        import re

        if not text:
            return ""

        # Convert to lowercase
        text = text.lower()

        # Replace accented characters
        replacements = {
            "a": "aáàäâ",
            "e": "eéèëê",
            "i": "iíìïî",
            "o": "oóòöô",
            "u": "uúùüû",
            "n": "nñ",
        }

        for char, accented in replacements.items():
            for acc in accented:
                text = text.replace(acc, char)

        # Replace non-alphanumeric with hyphen
        text = re.sub(r"[^a-z0-9]+", "-", text)

        # Remove leading/trailing hyphens
        text = text.strip("-")

        return text

    @classmethod
    def mask(cls, text: str, visible_chars: int = 4, mask_char: str = "*") -> str:
        """Mask text, showing only last N characters."""
        if not text or len(text) <= visible_chars:
            return text
        return mask_char * (len(text) - visible_chars) + text[-visible_chars:]


class PhoneFormatter:
    """Phone number formatting utilities."""

    @classmethod
    def format_ar(cls, phone: str) -> str:
        """Format Argentine phone number."""
        import re

        if not phone:
            return ""

        # Remove non-digits
        digits = re.sub(r"\D", "", phone)

        # Handle different lengths
        if len(digits) == 10:
            # Mobile without country code: 11 1234-5678
            return f"{digits[:2]} {digits[2:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits.startswith("9"):
            # Mobile with 9 prefix: 9 11 1234-5678
            return f"{digits[0]} {digits[1:3]} {digits[3:7]}-{digits[7:]}"
        elif len(digits) >= 12:
            # With country code: +54 9 11 1234-5678
            return f"+{digits[:2]} {digits[2]} {digits[3:5]} {digits[5:9]}-{digits[9:]}"
        else:
            return phone


class ListFormatter:
    """List formatting utilities."""

    @classmethod
    def bullet_list(cls, items: list[str], bullet: str = "-") -> str:
        """Format as bullet list."""
        if not items:
            return ""
        return "\n".join(f"{bullet} {item}" for item in items)

    @classmethod
    def numbered_list(cls, items: list[str], start: int = 1) -> str:
        """Format as numbered list."""
        if not items:
            return ""
        return "\n".join(f"{i}. {item}" for i, item in enumerate(items, start=start))

    @classmethod
    def comma_separated(cls, items: list[str], last_separator: str = " y ") -> str:
        """Format as comma-separated with 'and' before last item."""
        if not items:
            return ""
        if len(items) == 1:
            return items[0]
        return ", ".join(items[:-1]) + last_separator + items[-1]


def format_dict_for_display(data: dict[str, Any], indent: int = 0) -> str:
    """Format dictionary for human-readable display."""
    lines: list[str] = []
    prefix = "  " * indent

    for key, value in data.items():
        # Format key
        key_display = key.replace("_", " ").title()

        if isinstance(value, dict):
            lines.append(f"{prefix}{key_display}:")
            lines.append(format_dict_for_display(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key_display}:")
            for item in value:
                if isinstance(item, dict):
                    lines.append(format_dict_for_display(item, indent + 1))
                else:
                    lines.append(f"{prefix}  - {item}")
        elif value is not None:
            lines.append(f"{prefix}{key_display}: {value}")

    return "\n".join(lines)
