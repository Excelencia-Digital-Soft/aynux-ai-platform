"""
Excelencia Application DTOs

Data Transfer Objects for the Excelencia domain.
"""

from dataclasses import dataclass, field
from datetime import datetime


# ==================== Module DTOs ====================


@dataclass
class ModuleDTO:
    """Module data transfer object"""

    id: str
    code: str
    name: str
    description: str
    category: str
    status: str
    features: list[str]
    pricing_tier: str


@dataclass
class ShowModulesRequest:
    """Request for showing modules"""

    category: str | None = None
    include_beta: bool = True
    search_query: str | None = None


@dataclass
class ShowModulesResponse:
    """Response with module list"""

    modules: list[ModuleDTO]
    total_count: int
    category_filter: str | None = None


# ==================== Demo DTOs ====================


@dataclass
class ScheduleDemoRequest:
    """Request to schedule a demo"""

    company_name: str
    contact_name: str
    contact_email: str
    contact_phone: str | None = None
    modules_of_interest: list[str] = field(default_factory=list)
    demo_type: str = "general"
    notes: str = ""
    preferred_date: datetime | None = None


@dataclass
class ScheduleDemoResponse:
    """Response after scheduling a demo"""

    demo_id: str
    status: str
    scheduled_at: datetime | None
    confirmation_message: str
    meeting_link: str | None = None


@dataclass
class DemoDTO:
    """Demo data transfer object"""

    id: str
    company_name: str
    contact_name: str
    contact_email: str
    status: str
    scheduled_at: datetime | None
    duration_minutes: int
    modules_of_interest: list[str]


@dataclass
class GetPendingDemosResponse:
    """Response with pending demos"""

    demos: list[DemoDTO]
    total_count: int


__all__ = [
    # Module DTOs
    "ModuleDTO",
    "ShowModulesRequest",
    "ShowModulesResponse",
    # Demo DTOs
    "ScheduleDemoRequest",
    "ScheduleDemoResponse",
    "DemoDTO",
    "GetPendingDemosResponse",
]
