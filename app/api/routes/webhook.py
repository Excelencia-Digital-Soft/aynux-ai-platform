import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings
from app.database.async_db import get_async_db
from app.models.message import BotResponse, WhatsAppWebhookRequest
from app.services.domain_detector import get_domain_detector
from app.services.domain_manager import get_domain_manager
from app.services.langgraph_chatbot_service import LangGraphChatbotService
from app.services.super_orchestrator_service import get_super_orchestrator
from app.services.super_orchestrator_service_refactored import get_super_orchestrator_refactored
from app.services.whatsapp_service import WhatsAppService

router = APIRouter(tags=["webhook"])
logger = logging.getLogger(__name__)

# Services (initialized lazily)
_langgraph_service = None
whatsapp_service = WhatsAppService()

# Multi-domain system components
domain_detector = get_domain_detector()
domain_manager = get_domain_manager()

# Super orchestrator - use refactored version if enabled
def get_orchestrator():
    """Get super orchestrator based on feature flag."""
    settings = get_settings()
    use_refactored = getattr(settings, "USE_REFACTORED_ORCHESTRATOR", True)

    if use_refactored:
        logger.info("Using SuperOrchestratorServiceRefactored (SOLID-compliant)")
        return get_super_orchestrator_refactored()
    else:
        logger.info("Using SuperOrchestratorService (legacy)")
        return get_super_orchestrator()

super_orchestrator = get_orchestrator()


@router.get("/webhook/")
@router.get("/webhook")
async def verify_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),  # noqa: B008
):
    """
    Verifica el webhook para WhatsApp

    Esta ruta es llamada por WhatsApp para verificar que el webhook esté configurado correctamente.
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


async def _get_langgraph_service():
    """Obtiene el servicio LangGraph (lazy initialization)"""
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
    Procesa las notificaciones del webhook de WhatsApp con sistema multi-dominio

    Esta ruta recibe las notificaciones de WhatsApp, detecta el dominio del contacto
    y enruta al servicio especializado correspondiente.
    """

    # Verificar si es una actualización de estado
    if is_status_update(request):
        logger.info("Received a WhatsApp status update")
        return {"status": "ok"}

    # Extraer mensaje y contacto
    message = request.get_message()
    logger.info(f"Received message: {message}")
    contact = request.get_contact()
    logger.info(f"Received contact: {contact}")

    if not message or not contact:
        logger.warning("Invalid webhook payload: missing message or contact")
        return {"status": "error", "message": "Invalid webhook payload"}

    wa_id = contact.wa_id
    logger.info(f"Processing message from WhatsApp ID: {wa_id}")

    # PASO 1: Detectar dominio del contacto
    try:
        detection_result = await domain_detector.detect_domain(wa_id, db_session)
        domain = detection_result["domain"]
        confidence = detection_result["confidence"]
        method = detection_result["method"]

        logger.info(f"Domain detected: {wa_id} -> {domain} (confidence: {confidence:.2f}, method: {method})")

    except Exception as e:
        logger.error(f"Error in domain detection: {e}")
        # Fallback al dominio por defecto
        domain = "ecommerce"
        confidence = 0.1  # Baja confianza por fallback de error
        method = "error_fallback"
        logger.warning(f"Using fallback domain: {domain}")

    # PASO 2: Procesar según estrategia
    try:
        if method == "fallback_default" and confidence < 0.5:
            # Contacto nuevo sin dominio claro -> Super Orquestador
            logger.info(f"Using SuperOrchestrator for new contact: {wa_id}")
            result: BotResponse = await super_orchestrator.process_webhook_message(message, contact, db_session)

        else:
            # Dominio conocido -> Servicio directo
            logger.info(f"Using direct domain service: {domain}")
            domain_service = await domain_manager.get_service(domain)

            if not domain_service:
                logger.error(f"Domain service not available: {domain}")
                return {"status": "error", "message": f"Service for domain '{domain}' not available"}

            result: BotResponse = await domain_service.process_webhook_message(message, contact)

        logger.info(f"Message processed successfully: {result}")
        return {"status": "ok", "result": result, "domain": domain, "method": method}

    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")

        # Fallback final al servicio e-commerce
        try:
            logger.info("Attempting fallback to ecommerce service")
            ecommerce_service = await domain_manager.get_service("ecommerce")
            if ecommerce_service:
                result: BotResponse = await ecommerce_service.process_webhook_message(message, contact)
                return {"status": "ok", "result": result, "domain": "ecommerce", "method": "fallback"}
        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {fallback_error}")

        return {"status": "error", "message": str(e)}


@router.get("/webhook/health")
async def health_check():
    """
    Endpoint para verificar el estado del sistema LangGraph
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
        logger.error(f"Health check failed: {e}")
        return {"service_type": "langgraph", "status": "unhealthy", "error": str(e)}


@router.get("/webhook/conversation/{user_number}")
async def get_conversation_history(user_number: str, limit: int = 50):
    """
    Obtiene el historial de conversación para un usuario usando LangGraph
    """
    try:
        service = await _get_langgraph_service()
        history = await service.get_conversation_history_langgraph(user_number, limit)
        return history
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        return {"error": str(e)}


def is_status_update(request: WhatsAppWebhookRequest) -> bool:
    """
    Verifica si la solicitud es una actualización de estado
    """
    try:
        return bool(request.entry[0].changes[0].value.get("statuses"))
    except (IndexError, AttributeError, KeyError):
        return False

