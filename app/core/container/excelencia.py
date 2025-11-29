"""
Excelencia Domain Container.

Single Responsibility: Wire all Excelencia domain dependencies.
"""

import logging
from typing import TYPE_CHECKING

from app.domains.excelencia.application.use_cases import (
    ScheduleDemoUseCase,
    ShowModulesUseCase,
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

    def create_show_modules_use_case(self) -> ShowModulesUseCase:
        """Create ShowModulesUseCase."""
        return ShowModulesUseCase()

    def create_schedule_demo_use_case(self) -> ScheduleDemoUseCase:
        """Create ScheduleDemoUseCase."""
        return ScheduleDemoUseCase()
