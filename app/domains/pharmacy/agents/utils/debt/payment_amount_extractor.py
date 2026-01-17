# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Payment amount extraction from user messages.
#              Extracted from debt_manager_node._extract_payment_amount().
# Tenant-Aware: Yes - loads patterns from database per organization.
# ============================================================================
"""
Payment amount extraction utilities.

This module provides utilities for extracting payment amounts from
user messages using database-driven patterns with fallback support.

Single Responsibility: Extract payment amounts from messages.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class PaymentPatternProvider:
    """
    Provides payment amount extraction patterns.

    Single Responsibility: Load and provide regex patterns for amount extraction.
    """

    # Fallback patterns for resilience
    FALLBACK_PATTERNS: list[str] = [
        r"pagar\s*\$?\s*(\d+)",
        r"(\d+)\s*(?:pesos?|pe)",
        r"\$\s*(\d+)",
        r"monto\s*(?:de\s*)?\s*(\d+)",
    ]

    @staticmethod
    async def get_patterns(
        db: "AsyncSession | None",
        organization_id: UUID,
    ) -> list[str]:
        """
        Get payment amount patterns from database with fallback.

        Args:
            db: Database session (optional)
            organization_id: Organization UUID for multi-tenant support

        Returns:
            List of regex patterns for amount extraction
        """
        if db is None:
            logger.debug("No DB session, using fallback patterns")
            return PaymentPatternProvider.FALLBACK_PATTERNS

        try:
            from app.core.cache.domain_intent_cache import domain_intent_cache

            patterns = await domain_intent_cache.get_patterns(db, organization_id, "pharmacy")

            # Look for payment_amount intent patterns
            payment_intent = patterns.get("intents", {}).get("payment_amount", {})
            db_phrases = payment_intent.get("phrases", [])

            # Extract regex patterns from phrases
            regex_patterns: list[str] = []
            for phrase_obj in db_phrases:
                if isinstance(phrase_obj, dict):
                    phrase = phrase_obj.get("phrase", "")
                    match_type = phrase_obj.get("match_type", "")
                    if phrase and match_type == "regex":
                        regex_patterns.append(phrase)

            if regex_patterns:
                logger.debug(f"Loaded {len(regex_patterns)} patterns from database")
                return regex_patterns

            logger.debug("No payment_amount patterns in DB, using fallback")
            return PaymentPatternProvider.FALLBACK_PATTERNS

        except Exception as e:
            logger.warning(f"Failed to load payment patterns from DB: {e}")
            return PaymentPatternProvider.FALLBACK_PATTERNS


class PaymentAmountExtractor:
    """
    Extracts payment amounts from user messages.

    Single Responsibility: Parse user messages to extract payment amounts.

    Supports patterns like:
    - "quiero pagar 3000"
    - "pagar $3.000"
    - "3000 pesos"
    """

    @staticmethod
    async def extract(
        db: "AsyncSession | None",
        organization_id: UUID,
        message: str,
    ) -> float | None:
        """
        Extract payment amount from user message.

        Args:
            db: Database session for pattern loading
            organization_id: Organization UUID for multi-tenant support
            message: User message to extract amount from

        Returns:
            Extracted amount as float, or None if no amount found
        """
        # Normalize text (remove formatting)
        text = PaymentAmountExtractor._normalize_text(message)

        # Get patterns (from DB or fallback)
        patterns = await PaymentPatternProvider.get_patterns(db, organization_id)

        # Try to match amount
        return PaymentAmountExtractor._match_amount(text, patterns)

    @staticmethod
    def _normalize_text(message: str) -> str:
        """
        Normalize text for pattern matching.

        Removes dots and commas used as thousand separators.

        Args:
            message: Original message

        Returns:
            Normalized lowercase text
        """
        return message.lower().replace(".", "").replace(",", "")

    @staticmethod
    def _match_amount(text: str, patterns: list[str]) -> float | None:
        """
        Match amount using provided patterns.

        Args:
            text: Normalized text to search
            patterns: List of regex patterns

        Returns:
            First valid amount found, or None
        """
        for pattern in patterns:
            try:
                match = re.search(pattern, text)
                if match:
                    amount = float(match.group(1))
                    if amount > 0:
                        logger.debug(f"Extracted amount {amount} with pattern: {pattern}")
                        return amount
            except (ValueError, IndexError, re.error) as e:
                logger.debug(f"Pattern match failed for '{pattern}': {e}")
                continue

        return None
