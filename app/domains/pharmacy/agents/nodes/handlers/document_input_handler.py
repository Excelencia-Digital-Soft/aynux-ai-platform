"""
Document Input Handler

Handles document/DNI input validation and customer search.
Single responsibility: document input processing for identification.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.domains.pharmacy.agents.intent_analyzer import PharmacyIntentAnalyzer
from app.domains.pharmacy.agents.nodes.handlers.base_handler import BasePharmacyHandler
from app.domains.pharmacy.agents.nodes.handlers.disambiguation_handler import (
    DisambiguationHandler,
)
from app.domains.pharmacy.agents.nodes.handlers.identification_response_handler import (
    IdentificationResponseHandler,
)
from app.domains.pharmacy.agents.nodes.identification_constants import (
    DNI_PATTERNS,
    MIN_DOCUMENT_LENGTH,
    OUT_OF_SCOPE_INTENTS,
)
from app.domains.pharmacy.application.use_cases.identify_customer import (
    IdentificationStatus,
    IdentifyCustomerRequest,
    IdentifyCustomerUseCase,
)

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.utils.response_generator import (
        PharmacyResponseGenerator,
    )

logger = logging.getLogger(__name__)


class DocumentInputHandler(BasePharmacyHandler):
    """
    Handler for document input processing.

    Single responsibility: Validate document input, search customer,
    and route to appropriate response.
    """

    def __init__(
        self,
        use_case: IdentifyCustomerUseCase,
        intent_analyzer: PharmacyIntentAnalyzer | None = None,
        response_handler: IdentificationResponseHandler | None = None,
        disambiguation_handler: DisambiguationHandler | None = None,
        response_generator: PharmacyResponseGenerator | None = None,
    ):
        """
        Initialize document input handler.

        Args:
            use_case: IdentifyCustomerUseCase for customer search
            intent_analyzer: PharmacyIntentAnalyzer for intent detection
            response_handler: IdentificationResponseHandler for responses
            disambiguation_handler: DisambiguationHandler for disambiguation
            response_generator: ResponseGenerator for LLM-driven responses
        """
        super().__init__(response_generator)
        self._use_case = use_case
        self._intent_analyzer = intent_analyzer or PharmacyIntentAnalyzer()
        self._response_handler = response_handler or IdentificationResponseHandler(response_generator)
        self._disambiguation_handler = disambiguation_handler or DisambiguationHandler(response_generator)

    def _get_organization_id(self, state: dict[str, Any]) -> UUID:
        """Extract organization_id from state for multi-tenant intent analysis."""
        org_id = state.get("organization_id")
        if org_id is None:
            # Fallback to system org for backward compatibility
            return UUID("00000000-0000-0000-0000-000000000000")
        if isinstance(org_id, UUID):
            return org_id
        try:
            return UUID(str(org_id))
        except (ValueError, TypeError):
            logger.warning(f"Invalid organization_id in state: {org_id}")
            return UUID("00000000-0000-0000-0000-000000000000")

    async def handle(
        self,
        message: str,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process document input and search for customer.

        Args:
            message: User message with document
            state: Current state dictionary

        Returns:
            State update with search result
        """
        # First, try to detect DNI directly in the message
        detected_dni = self.detect_dni_in_message(message)

        # Extract organization_id for multi-tenant intent analysis
        org_id = self._get_organization_id(state)

        # Check intent with proper context
        intent_result = await self._intent_analyzer.analyze(
            message,
            {
                "customer_identified": False,
                "awaiting_document_input": True,
            },
            organization_id=org_id,
        )

        # Handle info_query first - it's PUBLIC data that doesn't require identification
        if intent_result.intent == "info_query":
            logger.info(f"Info query detected while awaiting document: {intent_result.intent}")
            return await self._response_handler.format_info_query_response(message, state)
        # Handle out-of-scope intents
        if intent_result.is_out_of_scope or intent_result.intent in OUT_OF_SCOPE_INTENTS:
            logger.info(f"Out-of-scope detected while awaiting document: {intent_result.intent}")
            return await self._response_handler.format_out_of_scope_response(message, state)

        # If intent is NOT document_input and no DNI detected, remind user we need their document
        # This handles cases like "pagar 5000" where intent is "invoice" but no valid DNI
        if intent_result.intent != "document_input" and not detected_dni:
            logger.info(
                f"Non-document intent '{intent_result.intent}' while awaiting document, "
                "reminding user to provide DNI first"
            )
            return await self._response_handler.format_document_reminder_message(state)

        # Use detected DNI or try to extract from message
        if detected_dni:
            cleaned_doc = detected_dni
        else:
            # Validate document from full message
            is_valid, cleaned_doc = self.validate_document(message)
            if not is_valid:
                return await self._response_handler.format_invalid_document_message(state)

        logger.info(f"Searching customer by document: {cleaned_doc}")

        # Search customer
        response = await self._use_case.execute(
            IdentifyCustomerRequest(document=cleaned_doc)
        )

        phone = state.get("customer_id") or state.get("user_id")

        if response.status == IdentificationStatus.IDENTIFIED:
            customer = response.customer
            if customer is None:
                return await self._response_handler.format_registration_offer(phone, state, cleaned_doc)

            logger.info(f"Customer identified by document: {customer}")
            return self._response_handler.format_identified_customer(
                customer,
                phone,
                state,
                greeting_type="found",
            )

        elif response.status == IdentificationStatus.DISAMBIGUATION_REQUIRED:
            return self._disambiguation_handler.format_disambiguation_request(
                response.candidates or [], state
            )

        else:
            # Not found - offer registration (pass document to skip DNI step)
            logger.info("Customer not found by document, offering registration")
            return await self._response_handler.format_registration_offer(phone, state, cleaned_doc)

    def detect_dni_in_message(self, message: str) -> str | None:
        """
        Detect if message contains a DNI pattern.

        Checks multiple patterns:
        1. Pure digits: "2259863"
        2. Natural language: "mi documento es 2259863", "DNI: 2259863"

        Args:
            message: User message to check

        Returns:
            Extracted DNI or None if not found
        """
        text = message.strip()
        for pattern in DNI_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(1)
        return None

    def validate_document(self, document: str) -> tuple[bool, str]:
        """
        Validate document format.

        Args:
            document: Document string to validate

        Returns:
            Tuple of (is_valid, cleaned_document)
        """
        cleaned_doc = "".join(c for c in document if c.isdigit())

        if not cleaned_doc or len(cleaned_doc) < MIN_DOCUMENT_LENGTH:
            return False, ""

        return True, cleaned_doc
