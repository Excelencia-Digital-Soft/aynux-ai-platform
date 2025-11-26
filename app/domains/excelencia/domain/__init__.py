"""
Excelencia Domain Layer

Core domain for the Excelencia ERP system information and support.
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
    SupportPriority,
    SupportTicketStatus,
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
    "SupportTicketStatus",
    "SupportPriority",
    "LicenseType",
]
