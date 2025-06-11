"""
Supervisor que coordina el flujo entre agentes usando IA
"""

import logging

from app.agents.langgraph_system.integrations.ollama_integration import OllamaIntegration
from app.agents.langgraph_system.intelligence.intent_router import IntentRouter
from app.agents.langgraph_system.models import SharedState

logger = logging.getLogger(__name__)


class IntelligentSupervisor:
    """Supervisor que usa IA para coordinar agentes"""

    def __init__(self, intent_router: IntentRouter, ollama: OllamaIntegration):
        self.intent_router = intent_router
        self.ollama = ollama

    async def process(self, state: SharedState) -> SharedState:
        """Procesa el estado y determina el siguiente agente"""
        try:
            # Analizar intención si no existe o necesita actualización
            if not state.current_intent or self._should_reanalyze_intent(state):
                intent_info = await self.intent_router.analyze_intent(state)
                state.set_current_intent(intent_info)

            # Determinar siguiente agente usando IA
            next_agent = await self._determine_next_agent(state)
            state.set_current_agent(next_agent)

            logger.info(f"Supervisor assigned: {next_agent} for intent: {state.current_intent.primary_intent}")
            return state

        except Exception as e:
            logger.error(f"Error in supervisor: {e}")
            state.increment_error()
            state.set_current_agent("category_agent")  # Fallback seguro
            return state

    def _should_reanalyze_intent(self, state: SharedState) -> bool:
        """Determina si debe reanalizar la intención"""
        if not state.current_intent:
            return True

        # Reanalizar si confidence es baja
        if state.current_intent.confidence < 0.6:
            return True

        # Reanalizar cada cierto número de mensajes
        if len(state.messages) % 5 == 0:
            return True

        return False

    async def _determine_next_agent(self, state: SharedState) -> str:
        """Determina el siguiente agente usando lógica inteligente"""

        # Si hay una intención clara con agente target
        if state.current_intent and state.current_intent.target_agent:
            return state.current_intent.target_agent

        # Si se requiere intervención humana
        if state.requires_human:
            return "human_handoff"

        # Si hay demasiados errores
        if state.error_count >= state.max_errors:
            return "human_handoff"

        # Decisión inteligente basada en contexto
        return await self._ai_agent_decision(state)

    async def _ai_agent_decision(self, state: SharedState) -> str:
        """Usa IA para decidir el mejor agente"""

        prompt = f"""
        Basándote en el contexto de la conversación, determina el mejor agente para continuar:
        
        AGENTES DISPONIBLES:
        - product_agent: Consultas sobre productos, precios, stock
        - support_agent: Soporte técnico, problemas, asistencia
        - tracking_agent: Seguimiento de pedidos y envíos
        - invoice_agent: Facturación, pagos, cobros
        - promotions_agent: Ofertas y promociones
        - category_agent: Información general, navegación
        
        CONTEXTO:
        - Intención actual: {state.current_intent.primary_intent if state.current_intent else "desconocida"}
        - Agentes usados: {", ".join(state.agent_history)}
        - Número de mensajes: {len(state.messages)}
        - Número de errores: {state.error_count}
        
        Responde SOLO con el nombre del agente: [agent_name]
        """

        try:
            response = await self.ollama.generate_response(
                system_prompt="Eres un coordinador experto de agentes de IA.",
                user_prompt=prompt,
                model="llama3.1:8b",
                temperature=0.1,
            )

            # Extraer nombre del agente
            agent_name = response.strip().replace("[", "").replace("]", "")

            # Validar que el agente existe
            valid_agents = [
                "product_agent",
                "support_agent",
                "tracking_agent",
                "invoice_agent",
                "promotions_agent",
                "category_agent",
            ]

            if agent_name in valid_agents:
                return agent_name

        except Exception as e:
            logger.error(f"Error in AI agent decision: {e}")

        # Fallback: category_agent
        return "category_agent"
