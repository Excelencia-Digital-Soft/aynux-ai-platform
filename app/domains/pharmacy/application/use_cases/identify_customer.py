"""
Identify Customer Use Case

Application use case for resolving WhatsApp user to Plex customer.
Handles the 2-step identification and disambiguation flow required by Plex API.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from app.domains.pharmacy.domain.entities.plex_customer import PlexCustomer

if TYPE_CHECKING:
    from app.clients.plex_client import PlexClient


class IdentificationStatus(str, Enum):
    """Status of customer identification attempt."""

    IDENTIFIED = "identified"  # Single match found
    DISAMBIGUATION_REQUIRED = "disambiguation_required"  # Multiple matches
    NOT_FOUND = "not_found"  # No matches
    ERROR = "error"  # API or processing error


@dataclass
class IdentifyCustomerRequest:
    """Request to identify customer."""

    phone: str | None = None  # WhatsApp phone number
    document: str | None = None  # Document number if provided by user
    user_message: str | None = None  # Original message for context


@dataclass
class IdentifyCustomerResponse:
    """Response from customer identification."""

    status: IdentificationStatus
    customer: PlexCustomer | None = None  # Single identified customer
    candidates: list[PlexCustomer] | None = None  # Multiple matches for disambiguation
    error: str | None = None

    @property
    def requires_user_input(self) -> bool:
        """Check if user needs to provide more information."""
        return self.status == IdentificationStatus.DISAMBIGUATION_REQUIRED

    @property
    def is_success(self) -> bool:
        """Check if identification was successful."""
        return self.status == IdentificationStatus.IDENTIFIED and self.customer is not None


class IdentifyCustomerUseCase:
    """
    Use case for identifying Plex customer from WhatsApp context.

    Strategy:
    1. Search by phone number (from WhatsApp)
    2. If multiple matches, request document number
    3. If no matches, try document number if provided
    4. Filter out generic/invalid customer records

    Single Responsibility: Customer identification and disambiguation
    Dependency Inversion: Depends on PlexClient abstraction
    """

    def __init__(self, plex_client: PlexClient):
        """
        Initialize use case with Plex client.

        Args:
            plex_client: PlexClient instance for API calls
        """
        self._plex = plex_client

    async def execute(
        self,
        request: IdentifyCustomerRequest,
    ) -> IdentifyCustomerResponse:
        """
        Execute customer identification.

        Args:
            request: IdentifyCustomerRequest with phone and/or document

        Returns:
            IdentifyCustomerResponse with status and customer/candidates
        """
        try:
            customers: list[PlexCustomer] = []

            # Step 1: Search by phone
            if request.phone:
                customers = await self._plex.search_customer(phone=request.phone)

                # Filter out invalid/generic records
                customers = [c for c in customers if c.is_valid_for_identification]

                if len(customers) == 1:
                    return IdentifyCustomerResponse(
                        status=IdentificationStatus.IDENTIFIED,
                        customer=customers[0],
                    )
                elif len(customers) > 1:
                    # Multiple matches - need disambiguation
                    return IdentifyCustomerResponse(
                        status=IdentificationStatus.DISAMBIGUATION_REQUIRED,
                        candidates=customers,
                    )

            # Step 2: Try document if provided
            if request.document:
                customers = await self._plex.search_customer(document=request.document)
                customers = [c for c in customers if c.is_valid_for_identification]

                if len(customers) == 1:
                    return IdentifyCustomerResponse(
                        status=IdentificationStatus.IDENTIFIED,
                        customer=customers[0],
                    )
                elif len(customers) > 1:
                    return IdentifyCustomerResponse(
                        status=IdentificationStatus.DISAMBIGUATION_REQUIRED,
                        candidates=customers,
                    )

            # No matches found
            return IdentifyCustomerResponse(
                status=IdentificationStatus.NOT_FOUND,
            )

        except Exception as e:
            return IdentifyCustomerResponse(
                status=IdentificationStatus.ERROR,
                error=str(e),
            )

    async def resolve_disambiguation(
        self,
        candidates: list[PlexCustomer],
        user_selection: int,  # 1-based index from user
    ) -> IdentifyCustomerResponse:
        """
        Resolve disambiguation by user selection.

        Args:
            candidates: List of candidate customers
            user_selection: 1-based index selected by user

        Returns:
            IdentifyCustomerResponse with selected customer or error
        """
        try:
            if 1 <= user_selection <= len(candidates):
                return IdentifyCustomerResponse(
                    status=IdentificationStatus.IDENTIFIED,
                    customer=candidates[user_selection - 1],
                )
            return IdentifyCustomerResponse(
                status=IdentificationStatus.ERROR,
                error=f"Invalid selection: {user_selection}. Must be between 1 and {len(candidates)}",
            )
        except Exception as e:
            return IdentifyCustomerResponse(
                status=IdentificationStatus.ERROR,
                error=str(e),
            )

    async def identify_by_document_after_phone_failed(
        self,
        document: str,
    ) -> IdentifyCustomerResponse:
        """
        Secondary identification attempt using document number.

        Called when phone search returns no results or ambiguous results.

        Args:
            document: Document number (DNI) provided by user

        Returns:
            IdentifyCustomerResponse with result
        """
        return await self.execute(
            IdentifyCustomerRequest(document=document)
        )
