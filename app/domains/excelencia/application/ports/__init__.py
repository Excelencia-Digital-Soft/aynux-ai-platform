"""
Excelencia Application Ports

Interface definitions (ports) for the Excelencia domain.
Uses Protocol for structural typing.
"""

from datetime import datetime
from typing import Protocol, runtime_checkable

from app.domains.excelencia.domain.entities.demo import Demo, DemoStatus
from app.domains.excelencia.domain.entities.module import ERPModule, ModuleCategory


@runtime_checkable
class IModuleRepository(Protocol):
    """
    Interface for module repository.

    Defines the contract for module data access.
    """

    async def get_all(self) -> list[ERPModule]:
        """Get all modules"""
        ...

    async def get_by_id(self, module_id: str) -> ERPModule | None:
        """Get module by ID"""
        ...

    async def get_by_code(self, code: str) -> ERPModule | None:
        """Get module by code"""
        ...

    async def get_by_category(self, category: ModuleCategory) -> list[ERPModule]:
        """Get modules by category"""
        ...

    async def save(self, module: ERPModule) -> ERPModule:
        """Save a module"""
        ...

    async def delete(self, module_id: str) -> bool:
        """Delete a module"""
        ...


@runtime_checkable
class IDemoRepository(Protocol):
    """
    Interface for demo repository.

    Defines the contract for demo data access.
    """

    async def save(self, demo: Demo) -> Demo:
        """Save a demo"""
        ...

    async def get_by_id(self, demo_id: str) -> Demo | None:
        """Get demo by ID"""
        ...

    async def get_pending(self) -> list[Demo]:
        """Get all pending demos"""
        ...

    async def get_by_status(self, status: DemoStatus) -> list[Demo]:
        """Get demos by status"""
        ...

    async def get_by_date_range(self, start: datetime, end: datetime) -> list[Demo]:
        """Get demos in date range"""
        ...

    async def delete(self, demo_id: str) -> bool:
        """Delete a demo"""
        ...

    async def get_all(self) -> list[Demo]:
        """Get all demos"""
        ...

    async def get_by_company(self, company_name: str) -> list[Demo]:
        """Get demos by company name"""
        ...


__all__ = [
    "IModuleRepository",
    "IDemoRepository",
]
