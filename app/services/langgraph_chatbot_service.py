"""
Servicio integrado de chatbot usando LangGraph multi-agente
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.agents.graph import EcommerceAssistantGraph
from app.agents.schemas import ConversationContext, CustomerContext
from app.config.langgraph_config import get_langgraph_config
from app.config.settings import get_settings
from app.database import check_db_connection
from app.models.conversation import ConversationHistory
from app.models.message import BotResponse, Contact, WhatsAppMessage
from app.repositories.redis_repository import RedisRepository
from app.services.customer_service import CustomerService
from app.services.whatsapp_service import WhatsAppService
from app.utils.language_detector import get_language_detector

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

        # Detector de idiomas con configuración
        self.language_detector = get_language_detector(
            {
                "supported_languages": ["es", "en"],
                "default_language": "es",
                "confidence_threshold": 0.6,
                "cache_size": 500,
                "cache_ttl": 1800,  # 30 minutos
            }
        )

        # Sistemas de monitoreo y seguridad (placeholders seguros)
        self.monitoring = self._create_monitoring_placeholder()
        self.security = self._create_security_placeholder()

        # Graph principal (se inicializa en initialize())
        self.graph_system: Optional[EcommerceAssistantGraph] = None
        self._initialized = False

    def _create_monitoring_placeholder(self):
        """Crea un placeholder simplificado para el sistema de monitoreo"""

        class MonitoringPlaceholder:
            async def record_message_processed(self, **kwargs):
                logger.info(
                    f"Message processed - Agent: {kwargs.get('agent_used', 'unknown')},"
                    f" Success: {kwargs.get('success', False)}"
                )

        return MonitoringPlaceholder()

    def _create_security_placeholder(self):
        """Crea un placeholder simplificado para el sistema de seguridad"""

        class SecurityPlaceholder:
            async def check_rate_limit(self, user_id: str) -> bool:
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
            self.graph_system.initialize()

            self._initialized = True
            self.logger.info("LangGraph chatbot service initialized successfully")

        except Exception as e:
            self.logger.error(f"Error initializing LangGraph service: {str(e)}")
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

            # Obtener contextos necesarios
            profile_name = (
                contact.profile.get("name") if contact.profile and isinstance(contact.profile, dict) else "Usuario"
            )
            customer_context = await self.customer_service._get_or_create_customer_context(user_number, profile_name)
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

            # Operaciones post-procesamiento
            await self._handle_post_processing(
                db_available=db_available,
                user_number=user_number,
                user_message=message_text,
                session_id=session_id,
                response_data=response_data,
            )

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
            return await self._handle_processing_error(e, user_number)

    async def _process_with_langgraph(
        self,
        message_text: str,
        customer_context: CustomerContext,
        conversation_context: ConversationContext,
        session_id: str,
    ) -> Dict[str, Any]:
        """
        Procesa el mensaje usando el sistema LangGraph multi-agente.

        Args:
            message_text: Texto del mensaje del usuario
            customer_context: Contexto del cliente
            conversation_context: Contexto de la conversación
            session_id: ID de la sesión

        Returns:
            Diccionario con respuesta del graph y metadatos
        """
        try:
            if not self.graph_system:
                raise RuntimeError("Graph system not initialized")

            # Procesar con el graph multi-agente
            result = await self.graph_system.invoke(
                message=message_text,
                conversation_id=session_id,
                customer_data=customer_context.model_dump(),
                conversation_data=conversation_context.model_dump(),
            )

            # Extraer la respuesta del último mensaje AI
            response_text = "Lo siento, no pude procesar tu mensaje."
            agent_used = result.get("current_agent", "unknown")

            # Buscar el último mensaje AI en los mensajes
            messages = result.get("messages", [])
            for msg in reversed(messages):
                if hasattr(msg, "content") and msg.__class__.__name__ == "AIMessage":
                    response_text = msg.content
                    break

            return {
                "response": response_text,
                "agent_used": agent_used,
                "requires_human": result.get("human_handoff_requested", False),
                "is_complete": result.get("is_complete", False),
                "processing_time_ms": 0,  # TODO: Implement timing
                "graph_result": result,
            }

        except Exception as e:
            self.logger.error(f"Error in LangGraph processing: {e}")
            # Respuesta de fallback
            return {
                "response": "Disculpa, tuve un problema procesando tu mensaje. ¿Podrías intentar de nuevo?",
                "agent_used": "fallback",
                "requires_human": False,
                "is_complete": False,
                "processing_time_ms": 0,
                "error": str(e),
            }

    async def _handle_post_processing(
        self, db_available: bool, user_number: str, user_message: str, session_id: str, response_data: Dict[str, Any]
    ) -> None:
        """Maneja las operaciones post-procesamiento de forma simplificada"""
        try:
            # Operaciones b\u00e1sicas en paralelo
            tasks = [
                self._cache_conversation(session_id, user_message, response_data["response"]),
                self._send_whatsapp_response(user_number, response_data["response"]),
                self._record_metrics(response_data),
            ]

            # A\u00f1adir logging si DB disponible
            if db_available:
                tasks.append(
                    self._log_conversation_safely(
                        user_number=user_number,
                        user_message=user_message,
                        bot_response=response_data["response"],
                        agent_used=response_data.get("agent_used"),
                        session_id=session_id,
                    )
                )

            # Ejecutar todas las tareas (ignorar errores individuales)
            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            self.logger.error(f"Error in post-processing: {e}")

    async def _handle_processing_error(self, error: Exception, user_number: str) -> BotResponse:
        """Maneja errores de procesamiento de forma unificada"""
        self.logger.error(f"Error processing webhook message: {str(error)}")

        fallback_response = "Disculpa, estoy experimentando dificultades técnicas. \
            Por favor, intenta nuevamente en unos momentos."

        try:
            await self._send_whatsapp_response(user_number, fallback_response)
        except Exception as send_error:
            self.logger.error(f"Error sending fallback response: {send_error}")

        return BotResponse(status="error", message=fallback_response, error=str(error))

    async def process_chat_message(
        self, message: str, user_id: str, session_id: str, metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Procesa un mensaje de chat genérico (no WhatsApp) usando el sistema multi-agente.

        Args:
            message: Texto del mensaje del usuario
            user_id: ID único del usuario
            session_id: ID de la sesión
            metadata: Metadatos adicionales opcionales

        Returns:
            Diccionario con respuesta del graph y metadatos
        """
        if not self._initialized:
            await self.initialize()

        metadata = metadata or {}

        self.logger.info(f"Processing chat message from user {user_id} in session {session_id}: {message[:100]}...")

        try:
            # Crear contexto del cliente simplificado
            customer_context = CustomerContext(
                customer_id=user_id,
                name=metadata.get("user_name", "Usuario"),
                email=metadata.get("email"),
                phone=metadata.get("phone", ""),
                tier=metadata.get("tier", "basic"),
                purchase_history=[],
                preferences=metadata.get("preferences", {}),
            )

            # Crear contexto de conversación
            conversation_context = ConversationContext(
                conversation_id=session_id,
                session_id=session_id,
                channel=metadata.get("channel", "chat"),
                language=metadata.get("language", self._detect_language(message)),
            )

            # Procesar con el sistema LangGraph
            response_data = await self._process_with_langgraph(
                message_text=message,
                customer_context=customer_context,
                conversation_context=conversation_context,
                session_id=session_id,
            )

            # Post-procesamiento simplificado (sin WhatsApp)
            await self._handle_chat_post_processing(
                user_id=user_id, user_message=message, session_id=session_id, response_data=response_data
            )

            return response_data

        except Exception as e:
            self.logger.error(f"Error processing chat message: {str(e)}")
            return {
                "response": "Disculpa, tuve un problema procesando tu mensaje. ¿Podrías intentar de nuevo?",
                "agent_used": "fallback",
                "requires_human": False,
                "is_complete": False,
                "processing_time_ms": 0,
                "error": str(e),
            }

    async def _handle_chat_post_processing(
        self, user_id: str, user_message: str, session_id: str, response_data: Dict[str, Any]
    ) -> None:
        """Maneja post-procesamiento para mensajes de chat (sin WhatsApp)"""
        try:
            # Solo operaciones que aplican al chat (sin WhatsApp)
            tasks = [
                self._cache_conversation(session_id, user_message, response_data["response"]),
                self._record_metrics(response_data),
            ]

            # Logging simplificado
            self.logger.info(f"Chat log - User ({user_id}): {user_message[:100]}...")
            self.logger.info(
                f"Chat log - Bot (agent: {response_data.get('agent_used')}): {response_data['response'][:100]}..."
            )

            # Ejecutar tareas en paralelo
            import asyncio

            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            self.logger.error(f"Error in chat post-processing: {e}")

    async def _check_message_security(self, user_number: str, message_text: str) -> Dict[str, Any]:
        """Verificación de seguridad simplificada del mensaje"""
        try:
            # Verificar rate limiting (simplificado)
            if not await self.security.check_rate_limit(user_number):
                return {"allowed": False, "message": "Has enviado demasiados mensajes. Por favor espera un momento."}

            # Verificar contenido (simplificado)
            is_safe, _ = await self.security.check_message_content(message_text)
            if not is_safe:
                return {"allowed": False, "message": "Tu mensaje contiene contenido no permitido."}

            return {"allowed": True}

        except Exception as e:
            self.logger.warning(f"Security check error: {e}")
            return {"allowed": True}  # Permitir por defecto en caso de error

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
        """Detecta el idioma del mensaje usando spaCy con fallback robusto"""
        try:
            result = self.language_detector.detect_language(text)
            detected_language = result.get("language", "es")
            confidence = result.get("confidence", 0.0)
            method = result.get("method", "unknown")

            # Log para debugging (opcional)
            if confidence < 0.7:
                self.logger.debug(
                    f"Language detection with low confidence: {detected_language} "
                    f"({confidence:.2f}) using {method} for text: '{text[:50]}...'"
                )

            return detected_language

        except Exception as e:
            self.logger.warning(f"Error in language detection, falling back to default: {e}")
            return "es"  # Default a español en caso de error

    async def _log_conversation_safely(
        self, user_number: str, user_message: str, bot_response: str, agent_used: Optional[str], session_id: str
    ):
        """Registra la conversación en la base de datos (placeholder)"""
        try:
            self.logger.info(f"Conversation log - User ({user_number}): {user_message[:100]}...")
            self.logger.info(f"Conversation log - Bot (agent: {agent_used}): {bot_response[:100]}...")
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
        """Envía respuesta por WhatsApp (modo prueba)"""
        try:
            self.logger.info(f"[TEST MODE] WhatsApp message to {user_number}: {response[:50]}...")
            # TODO: Implement actual WhatsApp sending
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
                return {"error": "LangGraph system not initialized", "user_number": user_number, "messages": []}

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
                            if hasattr(msg, "content"):
                                serialized_messages.append(
                                    {
                                        "type": getattr(msg, "type", "unknown"),
                                        "content": msg.content,
                                        "timestamp": getattr(msg, "timestamp", None),
                                    }
                                )
                            else:
                                serialized_messages.append({"type": "unknown", "content": str(msg), "timestamp": None})
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
                            "requires_human": current_state.values.get("requires_human", False),
                        },
                    }
                else:
                    return {
                        "user_number": user_number,
                        "messages": [],
                        "total_messages": 0,
                        "note": "No conversation history found",
                    }

            except Exception as e:
                self.logger.warning(f"Could not retrieve conversation state: {e}")
                return {
                    "user_number": user_number,
                    "messages": [],
                    "total_messages": 0,
                    "error": f"Could not retrieve conversation: {str(e)}",
                }

        except Exception as e:
            self.logger.error(f"Error getting conversation history: {e}")
            return {
                "error": f"Error retrieving conversation history: {str(e)}",
                "user_number": user_number,
                "messages": [],
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
                return {"error": "LangGraph system not initialized", "user_number": user_number}

            config = {"configurable": {"thread_id": user_number}}

            try:
                current_state = await self.graph_system.app.aget_state(config)

                if current_state and current_state.values:
                    state_values = current_state.values
                    messages = state_values.get("messages", [])

                    # Contar tipos de mensajes
                    human_messages = len([m for m in messages if hasattr(m, "type") and m.type == "human"])
                    ai_messages = len([m for m in messages if hasattr(m, "type") and m.type == "ai"])

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
                        "last_intent": (
                            state_values.get("current_intent", {}).get("primary_intent")
                            if state_values.get("current_intent")
                            else None
                        ),
                    }
                else:
                    return {
                        "user_number": user_number,
                        "total_messages": 0,
                        "conversation_active": False,
                        "note": "No conversation found",
                    }

            except Exception as e:
                self.logger.warning(f"Could not retrieve conversation state for stats: {e}")
                return {
                    "user_number": user_number,
                    "error": f"Could not retrieve stats: {str(e)}",
                    "conversation_active": False,
                }

        except Exception as e:
            self.logger.error(f"Error getting conversation stats: {e}")
            return {"error": f"Error retrieving conversation stats: {str(e)}", "user_number": user_number}

    async def get_system_health(self) -> Dict[str, Any]:
        """
        Obtiene el estado de salud del sistema LangGraph.

        Returns:
            Diccionario con información del estado de salud
        """
        try:
            health_status = {
                "service": "langgraph_chatbot",
                "initialized": self._initialized,
                "graph_system": self.graph_system is not None,
                "components": {},
            }

            # Check integrations
            if self.graph_system:
                health_status["components"]["ollama"] = (
                    hasattr(self.graph_system, "ollama") and self.graph_system.ollama is not None
                )
                health_status["components"]["postgres"] = (
                    hasattr(self.graph_system, "postgres") and self.graph_system.postgres is not None
                )
                health_status["components"]["chroma"] = (
                    hasattr(self.graph_system, "chroma") and self.graph_system.chroma is not None
                )
                health_status["components"]["supervisor_agent"] = (
                    hasattr(self.graph_system, "supervisor_agent") and self.graph_system.supervisor_agent is not None
                )

            # Check database health
            health_status["database"] = await self._check_database_health()

            # Overall status
            if self._initialized and self.graph_system and health_status["database"]:
                health_status["overall_status"] = "healthy"
            elif self._initialized and self.graph_system:
                health_status["overall_status"] = "degraded"
            else:
                health_status["overall_status"] = "unhealthy"

            return health_status

        except Exception as e:
            self.logger.error(f"Error checking system health: {e}")
            return {"service": "langgraph_chatbot", "overall_status": "unhealthy", "error": str(e)}

    async def cleanup(self):
        """Limpieza de recursos del servicio"""
        try:
            self.logger.info("Cleaning up LangGraph chatbot service...")
            self._initialized = False
            # TODO: Cleanup graph resources if needed
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
