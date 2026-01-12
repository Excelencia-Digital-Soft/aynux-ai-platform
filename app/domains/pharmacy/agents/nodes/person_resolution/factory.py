"""Dependency injection factory for PersonResolution components."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.domains.pharmacy.agents.nodes.person_resolution.handlers.account_selection_handler import (
    AccountSelectionHandler,
)
from app.domains.pharmacy.agents.nodes.person_resolution.handlers.error_handler import (
    ErrorHandler,
)
from app.domains.pharmacy.agents.nodes.person_resolution.handlers.escalation_handler import (
    EscalationHandler,
)
from app.domains.pharmacy.agents.nodes.person_resolution.handlers.identifier_flow_handler import (
    IdentifierFlowHandler,
)
from app.domains.pharmacy.agents.nodes.person_resolution.handlers.name_verification_handler import (
    NameVerificationHandler,
)
from app.domains.pharmacy.agents.nodes.person_resolution.handlers.own_or_other_handler import (
    OwnOrOtherHandler,
)
from app.domains.pharmacy.agents.nodes.person_resolution.handlers.welcome_flow_handler import (
    WelcomeFlowHandler,
)
from app.domains.pharmacy.agents.nodes.person_resolution.services.payment_state_service import (
    PaymentStateService,
)
from app.domains.pharmacy.agents.nodes.person_resolution.services.person_identification_service import (
    PersonIdentificationService,
)
from app.domains.pharmacy.agents.nodes.person_resolution.services.state_management_service import (
    StateManagementService,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.clients.plex_client import PlexClient


class PersonResolutionFactory:
    """
    Factory for creating PersonResolution dependencies.

    Supports lazy initialization and dependency injection.
    """

    def __init__(
        self,
        plex_client: PlexClient | None = None,
        db_session: AsyncSession | None = None,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize factory with optional pre-configured dependencies.

        Args:
            plex_client: Optional PlexClient instance
            db_session: Optional database session
            config: Optional configuration dictionary
        """
        self._plex_client = plex_client
        self._db_session = db_session
        self._config = config or {}

        # Lazy-initialized services
        self._identification_service: PersonIdentificationService | None = None
        self._state_service: StateManagementService | None = None
        self._payment_service: PaymentStateService | None = None

        # Lazy-initialized handlers
        self._welcome_handler: WelcomeFlowHandler | None = None
        self._identifier_handler: IdentifierFlowHandler | None = None
        self._name_handler: NameVerificationHandler | None = None
        self._own_other_handler: OwnOrOtherHandler | None = None
        self._escalation_handler: EscalationHandler | None = None
        self._error_handler: ErrorHandler | None = None
        self._account_selection_handler: AccountSelectionHandler | None = None

    # =========================================================================
    # Services
    # =========================================================================

    def get_identification_service(self) -> PersonIdentificationService:
        """Get or create PersonIdentificationService."""
        if self._identification_service is None:
            self._identification_service = PersonIdentificationService(self._plex_client)
        return self._identification_service

    def get_state_service(self) -> StateManagementService:
        """Get or create StateManagementService."""
        if self._state_service is None:
            self._state_service = StateManagementService()
        return self._state_service

    def get_payment_service(self) -> PaymentStateService:
        """Get or create PaymentStateService."""
        if self._payment_service is None:
            self._payment_service = PaymentStateService()
        return self._payment_service

    # =========================================================================
    # Handlers
    # =========================================================================

    def get_welcome_handler(self) -> WelcomeFlowHandler:
        """Get or create WelcomeFlowHandler."""
        if self._welcome_handler is None:
            self._welcome_handler = WelcomeFlowHandler()
        return self._welcome_handler

    def get_identifier_handler(self) -> IdentifierFlowHandler:
        """Get or create IdentifierFlowHandler."""
        if self._identifier_handler is None:
            self._identifier_handler = IdentifierFlowHandler(
                identification_service=self.get_identification_service()
            )
        return self._identifier_handler

    def get_name_handler(self) -> NameVerificationHandler:
        """Get or create NameVerificationHandler."""
        if self._name_handler is None:
            self._name_handler = NameVerificationHandler(
                identification_service=self.get_identification_service()
            )
        return self._name_handler

    def get_own_other_handler(self) -> OwnOrOtherHandler:
        """Get or create OwnOrOtherHandler."""
        if self._own_other_handler is None:
            self._own_other_handler = OwnOrOtherHandler()
        return self._own_other_handler

    def get_escalation_handler(self) -> EscalationHandler:
        """Get or create EscalationHandler."""
        if self._escalation_handler is None:
            self._escalation_handler = EscalationHandler()
        return self._escalation_handler

    def get_error_handler(self) -> ErrorHandler:
        """Get or create ErrorHandler."""
        if self._error_handler is None:
            self._error_handler = ErrorHandler()
        return self._error_handler

    def get_account_selection_handler(self) -> AccountSelectionHandler:
        """Get or create AccountSelectionHandler."""
        if self._account_selection_handler is None:
            self._account_selection_handler = AccountSelectionHandler()
        return self._account_selection_handler


__all__ = ["PersonResolutionFactory"]
