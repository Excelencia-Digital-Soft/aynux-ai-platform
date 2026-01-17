# ============================================================================
# SCOPE: MULTI-TENANT WORKFLOW
# Description: Reminder schedule configuration per institution.
#              Defines when and how reminders are sent.
# Tenant-Aware: Yes - via institution_config_id FK.
# ============================================================================
"""
ReminderSchedule model - Configurable reminder schedules per institution.

Stores reminder configuration including timing, messages, and buttons.
Each institution can have multiple reminder schedules (e.g., 7 days before, 24 hours before).

Usage:
    # Get all active reminder schedules for institution
    schedules = await session.execute(
        select(ReminderSchedule).where(
            ReminderSchedule.institution_config_id == config_id,
            ReminderSchedule.is_active == True,
        ).order_by(ReminderSchedule.trigger_value.desc())
    )
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, TimestampMixin
from ..schemas import CORE_SCHEMA, WORKFLOW_SCHEMA

if TYPE_CHECKING:
    from ..tenancy import TenantInstitutionConfig

    from .message_templates import MessageTemplate


class ReminderSchedule(Base, TimestampMixin):
    """
    Reminder schedule configuration.

    Defines when reminders are sent and links to message templates.

    Attributes:
        id: Unique identifier.
        institution_config_id: FK to tenant_institution_configs.
        schedule_key: Unique key (e.g., "7_day_reminder", "24_hour_reminder").
        display_name: Human-readable name.
        description: Description of the schedule.
        trigger_type: Type of trigger (days_before, hours_before).
        trigger_value: Numeric value for trigger (e.g., 7 for 7 days).
        execution_hour: Hour of day to send (0-23).
        timezone: Timezone for scheduling.
        message_template_id: FK to message template.
        fallback_message: Fallback message if template not found.
        buttons: Interactive buttons for the reminder.
        is_active: Whether the schedule is active.
    """

    __tablename__ = "reminder_schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique schedule identifier",
    )

    # Foreign key to institution
    institution_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{CORE_SCHEMA}.tenant_institution_configs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
        comment="Institution this schedule belongs to",
    )

    # Schedule identification
    schedule_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Unique key within institution (e.g., '7_day_reminder')",
    )

    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable schedule name",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description of this reminder schedule",
    )

    # Trigger configuration
    trigger_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="days_before",
        comment="Type: days_before, hours_before, minutes_before",
    )

    trigger_value: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Numeric value for trigger (e.g., 7 for 7 days before)",
    )

    execution_hour: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=9,
        comment="Hour of day to send reminders (0-23)",
    )

    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="America/Argentina/San_Juan",
        comment="Timezone for scheduling (IANA format)",
    )

    # Message configuration
    message_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{WORKFLOW_SCHEMA}.message_templates.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        comment="Message template to use",
    )

    fallback_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Fallback message if template not found",
    )

    # Interactive buttons
    buttons: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Interactive buttons [{id, title}, ...]",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether this schedule is active",
    )

    # Relationships
    institution_config: Mapped["TenantInstitutionConfig"] = relationship(
        "TenantInstitutionConfig",
        foreign_keys=[institution_config_id],
    )

    message_template: Mapped["MessageTemplate | None"] = relationship(
        "MessageTemplate",
        foreign_keys=[message_template_id],
    )

    __table_args__ = (
        Index("idx_reminder_schedules_institution", "institution_config_id"),
        Index("idx_reminder_schedules_trigger", "trigger_type", "trigger_value"),
        Index("idx_reminder_schedules_active", "is_active"),
        {"schema": WORKFLOW_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<ReminderSchedule(key='{self.schedule_key}', trigger='{self.trigger_type}:{self.trigger_value}')>"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "institution_config_id": str(self.institution_config_id),
            "schedule_key": self.schedule_key,
            "display_name": self.display_name,
            "description": self.description,
            "trigger_type": self.trigger_type,
            "trigger_value": self.trigger_value,
            "execution_hour": self.execution_hour,
            "timezone": self.timezone,
            "message_template_id": str(self.message_template_id) if self.message_template_id else None,
            "fallback_message": self.fallback_message,
            "buttons": self.buttons,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def format_message(
        self,
        patient_name: str,
        appointment_date: str,
        appointment_time: str,
        provider_name: str | None = None,
        specialty_name: str | None = None,
        institution_name: str | None = None,
        **extra_vars: Any,
    ) -> str:
        """Format the reminder message with placeholders.

        Args:
            patient_name: Patient's name.
            appointment_date: Formatted appointment date.
            appointment_time: Formatted appointment time.
            provider_name: Optional provider/doctor name.
            specialty_name: Optional specialty name.
            institution_name: Optional institution name.
            **extra_vars: Additional template variables.

        Returns:
            Formatted message string.
        """
        # Get template content or fallback
        if self.message_template:
            template = self.message_template.content
        elif self.fallback_message:
            template = self.fallback_message
        else:
            template = (
                "Hola {patient_name}, te recordamos tu turno para el {appointment_date} "
                "a las {appointment_time}."
            )

        # Build variables dict
        variables = {
            "patient_name": patient_name,
            "appointment_date": appointment_date,
            "appointment_time": appointment_time,
            "provider_name": provider_name or "",
            "specialty_name": specialty_name or "",
            "institution_name": institution_name or "",
            **extra_vars,
        }

        # Format template
        try:
            return template.format(**variables)
        except KeyError as e:
            # If a placeholder is missing, return template with partial substitution
            for key, value in variables.items():
                template = template.replace(f"{{{key}}}", str(value))
            return template
