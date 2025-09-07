"""
Message processing logic for LangGraph chatbot service
"""

import logging
from typing import Any, Dict

from app.agents.graph import EcommerceAssistantGraph
from app.agents.schemas import ConversationContext, CustomerContext
from app.models.message import WhatsAppMessage
from app.utils.language_detector import get_language_detector

logger = logging.getLogger(__name__)


class MessageProcessor:
    """Handles message processing and LangGraph integration"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.language_detector = get_language_detector({
            "supported_languages": ["es", "en"],
            "default_language": "es",
            "confidence_threshold": 0.6,
            "cache_size": 500,
            "cache_ttl": 1800,  # 30 minutos
        })
    
    def extract_message_text(self, message: WhatsAppMessage) -> str:
        """Extrae el texto del mensaje de WhatsApp"""
        if hasattr(message, "text") and message.text:
            return message.text.body.strip()
        return ""
    
    def detect_language(self, text: str) -> str:
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
    
    async def process_with_langgraph(
        self,
        graph_system: EcommerceAssistantGraph,
        message_text: str,
        customer_context: CustomerContext,
        conversation_context: ConversationContext,
        session_id: str,
    ) -> Dict[str, Any]:
        """
        Procesa el mensaje usando el sistema LangGraph multi-agente.
        
        Args:
            graph_system: Sistema de graph LangGraph
            message_text: Texto del mensaje del usuario
            customer_context: Contexto del cliente
            conversation_context: Contexto de la conversación
            session_id: ID de la sesión
            
        Returns:
            Diccionario con respuesta del graph y metadatos
        """
        try:
            if not graph_system:
                raise RuntimeError("Graph system not initialized")
            
            # Procesar con el graph multi-agente
            result = await graph_system.invoke(
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
    
    def create_customer_context(self, user_id: str, metadata: Dict[str, Any] = None) -> CustomerContext:
        """Crea contexto del cliente para chat genérico"""
        metadata = metadata or {}
        
        return CustomerContext(
            customer_id=user_id,
            name=metadata.get("user_name", "Usuario"),
            email=metadata.get("email"),
            phone=metadata.get("phone", ""),
            tier=metadata.get("tier", "basic"),
            purchase_history=[],
            preferences=metadata.get("preferences", {}),
        )
    
    def create_conversation_context(self, session_id: str, message_text: str, metadata: Dict[str, Any] = None) -> ConversationContext:
        """Crea contexto de conversación"""
        metadata = metadata or {}
        
        return ConversationContext(
            conversation_id=session_id,
            session_id=session_id,
            channel=metadata.get("channel", "whatsapp"),
            language=metadata.get("language", self.detect_language(message_text)),
        )