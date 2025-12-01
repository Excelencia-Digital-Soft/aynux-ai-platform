"""
Excelencia Admin Use Cases

CRUD operations for modules and demos.
"""

from app.domains.excelencia.application.use_cases.admin.create_module_use_case import (
    CreateModuleUseCase,
)
from app.domains.excelencia.application.use_cases.admin.delete_module_use_case import (
    DeleteModuleUseCase,
)
from app.domains.excelencia.application.use_cases.admin.list_demos_use_case import (
    ListDemosUseCase,
)
from app.domains.excelencia.application.use_cases.admin.list_modules_use_case import (
    ListModulesUseCase,
)
from app.domains.excelencia.application.use_cases.admin.schedule_demo_use_case import (
    ScheduleDemoAdminUseCase,
)
from app.domains.excelencia.application.use_cases.admin.update_demo_status_use_case import (
    UpdateDemoStatusUseCase,
)
from app.domains.excelencia.application.use_cases.admin.update_demo_use_case import (
    UpdateDemoUseCase,
)
from app.domains.excelencia.application.use_cases.admin.update_module_use_case import (
    UpdateModuleUseCase,
)

__all__ = [
    "ListModulesUseCase",
    "CreateModuleUseCase",
    "UpdateModuleUseCase",
    "DeleteModuleUseCase",
    "ListDemosUseCase",
    "UpdateDemoUseCase",
    "UpdateDemoStatusUseCase",
    "ScheduleDemoAdminUseCase",
]
