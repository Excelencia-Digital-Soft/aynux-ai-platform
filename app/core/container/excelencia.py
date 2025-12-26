"""
Excelencia Domain Container.

Note: Module and Demo functionality has been removed.
Software catalog data is now managed via company_knowledge table.
"""

import logging
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.core.container.base import BaseContainer

logger = logging.getLogger(__name__)


class ExcelenciaContainer:
    """
    Excelencia domain container.

    Note: Module/Demo repositories and use cases have been removed.
    Software catalog is now managed through company_knowledge.
    """

    def __init__(self, base: "BaseContainer"):
        """
        Initialize Excelencia container.

        Args:
            base: BaseContainer with shared singletons
        """
        self._base = base

    def create_support_ticket_use_case(self, db: AsyncSession):
        """
        Create a use case for creating support tickets (legacy).

        Args:
            db: Async database session

        Returns:
            CreateSupportTicketUseCase instance
        """
        from app.domains.excelencia.application.use_cases.support import (
            CreateSupportTicketUseCase,
        )

        return CreateSupportTicketUseCase(db)

    def create_incident_use_case(self, db: AsyncSession):
        """
        Create a use case for creating incidents (new soporte schema).

        Args:
            db: Async database session

        Returns:
            CreateIncidentUseCase instance
        """
        from app.domains.excelencia.application.use_cases.support import (
            CreateIncidentUseCase,
        )

        return CreateIncidentUseCase(db)

    def get_pending_ticket_use_case(self, db: AsyncSession):
        """
        Create a use case for getting pending tickets.

        Args:
            db: Async database session

        Returns:
            GetPendingTicketUseCase instance
        """
        from app.domains.excelencia.application.use_cases.support import (
            GetPendingTicketUseCase,
        )

        return GetPendingTicketUseCase(db)

    def save_pending_ticket_use_case(self, db: AsyncSession):
        """
        Create a use case for saving pending tickets.

        Args:
            db: Async database session

        Returns:
            SavePendingTicketUseCase instance
        """
        from app.domains.excelencia.application.use_cases.support import (
            SavePendingTicketUseCase,
        )

        return SavePendingTicketUseCase(db)
