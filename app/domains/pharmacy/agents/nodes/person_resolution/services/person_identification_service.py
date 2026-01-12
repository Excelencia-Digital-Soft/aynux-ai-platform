"""Person identification business logic."""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.clients.plex_client import PlexClient
    from app.models.db.tenancy.registered_person import RegisteredPerson

logger = logging.getLogger(__name__)


class PersonIdentificationService:
    """
    Service for person identification operations.

    Responsibilities:
    - Search PLEX by phone/identifier
    - Validate identifier format
    - Find self-registration from list
    - Calculate name similarity
    """

    def __init__(self, plex_client: PlexClient | None = None):
        self._plex_client = plex_client

    def _get_plex_client(self) -> PlexClient:
        """Get or create Plex client."""
        if self._plex_client is None:
            from app.clients.plex_client import PlexClient

            self._plex_client = PlexClient()
        return self._plex_client

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
                c
                for c in customers
                if hasattr(c, "is_valid_for_identification") and c.is_valid_for_identification
            ]

            if len(valid_customers) == 1:
                return self._customer_to_dict(valid_customers[0])
            elif len(valid_customers) > 1:
                logger.info(f"Multiple PLEX matches for phone: {len(valid_customers)}")
                return self._customer_to_dict(
                    valid_customers[0],
                    multiple_matches=True,
                    all_matches=valid_customers,
                )

            return None

        except Exception as e:
            logger.error(f"Error searching PLEX by phone: {e}")
            return None

    async def search_by_identifier(self, identifier: str) -> dict[str, Any] | None:
        """
        Search PLEX for customer by identifier (DNI/client number).

        Args:
            identifier: Normalized identifier

        Returns:
            PLEX customer dict or None if not found
        """
        try:
            plex_client = self._get_plex_client()
            async with plex_client:
                # Try document first
                customers = await plex_client.search_customer(document=identifier)

                if not customers:
                    # Try by client number
                    try:
                        customer_id_int = int(identifier)
                        customers = await plex_client.search_customer(
                            customer_id=customer_id_int
                        )
                    except ValueError:
                        customers = []

            valid_customers = [
                c
                for c in customers
                if hasattr(c, "is_valid_for_identification") and c.is_valid_for_identification
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
            logger.error(f"Error searching PLEX by identifier: {e}")
            return None

    def normalize_identifier(self, value: str) -> str | None:
        """
        Normalize and validate identifier format.

        Accepts:
        - DNI: 7-8 digits
        - Client number: digits
        - CUIT/CUIL: XX-XXXXXXXX-X format

        Extracts identifier from messages that may contain additional text.
        E.g., "2259863 Adela Pedrozo" → "2259863"

        Args:
            value: Raw identifier input

        Returns:
            Normalized identifier or None if invalid
        """
        text = value.strip()

        # First, try to find CUIT/CUIL format (XX-XXXXXXXX-X)
        cuit_match = re.search(r"\b(\d{2})-?(\d{8})-?(\d)\b", text)
        if cuit_match:
            return cuit_match.group(1) + cuit_match.group(2) + cuit_match.group(3)

        # Then, try to find a standalone number (DNI or client number)
        # Look for 6-11 digit sequences that are likely identifiers
        number_match = re.search(r"\b(\d{6,11})\b", text)
        if number_match:
            return number_match.group(1)

        # Fallback: clean the entire input and check if it's all digits
        cleaned = re.sub(r"[\s\-\.]", "", text)
        if cleaned.isdigit() and 1 <= len(cleaned) <= 11:
            return cleaned

        return None

    def find_self_registration(
        self,
        registrations: list[RegisteredPerson],
        plex_customer: dict[str, Any] | None,
    ) -> RegisteredPerson | None:
        """
        Find self-registration from list.

        Args:
            registrations: List of registered persons
            plex_customer: PLEX customer dict

        Returns:
            Self registration or None
        """
        if not plex_customer:
            return None

        plex_id = plex_customer.get("id")
        for reg in registrations:
            if bool(reg.is_self) and reg.plex_customer_id == plex_id:
                return reg
        return None

    def only_self_registered(
        self,
        registrations: list[RegisteredPerson],
        self_registration: RegisteredPerson | None,
    ) -> bool:
        """
        Check if only self is registered (no others).

        Args:
            registrations: List of registered persons
            self_registration: Self registration if found

        Returns:
            True if only self is registered
        """
        if not self_registration:
            return len(registrations) == 0
        return len(registrations) == 1 and str(registrations[0].id) == str(
            self_registration.id
        )

    def calculate_name_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between two names using smart matching.

        Uses a combination of:
        1. Subset matching: If all tokens from shorter name are in longer name
        2. Jaccard similarity as fallback

        This handles cases like:
        - "Adela Pedrozo" vs "PEDROZO, ADELA MARIA DE CTA CTE" → match (subset)
        - "Juan Perez" vs "PEREZ, JUAN CARLOS" → match (subset)

        Args:
            name1: First name (typically user input)
            name2: Second name (typically from database)

        Returns:
            Similarity score between 0 and 1
        """
        n1 = self.normalize_name(name1)
        n2 = self.normalize_name(name2)

        if not n1 or not n2:
            return 0.0

        # Filter out common noise words that don't identify a person
        noise_words = {"de", "la", "el", "los", "las", "del", "cta", "cte", "sra", "sr"}

        tokens1 = {t for t in n1.split() if t not in noise_words and len(t) > 1}
        tokens2 = {t for t in n2.split() if t not in noise_words and len(t) > 1}

        if not tokens1 or not tokens2:
            return 0.0

        # Check subset matching: if all tokens from one name are in the other
        # This handles "Adela Pedrozo" matching "PEDROZO, ADELA MARIA"
        if tokens1 <= tokens2:
            # All user tokens are in the expected name
            # Score based on how many of the expected tokens were matched
            return min(1.0, 0.8 + (len(tokens1) / len(tokens2)) * 0.2)

        if tokens2 <= tokens1:
            # All expected tokens are in the user's input
            return min(1.0, 0.8 + (len(tokens2) / len(tokens1)) * 0.2)

        # Partial overlap: use Jaccard but boost if significant overlap
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        jaccard = intersection / union if union > 0 else 0.0

        # Boost score if most of the smaller set matches
        smaller_set = min(len(tokens1), len(tokens2))
        if smaller_set > 0:
            overlap_ratio = intersection / smaller_set
            if overlap_ratio >= 0.8:
                # Most tokens match, boost the score
                jaccard = min(1.0, jaccard + 0.3)

        return jaccard

    def normalize_name(self, name: str) -> str:
        """
        Normalize a name for comparison.

        Args:
            name: Raw name string

        Returns:
            Normalized name (lowercase, no accents, no punctuation, no extra spaces)
        """
        name = name.lower().strip()
        # Remove accents
        name = unicodedata.normalize("NFD", name)
        name = "".join(c for c in name if unicodedata.category(c) != "Mn")
        # Remove punctuation (commas, periods, etc.)
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
                {"id": c.id, "nombre": c.nombre, "documento": c.documento}
                for c in (all_matches or [])
            ]
        return result


__all__ = ["PersonIdentificationService"]
