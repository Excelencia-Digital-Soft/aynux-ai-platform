"""
Schedule Demo Use Case

Use case for scheduling ERP demonstration sessions.
Follows Clean Architecture and SOLID principles.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from app.domains.excelencia.domain.value_objects.erp_types import LicenseType, ModuleType

logger = logging.getLogger(__name__)


@dataclass
class ScheduleDemoRequest:
    """Request for scheduling a demo."""

    company_name: str
    contact_name: str
    contact_email: str
    contact_phone: str | None = None
    preferred_date: date | None = None
    preferred_time: time | None = None
    company_size: str | None = None  # small, medium, large, enterprise
    industry: str | None = None
    interested_modules: list[ModuleType] | None = None
    notes: str | None = None


@dataclass
class DemoSlot:
    """Available demo slot."""

    date: date
    start_time: time
    end_time: time
    is_available: bool = True


@dataclass
class ScheduledDemo:
    """Scheduled demo information."""

    demo_id: str
    company_name: str
    contact_name: str
    contact_email: str
    scheduled_date: date
    scheduled_time: time
    duration_minutes: int
    meeting_url: str | None
    confirmation_sent: bool


@dataclass
class ScheduleDemoResponse:
    """Response from scheduling a demo."""

    success: bool
    scheduled_demo: ScheduledDemo | None = None
    available_slots: list[DemoSlot] | None = None
    recommended_license: LicenseType | None = None
    error: str | None = None
    message: str | None = None


class ScheduleDemoUseCase:
    """
    Use case for scheduling ERP demos.

    Handles demo scheduling, slot availability, and license recommendations.
    """

    # Demo duration by company size
    DEMO_DURATIONS = {
        "small": 30,      # 30 minutes
        "medium": 45,     # 45 minutes
        "large": 60,      # 1 hour
        "enterprise": 90,  # 1.5 hours
    }

    # License recommendations by company size
    LICENSE_RECOMMENDATIONS = {
        "small": LicenseType.BASIC,
        "medium": LicenseType.PROFESSIONAL,
        "large": LicenseType.PROFESSIONAL,
        "enterprise": LicenseType.ENTERPRISE,
    }

    def __init__(self):
        """Initialize use case."""
        # In production, this would connect to a calendar/scheduling service
        self._scheduled_demos: list[ScheduledDemo] = []

    async def execute(self, request: ScheduleDemoRequest) -> ScheduleDemoResponse:
        """
        Execute schedule demo use case.

        Args:
            request: Demo scheduling request

        Returns:
            Response with scheduled demo or available slots
        """
        try:
            # Validate request
            validation_error = self._validate_request(request)
            if validation_error:
                return ScheduleDemoResponse(
                    success=False,
                    error=validation_error,
                )

            # Determine demo duration
            duration = self.DEMO_DURATIONS.get(
                request.company_size or "medium",
                45,
            )

            # Get available slots
            available_slots = await self._get_available_slots(
                preferred_date=request.preferred_date,
                duration_minutes=duration,
            )

            # If preferred date/time specified and available, schedule
            if request.preferred_date and request.preferred_time:
                # Check if slot is available
                is_available = self._check_slot_available(
                    request.preferred_date,
                    request.preferred_time,
                    duration,
                )

                if is_available:
                    demo = await self._schedule_demo(request, duration)

                    # Get license recommendation
                    recommended_license = self.LICENSE_RECOMMENDATIONS.get(
                        request.company_size or "medium",
                        LicenseType.PROFESSIONAL,
                    )

                    return ScheduleDemoResponse(
                        success=True,
                        scheduled_demo=demo,
                        recommended_license=recommended_license,
                        message=f"Demo programada para {demo.scheduled_date} a las {demo.scheduled_time.strftime('%H:%M')}",
                    )
                else:
                    return ScheduleDemoResponse(
                        success=False,
                        available_slots=available_slots,
                        error="El horario solicitado no esta disponible. Por favor, elige otro horario.",
                    )

            # Return available slots if no preference specified
            return ScheduleDemoResponse(
                success=True,
                available_slots=available_slots,
                message="Estos son los horarios disponibles para tu demo:",
            )

        except Exception as e:
            logger.error(f"Error scheduling demo: {e}", exc_info=True)
            return ScheduleDemoResponse(
                success=False,
                error=f"Error al programar la demo: {str(e)}",
            )

    def _validate_request(self, request: ScheduleDemoRequest) -> str | None:
        """Validate demo request."""
        if not request.company_name:
            return "El nombre de la empresa es requerido"
        if not request.contact_name:
            return "El nombre de contacto es requerido"
        if not request.contact_email:
            return "El email de contacto es requerido"
        if "@" not in request.contact_email:
            return "El email no tiene un formato valido"
        return None

    async def _get_available_slots(
        self,
        preferred_date: date | None,
        duration_minutes: int,
    ) -> list[DemoSlot]:
        """Get available demo slots."""
        slots: list[DemoSlot] = []

        # Generate slots for next 7 business days
        start_date = preferred_date or date.today() + timedelta(days=1)

        business_days_found = 0
        current_date = start_date

        while business_days_found < 7:
            # Skip weekends
            if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                # Morning slots
                for hour in [9, 10, 11]:
                    slot_time = time(hour, 0)
                    end_time = (
                        datetime.combine(current_date, slot_time)
                        + timedelta(minutes=duration_minutes)
                    ).time()

                    is_available = self._check_slot_available(
                        current_date, slot_time, duration_minutes
                    )

                    slots.append(DemoSlot(
                        date=current_date,
                        start_time=slot_time,
                        end_time=end_time,
                        is_available=is_available,
                    ))

                # Afternoon slots
                for hour in [14, 15, 16]:
                    slot_time = time(hour, 0)
                    end_time = (
                        datetime.combine(current_date, slot_time)
                        + timedelta(minutes=duration_minutes)
                    ).time()

                    is_available = self._check_slot_available(
                        current_date, slot_time, duration_minutes
                    )

                    slots.append(DemoSlot(
                        date=current_date,
                        start_time=slot_time,
                        end_time=end_time,
                        is_available=is_available,
                    ))

                business_days_found += 1

            current_date += timedelta(days=1)

        return slots

    def _check_slot_available(
        self,
        check_date: date,
        check_time: time,
        duration_minutes: int,
    ) -> bool:
        """Check if a slot is available."""
        check_start = datetime.combine(check_date, check_time)
        check_end = check_start + timedelta(minutes=duration_minutes)

        for demo in self._scheduled_demos:
            demo_start = datetime.combine(demo.scheduled_date, demo.scheduled_time)
            demo_end = demo_start + timedelta(minutes=demo.duration_minutes)

            # Check for overlap
            if not (check_end <= demo_start or check_start >= demo_end):
                return False

        return True

    async def _schedule_demo(
        self,
        request: ScheduleDemoRequest,
        duration_minutes: int,
    ) -> ScheduledDemo:
        """Schedule the demo."""
        import uuid

        demo_id = str(uuid.uuid4())[:8].upper()

        # Assert preferred_date and preferred_time are set (validated before calling this method)
        assert request.preferred_date is not None, "preferred_date must be set"
        assert request.preferred_time is not None, "preferred_time must be set"

        demo = ScheduledDemo(
            demo_id=f"DEMO-{demo_id}",
            company_name=request.company_name,
            contact_name=request.contact_name,
            contact_email=request.contact_email,
            scheduled_date=request.preferred_date,
            scheduled_time=request.preferred_time,
            duration_minutes=duration_minutes,
            meeting_url=f"https://meet.excelencia-erp.com/demo/{demo_id.lower()}",
            confirmation_sent=False,
        )

        self._scheduled_demos.append(demo)

        logger.info(
            f"Demo scheduled: {demo.demo_id} for {request.company_name} "
            f"on {demo.scheduled_date} at {demo.scheduled_time}"
        )

        return demo

    async def get_available_slots(
        self,
        target_date: date,
        duration_minutes: int = 45,
    ) -> list[DemoSlot]:
        """
        Get available demo slots for a given date.

        Args:
            target_date: Date to get slots for
            duration_minutes: Duration of demo in minutes

        Returns:
            List of available DemoSlot objects
        """
        return await self._get_available_slots(
            preferred_date=target_date,
            duration_minutes=duration_minutes,
        )

    def get_confirmation_text(self, response: ScheduleDemoResponse) -> str:
        """
        Generate confirmation text for chat response.

        Args:
            response: ScheduleDemoResponse

        Returns:
            Formatted confirmation text
        """
        if not response.success:
            return f"Error: {response.error}"

        if response.scheduled_demo:
            demo = response.scheduled_demo
            lines = [
                "Tu demo ha sido programada con exito!",
                "",
                f"Codigo de demo: {demo.demo_id}",
                f"Fecha: {demo.scheduled_date.strftime('%d/%m/%Y')}",
                f"Hora: {demo.scheduled_time.strftime('%H:%M')}",
                f"Duracion: {demo.duration_minutes} minutos",
                "",
            ]

            if demo.meeting_url:
                lines.append(f"Link de la reunion: {demo.meeting_url}")
                lines.append("")

            if response.recommended_license:
                lines.append(
                    f"Basado en tu empresa, te recomendamos la licencia: "
                    f"{response.recommended_license.value.title()}"
                )

            lines.append("\nTe enviaremos un recordatorio por email.")

            return "\n".join(lines)

        if response.available_slots:
            lines = [response.message or "Horarios disponibles:", ""]

            # Group by date
            current_date = None
            for slot in response.available_slots:
                if slot.is_available:
                    if slot.date != current_date:
                        current_date = slot.date
                        lines.append(f"\n{current_date.strftime('%A %d/%m/%Y')}:")
                    lines.append(f"  - {slot.start_time.strftime('%H:%M')}")

            lines.append("\nIndica la fecha y hora que prefieras para agendar tu demo.")

            return "\n".join(lines)

        return "No hay informacion disponible."
