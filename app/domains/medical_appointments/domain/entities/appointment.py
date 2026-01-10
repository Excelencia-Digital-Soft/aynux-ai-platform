"""Appointment Entity - Aggregate Root.

Represents a medical appointment (turno) with business logic for
state transitions, validation, and confirmation/cancellation.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any

from app.core.domain.entities import AggregateRoot

from ..value_objects.appointment_status import AppointmentStatus
from ..value_objects.specialty import MedicalSpecialty


@dataclass
class Appointment(AggregateRoot[str]):
    """Turno médico - Aggregate Root.

    Contains all the business logic for managing a medical appointment,
    including state transitions and validation rules.
    """

    # Identificación externa (HCWeb/Mercedario)
    external_id: str | None = None
    institution: str = ""  # "mercedario" | "patologia_digestiva"

    # Paciente
    patient_document: str = ""
    patient_name: str = ""
    patient_phone: str = ""
    patient_email: str = ""

    # Prestador (doctor/specialist)
    provider_id: str = ""
    provider_name: str = ""
    provider_license: str = ""  # Matrícula

    # Turno details
    specialty: MedicalSpecialty = MedicalSpecialty.GENERAL
    appointment_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    status: AppointmentStatus = AppointmentStatus.PENDING

    # Timestamps
    confirmed_at: datetime | None = None
    cancelled_at: datetime | None = None

    # Notes and metadata
    notes: str = ""
    cancellation_reason: str = ""
    reminder_sent: bool = False
    reminder_sent_at: datetime | None = None

    def confirm(self) -> None:
        """Confirmar el turno.

        Raises:
            ValueError: Si el turno no puede ser confirmado desde su estado actual.
        """
        if not self.status.can_transition_to(AppointmentStatus.CONFIRMED):
            raise ValueError(f"No se puede confirmar turno en estado {self.status.display_name}")
        self.status = AppointmentStatus.CONFIRMED
        self.confirmed_at = datetime.now(UTC)
        self.touch()

    def cancel(self, reason: str = "") -> None:
        """Cancelar el turno.

        Args:
            reason: Motivo de la cancelación (opcional).

        Raises:
            ValueError: Si el turno no puede ser cancelado desde su estado actual.
        """
        if not self.status.can_transition_to(AppointmentStatus.CANCELLED):
            raise ValueError(f"No se puede cancelar turno en estado {self.status.display_name}")
        self.status = AppointmentStatus.CANCELLED
        self.cancelled_at = datetime.now(UTC)
        self.cancellation_reason = reason
        self.touch()

    def complete(self) -> None:
        """Marcar el turno como completado (atendido).

        Raises:
            ValueError: Si el turno no puede ser completado desde su estado actual.
        """
        if not self.status.can_transition_to(AppointmentStatus.COMPLETED):
            raise ValueError(f"No se puede completar turno en estado {self.status.display_name}")
        self.status = AppointmentStatus.COMPLETED
        self.touch()

    def mark_no_show(self) -> None:
        """Marcar el turno como no presentado.

        Raises:
            ValueError: Si el turno no puede ser marcado como no presentado.
        """
        if not self.status.can_transition_to(AppointmentStatus.NO_SHOW):
            raise ValueError(f"No se puede marcar como no presentado desde estado {self.status.display_name}")
        self.status = AppointmentStatus.NO_SHOW
        self.touch()

    def reschedule(self, new_date: date, new_time: time) -> None:
        """Reprogramar el turno.

        Args:
            new_date: Nueva fecha del turno.
            new_time: Nuevo horario del turno.

        Raises:
            ValueError: Si el turno no puede ser reprogramado desde su estado actual.
        """
        if not self.status.can_transition_to(AppointmentStatus.RESCHEDULED):
            raise ValueError(f"No se puede reprogramar turno en estado {self.status.display_name}")
        self.status = AppointmentStatus.RESCHEDULED
        self.appointment_date = new_date
        self.start_time = new_time
        self.touch()

    def mark_reminder_sent(self) -> None:
        """Marcar que se envió recordatorio."""
        self.reminder_sent = True
        self.reminder_sent_at = datetime.now(UTC)
        self.touch()

    # Query methods
    def is_today(self) -> bool:
        """Verificar si el turno es hoy."""
        if self.appointment_date is None:
            return False
        return self.appointment_date == date.today()

    def is_tomorrow(self) -> bool:
        """Verificar si el turno es mañana."""
        if self.appointment_date is None:
            return False
        from datetime import timedelta

        return self.appointment_date == date.today() + timedelta(days=1)

    def is_upcoming(self) -> bool:
        """Verificar si el turno es futuro."""
        if self.appointment_date is None:
            return False
        return self.appointment_date >= date.today()

    def is_past(self) -> bool:
        """Verificar si el turno ya pasó."""
        if self.appointment_date is None:
            return False
        return self.appointment_date < date.today()

    def is_active(self) -> bool:
        """Verificar si el turno está activo."""
        return self.status.is_active()

    def needs_reminder(self) -> bool:
        """Verificar si el turno necesita recordatorio."""
        return self.status.requires_reminder() and not self.reminder_sent and self.is_upcoming()

    # Properties for notification formatting
    @property
    def formatted_date(self) -> str:
        """Fecha formateada para mensajes (dd/mm/yyyy)."""
        if self.appointment_date is None:
            return ""
        return self.appointment_date.strftime("%d/%m/%Y")

    @property
    def formatted_time(self) -> str:
        """Hora formateada para mensajes (HH:MM)."""
        if self.start_time is None:
            return ""
        return self.start_time.strftime("%H:%M")

    @property
    def specialty_name(self) -> str:
        """Nombre de la especialidad para mensajes."""
        return self.specialty.display_name

    @property
    def appointment_datetime(self) -> datetime | None:
        """Combina fecha y hora en un datetime."""
        if self.appointment_date is None or self.start_time is None:
            return None
        return datetime.combine(self.appointment_date, self.start_time)

    # Factory methods
    @classmethod
    def create(
        cls,
        patient_document: str,
        patient_name: str,
        patient_phone: str,
        provider_id: str,
        provider_name: str,
        provider_license: str,
        specialty: MedicalSpecialty,
        appointment_date: date,
        start_time: time,
        institution: str = "patologia_digestiva",
        external_id: str | None = None,
        patient_email: str = "",
        notes: str = "",
    ) -> "Appointment":
        """Factory method para crear un nuevo turno.

        Args:
            patient_document: DNI del paciente.
            patient_name: Nombre completo del paciente.
            patient_phone: Teléfono del paciente.
            provider_id: ID del prestador.
            provider_name: Nombre del prestador.
            provider_license: Matrícula del prestador.
            specialty: Especialidad médica.
            appointment_date: Fecha del turno.
            start_time: Hora de inicio.
            institution: Institución ("mercedario" | "patologia_digestiva").
            external_id: ID externo del sistema (HCWeb/Mercedario).
            patient_email: Email del paciente (opcional).
            notes: Notas adicionales (opcional).

        Returns:
            Nueva instancia de Appointment.
        """
        return cls(
            external_id=external_id,
            institution=institution,
            patient_document=patient_document,
            patient_name=patient_name,
            patient_phone=patient_phone,
            patient_email=patient_email,
            provider_id=provider_id,
            provider_name=provider_name,
            provider_license=provider_license,
            specialty=specialty,
            appointment_date=appointment_date,
            start_time=start_time,
            status=AppointmentStatus.PENDING,
            notes=notes,
        )

    # Serialization methods
    def to_confirmation_dict(self) -> dict[str, Any]:
        """Diccionario para mensaje de confirmación al paciente."""
        return {
            "id": self.external_id or str(self.id),
            "paciente": self.patient_name,
            "documento": self.patient_document,
            "fecha": self.appointment_date.strftime("%d/%m/%Y") if self.appointment_date else "",
            "hora": self.start_time.strftime("%H:%M") if self.start_time else "",
            "especialidad": self.specialty.display_name,
            "prestador": self.provider_name,
            "matricula": self.provider_license,
            "institucion": self.institution,
            "estado": self.status.display_name,
        }

    def to_reminder_dict(self) -> dict[str, Any]:
        """Diccionario para mensaje de recordatorio."""
        return {
            "id": self.external_id or str(self.id),
            "paciente": self.patient_name,
            "fecha": self.appointment_date.strftime("%d/%m/%Y") if self.appointment_date else "",
            "hora": self.start_time.strftime("%H:%M") if self.start_time else "",
            "especialidad": self.specialty.display_name,
            "prestador": self.provider_name,
            "telefono": self.patient_phone,
        }

    def to_summary_dict(self) -> dict[str, Any]:
        """Diccionario con resumen del turno."""
        return {
            "id": self.external_id or str(self.id),
            "patient_document": self.patient_document,
            "patient_name": self.patient_name,
            "patient_phone": self.patient_phone,
            "provider_name": self.provider_name,
            "specialty": self.specialty.value,
            "specialty_name": self.specialty.display_name,
            "date": self.appointment_date.isoformat() if self.appointment_date else None,
            "time": self.start_time.isoformat() if self.start_time else None,
            "status": self.status.value,
            "status_name": self.status.display_name,
            "institution": self.institution,
            "is_today": self.is_today(),
            "is_upcoming": self.is_upcoming(),
        }
