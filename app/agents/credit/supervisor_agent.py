"""
Credit Supervisor Agent - Orchestrates credit system agents
"""

import logging
from datetime import UTC, datetime
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import OllamaLLM

from app.agents.credit.schemas import CreditAgentType, CreditState, UserRole
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class CreditSupervisorAgent:
    """Supervisor agent that routes credit requests to appropriate specialized agents"""

    def __init__(self):
        self.name = "credit_supervisor"
        self.logger = logging.getLogger(__name__)

        # Initialize LLM for intent classification
        settings = get_settings()
        self.llm = OllamaLLM(
            model=settings.OLLAMA_API_MODEL,
            base_url=settings.OLLAMA_API_URL,
            temperature=0.1,  # Lower temperature for more consistent routing
        )

        # Intent patterns for routing
        self.intent_patterns = {
            CreditAgentType.CREDIT_BALANCE: ["saldo", "balance", "límite", "disponible", "cuánto puedo", "cuánto debo"],
            CreditAgentType.CREDIT_APPLICATION: [
                "solicitar crédito",
                "aplicar",
                "nuevo crédito",
                "aumentar límite",
                "quiero un crédito",
            ],
            CreditAgentType.PAYMENT: ["pagar", "pago", "abonar", "depositar", "transferir", "cuota"],
            CreditAgentType.STATEMENT: ["estado de cuenta", "movimientos", "transacciones", "resumen", "extracto"],
            CreditAgentType.RISK_ASSESSMENT: ["evaluar riesgo", "scoring", "calificación", "análisis crediticio"],
            CreditAgentType.COLLECTION: ["cobranza", "mora", "vencido", "atrasado", "recuperación"],
            CreditAgentType.PRODUCT_CREDIT: ["agregar producto", "comprar a crédito", "producto en cuotas"],
            CreditAgentType.REFINANCING: ["refinanciar", "reestructurar", "cambiar plazo", "modificar crédito"],
        }

    async def process(self, state: CreditState) -> Dict[str, Any]:
        """Process incoming request and route to appropriate agent"""
        try:
            self.logger.info("Credit Supervisor processing request")

            # Get user message
            user_message = self._get_last_user_message(state)
            if not user_message:
                return self._create_welcome_response(state)

            # Analyze intent
            intent = await self._analyze_intent(user_message, state)
            self.logger.info(f"Detected intent: {intent}")

            # Route to appropriate agent
            next_agent = self._determine_next_agent(intent, state)
            self.logger.info(f"Routing to agent: {next_agent}")

            # Update state
            updated_state = dict(state)
            updated_state["current_agent"] = next_agent
            updated_state["intent"] = intent

            # Add supervisor message
            messages = updated_state.get("messages", [])
            if isinstance(messages, list):
                messages.append({
                    "role": "system",
                    "content": f"Routing to {next_agent} agent",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "metadata": {"agent": "supervisor", "intent": intent, "next_agent": next_agent},
                })
                updated_state["messages"] = messages

            return updated_state

        except Exception as e:
            self.logger.error(f"Error in supervisor: {str(e)}")
            return self._create_error_response(state, str(e))

    async def _analyze_intent(self, message: str, state: CreditState) -> str:
        """Analyze user intent from message"""
        # First try pattern matching for faster response
        intent = self._pattern_match_intent(message)
        if intent:
            return intent

        # If no pattern match, use LLM for intent classification
        try:
            system_prompt = """Eres un clasificador de intenciones para un sistema de crédito.
            Clasifica la intención del usuario en una de estas categorías:
            - credit_balance: Consultas de saldo, límite disponible
            - credit_application: Solicitudes de nuevo crédito o aumento de límite
            - payment: Pagos, abonos, cuotas
            - statement: Estados de cuenta, movimientos, transacciones
            - risk_assessment: Evaluación de riesgo (solo para analistas)
            - collection: Cobranza, cuentas vencidas
            - product_credit: Agregar productos al crédito
            - refinancing: Refinanciamiento, reestructuración
            - general: Consultas generales

            Responde SOLO con la categoría, sin explicación adicional."""

            user_prompt = f"Mensaje del usuario: {message}"

            response = await self.llm.ainvoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])

            intent = response.strip().lower()

            # Validate intent
            valid_intents = [agent.value for agent in CreditAgentType]
            if intent not in valid_intents:
                intent = "general"

            return intent

        except Exception as e:
            self.logger.error(f"Error in LLM intent analysis: {str(e)}")
            return "general"

    def _pattern_match_intent(self, message: str) -> Optional[str]:
        """Match message against predefined patterns"""
        message_lower = message.lower()

        for agent_type, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if pattern in message_lower:
                    return agent_type.value

        return None

    def _determine_next_agent(self, intent: str, state: CreditState) -> str:
        """Determine which agent should handle the request"""
        user_role = UserRole(state.get("user_role", UserRole.CUSTOMER))

        # Check role-based access
        if intent == CreditAgentType.RISK_ASSESSMENT.value:
            if user_role not in [UserRole.CREDIT_ANALYST, UserRole.MANAGER, UserRole.ADMIN]:
                return CreditAgentType.FALLBACK.value

        if intent == CreditAgentType.COLLECTION.value:
            # Customers can inquire about their overdue accounts
            # Staff can manage collection strategies
            pass

        # Map intent to agent
        agent_mapping = {
            "credit_balance": CreditAgentType.CREDIT_BALANCE.value,
            "credit_application": CreditAgentType.CREDIT_APPLICATION.value,
            "payment": CreditAgentType.PAYMENT.value,
            "statement": CreditAgentType.STATEMENT.value,
            "risk_assessment": CreditAgentType.RISK_ASSESSMENT.value,
            "collection": CreditAgentType.COLLECTION.value,
            "product_credit": CreditAgentType.PRODUCT_CREDIT.value,
            "refinancing": CreditAgentType.REFINANCING.value,
            "general": CreditAgentType.CREDIT_INQUIRY.value,
        }

        return agent_mapping.get(intent, CreditAgentType.FALLBACK.value)

    def _get_last_user_message(self, state: CreditState) -> Optional[str]:
        """Get the last user message from state"""
        for message in reversed(state.get("messages", [])):
            if message.get("role") == "user":
                return message.get("content", "")
        return None

    def _create_welcome_response(self, state: CreditState) -> Dict[str, Any]:
        """Create welcome response"""
        updated_state = dict(state)

        welcome_message = """🏦 **Bienvenido al Sistema de Crédito**

Soy tu asistente virtual de crédito. Puedo ayudarte con:

💳 **Consultas de Saldo** - Ver tu límite y crédito disponible
💰 **Pagos** - Realizar pagos y ver calendario de cuotas
📄 **Estados de Cuenta** - Revisar movimientos y transacciones
🎯 **Solicitudes de Crédito** - Aplicar para nuevo crédito o aumentos
🛍️ **Compras a Crédito** - Agregar productos a tu línea de crédito
📊 **Asesoría** - Información sobre productos y servicios

¿En qué puedo ayudarte hoy?"""

        messages = updated_state.get("messages", [])
        if isinstance(messages, list):
            messages.append({
                "role": "assistant",
                "content": welcome_message,
                "timestamp": datetime.now(UTC).isoformat(),
                "metadata": {"agent": "supervisor", "type": "welcome"},
            })
            updated_state["messages"] = messages

        return updated_state

    def _create_error_response(self, state: CreditState, error: str) -> Dict[str, Any]:
        """Create error response"""
        updated_state = dict(state)

        error_message = f"""❌ Lo siento, ocurrió un error al procesar tu solicitud.

Por favor, intenta nuevamente o contacta a soporte técnico si el problema persiste.

Error: {error}"""

        messages = updated_state.get("messages", [])
        if isinstance(messages, list):
            messages.append({
                "role": "assistant",
                "content": error_message,
                "timestamp": datetime.now(UTC).isoformat(),
                "metadata": {"agent": "supervisor", "type": "error", "error": error},
            })
            updated_state["messages"] = messages

        return updated_state

