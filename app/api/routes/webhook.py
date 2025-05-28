import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.config.settings import Settings, get_settings
from app.models.message import BotResponse, WhatsAppWebhookRequest
from app.services.chatbot_service import ChatbotService
from app.services.whatsapp_service import WhatsAppService

router = APIRouter(tags=["webhook"])
logger = logging.getLogger(__name__)
chatbot_service = ChatbotService()
whatsapp_service = WhatsAppService()


@router.get("/")
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


@router.post("/")
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

    # Procesar el mensaje con el servicio chatbot
    try:
        print("Procesando Mensaje...")
        result: BotResponse = await chatbot_service.procesar_mensaje(message, contact)
        await whatsapp_service.enviar_mensaje_texto(contact.wa_id, result.message)
        print("Mensaje Procesado con Resultado: ", result)
        return {"status": "ok", "result": result}
    except Exception as e:
        print(f"Error procesando el mensaje: {str(e)}")
        logger.error(f"Error processing message: {str(e)}")
        return {"status": "error", "message": str(e)}


def is_status_update(request: WhatsAppWebhookRequest) -> bool:
    """
    Verifica si la solicitud es una actualización de estado
    """
    try:
        return bool(request.entry[0].changes[0].value.get("statuses"))
    except (IndexError, AttributeError, KeyError):
        return False
