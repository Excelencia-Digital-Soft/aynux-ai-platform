"""
Capability Question Detector

Detects if a user message is asking about the bot's capabilities.
Single responsibility: capability question detection.

Supports database patterns via capability_question intent when available.
"""

from __future__ import annotations

from typing import Any


class CapabilityQuestionDetector:
    """
    Detects if a message is asking about bot capabilities.

    Responsibility: Identify messages asking what the bot can do.
    Supports database-driven patterns when available, with hardcoded fallback.
    """

    # Hardcoded fallback phrases (used when DB patterns not available)
    CAPABILITY_PHRASES: frozenset[str] = frozenset(
        {
            # Direct capability questions
            "que puedes hacer",
            "qué puedes hacer",
            "que puedes",
            "qué puedes",
            "puedes hacer",
            "que haces",
            "qué haces",
            "que sabes",
            "qué sabes",
            # Purpose questions
            "para que sirves",
            "para qué sirves",
            # Service questions
            "que servicios",
            "qué servicios",
            "que ofreces",
            "qué ofreces",
            # Help questions
            "en que me ayudas",
            "en qué me ayudas",
            "como puedes ayudar",
            "cómo puedes ayudar",
            # Function questions
            "como funciona",
            "cómo funciona",
        }
    )

    def __init__(self, patterns: dict[str, Any] | None = None):
        """
        Initialize detector with optional database patterns.

        Args:
            patterns: Optional patterns dict loaded from database cache.
                      If provided, uses capability_question intent phrases.
        """
        self._patterns = patterns
        self._db_phrases: set[str] | None = None

        if patterns:
            capability = patterns.get("intents", {}).get("capability_question", {})
            phrases = capability.get("phrases", [])
            if phrases:
                self._db_phrases = {p["phrase"].lower() for p in phrases if isinstance(p, dict) and "phrase" in p}

    def is_capability_question(self, text: str) -> bool:
        """
        Check if message is asking about bot capabilities.

        Uses database patterns when available, falls back to hardcoded patterns.
        These phrases indicate the user is asking what the bot can do,
        not requesting pharmacy contact information.

        Args:
            text: User message to check

        Returns:
            True if asking about bot capabilities
        """
        if not text:
            return False

        text_lower = text.lower().strip()

        # Use database patterns if available
        if self._db_phrases:
            return any(phrase in text_lower for phrase in self._db_phrases)

        # Fallback to hardcoded patterns
        return any(phrase in text_lower for phrase in self.CAPABILITY_PHRASES)

    def extract_capability_intent(self, text: str) -> str | None:
        """
        Extract the specific capability-related intent from the message.

        Uses database patterns when available.

        Args:
            text: User message

        Returns:
            The matched capability phrase or None if not a capability question
        """
        if not text:
            return None

        text_lower = text.lower().strip()

        # Check database patterns first
        if self._db_phrases:
            for phrase in self._db_phrases:
                if phrase in text_lower:
                    return phrase
            return None

        # Fallback to hardcoded
        for phrase in self.CAPABILITY_PHRASES:
            if phrase in text_lower:
                return phrase

        return None
