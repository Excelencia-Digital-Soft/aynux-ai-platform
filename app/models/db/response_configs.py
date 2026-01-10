# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Configuración de respuestas genérica para múltiples dominios.
#              Permite configurar is_critical, task_description y fallback_key
#              por intent, organización y dominio.
# Tenant-Aware: Yes - cada organización tiene su propia configuración.
# Domain-Aware: Yes - soporta pharmacy, healthcare, ecommerce, etc.
# ============================================================================
"""
Response Configurations - Database models for multi-domain response generation.

Stores configuration for response generation per intent:
- is_critical: Whether intent uses fixed templates (never LLM)
- task_description: Task description injected into LLM system prompt
- fallback_template_key: Key for fallback template when LLM fails

Multi-tenant: Each organization can customize their own response configurations.
Multi-domain: Supports pharmacy, healthcare, ecommerce, and future domains via domain_key.
"""

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin
from .schemas import CORE_SCHEMA


class ResponseConfig(Base, TimestampMixin):
    """
    Multi-domain response configuration.

    Each configuration defines how response generation handles
    a specific intent for a specific organization and domain.

    Attributes:
        id: Unique identifier
        organization_id: Tenant that owns this configuration
        domain_key: Domain scope (pharmacy, healthcare, ecommerce, etc.)
        intent_key: Intent identifier (e.g., "greeting", "payment_confirmation")
        is_critical: If True, always uses fixed template, never LLM
        task_description: Task description for LLM system prompt
        fallback_template_key: Key in fallback_templates.yaml
        display_name: Human-readable name
        description: Configuration description
        priority: Display/processing order
        is_enabled: Whether configuration is active
    """

    __tablename__ = "response_configs"

    # Primary identification
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique configuration identifier",
    )

    # Multi-tenant association
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization that owns this configuration",
    )

    # Domain scope (multi-domain support)
    domain_key = Column(
        String(50),
        nullable=False,
        default="pharmacy",
        comment="Domain: pharmacy, healthcare, ecommerce, etc.",
    )

    # Intent identification
    intent_key = Column(
        String(100),
        nullable=False,
        comment="Intent identifier (e.g., 'greeting', 'payment_confirmation')",
    )

    # Core configuration
    is_critical = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="If True, always uses fixed template from critical_templates.yaml, never LLM",
    )

    task_description = Column(
        Text,
        nullable=False,
        comment="Task description injected into LLM system prompt",
    )

    fallback_template_key = Column(
        String(100),
        nullable=False,
        comment="Key in fallback_templates.yaml",
    )

    # Display information
    display_name = Column(
        String(200),
        nullable=True,
        comment="Human-readable configuration name",
    )

    description = Column(
        Text,
        nullable=True,
        comment="Configuration description and usage notes",
    )

    # Status and ordering
    priority = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Display/processing order (higher = first)",
    )

    is_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether configuration is active",
    )

    # Relationships
    organization = relationship(
        "Organization",
        back_populates="response_configs",
    )

    # Table configuration
    __table_args__ = (
        Index("idx_response_configs_org", organization_id),
        Index("idx_response_configs_domain", domain_key),
        Index("idx_response_configs_enabled", organization_id, is_enabled),
        Index("idx_response_configs_org_domain", organization_id, domain_key),
        Index(
            "uq_response_configs_org_domain_intent",
            organization_id,
            domain_key,
            intent_key,
            unique=True,
        ),
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<ResponseConfig(domain='{self.domain_key}', intent='{self.intent_key}', org={self.organization_id})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "domain_key": self.domain_key,
            "intent_key": self.intent_key,
            "is_critical": self.is_critical,
            "task_description": self.task_description,
            "fallback_template_key": self.fallback_template_key,
            "display_name": self.display_name,
            "description": self.description,
            "priority": self.priority,
            "is_enabled": self.is_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# Backward compatibility alias (deprecated, use ResponseConfig)
PharmacyResponseConfig = ResponseConfig
