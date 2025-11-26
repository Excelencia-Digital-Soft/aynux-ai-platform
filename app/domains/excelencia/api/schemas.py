"""
Excelencia API Schemas

Pydantic schemas for API request/response validation.
"""

from datetime import date, time

from pydantic import BaseModel, EmailStr, Field


class ModuleResponse(BaseModel):
    """ERP module response schema."""

    name: str
    description: str
    features: list[str]


class ModulesListResponse(BaseModel):
    """List of ERP modules response schema."""

    modules: list[ModuleResponse]
    total: int


class DemoRequest(BaseModel):
    """Demo scheduling request schema."""

    contact_name: str = Field(..., min_length=2, max_length=100)
    company_name: str = Field(..., min_length=2, max_length=200)
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=20)
    preferred_date: date
    preferred_time: time
    modules_of_interest: list[str] = Field(default_factory=list)
    notes: str | None = None


class DemoResponse(BaseModel):
    """Demo scheduling response schema."""

    success: bool
    message: str
    demo_id: str | None = None
    scheduled_date: date | None = None
    scheduled_time: time | None = None


class AvailableSlotResponse(BaseModel):
    """Available demo slot response schema."""

    date: date
    time: time
    is_available: bool


__all__ = [
    "ModuleResponse",
    "ModulesListResponse",
    "DemoRequest",
    "DemoResponse",
    "AvailableSlotResponse",
]
