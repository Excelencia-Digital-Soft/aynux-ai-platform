"""
Person Validation Node - Validate DNI + Name against PLEX.

Multi-step validation flow:
1. STEP_DNI: Request and validate DNI against PLEX
2. STEP_NAME: Request name and validate with LLM fuzzy matching
3. On success: Register in local DB with 180-day expiration

This node handles both:
- New person registration (phone owner not in PLEX)
- Adding another person for an existing phone owner
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.agents import BaseAgent
from app.core.cache.domain_intent_cache import domain_intent_cache
from app.domains.pharmacy.agents.utils.db_helpers import generate_response
from app.domains.pharmacy.agents.utils.name_matcher import LLMNameMatcher
from app.domains.pharmacy.agents.utils.response_generator import (
    PharmacyResponseGenerator,
    get_response_generator,
)
from app.domains.pharmacy.infrastructure.repositories.registered_person_repository import (
    RegisteredPersonRepository,
)
from app.models.db.tenancy.registered_person import RegisteredPerson

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.clients.plex_client import PlexClient

logger = logging.getLogger(__name__)


class PersonValidationNode(BaseAgent):
    """
    Node for validating a new person by DNI + LLM name matching.

    Flow:
    1. Request DNI (if not provided)
    2. Validate DNI exists in PLEX
    3. Request name
    4. Use LLM to fuzzy match name against PLEX record
    5. If match > threshold: Register in local DB with 180-day expiry
    6. Proceed to debt check
    """

    # Validation steps
    STEP_DNI = "dni"
    STEP_NAME = "name"
    STEP_CONFIRM = "confirm"

    # Name match threshold
    NAME_MATCH_THRESHOLD = 0.75

    def __init__(
        self,
        plex_client: PlexClient | None = None,
        db_session: AsyncSession | None = None,
        config: dict[str, Any] | None = None,
        response_generator: PharmacyResponseGenerator | None = None,
        name_matcher: LLMNameMatcher | None = None,
    ):
        """
        Initialize person validation node.

        Args:
            plex_client: PlexClient instance for PLEX API calls
            db_session: SQLAlchemy async session for DB access
            config: Node configuration
            response_generator: PharmacyResponseGenerator for LLM-driven responses
            name_matcher: LLMNameMatcher for fuzzy name matching
        """
        super().__init__("person_validation_node", config or {})
        self._plex_client = plex_client
        self._db_session = db_session
        self._response_generator = response_generator
        self._name_matcher = name_matcher
        self._registered_person_repo: RegisteredPersonRepository | None = None
        # Cache confirmation patterns per-instance (loaded from database)
        self._confirmation_patterns: dict[str, Any] | None = None

    def _get_plex_client(self) -> PlexClient:
        """Get or create Plex client."""
        if self._plex_client is None:
            from app.clients.plex_client import PlexClient

            self._plex_client = PlexClient()
        return self._plex_client

    def _get_response_generator(self) -> PharmacyResponseGenerator:
        """Get or create response generator."""
        if self._response_generator is None:
            self._response_generator = get_response_generator()
        return self._response_generator

    def _get_name_matcher(self) -> LLMNameMatcher:
        """Get or create name matcher."""
        if self._name_matcher is None:
            self._name_matcher = LLMNameMatcher()
        return self._name_matcher

    async def _get_registered_person_repo(self) -> RegisteredPersonRepository:
        """Get or create registered person repository."""
        if self._registered_person_repo is None:
            if self._db_session is None:
                from app.database.async_db import get_async_db

                self._db_session = await anext(get_async_db())
            self._registered_person_repo = RegisteredPersonRepository(self._db_session)
        return self._registered_person_repo

    async def _get_db_session(self) -> "AsyncSession":
        """Get or create database session."""
        if self._db_session is None:
            from app.database.async_db import get_async_db

            self._db_session = await anext(get_async_db())
        return self._db_session

    def _get_organization_id(self, state_dict: dict[str, Any]) -> UUID | None:
        """Extract organization_id from state."""
        org_id = state_dict.get("organization_id")
        if org_id is None:
            return None
        if isinstance(org_id, UUID):
            return org_id
        try:
            return UUID(str(org_id))
        except (ValueError, TypeError):
            return None

    async def _load_confirmation_patterns(
        self,
        organization_id: UUID,
    ) -> dict[str, Any]:
        """
        Load confirmation patterns from database via domain_intent_cache.

        Uses the same pattern structure as PharmacyIntentAnalyzer._match_confirmation()
        to ensure consistency across the system.

        Returns:
            Dict of confirmation patterns, empty dict if none found.
        """
        if self._confirmation_patterns is None:
            db = await self._get_db_session()
            patterns = await domain_intent_cache.get_patterns(
                db, organization_id, "pharmacy"
            )
            self._confirmation_patterns = patterns.get("confirmation_patterns", {})
        return self._confirmation_patterns or {}

    async def _detect_confirmation_intent(
        self,
        message: str,
        organization_id: UUID,
    ) -> tuple[str | None, float]:
        """
        Detect confirmation/rejection using database patterns.

        Uses same pattern structure as PharmacyIntentAnalyzer._match_confirmation()
        to ensure consistency. NO HARDCODED PATTERNS - all from database.

        Priority:
        1. Exact matches (highest confidence)
        2. Contains matches (high confidence)
        3. If no pattern match AND multi-word with len > 5, treat as name

        Args:
            message: User message
            organization_id: Tenant UUID for pattern lookup

        Returns:
            Tuple of (intent_key, confidence) where intent_key is
            "confirm", "reject", or None
        """
        text_lower = message.strip().lower()
        words = text_lower.split()

        # Load patterns from database
        confirmation_patterns = await self._load_confirmation_patterns(organization_id)

        if not confirmation_patterns:
            logger.warning(
                f"No confirmation patterns found for org {organization_id}. "
                "Please seed patterns via Admin API."
            )
            return (None, 0.0)

        # First: Check exact matches (highest priority)
        for intent_key, patterns in confirmation_patterns.items():
            exact_patterns = patterns.get("exact", set())
            # Convert lists to sets if needed (from JSON deserialization)
            if isinstance(exact_patterns, list):
                exact_patterns = set(exact_patterns)

            if text_lower in exact_patterns:
                logger.debug(f"Confirmation exact match: '{text_lower}' -> {intent_key}")
                return (intent_key, 0.95)

        # Second: Check contains matches
        for intent_key, patterns in confirmation_patterns.items():
            contains_patterns = patterns.get("contains", set())
            # Convert lists to sets if needed (from JSON deserialization)
            if isinstance(contains_patterns, list):
                contains_patterns = set(contains_patterns)

            for pattern in contains_patterns:
                if pattern in text_lower:
                    logger.debug(
                        f"Confirmation contains match: '{pattern}' in '{text_lower}' "
                        f"-> {intent_key}"
                    )
                    return (intent_key, 0.85)

        # Third: Multi-word with length > 5 and no pattern match = treat as name
        # This heuristic catches names like "Si Garcia" that don't match any pattern
        if len(words) >= 2 and len(text_lower) > 5:
            logger.debug(f"Treating as name (multi-word, no pattern match): '{message}'")
            return (None, 0.0)

        return (None, 0.0)

    async def _handle_name_confirmation(
        self,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle when user says 'si' during name input.

        Interpretation: User confirms the PLEX name is correct without
        explicitly typing it.

        Returns:
            State updates for registration and debt check
        """
        plex_customer = state_dict.get("plex_customer")
        plex_candidates = state_dict.get("plex_candidates", [])

        if plex_customer:
            # Single match - user confirms PLEX name
            expected_name = plex_customer.get("nombre", "")
            return await self._register_and_proceed(
                state_dict,
                plex_customer,
                expected_name,
            )

        if plex_candidates and len(plex_candidates) == 1:
            # Single candidate - user confirms
            customer = plex_candidates[0]
            return await self._register_and_proceed(
                state_dict,
                customer,
                customer.get("nombre", ""),
            )

        # Multiple candidates or no PLEX data - need clarification
        return {
            "validation_step": self.STEP_NAME,
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "Para confirmar tu identidad necesito tu nombre completo.\n"
                        "Por favor, ingresa tu nombre y apellido:"
                    ),
                }
            ],
        }

    async def _handle_name_rejection(
        self,
        state_dict: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        """
        Handle when user says 'no' or 'cancelar' during name input.

        Action: Return to DNI step to start over with a fresh validation.

        Returns:
            State updates to reset to DNI step
        """
        return {
            "validation_step": self.STEP_DNI,
            "dni_requested": False,  # Reset to show welcome message
            "pending_dni": None,
            "plex_customer": None,
            "plex_candidates": None,
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "Entendido, volvemos al inicio.\n"
                        "Si deseas verificar tu identidad, ingresa tu numero de DNI:"
                    ),
                }
            ],
        }

    def _get_pharmacy_id(self, state_dict: dict[str, Any]) -> UUID | None:
        """Extract pharmacy_id from state."""
        pharmacy_id = state_dict.get("pharmacy_id")
        if pharmacy_id is None:
            return None
        if isinstance(pharmacy_id, UUID):
            return pharmacy_id
        try:
            return UUID(str(pharmacy_id))
        except (ValueError, TypeError):
            return None

    def _extract_phone(self, state_dict: dict[str, Any]) -> str | None:
        """Extract phone number from state."""
        return (
            state_dict.get("customer_id")
            or state_dict.get("user_id")
            or state_dict.get("user_phone")
            or state_dict.get("sender")
        )

    async def _process_internal(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle person validation workflow.

        Args:
            message: User message
            state_dict: Current state dictionary

        Returns:
            State updates
        """
        try:
            step = state_dict.get("validation_step", self.STEP_DNI)

            if step == self.STEP_DNI:
                return await self._handle_dni_step(message, state_dict)
            elif step == self.STEP_NAME:
                return await self._handle_name_step(message, state_dict)
            elif step == self.STEP_CONFIRM:
                return await self._handle_confirm_step(message, state_dict)
            else:
                # Unknown step - start from DNI with welcome message
                return await self._request_initial_dni(state_dict)

        except Exception as e:
            logger.error(f"Error in person validation: {e}", exc_info=True)
            return self._handle_error(str(e), state_dict)

    async def _handle_dni_step(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle DNI input step.

        Logic:
        - If dni_requested is False/None: First time → show welcome message
        - If dni_requested is True and no DNI: User tried but invalid format
        - If DNI found: Proceed to PLEX lookup

        Args:
            message: User message (should contain DNI)
            state_dict: Current state

        Returns:
            State updates
        """
        # Check if we already asked for DNI (to differentiate first time vs retry)
        dni_already_requested = state_dict.get("dni_requested", False)

        dni = self._extract_dni(message)

        if not dni:
            # First time entering the node - show welcome and request DNI
            if not dni_already_requested:
                return await self._request_initial_dni(state_dict)
            # Already asked for DNI but got invalid input
            return await self._request_dni_invalid_format(state_dict)

        logger.info(f"Validating DNI: {dni}")

        # Search PLEX by DNI
        plex_customers = await self._search_plex_by_dni(dni)

        if not plex_customers:
            return await self._dni_not_found(dni, state_dict)

        # Filter valid customers
        valid_customers = [
            c for c in plex_customers
            if c.get("is_valid", True)  # Default to valid if not specified
        ]

        if not valid_customers:
            return await self._dni_not_found(dni, state_dict)

        if len(valid_customers) == 1:
            # Single match - proceed to name verification
            customer = valid_customers[0]
            return {
                "validation_step": self.STEP_NAME,
                "plex_customer": customer,
                "pending_dni": dni,
                "messages": [
                    {
                        "role": "assistant",
                        "content": (
                            "DNI encontrado en nuestro sistema.\n"
                            "Por favor, ingresa tu nombre completo para verificar:"
                        ),
                    }
                ],
            }

        else:
            # Multiple matches - store candidates for name disambiguation
            return {
                "validation_step": self.STEP_NAME,
                "plex_candidates": valid_customers,
                "pending_dni": dni,
                "messages": [
                    {
                        "role": "assistant",
                        "content": (
                            "DNI encontrado. Hay varias personas con ese documento.\n"
                            "Por favor, ingresa tu nombre completo para verificar:"
                        ),
                    }
                ],
            }

    async def _handle_name_step(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle name input step with LLM fuzzy matching.

        Checks for confirmation/rejection intent FIRST to fix bug where
        "si"/"no" were treated as names instead of confirmations.
        Uses database patterns via domain_intent_cache.

        Args:
            message: User message (should contain name or confirmation)
            state_dict: Current state

        Returns:
            State updates
        """
        # PRIORITY 1: Check for confirmation/rejection intent using database patterns
        # This fixes the bug where "si"/"no" were treated as names (Tests 6-10)
        org_id = self._get_organization_id(state_dict)
        if org_id:
            intent, confidence = await self._detect_confirmation_intent(message, org_id)

            if intent == "confirm" and confidence >= 0.85:
                logger.info(
                    f"Detected confirmation intent during name step: '{message}' "
                    f"(confidence={confidence:.2f})"
                )
                return await self._handle_name_confirmation(state_dict)

            if intent == "reject" and confidence >= 0.85:
                logger.info(
                    f"Detected rejection intent during name step: '{message}' "
                    f"(confidence={confidence:.2f})"
                )
                return await self._handle_name_rejection(state_dict)

        # PRIORITY 2: Treat input as a name
        provided_name = message.strip()

        if len(provided_name) < 2:
            return {
                "validation_step": self.STEP_NAME,
                "messages": [
                    {
                        "role": "assistant",
                        "content": "Por favor, ingresa tu nombre completo:",
                    }
                ],
            }

        plex_customer = state_dict.get("plex_customer")
        plex_candidates = state_dict.get("plex_candidates", [])

        name_matcher = self._get_name_matcher()

        if plex_customer:
            # Single PLEX match - LLM fuzzy compare
            expected_name = plex_customer.get("nombre", "")
            match_result = await name_matcher.compare(provided_name, expected_name)

            logger.info(
                f"Name match result: score={match_result.score:.2f}, "
                f"is_match={match_result.is_match}"
            )

            if match_result.is_match:
                return await self._register_and_proceed(
                    state_dict,
                    plex_customer,
                    provided_name,
                )
            else:
                return self._name_mismatch(expected_name, provided_name, state_dict)

        elif plex_candidates:
            # Multiple candidates - find best LLM match
            best_match, best_score = await name_matcher.find_best_match(
                provided_name,
                plex_candidates,
                name_field="nombre",
            )

            if best_match and best_score >= self.NAME_MATCH_THRESHOLD:
                logger.info(f"Best match found with score {best_score:.2f}")
                return await self._register_and_proceed(
                    state_dict,
                    best_match,
                    provided_name,
                )
            else:
                return self._name_mismatch_multiple(plex_candidates, provided_name, state_dict)

        else:
            # No PLEX data - something went wrong, restart
            logger.error("No PLEX customer data in name step")
            return await self._request_initial_dni(state_dict)

    async def _handle_confirm_step(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle confirmation step (if needed).

        Uses database patterns via domain_intent_cache for confirmation detection.
        NO HARDCODED PATTERNS.

        Args:
            message: User message
            state_dict: Current state

        Returns:
            State updates
        """
        # Check for confirmation using database patterns
        org_id = self._get_organization_id(state_dict)
        if org_id:
            intent, confidence = await self._detect_confirmation_intent(message, org_id)

            if intent == "confirm" and confidence >= 0.85:
                # Confirmed - proceed with registration
                plex_customer = state_dict.get("plex_customer_to_confirm", {})
                provided_name = state_dict.get("provided_name_to_confirm", "")
                return await self._register_and_proceed(
                    state_dict,
                    plex_customer,
                    provided_name,
                )

            elif intent == "reject" and confidence >= 0.85:
                # Rejected - start over from beginning
                return await self._request_initial_dni(state_dict)

        # Unclear or no org_id - ask again
        return {
            "validation_step": self.STEP_CONFIRM,
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "Por favor confirma:\n"
                        "1. Si, los datos son correctos\n"
                        "2. No, quiero corregir"
                    ),
                }
            ],
        }

    async def _register_and_proceed(
        self,
        state_dict: dict[str, Any],
        plex_customer: dict,
        provided_name: str,
    ) -> dict[str, Any]:
        """
        Register person in local DB and proceed to debt check.

        Args:
            state_dict: Current state
            plex_customer: PLEX customer dict
            provided_name: Name provided by user

        Returns:
            State updates for debt check
        """
        phone = self._extract_phone(state_dict)
        pharmacy_id = self._get_pharmacy_id(state_dict)
        dni = state_dict.get("pending_dni", "")

        if not phone or not pharmacy_id:
            logger.error("Missing phone or pharmacy_id for registration")
            return self._handle_error("Datos incompletos", state_dict)

        # Check if is_self (phone matches PLEX record)
        plex_phone = plex_customer.get("telefono", "")
        is_self = self._is_same_phone(phone, plex_phone)

        # Create registration
        try:
            plex_customer_id = plex_customer.get("id")
            if plex_customer_id is None:
                raise ValueError("PLEX customer ID is required for registration")

            registration = RegisteredPerson.create(
                phone_number=phone,
                dni=dni,
                name=provided_name.upper(),
                plex_customer_id=int(plex_customer_id),
                pharmacy_id=pharmacy_id,
                is_self=is_self,
            )

            repo = await self._get_registered_person_repo()
            saved_registration = await repo.upsert(registration)

            logger.info(
                f"Registered person: {saved_registration.dni} "
                f"for phone {saved_registration.phone_number}"
            )

            registration_id = str(saved_registration.id)

        except Exception as e:
            logger.error(f"Failed to save registration: {e}")
            # Continue anyway - registration is not critical for debt query
            registration_id = None

        customer_name = plex_customer.get("nombre", provided_name)

        return {
            "plex_customer_id": plex_customer.get("id"),
            "plex_customer": plex_customer,
            "customer_name": customer_name,
            "customer_identified": True,
            "is_self": is_self,
            "active_registered_person_id": registration_id,
            "validation_step": None,
            "pending_dni": None,
            "plex_candidates": None,
            "next_node": "debt_check_node",
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        f"Perfecto {customer_name}, te he registrado correctamente.\n"
                        f"Consultando tu deuda..."
                    ),
                }
            ],
            "pharmacy_name": state_dict.get("pharmacy_name"),
            "pharmacy_phone": state_dict.get("pharmacy_phone"),
        }

    # =========================================================================
    # DNI Request Methods (using YAML prompts)
    # =========================================================================

    async def _request_initial_dni(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        First time request for DNI - welcoming message.
        Uses LLM with system context to generate empathetic response.
        """
        response_content = await generate_response(
            state=state_dict,
            intent="request_dni_welcome",
            user_message="",
            current_task=(
                "Da la bienvenida al cliente y solicita su DNI para verificar identidad. "
                "Explica que es necesario por seguridad."
            ),
        )

        return {
            "validation_step": self.STEP_DNI,
            "dni_requested": True,
            "messages": [{"role": "assistant", "content": response_content}],
        }

    async def _request_dni_invalid_format(
        self,
        state_dict: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        """
        User provided invalid DNI format after being asked.
        Uses critical template for consistent validation message.
        """
        response_content = await generate_response(
            state=state_dict,
            intent="invalid_dni_format",
            user_message="",
            current_task="Indica que el formato del DNI es inválido y pide que ingrese solo números.",
        )

        return {
            "validation_step": self.STEP_DNI,
            "dni_requested": True,
            "messages": [{"role": "assistant", "content": response_content}],
        }

    async def _request_dni_for_other(
        self,
        state_dict: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        """
        Request DNI for another person (not self).
        Uses LLM to generate contextual response.
        """
        response_content = await generate_response(
            state=state_dict,
            intent="request_dni",
            user_message="",
            current_task="Solicita el DNI de la otra persona para validar su identidad.",
        )

        return {
            "validation_step": self.STEP_DNI,
            "dni_requested": True,
            "messages": [{"role": "assistant", "content": response_content}],
        }

    async def _dni_not_found(self, dni: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Handle DNI not found in PLEX.
        Uses LLM to generate empathetic response.
        """
        # Add DNI to state for template rendering
        state_with_dni = {**state_dict, "dni": dni}

        response_content = await generate_response(
            state=state_with_dni,
            intent="dni_not_found",
            user_message="",
            current_task=f"Informa que el DNI {dni} no fue encontrado. Sé empático y sugiere verificar el número.",
        )

        return {
            "validation_step": self.STEP_DNI,
            "dni_requested": True,
            "messages": [{"role": "assistant", "content": response_content}],
        }

    def _name_mismatch(
        self,
        expected_name: str,  # noqa: ARG002 - kept for future logging/debugging
        provided_name: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle name mismatch for single customer."""
        return {
            "validation_step": self.STEP_NAME,
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        f"El nombre '{provided_name}' no coincide con nuestros registros.\n"
                        f"Por favor ingresa tu nombre completo tal como figura en la farmacia:"
                    ),
                }
            ],
            "name_mismatch_count": state_dict.get("name_mismatch_count", 0) + 1,
        }

    def _name_mismatch_multiple(
        self,
        candidates: list[dict],
        provided_name: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle name mismatch with multiple candidates."""
        mismatch_count = state_dict.get("name_mismatch_count", 0) + 1

        if mismatch_count >= 2:
            # Too many mismatches - suggest contact
            pharmacy_name = state_dict.get("pharmacy_name", "la farmacia")
            return {
                "messages": [
                    {
                        "role": "assistant",
                        "content": (
                            f"No pude verificar los datos.\n"
                            f"Por favor contacta directamente a {pharmacy_name} "
                            f"para ayudarte con tu consulta."
                        ),
                    }
                ],
                "is_complete": True,
                "requires_human": True,
            }

        return {
            "validation_step": self.STEP_NAME,
            "plex_candidates": candidates,
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        f"El nombre '{provided_name}' no coincide con ninguno de nuestros registros.\n"
                        f"Por favor ingresa tu nombre completo exactamente como esta registrado:"
                    ),
                }
            ],
            "name_mismatch_count": mismatch_count,
        }

    def _extract_dni(self, message: str) -> str | None:
        """Extract DNI from message."""
        # Look for 7-8 digit number
        match = re.search(r"\b(\d{7,8})\b", message)
        if match:
            return match.group(1)
        return None

    async def _search_plex_by_dni(self, dni: str) -> list[dict]:
        """
        Search PLEX by DNI.

        Args:
            dni: Document number

        Returns:
            List of matching PLEX customer dicts
        """
        try:
            plex_client = self._get_plex_client()
            async with plex_client:
                customers = await plex_client.search_customer(document=dni)

            # Convert to dicts with validity flag
            result = []
            for c in customers:
                is_valid = (
                    hasattr(c, "is_valid_for_identification")
                    and c.is_valid_for_identification
                )
                result.append({
                    "id": c.id,
                    "nombre": c.nombre,
                    "documento": c.documento,
                    "telefono": c.telefono,
                    "is_valid": is_valid,
                })

            return result

        except Exception as e:
            logger.error(f"Error searching PLEX by DNI: {e}")
            return []

    def _is_same_phone(self, phone1: str | None, phone2: str | None) -> bool:
        """Check if two phone numbers are the same (normalized)."""
        if not phone1 or not phone2:
            return False

        # Normalize: keep only digits
        p1 = re.sub(r"\D", "", phone1)
        p2 = re.sub(r"\D", "", phone2)

        # Compare last 10 digits (ignoring country code)
        return p1[-10:] == p2[-10:] if len(p1) >= 10 and len(p2) >= 10 else p1 == p2

    def _handle_error(self, error: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Handle processing error."""
        logger.error(f"Person validation error: {error}")
        error_count = state_dict.get("error_count", 0) + 1

        if error_count >= 3:
            return {
                "messages": [
                    {
                        "role": "assistant",
                        "content": (
                            "Tuve varios problemas verificando los datos. "
                            "Por favor contacta a la farmacia directamente."
                        ),
                    }
                ],
                "is_complete": True,
                "requires_human": True,
            }

        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "Tuve un problema. Por favor intenta de nuevo.\n"
                        "Ingresa tu numero de DNI:"
                    ),
                }
            ],
            "validation_step": self.STEP_DNI,
            "error_count": error_count,
        }


__all__ = ["PersonValidationNode"]
