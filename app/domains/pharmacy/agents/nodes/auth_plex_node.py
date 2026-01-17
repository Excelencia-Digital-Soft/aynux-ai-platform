"""
Auth PLEX Node - V2 Authentication Node for PLEX Customer Identification.

Simplified authentication flow for pharmacy V2 graph.
Handles DNI validation, PLEX customer lookup, and name verification.

Migrated from person_resolution/ package with simplified state management.
Uses V2 state fields: is_authenticated, pending_dni, awaiting_input, etc.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import TYPE_CHECKING, Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig

from app.core.cache.routing_config_cache import routing_config_cache
from app.domains.pharmacy.agents.utils.message_extractor import MessageExtractor

if TYPE_CHECKING:
    from app.clients.plex_client import PlexClient
    from app.domains.pharmacy.agents.state_v2 import PharmacyStateV2

logger = logging.getLogger(__name__)

# Validation constants
MAX_RETRIES = 3
NAME_MATCH_THRESHOLD = 0.75


class AuthPlexService:
    """
    Service for PLEX authentication operations.

    Responsibilities:
    - DNI validation and normalization
    - PLEX customer lookup
    - Name similarity calculation
    - Customer state management
    """

    def __init__(self, plex_client: "PlexClient | None" = None):
        self._plex_client = plex_client

    def _get_plex_client(self) -> "PlexClient":
        """Get or create Plex client."""
        if self._plex_client is None:
            from app.clients.plex_client import PlexClient

            self._plex_client = PlexClient()
        return self._plex_client

    def normalize_dni(self, value: str) -> str | None:
        """
        Normalize and validate DNI format.

        Accepts:
        - DNI: 7-8 digits
        - Client number: digits
        - CUIT/CUIL: XX-XXXXXXXX-X format

        Args:
            value: Raw identifier input

        Returns:
            Normalized identifier or None if invalid
        """
        text = value.strip()

        # Try CUIT/CUIL format (XX-XXXXXXXX-X)
        cuit_match = re.search(r"\b(\d{2})-?(\d{8})-?(\d)\b", text)
        if cuit_match:
            return cuit_match.group(1) + cuit_match.group(2) + cuit_match.group(3)

        # Try standalone number (6-11 digits)
        number_match = re.search(r"\b(\d{6,11})\b", text)
        if number_match:
            return number_match.group(1)

        # Fallback: clean entire input
        cleaned = re.sub(r"[\s\-\.]", "", text)
        if cleaned.isdigit() and 1 <= len(cleaned) <= 11:
            return cleaned

        return None

    async def search_by_dni(self, dni: str) -> dict[str, Any] | None:
        """
        Search PLEX for customer by DNI.

        Args:
            dni: Normalized DNI

        Returns:
            PLEX customer dict or None if not found
        """
        try:
            plex_client = self._get_plex_client()
            async with plex_client:
                # Try document first
                customers = await plex_client.search_customer(document=dni)

                if not customers:
                    # Try by client number
                    try:
                        customer_id_int = int(dni)
                        customers = await plex_client.search_customer(customer_id=customer_id_int)
                    except ValueError:
                        customers = []

            valid_customers = [
                c for c in customers if hasattr(c, "is_valid_for_identification") and c.is_valid_for_identification
            ]

            if len(valid_customers) == 1:
                return self._customer_to_dict(valid_customers[0])
            elif len(valid_customers) > 1:
                return self._customer_to_dict(
                    valid_customers[0],
                    multiple_matches=True,
                    all_matches=valid_customers,
                )

            return None

        except Exception as e:
            logger.error(f"Error searching PLEX by DNI: {e}")
            return None

    async def search_by_phone(self, phone: str) -> dict[str, Any] | None:
        """
        Search PLEX for customer by phone number.

        Args:
            phone: Phone number to search

        Returns:
            PLEX customer dict or None if not found
        """
        try:
            plex_client = self._get_plex_client()
            async with plex_client:
                customers = await plex_client.search_customer(phone=phone)

            valid_customers = [
                c for c in customers if hasattr(c, "is_valid_for_identification") and c.is_valid_for_identification
            ]

            if len(valid_customers) == 1:
                return self._customer_to_dict(valid_customers[0])
            elif len(valid_customers) > 1:
                return self._customer_to_dict(
                    valid_customers[0],
                    multiple_matches=True,
                    all_matches=valid_customers,
                )

            return None

        except Exception as e:
            logger.error(f"Error searching PLEX by phone: {e}")
            return None

    async def search_by_customer_id(self, customer_id: int) -> dict[str, Any] | None:
        """
        Search PLEX for customer by account number (customer_id).

        Args:
            customer_id: Account number / customer ID to search

        Returns:
            PLEX customer dict or None if not found
        """
        try:
            plex_client = self._get_plex_client()
            async with plex_client:
                customers = await plex_client.search_customer(customer_id=customer_id)

            valid_customers = [
                c for c in customers if hasattr(c, "is_valid_for_identification") and c.is_valid_for_identification
            ]

            if len(valid_customers) == 1:
                return self._customer_to_dict(valid_customers[0])
            elif len(valid_customers) > 1:
                return self._customer_to_dict(
                    valid_customers[0],
                    multiple_matches=True,
                    all_matches=valid_customers,
                )

            return None

        except Exception as e:
            logger.error(f"Error searching PLEX by customer_id: {e}")
            return None

    def calculate_name_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between two names using smart matching.

        Args:
            name1: First name (typically user input)
            name2: Second name (typically from database)

        Returns:
            Similarity score between 0 and 1
        """
        n1 = self._normalize_name(name1)
        n2 = self._normalize_name(name2)

        if not n1 or not n2:
            return 0.0

        # Filter out common noise words
        noise_words = {"de", "la", "el", "los", "las", "del", "cta", "cte", "sra", "sr"}

        tokens1 = {t for t in n1.split() if t not in noise_words and len(t) > 1}
        tokens2 = {t for t in n2.split() if t not in noise_words and len(t) > 1}

        if not tokens1 or not tokens2:
            return 0.0

        # Check subset matching
        if tokens1 <= tokens2:
            return min(1.0, 0.8 + (len(tokens1) / len(tokens2)) * 0.2)

        if tokens2 <= tokens1:
            return min(1.0, 0.8 + (len(tokens2) / len(tokens1)) * 0.2)

        # Partial overlap: use Jaccard
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        jaccard = intersection / union if union > 0 else 0.0

        # Boost if most of smaller set matches
        smaller_set = min(len(tokens1), len(tokens2))
        if smaller_set > 0:
            overlap_ratio = intersection / smaller_set
            if overlap_ratio >= 0.8:
                jaccard = min(1.0, jaccard + 0.3)

        return jaccard

    def _normalize_name(self, name: str) -> str:
        """Normalize a name for comparison."""
        name = name.lower().strip()
        # Remove accents
        name = unicodedata.normalize("NFD", name)
        name = "".join(c for c in name if unicodedata.category(c) != "Mn")
        # Remove punctuation
        name = re.sub(r"[^\w\s]", " ", name)
        return " ".join(name.split())

    def _customer_to_dict(
        self,
        customer: Any,
        multiple_matches: bool = False,
        all_matches: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Convert PLEX customer to dict."""
        result: dict[str, Any] = {
            "id": customer.id,
            "nombre": customer.nombre,
            "documento": customer.documento,
            "telefono": customer.telefono,
        }
        if multiple_matches:
            result["_multiple_matches"] = True
            result["_all_matches"] = [
                {"id": c.id, "nombre": c.nombre, "documento": c.documento} for c in (all_matches or [])
            ]
        return result


async def _build_auth_success_response(
    plex_customer: dict[str, Any],
    state: "PharmacyStateV2",
    org_id: UUID | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build the auth success response, resuming previous_intent if applicable.

    After successful authentication, checks if there's a previous_intent that
    should be resumed instead of showing the main menu. The intent-to-node
    mapping is loaded from database via routing_config_cache.

    Args:
        plex_customer: The authenticated PLEX customer data
        state: Current conversation state (to check previous_intent)
        org_id: Organization ID for multi-tenant routing config lookup
        extra_fields: Additional fields to include in response

    Returns:
        State updates with authentication result and appropriate routing
    """
    previous_intent = state.get("previous_intent")

    # Base auth success fields
    response: dict[str, Any] = {
        "is_authenticated": True,
        "plex_user_id": plex_customer.get("id"),
        "plex_customer": plex_customer,
        "customer_name": plex_customer.get("nombre", "Cliente"),
        "error_count": 0,
    }

    # Add any extra fields
    if extra_fields:
        response.update(extra_fields)

    # Check if we should resume a previous intent
    if previous_intent:
        # Load intent-to-node mappings from database
        configs = await routing_config_cache.get_configs(None, org_id, "pharmacy")
        intent_mappings = configs.get("intent_node_mapping", [])

        # Find the mapping for this intent
        target_node = None
        for config in intent_mappings:
            if config.trigger_value == previous_intent:
                target_node = config.target_node
                break

        if target_node:
            logger.info(f"[AUTH_PLEX] Resuming previous_intent: {previous_intent}")
            logger.info(f"[AUTH_PLEX] Routing to {target_node} after auth")
            response.update({
                "intent": previous_intent,
                "previous_intent": None,  # Clear to prevent loops
                "next_node": target_node,
                "awaiting_input": None,
            })
            return response

    # No resumable intent - show main menu as before
    logger.debug("[AUTH_PLEX] No resumable intent, showing main menu")
    response.update({
        "intent": "auth_success",
        "next_node": "main_menu_node",
        "awaiting_input": "menu_selection",
    })

    return response


async def auth_plex_node(
    state: "PharmacyStateV2",
    config: RunnableConfig | None = None,  # noqa: ARG001
) -> dict[str, Any]:
    """
    Authentication node - handles PLEX customer identification.

    Flow:
    1. If awaiting_input == "account_number": validate account and lookup in PLEX
    2. If awaiting_input == "account_not_found": handle button selection (retry/dni)
    3. If awaiting_input == "dni": validate DNI and lookup in PLEX
    4. If awaiting_input == "name": verify name matches PLEX record
    5. If not authenticated and has phone: auto-lookup by phone
    6. Otherwise: request account number input (primary auth method)

    Args:
        state: Current conversation state
        config: Optional configuration

    Returns:
        State updates
    """
    service = AuthPlexService()

    # Extract message content
    message = MessageExtractor.extract_last_human_message(state) or ""
    awaiting = state.get("awaiting_input")

    # Handle account number input (primary auth method)
    if awaiting == "account_number":
        return await _handle_account_number_input(service, message, state)

    # Handle button selection after account not found
    if awaiting == "account_not_found":
        return await _handle_account_not_found_selection(message)

    # Handle DNI input (fallback auth method)
    if awaiting == "dni":
        return await _handle_dni_input(service, message, state)

    # Handle name verification
    if awaiting == "name":
        return await _handle_name_verification(service, message, state)

    # Already authenticated - pass through
    if state.get("is_authenticated") and state.get("plex_user_id"):
        logger.debug("Customer already authenticated, passing through")
        return {
            "is_authenticated": True,
            "next_node": "debt_manager",
        }

    # Try auto-identification by phone
    phone = state.get("user_phone")
    if phone:
        plex_customer = await service.search_by_phone(phone)
        if plex_customer:
            logger.info(f"Auto-identified customer by phone: {plex_customer.get('id')}")
            # Build auth success response, resuming previous_intent if applicable
            org_id_str = state.get("organization_id")
            org_id = UUID(org_id_str) if org_id_str else None
            return await _build_auth_success_response(plex_customer, state, org_id)

    # Request account number (primary auth method)
    return {
        "awaiting_input": "account_number",
        "next_node": "response_formatter",
    }


async def _handle_account_number_input(
    service: AuthPlexService,
    message: str,
    state: "PharmacyStateV2",
) -> dict[str, Any]:
    """
    Handle account number validation and PLEX lookup.

    Args:
        service: AuthPlexService instance
        message: User message (account number)
        state: Current conversation state

    Returns:
        State updates with authentication result or error
    """
    # Extract account number (only digits)
    account_number = re.sub(r"\D", "", message.strip())

    if not account_number:
        error_count = state.get("error_count", 0) + 1
        logger.info(f"Invalid account number format (attempt {error_count})")
        return {
            "error_count": error_count,
            "awaiting_input": "account_number",
            "next_node": "response_formatter",
        }

    # Search in PLEX by customer ID
    try:
        account_id = int(account_number)
        plex_customer = await service.search_by_customer_id(account_id)

        if plex_customer:
            # Account found - authenticated
            logger.info(f"Account validated: {plex_customer.get('id')}")
            # Build auth success response, resuming previous_intent if applicable
            org_id_str = state.get("organization_id")
            org_id = UUID(org_id_str) if org_id_str else None
            return await _build_auth_success_response(plex_customer, state, org_id)
    except (ValueError, TypeError):
        logger.warning(f"Invalid account number format: {account_number}")

    # Account not found - show options (retry or DNI validation)
    logger.info(f"Account not found: {account_number}")
    return {
        "pending_account_number": account_number,
        "awaiting_input": "account_not_found",
        "next_node": "response_formatter",
    }


async def _handle_account_not_found_selection(
    message: str,
) -> dict[str, Any]:
    """
    Handle button selection when account was not found.

    Options:
    - btn_retry_account: Try account number again
    - btn_validate_dni: Switch to DNI validation flow

    Args:
        message: User message or button ID

    Returns:
        State updates to continue appropriate flow
    """
    message_lower = message.lower().strip()

    # Button: Retry account number
    if message == "btn_retry_account" or "intentar" in message_lower or "volver" in message_lower:
        logger.info("User chose to retry account number")
        return {
            "awaiting_input": "account_number",
            "pending_account_number": None,
            "error_count": 0,
            "next_node": "response_formatter",
        }

    # Button: Validate by DNI (fallback method)
    if message == "btn_validate_dni" or "dni" in message_lower:
        logger.info("User chose DNI validation fallback")
        return {
            "awaiting_input": "dni",
            "pending_account_number": None,
            "error_count": 0,
            "next_node": "response_formatter",
        }

    # Unrecognized input - keep showing options
    logger.info(f"Unrecognized selection: {message}, keeping account_not_found state")
    return {
        "awaiting_input": "account_not_found",
        "next_node": "response_formatter",
    }


async def _handle_dni_input(
    service: AuthPlexService,
    message: str,
    state: PharmacyStateV2,
) -> dict[str, Any]:
    """Handle DNI input validation and PLEX lookup."""
    # Normalize DNI
    dni = service.normalize_dni(message)

    if not dni:
        error_count = state.get("error_count", 0) + 1
        if error_count >= MAX_RETRIES:
            logger.warning(f"DNI validation failed after {MAX_RETRIES} retries")
            return {
                "error_count": error_count,
                "requires_human": True,
                "next_node": "response_formatter",
            }
        return {
            "error_count": error_count,
            "awaiting_input": "dni",  # Keep waiting for valid DNI
            "next_node": "response_formatter",
        }

    # Search PLEX
    plex_customer = await service.search_by_dni(dni)

    if not plex_customer:
        # DNI not found in PLEX - validation failed, user must contact pharmacy
        logger.info(f"No PLEX customer found for DNI: {dni} - validation failed")
        return {
            "pending_dni": dni,
            "validation_failed": True,
            "awaiting_input": None,
            "next_node": "response_formatter",
        }

    # Found customer - request name verification
    logger.info(f"Found PLEX customer: {plex_customer.get('id')}")
    return {
        "pending_dni": dni,
        "plex_customer": plex_customer,
        "awaiting_input": "name",  # Verify name matches
        "next_node": "response_formatter",
    }


async def _handle_name_verification(
    service: AuthPlexService,
    message: str,
    state: "PharmacyStateV2",
) -> dict[str, Any]:
    """Handle name verification against PLEX record."""
    plex_customer = state.get("plex_customer")

    if not plex_customer:
        # No PLEX customer found for DNI - validation failed
        # User must contact pharmacy to register
        pending_dni = state.get("pending_dni")
        logger.info(f"DNI {pending_dni} not found in PLEX - validation failed")
        return {
            "validation_failed": True,
            "awaiting_input": None,
            "next_node": "response_formatter",
        }

    # Verify name matches PLEX record
    expected_name = plex_customer.get("nombre", "")
    provided_name = message.strip()

    similarity = service.calculate_name_similarity(provided_name, expected_name)
    logger.debug(f"Name similarity: {similarity:.2f} (threshold: {NAME_MATCH_THRESHOLD})")

    if similarity >= NAME_MATCH_THRESHOLD:
        # Name matches - authenticate
        logger.info(f"Name verified for customer: {plex_customer.get('id')}")
        # Build auth success response, resuming previous_intent if applicable
        org_id_str = state.get("organization_id")
        org_id = UUID(org_id_str) if org_id_str else None
        return await _build_auth_success_response(
            plex_customer,
            state,
            org_id,
            extra_fields={"pending_dni": None, "customer_name": expected_name},
        )

    # Name mismatch
    error_count = state.get("error_count", 0) + 1
    if error_count >= MAX_RETRIES:
        logger.warning(f"Name verification failed after {MAX_RETRIES} retries")
        return {
            "error_count": error_count,
            "validation_failed": True,
            "awaiting_input": None,
            "next_node": "response_formatter",
        }

    logger.info(f"Name mismatch (attempt {error_count}): '{provided_name}' vs '{expected_name}'")
    return {
        "error_count": error_count,
        "awaiting_input": "name",  # Keep waiting for matching name
        "next_node": "response_formatter",
    }


__all__ = ["auth_plex_node", "AuthPlexService"]
