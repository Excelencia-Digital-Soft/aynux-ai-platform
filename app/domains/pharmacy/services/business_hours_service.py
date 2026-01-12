"""
Pharmacy Business Hours Service

Verifies if the bot is operating within configured service hours.
Implements CASO 0: Horario de Atención Bot from docs/pharmacy_flujo_mejorado_v2.md.

Business hours are stored in PharmacyMerchantConfig:
- bot_service_hours: JSONB with schedule per day
- bot_service_enabled: bool to enable/disable the check
- emergency_phone: str for urgent contact outside hours
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Argentina timezone
ARGENTINA_TZ = ZoneInfo("America/Argentina/Buenos_Aires")

# Default bot service hours (if not configured)
DEFAULT_SERVICE_HOURS = {
    "lunes": "08:00-20:00",
    "martes": "08:00-20:00",
    "miercoles": "08:00-20:00",
    "jueves": "08:00-20:00",
    "viernes": "08:00-20:00",
    "sabado": "09:00-13:00",
    "domingo": None,  # Closed
}

# Day name mapping (Python weekday to Spanish)
DAY_NAMES = {
    0: "lunes",
    1: "martes",
    2: "miercoles",
    3: "jueves",
    4: "viernes",
    5: "sabado",
    6: "domingo",
}


@dataclass
class BusinessHoursResult:
    """Result of business hours check."""

    is_open: bool
    current_time: str  # HH:MM format
    current_day: str  # Day name in Spanish
    opens_at: str | None = None  # HH:MM when service opens today
    closes_at: str | None = None  # HH:MM when service closes today
    next_open_day: str | None = None  # If closed today, when does it open
    next_open_time: str | None = None  # Time it opens next
    emergency_phone: str | None = None  # Emergency contact

    @property
    def message(self) -> str:
        """Human-readable message about service status."""
        if self.is_open:
            return f"Estamos disponibles hasta las {self.closes_at}."

        if self.next_open_day and self.next_open_time:
            if self.next_open_day == self.current_day:
                return (
                    f"Nuestro asistente virtual está disponible de {self.opens_at} a {self.closes_at}. "
                    f"Actualmente son las {self.current_time}."
                )
            return (
                f"Nuestro asistente virtual no está disponible ahora. "
                f"Abrimos {self.next_open_day} a las {self.next_open_time}."
            )

        return "El servicio de asistente virtual no está disponible en este momento."

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for state merging."""
        return {
            "is_within_service_hours": self.is_open,
            "service_hours_message": self.message if not self.is_open else None,
            "emergency_phone": self.emergency_phone,
        }


class BusinessHoursService:
    """
    Service for checking pharmacy bot service hours.

    Uses Argentina timezone for all calculations.
    Configuration loaded from PharmacyMerchantConfig database table.
    """

    def __init__(self) -> None:
        """Initialize service."""
        self._config_cache: dict[str, dict[str, Any]] = {}

    def _parse_time_range(self, time_range: str | None) -> tuple[time | None, time | None]:
        """
        Parse time range string like "08:00-20:00".

        Args:
            time_range: String in format "HH:MM-HH:MM" or None if closed

        Returns:
            Tuple of (open_time, close_time) or (None, None) if closed
        """
        if not time_range:
            return (None, None)

        try:
            parts = time_range.split("-")
            if len(parts) != 2:
                return (None, None)

            open_parts = parts[0].strip().split(":")
            close_parts = parts[1].strip().split(":")

            open_time = time(int(open_parts[0]), int(open_parts[1]))
            close_time = time(int(close_parts[0]), int(close_parts[1]))

            return (open_time, close_time)
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse time range '{time_range}': {e}")
            return (None, None)

    def _get_current_argentina_time(self) -> datetime:
        """Get current time in Argentina timezone."""
        return datetime.now(ARGENTINA_TZ)

    def _is_time_in_range(
        self,
        current: time,
        open_time: time,
        close_time: time,
    ) -> bool:
        """Check if current time is within range."""
        # Handle overnight ranges (e.g., 22:00-06:00)
        if close_time < open_time:
            return current >= open_time or current <= close_time
        return open_time <= current <= close_time

    def _find_next_open(
        self,
        hours_config: dict[str, str | None],
        current_day_index: int,
        current_time: time,
    ) -> tuple[str | None, str | None]:
        """
        Find the next day and time the service opens.

        Args:
            hours_config: Service hours configuration
            current_day_index: Current day (0=Monday)
            current_time: Current time

        Returns:
            Tuple of (day_name, open_time) or (None, None)
        """
        # First, check if it opens later today
        today_name = DAY_NAMES[current_day_index]
        today_range = hours_config.get(today_name)

        if today_range:
            open_time, _ = self._parse_time_range(today_range)
            if open_time and current_time < open_time:
                return (today_name, open_time.strftime("%H:%M"))

        # Check upcoming days
        for i in range(1, 8):  # Check next 7 days
            next_day_index = (current_day_index + i) % 7
            next_day_name = DAY_NAMES[next_day_index]
            next_day_range = hours_config.get(next_day_name)

            if next_day_range:
                open_time, _ = self._parse_time_range(next_day_range)
                if open_time:
                    return (next_day_name, open_time.strftime("%H:%M"))

        return (None, None)

    async def check_service_hours(
        self,
        pharmacy_id: str | None = None,
        bot_service_hours: dict[str, str | None] | None = None,
        bot_service_enabled: bool = True,
        emergency_phone: str | None = None,
    ) -> BusinessHoursResult:
        """
        Check if the bot is operating within service hours.

        Args:
            pharmacy_id: Optional pharmacy ID to load config from DB
            bot_service_hours: Pre-loaded hours config (bypasses DB lookup)
            bot_service_enabled: Whether to enforce hours check
            emergency_phone: Emergency contact number

        Returns:
            BusinessHoursResult with current status
        """
        now = self._get_current_argentina_time()
        current_day_index = now.weekday()
        current_day_name = DAY_NAMES[current_day_index]
        current_time = now.time()

        # If service hours check is disabled, always open
        if not bot_service_enabled:
            return BusinessHoursResult(
                is_open=True,
                current_time=current_time.strftime("%H:%M"),
                current_day=current_day_name,
                emergency_phone=emergency_phone,
            )

        # Get hours configuration
        hours_config = bot_service_hours
        if hours_config is None:
            if pharmacy_id:
                hours_config = await self._load_hours_from_db(pharmacy_id)
            if hours_config is None:
                hours_config = DEFAULT_SERVICE_HOURS

        # Get today's hours
        today_range = hours_config.get(current_day_name)
        open_time, close_time = self._parse_time_range(today_range)

        # Check if currently open
        is_open = False
        opens_at = None
        closes_at = None

        if open_time and close_time:
            is_open = self._is_time_in_range(current_time, open_time, close_time)
            opens_at = open_time.strftime("%H:%M")
            closes_at = close_time.strftime("%H:%M")

        # Find next open time if currently closed
        next_open_day = None
        next_open_time = None

        if not is_open:
            next_open_day, next_open_time = self._find_next_open(
                hours_config,
                current_day_index,
                current_time,
            )

        return BusinessHoursResult(
            is_open=is_open,
            current_time=current_time.strftime("%H:%M"),
            current_day=current_day_name,
            opens_at=opens_at,
            closes_at=closes_at,
            next_open_day=next_open_day,
            next_open_time=next_open_time,
            emergency_phone=emergency_phone,
        )

    async def _load_hours_from_db(
        self,
        pharmacy_id: str,
    ) -> dict[str, str | None] | None:
        """
        Load service hours from database.

        Args:
            pharmacy_id: Pharmacy UUID

        Returns:
            Hours configuration dictionary or None
        """
        try:
            pharmacy_uuid = UUID(str(pharmacy_id))
        except ValueError as e:
            logger.warning(f"Invalid pharmacy_id format: {e}")
            return None

        try:
            from app.core.tenancy.pharmacy_repository import PharmacyRepository
            from app.database.async_db import get_async_db_context

            async with get_async_db_context() as session:
                repo = PharmacyRepository(session)
                config = await repo.get_by_id(pharmacy_uuid)

                if config and hasattr(config, "bot_service_hours"):
                    return config.bot_service_hours  # type: ignore[return-value]
        except Exception as e:
            logger.warning(f"Failed to load service hours from DB: {e}")

        return None

    async def get_service_info(
        self,
        pharmacy_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get full service hours information for display.

        Args:
            pharmacy_id: Pharmacy UUID

        Returns:
            Dictionary with all service hours info
        """
        hours_config = None
        if pharmacy_id:
            hours_config = await self._load_hours_from_db(pharmacy_id)
        if hours_config is None:
            hours_config = DEFAULT_SERVICE_HOURS

        result = self.check_service_hours(
            bot_service_hours=hours_config,
        )

        return {
            "schedule": hours_config,
            "current_status": await result,
        }


# Singleton instance
_business_hours_service: BusinessHoursService | None = None


def get_business_hours_service() -> BusinessHoursService:
    """
    Get singleton business hours service instance.

    Returns:
        BusinessHoursService instance
    """
    global _business_hours_service
    if _business_hours_service is None:
        _business_hours_service = BusinessHoursService()
    return _business_hours_service


__all__ = [
    "BusinessHoursService",
    "BusinessHoursResult",
    "get_business_hours_service",
    "DEFAULT_SERVICE_HOURS",
    "ARGENTINA_TZ",
]
