"""
Jira Webhook Endpoint - Stub for future Jira integration.

This module provides webhook endpoints for receiving Jira events.
Currently a stub implementation - actual processing will be added
when Jira integration is ready.

Endpoints:
- POST /api/v1/webhooks/jira/{organization_id} - Receive Jira webhooks
"""

import hashlib
import hmac
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks/jira", tags=["jira-webhook"])


@router.post("/{organization_id}")
async def handle_jira_webhook(
    organization_id: UUID,
    request: Request,
    x_atlassian_webhook_identifier: str | None = Header(None, alias="X-Atlassian-Webhook-Identifier"),
) -> dict[str, Any]:
    """
    Handle incoming Jira webhook events.

    STUB IMPLEMENTATION - Logs the webhook but doesn't process it.
    Actual implementation will:
    1. Verify webhook signature
    2. Parse event type
    3. Update corresponding incident

    Args:
        organization_id: Organization UUID for multi-tenant routing
        request: FastAPI request object
        x_atlassian_webhook_identifier: Optional Jira webhook identifier header

    Returns:
        Acknowledgment response

    Supported Events (future):
    - jira:issue_created - When a new issue is created
    - jira:issue_updated - When an issue is updated
    - jira:issue_deleted - When an issue is deleted
    - comment_created - When a comment is added
    - comment_updated - When a comment is updated
    """
    try:
        # Get request body
        body = await request.body()
        payload = await request.json()

        # Log webhook receipt
        webhook_event = payload.get("webhookEvent", "unknown")
        issue_key = payload.get("issue", {}).get("key", "unknown")

        logger.info(
            f"[JIRA WEBHOOK] Received event '{webhook_event}' "
            f"for org {organization_id}, issue {issue_key}"
        )

        # TODO: Implement webhook signature verification
        # The webhook_secret should be stored in soporte.jira_configs
        # signature = request.headers.get("X-Hub-Signature")
        # if signature:
        #     expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        #     if not hmac.compare_digest(f"sha256={expected}", signature):
        #         raise HTTPException(status_code=401, detail="Invalid signature")

        # TODO: Implement event processing
        # Currently just acknowledging receipt
        # Future implementation:
        # async with get_async_db_context() as db:
        #     jira_service = JiraSyncService(db)
        #     result = await jira_service.handle_webhook(payload)

        return {
            "status": "received",
            "organization_id": str(organization_id),
            "webhook_event": webhook_event,
            "issue_key": issue_key,
            "message": "Webhook received. Processing not yet implemented.",
        }

    except Exception as e:
        logger.error(f"[JIRA WEBHOOK] Error processing webhook: {e}")
        # Still return 200 to acknowledge receipt
        return {
            "status": "error",
            "message": f"Error processing webhook: {str(e)}",
        }


@router.get("/{organization_id}/test")
async def test_jira_webhook(organization_id: UUID) -> dict[str, Any]:
    """
    Test endpoint for Jira webhook configuration.

    Use this endpoint to verify that Jira can reach the webhook URL.

    Args:
        organization_id: Organization UUID

    Returns:
        Test response confirming endpoint is reachable
    """
    logger.info(f"[JIRA WEBHOOK] Test endpoint called for org {organization_id}")

    return {
        "status": "ok",
        "organization_id": str(organization_id),
        "message": "Jira webhook endpoint is reachable",
        "webhook_url": f"/api/v1/webhooks/jira/{organization_id}",
    }


@router.get("/health")
async def jira_webhook_health() -> dict[str, Any]:
    """
    Health check for Jira webhook service.

    Returns:
        Health status
    """
    return {
        "status": "healthy",
        "service": "jira-webhook",
        "integration_status": "stub",
        "message": "Jira webhook endpoint is active. Integration pending.",
    }
