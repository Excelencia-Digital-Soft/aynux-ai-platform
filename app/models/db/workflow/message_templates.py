# ============================================================================
# SCOPE: MULTI-TENANT WORKFLOW
# Description: Message templates for workflows and reminders.
#              Configurable message content with placeholders.
# Tenant-Aware: Yes - via institution_config_id FK (nullable for global).
# ============================================================================
"""
MessageTemplate model - Configurable message templates.

Stores message templates with placeholder support for dynamic content.
Templates can be global (institution_config_id = NULL) or per-institution.

Usage:
    # Get institution-specific template with global fallback
    template = await session.execute(
        select(MessageTemplate).where(
            MessageTemplate.template_key == "reminder_7_days",
            or_(
                MessageTemplate.institution_config_id == config_id,
                MessageTemplate.institution_config_id.is_(None),
            ),
        ).order_by(MessageTemplate.institution_config_id.desc().nullslast())
    )
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, TimestampMixin
from ..schemas import CORE_SCHEMA, WORKFLOW_SCHEMA

if TYPE_CHECKING:
    from ..tenancy import TenantInstitutionConfig


class MessageTemplate(Base, TimestampMixin):
    """
    Message template for workflows and reminders.

    Stores configurable message content with placeholder support.
    Can be global (shared across institutions) or institution-specific.

    Attributes:
        id: Unique identifier.
        institution_config_id: FK to tenant_institution_configs (NULL for global).
        template_key: Unique key (e.g., "reminder_7_days", "booking_confirmed").
        template_type: Type of template (reminder, confirmation, error, etc.).
        display_name: Human-readable name.
        description: Description of the template.
        content: Message content with {placeholders}.
        content_html: Optional HTML version.
        buttons: Interactive buttons for WhatsApp.
        placeholders: List of expected placeholders.
        language: Language code (es, en, etc.).
        is_active: Whether the template is active.
    """

    __tablename__ = "message_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique template identifier",
    )

    # Foreign key to institution (NULL for global templates)
    institution_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{CORE_SCHEMA}.tenant_institution_configs.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
        comment="Institution this template belongs to (NULL for global)",
    )

    # Template identification
    template_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Unique key (e.g., 'reminder_7_days', 'booking_confirmed')",
    )

    template_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="general",
        index=True,
        comment="Type: reminder, confirmation, error, greeting, etc.",
    )

    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable template name",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description of this template",
    )

    # Content
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Message content with {placeholders}",
    )

    content_html: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional HTML version for email",
    )

    # Interactive elements
    buttons: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Interactive buttons [{id, title}, ...]",
    )

    # Metadata
    placeholders: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="List of expected placeholders",
    )

    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="es",
        comment="Language code (es, en, etc.)",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether this template is active",
    )

    # Relationships
    institution_config: Mapped["TenantInstitutionConfig | None"] = relationship(
        "TenantInstitutionConfig",
        foreign_keys=[institution_config_id],
    )

    __table_args__ = (
        Index("idx_message_templates_institution", "institution_config_id"),
        Index("idx_message_templates_key_type", "template_key", "template_type"),
        Index("idx_message_templates_language", "language"),
        # Partial unique index: one global template per key
        Index(
            "idx_message_templates_global_unique",
            "template_key",
            unique=True,
            postgresql_where="institution_config_id IS NULL",
        ),
        {"schema": WORKFLOW_SCHEMA},
    )

    def __repr__(self) -> str:
        scope = "global" if self.institution_config_id is None else f"inst:{self.institution_config_id}"
        return f"<MessageTemplate(key='{self.template_key}', scope='{scope}')>"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "institution_config_id": str(self.institution_config_id) if self.institution_config_id else None,
            "template_key": self.template_key,
            "template_type": self.template_type,
            "display_name": self.display_name,
            "description": self.description,
            "content": self.content,
            "content_html": self.content_html,
            "buttons": self.buttons,
            "placeholders": self.placeholders,
            "language": self.language,
            "is_active": self.is_active,
            "is_global": self.institution_config_id is None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def format(self, **variables: Any) -> str:
        """Format the template with provided variables.

        Args:
            **variables: Template variables to substitute.

        Returns:
            Formatted message string.
        """
        try:
            return self.content.format(**variables)
        except KeyError:
            # Partial substitution for missing keys
            result = self.content
            for key, value in variables.items():
                result = result.replace(f"{{{key}}}", str(value))
            return result

    def get_buttons_for_whatsapp(self) -> list[dict[str, str]]:
        """Get buttons formatted for WhatsApp interactive message.

        Returns:
            List of button dicts with 'id' and 'title' keys.
        """
        return [
            {
                "id": btn.get("id", f"btn_{i}"),
                "title": btn.get("title", f"Option {i + 1}")[:20],  # WhatsApp limit
            }
            for i, btn in enumerate(self.buttons[:3])  # WhatsApp max 3 buttons
        ]
