"""
Servicio integrado de chatbot usando LangGraph multi-agente
"""

import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.agents.langgraph_system.graph import EcommerceAssistantGraph
from app.agents.langgraph_system.models import ConversationContext, CustomerContext
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

logger = logging.getLogger(__name__)


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

        # Sistemas de monitoreo y seguridad (placeholders seguros)
        self.monitoring = self._create_monitoring_placeholder()
        self.security = self._create_security_placeholder()

        # Graph principal (se inicializa en initialize())
        self.graph_system: Optional[EcommerceAssistantGraph] = None
        self._initialized = False

    def _create_monitoring_placeholder(self):
        """Crea un placeholder para el sistema de monitoreo"""

        class MonitoringPlaceholder:
            async def record_message_processed(self, **kwargs):
                logger.debug(f"Monitoring placeholder: {kwargs}")

        return MonitoringPlaceholder()

    def _create_security_placeholder(self):
        """Crea un placeholder para el sistema de seguridad"""

        class SecurityPlaceholder:
            async def check_rate_limit(self, user_id: str) -> bool:
                _ = user_id  # Parámetro requerido por la interfaz pero no usado en placeholder
                return True  # Permitir por defecto

            async def check_message_content(self, message: str) -> Tuple[bool, Dict[str, Any]]:
                return True, {"safe": True}

        return SecurityPlaceholder()

    async def initialize(self):
        """
        Inicializa el sistema de forma asíncrona.
        Debe llamarse antes de procesar mensajes.
        """
        try:
            if self._initialized:
                return

            self.logger.info("Initializing LangGraph chatbot service...")

            # Crear y configurar el sistema de graph
            self.graph_system = EcommerceAssistantGraph(self.langgraph_config.model_dump())

            # Inicializar el graph de forma asíncrona
            await self.graph_system.initialize()

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
            profile_name = None
            if contact.profile and isinstance(contact.profile, dict):
                profile_name = contact.profile.get("name")
            
            customer_context = await self._get_or_create_customer_context(
                user_number, profile_name or "Usuario"
            )

            # 4. Crear contexto de conversación
            conversation_context = ConversationContext(
                conversation_id=session_id,
                session_id=session_id,
                channel="whatsapp",
                language=self._detect_language(message_text),
            )

            # 5. Procesar con el sistema LangGraph
            response_data = await self._process_with_langgraph(
                message_text=message_text,
                customer_context=customer_context,
                conversation_context=conversation_context,
                session_id=session_id,
            )

            # 6. Registrar la conversación si DB está disponible
            if db_available:
                await self._log_conversation_safely(
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
                phone_number=user_number, profile_name=user_name
            )

            if not customer:
                # Si no se pudo obtener/crear el cliente, crear contexto por defecto
                return CustomerContext(
                    customer_id=f"whatsapp_{user_number}",
                    name=user_name or "Usuario",
                    email=None,
                    phone=user_number,
                    tier="basic",
                    purchase_history=[],
                    preferences={},
                )

            # Crear contexto usando modelo Pydantic para validación
            customer_context = CustomerContext(
                customer_id=str(customer.get("id", f"whatsapp_{user_number}")),
                name=customer.get("name", user_name or "Usuario"),
                email=customer.get("email"),
                phone=customer.get("phone", user_number),
                tier=customer.get("tier", "basic"),
                purchase_history=[],  # Se puede cargar desde DB si es necesario
                preferences=customer.get("preferences", {}),
            )

            return customer_context

        except Exception as e:
            self.logger.warning(f"Error getting customer context: {e}")

            # Crear contexto básico como fallback
            return CustomerContext(
                customer_id=f"temp_{user_number}", 
                name=user_name or "Usuario", 
                phone=user_number, 
                tier="basic",
                email=None,
                purchase_history=[],
                preferences={}
            )

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
            rate_limit_result = await self.security.check_rate_limit(user_number)
            
            # Manejar diferentes tipos de respuesta de check_rate_limit
            if isinstance(rate_limit_result, tuple):
                # Si es una tupla, el primer elemento es el booleano
                rate_allowed = rate_limit_result[0]
            else:
                # Si es un booleano directo
                rate_allowed = rate_limit_result
                
            if not rate_allowed:
                return {"allowed": False, "message": "Has enviado demasiados mensajes. Por favor espera un momento."}

            # Verificar contenido del mensaje
            content_check_result = await self.security.check_message_content(message_text)
            
            # Manejar diferentes tipos de respuesta de check_message_content
            if isinstance(content_check_result, tuple):
                # Si es una tupla (bool, dict)
                is_safe, content_info = content_check_result
                if not is_safe:
                    return {"allowed": False, "message": "Tu mensaje contiene contenido no permitido."}
            elif isinstance(content_check_result, dict):
                # Si es un diccionario directo
                if not content_check_result.get("safe", True):
                    return {"allowed": False, "message": "Tu mensaje contiene contenido no permitido."}
            else:
                # Si es otro tipo, asumir que es seguro
                self.logger.warning(f"Unexpected content check result type: {type(content_check_result)}")

            return {"allowed": True}

        except AttributeError as e:
            # Si el método no existe, permitir el mensaje
            self.logger.warning(f"Security method not found: {e}")
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

    async def _log_conversation_safely(
        self, user_number: str, user_message: str, bot_response: str, agent_used: Optional[str], session_id: str
    ):
        """Registra la conversación en la base de datos de forma segura"""
        try:
            # TODO: Implement proper database logging when conversation model is ready
            # For now, just log to logger
            self.logger.info(f"Conversation log - User ({user_number}): {user_message[:100]}...")
            self.logger.info(f"Conversation log - Bot (agent: {agent_used}): {bot_response[:100]}...")
            
            # Note: The actual implementation needs:
            # 1. Proper conversation model that returns UUID for conversation_id
            # 2. Message model expects: user_phone, message_type ("user"/"bot"), content, conversation_id (UUID)
            # 3. Async database operations
            
        except Exception as e:
            self.logger.error(f"Error logging conversation: {e}")

    async def _cache_conversation(self, session_id: str, user_message: str, bot_response: str):
        """Cachea la conversación en Redis"""
        try:
            # Obtener historial existente
            history = self.redis_repo.get(session_id)
            if not history:
                # Extraer user_id del session_id (formato: whatsapp_NUMERO)
                user_id = session_id.replace("whatsapp_", "") if session_id.startswith("whatsapp_") else session_id
                history = ConversationHistory(user_id=user_id, messages=[], created_at=datetime.now(timezone.utc))

            # Añadir nuevos mensajes usando el método add_message
            history.add_message(role="persona", content=user_message)
            history.add_message(role="bot", content=bot_response)

            # Mantener solo los últimos 20 mensajes para optimizar memoria
            if len(history.messages) > 20:
                history.messages = history.messages[-20:]

            # Guardar en Redis con expiración
            self.redis_repo.set(session_id, history, expiration=CONVERSATION_EXPIRATION)

        except Exception as e:
            self.logger.error(f"Error caching conversation: {e}")

    async def _send_whatsapp_response(self, user_number: str, response: str):
        """Envía respuesta por WhatsApp"""
        try:
            # Para pruebas: solo registrar en log en lugar de enviar por WhatsApp
            self.logger.info(f"[TEST MODE] WhatsApp message to {user_number}: {response[:100]}...")
            # Comentado para pruebas locales:
            # await self.whatsapp_service.enviar_mensaje_texto(user_number, response)
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
    async def _get_or_create_conversation(self, db, user_number: str, session_id: str) -> ConversationHistory:
        """Obtiene o crea una conversación en la base de datos"""
        # TODO: Implementar según modelo de datos
        # Por ahora, crear un objeto ConversationHistory con el user_id requerido
        return ConversationHistory(user_id=user_number)

    async def get_system_health(self) -> Dict[str, Any]:
        """Obtiene el estado de salud del sistema"""
        try:
            if not self.graph_system:
                return {"status": "not_initialized"}

            return await self.graph_system.health_check()

        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def get_conversation_history_langgraph(self, user_number: str, limit: int = 50) -> Dict[str, Any]:
        """
        Obtiene el historial de conversación para un usuario usando LangGraph
        
        Args:
            user_number: Número de teléfono del usuario
            limit: Límite de mensajes a obtener
            
        Returns:
            Dict con el historial de conversación
        """
        try:
            if not self.graph_system or not self.graph_system.app:
                return {
                    "error": "LangGraph system not initialized",
                    "user_number": user_number,
                    "messages": []
                }
            
            # Intentar obtener el estado de la conversación
            config = {"configurable": {"thread_id": user_number}}
            
            try:
                current_state = await self.graph_system.app.aget_state(config)
                
                if current_state and current_state.values:
                    messages = current_state.values.get("messages", [])
                    
                    # Limitar los mensajes
                    limited_messages = messages[-limit:] if len(messages) > limit else messages
                    
                    # Convertir mensajes a formato serializable
                    serialized_messages = []
                    for msg in limited_messages:
                        try:
                            if hasattr(msg, 'content'):
                                serialized_messages.append({
                                    "type": getattr(msg, 'type', 'unknown'),
                                    "content": msg.content,
                                    "timestamp": getattr(msg, 'timestamp', None)
                                })
                            else:
                                serialized_messages.append({
                                    "type": "unknown",
                                    "content": str(msg),
                                    "timestamp": None
                                })
                        except Exception as e:
                            self.logger.warning(f"Error serializing message: {e}")
                            continue
                    
                    return {
                        "user_number": user_number,
                        "messages": serialized_messages,
                        "total_messages": len(messages),
                        "limited_to": limit,
                        "conversation_state": {
                            "current_agent": current_state.values.get("current_agent"),
                            "is_complete": current_state.values.get("is_complete", False),
                            "requires_human": current_state.values.get("requires_human", False)
                        }
                    }
                else:
                    return {
                        "user_number": user_number,
                        "messages": [],
                        "total_messages": 0,
                        "note": "No conversation history found"
                    }
                    
            except Exception as e:
                self.logger.warning(f"Could not retrieve conversation state: {e}")
                return {
                    "user_number": user_number,
                    "messages": [],
                    "total_messages": 0,
                    "error": f"Could not retrieve conversation: {str(e)}"
                }
                
        except Exception as e:
            self.logger.error(f"Error getting conversation history: {e}")
            return {
                "error": f"Error retrieving conversation history: {str(e)}",
                "user_number": user_number,
                "messages": []
            }

    async def get_conversation_stats(self, user_number: str) -> Dict[str, Any]:
        """
        Obtiene estadísticas de conversación para un usuario
        
        Args:
            user_number: Número de teléfono del usuario
            
        Returns:
            Dict con estadísticas de la conversación
        """
        try:
            if not self.graph_system or not self.graph_system.app:
                return {
                    "error": "LangGraph system not initialized",
                    "user_number": user_number
                }
            
            config = {"configurable": {"thread_id": user_number}}
            
            try:
                current_state = await self.graph_system.app.aget_state(config)
                
                if current_state and current_state.values:
                    state_values = current_state.values
                    messages = state_values.get("messages", [])
                    
                    # Contar tipos de mensajes
                    human_messages = len([m for m in messages if hasattr(m, 'type') and m.type == 'human'])
                    ai_messages = len([m for m in messages if hasattr(m, 'type') and m.type == 'ai'])
                    
                    # Obtener agentes utilizados
                    agent_history = state_values.get("agent_history", [])
                    
                    return {
                        "user_number": user_number,
                        "total_messages": len(messages),
                        "human_messages": human_messages,
                        "ai_messages": ai_messages,
                        "current_agent": state_values.get("current_agent"),
                        "agents_used": list(set(agent_history)) if agent_history else [],
                        "agents_used_count": len(set(agent_history)) if agent_history else 0,
                        "is_complete": state_values.get("is_complete", False),
                        "requires_human": state_values.get("requires_human", False),
                        "error_count": state_values.get("error_count", 0),
                        "conversation_active": len(messages) > 0,
                        "last_intent": (state_values.get("current_intent", {}).get("primary_intent") 
                                       if state_values.get("current_intent") else None)
                    }
                else:
                    return {
                        "user_number": user_number,
                        "total_messages": 0,
                        "conversation_active": False,
                        "note": "No conversation found"
                    }
                    
            except Exception as e:
                self.logger.warning(f"Could not retrieve conversation state for stats: {e}")
                return {
                    "user_number": user_number,
                    "error": f"Could not retrieve stats: {str(e)}",
                    "conversation_active": False
                }
                
        except Exception as e:
            self.logger.error(f"Error getting conversation stats: {e}")
            return {
                "error": f"Error retrieving conversation stats: {str(e)}",
                "user_number": user_number
            }

    async def cleanup(self):
        """Limpieza de recursos"""
        try:
            self.logger.info("Cleaning up LangGraph chatbot service...")
            # Placeholder para limpieza
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
