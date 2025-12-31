# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Excepciones para el módulo de integración Chattigo.
# ============================================================================
"""
Chattigo Integration Exceptions.

Single Responsibility: Define exception types for Chattigo operations.
"""


class ChattigoTokenError(Exception):
    """Error obtaining or refreshing Chattigo token."""

    pass


class ChattigoSendError(Exception):
    """Error sending message via Chattigo API."""

    pass


class ChattigoRetryableError(ChattigoSendError):
    """
    Transient error that can be retried (5xx server errors).

    Per Chattigo ISV Documentation (Section 8.1):
    - 500 Internal Server Error: Implement "Exponential Backoff" strategy
    - 502/503/504: Gateway errors, typically transient

    These errors are caught by tenacity's retry decorator for automatic retry.
    """

    pass


class ChattigoRateLimitError(ChattigoSendError):
    """
    Rate limiting error (429 Too Many Requests).

    Should be retried with a longer backoff period, typically
    respecting the Retry-After header if provided.
    """

    pass
