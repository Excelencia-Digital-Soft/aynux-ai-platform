"""
Jira Configuration model for multi-Jira integration.

Each organization can have its own Jira configuration with
category/priority/module mappings.
"""

import uuid
from typing import Any, cast

from sqlalchemy import Boolean, Column, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ..base import Base, TimestampMixin
from ..schemas import CORE_SCHEMA, SOPORTE_SCHEMA


class JiraConfig(Base, TimestampMixin):
    """
    Jira configuration per organization for multi-Jira support.

    Attributes:
        id: Unique identifier (UUID)
        organization_id: FK to organization (multi-tenant)
        name: Descriptive name for this config
        jira_base_url: Jira instance URL
        jira_project_key: Default project key
        jira_api_token_encrypted: Encrypted API token
        jira_email: Email for authentication
        webhook_secret: Secret for webhook verification
        category_mapping: JSON mapping category -> Jira issue type
        module_mapping: JSON mapping module -> Jira component
        priority_mapping: JSON mapping priority -> Jira priority
        custom_fields: JSON mapping for custom field IDs
        is_active: Whether config is active
    """

    __tablename__ = "jira_configs"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Multi-tenant
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CORE_SCHEMA}.organizations.id", ondelete="CASCADE"),
        nullable=True,
        comment="Organization for multi-tenant (null for global)",
    )

    # Configuration identity
    name = Column(
        String(100),
        nullable=False,
        comment="Descriptive name for this configuration",
    )

    # Jira connection
    jira_base_url = Column(
        String(500),
        nullable=False,
        comment="Jira instance base URL (e.g., https://company.atlassian.net)",
    )
    jira_project_key = Column(
        String(20),
        nullable=False,
        comment="Default Jira project key",
    )
    jira_api_token_encrypted = Column(
        Text,
        nullable=True,
        comment="Encrypted Jira API token",
    )
    jira_email = Column(
        String(200),
        nullable=False,
        comment="Email for Jira API authentication",
    )

    # Webhook
    webhook_secret = Column(
        String(200),
        nullable=True,
        comment="Secret for verifying Jira webhooks",
    )

    # Mappings (JSONB)
    category_mapping = Column(
        JSONB,
        default=dict,
        comment="Mapping: category_code -> Jira issue type",
    )
    module_mapping = Column(
        JSONB,
        default=dict,
        comment="Mapping: module_code -> Jira component",
    )
    priority_mapping = Column(
        JSONB,
        default=dict,
        comment="Mapping: priority -> Jira priority",
    )
    custom_fields = Column(
        JSONB,
        default=dict,
        comment="Mapping: field_name -> Jira custom field ID",
    )

    # Status
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this configuration is active",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<JiraConfig(name={self.name}, project={self.jira_project_key}, active={self.is_active})>"

    @property
    def default_mappings(self) -> dict:
        """Return default mappings if none configured."""
        return {
            "category_mapping": {
                "TECNICO": "Bug",
                "FACTURACION": "Task",
                "CAPACITACION": "Story",
                "INVENTARIO": "Bug",
                "NOMINA": "Task",
                "CONTABILIDAD": "Task",
                "GENERAL": "Task",
            },
            "priority_mapping": {
                "critical": "Highest",
                "high": "High",
                "medium": "Medium",
                "low": "Low",
            },
        }

    def get_jira_issue_type(self, category_code: str) -> str:
        """Get Jira issue type for a category."""
        mapping = cast(dict[str, Any], self.category_mapping)
        if mapping and category_code in mapping:
            return str(mapping[category_code])
        return self.default_mappings["category_mapping"].get(category_code, "Task")

    def get_jira_priority(self, priority: str) -> str:
        """Get Jira priority for our priority."""
        mapping = cast(dict[str, Any], self.priority_mapping)
        if mapping and priority in mapping:
            return str(mapping[priority])
        return self.default_mappings["priority_mapping"].get(priority, "Medium")

    # Table configuration
    __table_args__ = (
        Index("idx_jira_configs_organization_id", organization_id),
        Index("idx_jira_configs_active", is_active),
        Index("idx_jira_configs_project_key", jira_project_key),
        {"schema": SOPORTE_SCHEMA},
    )
