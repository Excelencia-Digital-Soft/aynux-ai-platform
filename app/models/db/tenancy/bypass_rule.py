# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Reglas de bypass routing por tenant. Permite routing directo
#              basado en patrones de número de teléfono o WhatsApp ID.
# Tenant-Aware: Yes - organization_id FK.
# ============================================================================
"""
BypassRule model - Per-tenant bypass routing rules.

Allows tenants to configure direct routing based on:
- Phone number patterns (e.g., "549264*")
- Phone number lists (exact matches)
- WhatsApp Business phone number IDs
"""

import uuid

from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship

from ..base import Base, TimestampMixin
from ..schemas import CORE_SCHEMA


class BypassRule(Base, TimestampMixin):
    """
    Bypass routing rule for a tenant.

    Each rule defines a condition that, when matched, routes messages
    directly to a specific agent bypassing the orchestrator.

    Rule types:
    - phone_number: Pattern matching with wildcard support (e.g., "549*")
    - phone_number_list: Exact match against a list of numbers
    - whatsapp_phone_number_id: Match WhatsApp Business phone number ID

    Attributes:
        id: Unique identifier
        organization_id: FK to organizations
        rule_name: Human-readable name for the rule
        description: Description of what this rule does
        rule_type: Type of matching ("phone_number", "phone_number_list", "whatsapp_phone_number_id")
        pattern: Pattern string for phone_number type (supports * wildcard at end)
        phone_numbers: List of phone numbers for phone_number_list type
        phone_number_id: WhatsApp Business phone number ID for whatsapp_phone_number_id type
        target_agent: Agent key to route to when rule matches
        target_domain: Optional domain override (uses tenant default if not set)
        priority: Priority for rule evaluation (higher = evaluated first)
        enabled: Whether this rule is active
    """

    __tablename__ = "bypass_rules"

    # Primary identification
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique bypass rule identifier",
    )

    # Foreign key
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CORE_SCHEMA}.organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization this rule belongs to",
    )

    # Rule identification
    rule_name = Column(
        String(100),
        nullable=False,
        comment="Human-readable name for the rule",
    )

    description = Column(
        Text,
        nullable=True,
        comment="Description of what this rule does",
    )

    # Rule type
    rule_type = Column(
        String(50),
        nullable=False,
        comment="Type: 'phone_number', 'phone_number_list', 'whatsapp_phone_number_id'",
    )

    # Pattern fields (mutually exclusive based on rule_type)
    pattern = Column(
        String(100),
        nullable=True,
        comment="Pattern for phone_number type (e.g., '549264*' for all San Juan numbers)",
    )

    phone_numbers = Column(
        ARRAY(String),
        nullable=True,
        comment="List of phone numbers for phone_number_list type",
    )

    phone_number_id = Column(
        String(100),
        nullable=True,
        comment="WhatsApp Business phone number ID for whatsapp_phone_number_id type",
    )

    # Routing target
    target_agent = Column(
        String(100),
        nullable=False,
        comment="Agent key to route to (e.g., 'pharmacy_operations_agent')",
    )

    target_domain = Column(
        String(50),
        nullable=True,
        comment="Optional domain override (uses tenant default_domain if not set)",
    )

    # Priority and status
    priority = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Priority for rule evaluation (higher = evaluated first)",
    )

    enabled = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether this rule is active",
    )

    # Relationships
    organization = relationship(
        "Organization",
        back_populates="bypass_rules",
    )

    # Table configuration
    __table_args__ = (
        UniqueConstraint("organization_id", "rule_name", name="uq_org_bypass_rule_name"),
        Index("idx_bypass_rules_org_id", organization_id),
        Index("idx_bypass_rules_enabled", enabled),
        Index("idx_bypass_rules_priority", priority.desc()),
        Index("idx_bypass_rules_rule_type", rule_type),
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<BypassRule(org_id='{self.organization_id}', name='{self.rule_name}', type='{self.rule_type}', enabled={self.enabled})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "rule_name": self.rule_name,
            "description": self.description,
            "rule_type": self.rule_type,
            "pattern": self.pattern,
            "phone_numbers": self.phone_numbers or [],
            "phone_number_id": self.phone_number_id,
            "target_agent": self.target_agent,
            "target_domain": self.target_domain,
            "priority": self.priority,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def matches(self, wa_id: str | None, whatsapp_phone_number_id: str | None = None) -> bool:
        """
        Check if this rule matches the given identifiers.

        Args:
            wa_id: WhatsApp ID (phone number) of the sender
            whatsapp_phone_number_id: WhatsApp Business phone number ID

        Returns:
            True if the rule matches, False otherwise
        """
        if not self.enabled:
            return False

        if self.rule_type == "phone_number":
            if not wa_id or not self.pattern:
                return False
            # Wildcard matching (* at end)
            if self.pattern.endswith("*"):
                return wa_id.startswith(self.pattern[:-1])
            return wa_id == self.pattern

        elif self.rule_type == "phone_number_list":
            if not wa_id or not self.phone_numbers:
                return False
            return wa_id in self.phone_numbers

        elif self.rule_type == "whatsapp_phone_number_id":
            if not whatsapp_phone_number_id or not self.phone_number_id:
                return False
            return whatsapp_phone_number_id == self.phone_number_id

        return False

    @classmethod
    def create_phone_pattern_rule(
        cls,
        organization_id: uuid.UUID,
        rule_name: str,
        pattern: str,
        target_agent: str,
        target_domain: str | None = None,
        description: str | None = None,
        priority: int = 0,
    ) -> "BypassRule":
        """Factory method to create a phone number pattern rule."""
        return cls(
            organization_id=organization_id,
            rule_name=rule_name,
            description=description,
            rule_type="phone_number",
            pattern=pattern,
            target_agent=target_agent,
            target_domain=target_domain,
            priority=priority,
            enabled=True,
        )

    @classmethod
    def create_phone_list_rule(
        cls,
        organization_id: uuid.UUID,
        rule_name: str,
        phone_numbers: list[str],
        target_agent: str,
        target_domain: str | None = None,
        description: str | None = None,
        priority: int = 0,
    ) -> "BypassRule":
        """Factory method to create a phone number list rule."""
        return cls(
            organization_id=organization_id,
            rule_name=rule_name,
            description=description,
            rule_type="phone_number_list",
            phone_numbers=phone_numbers,
            target_agent=target_agent,
            target_domain=target_domain,
            priority=priority,
            enabled=True,
        )

    @classmethod
    def create_whatsapp_id_rule(
        cls,
        organization_id: uuid.UUID,
        rule_name: str,
        phone_number_id: str,
        target_agent: str,
        target_domain: str | None = None,
        description: str | None = None,
        priority: int = 0,
    ) -> "BypassRule":
        """Factory method to create a WhatsApp Business phone number ID rule."""
        return cls(
            organization_id=organization_id,
            rule_name=rule_name,
            description=description,
            rule_type="whatsapp_phone_number_id",
            phone_number_id=phone_number_id,
            target_agent=target_agent,
            target_domain=target_domain,
            priority=priority,
            enabled=True,
        )
