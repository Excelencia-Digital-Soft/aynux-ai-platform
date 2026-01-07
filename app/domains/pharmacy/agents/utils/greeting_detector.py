"""
Greeting Detector

Detects if a message is purely a greeting or contains additional content.
Single responsibility: greeting detection and classification.
"""

from __future__ import annotations


class GreetingDetector:
    """
    Detects if a message is purely a greeting or contains additional content.

    Responsibility: Determine if user input is just a greeting or has meaningful content.
    """

    # Pure greeting messages (no additional content)
    PURE_GREETINGS: frozenset[str] = frozenset({
        "hola",
        "hey",
        "buenas",
        "buenos dias",
        "buen dia",
        "buen día",
        "buenos días",
        "buenas tardes",
        "buenas noches",
        "saludos",
        "que tal",
        "qué tal",
        "como estas",
        "cómo estás",
        "hi",
        "hello",
    })

    # Greeting prefixes that might have additional content
    GREETING_PREFIXES: tuple[str, ...] = (
        "hola ",
        "buenas ",
        "buenos ",
        "hey ",
        "saludos ",
    )

    # Minimum length to assume additional content exists
    MIN_LENGTH_FOR_CONTENT = 20

    def has_content_beyond_greeting(self, message: str | None) -> bool:
        """
        Check if message has meaningful content beyond just a greeting.

        Args:
            message: User message to check

        Returns:
            True if message contains content beyond a simple greeting
        """
        if not message:
            return False

        text = message.lower().strip()

        if not text:
            return False

        # If it's just a greeting, no additional content
        if text in self.PURE_GREETINGS:
            return False

        # If message is longer than typical greeting, there's likely more content
        if len(text) > self.MIN_LENGTH_FOR_CONTENT:
            return True

        # Check if starts with greeting but has more
        for prefix in self.GREETING_PREFIXES:
            if text.startswith(prefix):
                remaining = text[len(prefix):].strip()
                if remaining:
                    return True

        # If message doesn't start with any greeting prefix and isn't a pure greeting,
        # then it has meaningful content (e.g., "quiero ver mi deuda")
        has_greeting_prefix = any(text.startswith(p) for p in self.GREETING_PREFIXES)
        if not has_greeting_prefix:
            return True

        return False

    def is_pure_greeting(self, message: str | None) -> bool:
        """
        Check if message is a pure greeting with no additional content.

        Args:
            message: User message to check

        Returns:
            True if message is only a greeting
        """
        return not self.has_content_beyond_greeting(message)

    def extract_greeting_prefix(self, message: str | None) -> str | None:
        """
        Extract the greeting prefix from a message if present.

        Args:
            message: User message to check

        Returns:
            The greeting prefix or None if no prefix found
        """
        if not message:
            return None

        text = message.lower().strip()

        # Check pure greetings
        if text in self.PURE_GREETINGS:
            return text

        # Check greeting prefixes
        for prefix in self.GREETING_PREFIXES:
            if text.startswith(prefix):
                return prefix.strip()

        return None
