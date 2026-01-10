# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Data Transfer Objects for appointment-related operations.
# ============================================================================
"""Appointment DTOs.

Data Transfer Objects for appointment operations including
booking, cancellation, rescheduling, and queries.
"""

from dataclasses import dataclass, field
from datetime import date, time
from typing import Any

# =============================================================================
# Request DTOs
# =============================================================================


@dataclass(frozen=True)
class BookAppointmentRequest:
    """Request DTO for booking a new appointment."""

    patient_id: str
    patient_document: str
    patient_name: str
    patient_phone: str
    provider_id: str
    specialty_code: str
    appointment_date: date
    appointment_time: time
    frequency: int = 0  # 0 = single appointment


@dataclass(frozen=True)
class CancelAppointmentRequest:
    """Request DTO for cancelling an appointment."""

    appointment_id: str
    reason: str = ""


@dataclass(frozen=True)
class ConfirmAppointmentRequest:
    """Request DTO for confirming an appointment."""

    appointment_id: str


@dataclass(frozen=True)
class RescheduleAppointmentRequest:
    """Request DTO for rescheduling an appointment."""

    appointment_id: str
    new_date: date
    new_time: time
    frequency: int = 0


@dataclass(frozen=True)
class RegisterPatientRequest:
    """Request DTO for registering a new patient."""

    document: str
    first_name: str
    last_name: str
    phone: str
    birth_date: date | None = None
    email: str = ""
    obra_social: str = ""


@dataclass(frozen=True)
class GetAvailableSlotsRequest:
    """Request DTO for getting available time slots."""

    provider_id: str
    specialty_code: str | None = None
    target_date: date | None = None


@dataclass(frozen=True)
class GetPatientAppointmentsRequest:
    """Request DTO for getting patient's appointments."""

    patient_id: str | None = None
    patient_document: str | None = None


@dataclass(frozen=True)
class SendReminderRequest:
    """Request DTO for sending appointment reminders."""

    days_before: int = 1  # 1 = tomorrow, 7 = next week


# =============================================================================
# Response DTOs
# =============================================================================


@dataclass
class AppointmentDTO:
    """DTO representing an appointment."""

    id: str
    external_id: str | None
    patient_document: str
    patient_name: str
    provider_id: str
    provider_name: str
    specialty_code: str
    specialty_name: str
    appointment_date: str  # ISO format
    appointment_time: str  # HH:MM format
    status: str
    status_display: str
    institution: str
    is_today: bool = False
    is_upcoming: bool = False

    @classmethod
    def from_external_data(cls, data: dict[str, Any]) -> "AppointmentDTO":
        """Create DTO from external system data."""
        return cls(
            id=str(data.get("idTurno") or data.get("id") or ""),
            external_id=data.get("idTurno") or data.get("id"),
            patient_document=data.get("documento") or data.get("dni") or "",
            patient_name=data.get("paciente") or data.get("nombrePaciente") or "",
            provider_id=str(data.get("idPrestador") or data.get("matricula") or ""),
            provider_name=data.get("prestador") or data.get("nombrePrestador") or "",
            specialty_code=data.get("especialidad") or data.get("codigoEspecialidad") or "",
            specialty_name=data.get("nombreEspecialidad") or data.get("especialidadNombre") or "",
            appointment_date=data.get("fecha") or "",
            appointment_time=data.get("hora") or "",
            status=data.get("estado") or "pending",
            status_display=data.get("estadoNombre") or "Pendiente",
            institution=data.get("institucion") or "",
        )


@dataclass
class PatientDTO:
    """DTO representing a patient."""

    id: str
    external_id: str | None
    document: str
    first_name: str
    last_name: str
    full_name: str
    phone: str
    email: str
    obra_social: str
    is_registered: bool
    is_verified: bool = False

    @classmethod
    def from_external_data(cls, data: dict[str, Any]) -> "PatientDTO":
        """Create DTO from external system data."""
        first_name = data.get("nombre") or data.get("Nombre") or ""
        last_name = data.get("apellido") or data.get("Apellido") or ""
        full_name = data.get("nombreCompleto") or data.get("paciente") or f"{first_name} {last_name}".strip()

        return cls(
            id=str(data.get("idPaciente") or data.get("IdPaciente") or data.get("id") or ""),
            external_id=data.get("idPaciente") or data.get("IdPaciente"),
            document=data.get("documento") or data.get("Documento") or data.get("dni") or "",
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
            phone=data.get("telefono") or data.get("celular") or data.get("TelefonoMovil") or "",
            email=data.get("email") or data.get("correo") or "",
            obra_social=data.get("obraSocial") or data.get("cobertura") or "",
            is_registered=True,
            is_verified=data.get("verificadoWhatsapp", False),
        )


@dataclass
class ProviderDTO:
    """DTO representing a medical provider."""

    id: str
    name: str
    license_number: str  # Matrícula
    specialty_code: str
    specialty_name: str
    next_available: str | None = None

    @classmethod
    def from_external_data(cls, data: dict[str, Any]) -> "ProviderDTO":
        """Create DTO from external system data."""
        return cls(
            id=str(data.get("idPrestador") or data.get("matricula") or data.get("id") or ""),
            name=data.get("nombre") or data.get("nombrePrestador") or "",
            license_number=str(data.get("matricula") or ""),
            specialty_code=data.get("especialidad") or data.get("codigoEspecialidad") or "",
            specialty_name=data.get("nombreEspecialidad") or "",
            next_available=data.get("proximoTurno"),
        )


@dataclass
class SpecialtyDTO:
    """DTO representing a medical specialty."""

    code: str
    name: str
    description: str = ""

    @classmethod
    def from_external_data(cls, data: dict[str, Any]) -> "SpecialtyDTO":
        """Create DTO from external system data."""
        return cls(
            code=data.get("codigo") or data.get("id") or "",
            name=data.get("nombre") or data.get("descripcion") or "",
            description=data.get("descripcion") or "",
        )


@dataclass
class AvailableSlotDTO:
    """DTO representing an available time slot."""

    date: str  # ISO format or dd/mm/yyyy
    time: str  # HH:MM format
    provider_id: str | None = None
    provider_name: str | None = None


@dataclass
class AvailableDateDTO:
    """DTO representing an available date."""

    date: str  # ISO format or dd/mm/yyyy
    day_name: str = ""  # Lunes, Martes, etc.
    slots_count: int = 0


# =============================================================================
# Result DTOs
# =============================================================================


@dataclass
class UseCaseResult:
    """Generic result for use case operations."""

    success: bool
    data: Any | None = None
    error_code: str | None = None
    error_message: str | None = None

    @classmethod
    def ok(cls, data: Any = None) -> "UseCaseResult":
        """Create successful result."""
        return cls(success=True, data=data)

    @classmethod
    def error(cls, code: str, message: str) -> "UseCaseResult":
        """Create error result."""
        return cls(success=False, error_code=code, error_message=message)


@dataclass
class BookAppointmentResult(UseCaseResult):
    """Result for book appointment operation."""

    appointment: AppointmentDTO | None = None


@dataclass
class GetAvailableSlotsResult(UseCaseResult):
    """Result for get available slots operation."""

    dates: list[AvailableDateDTO] = field(default_factory=list)
    slots: list[AvailableSlotDTO] = field(default_factory=list)
    suggested_slot: AvailableSlotDTO | None = None


@dataclass
class GetPatientAppointmentsResult(UseCaseResult):
    """Result for get patient appointments operation."""

    appointments: list[AppointmentDTO] = field(default_factory=list)


@dataclass
class SendReminderResult(UseCaseResult):
    """Result for send reminder operation."""

    sent_count: int = 0
    failed_count: int = 0
    appointment_ids: list[str] = field(default_factory=list)
