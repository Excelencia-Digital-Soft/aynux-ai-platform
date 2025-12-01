"""
Excelencia Admin API Schemas

Pydantic schemas for Excelencia admin CRUD operations.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


# ============================================================================
# Module Schemas
# ============================================================================


class ModuleCategoryEnum(str, Enum):
    """Module category options."""

    FINANCE = "finance"
    INVENTORY = "inventory"
    SALES = "sales"
    PURCHASING = "purchasing"
    HR = "hr"
    PRODUCTION = "production"
    CRM = "crm"
    REPORTING = "reporting"
    HEALTHCARE = "healthcare"
    HOSPITALITY = "hospitality"


class ModuleStatusEnum(str, Enum):
    """Module status options."""

    ACTIVE = "active"
    BETA = "beta"
    COMING_SOON = "coming_soon"
    DEPRECATED = "deprecated"


class ModuleCreate(BaseModel):
    """Schema for creating a new module."""

    code: str = Field(..., min_length=1, max_length=50, description="Unique module code (e.g., 'FIN-001')")
    name: str = Field(..., min_length=1, max_length=100, description="Module display name")
    description: str | None = Field(None, max_length=2000, description="Module description")
    category: ModuleCategoryEnum = Field(..., description="Module category")
    status: ModuleStatusEnum = Field(default=ModuleStatusEnum.ACTIVE, description="Module status")
    features: list[str] = Field(default_factory=list, description="List of module features")
    pricing_tier: str = Field(default="standard", description="Pricing tier (standard, premium, enterprise)")


class ModuleUpdate(BaseModel):
    """Schema for updating a module. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=2000)
    category: ModuleCategoryEnum | None = None
    status: ModuleStatusEnum | None = None
    features: list[str] | None = None
    pricing_tier: str | None = None


class ModuleResponse(BaseModel):
    """Schema for module response."""

    id: str
    code: str
    name: str
    description: str
    category: str
    status: str
    features: list[str]
    pricing_tier: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModuleListResponse(BaseModel):
    """Schema for paginated module list."""

    modules: list[ModuleResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ============================================================================
# Demo Schemas
# ============================================================================


class DemoStatusEnum(str, Enum):
    """Demo status options."""

    PENDING = "pending"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class DemoTypeEnum(str, Enum):
    """Demo type options."""

    GENERAL = "general"
    MODULE_SPECIFIC = "module_specific"
    TECHNICAL = "technical"
    EXECUTIVE = "executive"


class DemoUpdate(BaseModel):
    """Schema for full demo update."""

    company_name: str | None = Field(None, min_length=1, max_length=200)
    contact_name: str | None = Field(None, min_length=1, max_length=200)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(None, max_length=50)
    modules_of_interest: list[str] | None = None
    demo_type: DemoTypeEnum | None = None
    request_notes: str | None = None
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(None, ge=15, le=480)
    assigned_to: str | None = Field(None, max_length=200)
    meeting_link: str | None = Field(None, max_length=500)
    status: DemoStatusEnum | None = None


class DemoStatusUpdate(BaseModel):
    """Schema for updating demo status only."""

    status: DemoStatusEnum = Field(..., description="New demo status")
    notes: str | None = Field(None, max_length=1000, description="Status change notes")


class DemoSchedule(BaseModel):
    """Schema for scheduling a demo."""

    scheduled_at: datetime = Field(..., description="Scheduled date and time")
    duration_minutes: int = Field(default=60, ge=15, le=480, description="Demo duration in minutes")
    assigned_to: str = Field(..., min_length=1, max_length=200, description="Sales rep assigned")
    meeting_link: str | None = Field(None, max_length=500, description="Virtual meeting URL")


class DemoAssign(BaseModel):
    """Schema for assigning a demo to a sales rep."""

    assigned_to: str = Field(..., min_length=1, max_length=200, description="Sales rep to assign")


class DemoResponse(BaseModel):
    """Schema for demo response."""

    id: str
    company_name: str
    contact_name: str
    contact_email: str
    contact_phone: str | None
    modules_of_interest: list[str]
    demo_type: str
    request_notes: str | None
    scheduled_at: datetime | None
    duration_minutes: int
    status: str
    assigned_to: str | None
    meeting_link: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DemoListResponse(BaseModel):
    """Schema for paginated demo list."""

    demos: list[DemoResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ============================================================================
# Common Schemas
# ============================================================================


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
    success: bool
    details: dict | None = None


class ErrorResponse(BaseModel):
    """Error response schema."""

    detail: str
    error_code: str | None = None
