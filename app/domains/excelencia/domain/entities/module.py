"""
ERPModule Entity

Represents an ERP module in the Excelencia system.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ModuleCategory(str, Enum):
    """Categories of ERP modules"""

    FINANCE = "finance"
    INVENTORY = "inventory"
    SALES = "sales"
    PURCHASING = "purchasing"
    HR = "hr"
    PRODUCTION = "production"
    CRM = "crm"
    REPORTING = "reporting"


class ModuleStatus(str, Enum):
    """Module availability status"""

    ACTIVE = "active"
    BETA = "beta"
    COMING_SOON = "coming_soon"
    DEPRECATED = "deprecated"


@dataclass
class ERPModule:
    """
    Domain entity representing an ERP module.

    Attributes:
        id: Unique identifier
        code: Module code (e.g., 'FIN-001')
        name: Display name
        description: Module description
        category: Module category
        status: Availability status
        features: List of module features
        pricing_tier: Pricing tier name
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    id: str
    code: str
    name: str
    description: str
    category: ModuleCategory
    status: ModuleStatus = ModuleStatus.ACTIVE
    features: list[str] = field(default_factory=list)
    pricing_tier: str = "standard"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_available(self) -> bool:
        """Check if module is available for demos"""
        return self.status in (ModuleStatus.ACTIVE, ModuleStatus.BETA)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "status": self.status.value,
            "features": self.features,
            "pricing_tier": self.pricing_tier,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ERPModule":
        """Create from dictionary"""
        return cls(
            id=data["id"],
            code=data["code"],
            name=data["name"],
            description=data["description"],
            category=ModuleCategory(data["category"]),
            status=ModuleStatus(data.get("status", "active")),
            features=data.get("features", []),
            pricing_tier=data.get("pricing_tier", "standard"),
        )
