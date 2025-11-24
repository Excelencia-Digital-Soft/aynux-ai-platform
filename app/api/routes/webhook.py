"""
✅ CLEAN ARCHITECTURE - Webhook Endpoints (VERSION 2)

This is the new version of webhook.py that uses Clean Architecture patterns.
Replaces legacy webhook.py which used deprecated domain_detector and domain_manager services.

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

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings
from app.core.container import DependencyContainer
from app.database.async_db import get_async_db
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
    settings: Settings = Depends(get_settings),  # noqa: B008
):
    """
    Verifica el webhook para WhatsApp.

    Esta ruta es llamada por WhatsApp para verificar que el webhook esté configurado correctamente.
    No requiere migración - es lógica simple sin dependencias.
    """
    query_params = dict(request.query_params)

    # Parámetros de verificación de WhatsApp
    mode = query_params.get("hub.mode")
    token = query_params.get("hub.verify_token")
    challenge = query_params.get("hub.challenge")

    # Verificar que los parámetros sean correctos
    if mode and token:
        if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
            logger.info("WEBHOOK_VERIFIED")
            return PlainTextResponse(content=challenge)
        else:
            logger.warning("VERIFICATION_FAILED")
            raise HTTPException(status_code=403, detail="Verification failed: token mismatch")
    else:
        logger.warning("MISSING_PARAMETER")
        raise HTTPException(status_code=400, detail="Missing required parameters")


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
):
    """
    Procesa las notificaciones del webhook de WhatsApp con Clean Architecture.

    Esta versión usa:
    - GetContactDomainUseCase para detección de dominio
    - LangGraphChatbotService para procesamiento (ya usa Clean Architecture)

    Args:
        request: WhatsApp webhook request payload
        db_session: Async database session

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

    # PASO 2: Procesar mensaje con LangGraph Service
    try:
        service = await _get_langgraph_service()

        # LangGraphChatbotService ya usa Clean Architecture internamente
        result: BotResponse = await service.process_webhook_message(
            message=message, contact=contact, business_domain=domain
        )

        logger.info(f"Message processed successfully: {result.status}")
        return {"status": "ok", "result": result, "domain": domain}

    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)

        # Intentar fallback con dominio por defecto
        try:
            logger.info("Attempting fallback to default domain (ecommerce)")
            service = await _get_langgraph_service()
            result: BotResponse = await service.process_webhook_message(
                message=message, contact=contact, business_domain="ecommerce"
            )

            return {"status": "ok", "result": result, "domain": "ecommerce", "method": "fallback"}

        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {fallback_error}", exc_info=True)
            return {
                "status": "error",
                "message": str(e),
                "fallback_error": str(fallback_error),
            }


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


# ============================================================
# MIGRATION NOTES
# ============================================================

"""
MIGRATION PATTERN COMPARISON:

BEFORE (Legacy - webhook.py):
```python
# DEPRECATED: Uses legacy services
from app.services.domain_detector import get_domain_detector
from app.services.domain_manager import get_domain_manager
from app.services.super_orchestrator_service import get_super_orchestrator

domain_detector = get_domain_detector()
domain_manager = get_domain_manager()
super_orchestrator = get_super_orchestrator()

@router.post("/webhook")
async def process_webhook(request, db_session):
    # Direct service instantiation (violates DIP)
    detection_result = await domain_detector.detect_domain(wa_id, db_session)
    domain = detection_result["domain"]

    if method == "fallback_default":
        result = await super_orchestrator.process_webhook_message(message, contact, db_session)
    else:
        domain_service = await domain_manager.get_service(domain)
        result = await domain_service.process_webhook_message(message, contact)
```

AFTER (Clean Architecture - webhook_v2.py):
```python
# Clean: Use Cases via Dependency Injection
from app.core.container import DependencyContainer
from app.services.langgraph_chatbot_service import LangGraphChatbotService

@router.post("/webhook")
async def process_webhook(request, db_session):
    # Use Case for domain detection (follows SOLID)
    domain = await _detect_contact_domain(wa_id, db_session)

    # Single service handles all processing (already Clean Architecture)
    service = await _get_langgraph_service()
    result = await service.process_webhook_message(
        message=message,
        contact=contact,
        business_domain=domain
    )
```

BENEFITS:
✅ Single Responsibility: Each function has one clear purpose
✅ Dependency Inversion: Depends on Use Cases, not concrete services
✅ Testability: Easy to mock Use Cases for testing
✅ Maintainability: Business logic in Use Cases, API layer is thin
✅ No deprecated services: Clean dependency tree
✅ Consistent error handling: Structured responses
✅ Better logging: Domain detection and processing tracked separately
"""
