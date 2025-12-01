"""
Create Module Use Case

Creates a new ERP module.
"""

import logging
from datetime import UTC, datetime

from app.domains.excelencia.application.ports import IModuleRepository
from app.domains.excelencia.domain.entities.module import (
    ERPModule,
    ModuleCategory,
    ModuleStatus,
)

logger = logging.getLogger(__name__)


class CreateModuleUseCase:
    """
    Use Case: Create a new ERP module.

    Single Responsibility: Validate and persist new module.
    """

    def __init__(self, repository: IModuleRepository):
        """Initialize with repository."""
        self.repository = repository

    async def execute(
        self,
        code: str,
        name: str,
        category: str,
        description: str | None = None,
        status: str = "active",
        features: list[str] | None = None,
        pricing_tier: str = "standard",
    ) -> dict:
        """
        Execute the use case.

        Args:
            code: Unique module code
            name: Display name
            category: Module category
            description: Module description
            status: Module status
            features: List of features
            pricing_tier: Pricing tier

        Returns:
            Created module as dict

        Raises:
            ValueError: If code already exists or invalid data
        """
        logger.info(f"Creating module: code={code}, name={name}")

        # Check if code already exists
        existing = await self.repository.get_by_code(code)
        if existing:
            raise ValueError(f"Module with code '{code}' already exists")

        # Validate enums
        try:
            cat_enum = ModuleCategory(category)
        except ValueError as e:
            raise ValueError(f"Invalid category: {category}") from e

        try:
            status_enum = ModuleStatus(status)
        except ValueError as e:
            raise ValueError(f"Invalid status: {status}") from e

        # Create entity
        now = datetime.now(UTC)
        module = ERPModule(
            id="",  # Will be assigned by DB
            code=code,
            name=name,
            description=description or "",
            category=cat_enum,
            status=status_enum,
            features=features or [],
            pricing_tier=pricing_tier,
            created_at=now,
            updated_at=now,
        )

        # Persist
        saved_module = await self.repository.save(module)
        logger.info(f"Module created: {saved_module.id}")

        return saved_module.to_dict()
