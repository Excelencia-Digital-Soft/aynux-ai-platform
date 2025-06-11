"""
Servicio integrado de chatbot usando LangGraph multi-agente
"""
import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.agents.langgraph_system.graph import EcommerceAssistantGraph
from app.agents.langgraph_system.monitoring import MonitoringSystem, SecurityManager
from app.config.langgraph_config import get_langgraph_config
from app.config.settings import get_settings
from app.database import check_db_connection, get_db_context
from app.models.chatbot import UserIntent
from app.models.conversation import ConversationHistory
from app.models.database import Conversation, Message
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
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.settings = get_settings()
        
        # Cargar configuración LangGraph
        self.langgraph_config = get_langgraph_config()
        
        # Servicios básicos
        self.redis_repo = RedisRepository[ConversationHistory](ConversationHistory, prefix="chat")
        self.whatsapp_service = WhatsAppService()
        self.customer_service = CustomerService()
        
        # Sistema multi-agente LangGraph
        self.graph_system = None
        self.monitoring = None
        self.security = None
        
        # Estado de la base de datos
        self._db_available = None
        
        # Configuración del sistema (usar la nueva configuración)
        self.config = self._prepare_system_config()
        
        self.logger.info("LangGraphChatbotService initialized")
    
    def _prepare_system_config(self) -> Dict[str, Any]:
        """Prepara la configuración del sistema usando LangGraphConfig"""
        config = self.langgraph_config.get_config()
        
        # Adaptar la configuración para el formato esperado por EcommerceAssistantGraph
        return {
            # Base de datos principal
            "db_connection": config["database"]["primary_db_url"],
            
            # Configuración de caché
            "cache_service": {
                "redis_url": config["database"]["redis_url"],
                "ttl": config["performance"]["caching"]["ttl"]
            },
            
            # APIs externas
            "shipping_apis": config["external_services"]["shipping_apis"],
            
            # Base de conocimiento
            "knowledge_base": {
                "enabled": config["agents"]["support_agent"]["enabled"],
                "sources": config["agents"]["support_agent"]["knowledge_sources"]
            },
            
            # API de facturación
            "invoice_api": config["external_services"]["invoice_api"],
            
            # Configuración adicional para monitoreo y seguridad
            "monitoring_config": config["monitoring"],
            "security_config": config["security"],
            "performance_config": config["performance"],
            "agents_config": config["agents"]
        }
    
    async def initialize(self):
        """Inicializa el sistema completo"""
        try:
            self.logger.info("Initializing LangGraph system...")
            
            # Validar configuración antes de inicializar
            validation_results = self.langgraph_config.validate_config()
            failed_validations = [k for k, v in validation_results.items() if not v]
            
            if failed_validations:
                self.logger.warning(f"Configuration validation failed for: {failed_validations}")
                # Continuar pero con advertencias
            
            # Inicializar sistema de monitoreo
            monitoring_config = self.config.get("monitoring_config", {})
            self.monitoring = MonitoringSystem(monitoring_config)
            
            # Inicializar sistema de seguridad
            security_config = self.config.get("security_config", {})
            self.security = SecurityManager(security_config)
            
            # Inicializar sistema multi-agente
            self.graph_system = EcommerceAssistantGraph(self.config)
            await self.graph_system.initialize()
            
            # Verificar estado del sistema
            health_status = await self.graph_system.health_check()
            if health_status["overall_status"] != "healthy":
                self.logger.warning(f"System not fully healthy: {health_status}")
            else:
                self.logger.info("All system components are healthy")
            
            self.logger.info("LangGraph system initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing LangGraph system: {e}")
            raise
    
    async def _check_database_health(self) -> bool:
        """Verifica si la base de datos está disponible y saludable"""
        if self._db_available is None:
            self._db_available = await check_db_connection()
            if not self._db_available:
                self.logger.warning("Base de datos no disponible, usando modo de respuesta básica")
        return self._db_available
    
    async def procesar_mensaje(self, message: WhatsAppMessage, contact: Contact) -> BotResponse:
        """
        Procesa un mensaje entrante de WhatsApp usando el sistema multi-agente
        
        Args:
            message: Mensaje entrante
            contact: Información del contacto
        
        Returns:
            Respuesta del procesamiento
        """
        
        user_number = None
        customer = None
        message_text = None
        session_id = None
        
        try:
            # 1. Extraer datos básicos
            user_number = contact.wa_id
            message_text = self._extract_message_text(message)
            
            if not message_text.strip():
                self.logger.warning(f"Mensaje vacío recibido de {user_number}")
                return BotResponse(status="failure", message="No se pudo procesar el mensaje vacío")
            
            self.logger.info(f"Procesando mensaje de {user_number}: '{message_text[:50]}...'")
            
            # 2. Verificar estado de la base de datos
            db_available = await self._check_database_health()
            
            if not db_available:
                # Modo fallback sin LangGraph
                return await self._handle_fallback_mode(message_text, user_number)
            
            # 3. Verificar si el sistema LangGraph está inicializado
            if not self.graph_system:
                self.logger.warning("LangGraph system not initialized, using fallback")
                return await self._handle_fallback_mode(message_text, user_number)
            
            # 4. Obtener o crear cliente
            customer = await self._safe_get_or_create_customer(user_number, contact.profile.get("name"))
            
            if not customer:
                self.logger.warning(f"No se pudo crear/obtener cliente para {user_number}, usando modo básico")
                return await self._handle_fallback_mode(message_text, user_number)
            
            # 5. Iniciar sesión de monitoreo
            if self.monitoring:
                session_id = self.monitoring.start_session(
                    conversation_id=f"conv_{user_number}",
                    customer_data={
                        "customer_id": customer["id"],
                        "phone_number": user_number,
                        "tier": customer.get("tier", "basic")
                    }
                )
            
            # 6. Procesar con el sistema multi-agente
            response_data = await self._process_with_langgraph(
                message_text=message_text,
                user_number=user_number,
                customer=customer,
                session_id=session_id
            )
            
            if not response_data["success"]:
                # Si falla LangGraph, usar fallback
                return await self._handle_fallback_mode(message_text, user_number)
            
            bot_response = response_data["response"]
            
            # 7. Guardar en base de datos tradicional (para compatibilidad)
            await self._save_conversation_to_db(
                customer_id=customer["id"],
                user_message=message_text,
                bot_response=bot_response,
                intent=response_data.get("intent"),
                confidence=response_data.get("confidence"),
                whatsapp_message_id=message.id if hasattr(message, "id") else None,
            )
            
            # 8. Mantener conversación en Redis (para compatibilidad)
            await self._update_redis_conversation(user_number, message_text, bot_response)
            
            # 9. Enviar respuesta por WhatsApp
            await self._send_whatsapp_response(user_number, bot_response)
            
            # 10. Finalizar monitoreo
            if self.monitoring and session_id:
                self.monitoring.end_session(session_id)
            
            self.logger.info(f"Mensaje procesado exitosamente con LangGraph para {user_number}")
            return BotResponse(status="success", message=bot_response)
            
        except Exception as e:
            tb = traceback.format_exc()
            error_msg = f"Error procesando mensaje para {user_number or 'unknown'}"
            self.logger.error(f"{error_msg}: {e}\n{tb}")
            
            # Registrar error en monitoreo
            if self.monitoring and session_id:
                self.monitoring.end_session(session_id)
            
            # Intentar enviar mensaje de error al usuario
            if user_number:
                try:
                    await self._send_whatsapp_response(
                        user_number,
                        "Lo siento, ocurrió un error técnico. Por favor, intenta nuevamente en un momento. 🔧",
                    )
                except Exception as send_error:
                    self.logger.error(f"No se pudo enviar mensaje de error a {user_number}: {send_error}")
            
            return BotResponse(status="failure", message="Error en el procesamiento del mensaje")
    
    async def _process_with_langgraph(
        self,
        message_text: str,
        user_number: str,
        customer: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Procesa el mensaje usando el sistema LangGraph
        
        Args:
            message_text: Texto del mensaje
            user_number: Número del usuario
            customer: Datos del cliente
            session_id: ID de sesión de monitoreo
            
        Returns:
            Resultado del procesamiento
        """
        try:
            conversation_id = f"conv_{user_number}"
            
            # Preparar datos del cliente para LangGraph
            customer_data = {
                "customer_id": str(customer["id"]),
                "phone": user_number,
                "name": customer.get("profile_name", "Cliente"),
                "tier": customer.get("tier", "basic"),
                "preferences": customer.get("preferences", {}),
                "purchase_history": customer.get("purchase_history", [])
            }
            
            # Configuración de sesión
            session_config = {
                "session_id": session_id,
                "monitoring_enabled": bool(self.monitoring),
                "security_enabled": bool(self.security)
            }
            
            # Procesar con LangGraph
            result = await self.graph_system.process_message(
                message=message_text,
                conversation_id=conversation_id,
                customer_data=customer_data,
                session_config=session_config
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing with LangGraph: {e}")
            return {
                "success": False,
                "response": "Error interno del sistema",
                "error": str(e)
            }
    
    async def _handle_fallback_mode(self, message_text: str, user_number: str) -> BotResponse:
        """
        Modo de respuesta básica cuando LangGraph no está disponible
        """
        try:
            self.logger.info(f"Usando modo fallback para {user_number}")
            
            # Respuestas predefinidas básicas
            message_lower = message_text.lower()
            
            if any(word in message_lower for word in ["hola", "buenos", "buen", "inicio", "empezar"]):
                response_text = (
                    f"¡Hola! 👋 Soy tu asesor virtual de **{BUSINESS_NAME}**.\n\n"
                    "Estamos experimentando algunos problemas técnicos temporales, "
                    "pero estaré encantado de ayudarte con información básica.\n\n"
                    "¿En qué puedo ayudarte específicamente?"
                )
            elif any(word in message_lower for word in ["gracias", "chau", "adiós", "bye"]):
                response_text = (
                    f"¡Gracias por contactar **{BUSINESS_NAME}**! 😊\n\n"
                    "📞 Estamos aquí cuando nos necesites\n"
                    "🛡️ Garantía oficial en todos los productos\n\n"
                    "¡Que tengas un excelente día! 🚀"
                )
            else:
                response_text = (
                    f"¡Hola! Soy el asesor de **{BUSINESS_NAME}**. "
                    "Estamos disponibles para ayudarte con cualquier consulta sobre productos tecnológicos. 🖥️\n\n"
                    "Por favor, cuéntame específicamente qué necesitas y te asistiré lo mejor posible."
                )
            
            # Enviar respuesta
            await self._send_whatsapp_response(user_number, response_text)
            
            return BotResponse(status="success", message=response_text)
            
        except Exception as e:
            self.logger.error(f"Error en modo fallback para {user_number}: {e}")
            simple_message = f"¡Hola! Soy el asesor de {BUSINESS_NAME}. Estamos disponibles para ayudarte. 🖥️"
            
            try:
                await self._send_whatsapp_response(user_number, simple_message)
            except Exception:
                pass  # Si falla el envío, no hacer nada más
            
            return BotResponse(status="success", message=simple_message)
    
    async def _safe_get_or_create_customer(
        self, phone_number: str, profile_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Versión segura de obtención/creación de cliente con manejo de errores"""
        try:
            return await self.customer_service.get_or_create_customer(phone_number, profile_name)
        except Exception as e:
            self.logger.error(f"Error al obtener cliente {phone_number}: {e}")
            return None
    
    async def _update_redis_conversation(self, user_number: str, user_message: str, bot_response: str):
        """Actualiza la conversación en Redis para compatibilidad con el sistema existente"""
        try:
            conversation_key = f"conversation:{user_number}"
            conversation = self.redis_repo.get(conversation_key)
            
            if conversation is None:
                conversation = ConversationHistory(user_id=user_number)
            
            # Añadir mensajes
            conversation.add_message("persona", user_message)
            conversation.add_message("bot", bot_response)
            
            # Guardar en Redis
            self.redis_repo.set(conversation_key, conversation, expiration=CONVERSATION_EXPIRATION)
            
        except Exception as e:
            self.logger.error(f"Error actualizando conversación Redis para {user_number}: {e}")
    
    async def _save_conversation_to_db(
        self,
        customer_id: str,
        user_message: str,
        bot_response: str,
        intent: str = None,
        confidence: float = None,
        whatsapp_message_id: str = None,
    ) -> bool:
        """Guarda la conversación en la base de datos para compatibilidad"""
        try:
            with get_db_context() as db:
                # Buscar o crear conversación
                conversation = (
                    db.query(Conversation)
                    .filter(Conversation.customer_id == customer_id, Conversation.ended_at.is_(None))
                    .order_by(Conversation.started_at.desc())
                    .first()
                )
                
                if not conversation:
                    conversation = Conversation(
                        customer_id=customer_id,
                        session_id=f"langgraph_{customer_id}_{datetime.now().timestamp()}",
                    )
                    db.add(conversation)
                    db.flush()
                
                # Guardar mensaje del usuario
                user_msg = Message(
                    conversation_id=conversation.id,
                    message_type="user",
                    content=user_message,
                    intent=intent,
                    confidence=confidence,
                    whatsapp_message_id=whatsapp_message_id,
                    message_format="text",
                )
                db.add(user_msg)
                
                # Guardar respuesta del bot
                bot_msg = Message(
                    conversation_id=conversation.id,
                    message_type="bot",
                    content=bot_response,
                    message_format="text",
                )
                db.add(bot_msg)
                
                # Actualizar contadores
                conversation.total_messages = (conversation.total_messages or 0) + 2
                conversation.user_messages = (conversation.user_messages or 0) + 1
                conversation.bot_messages = (conversation.bot_messages or 0) + 1
                
                if intent:
                    conversation.intent_detected = intent
                conversation.updated_at = datetime.now(timezone.utc)
                
                db.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"Error al guardar conversación en DB: {e}")
            return False
    
    async def _send_whatsapp_response(self, user_number: str, message: str) -> bool:
        """Envía la respuesta por WhatsApp"""
        try:
            response = await self.whatsapp_service.enviar_mensaje_texto(user_number, message)
            
            if response.get("success", True):
                self.logger.info(f"Mensaje enviado exitosamente a {user_number}")
                return True
            else:
                self.logger.error(f"Error enviando mensaje a {user_number}: {response.get('error')}")
                return False
                
        except Exception as e:
            self.logger.error(f"Excepción al enviar mensaje a {user_number}: {e}")
            return False
    
    def _extract_message_text(self, message: WhatsAppMessage) -> str:
        """Extrae el texto del mensaje según su tipo"""
        try:
            if message.type == "text" and message.text:
                return message.text.body
            elif message.type == "interactive" and message.interactive:
                if message.interactive.type == "button_reply" and message.interactive.button_reply:
                    return message.interactive.button_reply.title
                elif message.interactive.type == "list_reply" and message.interactive.list_reply:
                    return message.interactive.list_reply.title
            
            self.logger.warning(f"No se pudo extraer texto del mensaje tipo: {message.type}")
            return ""
            
        except Exception as e:
            self.logger.error(f"Error extrayendo texto del mensaje: {e}")
            return ""
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Obtiene el estado de salud del sistema completo"""
        try:
            health_status = {
                "overall_status": "healthy",
                "components": {},
                "timestamp": datetime.now().isoformat()
            }
            
            # Estado de LangGraph
            if self.graph_system:
                langgraph_health = await self.graph_system.health_check()
                health_status["components"]["langgraph"] = langgraph_health
            else:
                health_status["components"]["langgraph"] = {
                    "status": "not_initialized"
                }
            
            # Estado de monitoreo
            if self.monitoring:
                monitoring_metrics = self.monitoring.get_performance_metrics()
                health_status["components"]["monitoring"] = {
                    "status": "healthy",
                    "metrics": monitoring_metrics
                }
            
            # Estado de seguridad
            if self.security:
                security_metrics = self.security.get_security_metrics()
                health_status["components"]["security"] = {
                    "status": "healthy",
                    "metrics": security_metrics
                }
            
            # Estado de base de datos
            db_healthy = await self._check_database_health()
            health_status["components"]["database"] = {
                "status": "healthy" if db_healthy else "unhealthy"
            }
            
            # Determinar estado general
            component_statuses = []
            for component in health_status["components"].values():
                if isinstance(component, dict):
                    component_statuses.append(component.get("status", "unknown"))
            
            if "unhealthy" in component_statuses or "not_initialized" in component_statuses:
                health_status["overall_status"] = "degraded"
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"Error getting system health: {e}")
            return {
                "overall_status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def get_conversation_history_langgraph(
        self,
        user_number: str,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Obtiene el historial de conversación desde LangGraph"""
        try:
            if not self.graph_system:
                return {"error": "LangGraph system not available"}
            
            conversation_id = f"conv_{user_number}"
            history = await self.graph_system.get_conversation_history(conversation_id, limit)
            
            return {
                "success": True,
                "conversation_id": conversation_id,
                "messages": history,
                "total_messages": len(history)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting LangGraph conversation history: {e}")
            return {"error": str(e)}
    
    async def cleanup(self):
        """Limpia recursos del sistema"""
        try:
            if self.graph_system:
                await self.graph_system.cleanup()
            
            if self.monitoring:
                # Limpiar tokens expirados
                self.monitoring.cleanup_old_checkpoints()
            
            if self.security:
                self.security.cleanup_expired_tokens()
            
            self.logger.info("LangGraphChatbotService cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    async def __aenter__(self):
        """Context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.cleanup()