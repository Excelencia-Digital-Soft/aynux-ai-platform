"""
Excelencia Use Cases

Application layer use cases for Excelencia ERP domain.
"""

from app.domains.excelencia.application.use_cases.show_modules import (
    ModuleInfo,
    ShowModulesRequest,
    ShowModulesResponse,
    ShowModulesUseCase,
)
from app.domains.excelencia.application.use_cases.schedule_demo import (
    DemoSlot,
    ScheduledDemo,
    ScheduleDemoRequest,
    ScheduleDemoResponse,
    ScheduleDemoUseCase,
)

__all__ = [
    # Show Modules
    "ModuleInfo",
    "ShowModulesRequest",
    "ShowModulesResponse",
    "ShowModulesUseCase",
    # Schedule Demo
    "DemoSlot",
    "ScheduledDemo",
    "ScheduleDemoRequest",
    "ScheduleDemoResponse",
    "ScheduleDemoUseCase",
]
