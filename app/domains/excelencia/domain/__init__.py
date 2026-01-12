"""
Excelencia Domain Layer

Core domain for the Excelencia Software system information and support.
"""

from app.domains.excelencia.domain.entities import Demo, DemoRequest, ERPModule
from app.domains.excelencia.domain.services import (
    DemoSchedulingService,
    IDemoRepository,
    IModuleRepository,
    ModuleService,
)
from app.domains.excelencia.domain.value_objects import (
    LicenseType,
    ModuleType,
)

__all__ = [
    # Entities
    "Demo",
    "DemoRequest",
    "ERPModule",
    # Services
    "DemoSchedulingService",
    "ModuleService",
    # Interfaces
    "IDemoRepository",
    "IModuleRepository",
    # Value Objects
    "ModuleType",
    "LicenseType",
]
