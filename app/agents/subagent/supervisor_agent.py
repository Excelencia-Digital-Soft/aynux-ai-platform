"""
Agente supervisor que orquesta el flujo de conversación
"""

import logging
from typing import Any, Dict, List, Optional

from ..intelligence.intent_router import IntentRouter
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class SupervisorAgent(BaseAgent):
    """Agente supervisor que enruta mensajes a agentes especializados"""

    def __init__(self, ollama=None, config: Optional[Dict[str, Any]] = None):
        super().__init__("supervisor", config or {}, ollama=ollama)
        
        # Configuración del supervisor
        self.max_retries = self.config.get("max_retries", 2)
        self.confidence_threshold = self.config.get("confidence_threshold", 0.7)
        self.enable_human_handoff = self.config.get("enable_human_handoff", False)
        
        # Inicializar el router de intents con thresholds ajustados para spaCy
        self.intent_router = IntentRouter(
            ollama=ollama,
            config={
                "confidence_threshold": min(self.confidence_threshold, 0.4),  # Threshold más bajo para router
                "fallback_agent": "fallback_agent",
                "use_spacy_fallback": True,
                "cache_size": 1000
            }
        )
        
        logger.info("SupervisorAgent initialized with intent routing")

    async def _process_internal(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa el mensaje y decide a qué agente delegarlo.
        
        Args:
            message: Mensaje del usuario
            state_dict: Estado actual de la conversación
            
        Returns:
            Diccionario con actualizaciones para el estado
        """
        try:
            # Obtener contexto de la conversación
            conversation_history = state_dict.get("messages", [])
            customer_data = state_dict.get("customer_data", {})
            conversation_data = {
                "message_count": len(conversation_history),
                "current_agent": state_dict.get("current_agent"),
                "agent_history": state_dict.get("agent_history", [])
            }
            
            # Analizar el intent del mensaje
            intent_result = await self.intent_router.determine_intent(
                message=message,
                customer_data=customer_data,
                conversation_data=conversation_data
            )
            
            # Extraer información del análisis
            intent = intent_result.get("primary_intent", "fallback")
            confidence = intent_result.get("confidence", 0.0)
            target_agent = intent_result.get("target_agent", "fallback_agent")
            
            logger.info(
                f"Intent analysis - Intent: {intent}, "
                f"Agent: {target_agent}, Confidence: {confidence:.2f}"
            )
            
            # Verificar si necesita escalamiento humano
            if self.enable_human_handoff and self._needs_human_handoff(intent, confidence, state_dict):
                return self._create_handoff_response(message, intent, state_dict)
            
            # Verificar confianza mínima (usar <= para evitar problemas de floating point)
            if confidence <= self.confidence_threshold:
                logger.warning(
                    f"Low confidence ({confidence:.2f}) <= threshold ({self.confidence_threshold}). "
                    f"Routing to fallback agent instead of {target_agent}"
                )
                target_agent = "fallback_agent"
            else:
                logger.info(
                    f"Confidence ({confidence:.2f}) > threshold ({self.confidence_threshold}). "
                    f"Routing to {target_agent}"
                )
            
            # Actualizar el estado con la decisión de routing
            return {
                "next_agent": target_agent,
                "routing_decision": {
                    "intent": intent,
                    "confidence": confidence,
                    "reason": intent_result.get("reasoning", ""),
                    "suggested_agent": target_agent
                },
                "supervisor_analysis": {
                    "message": message,
                    "detected_intent": intent,
                    "confidence_score": confidence,
                    "routing_path": [self.name, target_agent]
                },
                "needs_processing": True  # Indica que el mensaje necesita ser procesado
            }
            
        except Exception as e:
            logger.error(f"Error in supervisor processing: {str(e)}")
            
            # En caso de error, enviar a agente fallback
            return {
                "next_agent": "fallback_agent",
                "routing_decision": {
                    "intent": "error",
                    "confidence": 0.0,
                    "reason": f"Error in supervisor: {str(e)}",
                    "suggested_agent": "fallback_agent"
                },
                "error_count": state_dict.get("error_count", 0) + 1,
                "needs_processing": True
            }
    
    def _needs_human_handoff(self, intent: str, confidence: float, state_dict: Dict[str, Any]) -> bool:
        """
        Determina si la conversación necesita ser escalada a un humano.
        
        Args:
            intent: Intent detectado
            confidence: Confianza en el intent
            state_dict: Estado actual
            
        Returns:
            True si necesita escalamiento humano
        """
        # Verificar si hay demasiados errores
        error_count = state_dict.get("error_count", 0)
        if error_count >= self.max_retries:
            logger.info(f"Too many errors ({error_count}), suggesting human handoff")
            return True
        
        # Verificar intents que requieren humano
        human_required_intents = ["complaint", "legal_issue", "urgent_support"]
        if intent in human_required_intents:
            logger.info(f"Intent {intent} requires human handoff")
            return True
        
        # Verificar frustración del usuario
        frustration_keywords = ["no funciona", "terrible", "pésimo", "queja", "reclamo", "gerente"]
        message = state_dict.get("messages", [])[-1].get("content", "").lower() if state_dict.get("messages") else ""
        
        if any(keyword in message for keyword in frustration_keywords):
            logger.info("Detected user frustration, suggesting human handoff")
            return True
        
        return False
    
    def _create_handoff_response(self, message: str, intent: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea una respuesta para escalamiento a humano.
        
        Args:
            message: Mensaje del usuario
            intent: Intent detectado
            state_dict: Estado actual
            
        Returns:
            Diccionario con respuesta de escalamiento
        """
        return {
            "messages": [{
                "role": "assistant",
                "content": (
                    "Entiendo tu situación y quiero asegurarme de brindarte la mejor ayuda posible. "
                    "Te voy a conectar con un especialista humano que podrá asistirte mejor. "
                    "Por favor, espera un momento mientras te transfiero."
                )
            }],
            "human_handoff_requested": True,
            "handoff_reason": f"Intent: {intent}, Message: {message}",
            "current_agent": self.name,
            "is_complete": True
        }
    
    async def analyze_conversation_context(self, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analiza el contexto completo de la conversación para decisiones de routing.
        
        Args:
            state_dict: Estado actual de la conversación
            
        Returns:
            Análisis del contexto
        """
        messages = state_dict.get("messages", [])
        agent_history = state_dict.get("agent_history", [])
        
        # Analizar patrones en la conversación
        context = {
            "total_messages": len(messages),
            "unique_agents_used": len(set(agent_history)),
            "last_agent": agent_history[-1] if agent_history else None,
            "topic_switches": self._count_topic_switches(messages),
            "conversation_duration": self._estimate_duration(state_dict),
            "customer_tier": state_dict.get("customer_data", {}).get("tier", "basic"),
            "detected_language": state_dict.get("language", "es")
        }
        
        return context
    
    def _count_topic_switches(self, messages: List[Dict[str, Any]]) -> int:
        """Cuenta los cambios de tema en la conversación"""
        # Implementación simplificada
        return len(messages) // 3  # Asume cambio de tema cada 3 mensajes
    
    def _estimate_duration(self, state_dict: Dict[str, Any]) -> float:
        """Estima la duración de la conversación en minutos"""
        # Implementación simplificada
        message_count = len(state_dict.get("messages", []))
        return message_count * 0.5  # Asume 30 segundos por mensaje
    
    def get_routing_metrics(self) -> Dict[str, Any]:
        """
        Obtiene métricas de routing del supervisor.
        
        Returns:
            Diccionario con métricas de routing
        """
        base_metrics = self.get_agent_metrics()
        router_stats = self.intent_router._stats if hasattr(self.intent_router, '_stats') else {}
        
        return {
            **base_metrics,
            "routing_metrics": {
                "total_routings": router_stats.get("total_requests", 0),
                "cache_hits": router_stats.get("cache_hits", 0),
                "cache_misses": router_stats.get("cache_misses", 0),
                "llm_calls": router_stats.get("llm_calls", 0),
                "fallback_routings": router_stats.get("fallback_calls", 0),
                "avg_routing_time": router_stats.get("avg_response_time", 0.0)
            }
        }