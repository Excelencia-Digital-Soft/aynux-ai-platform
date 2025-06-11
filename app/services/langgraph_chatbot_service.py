"""
Servicio integrado de chatbot usando LangGraph multi-agente
"""

import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.agents.langgraph_system.graph import EcommerceAssistantGraph
from app.agents.langgraph_system.models import ConversationContext, CustomerContext
from app.agents.langgraph_system.monitoring import MonitoringSystem, SecurityManager
from app.config.langgraph_config import get_langgraph_config
from app.config.settings import get_settings
from app.database import check_db_connection, get_db_context
from app.models.conversation import ConversationHistory
from app.models.database import Message
from app.models.message import BotResponse, Contact, WhatsAppMessage
from app.repositories.redis_repository import RedisRepository
from app.services.customer_service import CustomerService
from app.services.whatsapp_service import WhatsAppService

# Configurar expiración de conversación (24 horas)
CONVERSATION_EXPIRATION = 86400  # 24 horas en segundos
BUSINESS_NAME = "Conversa Shop"


class LangGraphChatbotService:
    """
    Servicio de chatbot integrado con sistema multi-agente LangGraph

    Versión que usa:
    - Modelos Pydantic para validación de datos
    - TypedDict para estado de LangGraph (máximo rendimiento)
    - StateManager como puente entre ambos
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.settings = get_settings()

        # Cargar configuración LangGraph
        self.langgraph_config = get_langgraph_config()

        # Servicios básicos
        self.redis_repo = RedisRepository[ConversationHistory](ConversationHistory, prefix="chat")
        self.customer_service = CustomerService()
        self.whatsapp_service = WhatsAppService()

        # Sistema de monitoreo y seguridad
        self.monitoring = MonitoringSystem()
        self.security = SecurityManager()

        # Graph principal (se inicializa en initialize())
        self.graph_system: Optional[EcommerceAssistantGraph] = None
        self._initialized = False

    async def initialize(self):
        """
        Inicializa el sistema de forma asíncrona.
        Debe llamarse antes de procesar mensajes.
        """
        try:
            if self._initialized:
                return

            self.logger.info("Initializing LangGraph chatbot service...")

            # Inicializar el graph de forma asíncrona
            await self.graph_system.initialize()

            # Verificar estado del sistema
            health_status = await self.graph_system.health_check()
            if health_status["overall_status"] != "healthy":
                self.logger.warning(f"System not fully healthy: {health_status}")
            else:
                self.logger.info("All system components are healthy")

            self._initialized = True
            self.logger.info("LangGraph chatbot service initialized successfully")

        except Exception as e:
            self.logger.error(f"Error initializing LangGraph service: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise

    async def process_webhook_message(self, message: WhatsAppMessage, contact: Contact) -> BotResponse:
        """
        Procesa un mensaje de WhatsApp usando el sistema multi-agente refactorizado.

        Args:
            message: Mensaje de WhatsApp recibido
            contact: Información de contacto del usuario

        Returns:
            Respuesta estructurada del bot
        """

        if not self._initialized:
            await self.initialize()

        # Extraer información básica
        user_number = contact.wa_id
        message_text = self._extract_message_text(message)
        session_id = f"whatsapp_{user_number}"

        self.logger.info(f"Processing message from {user_number}: {message_text[:100]}...")

        try:
            # 1. Verificar seguridad del mensaje
            security_check = await self._check_message_security(user_number, message_text)
            if not security_check["allowed"]:
                return BotResponse(status="blocked", message=security_check["message"])

            # 2. Verificar estado de la base de datos
            db_available = await self._check_database_health()

            # 3. Obtener o crear contexto del cliente
            customer_context = await self._get_or_create_customer_context(
                user_number, contact.profile.get("name", "Usuario")
            )

            # 4. Crear contexto de conversación
            conversation_context = ConversationContext(
                conversation_id=session_id,
                session_id=session_id,
                channel="whatsapp",
                language=self._detect_language(message_text),
            )

            # 4. Obtener o crear contexto del cliente
            await self._get_or_create_customer_context(user_number, contact.profile.get("name", "Usuario"))

            # 5. Procesar con el sistema LangGraph
            response_data = await self._process_with_langgraph(
                message_text=message_text,
                customer_context=customer_context,
                conversation_context=conversation_context,
                session_id=session_id,
            )

            # 6. Registrar la conversación si DB está disponible
            if db_available:
                await self._log_conversation(
                    user_number=user_number,
                    user_message=message_text,
                    bot_response=response_data["response"],
                    agent_used=response_data.get("agent_used"),
                    session_id=session_id,
                )

            # 7. Cachear conversación en Redis
            await self._cache_conversation(session_id, message_text, response_data["response"])

            # 8. Enviar respuesta por WhatsApp
            await self._send_whatsapp_response(user_number, response_data["response"])

            # 9. Registrar métricas
            await self._record_metrics(response_data)

            return BotResponse(
                status="success",
                message=response_data["response"],
                metadata={
                    "agent_used": response_data.get("agent_used"),
                    "requires_human": response_data.get("requires_human", False),
                    "conversation_id": session_id,
                },
            )

        except Exception as e:
            self.logger.error(f"Error processing webhook message: {str(e)}")
            self.logger.error(traceback.format_exc())

            # Respuesta de fallback
            fallback_response = (
                "Disculpa, estoy experimentando dificultades técnicas.Por favor, intenta nuevamente en unos momentos."
            )

            try:
                await self._send_whatsapp_response(user_number, fallback_response)
            except Exception as send_error:
                self.logger.error(f"Error sending fallback response: {send_error}")

            return BotResponse(status="error", message=fallback_response, error=str(e))

    async def _process_with_langgraph(
        self,
        message_text: str,
        customer_context: CustomerContext,
        conversation_context: ConversationContext,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Procesa el mensaje usando el sistema LangGraph

        Args:
            message_text: Texto del mensaje del usuario
            customer_context: Contexto del cliente (Pydantic model)
            conversation_context: Contexto de conversación (Pydantic model)
            session_id: ID de sesión para checkpointing

        Returns:
            Diccionario con la respuesta y metadatos
        """
        try:
            # Convertir customer_context a diccionario para compatibilidad
            customer_data = customer_context.to_dict()

            # Procesar con el graph usando la nueva arquitectura
            result = await self.graph_system.process_message(
                message=message_text,
                customer_data=customer_data,
                conversation_id=session_id,
                session_config={
                    "language": conversation_context.language,
                    "channel": conversation_context.channel,
                    "timezone": conversation_context.timezone,
                },
            )

            return result

        except Exception as e:
            self.logger.error(f"Error in LangGraph processing: {str(e)}")
            raise

    async def _get_or_create_customer_context(self, user_number: str, user_name: str) -> CustomerContext:
        """
        Obtiene o crea el contexto del cliente usando modelos Pydantic.

        Args:
            user_number: Número de WhatsApp del usuario
            user_name: Nombre del usuario

        Returns:
            Contexto del cliente validado
        """
        try:
            # Intentar obtener cliente existente
            customer = await self.customer_service.get_or_create_customer(
                phone=user_number, name=user_name, channel="whatsapp"
            )

            # Crear contexto usando modelo Pydantic para validación
            customer_context = CustomerContext(
                customer_id=str(customer.id),
                name=customer.name,
                email=customer.email,
                phone=customer.phone,
                tier=getattr(customer, "tier", "basic"),
                purchase_history=[],  # Se puede cargar desde DB si es necesario
                preferences=getattr(customer, "preferences", {}),
            )

            return customer_context

        except Exception as e:
            self.logger.warning(f"Error getting customer context: {e}")

            # Crear contexto básico como fallback
            return CustomerContext(customer_id=f"temp_{user_number}", name=user_name, phone=user_number, tier="basic")

    async def _check_message_security(self, user_number: str, message_text: str) -> Dict[str, Any]:
        """
        Verifica la seguridad del mensaje usando el sistema de seguridad.

        Args:
            user_number: Número del usuario
            message_text: Texto del mensaje

        Returns:
            Resultado de la verificación de seguridad
        """
        try:
            # Verificar rate limiting
            if not await self.security.check_rate_limit(user_number):
                return {"allowed": False, "message": "Has enviado demasiados mensajes. Por favor espera un momento."}

            # Verificar contenido del mensaje
            content_check = await self.security.check_message_content(message_text)
            if not content_check["safe"]:
                return {"allowed": False, "message": "Tu mensaje contiene contenido no permitido."}

            return {"allowed": True}

        except Exception as e:
            self.logger.error(f"Error in security check: {e}")
            # En caso de error, permitir el mensaje pero registrar
            return {"allowed": True}

    async def _check_database_health(self) -> bool:
        """Verifica la salud de la base de datos"""
        try:
            return await check_db_connection()
        except Exception as e:
            self.logger.warning(f"Database health check failed: {e}")
            return False

    def _extract_message_text(self, message: WhatsAppMessage) -> str:
        """Extrae el texto del mensaje de WhatsApp"""
        if hasattr(message, "text") and message.text:
            return message.text.body.strip()
        return ""

    def _detect_language(self, text: str) -> str:
        """Detecta el idioma del mensaje (implementación básica)"""
        # Implementación básica - se puede mejorar con librerías de detección
        spanish_words = ["hola", "que", "como", "donde", "cuando", "por", "para"]
        text_lower = text.lower()

        if any(word in text_lower for word in spanish_words):
            return "es"
        return "es"  # Default a español

    async def _log_conversation(
        self, user_number: str, user_message: str, bot_response: str, agent_used: Optional[str], session_id: str
    ):
        """Registra la conversación en la base de datos"""
        try:
            async with get_db_context() as db:
                # Obtener o crear conversación
                conversation = await self._get_or_create_conversation(db, user_number, session_id)

                # Crear mensajes
                user_msg = Message(
                    conversation_id=conversation.id,
                    content=user_message,
                    is_from_user=True,
                    metadata={"channel": "whatsapp"},
                )

                bot_msg = Message(
                    conversation_id=conversation.id,
                    content=bot_response,
                    is_from_user=False,
                    metadata={"agent_used": agent_used, "channel": "whatsapp"},
                )

                db.add_all([user_msg, bot_msg])
                await db.commit()

        except Exception as e:
            self.logger.error(f"Error logging conversation: {e}")

    async def _cache_conversation(self, session_id: str, user_message: str, bot_response: str):
        """Cachea la conversación en Redis"""
        try:
            # Obtener historial existente
            history = await self.redis_repo.get(session_id)
            if not history:
                history = ConversationHistory(session_id=session_id, messages=[], created_at=datetime.now(timezone.utc))

            # Añadir nuevos mensajes
            history.messages.extend(
                [
                    {"role": "user", "content": user_message, "timestamp": datetime.now().isoformat()},
                    {"role": "assistant", "content": bot_response, "timestamp": datetime.now().isoformat()},
                ]
            )

            # Mantener solo los últimos 20 mensajes para optimizar memoria
            if len(history.messages) > 20:
                history.messages = history.messages[-20:]

            # Guardar en Redis con expiración
            await self.redis_repo.set(session_id, history, expiration=CONVERSATION_EXPIRATION)

        except Exception as e:
            self.logger.error(f"Error caching conversation: {e}")

    async def _send_whatsapp_response(self, user_number: str, response: str):
        """Envía respuesta por WhatsApp"""
        try:
            await self.whatsapp_service.send_message(user_number, response)
        except Exception as e:
            self.logger.error(f"Error sending WhatsApp message: {e}")
            raise

    async def _record_metrics(self, response_data: Dict[str, Any]):
        """Registra métricas del procesamiento"""
        try:
            await self.monitoring.record_message_processed(
                agent_used=response_data.get("agent_used"),
                success=True,
                response_time_ms=response_data.get("processing_time_ms", 0),
            )
        except Exception as e:
            self.logger.error(f"Error recording metrics: {e}")

    # Métodos auxiliares adicionales...
    async def _get_or_create_conversation(self, db, user_number: str, session_id: str):
        """Obtiene o crea una conversación en la base de datos"""
        # Implementación específica según tu modelo de datos
        pass

