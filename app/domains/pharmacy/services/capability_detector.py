"""
Capability Question Detector

Detects if a user message is asking about the bot's capabilities.
Single responsibility: capability question detection.
"""

from __future__ import annotations


class CapabilityQuestionDetector:
    """
    Detects if a message is asking about bot capabilities.

    Responsibility: Identify messages asking what the bot can do.
    """

    # Phrases that indicate the user is asking about bot capabilities
    CAPABILITY_PHRASES: frozenset[str] = frozenset({
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
        "que sabes hacer",
        "qué sabes hacer",
        # Purpose questions
        "para que sirves",
        "para qué sirves",
        "para que eres",
        "para qué eres",
        # Service questions
        "que servicios",
        "qué servicios",
        "que ofreces",
        "qué ofreces",
        "servicios ofreces",
        # Help questions
        "en que me ayudas",
        "en qué me ayudas",
        "como me ayudas",
        "cómo me ayudas",
        "que me ofreces",
        "qué me ofreces",
        "como puedes ayudar",
        "cómo puedes ayudar",
        # Function questions
        "como funciona",
        "cómo funciona",
        "como funcionas",
        "cómo funcionas",
        # More capability
        "que mas puedes",
        "qué más puedes",
        "que mas haces",
        "qué más haces",
    })

    def is_capability_question(self, text: str) -> bool:
        """
        Check if message is asking about bot capabilities.

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
        return any(phrase in text_lower for phrase in self.CAPABILITY_PHRASES)

    def extract_capability_intent(self, text: str) -> str | None:
        """
        Extract the specific capability-related intent from the message.

        Args:
            text: User message

        Returns:
            The matched capability phrase or None if not a capability question
        """
        if not text:
            return None

        text_lower = text.lower().strip()
        for phrase in self.CAPABILITY_PHRASES:
            if phrase in text_lower:
                return phrase

        return None
