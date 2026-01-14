"""
Pharmacy Pattern Matchers

Functions for matching payment patterns using database-driven patterns.
"""

from __future__ import annotations

from typing import Any


def is_payment_intent_from_patterns(
    text_lower: str,
    entities: dict[str, Any],
    patterns: dict[str, Any] | None,
) -> bool:
    """
    Detect payment intent using database patterns.

    Uses patterns from invoice intent in database. Returns False if
    patterns are not available (database not seeded).

    Args:
        text_lower: Lowercase message text
        entities: Extracted entities dictionary
        patterns: Loaded intent patterns from database (can be None)

    Returns:
        True if payment intent detected
    """
    if not patterns:
        return False

    has_amount = entities.get("amount") is not None

    invoice = patterns.get("intents", {}).get("invoice", {})
    if not invoice:
        return False

    # Get lemmas (payment verbs) from database
    db_lemmas = invoice.get("lemmas", [])
    payment_verbs = {lemma.lower() for lemma in db_lemmas if isinstance(lemma, str)}

    # Get phrases from database
    db_phrases = invoice.get("phrases", [])
    payment_phrases = {p["phrase"].lower() for p in db_phrases if isinstance(p, dict) and "phrase" in p}

    if not payment_verbs and not payment_phrases:
        return False

    # Check for payment verb + amount
    has_payment_verb = any(verb in text_lower for verb in payment_verbs)
    if has_payment_verb and has_amount:
        return True

    # Check payment phrases
    return any(phrase in text_lower for phrase in payment_phrases)
