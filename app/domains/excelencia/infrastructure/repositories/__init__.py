"""
Excelencia Infrastructure Repositories

Concrete implementations of repository interfaces.
"""

from app.domains.excelencia.infrastructure.repositories.demo_repository import (
    InMemoryDemoRepository,
)
from app.domains.excelencia.infrastructure.repositories.module_repository import (
    InMemoryModuleRepository,
)

__all__ = [
    "InMemoryDemoRepository",
    "InMemoryModuleRepository",
]
