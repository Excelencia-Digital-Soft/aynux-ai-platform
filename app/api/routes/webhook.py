# ============================================================================
# SCOPE: MIXED (Dual-mode: Global + Multi-tenant)
# Description: Webhook de WhatsApp con soporte dual-mode automático.
#              Sin token = modo global. Con token = carga config de DB por tenant.
# Tenant-Aware: Yes - detecta TenantContext y carga TenantAgentRegistry si existe.
# ============================================================================
"""
✅ CLEAN ARCHITECTURE - Webhook Endpoints (VERSION 2)

This is the new version of webhook.py that uses Clean Architecture patterns.
Replaces legacy webhook.py which used deprecated domain_detector and domain_manager services.

DUAL-MODE SUPPORT:
  ✅ Global mode (no token): Uses Python default agent configurations
  ✅ Multi-tenant mode (with token): Loads agent config from database per-request

MIGRATION STATUS:
  ✅ Uses Admin Use Cases for domain detection
  ✅ Uses LangGraphChatbotService (already Clean Architecture compliant)
  ✅ Follows Dependency Injection via DependencyContainer
  ✅ Proper error handling with structured responses
  ✅ Maintains API contract compatibility with webhook.py

ENDPOINTS MIGRATED:
  ✅ GET /webhook → WhatsApp webhook verification (no dependencies)
  ✅ POST /webhook → Message processing using Clean Architecture
  ✅ GET /webhook/health → LangGraph health check (already Clean)
  ✅ GET /webhook/conversation/{user_number} → Conversation history (already Clean)

ARCHITECTURE IMPROVEMENTS:
  ✅ No deprecated services (removed domain_detector, domain_manager, super_orchestrator_service)
  ✅ Single Responsibility: Each function does one thing
  ✅ Dependency Injection: Use Cases injected via DependencyContainer
  ✅ Clear separation: API layer delegates to Application layer (Use Cases + Services)

READY TO REPLACE: webhook.py can now be replaced with this file
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings
from app.core.container import DependencyContainer
from app.core.tenancy.context import get_tenant_context
from app.core.tenancy.credential_service import (
    CredentialNotFoundError,
    get_credential_service,
)
from app.database.async_db import get_async_db
from app.models.db.tenancy import Organization
from app.models.message import BotResponse, WhatsAppWebhookRequest
from app.services.langgraph_chatbot_service import LangGraphChatbotService

router = APIRouter(tags=["webhook"])
logger = logging.getLogger(__name__)

# LangGraph Service (initialized lazily)
_langgraph_service: Optional[LangGraphChatbotService] = None


# ============================================================
# WEBHOOK VERIFICATION ENDPOINT
# ============================================================


@router.get("/webhook/")
@router.get("/webhook")
async def verify_webhook(
    request: Request,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
):
    """
    Verifica el webhook para WhatsApp.

    Esta ruta es llamada por WhatsApp para verificar que el webhook esté configurado correctamente.

    CREDENTIAL RESOLUTION:
    1. If org_id query param provided → load verify_token from DB for that org
    2. If no org_id → load from default organization (slug='excelencia' or 'system')
    3. Compare provided token with stored token

    The webhook URL should include org_id for multi-tenant deployments:
    https://yourdomain.com/webhook?org_id=<organization-uuid>
    """
    query_params = dict(request.query_params)

    # Parámetros de verificación de WhatsApp
    mode = query_params.get("hub.mode")
    token = query_params.get("hub.verify_token")
    challenge = query_params.get("hub.challenge")

    if not mode or not token:
        logger.warning("MISSING_PARAMETER")
        raise HTTPException(status_code=400, detail="Missing required parameters")

    if mode != "subscribe":
        logger.warning(f"INVALID_MODE: {mode}")
        raise HTTPException(status_code=400, detail="Invalid mode")

    # Resolver organización
    org_id = await _resolve_organization_for_webhook(
        db=db,
        query_params=query_params,
        headers=dict(request.headers),
    )

    # Obtener verify_token esperado desde base de datos
    expected_token = await _get_expected_verify_token(db, org_id)

    # Verificar token
    if token == expected_token:
        logger.info(f"WEBHOOK_VERIFIED for org {org_id}")
        return PlainTextResponse(content=challenge)
    else:
        logger.warning(f"VERIFICATION_FAILED for org {org_id}")
        raise HTTPException(status_code=403, detail="Verification failed: token mismatch")


async def _resolve_organization_for_webhook(
    db: AsyncSession,
    query_params: dict,
    headers: dict,
) -> UUID:
    """
    Resolve organization ID for webhook verification.

    Priority:
    1. Query parameter: org_id
    2. Header: X-Organization-ID
    3. Default organization (excelencia or system)

    Args:
        db: Database session
        query_params: Query parameters from request
        headers: HTTP headers from request

    Returns:
        Organization UUID

    Raises:
        HTTPException: If no organization can be resolved
    """
    # Try query parameter
    org_id_str = query_params.get("org_id")
    if org_id_str:
        try:
            return UUID(org_id_str)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid org_id format: {org_id_str}"
            ) from e

    # Try header
    org_id_header = headers.get("x-organization-id")
    if org_id_header:
        try:
            return UUID(org_id_header)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid X-Organization-ID format: {org_id_header}"
            ) from e

    # Fallback to default organization
    default_org = await _get_default_organization(db)
    if default_org:
        return UUID(str(default_org.id))

    raise HTTPException(
        status_code=404,
        detail="No organization found. Provide org_id query param or create default organization.",
    )


async def _get_default_organization(db: AsyncSession) -> Organization | None:
    """
    Get the default organization for global mode.

    Tries 'excelencia' first, then 'system'.
    """
    for slug in ["excelencia", "system"]:
        result = await db.execute(
            select(Organization).where(Organization.slug == slug)
        )
        org = result.scalar_one_or_none()
        if org:
            return org
    return None


async def _get_expected_verify_token(db: AsyncSession, org_id: UUID) -> str:
    """
    Get the expected verify token for an organization from the database.

    Args:
        db: Database session
        org_id: Organization UUID

    Returns:
        Expected verify token string

    Raises:
        HTTPException: If credentials not found or incomplete
    """
    credential_service = get_credential_service()

    try:
        creds = await credential_service.get_whatsapp_credentials(db, org_id)
        return creds.verify_token
    except CredentialNotFoundError as e:
        logger.error(f"Credentials not found for org {org_id}: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"WhatsApp credentials not configured for organization {org_id}. "
            "Use the Admin API to configure credentials.",
        ) from e
    except ValueError as e:
        logger.error(f"Incomplete credentials for org {org_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Incomplete WhatsApp credentials for organization {org_id}: {e}",
        ) from e


# ============================================================
# MESSAGE PROCESSING ENDPOINT (MAIN WEBHOOK)
# ============================================================


async def _get_langgraph_service() -> LangGraphChatbotService:
    """
    Obtiene el servicio LangGraph (lazy initialization).

    Returns:
        LangGraphChatbotService instance
    """
    global _langgraph_service

    if _langgraph_service is None:
        _langgraph_service = LangGraphChatbotService()
        try:
            await _langgraph_service.initialize()
            logger.info("LangGraph service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LangGraph service: {e}")
            raise
    return _langgraph_service


@router.post("/webhook/")
@router.post("/webhook")
async def process_webhook(
    request: WhatsAppWebhookRequest = Body(...),  # noqa: B008
    db_session: AsyncSession = Depends(get_async_db),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
):
    """
    Procesa las notificaciones del webhook de WhatsApp con Clean Architecture.

    DUAL-MODE SUPPORT:
    - Global mode: No tenant context → uses Python default configs
    - Multi-tenant mode: Has tenant context → loads agent config from database

    Esta versión usa:
    - GetContactDomainUseCase para detección de dominio
    - LangGraphChatbotService para procesamiento (ya usa Clean Architecture)
    - TenantAgentService para cargar configuración de agentes (multi-tenant mode)

    Args:
        request: WhatsApp webhook request payload
        db_session: Async database session
        settings: Application settings

    Returns:
        Processing result with status and response
    """

    # Verificar si es una actualización de estado
    if _is_status_update(request):
        logger.info("Received a WhatsApp status update")
        return {"status": "ok", "type": "status_update"}

    # Extraer mensaje y contacto
    message = request.get_message()
    contact = request.get_contact()

    if not message or not contact:
        logger.warning("Invalid webhook payload: missing message or contact")
        return {"status": "error", "message": "Invalid webhook payload"}

    wa_id = contact.wa_id
    logger.info(f"Processing message from WhatsApp ID: {wa_id}")

    # PASO 1: Detectar dominio del contacto usando Use Case
    domain = await _detect_contact_domain(wa_id, db_session)
    logger.info(f"Contact domain detected: {wa_id} -> {domain}")

    # PASO 2: Load tenant registry if in multi-tenant mode
    service = await _get_langgraph_service()
    tenant_registry = None
    mode = "global"

    if settings.MULTI_TENANT_MODE:
        tenant_registry = await _load_tenant_registry_if_available(db_session)
        if tenant_registry:
            mode = "multi_tenant"
            service.set_tenant_registry_for_request(tenant_registry)
            logger.info(f"Processing in multi-tenant mode for org: {tenant_registry.organization_id}")
        else:
            logger.info("No tenant context found, processing in global mode")

    # PASO 3: Procesar mensaje con LangGraph Service
    try:
        # LangGraphChatbotService ya usa Clean Architecture internamente
        result: BotResponse = await service.process_webhook_message(
            message=message, contact=contact, business_domain=domain, db_session=db_session
        )

        logger.info(f"Message processed successfully: {result.status}")

        # Reset tenant config after processing (cleanup)
        if mode == "multi_tenant":
            service.reset_tenant_config()

        return {"status": "ok", "result": result, "domain": domain, "mode": mode}

    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)

        # Intentar fallback con dominio por defecto
        try:
            logger.info("Attempting fallback to default domain (ecommerce)")
            result: BotResponse = await service.process_webhook_message(
                message=message, contact=contact, business_domain="ecommerce", db_session=db_session
            )

            # Reset tenant config after processing
            if mode == "multi_tenant":
                service.reset_tenant_config()

            return {"status": "ok", "result": result, "domain": "ecommerce", "method": "fallback", "mode": mode}

        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {fallback_error}", exc_info=True)
            # Ensure cleanup even on error
            if mode == "multi_tenant":
                service.reset_tenant_config()
            return {
                "status": "error",
                "message": str(e),
                "fallback_error": str(fallback_error),
            }


async def _load_tenant_registry_if_available(db_session: AsyncSession):
    """
    Load tenant agent registry from database if tenant context is available.

    In multi-tenant mode, this loads the agent configuration for the current
    tenant from the database. In global mode, returns None.

    Args:
        db_session: Async database session

    Returns:
        TenantAgentRegistry or None if no tenant context
    """
    try:
        # Get current tenant context (set by middleware)
        ctx = get_tenant_context()
        if not ctx or not ctx.organization_id:
            logger.debug("No tenant context available, using global mode")
            return None

        # Load tenant registry using TenantAgentService
        from app.core.tenancy.agent_service import TenantAgentService

        service = TenantAgentService(db=db_session)
        registry = await service.get_agent_registry(ctx.organization_id)

        logger.info(f"Loaded tenant registry for org {ctx.organization_id}")
        return registry

    except ImportError as e:
        logger.warning(f"TenantAgentService not available: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error loading tenant registry: {e}")
        return None


async def _detect_contact_domain(wa_id: str, db_session: AsyncSession) -> str:
    """
    Detecta el dominio asignado a un contacto usando Clean Architecture Use Case.

    Args:
        wa_id: WhatsApp ID del contacto
        db_session: Sesión de base de datos

    Returns:
        Nombre del dominio (ecommerce, healthcare, credit, etc.)
    """
    try:
        # Usar GetContactDomainUseCase en lugar de domain_detector deprecated
        container = DependencyContainer()
        use_case = container.create_get_contact_domain_use_case(db_session)

        result = await use_case.execute(wa_id=wa_id)

        if result["status"] == "assigned":
            domain = result["domain_info"]["domain"]
            logger.info(f"Found existing domain assignment: {wa_id} -> {domain}")
            return domain
        else:
            # No tiene dominio asignado, usar por defecto
            logger.info(f"No domain assignment found for {wa_id}, using default: ecommerce")
            return "ecommerce"

    except Exception as e:
        logger.error(f"Error detecting contact domain: {e}", exc_info=True)
        # Fallback al dominio por defecto en caso de error
        return "ecommerce"


def _is_status_update(request: WhatsAppWebhookRequest) -> bool:
    """
    Verifica si la solicitud es una actualización de estado.

    Args:
        request: WhatsApp webhook request

    Returns:
        True si es actualización de estado, False si es mensaje
    """
    try:
        return bool(request.entry[0].changes[0].value.get("statuses"))
    except (IndexError, AttributeError, KeyError):
        return False


# ============================================================
# HEALTH & MONITORING ENDPOINTS
# ============================================================


@router.get("/webhook/health")
async def health_check():
    """
    Endpoint para verificar el estado del sistema LangGraph.

    Ya usa Clean Architecture (LangGraphChatbotService).
    No requiere migración.
    """
    try:
        service = await _get_langgraph_service()
        health_status = await service.get_system_health()
        overall_status = (
            health_status.get("overall_status", "unknown")
            if isinstance(health_status, dict)
            else ("healthy" if health_status else "unhealthy")
        )
        return {"service_type": "langgraph", "status": overall_status, "details": health_status}
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {"service_type": "langgraph", "status": "unhealthy", "error": str(e)}


@router.get("/webhook/conversation/{user_number}")
async def get_conversation_history(user_number: str, limit: int = 50):
    """
    Obtiene el historial de conversación para un usuario usando LangGraph.

    Ya usa Clean Architecture (LangGraphChatbotService).
    No requiere migración.

    Args:
        user_number: WhatsApp ID del usuario
        limit: Número máximo de mensajes a retornar

    Returns:
        Historial de conversación
    """
    try:
        service = await _get_langgraph_service()
        history = await service.get_conversation_history_langgraph(user_number, limit)
        return history
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}", exc_info=True)
        return {"error": str(e)}
