# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Database-driven routing configuration model. Stores routing
#              rules for keywords, buttons, menu options, and list selections.
# Tenant-Aware: Yes - each organization can customize (NULL = system defaults).
# Domain-Aware: Yes - supports pharmacy, healthcare, ecommerce via domain_key.
# ============================================================================
"""
RoutingConfig model - Database-driven routing configuration.

Stores routing rules that replace hardcoded dictionaries:
- GLOBAL_KEYWORDS: Keywords that interrupt any flow
- MENU_OPTIONS: Main menu number selections
- Button mappings: WhatsApp interactive button IDs to intents
- List selections: WhatsApp interactive list selections

Multi-tenant: Each organization can customize their own routing.
Multi-domain: Supports multiple domains via domain_key field.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin
from .schemas import CORE_SCHEMA


class RoutingConfig(Base, TimestampMixin):
    """
    Database-driven routing configuration.

    Replaces hardcoded routing dictionaries in router.py with database-driven
    configuration that supports multi-tenancy and multi-domain.

    Attributes:
        id: Unique identifier
        organization_id: FK to organizations (NULL for system-wide defaults)
        domain_key: Domain scope (pharmacy, healthcare, etc.)
        config_type: Type of routing rule (global_keyword, button_mapping, etc.)
        trigger_value: Value that triggers routing (keyword, button_id, menu number)
        target_intent: Intent to set when triggered
        target_node: Node to route to (NULL to use default for intent)
        priority: Processing priority (higher = first)
        is_enabled: Whether configuration is active
        requires_auth: Whether route requires authentication
        clears_context: Whether to clear pending flow context
        metadata: Additional configuration (aliases, conditions)
        display_name: Human-readable name
        description: Usage notes

    Config Types:
        - global_keyword: Keywords that interrupt any flow (priority=100)
        - button_mapping: WhatsApp interactive button IDs (priority=50)
        - menu_option: Main menu number selections (priority=40)
        - list_selection: WhatsApp interactive list selections (priority=45)
    """

    __tablename__ = "routing_configs"
    __table_args__ = (
        Index(
            "idx_routing_configs_lookup",
            "organization_id",
            "domain_key",
            "config_type",
            "is_enabled",
        ),
        Index("idx_routing_configs_trigger", "trigger_value"),
        Index("idx_routing_configs_priority", "priority"),
        {"schema": CORE_SCHEMA},
    )

    # Primary identification
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique configuration identifier",
    )

    # Foreign key (nullable for system-wide defaults)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CORE_SCHEMA}.organizations.id", ondelete="CASCADE"),
        nullable=True,
        comment="Organization (NULL for system defaults)",
    )

    # Domain scope
    domain_key = Column(
        String(50),
        nullable=False,
        default="pharmacy",
        comment="Domain: pharmacy, healthcare, ecommerce, etc.",
    )

    # Configuration type
    config_type = Column(
        String(50),
        nullable=False,
        comment="Type: global_keyword, button_mapping, menu_option, list_selection",
    )

    # Trigger and target
    trigger_value = Column(
        String(100),
        nullable=False,
        comment="Value that triggers routing",
    )
    target_intent = Column(
        String(100),
        nullable=False,
        comment="Intent to set when triggered",
    )
    target_node = Column(
        String(100),
        nullable=True,
        comment="Node to route to (NULL for default)",
    )

    # Priority and flags
    priority = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Processing priority (higher = first)",
    )
    is_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether configuration is active",
    )
    requires_auth = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether route requires authentication",
    )
    clears_context = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether to clear pending flow context",
    )

    # Metadata for extensibility
    metadata_ = Column(
        "metadata",
        JSONB,
        nullable=True,
        comment="Additional configuration (aliases, conditions)",
    )

    # Display information
    display_name = Column(
        String(200),
        nullable=True,
        comment="Human-readable name",
    )
    description = Column(
        Text,
        nullable=True,
        comment="Usage notes",
    )

    # Relationships
    organization = relationship(
        "Organization",
        back_populates="routing_configs",
        foreign_keys=[organization_id],
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<RoutingConfig(id={self.id}, "
            f"config_type={self.config_type}, "
            f"trigger={self.trigger_value}, "
            f"intent={self.target_intent})>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        # Cast to runtime values to avoid Column type issues
        id_value: uuid.UUID | None = getattr(self, "id", None)
        org_id_value: uuid.UUID | None = getattr(self, "organization_id", None)
        created: Any = getattr(self, "created_at", None)
        updated: Any = getattr(self, "updated_at", None)

        return {
            "id": str(id_value) if id_value is not None else None,
            "organization_id": str(org_id_value) if org_id_value is not None else None,
            "domain_key": self.domain_key,
            "config_type": self.config_type,
            "trigger_value": self.trigger_value,
            "target_intent": self.target_intent,
            "target_node": self.target_node,
            "priority": self.priority,
            "is_enabled": self.is_enabled,
            "requires_auth": self.requires_auth,
            "clears_context": self.clears_context,
            "metadata": self.metadata_,
            "display_name": self.display_name,
            "description": self.description,
            "created_at": created.isoformat() if created is not None else None,
            "updated_at": updated.isoformat() if updated is not None else None,
        }

    @classmethod
    def create(
        cls,
        config_type: str,
        trigger_value: str,
        target_intent: str,
        target_node: str | None = None,
        priority: int = 0,
        is_enabled: bool = True,
        requires_auth: bool = False,
        clears_context: bool = False,
        metadata: dict[str, Any] | None = None,
        organization_id: uuid.UUID | None = None,
        domain_key: str = "pharmacy",
        display_name: str | None = None,
        description: str | None = None,
    ) -> "RoutingConfig":
        """Factory method to create a new RoutingConfig instance."""
        return cls(
            organization_id=organization_id,
            domain_key=domain_key,
            config_type=config_type,
            trigger_value=trigger_value,
            target_intent=target_intent,
            target_node=target_node,
            priority=priority,
            is_enabled=is_enabled,
            requires_auth=requires_auth,
            clears_context=clears_context,
            metadata_=metadata,
            display_name=display_name or trigger_value,
            description=description,
        )


# Config type constants
class RoutingConfigType:
    """Constants for routing configuration types."""

    GLOBAL_KEYWORD = "global_keyword"
    BUTTON_MAPPING = "button_mapping"
    MENU_OPTION = "menu_option"
    LIST_SELECTION = "list_selection"

    ALL_TYPES = frozenset(
        {
            GLOBAL_KEYWORD,
            BUTTON_MAPPING,
            MENU_OPTION,
            LIST_SELECTION,
        }
    )

    # Default priorities by type
    DEFAULT_PRIORITIES = {
        GLOBAL_KEYWORD: 100,
        BUTTON_MAPPING: 50,
        LIST_SELECTION: 45,
        MENU_OPTION: 40,
    }
