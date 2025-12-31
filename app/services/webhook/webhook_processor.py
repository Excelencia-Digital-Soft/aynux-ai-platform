# ============================================================================
# SCOPE: GLOBAL
# Description: Background processor for webhook messages.
#              Handles heavy business logic asynchronously per Chattigo ISV.
# ============================================================================
"""
Webhook Background Processor.

Per Chattigo ISV Documentation (Section 4.2):
- "Chattigo expects a quick HTTP 200 OK confirmation after delivering the webhook"
- "If business logic is heavy, async architecture is recommended:
   receive webhook, respond 200 OK immediately, queue message internally,
   process in background"

This module provides background processing via FastAPI BackgroundTasks.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from app.config.settings import Settings
from app.integrations.chattigo import ChattigoWebhookPayload
from app.models.message import ChattigoToWhatsAppAdapter, WhatsAppWebhookRequest
from app.models.parsers.whatsapp_webhook_parser import (
    extract_display_phone_number,
    extract_phone_number_id,
    is_status_update,
)
from app.services.webhook.idempotency_service import IdempotencyService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.langgraph_chatbot_service import LangGraphChatbotService

logger = logging.getLogger(__name__)


@dataclass
class WebhookTask:
    """Encapsulates webhook processing context."""

    message_id: str
    payload_type: str  # "whatsapp" or "chattigo"
    raw_json: dict[str, Any]
    settings: Settings


class WebhookProcessor:
    """
    Background processor for webhook messages.

    Handles the heavy business logic asynchronously to meet
    Chattigo's fast response requirement.

    Usage:
        processor = WebhookProcessor(idempotency, get_service, get_db)
        background_tasks.add_task(processor.process_in_background, task)
    """

    def __init__(
        self,
        idempotency_service: IdempotencyService,
        langgraph_service_factory: Callable[[], Awaitable[LangGraphChatbotService]],
        db_session_factory: Callable,
    ):
        self._idempotency = idempotency_service
        self._get_langgraph_service = langgraph_service_factory
        self._get_db_session = db_session_factory

    async def process_in_background(self, task: WebhookTask) -> None:
        """
        Process webhook in background.

        This method is designed to be called via BackgroundTasks.add_task().

        Args:
            task: WebhookTask containing message context
        """
        start_time = time.time()
        logger.info(f"Background processing started: {task.message_id}")

        try:
            async for db_session in self._get_db_session():
                try:
                    if task.payload_type == "whatsapp":
                        await self._process_whatsapp(task, db_session)
                    else:
                        await self._process_chattigo(task, db_session)

                    # Mark as completed
                    await self._idempotency.mark_completed(task.message_id)

                    elapsed = time.time() - start_time
                    logger.info(
                        f"Background processing completed: {task.message_id} "
                        f"(elapsed={elapsed:.2f}s)"
                    )

                except Exception as e:
                    logger.error(
                        f"Background processing failed: {task.message_id} - {e}",
                        exc_info=True,
                    )
                    # Mark as failed to allow retry from Chattigo
                    await self._idempotency.mark_failed(task.message_id)
                finally:
                    break  # Only need one session iteration

        except Exception as e:
            logger.error(
                f"Background task error (session): {task.message_id} - {e}",
                exc_info=True,
            )
            await self._idempotency.mark_failed(task.message_id)

    async def _process_whatsapp(
        self,
        task: WebhookTask,
        db_session: AsyncSession,
    ) -> None:
        """Process WhatsApp format message."""
        from app.domains.shared.application.use_cases.process_webhook_use_case import (
            ProcessWebhookUseCase,
        )

        raw_json = task.raw_json

        try:
            wa_request = WhatsAppWebhookRequest.model_validate(raw_json)
        except Exception as e:
            logger.error(f"Failed to parse WhatsApp format: {e}")
            raise ValueError(f"Invalid WhatsApp format: {e}") from e

        # Skip status updates
        if is_status_update(wa_request):
            logger.debug("Skipping WhatsApp status update in background")
            return

        # Extract message and contact
        message = wa_request.get_message()
        contact = wa_request.get_contact()

        if not message:
            logger.debug("No message in WhatsApp webhook (background)")
            return

        if not contact:
            raise ValueError("Missing contact in WhatsApp webhook")

        # Extract phone number ID and DID for routing
        phone_number_id = extract_phone_number_id(wa_request)
        display_phone_number = extract_display_phone_number(wa_request)

        # Build chattigo context for credential lookup
        chattigo_context = {"did": display_phone_number} if display_phone_number else None

        # Process via Use Case
        service = await self._get_langgraph_service()
        use_case = ProcessWebhookUseCase(
            db=db_session,
            settings=task.settings,
            langgraph_service=service,
        )

        result = await use_case.execute(
            message=message,
            contact=contact,
            whatsapp_phone_number_id=phone_number_id,
            chattigo_context=chattigo_context,
        )

        if result.status != "ok":
            logger.warning(f"WhatsApp processing returned non-ok: {result.status}")

    async def _process_chattigo(
        self,
        task: WebhookTask,
        db_session: AsyncSession,
    ) -> None:
        """Process Chattigo ISV format message."""
        from app.domains.shared.application.use_cases.process_webhook_use_case import (
            ProcessWebhookUseCase,
        )

        raw_json = task.raw_json
        payload = ChattigoWebhookPayload(**raw_json)

        # Skip empty content (status updates)
        if not payload.content and not payload.is_attachment():
            logger.debug("Skipping Chattigo status update in background")
            return

        # Skip OUTBOUND (messages sent by bot)
        if payload.chatType == "OUTBOUND":
            logger.debug("Skipping OUTBOUND message in background")
            return

        if not payload.msisdn:
            raise ValueError("Missing msisdn in Chattigo payload")

        # Store Chattigo context
        chattigo_context = {
            "did": payload.did,
            "idChat": payload.idChat,
            "channelId": payload.channelId,
            "idCampaign": payload.idCampaign,
        }

        # Convert to internal models
        message = ChattigoToWhatsAppAdapter.to_whatsapp_message(
            msisdn=payload.msisdn,
            content=payload.content or "",
            message_id=payload.id or str(int(time.time() * 1000)),
            timestamp=str(int(time.time())),
            message_type=payload.type or "Text",
        )

        contact = ChattigoToWhatsAppAdapter.to_contact(
            msisdn=payload.msisdn,
            name=payload.name,
        )

        # Process via Use Case
        service = await self._get_langgraph_service()
        use_case = ProcessWebhookUseCase(
            db=db_session,
            settings=task.settings,
            langgraph_service=service,
        )

        result = await use_case.execute(
            message=message,
            contact=contact,
            whatsapp_phone_number_id=payload.did,
            chattigo_context=chattigo_context,
        )

        if result.status != "ok":
            logger.warning(f"Chattigo processing returned non-ok: {result.status}")
