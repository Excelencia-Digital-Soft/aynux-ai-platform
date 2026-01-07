"""
Domain Pydantic schemas for API request/response validation.

Provides schemas for:
- Creating new domains
- Updating existing domains
- API response serialization
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DomainBase(BaseModel):
    """Base domain schema with common fields."""

    domain_key: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^[a-z_]+$",
        description="Unique domain identifier (lowercase with underscores only)",
        examples=["excelencia", "pharmacy", "e_commerce"],
    )
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable display name",
        examples=["Excelencia", "Farmacia", "E-commerce"],
    )
    description: str | None = Field(
        None,
        max_length=1000,
        description="Domain description and purpose",
    )
    icon: str | None = Field(
        None,
        max_length=100,
        description="PrimeVue icon class (e.g., 'pi-building')",
        examples=["pi-building", "pi-heart", "pi-shopping-cart"],
    )
    color: str | None = Field(
        None,
        max_length=50,
        description="Tag severity color for UI",
        examples=["info", "success", "warn", "help", "secondary"],
    )
    enabled: bool = Field(
        True,
        description="Whether domain is available for selection",
    )
    sort_order: int = Field(
        0,
        ge=0,
        description="Display order in dropdowns (lower = first)",
    )


class DomainCreate(DomainBase):
    """Schema for creating a new domain."""

    pass


class DomainUpdate(BaseModel):
    """Schema for updating an existing domain (all fields optional)."""

    display_name: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description="Human-readable display name",
    )
    description: str | None = Field(
        None,
        max_length=1000,
        description="Domain description and purpose",
    )
    icon: str | None = Field(
        None,
        max_length=100,
        description="PrimeVue icon class",
    )
    color: str | None = Field(
        None,
        max_length=50,
        description="Tag severity color",
    )
    enabled: bool | None = Field(
        None,
        description="Whether domain is available for selection",
    )
    sort_order: int | None = Field(
        None,
        ge=0,
        description="Display order in dropdowns",
    )


class DomainResponse(DomainBase):
    """Schema for domain API responses."""

    id: UUID = Field(..., description="Unique domain identifier")

    model_config = ConfigDict(from_attributes=True)


class DomainListResponse(BaseModel):
    """Schema for domain list API response."""

    domains: list[DomainResponse] = Field(
        ...,
        description="List of domains",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total count of domains",
    )
