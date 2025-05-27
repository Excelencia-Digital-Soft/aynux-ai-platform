import logging
import traceback

from app.models.conversation import ConversationHistory
from app.models.message import BotResponse, Contact, WhatsAppMessage
from app.repositories.redis_repository import RedisRepository
from app.services.ai_service import AIService
from app.services.whatsapp_service import WhatsAppService
from app.utils.certificate_utils import CertificateGenerator


class ChatbotService:
    """
    Servicio principal que coordina la interacción con el chatbot
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.redis_repo = RedisRepository[ConversationHistory](ConversationHistory, prefix="chat")
        self.whatsapp_service = WhatsAppService()
        self.ai_service = AIService()
        self.certificate_generator = CertificateGenerator()

    async def procesar_mensaje(self, message: WhatsAppMessage, contact: Contact) -> BotResponse:
        """
        Procesa un mensaje entrante de WhatsApp

        Procesos:
        1) Extraer message_text
        2) Buscar historial de mensajes.
        3) Buscar en vectorial del numero conversación importantes.
        4) Enviar a ollama para que detecte intención
        5) Redirecionar al servicio según intención.
        6) Responder según el agente al que se redireccione.

        Args:
            message: Mensaje entrante
            contact: Información del contacto

        Returns:
            Respuesta del procesamiento
        """
        try:
            # 1. Extraer message_text
            user_number = contact.wa_id
            message_text = self._extract_message_text(message)

            ## 2. Buscar historial de conversación
            conversation_key = f"conversation:{user_number}"
            conversation = self.redis_repo.get(conversation_key)
            
            # Si no existe conversación previa, crear una nueva
            if conversation is None:
                conversation = ConversationHistory(user_id=user_number)
            
            # Añadir mensaje del usuario al historial
            conversation.add_message("persona", message_text)
            
            # Obtener historial formateado para el contexto
            historial_str = conversation.to_formatted_history()

            ## 3. TODO: realizar busqueda en vectorial
            ## 4. Enviar a ollama para que detecte intención
            ## 5. Redirecionar al servicio según intención
            ## 6. Responder por el agente al que se redireccione

            ## RESPUESTA HARDCODEADA
            ## Asegurarse de que el agente no responda directamente al usuario
            bot_response = "Hola. Soy el asistente virtual de la Municipalidad. ¿En qué puedo ayudarte?"

            # Añadir respuesta del bot al historial
            conversation.add_message("bot", bot_response)
            
            # Guardar conversación actualizada en Redis con expiración de 1 hora
            self.redis_repo.set(conversation_key, conversation, expiration=3600)

            response = BotResponse(status="success", message=bot_response)
            return response

        except Exception as e:
            tb = traceback.format_exc()
            self.logger.error(
                f"Error en el procesamiento del mensaje en la línea {e.__traceback__.tb_lineno}: {e}\n{tb}"
            )
            return BotResponse(status="failure", message="Error en el procesamiento del mensaje")

    def _extract_message_text(self, message: WhatsAppMessage) -> str:
        """
        Extrae el texto del mensaje según su tipo
        """
        if message.type == "text" and message.text:
            return message.text.body
        elif message.type == "interactive" and message.interactive:
            if message.interactive.type == "button_reply" and message.interactive.button_reply:
                return message.interactive.button_reply.title
            elif message.interactive.type == "list_reply" and message.interactive.list_reply:
                return message.interactive.list_reply.title

        # Si no podemos extraer el texto, retornamos un mensaje vacío
        return ""
