"""Provider Entity.

Represents a medical provider (doctor/specialist) in the appointment system.
"""

from dataclasses import dataclass
from typing import Any

from app.core.domain.entities import Entity

from ..value_objects.specialty import MedicalSpecialty


@dataclass
class Provider(Entity[str]):
    """Prestador médico (doctor/especialista).

    Stores provider information for appointment scheduling.
    """

    # Identificación externa
    external_id: str | None = None
    institution: str = ""  # "mercedario" | "patologia_digestiva"

    # Datos profesionales
    license_number: str = ""  # Matrícula
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""

    # Especialidad
    specialty: MedicalSpecialty = MedicalSpecialty.GENERAL
    specialty_code: str = ""  # Código en sistema externo

    # Disponibilidad
    is_active: bool = True
    consultation_duration_minutes: int = 30

    @property
    def display_name(self) -> str:
        """Nombre para mostrar."""
        if self.full_name:
            return self.full_name
        if self.first_name and self.last_name:
            return f"Dr. {self.first_name} {self.last_name}"
        return self.license_number

    @property
    def short_description(self) -> str:
        """Descripción corta para botones/opciones."""
        return f"{self.display_name} - {self.specialty.display_name}"

    @classmethod
    def from_external_data(
        cls,
        data: dict[str, Any],
        institution: str = "patologia_digestiva",
    ) -> "Provider":
        """Factory method para crear desde datos externos.

        Args:
            data: Diccionario con datos del prestador del sistema externo.
            institution: Institución de origen.

        Returns:
            Nueva instancia de Provider.
        """
        # Intentar mapear especialidad
        specialty_value = data.get("especialidad") or data.get("specialty") or data.get("codEspecialidad") or ""
        specialty = MedicalSpecialty.GENERAL
        try:
            # Try exact match first
            specialty = MedicalSpecialty(specialty_value.lower())
        except ValueError:
            # Try by code
            from_code = MedicalSpecialty.from_code(specialty_value)
            if from_code:
                specialty = from_code

        return cls(
            external_id=data.get("idPrestador") or data.get("id") or data.get("matricula"),
            institution=institution,
            license_number=data.get("matricula") or data.get("license") or "",
            first_name=data.get("nombre") or "",
            last_name=data.get("apellido") or "",
            full_name=data.get("nombreCompleto") or data.get("prestador") or "",
            specialty=specialty,
            specialty_code=specialty_value,
            is_active=data.get("activo", True),
            consultation_duration_minutes=data.get("duracionTurno", 30),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convertir a diccionario."""
        return {
            "id": self.external_id or str(self.id),
            "license_number": self.license_number,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "display_name": self.display_name,
            "specialty": self.specialty.value,
            "specialty_name": self.specialty.display_name,
            "specialty_code": self.specialty_code,
            "is_active": self.is_active,
            "institution": self.institution,
        }

    def to_selection_dict(self) -> dict[str, Any]:
        """Diccionario para selección en UI/bot."""
        return {
            "id": self.external_id or str(self.id),
            "label": self.display_name,
            "description": self.specialty.display_name,
            "license": self.license_number,
        }
