import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.config.settings import Settings, get_settings
from app.models.message import BotResponse, WhatsAppWebhookRequest
from app.services.langgraph_chatbot_service import LangGraphChatbotService
from app.services.whatsapp_service import WhatsAppService

router = APIRouter(tags=["webhook"])
logger = logging.getLogger(__name__)

# LangGraph multi-agent service (initialized lazily)
_langgraph_service = None
whatsapp_service = WhatsAppService()


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
):
    """
    Procesa las notificaciones del webhook de WhatsApp

    Esta ruta recibe las notificaciones de WhatsApp cuando hay nuevos mensajes.
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

    # Obtener el servicio LangGraph
    try:
        service = await _get_langgraph_service()
        logger.info("Processing message with LangGraph multi-agent service")
    except Exception as e:
        logger.error(f"Error getting LangGraph service: {e}")
        return {"status": "error", "message": "LangGraph service initialization failed"}

    # Procesar el mensaje con el servicio LangGraph
    try:
        result: BotResponse = await service.process_webhook_message(message, contact)
        logger.info(f"Message processed successfully: {result}")
        return {"status": "ok", "result": result}
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
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