"""
Excelencia Infrastructure Repositories

SQLAlchemy implementations of repository interfaces.
"""

from app.domains.excelencia.infrastructure.repositories.demo_repository import (
    SQLAlchemyDemoRepository,
    InMemoryDemoRepository,  # Backward compatibility alias
)
from app.domains.excelencia.infrastructure.repositories.module_repository import (
    SQLAlchemyModuleRepository,
    InMemoryModuleRepository,  # Backward compatibility alias
)

__all__ = [
    "SQLAlchemyDemoRepository",
    "SQLAlchemyModuleRepository",
    # Backward compatibility aliases
    "InMemoryDemoRepository",
    "InMemoryModuleRepository",
]
