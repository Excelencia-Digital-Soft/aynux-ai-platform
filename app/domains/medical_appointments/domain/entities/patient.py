"""Patient Entity.

Represents a patient in the medical appointment system.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.core.domain.entities import Entity


@dataclass
class Patient(Entity[str]):
    """Paciente del sistema de turnos médicos.

    Stores patient information retrieved from external systems
    (HCWeb/Mercedario) for use during the appointment flow.
    """

    # Identificación externa
    external_id: str | None = None
    institution: str = ""  # "mercedario" | "patologia_digestiva"

    # Datos personales
    document: str = ""  # DNI
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""
    birth_date: date | None = None

    # Contacto
    phone: str = ""
    email: str = ""
    address: str = ""

    # Datos médicos
    obra_social: str = ""  # Obra social/prepaga
    obra_social_number: str = ""  # Número de afiliado

    # Estado
    is_registered: bool = False  # Si está registrado en el sistema externo

    @property
    def display_name(self) -> str:
        """Nombre para mostrar."""
        if self.full_name:
            return self.full_name
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or self.document

    @property
    def whatsapp_number(self) -> str:
        """Número formateado para WhatsApp."""
        # Remove non-digits and ensure country code
        phone = "".join(c for c in self.phone if c.isdigit())
        if phone.startswith("0"):
            phone = "54" + phone[1:]  # Argentina
        if not phone.startswith("54"):
            phone = "54" + phone
        return phone

    @classmethod
    def from_external_data(
        cls,
        data: dict[str, Any],
        institution: str = "patologia_digestiva",
    ) -> "Patient":
        """Factory method para crear desde datos externos.

        Args:
            data: Diccionario con datos del paciente del sistema externo.
            institution: Institución de origen.

        Returns:
            Nueva instancia de Patient.
        """
        return cls(
            external_id=data.get("idPaciente") or data.get("id"),
            institution=institution,
            document=data.get("dni") or data.get("documento") or "",
            first_name=data.get("nombre") or "",
            last_name=data.get("apellido") or "",
            full_name=data.get("nombreCompleto") or data.get("paciente") or "",
            phone=data.get("telefono") or data.get("celular") or "",
            email=data.get("email") or data.get("correo") or "",
            address=data.get("direccion") or data.get("domicilio") or "",
            obra_social=data.get("obraSocial") or data.get("cobertura") or "",
            obra_social_number=data.get("nroAfiliado") or "",
            is_registered=True,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convertir a diccionario."""
        return {
            "id": self.external_id or str(self.id),
            "document": self.document,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "display_name": self.display_name,
            "phone": self.phone,
            "email": self.email,
            "obra_social": self.obra_social,
            "is_registered": self.is_registered,
            "institution": self.institution,
        }

    def to_booking_dict(self) -> dict[str, Any]:
        """Diccionario para crear turno."""
        return {
            "idPaciente": self.external_id,
            "dni": self.document,
            "nombre": self.first_name,
            "apellido": self.last_name,
            "telefono": self.phone,
            "email": self.email,
            "obraSocial": self.obra_social,
        }
