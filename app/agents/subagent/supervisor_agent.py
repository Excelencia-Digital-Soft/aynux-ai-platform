"""
Agente supervisor que evalúa respuestas y gestiona la calidad de la conversación
"""

import logging
from typing import Any, Dict, List, Optional

from ..utils.tracing import trace_async_method
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class SupervisorAgent(BaseAgent):
    """Agente supervisor que evalúa la calidad de respuestas y gestiona el flujo conversacional"""

    def __init__(self, ollama=None, config: Optional[Dict[str, Any]] = None):
        super().__init__("supervisor", config or {}, ollama=ollama)

        # Configuración del supervisor
        self.max_retries = self.config.get("max_retries", 2)
        self.quality_threshold = self.config.get("quality_threshold", 0.7)
        self.enable_human_handoff = self.config.get("enable_human_handoff", True)
        self.enable_re_routing = self.config.get("enable_re_routing", True)
        
        # Umbrales de calidad para diferentes aspectos
        self.quality_thresholds = {
            "response_completeness": self.config.get("completeness_threshold", 0.6),
            "response_relevance": self.config.get("relevance_threshold", 0.7),
            "task_completion": self.config.get("task_completion_threshold", 0.8),
        }

        logger.info("SupervisorAgent initialized for response evaluation and quality control")

    @trace_async_method(
        name="supervisor_agent_process",
        run_type="agent",
        metadata={"agent_type": "supervisor", "role": "response_evaluation"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evalúa la respuesta del agente anterior y determina si la conversación debe continuar.

        Args:
            message: Mensaje del usuario (para contexto)
            state_dict: Estado actual de la conversación incluyendo la respuesta del agente

        Returns:
            Diccionario con evaluación de calidad y decisión de flujo
        """
        try:
            # Obtener contexto de la conversación
            conversation_history = state_dict.get("messages", [])
            current_agent = state_dict.get("current_agent")
            agent_history = state_dict.get("agent_history", [])
            
            # Obtener la última respuesta del agente
            last_response = self._extract_last_agent_response(conversation_history)
            
            if not last_response:
                return self._handle_missing_response(state_dict)

            # Evaluar la calidad de la respuesta
            quality_evaluation = await self._evaluate_response_quality(
                user_message=message,
                agent_response=last_response,
                agent_name=current_agent,
                conversation_context=state_dict
            )

            # Determinar si la conversación debe continuar
            flow_decision = self._determine_conversation_flow(quality_evaluation, state_dict)

            # Preparar respuesta del supervisor
            return {
                "supervisor_evaluation": quality_evaluation,
                "conversation_flow": flow_decision,
                "is_complete": flow_decision.get("should_end", False),
                "needs_re_routing": flow_decision.get("needs_re_routing", False),
                "human_handoff_requested": flow_decision.get("needs_human_handoff", False),
                "supervisor_analysis": {
                    "current_agent": current_agent,
                    "quality_score": quality_evaluation.get("overall_score", 0.0),
                    "evaluation_timestamp": self.get_current_timestamp(),
                    "flow_decision": flow_decision["decision_type"],
                },
            }

        except Exception as e:
            logger.error(f"Error in supervisor evaluation: {str(e)}")
            return self._handle_evaluation_error(str(e), state_dict)

    def _extract_last_agent_response(self, conversation_history: List[Dict[str, Any]]) -> Optional[str]:
        """
        Extrae la última respuesta del agente de la conversación.

        Args:
            conversation_history: Historial de mensajes

        Returns:
            Contenido de la última respuesta del agente
        """
        if not conversation_history:
            return None

        # Buscar la última respuesta del asistente
        for message in reversed(conversation_history):
            if isinstance(message, dict) and message.get("role") == "assistant":
                return message.get("content", "")
            elif hasattr(message, "content") and hasattr(message, "role"):
                if getattr(message, "role", None) == "assistant":
                    return getattr(message, "content", "")

        return None

    async def _evaluate_response_quality(
        self, user_message: str, agent_response: str, agent_name: str, conversation_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evalúa la calidad de la respuesta del agente.

        Args:
            user_message: Mensaje original del usuario
            agent_response: Respuesta del agente
            agent_name: Nombre del agente que respondió
            conversation_context: Contexto completo de la conversación

        Returns:
            Diccionario con evaluación de calidad
        """
        # Evaluar diferentes aspectos de la calidad
        completeness_score = self._evaluate_completeness(user_message, agent_response)
        relevance_score = self._evaluate_relevance(user_message, agent_response, agent_name)
        clarity_score = self._evaluate_clarity(agent_response)
        helpfulness_score = self._evaluate_helpfulness(agent_response, agent_name)

        # Calcular puntaje general
        overall_score = (
            completeness_score * 0.3 + relevance_score * 0.3 + clarity_score * 0.2 + helpfulness_score * 0.2
        )

        return {
            "overall_score": overall_score,
            "completeness_score": completeness_score,
            "relevance_score": relevance_score,
            "clarity_score": clarity_score,
            "helpfulness_score": helpfulness_score,
            "agent_name": agent_name,
            "response_length": len(agent_response),
            "evaluation_details": {
                "has_actionable_content": self._has_actionable_content(agent_response),
                "provides_specific_info": self._provides_specific_info(agent_response),
                "appropriate_tone": self._has_appropriate_tone(agent_response),
            },
        }

    def _determine_conversation_flow(self, quality_evaluation: Dict[str, Any], state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determina el siguiente paso en el flujo de conversación basado en la evaluación de calidad.

        Args:
            quality_evaluation: Evaluación de calidad de la respuesta
            state_dict: Estado actual de la conversación

        Returns:
            Diccionario con decisión de flujo
        """
        overall_score = quality_evaluation.get("overall_score", 0.0)
        agent_history = state_dict.get("agent_history", [])
        error_count = state_dict.get("error_count", 0)
        retry_count = state_dict.get("supervisor_retry_count", 0)

        # Verificar si necesita escalamiento humano
        if self._needs_human_handoff_evaluation(quality_evaluation, state_dict):
            return {
                "decision_type": "human_handoff",
                "should_end": True,
                "needs_human_handoff": True,
                "reason": "Response quality below threshold or user frustration detected",
            }

        # Verificar si la respuesta es satisfactoria
        if overall_score >= self.quality_threshold:
            return {
                "decision_type": "conversation_complete",
                "should_end": True,
                "reason": f"High quality response (score: {overall_score:.2f})",
            }

        # Verificar si necesita re-routing
        if self.enable_re_routing and retry_count < self.max_retries and overall_score < 0.5:
            return {
                "decision_type": "re_route",
                "should_end": False,
                "needs_re_routing": True,
                "reason": f"Low quality response (score: {overall_score:.2f}), attempting re-route",
            }

        # Si no se puede mejorar más, terminar la conversación
        return {
            "decision_type": "conversation_end",
            "should_end": True,
            "reason": "Max retries reached or quality cannot be improved further",
        }

    def _evaluate_completeness(self, user_message: str, agent_response: str) -> float:
        """Evalúa si la respuesta es completa basada en la pregunta del usuario."""
        if not agent_response or len(agent_response) < 10:
            return 0.0

        # Heurísticas simples para evaluar completeness
        response_length = len(agent_response)
        question_indicators = len([word for word in ["qué", "cómo", "dónde", "cuándo", "por qué", "cuánto"] 
                                   if word in user_message.lower()])

        # Penalizar respuestas muy cortas para preguntas complejas
        if question_indicators > 0 and response_length < 50:
            return 0.3

        # Recompensar respuestas con información estructurada
        if response_length > 100 and any(indicator in agent_response.lower() 
                                        for indicator in ["información", "detalles", "proceso", "pasos"]):
            return 0.9

        # Puntuación base por longitud y estructura
        base_score = min(0.8, response_length / 200)
        return base_score

    def _evaluate_relevance(self, user_message: str, agent_response: str, agent_name: str) -> float:
        """Evalúa si la respuesta es relevante al mensaje del usuario."""
        if not agent_response:
            return 0.0

        user_words = set(user_message.lower().split())
        response_words = set(agent_response.lower().split())
        
        # Calcular solapamiento de palabras
        common_words = user_words.intersection(response_words)
        word_overlap = len(common_words) / len(user_words) if user_words else 0

        # Considerar si el agente es apropiado para el tipo de consulta
        agent_relevance = self._check_agent_relevance(user_message, agent_name)

        # Combinar métricas
        return min(1.0, word_overlap * 0.6 + agent_relevance * 0.4)

    def _evaluate_clarity(self, agent_response: str) -> float:
        """Evalúa la claridad y legibilidad de la respuesta."""
        if not agent_response:
            return 0.0

        # Heurísticas para claridad
        sentence_count = len([s for s in agent_response.split('.') if len(s.strip()) > 5])
        avg_sentence_length = len(agent_response) / max(1, sentence_count)
        
        # Penalizar oraciones muy largas o muy cortas
        clarity_score = 0.8
        if avg_sentence_length > 150:
            clarity_score -= 0.3
        elif avg_sentence_length < 10:
            clarity_score -= 0.2

        # Recompensar estructura clara
        if any(indicator in agent_response.lower() for indicator in ["primero", "segundo", "además", "finalmente"]):
            clarity_score += 0.1

        return max(0.0, min(1.0, clarity_score))

    def _evaluate_helpfulness(self, agent_response: str, agent_name: str) -> float:
        """Evalúa qué tan útil es la respuesta para el usuario."""
        if not agent_response:
            return 0.0

        helpfulness_score = 0.5  # Base score

        # Recompensar contenido accionable
        if self._has_actionable_content(agent_response):
            helpfulness_score += 0.2

        # Recompensar información específica
        if self._provides_specific_info(agent_response):
            helpfulness_score += 0.2

        # Recompensar tono apropiado
        if self._has_appropriate_tone(agent_response):
            helpfulness_score += 0.1

        return min(1.0, helpfulness_score)

    def _has_actionable_content(self, agent_response: str) -> bool:
        """Verifica si la respuesta contiene contenido accionable."""
        action_indicators = [
            "puedes", "debes", "recomiendo", "sugiero", "pasos", "proceso",
            "hacer", "seguir", "contactar", "verificar", "comprobar"
        ]
        return any(indicator in agent_response.lower() for indicator in action_indicators)

    def _provides_specific_info(self, agent_response: str) -> bool:
        """Verifica si la respuesta proporciona información específica."""
        specific_indicators = [
            "precio", "costo", "disponible", "stock", "características",
            "modelo", "marca", "especificaciones", "número", "fecha"
        ]
        return any(indicator in agent_response.lower() for indicator in specific_indicators)

    def _has_appropriate_tone(self, agent_response: str) -> bool:
        """Verifica si la respuesta tiene un tono apropiado."""
        positive_indicators = ["gracias", "gusto", "ayudar", "servicio", "atención"]
        negative_indicators = ["no puedo", "no sé", "imposible", "error"]
        
        positive_count = sum(1 for indicator in positive_indicators if indicator in agent_response.lower())
        negative_count = sum(1 for indicator in negative_indicators if indicator in agent_response.lower())
        
        return positive_count > negative_count

    def _check_agent_relevance(self, user_message: str, agent_name: str) -> float:
        """Verifica si el agente es relevante para el mensaje del usuario."""
        # Mapeo simple de keywords a tipos de agente
        agent_keywords = {
            "product_agent": ["producto", "precio", "stock", "disponible", "características"],
            "category_agent": ["categoría", "tipo", "clase", "sección"],
            "support_agent": ["problema", "ayuda", "soporte", "técnico", "falla"],
            "tracking_agent": ["pedido", "envío", "seguimiento", "entrega"],
            "invoice_agent": ["factura", "pago", "cobro", "recibo"],
            "promotions_agent": ["descuento", "oferta", "promoción", "cupón"],
        }

        keywords = agent_keywords.get(agent_name, [])
        if not keywords:
            return 0.5  # Neutral para agentes no mapeados

        matches = sum(1 for keyword in keywords if keyword in user_message.lower())
        return min(1.0, matches / len(keywords) * 2)

    def _needs_human_handoff_evaluation(self, quality_evaluation: Dict[str, Any], state_dict: Dict[str, Any]) -> bool:
        """Determina si necesita escalamiento humano basado en la evaluación."""
        # Verificar si hay demasiados errores
        error_count = state_dict.get("error_count", 0)
        retry_count = state_dict.get("supervisor_retry_count", 0)
        
        if error_count >= self.max_retries or retry_count >= self.max_retries:
            logger.info(f"Too many errors/retries ({error_count}/{retry_count}), suggesting human handoff")
            return True

        # Verificar si la calidad es muy baja
        overall_score = quality_evaluation.get("overall_score", 0.0)
        if overall_score < 0.3:
            logger.info(f"Very low quality score ({overall_score:.2f}), suggesting human handoff")
            return True

        # Verificar frustración del usuario en mensajes recientes
        messages = state_dict.get("messages", [])
        if self._detect_user_frustration(messages):
            return True

        return False

    def _detect_user_frustration(self, messages: List[Dict[str, Any]]) -> bool:
        """Detecta frustración del usuario en mensajes recientes."""
        frustration_keywords = [
            "no funciona", "terrible", "pésimo", "queja", "reclamo", 
            "gerente", "supervisor", "no sirve", "horrible", "malo"
        ]
        
        # Revisar los últimos 2 mensajes del usuario
        user_messages = [msg for msg in messages[-4:] 
                        if (isinstance(msg, dict) and msg.get("role") == "user")][-2:]
        
        for msg in user_messages:
            content = msg.get("content", "").lower()
            if any(keyword in content for keyword in frustration_keywords):
                logger.info("Detected user frustration, suggesting human handoff")
                return True
        
        return False

    def _handle_missing_response(self, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Maneja el caso donde no hay respuesta del agente anterior."""
        return {
            "supervisor_evaluation": {
                "overall_score": 0.0,
                "error": "No agent response found",
            },
            "conversation_flow": {
                "decision_type": "error_fallback",
                "should_end": False,
                "needs_re_routing": True,
            },
            "needs_re_routing": True,
            "supervisor_analysis": {
                "error": "Missing agent response",
                "evaluation_timestamp": self.get_current_timestamp(),
            },
        }

    def _handle_evaluation_error(self, error_message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Maneja errores durante la evaluación."""
        return {
            "supervisor_evaluation": {
                "overall_score": 0.0,
                "error": error_message,
            },
            "conversation_flow": {
                "decision_type": "error_end",
                "should_end": True,
            },
            "is_complete": True,
            "error_count": state_dict.get("error_count", 0) + 1,
            "supervisor_analysis": {
                "error": error_message,
                "evaluation_timestamp": self.get_current_timestamp(),
            },
        }

    def get_supervisor_metrics(self) -> Dict[str, Any]:
        """
        Obtiene métricas del supervisor.

        Returns:
            Diccionario con métricas de evaluación
        """
        base_metrics = self.get_agent_metrics()

        return {
            **base_metrics,
            "supervisor_metrics": {
                "quality_threshold": self.quality_threshold,
                "max_retries": self.max_retries,
                "human_handoff_enabled": self.enable_human_handoff,
                "re_routing_enabled": self.enable_re_routing,
                "quality_thresholds": self.quality_thresholds,
            },
        }

