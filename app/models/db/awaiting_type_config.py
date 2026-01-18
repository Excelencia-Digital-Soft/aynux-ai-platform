# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Database-driven awaiting type configuration model. Stores mappings
#              for awaiting input types to handler nodes and valid response intents.
# Tenant-Aware: Yes - each organization can customize (NULL = system defaults).
# Domain-Aware: Yes - supports pharmacy, healthcare, ecommerce via domain_key.
# ============================================================================
"""
AwaitingTypeConfig model - Database-driven awaiting type routing configuration.

Stores routing rules that replace hardcoded dictionaries:
- awaiting_node_map: Maps awaiting_input types to handler nodes
- awaiting_intent_map: Maps awaiting types to valid response intents for validation

Multi-tenant: Each organization can customize their own awaiting type routing.
Multi-domain: Supports multiple domains via domain_key field.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .schemas import CORE_SCHEMA


class AwaitingTypeConfig(Base, TimestampMixin):
    """
    Database-driven awaiting type configuration.

    Replaces hardcoded awaiting_node_map and awaiting_intent_map in router_supervisor.py
    with database-driven configuration that supports multi-tenancy and multi-domain.

    Attributes:
        id: Unique identifier
        organization_id: FK to organizations (NULL for system-wide defaults)
        domain_key: Domain scope (pharmacy, healthcare, etc.)
        awaiting_type: Type of awaited input (dni, amount, payment_confirmation, etc.)
        target_node: Node to route to when this awaiting type is active
        valid_response_intents: List of intent keys for Priority 0 validation
        validation_pattern: Optional regex pattern for validating responses
        priority: Processing priority (higher = first)
        is_enabled: Whether configuration is active
        display_name: Human-readable name
        description: Usage notes

    Awaiting Types (from router_supervisor.py):
        - account_number: Awaiting pharmacy account number -> auth_plex (primary auth)
        - account_not_found: Awaiting retry/DNI selection -> auth_plex
        - dni: Awaiting DNI input -> auth_plex (fallback auth)
        - name: Awaiting name input -> auth_plex
        - amount: Awaiting payment amount -> payment_processor
        - payment_confirmation: Awaiting yes/no -> payment_processor
        - account_selection: Awaiting account number -> account_switcher
        - own_or_other: Awaiting own/other selection -> account_switcher
        - menu_selection: Awaiting menu option -> main_menu_node
        - debt_action: V2 Flow debt menu -> debt_manager
        - pay_debt_action: V2 Flow payment menu -> debt_manager
        - invoice_detail_action: V2 Flow invoice menu -> debt_manager
    """

    __tablename__ = "awaiting_type_configs"
    __table_args__ = (
        Index(
            "idx_awaiting_type_configs_lookup",
            "organization_id",
            "domain_key",
            "is_enabled",
        ),
        Index("idx_awaiting_type_configs_type", "awaiting_type"),
        Index("idx_awaiting_type_configs_priority", "priority"),
        {"schema": CORE_SCHEMA},
    )

    # Primary identification
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique configuration identifier",
    )

    # Foreign key (nullable for system-wide defaults)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{CORE_SCHEMA}.organizations.id", ondelete="CASCADE"),
        nullable=True,
        comment="Organization (NULL for system defaults)",
    )

    # Domain scope
    domain_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pharmacy",
        comment="Domain: pharmacy, healthcare, ecommerce, etc.",
    )

    # Awaiting type identifier
    awaiting_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Awaiting input type (dni, amount, payment_confirmation, etc.)",
    )

    # Target node for routing
    target_node: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Node to route to when awaiting this type",
    )

    # Valid response intents for Priority 0 validation (JSONB array)
    valid_response_intents: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="Intent keys for validating responses (bypasses global keywords)",
    )

    # Optional validation pattern (regex)
    validation_pattern: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Optional regex pattern for validating responses (e.g., amount format)",
    )

    # Priority and flags
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Processing priority (higher = first)",
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether configuration is active",
    )

    # Display information
    display_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Human-readable name",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Usage notes",
    )

    # Extensible configuration (JSONB)
    # Named config_metadata to avoid conflict with SQLAlchemy's metadata attribute
    config_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Additional config: intent_overrides, etc.",
    )

    # Relationships
    organization = relationship(
        "Organization",
        back_populates="awaiting_type_configs",
        foreign_keys=[organization_id],
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<AwaitingTypeConfig(id={self.id}, "
            f"awaiting_type={self.awaiting_type}, "
            f"target_node={self.target_node})>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id) if self.id else None,
            "organization_id": str(self.organization_id) if self.organization_id else None,
            "domain_key": self.domain_key,
            "awaiting_type": self.awaiting_type,
            "target_node": self.target_node,
            "valid_response_intents": self.valid_response_intents or [],
            "validation_pattern": self.validation_pattern,
            "priority": self.priority,
            "is_enabled": self.is_enabled,
            "display_name": self.display_name,
            "description": self.description,
            "metadata": self.config_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def create(
        cls,
        awaiting_type: str,
        target_node: str,
        valid_response_intents: list[str] | None = None,
        validation_pattern: str | None = None,
        priority: int = 0,
        is_enabled: bool = True,
        organization_id: uuid.UUID | None = None,
        domain_key: str = "pharmacy",
        display_name: str | None = None,
        description: str | None = None,
    ) -> "AwaitingTypeConfig":
        """Factory method to create a new AwaitingTypeConfig instance."""
        return cls(
            organization_id=organization_id,
            domain_key=domain_key,
            awaiting_type=awaiting_type,
            target_node=target_node,
            valid_response_intents=valid_response_intents or [],
            validation_pattern=validation_pattern,
            priority=priority,
            is_enabled=is_enabled,
            display_name=display_name or awaiting_type,
            description=description,
        )


# Awaiting type constants for reference
class AwaitingTypes:
    """Constants for awaiting input types (from router_supervisor.py)."""

    # Authentication flow - Account Number (Primary)
    ACCOUNT_NUMBER = "account_number"
    ACCOUNT_NOT_FOUND = "account_not_found"

    # Authentication flow - DNI (Fallback)
    DNI = "dni"
    NAME = "name"

    # Payment flow
    AMOUNT = "amount"
    PAYMENT_CONFIRMATION = "payment_confirmation"

    # Account management
    ACCOUNT_SELECTION = "account_selection"
    OWN_OR_OTHER = "own_or_other"

    # Menu navigation
    MENU_SELECTION = "menu_selection"

    # V2 Flow types
    DEBT_ACTION = "debt_action"
    PAY_DEBT_ACTION = "pay_debt_action"
    INVOICE_DETAIL_ACTION = "invoice_detail_action"

    ALL_TYPES = frozenset(
        {
            ACCOUNT_NUMBER,
            ACCOUNT_NOT_FOUND,
            DNI,
            NAME,
            AMOUNT,
            PAYMENT_CONFIRMATION,
            ACCOUNT_SELECTION,
            OWN_OR_OTHER,
            MENU_SELECTION,
            DEBT_ACTION,
            PAY_DEBT_ACTION,
            INVOICE_DETAIL_ACTION,
        }
    )
