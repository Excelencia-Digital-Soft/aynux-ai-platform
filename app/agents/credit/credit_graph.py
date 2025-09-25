"""
Credit System Graph Orchestration using LangGraph
"""

import logging
from datetime import UTC, datetime
from typing import Any, Dict, Optional

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph

from app.agents.credit.agents.collection_agent import CollectionAgent
from app.agents.credit.agents.credit_application_agent import CreditApplicationAgent
from app.agents.credit.agents.credit_balance_agent import CreditBalanceAgent
from app.agents.credit.agents.payment_agent import PaymentAgent
from app.agents.credit.agents.risk_assessment_agent import RiskAssessmentAgent
from app.agents.credit.agents.statement_agent import StatementAgent
from app.agents.credit.schemas import CreditAgentType, CreditState
from app.agents.credit.supervisor_agent import CreditSupervisorAgent
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class CreditSystemGraph:
    """Main orchestrator for credit system using LangGraph"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.graph = None
        self.compiled_graph = None
        self.checkpointer = None

        # Initialize agents
        self._init_agents()

        # Build the graph
        self._build_graph()

    def _init_agents(self):
        """Initialize all credit agents"""
        self.supervisor = CreditSupervisorAgent()
        self.agents = {
            CreditAgentType.CREDIT_BALANCE: CreditBalanceAgent(),
            CreditAgentType.CREDIT_APPLICATION: CreditApplicationAgent(),
            CreditAgentType.PAYMENT: PaymentAgent(),
            CreditAgentType.STATEMENT: StatementAgent(),
            CreditAgentType.RISK_ASSESSMENT: RiskAssessmentAgent(),
            CreditAgentType.COLLECTION: CollectionAgent(),
        }

    def _build_graph(self):
        """Build the credit system graph"""
        # Create state graph
        workflow = StateGraph(CreditState)

        # Add nodes
        workflow.add_node("supervisor", self.supervisor.process)

        # Add agent nodes
        for agent_type, agent in self.agents.items():
            workflow.add_node(agent_type.value, agent.process)

        # Add fallback node
        workflow.add_node("fallback", self._fallback_agent)
        workflow.add_node("end", self._end_node)

        # Set entry point
        workflow.set_entry_point("supervisor")

        # Add conditional edges from supervisor
        def route_from_supervisor(state: CreditState) -> str:
            """Route based on supervisor decision"""
            current_agent = state.get("current_agent", "fallback")
            self.logger.info(f"Routing from supervisor to: {current_agent}")

            # Check if agent exists
            if current_agent in [agent.value for agent in CreditAgentType]:
                return current_agent
            return "fallback"

        workflow.add_conditional_edges(
            "supervisor",
            route_from_supervisor,
            {
                CreditAgentType.CREDIT_BALANCE.value: CreditAgentType.CREDIT_BALANCE.value,
                CreditAgentType.CREDIT_APPLICATION.value: CreditAgentType.CREDIT_APPLICATION.value,
                CreditAgentType.PAYMENT.value: CreditAgentType.PAYMENT.value,
                CreditAgentType.STATEMENT.value: CreditAgentType.STATEMENT.value,
                CreditAgentType.RISK_ASSESSMENT.value: CreditAgentType.RISK_ASSESSMENT.value,
                CreditAgentType.COLLECTION.value: CreditAgentType.COLLECTION.value,
                "fallback": "fallback",
            },
        )

        # Add edges from agents back to supervisor or end
        for agent_type in self.agents.keys():
            workflow.add_conditional_edges(
                agent_type.value, self._should_continue, {"continue": "supervisor", "end": "end"}
            )

        # Add edge from fallback
        workflow.add_edge("fallback", "end")
        workflow.add_edge("end", END)

        # Compile the graph
        self.graph = workflow
        self.compiled_graph = workflow.compile()

    def _should_continue(self, state: CreditState) -> str:
        """Determine if conversation should continue or end"""
        # Check if there are pending operations
        if state.get("pending_operations"):
            return "continue"

        # Check for conversation ending signals
        last_message = self._get_last_message(state)
        if last_message and any(word in last_message.lower() for word in ["gracias", "adiós", "fin", "terminar"]):
            return "end"

        # Default to continue for interactive conversation
        return "continue"

    def _get_last_message(self, state: CreditState) -> Optional[str]:
        """Get last message from state"""
        messages = state.get("messages", [])
        if messages:
            last_msg = messages[-1]
            return last_msg.get("content", "")
        return None

    async def _fallback_agent(self, state: CreditState) -> Dict[str, Any]:
        """Fallback agent for unhandled requests"""
        updated_state = dict(state)

        fallback_message = """❓ Lo siento, no entendí tu solicitud.

Por favor, intenta reformular tu pregunta o selecciona una de estas opciones:

1️⃣ **Consultar saldo** - Ver tu crédito disponible
2️⃣ **Realizar pago** - Pagar tu crédito
3️⃣ **Estado de cuenta** - Ver tus movimientos
4️⃣ **Solicitar crédito** - Aplicar para nuevo crédito
5️⃣ **Hablar con asesor** - Contactar servicio al cliente

¿Cómo puedo ayudarte?"""

        # Ensure messages is a list and append
        messages = updated_state.get("messages", [])
        if isinstance(messages, list):
            messages.append({
                "role": "assistant",
                "content": fallback_message,
                "timestamp": datetime.now(UTC).isoformat(),
                "metadata": {"agent": "fallback"},
            })
            updated_state["messages"] = messages

        return updated_state

    async def _end_node(self, state: CreditState) -> Dict[str, Any]:
        """End node for conversation completion"""
        updated_state = dict(state)

        end_message = """👋 Gracias por usar nuestro sistema de crédito.

Si necesitas ayuda adicional, no dudes en contactarnos nuevamente.

¡Que tengas un excelente día!"""

        # Ensure messages is a list and append
        messages = updated_state.get("messages", [])
        if isinstance(messages, list):
            messages.append({
                "role": "assistant",
                "content": end_message,
                "timestamp": datetime.now(UTC).isoformat(),
                "metadata": {"agent": "end", "type": "farewell"},
            })
            updated_state["messages"] = messages

        return updated_state

    async def initialize_checkpointer(self):
        """Initialize PostgreSQL checkpointer for conversation persistence"""
        try:
            settings = get_settings()
            connection_string = (
                f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}"
                f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
            )

            async with AsyncPostgresSaver.from_conn_string(connection_string) as checkpointer:
                await checkpointer.setup()
                self.checkpointer = checkpointer

            # Recompile graph with checkpointer
            self.compiled_graph = self.graph.compile(checkpointer=self.checkpointer)

            self.logger.info("Credit graph checkpointer initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize checkpointer: {str(e)}")
            # Continue without checkpointing
            self.checkpointer = None

    async def process_message(
        self,
        message: str,
        user_id: str,
        user_role: str = "customer",
        session_id: Optional[str] = None,
        credit_account_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process a credit system message"""
        try:
            # Create initial state
            initial_state = CreditState(
                messages=[{"role": "user", "content": message, "timestamp": datetime.now(UTC).isoformat()}],
                current_agent="supervisor",
                user_id=user_id,
                user_role=user_role,
                session_id=session_id or f"session_{user_id}_{datetime.now(UTC).timestamp()}",
                credit_account_id=credit_account_id,
                context={},
                last_update=datetime.now(UTC).isoformat(),
                intent=None,
                risk_score=None,
                credit_limit=None,
                available_credit=None,
                payment_history=None,
                pending_operations=None,
            )

            # Configure for persistence if checkpointer available
            config = {}
            if self.checkpointer and session_id:
                config = {"configurable": {"thread_id": session_id}}

            # Process through graph
            result = await self.compiled_graph.ainvoke(initial_state, config)

            # Extract response
            if result and "messages" in result:
                # Get the last assistant message
                for msg in reversed(result["messages"]):
                    if msg.get("role") == "assistant":
                        return {
                            "success": True,
                            "message": msg.get("content", ""),
                            "metadata": msg.get("metadata", {}),
                            "state": {
                                "session_id": result.get("session_id"),
                                "credit_limit": result.get("credit_limit"),
                                "available_credit": result.get("available_credit"),
                                "risk_score": result.get("risk_score"),
                            },
                        }

            return {"success": False, "message": "No se pudo procesar tu solicitud.", "metadata": {}}

        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}")
            return {
                "success": False,
                "message": "Ocurrió un error al procesar tu mensaje. Por favor, intenta nuevamente.",
                "error": str(e),
            }

    def visualize_graph(self) -> Optional[bytes]:
        """Generate a visualization of the graph structure"""
        try:
            # Use LangGraph's built-in visualization
            img = self.compiled_graph.get_graph().draw_mermaid_png()
            if isinstance(img, bytes):
                return img
            return None
        except Exception as e:
            self.logger.error(f"Error visualizing graph: {str(e)}")
            return None

