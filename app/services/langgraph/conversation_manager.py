"""
Conversation management and post-processing for LangGraph chatbot service
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.models.conversation import ConversationHistory
from app.repositories.redis_repository import RedisRepository
from app.services.whatsapp_service import WhatsAppService

# Configurar expiración de conversación (24 horas)
CONVERSATION_EXPIRATION = 86400  # 24 horas en segundos

logger = logging.getLogger(__name__)


class ConversationManager:
    """Handles conversation caching, post-processing, and WhatsApp integration"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.redis_repo = RedisRepository[ConversationHistory](ConversationHistory, prefix="chat")
        self.whatsapp_service = WhatsAppService()
        self.monitoring = self._create_monitoring_placeholder()
    
    def _create_monitoring_placeholder(self):
        """Crea un placeholder simplificado para el sistema de monitoreo"""
        
        class MonitoringPlaceholder:
            async def record_message_processed(self, **kwargs):
                logger.info(
                    f"Message processed - Agent: {kwargs.get('agent_used', 'unknown')},"
                    f" Success: {kwargs.get('success', False)}"
                )
        
        return MonitoringPlaceholder()
    
    async def cache_conversation(self, session_id: str, user_message: str, bot_response: str):
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
    
    async def send_whatsapp_response(self, user_number: str, response: str):
        """Envía respuesta por WhatsApp (modo prueba)"""
        try:
            self.logger.info(f"[TEST MODE] WhatsApp message to {user_number}: {response[:50]}...")
            # TODO: Implement actual WhatsApp sending
            # await self.whatsapp_service.enviar_mensaje_texto(user_number, response)
        except Exception as e:
            self.logger.error(f"Error sending WhatsApp message: {e}")
            raise
    
    async def record_metrics(self, response_data: Dict[str, Any]):
        """Registra métricas del procesamiento"""
        try:
            await self.monitoring.record_message_processed(
                agent_used=response_data.get("agent_used"),
                success=True,
                response_time_ms=response_data.get("processing_time_ms", 0),
            )
        except Exception as e:
            self.logger.error(f"Error recording metrics: {e}")
    
    async def log_conversation_safely(
        self, user_number: str, user_message: str, bot_response: str, agent_used: Optional[str], session_id: str
    ):
        """Registra la conversación en la base de datos (placeholder)"""
        try:
            self.logger.info(f"Conversation log - User ({user_number}): {user_message[:100]}...")
            self.logger.info(f"Conversation log - Bot (agent: {agent_used}): {bot_response[:100]}...")
        except Exception as e:
            self.logger.error(f"Error logging conversation: {e}")
    
    async def handle_whatsapp_post_processing(
        self, db_available: bool, user_number: str, user_message: str, session_id: str, response_data: Dict[str, Any]
    ) -> None:
        """Maneja las operaciones post-procesamiento para WhatsApp"""
        try:
            # Operaciones básicas en paralelo
            tasks = [
                self.cache_conversation(session_id, user_message, response_data["response"]),
                self.send_whatsapp_response(user_number, response_data["response"]),
                self.record_metrics(response_data),
            ]
            
            # Añadir logging si DB disponible
            if db_available:
                tasks.append(
                    self.log_conversation_safely(
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
            self.logger.error(f"Error in WhatsApp post-processing: {e}")
    
    async def handle_chat_post_processing(
        self, user_id: str, user_message: str, session_id: str, response_data: Dict[str, Any]
    ) -> None:
        """Maneja post-procesamiento para mensajes de chat (sin WhatsApp)"""
        try:
            # Solo operaciones que aplican al chat (sin WhatsApp)
            tasks = [
                self.cache_conversation(session_id, user_message, response_data["response"]),
                self.record_metrics(response_data),
            ]
            
            # Logging simplificado
            self.logger.info(f"Chat log - User ({user_id}): {user_message[:100]}...")
            self.logger.info(
                f"Chat log - Bot (agent: {response_data.get('agent_used')}): {response_data['response'][:100]}..."
            )
            
            # Ejecutar tareas en paralelo
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"Error in chat post-processing: {e}")
    
    async def handle_processing_error(self, error: Exception, user_number: str):
        """Maneja errores de procesamiento de forma unificada"""
        from app.models.message import BotResponse  # Import here to avoid circular imports
        
        self.logger.error(f"Error processing webhook message: {str(error)}")
        
        fallback_response = ("Disculpa, estoy experimentando dificultades técnicas. "
                           "Por favor, intenta nuevamente en unos momentos.")
        
        try:
            await self.send_whatsapp_response(user_number, fallback_response)
        except Exception as send_error:
            self.logger.error(f"Error sending fallback response: {send_error}")
        
        return BotResponse(status="error", message=fallback_response, error=str(error))