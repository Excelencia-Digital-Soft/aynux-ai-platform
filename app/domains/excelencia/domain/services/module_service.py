"""
Module Service

Domain service for ERP module business logic.
"""

from typing import Protocol

from app.domains.excelencia.domain.entities.module import ERPModule, ModuleCategory, ModuleStatus


class IModuleRepository(Protocol):
    """Interface for module repository"""

    async def get_all(self) -> list[ERPModule]: ...
    async def get_by_id(self, module_id: str) -> ERPModule | None: ...
    async def get_by_category(self, category: ModuleCategory) -> list[ERPModule]: ...
    async def get_by_code(self, code: str) -> ERPModule | None: ...


class ModuleService:
    """
    Domain service for module-related business logic.

    Single Responsibility: Handle module queries and filtering.
    """

    def __init__(self, repository: IModuleRepository):
        self._repository = repository

    async def get_all_modules(self) -> list[ERPModule]:
        """Get all available modules"""
        return await self._repository.get_all()

    async def get_available_modules(self) -> list[ERPModule]:
        """Get only modules available for demos"""
        modules = await self._repository.get_all()
        return [m for m in modules if m.is_available()]

    async def get_modules_by_category(self, category: ModuleCategory) -> list[ERPModule]:
        """Get modules by category"""
        return await self._repository.get_by_category(category)

    async def get_module_by_code(self, code: str) -> ERPModule | None:
        """Get a specific module by code"""
        return await self._repository.get_by_code(code)

    async def search_modules(self, query: str) -> list[ERPModule]:
        """Search modules by name or description"""
        modules = await self._repository.get_all()
        query_lower = query.lower()
        return [
            m
            for m in modules
            if query_lower in m.name.lower() or query_lower in m.description.lower()
        ]

    def get_module_summary(self, modules: list[ERPModule]) -> str:
        """Generate a summary of modules for display"""
        if not modules:
            return "No hay modulos disponibles en este momento."

        lines = ["Modulos disponibles de Excelencia ERP:", ""]
        for module in modules:
            status_icon = "✅" if module.status == ModuleStatus.ACTIVE else "🔄"
            lines.append(f"{status_icon} **{module.name}** ({module.code})")
            lines.append(f"   {module.description}")
            if module.features:
                lines.append(f"   Caracteristicas: {', '.join(module.features[:3])}")
            lines.append("")

        return "\n".join(lines)
