"""
Pharmacy Pattern Matchers

Functions for matching confirmation, greeting, and payment patterns.
"""

from __future__ import annotations

from typing import Any

from app.domains.pharmacy.agents.intent_patterns import (
    CONFIDENCE_CONTAINS,
    CONFIDENCE_EXACT_MATCH,
    CONFIRMATION_PATTERNS,
    GREETING_EXACT,
    GREETING_PREFIXES,
    PAYMENT_PHRASES,
    PAYMENT_VERBS,
)
from app.domains.pharmacy.agents.intent_result import PharmacyIntentResult


def match_confirmation(text_lower: str) -> PharmacyIntentResult | None:
    """
    Match confirmation/rejection patterns.

    Args:
        text_lower: Lowercase message text

    Returns:
        PharmacyIntentResult if matched, None otherwise
    """
    for intent, patterns in CONFIRMATION_PATTERNS.items():
        # Check exact matches first
        if text_lower in patterns["exact"]:
            return create_match_result(intent, CONFIDENCE_EXACT_MATCH, "exact", text_lower)

        # Check contains patterns
        for pattern in patterns["contains"]:
            if pattern in text_lower:
                return create_match_result(intent, CONFIDENCE_CONTAINS, "contains", pattern)

    return None


def match_greeting(text_lower: str) -> PharmacyIntentResult | None:
    """
    Match greeting patterns with high priority.

    This runs BEFORE general intent scoring to ensure greetings are
    always detected reliably, even for short messages like "hola".

    Args:
        text_lower: Lowercase message text

    Returns:
        PharmacyIntentResult if matched, None otherwise
    """
    # Exact match (highest confidence)
    if text_lower in GREETING_EXACT:
        return PharmacyIntentResult(
            intent="greeting",
            confidence=CONFIDENCE_EXACT_MATCH,
            is_out_of_scope=False,
            entities={},
            method="greeting_priority",
            analysis={"matched_pattern": text_lower, "match_type": "exact"},
        )

    # Prefix match (high confidence)
    for prefix in GREETING_PREFIXES:
        if text_lower.startswith(prefix):
            return PharmacyIntentResult(
                intent="greeting",
                confidence=CONFIDENCE_CONTAINS,
                is_out_of_scope=False,
                entities={},
                method="greeting_priority",
                analysis={"matched_pattern": prefix, "match_type": "prefix"},
            )

    return None


def is_payment_intent(text_lower: str, entities: dict[str, Any]) -> bool:
    """
    Detect if the message is clearly a payment intent.

    This runs with high priority to catch patterns like "pagar 50 mil"
    that would otherwise be misclassified as data_query.

    Args:
        text_lower: Lowercase message text
        entities: Extracted entities dictionary

    Returns:
        True if payment intent detected
    """
    has_payment_verb = any(verb in text_lower for verb in PAYMENT_VERBS)
    has_amount = entities.get("amount") is not None

    # "pagar X" with amount = definitely payment
    if has_payment_verb and has_amount:
        return True

    # Explicit payment phrases (with and without amount)
    return any(phrase in text_lower for phrase in PAYMENT_PHRASES)


def create_match_result(
    intent: str,
    confidence: float,
    match_type: str,
    pattern: str,
) -> PharmacyIntentResult:
    """
    Factory for pattern match results.

    Args:
        intent: Detected intent
        confidence: Confidence score
        match_type: Type of match (exact, contains, prefix)
        pattern: Pattern that matched

    Returns:
        PharmacyIntentResult instance
    """
    return PharmacyIntentResult(
        intent=intent,
        confidence=confidence,
        is_out_of_scope=False,
        entities={},
        method="pattern_match",
        analysis={"matched_pattern": pattern, "match_type": match_type},
    )
