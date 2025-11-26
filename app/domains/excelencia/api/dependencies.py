"""
Excelencia API Dependencies

FastAPI dependencies for the Excelencia domain.
"""

from app.core.container import DependencyContainer
from app.domains.excelencia.application.use_cases import (
    ScheduleDemoUseCase,
    ShowModulesUseCase,
)


def get_container() -> DependencyContainer:
    """Get dependency container instance."""
    return DependencyContainer()


def get_show_modules_use_case() -> ShowModulesUseCase:
    """Get ShowModulesUseCase instance."""
    container = get_container()
    return container.create_show_modules_use_case()


def get_schedule_demo_use_case() -> ScheduleDemoUseCase:
    """Get ScheduleDemoUseCase instance."""
    container = get_container()
    return container.create_schedule_demo_use_case()


__all__ = [
    "get_container",
    "get_show_modules_use_case",
    "get_schedule_demo_use_case",
]
