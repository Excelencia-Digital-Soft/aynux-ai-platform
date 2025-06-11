import logging
import os

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.config.settings import Settings, get_settings
from app.models.message import BotResponse, WhatsAppWebhookRequest
from app.services.chatbot_service import ChatbotService
from app.services.langgraph_chatbot_service import LangGraphChatbotService
from app.services.whatsapp_service import WhatsAppService

router = APIRouter(tags=["webhook"])
logger = logging.getLogger(__name__)

# Determinar qué servicio usar basado en variable de entorno
USE_LANGGRAPH = os.getenv("USE_LANGGRAPH", "true").lower() == "true"

if USE_LANGGRAPH:
    logger.info("Using LangGraph multi-agent chatbot service")
    chatbot_service = None  # Se inicializará de forma lazy
    _langgraph_service = None
else:
    logger.info("Using traditional chatbot service")
    chatbot_service = ChatbotService()
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


async def _get_chatbot_service():
    """Obtiene el servicio de chatbot apropiado (lazy initialization)"""
    global _langgraph_service, chatbot_service

    if USE_LANGGRAPH:
        if _langgraph_service is None:
            _langgraph_service = LangGraphChatbotService()
            try:
                await _langgraph_service.initialize()
                logger.info("LangGraph service initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize LangGraph service: {e}")
                # Fallback al servicio tradicional
                if chatbot_service is None:
                    chatbot_service = ChatbotService()
                    logger.info("Falling back to traditional chatbot service")
                return chatbot_service
        return _langgraph_service
    else:
        if chatbot_service is None:
            chatbot_service = ChatbotService()
        return chatbot_service


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
    print("Message: ", message)
    contact = request.get_contact()
    print("Contact: ", contact)

    if not message or not contact:
        logger.warning("Invalid webhook payload: missing message or contact")
        return {"status": "error", "message": "Invalid webhook payload"}

    # Obtener el servicio de chatbot apropiado
    try:
        service = await _get_chatbot_service()
        service_type = "LangGraph" if USE_LANGGRAPH and isinstance(service, LangGraphChatbotService) else "Traditional"
        logger.info(f"Processing message with {service_type} service")
    except Exception as e:
        logger.error(f"Error getting chatbot service: {e}")
        return {"status": "error", "message": "Service initialization failed"}

    # Procesar el mensaje con el servicio chatbot
    try:
        print("Procesando Mensaje...")
        result: BotResponse = await service.procesar_mensaje(message, contact)
        print("Mensaje Procesado con Resultado: ", result)
        return {"status": "ok", "result": result}
    except Exception as e:
        print(f"Error procesando el mensaje: {str(e)}")
        logger.error(f"Error processing message: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.get("/webhook/health")
async def health_check():
    """
    Endpoint para verificar el estado del sistema de chatbot
    """
    try:
        service = await _get_chatbot_service()

        if USE_LANGGRAPH and isinstance(service, LangGraphChatbotService):
            health_status = await service.get_system_health()
            return {"service_type": "langgraph", "status": health_status["overall_status"], "details": health_status}
        else:
            # Health check básico para servicio tradicional
            return {
                "service_type": "traditional",
                "status": "healthy",
                "details": {"chatbot_service": "available", "whatsapp_service": "available"},
            }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"service_type": "unknown", "status": "unhealthy", "error": str(e)}


@router.get("/webhook/conversation/{user_number}")
async def get_conversation_history(user_number: str, limit: int = 50):
    """
    Obtiene el historial de conversación para un usuario
    """
    try:
        service = await _get_chatbot_service()

        if USE_LANGGRAPH and isinstance(service, LangGraphChatbotService):
            history = await service.get_conversation_history_langgraph(user_number, limit)
            return history
        else:
            # Para el servicio tradicional, usar el método existente si existe
            if hasattr(service, "get_conversation_stats"):
                stats = await service.get_conversation_stats(user_number)
                return {"stats": stats, "message": "Full history not available in traditional mode"}
            else:
                return {"error": "Conversation history not available"}

    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        return {"error": str(e)}


@router.post("/webhook/switch-service")
async def switch_service(enable_langgraph: bool = True):
    """
    Endpoint administrativo para cambiar entre servicios (solo para desarrollo)
    """
    global USE_LANGGRAPH, _langgraph_service, chatbot_service

    try:
        USE_LANGGRAPH = enable_langgraph

        if enable_langgraph:
            # Limpiar servicio anterior
            if _langgraph_service:
                await _langgraph_service.cleanup()
            _langgraph_service = None

            # El nuevo servicio se inicializará en la próxima request
            logger.info("Switched to LangGraph service")
            return {
                "status": "success",
                "service": "langgraph",
                "message": "Service will be initialized on next request",
            }
        else:
            # Limpiar LangGraph y usar tradicional
            if _langgraph_service:
                await _langgraph_service.cleanup()
            _langgraph_service = None

            if chatbot_service is None:
                chatbot_service = ChatbotService()

            logger.info("Switched to traditional service")
            return {"status": "success", "service": "traditional", "message": "Using traditional chatbot service"}

    except Exception as e:
        logger.error(f"Error switching service: {e}")
        return {"status": "error", "message": str(e)}


def is_status_update(request: WhatsAppWebhookRequest) -> bool:
    """
    Verifica si la solicitud es una actualización de estado
    """
    try:
        return bool(request.entry[0].changes[0].value.get("statuses"))
    except (IndexError, AttributeError, KeyError):
        return False
