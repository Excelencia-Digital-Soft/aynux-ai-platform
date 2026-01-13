"""Dependency injection factory for PersonResolution components."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

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
from app.domains.pharmacy.agents.nodes.person_resolution.services.initial_resolution_service import (
    InitialResolutionService,
)
from app.domains.pharmacy.agents.nodes.person_resolution.services.payment_amount_extractor import (
    PaymentAmountExtractor,
)
from app.domains.pharmacy.agents.nodes.person_resolution.services.payment_state_service import (
    PaymentStateService,
)
from app.domains.pharmacy.agents.nodes.person_resolution.services.person_identification_service import (
    PersonIdentificationService,
)
from app.domains.pharmacy.agents.nodes.person_resolution.services.person_registration_service import (
    PersonRegistrationService,
)
from app.domains.pharmacy.agents.nodes.person_resolution.services.response_builder import (
    ResponseBuilder,
)
from app.domains.pharmacy.agents.nodes.person_resolution.services.state_management_service import (
    StateManagementService,
)
from app.domains.pharmacy.agents.nodes.person_resolution.services.workflow_orchestrator import (
    WorkflowOrchestrator,
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
        self._initial_resolution_service: InitialResolutionService | None = None
        self._state_service: StateManagementService | None = None
        self._payment_service: PaymentStateService | None = None
        self._payment_amount_extractor: PaymentAmountExtractor | None = None
        self._person_registration_service: PersonRegistrationService | None = None
        self._response_builder: ResponseBuilder | None = None
        self._workflow_orchestrator: WorkflowOrchestrator | None = None

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

    def get_initial_resolution_service(
        self,
        organization_id: UUID | None = None,
    ) -> InitialResolutionService:
        """Get or create InitialResolutionService.

        Args:
            organization_id: Optional organization UUID from current request state.
                            Takes precedence over config value for multi-tenant support.
        """
        # Use passed organization_id or fall back to config
        resolved_org_id = organization_id or self._config.get("organization_id")

        if self._initial_resolution_service is None:
            self._initial_resolution_service = InitialResolutionService(
                self._db_session,
                resolved_org_id,
            )
        elif resolved_org_id and self._initial_resolution_service._organization_id != resolved_org_id:
            # Re-create service if organization_id changed (multi-tenant request)
            self._initial_resolution_service = InitialResolutionService(
                self._db_session,
                resolved_org_id,
            )
        return self._initial_resolution_service

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

    def get_payment_amount_extractor(self) -> PaymentAmountExtractor:
        """Get or create PaymentAmountExtractor."""
        if self._payment_amount_extractor is None:
            self._payment_amount_extractor = PaymentAmountExtractor()
        return self._payment_amount_extractor

    def get_person_registration_service(self) -> PersonRegistrationService:
        """Get or create PersonRegistrationService."""
        if self._person_registration_service is None:
            self._person_registration_service = PersonRegistrationService(self._db_session)
        return self._person_registration_service

    def get_response_builder(self) -> ResponseBuilder:
        """Get or create ResponseBuilder."""
        if self._response_builder is None:
            self._response_builder = ResponseBuilder(self._db_session)
        return self._response_builder

    def get_workflow_orchestrator(self) -> WorkflowOrchestrator:
        """Get or create WorkflowOrchestrator."""
        if self._workflow_orchestrator is None:
            self._workflow_orchestrator = WorkflowOrchestrator(self)
        return self._workflow_orchestrator

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
