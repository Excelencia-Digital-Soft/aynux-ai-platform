"""
Agente orquestador que analiza la intención del usuario y enruta a agentes especializados
"""

import logging
from typing import Any, Dict, List, Optional

from ..intelligence.intent_router import IntentRouter
from ..utils.tracing import trace_async_method
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """Agente orquestador que analiza intención y enruta mensajes a agentes especializados"""

    def __init__(self, ollama=None, config: Optional[Dict[str, Any]] = None):
        super().__init__("orchestrator", config or {}, ollama=ollama)

        # Configuración del orquestador
        self.confidence_threshold = self.config.get("confidence_threshold", 0.7)
        self.max_routing_attempts = self.config.get("max_routing_attempts", 2)

        # Inicializar el router de intents con thresholds ajustados para spaCy
        self.intent_router = IntentRouter(
            ollama=ollama,
            config={
                "confidence_threshold": min(self.confidence_threshold, 0.4),  # Threshold más bajo para router
                "fallback_agent": "fallback_agent",
                "use_spacy_fallback": True,
                "cache_size": 1000,
            },
        )

        logger.info("OrchestratorAgent initialized with intent routing")

    @trace_async_method(
        name="orchestrator_agent_process",
        run_type="agent",
        metadata={"agent_type": "orchestrator", "role": "intent_analysis"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analiza la intención del mensaje y determina el agente más apropiado.

        Args:
            message: Mensaje del usuario
            state_dict: Estado actual de la conversación

        Returns:
            Diccionario con la decisión de routing y análisis de intención
        """
        try:
            # Obtener contexto de la conversación
            conversation_history = state_dict.get("messages", [])
            customer_data = state_dict.get("customer_data", {})
            conversation_data = {
                "message_count": len(conversation_history),
                "current_agent": state_dict.get("current_agent"),
                "agent_history": state_dict.get("agent_history", []),
                "routing_attempts": state_dict.get("routing_attempts", 0),
            }

            # Analizar el intent del mensaje
            intent_result = await self.intent_router.determine_intent(
                message=message, customer_data=customer_data, conversation_data=conversation_data
            )

            # Extraer información del análisis
            intent = intent_result.get("primary_intent", "fallback")
            confidence = intent_result.get("confidence", 0.0)
            target_agent = intent_result.get("target_agent", "fallback_agent")

            logger.info(f"Intent analysis - Intent: {intent}, Agent: {target_agent}, Confidence: {confidence:.2f}")

            # Verificar confianza mínima y manejar umbral
            routing_decision = self._evaluate_routing_confidence(intent, confidence, target_agent, state_dict)

            # Preparar respuesta del orquestador
            return {
                "next_agent": routing_decision["target_agent"],
                "routing_decision": routing_decision,
                "orchestrator_analysis": {
                    "message": message,
                    "detected_intent": intent,
                    "confidence_score": confidence,
                    "routing_path": [self.name, routing_decision["target_agent"]],
                    "analysis_timestamp": self.get_current_timestamp(),
                },
                "needs_processing": True,  # Indica que el mensaje necesita ser procesado
                "routing_attempts": conversation_data["routing_attempts"] + 1,
            }

        except Exception as e:
            logger.error(f"Error in orchestrator processing: {str(e)}")

            # En caso de error, enviar a agente fallback
            return {
                "next_agent": "fallback_agent",
                "routing_decision": {
                    "intent": "error",
                    "confidence": 0.0,
                    "target_agent": "fallback_agent",
                    "reason": f"Error in orchestrator: {str(e)}",
                    "routing_strategy": "error_fallback",
                },
                "orchestrator_analysis": {
                    "error": str(e),
                    "fallback_triggered": True,
                    "analysis_timestamp": self.get_current_timestamp(),
                },
                "error_count": state_dict.get("error_count", 0) + 1,
                "needs_processing": True,
            }

    def _evaluate_routing_confidence(
        self, intent: str, confidence: float, target_agent: str, state_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evalúa la confianza del routing y determina la mejor estrategia.

        Args:
            intent: Intención detectada
            confidence: Confianza en la intención
            target_agent: Agente sugerido
            state_dict: Estado actual

        Returns:
            Diccionario con decisión de routing detallada
        """
        routing_attempts = state_dict.get("routing_attempts", 0)

        # Estrategia de routing basada en confianza
        if confidence >= self.confidence_threshold:
            routing_strategy = "high_confidence"
            final_agent = target_agent
            reason = f"High confidence ({confidence:.2f}) routing to {target_agent}"

        elif confidence >= 0.5 and routing_attempts == 0:
            # Primera oportunidad con confianza media
            routing_strategy = "medium_confidence_first_try"
            final_agent = target_agent
            reason = f"Medium confidence ({confidence:.2f}) routing to {target_agent} (first attempt)"

        elif routing_attempts >= self.max_routing_attempts:
            # Demasiados intentos, usar fallback
            routing_strategy = "max_attempts_fallback"
            final_agent = "fallback_agent"
            reason = f"Max routing attempts ({routing_attempts}) reached, using fallback"

        else:
            # Confianza baja, usar fallback
            routing_strategy = "low_confidence_fallback"
            final_agent = "fallback_agent"
            reason = f"Low confidence ({confidence:.2f}) < threshold ({self.confidence_threshold}), using fallback"

        logger.info(f"Routing decision: {routing_strategy} - {reason}")

        return {
            "intent": intent,
            "confidence": confidence,
            "target_agent": final_agent,
            "suggested_agent": target_agent,  # Agente originalmente sugerido
            "reason": reason,
            "routing_strategy": routing_strategy,
            "routing_attempts": routing_attempts + 1,
        }

    async def analyze_conversation_context(self, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analiza el contexto completo de la conversación para decisiones de routing.

        Args:
            state_dict: Estado actual de la conversación

        Returns:
            Análisis del contexto conversacional
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
            "detected_language": state_dict.get("language", "es"),
            "routing_history": self._analyze_routing_history(agent_history),
        }

        return context

    def _count_topic_switches(self, messages: List[Dict[str, Any]]) -> int:
        """Cuenta los cambios de tema en la conversación"""
        # Implementación simplificada basada en longitud de mensaje
        if len(messages) < 2:
            return 0

        # Asume cambio de tema en mensajes largos o después de cierto número de intercambios
        topic_switches = 0
        for i, msg in enumerate(messages):
            if i > 0 and len(msg.get("content", "")) > 100:
                topic_switches += 1

        return min(topic_switches, len(messages) // 3)  # Máximo un cambio cada 3 mensajes

    def _estimate_duration(self, state_dict: Dict[str, Any]) -> float:
        """Estima la duración de la conversación en minutos"""
        message_count = len(state_dict.get("messages", []))
        # Asume 45 segundos por intercambio de mensajes
        return message_count * 0.75

    def _analyze_routing_history(self, agent_history: List[str]) -> Dict[str, Any]:
        """
        Analiza el historial de routing para detectar patrones.

        Args:
            agent_history: Lista de agentes utilizados

        Returns:
            Análisis del historial de routing
        """
        if not agent_history:
            return {
                "total_routes": 0,
                "unique_agents": 0,
                "routing_efficiency": 1.0,
                "loop_detected": False,
            }

        unique_agents = set(agent_history)
        total_routes = len(agent_history)

        # Detectar loops (mismo agente repetido consecutivamente)
        loop_detected = False
        consecutive_same = 1
        for i in range(1, len(agent_history)):
            if agent_history[i] == agent_history[i - 1]:
                consecutive_same += 1
                if consecutive_same >= 3:  # 3 veces el mismo agente
                    loop_detected = True
                    break
            else:
                consecutive_same = 1

        # Calcular eficiencia de routing (menos rebotes = más eficiente)
        routing_efficiency = 1.0 - min(0.8, (total_routes - 1) * 0.15) if total_routes > 1 else 1.0

        return {
            "total_routes": total_routes,
            "unique_agents": len(unique_agents),
            "routing_efficiency": routing_efficiency,
            "loop_detected": loop_detected,
            "most_used_agent": max(set(agent_history), key=agent_history.count) if agent_history else None,
        }

    def get_routing_metrics(self) -> Dict[str, Any]:
        """
        Obtiene métricas de routing del orquestador.

        Returns:
            Diccionario con métricas de routing y análisis
        """
        base_metrics = self.get_agent_metrics()
        router_stats = self.intent_router._stats if hasattr(self.intent_router, "_stats") else {}

        return {
            **base_metrics,
            "orchestrator_metrics": {
                "total_routings": router_stats.get("total_requests", 0),
                "cache_hits": router_stats.get("cache_hits", 0),
                "cache_misses": router_stats.get("cache_misses", 0),
                "llm_calls": router_stats.get("llm_calls", 0),
                "fallback_routings": router_stats.get("fallback_calls", 0),
                "avg_routing_time": router_stats.get("avg_response_time", 0.0),
                "confidence_threshold": self.confidence_threshold,
                "max_routing_attempts": self.max_routing_attempts,
            },
        }

    def get_supported_intents(self) -> List[str]:
        """
        Obtiene la lista de intenciones soportadas por el orquestador.

        Returns:
            Lista de nombres de intenciones válidas
        """
        return self.intent_router.spacy_analyzer.get_supported_intents() if self.intent_router.spacy_analyzer else []