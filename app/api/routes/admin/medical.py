# ============================================================================
# SCOPE: MULTI-TENANT
# Description: API de admin para turnos médicos - listar instituciones, testing.
# Tenant-Aware: Yes - lista instituciones de tenant_institution_configs.
# ============================================================================
"""
Medical Admin API - Endpoints for medical appointments testing.

Provides endpoints for the Vue.js medical testing interface.
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.admin.medical_models import (
    InstitutionResponse,
    MedicalTestRequest,
    MedicalTestResponse,
)
from app.config.settings import get_settings
from app.database.async_db import get_async_db
from app.domains.shared.application.use_cases.process_webhook_use_case import (
    ProcessWebhookUseCase,
)
from app.models.message import (
    Contact,
    TextMessage,
    WhatsAppMessage,
)
from app.services.langgraph_chatbot_service import LangGraphChatbotService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/medical", tags=["Medical Admin"])


async def _get_langgraph_service() -> LangGraphChatbotService:
    """Get or create LangGraph service instance."""
    service = LangGraphChatbotService()
    await service.initialize()
    return service


@router.get("/institutions", response_model=list[InstitutionResponse])
async def list_institutions(
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
) -> list[InstitutionResponse]:
    """
    List all available medical institutions for testing.

    Returns institution configurations from the database filtered by type 'medical'
    and having a whatsapp_phone_number_id configured.
    """
    from sqlalchemy import select

    from app.models.db.tenancy.tenant_institution_config import TenantInstitutionConfig

    try:
        # Query directly - don't use get_all_enabled_institutions which filters by scheduler.enabled
        stmt = (
            select(TenantInstitutionConfig)
            .where(TenantInstitutionConfig.enabled == True)  # noqa: E712
            .where(TenantInstitutionConfig.institution_type == "medical")
            .order_by(TenantInstitutionConfig.institution_name)
        )

        result = await db.execute(stmt)
        db_configs = result.scalars().all()

        # Filter and transform to response
        return [
            InstitutionResponse(
                id=str(cfg.id),
                name=cfg.institution_name,
                code=cfg.whatsapp_phone_number_id or "",
                institution_key=cfg.institution_key,
                institution_type=cfg.institution_type,
                active=cfg.enabled,
            )
            for cfg in db_configs
            if cfg.whatsapp_phone_number_id  # Only include institutions with WhatsApp configured
        ]
    except Exception as e:
        logger.error(f"Error listing medical institutions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading institutions: {e}",
        ) from e


@router.post("/test", response_model=MedicalTestResponse)
async def send_test_message(
    request: MedicalTestRequest,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
    settings=Depends(get_settings),  # noqa: B008
) -> MedicalTestResponse:
    """
    Send a test message to the medical appointments agent.

    This endpoint mirrors the EXACT behavior of the original webhook:
    1. Uses whatsapp_phone_number_id (DID) for bypass routing
    2. Bypass routing determines organization_id, institution, domain, target_agent
    3. ProcessWebhookUseCase handles all business logic identically to production

    Args:
        request: MedicalTestRequest with:
            - whatsapp_phone_number_id: Business phone (DID) - REQUIRED
            - phone_number: Customer phone - REQUIRED
            - message: Content to send
            - session_id: Optional existing session
    """
    try:
        # 1. Construct WhatsApp Message (same as webhook_processor.py)
        customer_phone = request.phone_number
        timestamp = str(int(time.time()))
        message_id = str(uuid.uuid4())

        if not request.message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'message' must be provided",
            )

        wa_message = WhatsAppMessage(
            from_=customer_phone,
            id=message_id,
            timestamp=timestamp,
            type="text",
            text=TextMessage(body=request.message),
        )

        contact = Contact(wa_id=customer_phone, profile={"name": "Test User"})

        # 2. Execute Use Case - IDENTICAL to original webhook
        # The DID triggers bypass routing which determines organization/institution
        langgraph_service = await _get_langgraph_service()
        use_case = ProcessWebhookUseCase(db, settings, langgraph_service)

        logger.info(
            f"[TEST_MEDICAL] Processing test message: did={request.whatsapp_phone_number_id}, "
            f"phone={customer_phone}"
        )

        result = await use_case.execute(
            message=wa_message,
            contact=contact,
            whatsapp_phone_number_id=request.whatsapp_phone_number_id,
        )

        if result.status == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing webhook: {result.error_message}",
            )

        # 3. Extract Response Data
        bot_response = result.result
        response_text = bot_response.message if bot_response else ""
        metadata = bot_response.metadata if bot_response else {}
        if metadata is None:
            metadata = {}

        # The graph result contains the full execution state
        graph_result = metadata.get("graph_result", {})

        # Determine the actual session ID used
        real_session_id = metadata.get(
            "conversation_id", request.session_id or f"whatsapp_{customer_phone}"
        )

        # Extract organization_id safely
        org_id = metadata.get("organization_id")

        return MedicalTestResponse(
            session_id=real_session_id,
            response=response_text,
            response_type="text",
            execution_steps=[
                {
                    "workflow_step": graph_result.get("workflow_step"),
                    "next_agent": graph_result.get("next_agent"),
                    "agent_used": metadata.get("agent_used"),
                }
            ],
            metadata={
                "whatsapp_phone_number_id": request.whatsapp_phone_number_id,
                "organization_id": str(org_id) if org_id else None,
                "processing_mode": result.mode,
                "domain": result.domain,
                "bypass_matched": result.domain != ProcessWebhookUseCase.DEFAULT_DOMAIN,
                "agent_used": metadata.get("agent_used"),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in medical test: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing test message: {e}",
        ) from e
