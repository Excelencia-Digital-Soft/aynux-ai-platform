"""
Customer Identification Node

Pharmacy domain node for identifying Plex customer from WhatsApp context.
Orchestrates the identification flow by delegating to specialized handlers.

Refactored to follow Single Responsibility Principle:
- Node: Orchestration only
- PharmacyConfigService: Config loading
- PharmacyIntentAnalyzer: Intent analysis
- DisambiguationHandler: Disambiguation flow
- DocumentInputHandler: Document input flow
- IdentificationResponseHandler: Response formatting
- GreetingManager: Greeting state management
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.core.agents import BaseAgent
from app.domains.pharmacy.agents.intent_analyzer import PharmacyIntentAnalyzer
from app.domains.pharmacy.agents.nodes.handlers.disambiguation_handler import (
    DisambiguationHandler,
)
from app.domains.pharmacy.agents.nodes.handlers.document_input_handler import (
    DocumentInputHandler,
)
from app.domains.pharmacy.agents.nodes.handlers.identification_response_handler import (
    IdentificationResponseHandler,
)
from app.domains.pharmacy.agents.nodes.identification_constants import (
    OUT_OF_SCOPE_INTENTS,
)
from app.domains.pharmacy.agents.utils.greeting_manager import GreetingManager
from app.domains.pharmacy.application.use_cases.identify_customer import (
    IdentificationStatus,
    IdentifyCustomerRequest,
    IdentifyCustomerUseCase,
)
from app.domains.pharmacy.services.pharmacy_config_service import PharmacyConfigService
from app.prompts.manager import PromptManager

if TYPE_CHECKING:
    from app.clients.plex_client import PlexClient

logger = logging.getLogger(__name__)


class CustomerIdentificationNode(BaseAgent):
    """
    Node for identifying Plex customer from WhatsApp user.

    Orchestration responsibilities only:
    - Route to appropriate handler based on state
    - Coordinate between handlers
    - Manage workflow transitions

    This is the entry point for the pharmacy workflow. It:
    1. Searches for customer by WhatsApp phone number
    2. Handles disambiguation if multiple matches found
    3. Handles document input if phone search fails
    4. Offers registration if customer not found
    """

    def __init__(
        self,
        plex_client: PlexClient | None = None,
        config: dict[str, Any] | None = None,
        config_service: PharmacyConfigService | None = None,
        intent_analyzer: PharmacyIntentAnalyzer | None = None,
        disambiguation_handler: DisambiguationHandler | None = None,
        document_handler: DocumentInputHandler | None = None,
        response_handler: IdentificationResponseHandler | None = None,
        greeting_manager: GreetingManager | None = None,
    ):
        """
        Initialize customer identification node.

        Args:
            plex_client: PlexClient instance for API calls
            config: Node configuration
            config_service: PharmacyConfigService for loading pharmacy config
            intent_analyzer: PharmacyIntentAnalyzer for intent detection
            disambiguation_handler: DisambiguationHandler for disambiguation flow
            document_handler: DocumentInputHandler for document input flow
            response_handler: IdentificationResponseHandler for response formatting
            greeting_manager: GreetingManager for greeting state
        """
        super().__init__("customer_identification_node", config or {})
        self._plex_client = plex_client
        self._use_case: IdentifyCustomerUseCase | None = None

        # Services (lazy initialization)
        self._config_service = config_service
        self._intent_analyzer = intent_analyzer
        self._prompt_manager: PromptManager | None = None
        self._greeting_manager = greeting_manager

        # Handlers (lazy initialization)
        self._disambiguation_handler = disambiguation_handler
        self._document_handler = document_handler
        self._response_handler = response_handler

    def _get_plex_client(self) -> PlexClient:
        """Get or create Plex client."""
        if self._plex_client is None:
            from app.clients.plex_client import PlexClient

            self._plex_client = PlexClient()
        return self._plex_client

    def _get_use_case(self) -> IdentifyCustomerUseCase:
        """Get or create the use case."""
        if self._use_case is None:
            self._use_case = IdentifyCustomerUseCase(self._get_plex_client())
        return self._use_case

    def _get_config_service(self) -> PharmacyConfigService:
        """Get or create config service."""
        if self._config_service is None:
            self._config_service = PharmacyConfigService()
        return self._config_service

    def _get_intent_analyzer(self) -> PharmacyIntentAnalyzer:
        """Get or create intent analyzer."""
        if self._intent_analyzer is None:
            self._intent_analyzer = PharmacyIntentAnalyzer()
        return self._intent_analyzer

    def _get_prompt_manager(self) -> PromptManager:
        """Get or create prompt manager."""
        if self._prompt_manager is None:
            self._prompt_manager = PromptManager()
        return self._prompt_manager

    def _get_greeting_manager(self) -> GreetingManager:
        """Get or create greeting manager."""
        if self._greeting_manager is None:
            self._greeting_manager = GreetingManager()
        return self._greeting_manager

    def _get_response_handler(self) -> IdentificationResponseHandler:
        """Get or create response handler."""
        if self._response_handler is None:
            self._response_handler = IdentificationResponseHandler(
                self._get_prompt_manager(),
                self._get_greeting_manager(),
            )
        return self._response_handler

    def _get_disambiguation_handler(self) -> DisambiguationHandler:
        """Get or create disambiguation handler."""
        if self._disambiguation_handler is None:
            self._disambiguation_handler = DisambiguationHandler(
                self._get_prompt_manager(),
                self._get_greeting_manager(),
            )
        return self._disambiguation_handler

    def _get_document_handler(self) -> DocumentInputHandler:
        """Get or create document handler."""
        if self._document_handler is None:
            self._document_handler = DocumentInputHandler(
                self._get_use_case(),
                self._get_intent_analyzer(),
                self._get_response_handler(),
                self._get_disambiguation_handler(),
                self._get_prompt_manager(),
            )
        return self._document_handler

    async def _ensure_pharmacy_config(
        self,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Ensure pharmacy config is loaded into state.

        Args:
            state_dict: Current state dictionary

        Returns:
            State dictionary with pharmacy config merged
        """
        pharmacy_id = state_dict.get("pharmacy_id")
        pharmacy_name = state_dict.get("pharmacy_name")

        if not pharmacy_name and pharmacy_id:
            logger.info(f"Loading pharmacy config for pharmacy_id={pharmacy_id}")
            config = await self._get_config_service().get_config_dict(pharmacy_id)
            logger.info(f"Loaded pharmacy config: {config}")
            return {**state_dict, **config}

        if not pharmacy_id:
            logger.debug("No pharmacy_id in state, skipping config load")

        return state_dict

    async def _process_internal(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Orchestrate customer identification workflow.

        Args:
            message: User message
            state_dict: Current state dictionary

        Returns:
            State updates
        """
        try:
            # Load pharmacy config if needed
            state_dict = await self._ensure_pharmacy_config(state_dict)

            # Already identified?
            if state_dict.get("customer_identified") and state_dict.get("plex_customer_id"):
                logger.debug("Customer already identified, passing through")
                return {
                    "customer_identified": True,
                    "pharmacy_name": state_dict.get("pharmacy_name"),
                    "pharmacy_phone": state_dict.get("pharmacy_phone"),
                }

            # Route to disambiguation handler
            if state_dict.get("requires_disambiguation"):
                return await self._get_disambiguation_handler().handle_selection(
                    message,
                    state_dict.get("disambiguation_candidates", []),
                    state_dict,
                )

            # Pass through to registration node when awaiting registration data
            # Graph routing in _route_after_identification() handles actual routing
            if state_dict.get("awaiting_registration_data"):
                logger.debug("Passing through to registration node (awaiting_registration_data)")
                return {
                    "awaiting_registration_data": True,
                    "pharmacy_name": state_dict.get("pharmacy_name"),
                    "pharmacy_phone": state_dict.get("pharmacy_phone"),
                }

            # Route to document handler
            if state_dict.get("awaiting_document_input"):
                return await self._get_document_handler().handle(message, state_dict)

            # Auto-detect DNI in message
            if dni := self._get_document_handler().detect_dni_in_message(message):
                logger.info(f"Auto-detected DNI in message: {dni}")
                return await self._get_document_handler().handle(message, state_dict)

            # Initial identification
            return await self._initial_identification(message, state_dict)

        except Exception as e:
            logger.error(f"Error in customer identification: {e}", exc_info=True)
            return self._handle_error(str(e), state_dict)

    async def _initial_identification(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Perform initial customer identification by phone.

        Args:
            message: User message
            state_dict: Current state dictionary

        Returns:
            State updates
        """
        phone = state_dict.get("customer_id") or state_dict.get("user_id")
        response_handler = self._get_response_handler()

        if not phone:
            logger.warning("No phone number available for identification")
            # Check if message is out-of-scope before requesting DNI
            intent_result = await self._get_intent_analyzer().analyze(
                message,
                {"customer_identified": False},
            )
            if intent_result.is_out_of_scope or intent_result.intent in OUT_OF_SCOPE_INTENTS:
                return await response_handler.format_out_of_scope_response(message, state_dict)
            return await response_handler.format_welcome_message(state_dict)

        logger.info(f"Identifying customer by phone: {phone}")

        plex_client = self._get_plex_client()

        async with plex_client:
            response = await self._get_use_case().execute(
                IdentifyCustomerRequest(phone=phone)
            )

        if response.status == IdentificationStatus.IDENTIFIED:
            customer = response.customer
            if customer is None:
                return self._handle_error("Customer object is None", state_dict)

            logger.info(f"Customer identified: {customer}")
            return response_handler.format_identified_customer(
                customer,
                phone,
                state_dict,
                greeting_type="welcome",
            )

        elif response.status == IdentificationStatus.DISAMBIGUATION_REQUIRED:
            logger.info(f"Disambiguation required: {len(response.candidates or [])} candidates")
            return self._get_disambiguation_handler().format_disambiguation_request(
                response.candidates or [], state_dict
            )

        elif response.status == IdentificationStatus.NOT_FOUND:
            # Check if message is out-of-scope before requesting DNI
            intent_result = await self._get_intent_analyzer().analyze(
                message,
                {"customer_identified": False},
            )
            if intent_result.is_out_of_scope or intent_result.intent in OUT_OF_SCOPE_INTENTS:
                logger.info(f"Out-of-scope intent detected: {intent_result.intent}")
                return await response_handler.format_out_of_scope_response(message, state_dict)

            logger.info("Customer not found by phone, requesting document")
            return await response_handler.format_welcome_message(state_dict)

        else:
            return self._handle_error(
                response.error or "Identification failed",
                state_dict,
            )

    def _handle_error(self, error: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Handle processing error.

        Args:
            error: Error message
            state_dict: Current state dictionary

        Returns:
            State updates with error handling
        """
        import traceback

        tb = traceback.format_exc()
        logger.error(f"Customer identification error: {error}")
        logger.error(f"Full traceback:\n{tb}")
        error_count = state_dict.get("error_count", 0) + 1

        if error_count >= state_dict.get("max_errors", 3):
            return {
                "messages": [
                    {
                        "role": "assistant",
                        "content": (
                            "Tuve varios problemas intentando identificarte. "
                            "Por favor contacta a la farmacia directamente."
                        ),
                    }
                ],
                "error_count": error_count,
                "is_complete": True,
                "requires_human": True,
            }

        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "Tuve un problema identificando tu cuenta. "
                        "Por favor intenta de nuevo o ingresa tu DNI."
                    ),
                }
            ],
            "error_count": error_count,
            "awaiting_document_input": True,
        }
