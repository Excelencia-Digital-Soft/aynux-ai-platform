# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Personas registradas/autorizadas para consultas de deuda.
#              Almacena validaciones de DNI+nombre con vencimiento renovable
#              de 180 dias. Un numero de telefono puede tener multiples
#              personas registradas (ej: familiares).
# Tenant-Aware: Yes - cada registro pertenece a una farmacia especifica.
# ============================================================================
"""
RegisteredPerson model - Locally cached authorized persons for debt queries.

Stores verified person data with 180-day expiration (renewable on each use):
- Phone number (WhatsApp) that initiated the registration
- DNI (validated against PLEX)
- Name (validated with LLM fuzzy matching against PLEX)
- PLEX customer ID (for debt queries)
- Expiration date (refreshed to +180 days on each use)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..base import Base, TimestampMixin
from ..schemas import PHARMACY_SCHEMA

# Registration validity period in days
REGISTRATION_VALIDITY_DAYS = 180


class RegisteredPerson(Base, TimestampMixin):
    """
    Locally cached authorized person for debt queries.

    One phone number can have multiple registered persons (e.g., family members).
    Each registration expires after 180 days but is renewed on each use.

    Attributes:
        id: Unique identifier (UUID)
        phone_number: WhatsApp phone number that registered this person
        dni: Document number (validated against PLEX)
        name: Full name (validated with LLM fuzzy matching)
        plex_customer_id: PLEX customer ID for debt queries
        pharmacy_id: FK to pharmacy_merchant_configs (multi-tenant)
        is_self: True if this person is the phone owner (detected by phone match)
        expires_at: Expiration datetime (refreshed to +180 days on each use)
        is_active: Soft-delete flag
        last_used_at: Last time this registration was used for a query
    """

    __tablename__ = "registered_persons"

    # Primary identification
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique registration identifier",
    )

    # WhatsApp phone number that registered this person
    phone_number = Column(
        String(20),
        nullable=False,
        index=True,
        comment="WhatsApp phone number that registered this person",
    )

    # Document number (validated against PLEX)
    dni = Column(
        String(20),
        nullable=False,
        comment="Document number (validated against PLEX)",
    )

    # Full name (validated with LLM fuzzy matching)
    name = Column(
        String(255),
        nullable=False,
        comment="Full name (validated with LLM fuzzy matching)",
    )

    # PLEX customer ID for debt queries
    plex_customer_id = Column(
        Integer,
        nullable=False,
        comment="PLEX customer ID for debt queries",
    )

    # Foreign key to pharmacy_merchant_configs (multi-tenant)
    pharmacy_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{PHARMACY_SCHEMA}.pharmacy_merchant_configs.id", ondelete="CASCADE"),
        nullable=False,
        comment="Pharmacy this registration belongs to",
    )

    # True if person is the phone owner (auto-detected)
    is_self = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if person is the phone owner (auto-detected)",
    )

    # Registration expiration (refreshed to +180 days on each use)
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="Registration expiration (refreshed to +180 days on each use)",
    )

    # Soft-delete flag
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Soft-delete flag",
    )

    # Last time this registration was used
    last_used_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last time this registration was used",
    )

    # Relationships
    pharmacy = relationship("PharmacyMerchantConfig")

    # Table configuration
    __table_args__ = (
        Index("idx_registered_persons_phone", phone_number),
        Index("idx_registered_persons_phone_pharmacy", phone_number, pharmacy_id),
        Index("idx_registered_persons_dni_pharmacy", dni, pharmacy_id),
        Index("idx_registered_persons_expires", expires_at),
        UniqueConstraint(
            "phone_number",
            "dni",
            "pharmacy_id",
            name="uq_registered_persons_phone_dni_pharmacy",
        ),
        {"schema": PHARMACY_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<RegisteredPerson(phone='{self.phone_number}', dni='***{self.dni[-4:]}', name='{self.name}')>"

    @classmethod
    def create(
        cls,
        phone_number: str,
        dni: str,
        name: str,
        plex_customer_id: int,
        pharmacy_id: uuid.UUID,
        is_self: bool = False,
    ) -> RegisteredPerson:
        """
        Factory method to create a new registration with proper expiration.

        Args:
            phone_number: WhatsApp phone number that registered this person
            dni: Document number (validated against PLEX)
            name: Full name (validated with LLM fuzzy matching)
            plex_customer_id: PLEX customer ID for debt queries
            pharmacy_id: Pharmacy UUID this registration belongs to
            is_self: True if person is the phone owner

        Returns:
            New RegisteredPerson instance with expires_at set to +180 days
        """
        now = datetime.now(UTC)
        return cls(
            phone_number=phone_number,
            dni=dni.strip(),
            name=name.upper().strip(),
            plex_customer_id=plex_customer_id,
            pharmacy_id=pharmacy_id,
            is_self=is_self,
            expires_at=now + timedelta(days=REGISTRATION_VALIDITY_DAYS),
            is_active=True,
            last_used_at=now,
        )

    @property
    def is_expired(self) -> bool:
        """Check if registration has expired."""
        if self.expires_at is None:
            return True
        return bool(datetime.now(UTC) > self.expires_at)

    @property
    def is_valid(self) -> bool:
        """Check if registration is valid (active and not expired)."""
        return bool(self.is_active) and not self.is_expired

    @property
    def days_until_expiry(self) -> int:
        """Get days until expiration (negative if expired)."""
        delta = self.expires_at - datetime.now(UTC)
        return delta.days

    def mark_used(self) -> None:
        """
        Update last_used_at timestamp and renew expiration.

        This method refreshes the expiration date to +180 days from now,
        implementing the "renewable on use" behavior.
        """
        now = datetime.now(UTC)
        self.last_used_at = now
        self.expires_at = now + timedelta(days=REGISTRATION_VALIDITY_DAYS)

    def refresh_expiration(self) -> None:
        """Refresh expiration date (after revalidation)."""
        self.expires_at = datetime.now(UTC) + timedelta(days=REGISTRATION_VALIDITY_DAYS)

    def deactivate(self) -> None:
        """Soft-delete this registration."""
        self.is_active = False

    def reactivate(self) -> None:
        """Reactivate a soft-deleted registration and refresh expiration."""
        self.is_active = True
        self.refresh_expiration()

    def _mask_dni(self, dni_value: str | None) -> str:
        """Mask DNI for privacy, showing only last 4 digits."""
        if not dni_value:
            return "****"
        dni_str = str(dni_value)
        return f"***{dni_str[-4:]}" if len(dni_str) >= 4 else "****"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses (masks DNI for privacy)."""
        dni_value: str | None = str(self.dni) if self.dni else None
        expires_at_value = getattr(self, "expires_at", None)
        last_used_at_value = getattr(self, "last_used_at", None)
        created_at_value = getattr(self, "created_at", None)

        return {
            "id": str(self.id),
            "phone_number": str(self.phone_number) if self.phone_number else None,
            "dni_masked": self._mask_dni(dni_value),
            "dni": dni_value,  # Full DNI for internal use
            "name": str(self.name) if self.name else None,
            "plex_customer_id": self.plex_customer_id,
            "pharmacy_id": str(self.pharmacy_id) if self.pharmacy_id else None,
            "is_self": bool(self.is_self),
            "is_valid": self.is_valid,
            "is_expired": self.is_expired,
            "days_until_expiry": self.days_until_expiry,
            "expires_at": expires_at_value.isoformat() if expires_at_value else None,
            "last_used_at": last_used_at_value.isoformat() if last_used_at_value else None,
            "created_at": created_at_value.isoformat() if created_at_value else None,
        }

    def to_display_dict(self) -> dict:
        """Convert to dictionary for user-facing display (no sensitive data)."""
        dni_value: str | None = str(self.dni) if self.dni else None
        return {
            "id": str(self.id),
            "dni_masked": self._mask_dni(dni_value),
            "name": str(self.name) if self.name else None,
            "is_self": bool(self.is_self),
            "days_until_expiry": self.days_until_expiry,
        }
