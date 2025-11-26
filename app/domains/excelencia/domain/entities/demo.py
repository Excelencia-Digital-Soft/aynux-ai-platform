"""
Demo Entity

Represents a demo request in the Excelencia system.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class DemoStatus(str, Enum):
    """Demo request status"""

    PENDING = "pending"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class DemoType(str, Enum):
    """Types of demos available"""

    GENERAL = "general"
    MODULE_SPECIFIC = "module_specific"
    TECHNICAL = "technical"
    EXECUTIVE = "executive"


@dataclass
class DemoRequest:
    """
    Value object representing a demo request from a potential customer.

    Attributes:
        company_name: Name of the requesting company
        contact_name: Contact person name
        contact_email: Contact email
        contact_phone: Contact phone
        modules_of_interest: List of module codes of interest
        demo_type: Type of demo requested
        notes: Additional notes
    """

    company_name: str
    contact_name: str
    contact_email: str
    contact_phone: str | None = None
    modules_of_interest: list[str] = field(default_factory=list)
    demo_type: DemoType = DemoType.GENERAL
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "company_name": self.company_name,
            "contact_name": self.contact_name,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "modules_of_interest": self.modules_of_interest,
            "demo_type": self.demo_type.value,
            "notes": self.notes,
        }


@dataclass
class Demo:
    """
    Domain entity representing a scheduled demo.

    Attributes:
        id: Unique identifier
        request: The original demo request
        scheduled_at: Scheduled date and time
        duration_minutes: Demo duration in minutes
        status: Current status
        assigned_to: Sales rep assigned
        meeting_link: Virtual meeting link
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    id: str
    request: DemoRequest
    scheduled_at: datetime | None = None
    duration_minutes: int = 60
    status: DemoStatus = DemoStatus.PENDING
    assigned_to: str | None = None
    meeting_link: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def schedule(self, scheduled_at: datetime, assigned_to: str, meeting_link: str | None = None) -> None:
        """Schedule the demo"""
        self.scheduled_at = scheduled_at
        self.assigned_to = assigned_to
        self.meeting_link = meeting_link
        self.status = DemoStatus.SCHEDULED
        self.updated_at = datetime.now(UTC)

    def complete(self) -> None:
        """Mark demo as completed"""
        self.status = DemoStatus.COMPLETED
        self.updated_at = datetime.now(UTC)

    def cancel(self) -> None:
        """Cancel the demo"""
        self.status = DemoStatus.CANCELLED
        self.updated_at = datetime.now(UTC)

    def is_pending(self) -> bool:
        """Check if demo is pending scheduling"""
        return self.status == DemoStatus.PENDING

    def is_scheduled(self) -> bool:
        """Check if demo is scheduled"""
        return self.status == DemoStatus.SCHEDULED

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "request": self.request.to_dict(),
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "duration_minutes": self.duration_minutes,
            "status": self.status.value,
            "assigned_to": self.assigned_to,
            "meeting_link": self.meeting_link,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
