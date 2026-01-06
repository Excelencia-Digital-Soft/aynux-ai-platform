"""
Credit Domain Graph

LangGraph StateGraph implementation for the credit domain.
Handles balance inquiries, payments, schedules, and collections.
"""

import logging
from datetime import datetime
from typing import Any, Hashable, cast

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from app.integrations.llm import VllmLLM

from .nodes import BalanceNode, PaymentNode, ScheduleNode
from .state import CreditState

logger = logging.getLogger(__name__)


class CreditNodeType:
    """Credit domain node types."""

    ROUTER = "credit_router"
    BALANCE = "balance_node"
    PAYMENT = "payment_node"
    SCHEDULE = "schedule_node"


class CreditGraph:
    """
    Credit domain LangGraph implementation.

    Handles routing and processing for all credit related queries:
    - Balance inquiries
    - Payment processing
    - Payment schedules
    - Collections (future)
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the credit domain graph.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.enabled_nodes = self.config.get(
            "enabled_nodes",
            [
                CreditNodeType.BALANCE,
                CreditNodeType.PAYMENT,
                CreditNodeType.SCHEDULE,
            ],
        )

        # Initialize integrations
        self._init_integrations()

        # Initialize nodes
        self._init_nodes()

        # Build graph
        self.graph = self._build_graph()
        self.app = None

        logger.info(f"CreditGraph initialized with nodes: {self.enabled_nodes}")

    def _init_integrations(self):
        """Initialize integrations."""
        # integrations_config reserved for future LLM configuration options
        _ = self.config.get("integrations", {})
        self.llm = VllmLLM()

    def _init_nodes(self):
        """Initialize credit domain nodes."""
        self.nodes: dict[str, Any] = {}

        node_config = self.config.get("node_config", {})

        # Balance node
        if CreditNodeType.BALANCE in self.enabled_nodes:
            self.nodes[CreditNodeType.BALANCE] = BalanceNode(
                llm=self.llm,
                config=node_config.get("balance", {}),
            )

        # Payment node
        if CreditNodeType.PAYMENT in self.enabled_nodes:
            self.nodes[CreditNodeType.PAYMENT] = PaymentNode(
                llm=self.llm,
                config=node_config.get("payment", {}),
            )

        # Schedule node
        if CreditNodeType.SCHEDULE in self.enabled_nodes:
            self.nodes[CreditNodeType.SCHEDULE] = ScheduleNode(
                llm=self.llm,
                config=node_config.get("schedule", {}),
            )

        logger.info(f"Initialized {len(self.nodes)} credit nodes")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph StateGraph for credit domain."""
        workflow = StateGraph(CreditState)

        # Add router node
        workflow.add_node(CreditNodeType.ROUTER, self._route_query)

        # Add domain nodes
        for node_name, node_instance in self.nodes.items():
            workflow.add_node(node_name, self._create_node_executor(node_instance))

        # Set entry point
        workflow.set_entry_point(CreditNodeType.ROUTER)

        # Add conditional edges from router to nodes
        routing_map: dict[Hashable, str] = {
            CreditNodeType.BALANCE: CreditNodeType.BALANCE,
            CreditNodeType.PAYMENT: CreditNodeType.PAYMENT,
            CreditNodeType.SCHEDULE: CreditNodeType.SCHEDULE,
            "__end__": END,
        }

        workflow.add_conditional_edges(
            CreditNodeType.ROUTER,
            self._get_next_node,
            cast(dict[Hashable, str], routing_map),
        )

        # Add edges from nodes to END
        for node_name in self.nodes:
            workflow.add_edge(node_name, END)

        return workflow

    def _create_node_executor(self, node_instance):
        """Create async executor wrapper for a node."""

        async def executor(state: CreditState) -> dict[str, Any]:
            try:
                messages = state.get("messages", [])
                if not messages:
                    return {"error_count": state.get("error_count", 0) + 1}

                last_message = messages[-1]
                message_content = (
                    last_message.content if hasattr(last_message, "content") else str(last_message)
                )

                result = await node_instance.process(message_content, state)
                return result

            except Exception as e:
                logger.error(f"Error in node executor: {e}")
                return {
                    "error_count": state.get("error_count", 0) + 1,
                    "messages": [
                        {
                            "role": "assistant",
                            "content": "Disculpa, tuve un problema. ¿Podrías intentar de nuevo?",
                        }
                    ],
                }

        return executor

    async def _route_query(self, state: CreditState) -> dict[str, Any]:
        """Route incoming query to appropriate credit node."""
        try:
            messages = state.get("messages", [])
            if not messages:
                return {"next_agent": "__end__", "is_complete": True}

            last_message = messages[-1]
            raw_content = last_message.content if hasattr(last_message, "content") else str(last_message)
            message_content = str(raw_content).lower()

            intent_type, next_node = self._detect_intent(message_content)

            return {
                "credit_intent_type": intent_type,
                "next_agent": next_node,
                "routing_decision": {
                    "domain": "credit",
                    "intent_type": intent_type,
                    "routed_to": next_node,
                    "timestamp": datetime.now().isoformat(),
                },
            }

        except Exception as e:
            logger.error(f"Error in routing: {e}")
            return {
                "next_agent": CreditNodeType.BALANCE,
                "error_count": state.get("error_count", 0) + 1,
            }

    def _detect_intent(self, message: str) -> tuple[str, str]:
        """Detect credit intent from message."""
        # Payment keywords
        payment_keywords = [
            "pagar",
            "pago",
            "abonar",
            "depositar",
            "transferir",
            "liquidar",
            "historial de pagos",
        ]
        if any(kw in message for kw in payment_keywords):
            return "payment", CreditNodeType.PAYMENT

        # Schedule keywords
        schedule_keywords = [
            "calendario",
            "proximos pagos",
            "cronograma",
            "plan de pagos",
            "siguiente pago",
            "proximo pago",
            "fecha de pago",
            "cuando debo",
        ]
        if any(kw in message for kw in schedule_keywords):
            return "schedule", CreditNodeType.SCHEDULE

        # Balance keywords (default)
        balance_keywords = [
            "saldo",
            "balance",
            "disponible",
            "credito",
            "limite",
            "deuda",
            "cuanto debo",
            "estado de cuenta",
        ]
        if any(kw in message for kw in balance_keywords):
            return "balance", CreditNodeType.BALANCE

        # Default to balance for credit queries
        return "balance", CreditNodeType.BALANCE

    def _get_next_node(self, state: CreditState) -> str:
        """Get the next node from state for conditional routing."""
        next_node = state.get("next_agent")

        if next_node and next_node in self.nodes:
            return next_node

        if next_node == "__end__" or state.get("is_complete"):
            return "__end__"

        return CreditNodeType.BALANCE

    def initialize(self):
        """Initialize and compile the graph."""
        try:
            self.app = self.graph.compile()
            logger.info("CreditGraph compiled successfully")
        except Exception as e:
            logger.error(f"Error compiling CreditGraph: {e}")
            raise

    async def invoke(
        self,
        message: str,
        conversation_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Process a message through the credit graph."""
        if not self.app:
            raise RuntimeError("Graph not initialized. Call initialize() first")

        try:
            initial_state = {
                "messages": [HumanMessage(content=message)],
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat(),
                "is_complete": False,
                "error_count": 0,
                "max_errors": self.config.get("max_errors", 3),
                **kwargs,
            }

            config: dict[str, Any] = {}
            if conversation_id:
                config["configurable"] = {"thread_id": conversation_id}

            result = await self.app.ainvoke(initial_state, cast(RunnableConfig, config))
            return result

        except Exception as e:
            logger.error(f"Error invoking CreditGraph: {e}")
            raise

    async def health_check(self) -> dict[str, Any]:
        """Check health of all nodes."""
        health: dict[str, Any] = {
            "healthy": True,
            "nodes": {},
        }

        for node_name, node_instance in self.nodes.items():
            try:
                if hasattr(node_instance, "health_check"):
                    node_health = await node_instance.health_check()
                    health["nodes"][node_name] = node_health
                else:
                    health["nodes"][node_name] = {"healthy": True}
            except Exception as e:
                health["nodes"][node_name] = {"healthy": False, "error": str(e)}
                health["healthy"] = False

        return health

    def get_enabled_nodes(self) -> list[str]:
        """Get list of enabled node names."""
        return list(self.nodes.keys())


# Alias for compatibility
CreditDomainGraph = CreditGraph
