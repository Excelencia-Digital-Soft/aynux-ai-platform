"""
Plex Customer Entity

Domain entity representing a customer from the Plex ERP system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlexCustomer:
    """
    Customer entity from Plex ERP system.

    Represents a customer record from the /wsplex/clientes endpoint.
    Includes validation logic for identifying "dirty" or generic records.

    Attributes:
        id: Plex internal customer ID
        nombre: Customer display name
        documento: Document number (DNI) - may be empty or "1"
        telefono: Phone number
        email: Email address (optional)
        cuit: Tax ID (optional)
        direccion: Address (optional)
    """

    id: int
    nombre: str
    documento: str | None = None
    telefono: str | None = None
    email: str | None = None
    cuit: str | None = None
    direccion: str | None = None

    # Generic/placeholder names that indicate invalid records
    GENERIC_NAMES: set[str] = field(
        default_factory=lambda: {
            "CONSUMIDOR FINAL",
            "ALL MEDICINE",
            "BANCARIA",
            "OSPECON",
            "JUZFED",
            "MOSTRADOR",
            "VARIOS",
            "CLIENTE",
            "SIN NOMBRE",
        },
        repr=False,
    )

    @property
    def is_valid_for_identification(self) -> bool:
        """
        Check if customer has valid identification data.

        Returns False for:
        - Generic/placeholder names (CONSUMIDOR FINAL, etc.)
        - Empty or placeholder documents ("", "1")
        - Missing essential data
        """
        # Check for generic names
        if self.nombre and self.nombre.upper() in self.GENERIC_NAMES:
            return False

        # Check for invalid documents
        if self.documento in (None, "", "1", "0"):
            return False

        # Must have at least name
        if not self.nombre or len(self.nombre.strip()) < 2:
            return False

        return True

    @property
    def display_name(self) -> str:
        """Get formatted display name for user-facing messages."""
        return self.nombre.title() if self.nombre else "Cliente"

    @property
    def masked_document(self) -> str:
        """Get partially masked document for privacy."""
        if not self.documento or len(self.documento) < 4:
            return "N/A"
        return f"***{self.documento[-4:]}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "nombre": self.nombre,
            "documento": self.documento,
            "telefono": self.telefono,
            "email": self.email,
            "cuit": self.cuit,
            "direccion": self.direccion,
            "is_valid": self.is_valid_for_identification,
        }

    @classmethod
    def from_plex_response(cls, data: dict[str, Any]) -> PlexCustomer:
        """
        Create instance from Plex API response.

        Args:
            data: Raw response from /wsplex/clientes endpoint

        Returns:
            PlexCustomer instance

        Note:
            Handles field name variations from PLEX API:
            - idcliente/id → id
            - nrodoc/nro_doc/documento → documento
            - domicilio/direccion → direccion
        """
        # Handle both "id" and "idcliente" field names
        customer_id = data.get("idcliente") or data.get("id", 0)

        # Handle both "nrodoc" and "nro_doc" field names
        documento = data.get("nrodoc") or data.get("nro_doc") or data.get("documento")

        return cls(
            id=int(customer_id),
            nombre=data.get("nombre", "") or "",
            documento=documento,
            telefono=data.get("telefono"),
            email=data.get("email"),
            cuit=data.get("cuit"),
            direccion=data.get("domicilio") or data.get("direccion"),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlexCustomer:
        """Create instance from dictionary (e.g., from state)."""
        return cls(
            id=data.get("id", 0),
            nombre=data.get("nombre", ""),
            documento=data.get("documento"),
            telefono=data.get("telefono"),
            email=data.get("email"),
            cuit=data.get("cuit"),
            direccion=data.get("direccion"),
        )

    def __str__(self) -> str:
        """String representation for logging."""
        return f"PlexCustomer(id={self.id}, nombre='{self.nombre}', doc={self.masked_document})"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"PlexCustomer(id={self.id}, nombre='{self.nombre}', "
            f"documento='{self.documento}', telefono='{self.telefono}')"
        )
