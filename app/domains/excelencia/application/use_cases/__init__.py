"""
Excelencia Use Cases

Application layer use cases for Excelencia ERP domain.
"""

from app.domains.excelencia.application.use_cases.get_modules_use_case import (
    GetModulesResult,
    GetModulesUseCase,
)
from app.domains.excelencia.application.use_cases.schedule_demo import (
    DemoSlot,
    ScheduledDemo,
    ScheduleDemoRequest,
    ScheduleDemoResponse,
    ScheduleDemoUseCase,
)
from app.domains.excelencia.application.use_cases.show_modules import (
    ModuleInfo,
    ShowModulesRequest,
    ShowModulesResponse,
    ShowModulesUseCase,
)

__all__ = [
    # Get Modules (from DB)
    "GetModulesResult",
    "GetModulesUseCase",
    # Show Modules (license-based)
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
