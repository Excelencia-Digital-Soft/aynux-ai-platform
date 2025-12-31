# ============================================================================
# SCOPE: GLOBAL
# Description: Webhook services for idempotency and background processing.
#              Implements Chattigo ISV requirements for fast response and dedup.
# ============================================================================
"""
Webhook Services Module.

Provides:
- IdempotencyService: Redis-based duplicate detection (SET NX)
- WebhookProcessor: Background message processing
"""

from app.services.webhook.idempotency_service import (
    IdempotencyResult,
    IdempotencyService,
    IdempotencyState,
    ProcessingState,
)
from app.services.webhook.webhook_processor import WebhookProcessor, WebhookTask

__all__ = [
    "IdempotencyService",
    "IdempotencyResult",
    "IdempotencyState",
    "ProcessingState",
    "WebhookProcessor",
    "WebhookTask",
]
