"""
Excelencia Domain Container.

Single Responsibility: Wire all Excelencia domain dependencies.
"""

import logging
from typing import TYPE_CHECKING

from app.domains.excelencia.application.use_cases import (
    GetModulesUseCase,
    ScheduleDemoUseCase,
    ShowModulesUseCase,
)
from app.domains.excelencia.application.use_cases.admin import (
    CreateModuleUseCase,
    DeleteModuleUseCase,
    ListDemosUseCase,
    ListModulesUseCase,
    ScheduleDemoAdminUseCase,
    UpdateDemoStatusUseCase,
    UpdateDemoUseCase,
    UpdateModuleUseCase,
)
from app.domains.excelencia.infrastructure.repositories import (
    SQLAlchemyDemoRepository,
    SQLAlchemyModuleRepository,
)

if TYPE_CHECKING:
    from app.core.container.base import BaseContainer

logger = logging.getLogger(__name__)


class ExcelenciaContainer:
    """
    Excelencia domain container.

    Single Responsibility: Create Excelencia repositories and use cases.
    """

    def __init__(self, base: "BaseContainer"):
        """
        Initialize Excelencia container.

        Args:
            base: BaseContainer with shared singletons
        """
        self._base = base

    # ==================== REPOSITORIES ====================

    def create_module_repository(self, db) -> SQLAlchemyModuleRepository:
        """Create Module Repository."""
        return SQLAlchemyModuleRepository(session=db)

    def create_demo_repository(self, db) -> SQLAlchemyDemoRepository:
        """Create Demo Repository."""
        return SQLAlchemyDemoRepository(session=db)

    # ==================== USE CASES ====================

    def create_get_modules_use_case(self, db) -> GetModulesUseCase:
        """Create GetModulesUseCase with repository."""
        repository = self.create_module_repository(db)
        return GetModulesUseCase(repository=repository)

    def create_show_modules_use_case(self) -> ShowModulesUseCase:
        """Create ShowModulesUseCase."""
        return ShowModulesUseCase()

    def create_schedule_demo_use_case(self) -> ScheduleDemoUseCase:
        """Create ScheduleDemoUseCase."""
        return ScheduleDemoUseCase()

    # ==================== ADMIN USE CASES ====================

    def create_list_modules_admin_use_case(self, db) -> ListModulesUseCase:
        """Create ListModulesUseCase for admin."""
        repository = self.create_module_repository(db)
        return ListModulesUseCase(repository=repository)

    def create_create_module_use_case(self, db) -> CreateModuleUseCase:
        """Create CreateModuleUseCase."""
        repository = self.create_module_repository(db)
        return CreateModuleUseCase(repository=repository)

    def create_update_module_use_case(self, db) -> UpdateModuleUseCase:
        """Create UpdateModuleUseCase."""
        repository = self.create_module_repository(db)
        return UpdateModuleUseCase(repository=repository)

    def create_delete_module_use_case(self, db) -> DeleteModuleUseCase:
        """Create DeleteModuleUseCase."""
        repository = self.create_module_repository(db)
        return DeleteModuleUseCase(repository=repository)

    def create_list_demos_admin_use_case(self, db) -> ListDemosUseCase:
        """Create ListDemosUseCase for admin."""
        repository = self.create_demo_repository(db)
        return ListDemosUseCase(repository=repository)

    def create_update_demo_use_case(self, db) -> UpdateDemoUseCase:
        """Create UpdateDemoUseCase."""
        repository = self.create_demo_repository(db)
        return UpdateDemoUseCase(repository=repository)

    def create_update_demo_status_use_case(self, db) -> UpdateDemoStatusUseCase:
        """Create UpdateDemoStatusUseCase."""
        repository = self.create_demo_repository(db)
        return UpdateDemoStatusUseCase(repository=repository)

    def create_schedule_demo_admin_use_case(self, db) -> ScheduleDemoAdminUseCase:
        """Create ScheduleDemoAdminUseCase."""
        repository = self.create_demo_repository(db)
        return ScheduleDemoAdminUseCase(repository=repository)
