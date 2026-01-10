#!/usr/bin/env python
"""
Test script for confirmation intent detection flow.

Tests that PersonValidationNode._detect_confirmation_intent() correctly
identifies confirm/reject intents using patterns from the database.

Usage:
    uv run python -m app.scripts.test_confirmation_detection
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.core.cache.domain_intent_cache import domain_intent_cache
from app.database.async_db import get_async_db_context

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# System organization UUID
SYSTEM_ORG_ID = UUID("00000000-0000-0000-0000-000000000000")
DOMAIN_KEY = "pharmacy"


async def detect_confirmation_intent(
    message: str,
    confirmation_patterns: dict[str, dict[str, set[str]]],
) -> tuple[str | None, float]:
    """
    Detect confirmation/rejection intent using database patterns.

    This mirrors the logic in PersonValidationNode._detect_confirmation_intent()

    Priority:
    1. Exact matches (highest confidence)
    2. Contains matches (high confidence)
    3. If no pattern match AND multi-word with len > 5, treat as name
    """
    text_lower = message.strip().lower()
    words = text_lower.split()

    # First: Check exact matches (highest priority)
    for intent_key, patterns in confirmation_patterns.items():
        exact_patterns = patterns.get("exact", set())
        if text_lower in exact_patterns:
            return (intent_key, 0.95)

    # Second: Check contains matches
    for intent_key, patterns in confirmation_patterns.items():
        contains_patterns = patterns.get("contains", set())
        for pattern in contains_patterns:
            if pattern in text_lower:
                return (intent_key, 0.85)

    # Third: Multi-word with length > 5 and no pattern match = treat as name
    # This prevents "Si Garcia" from being treated as confirmation
    if len(words) >= 2 and len(text_lower) > 5:
        return (None, 0.0)

    return (None, 0.0)


async def run_tests():
    """Run confirmation detection tests."""

    # Load patterns from database via cache
    async with get_async_db_context() as db:
        patterns = await domain_intent_cache.get_patterns(db, SYSTEM_ORG_ID, DOMAIN_KEY)

    confirmation_patterns = patterns.get("confirmation_patterns", {})

    if not confirmation_patterns:
        logger.error("No confirmation patterns found in database!")
        logger.error("Run: uv run python -m app.scripts.run_seed_intents --domain pharmacy --overwrite")
        return False

    logger.info("Loaded confirmation patterns from database:")
    for intent_key, intent_patterns in confirmation_patterns.items():
        exact = intent_patterns.get("exact", set())
        contains = intent_patterns.get("contains", set())
        logger.info(f"  {intent_key}: exact={len(exact)}, contains={len(contains)}")

    logger.info("-" * 60)

    # Test cases: (input, expected_intent, description)
    test_cases = [
        # Confirm - exact matches
        ("si", "confirm", "Basic 'si'"),
        ("sí", "confirm", "Accented 'sí'"),
        ("s", "confirm", "Single letter 's'"),
        ("ok", "confirm", "English 'ok'"),
        ("yes", "confirm", "English 'yes'"),
        ("1", "confirm", "Number '1'"),
        ("dale", "confirm", "Colloquial 'dale'"),
        ("bueno", "confirm", "Spanish 'bueno'"),
        ("listo", "confirm", "'listo'"),
        ("claro", "confirm", "'claro'"),
        ("perfecto", "confirm", "'perfecto'"),
        ("bien", "confirm", "'bien'"),

        # Confirm - contains matches
        ("si, confirmo", "confirm", "Contains 'confirmo'"),
        ("de acuerdo", "confirm", "Contains 'de acuerdo'"),
        ("esta bien gracias", "confirm", "Contains 'esta bien'"),

        # Reject - exact matches
        ("no", "reject", "Basic 'no'"),
        ("n", "reject", "Single letter 'n'"),
        ("2", "reject", "Number '2'"),

        # Reject - contains matches
        ("quiero cancelar", "reject", "Contains 'cancelar'"),
        ("no quiero eso", "reject", "Contains 'no quiero'"),
        ("esta mal el nombre", "reject", "Contains 'esta mal'"),

        # Should NOT match (treated as names)
        ("Si Garcia", None, "Name with 'Si' prefix - should be name"),
        ("Juan Carlos", None, "Full name - should be name"),
        ("Maria Fernanda Lopez", None, "Long name - should be name"),

        # Edge cases
        ("SI", "confirm", "Uppercase 'SI'"),
        ("NO", "reject", "Uppercase 'NO'"),
        ("  si  ", "confirm", "'si' with spaces"),
        ("hola", None, "Greeting - no match"),
        ("12345678", None, "DNI number - no match"),
    ]

    passed = 0
    failed = 0

    logger.info("Running test cases:")
    logger.info("-" * 60)

    for input_text, expected_intent, description in test_cases:
        intent, confidence = await detect_confirmation_intent(input_text, confirmation_patterns)

        if intent == expected_intent:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1

        conf_str = f"{confidence:.2f}" if confidence > 0 else "----"
        intent_str = intent or "None"
        expected_str = expected_intent or "None"

        logger.info(
            f"{status} | Input: {input_text!r:25} | "
            f"Got: {intent_str:8} ({conf_str}) | "
            f"Expected: {expected_str:8} | {description}"
        )

    logger.info("-" * 60)
    logger.info(f"Results: {passed} passed, {failed} failed")

    return failed == 0


async def main():
    logger.info("=" * 60)
    logger.info("CONFIRMATION INTENT DETECTION TEST")
    logger.info("=" * 60)

    success = await run_tests()

    if success:
        logger.info("\n✅ ALL TESTS PASSED!")
    else:
        logger.error("\n❌ SOME TESTS FAILED!")

    return success


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
