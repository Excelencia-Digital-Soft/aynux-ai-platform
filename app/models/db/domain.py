# ============================================================================
# SCOPE: GLOBAL
# Description: Centralized domain registry for the multi-domain system.
#              Domains are business verticals (excelencia, pharmacy, healthcare, etc.)
#              shared between agent catalog and bypass rules.
# Tenant-Aware: No - domains are system-wide configuration.
# ============================================================================
"""
Domain model - Centralized domain registry.

Stores available business domains that can be assigned to agents and bypass rules.
Provides a single source of truth for domain options across the application.
"""

import uuid

from sqlalchemy import Boolean, Column, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from .base import Base, TimestampMixin
from .schemas import CORE_SCHEMA


class Domain(Base, TimestampMixin):
    """
    Domain registry entry.

    Stores information about available business domains in the system.
    Used by agent catalog and bypass rules for domain assignment.

    Attributes:
        id: Unique identifier
        domain_key: Unique domain identifier (e.g., "excelencia", "pharmacy")
        display_name: Human-readable display name for UI
        description: Domain description and purpose
        icon: PrimeVue icon class (e.g., "pi-building", "pi-heart")
        color: Tag severity color (e.g., "info", "success", "warn")
        enabled: Whether domain is available for selection
        sort_order: Display order in dropdowns (lower = first)
    """

    __tablename__ = "domains"
    __table_args__ = (
        Index("ix_core_domains_enabled", "enabled"),
        {"schema": CORE_SCHEMA},
    )

    # Primary identification
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique domain identifier",
    )

    # Domain identification
    domain_key = Column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique domain key (e.g., 'excelencia', 'pharmacy')",
    )

    # Display properties
    display_name = Column(
        String(255),
        nullable=False,
        comment="Human-readable name for UI display",
    )

    description = Column(
        Text,
        nullable=True,
        comment="Domain description and purpose",
    )

    icon = Column(
        String(100),
        nullable=True,
        comment="PrimeVue icon class (e.g., 'pi-building')",
    )

    color = Column(
        String(50),
        nullable=True,
        comment="Tag severity color (e.g., 'info', 'success')",
    )

    # Status and ordering
    enabled = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether domain is available for selection",
    )

    sort_order = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Display order in dropdowns (lower = first)",
    )

    def __repr__(self) -> str:
        return f"<Domain(key={self.domain_key}, name={self.display_name})>"

    def to_dict(self) -> dict:
        """Convert domain to dictionary representation."""
        return {
            "id": str(self.id),
            "domain_key": self.domain_key,
            "display_name": self.display_name,
            "description": self.description,
            "icon": self.icon,
            "color": self.color,
            "enabled": self.enabled,
            "sort_order": self.sort_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
