"""
GetModulesUseCase - Obtiene modulos ERP desde PostgreSQL.

Use case para cargar modulos dinamicamente desde la base de datos,
reemplazando el uso de constantes hardcodeadas en los agentes.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.domains.excelencia.application.ports import IModuleRepository
from app.domains.excelencia.domain.entities.module import ERPModule

logger = logging.getLogger(__name__)


@dataclass
class GetModulesResult:
    """Result of GetModulesUseCase."""

    modules: list[ERPModule] = field(default_factory=list)
    modules_by_code: dict[str, ERPModule] = field(default_factory=dict)
    modules_dict: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def count(self) -> int:
        """Number of modules loaded."""
        return len(self.modules)


class GetModulesUseCase:
    """
    Use Case: Get all ERP modules from database.

    Single responsibility: Fetch module data from repository.
    Replaces hardcoded EXCELENCIA_MODULES in agents.
    """

    def __init__(self, repository: IModuleRepository):
        """
        Initialize use case.

        Args:
            repository: Module repository for data access
        """
        self.repository = repository

    async def execute(self, only_available: bool = True) -> GetModulesResult:
        """
        Get all modules from database.

        Args:
            only_available: If True, only return active/beta modules

        Returns:
            GetModulesResult with modules in various formats
        """
        try:
            all_modules = await self.repository.get_all()

            # Filter if requested
            if only_available:
                modules = [m for m in all_modules if m.is_available()]
            else:
                modules = all_modules

            # Build lookup dictionaries
            modules_by_code = {m.code: m for m in modules}

            # Build legacy-compatible dict format for agents
            modules_dict: dict[str, dict[str, Any]] = {}
            for module in modules:
                modules_dict[module.code] = {
                    "name": module.name,
                    "description": module.description,
                    "features": module.features,
                    "target": module.category.value,
                    "status": module.status.value,
                    "pricing_tier": module.pricing_tier,
                }

            logger.info(f"Loaded {len(modules)} ERP modules from database")

            return GetModulesResult(
                modules=modules,
                modules_by_code=modules_by_code,
                modules_dict=modules_dict,
            )

        except Exception as e:
            logger.error(f"Error loading modules from database: {e}")
            raise

    async def get_by_code(self, code: str) -> ERPModule | None:
        """
        Get a specific module by code.

        Args:
            code: Module code (e.g., 'HC-001')

        Returns:
            ERPModule if found, None otherwise
        """
        return await self.repository.get_by_code(code)

    async def search_by_name(self, query: str) -> list[ERPModule]:
        """
        Search modules by name (case-insensitive).

        Args:
            query: Search query

        Returns:
            List of matching modules
        """
        result = await self.execute(only_available=True)
        query_lower = query.lower()

        matches = []
        for module in result.modules:
            if query_lower in module.name.lower():
                matches.append(module)
            elif query_lower in module.description.lower():
                matches.append(module)

        return matches
