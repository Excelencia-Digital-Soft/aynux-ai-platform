"""
Pharmacy Fallback Handler - Facade

Facade pattern that maintains backward compatibility with PharmacyGraph
by delegating to specialized handlers.

Original monolithic handler (688 lines) has been refactored into:
- handlers/base_handler.py - Shared ResponseGenerator utilities
- handlers/greeting_handler.py - Greeting messages
- handlers/summary_handler.py - Summary generation
- handlers/data_query_handler.py - Data analysis queries
- handlers/fallback_handler.py - Unknown, error, cancelled
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.domains.pharmacy.agents.utils.response_generator import get_response_generator

from .handlers import (
    DataQueryHandler,
    FallbackHandler,
    GreetingHandler,
    PharmacyInfoHandler,
    SummaryHandler,
)

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.utils.response_generator import (
        PharmacyResponseGenerator,
    )

logger = logging.getLogger(__name__)


class PharmacyFallbackHandler:
    """
    Facade for pharmacy domain handlers.

    Maintains backward compatibility with existing PharmacyGraph code
    by delegating to specialized handlers. Each handler follows SRP.
    """

    def __init__(self, response_generator: PharmacyResponseGenerator | None = None):
        """
        Initialize all handlers with shared ResponseGenerator.

        Args:
            response_generator: ResponseGenerator instance (creates one if not provided)
        """
        rg = response_generator or get_response_generator()
        self._greeting = GreetingHandler(rg)
        self._summary = SummaryHandler(rg)
        self._data_query = DataQueryHandler(rg)
        self._info = PharmacyInfoHandler(rg)
        self._fallback = FallbackHandler(rg)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def handle_greeting(
        self,
        message: str,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Handle greeting message."""
        return await self._greeting.handle(message, state)

    async def handle_summary(
        self,
        message: str,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Handle summary request."""
        return await self._summary.handle(message, state)

    async def handle_data_query(
        self,
        message: str,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Handle data analysis query."""
        return await self._data_query.handle(message, state)

    async def handle_info_query(
        self,
        message: str,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Handle pharmacy info query (address, phone, hours, etc.)."""
        return await self._info.handle(message, state)

    async def handle_unknown(
        self,
        message: str,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Handle unknown/out-of-scope message."""
        return await self._fallback.handle_unknown(message, state)

    async def handle_out_of_scope(
        self,
        message: str,
        suggested_response: str | None = None,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Handle out-of-scope message."""
        return await self._fallback.handle_out_of_scope(message, suggested_response, state)

    async def handle_error(
        self,
        error: str | Exception,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Handle processing error."""
        return await self._fallback.handle_error(error, state)

    async def handle_cancelled(
        self,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Handle user cancellation."""
        return await self._fallback.handle_cancelled(state)
