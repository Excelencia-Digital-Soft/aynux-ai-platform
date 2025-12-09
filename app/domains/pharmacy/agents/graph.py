"""
Pharmacy Domain Graph

LangGraph StateGraph implementation for the pharmacy domain.
Handles debt checking, confirmation, and invoice generation workflows.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Hashable, cast

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from app.clients.pharmacy_erp_client import PharmacyERPClient
from app.domains.pharmacy.agents.nodes import (
    ConfirmationNode,
    DebtCheckNode,
    InvoiceGenerationNode,
)
from app.domains.pharmacy.agents.state import PharmacyState

logger = logging.getLogger(__name__)


class PharmacyNodeType:
    """Pharmacy domain node types."""

    ROUTER = "pharmacy_router"
    DEBT_CHECK = "debt_check_node"
    CONFIRMATION = "confirmation_node"
    INVOICE = "invoice_generation_node"


class PharmacyGraph:
    """
    Pharmacy domain LangGraph implementation.

    Handles the transactional flow:
    1. Debt Check -> Show debt to customer
    2. Confirmation -> Customer confirms debt
    3. Invoice Generation -> Generate invoice for confirmed debt

    The graph uses keyword-based routing (no LLM) for efficiency.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize pharmacy graph.

        Args:
            config: Graph configuration options
        """
        self.config = config or {}
        self.enabled_nodes = self.config.get(
            "enabled_nodes",
            [
                PharmacyNodeType.DEBT_CHECK,
                PharmacyNodeType.CONFIRMATION,
                PharmacyNodeType.INVOICE,
            ],
        )

        # Initialize ERP client (shared across nodes)
        self._erp_client = PharmacyERPClient()

        # Initialize nodes
        self._init_nodes()

        # Build graph
        self.graph = self._build_graph()
        self.app = None

        logger.info(f"PharmacyGraph initialized with nodes: {self.enabled_nodes}")

    def _init_nodes(self) -> None:
        """Initialize pharmacy domain nodes."""
        self.nodes: dict[str, DebtCheckNode | ConfirmationNode | InvoiceGenerationNode] = {}
        node_config = self.config.get("node_config", {})

        # Debt check node
        if PharmacyNodeType.DEBT_CHECK in self.enabled_nodes:
            self.nodes[PharmacyNodeType.DEBT_CHECK] = DebtCheckNode(
                erp_client=self._erp_client,
                config=node_config.get("debt_check", {}),
            )

        # Confirmation node
        if PharmacyNodeType.CONFIRMATION in self.enabled_nodes:
            self.nodes[PharmacyNodeType.CONFIRMATION] = ConfirmationNode(
                erp_client=self._erp_client,
                config=node_config.get("confirmation", {}),
            )

        # Invoice node
        if PharmacyNodeType.INVOICE in self.enabled_nodes:
            self.nodes[PharmacyNodeType.INVOICE] = InvoiceGenerationNode(
                erp_client=self._erp_client,
                config=node_config.get("invoice", {}),
            )

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph StateGraph for pharmacy domain."""
        workflow = StateGraph(PharmacyState)

        # Add router node
        workflow.add_node(PharmacyNodeType.ROUTER, self._route_query)

        # Add domain nodes
        for node_name, node_instance in self.nodes.items():
            workflow.add_node(node_name, self._create_node_executor(node_instance))

        # Set entry point
        workflow.set_entry_point(PharmacyNodeType.ROUTER)

        # Add conditional edges from router
        routing_map: dict[Hashable, str] = {
            PharmacyNodeType.DEBT_CHECK: PharmacyNodeType.DEBT_CHECK,
            PharmacyNodeType.CONFIRMATION: PharmacyNodeType.CONFIRMATION,
            PharmacyNodeType.INVOICE: PharmacyNodeType.INVOICE,
            "__end__": END,
        }

        workflow.add_conditional_edges(
            PharmacyNodeType.ROUTER,
            self._get_next_node,
            cast(dict[Hashable, str], routing_map),
        )

        # Add edges from nodes to END
        for node_name in self.nodes:
            workflow.add_edge(node_name, END)

        return workflow

    def _create_node_executor(
        self,
        node_instance: DebtCheckNode | ConfirmationNode | InvoiceGenerationNode,
    ):
        """Create async executor wrapper for a node."""

        async def executor(state: PharmacyState) -> dict[str, Any]:
            try:
                messages = state.get("messages", [])
                if not messages:
                    return {"error_count": state.get("error_count", 0) + 1}

                last_message = messages[-1]
                message_content = (
                    last_message.content
                    if hasattr(last_message, "content")
                    else str(last_message)
                )

                # Convert state to dict for processing
                state_dict = dict(state)
                result = await node_instance.process(str(message_content), state_dict)

                # Convert messages to proper format if needed
                if "messages" in result:
                    formatted_messages = []
                    for msg in result["messages"]:
                        if isinstance(msg, dict):
                            role = msg.get("role", "assistant")
                            content = msg.get("content", "")
                            if role == "assistant":
                                formatted_messages.append(AIMessage(content=content))
                            else:
                                formatted_messages.append(HumanMessage(content=content))
                        else:
                            formatted_messages.append(msg)
                    result["messages"] = formatted_messages

                return result

            except Exception as e:
                logger.error(f"Error in pharmacy node executor: {e}", exc_info=True)
                return {
                    "error_count": state.get("error_count", 0) + 1,
                    "messages": [
                        AIMessage(
                            content="Disculpa, tuve un problema. Podrias intentar de nuevo?"
                        )
                    ],
                }

        return executor

    async def _route_query(self, state: PharmacyState) -> dict[str, Any]:
        """
        Route incoming query to appropriate pharmacy node.

        Uses keyword-based routing for efficiency (no LLM calls).

        Args:
            state: Current pharmacy state

        Returns:
            State updates with routing decision
        """
        try:
            messages = state.get("messages", [])
            if not messages:
                return {"next_agent": "__end__", "is_complete": True}

            last_message = messages[-1]
            raw_content = (
                last_message.content
                if hasattr(last_message, "content")
                else str(last_message)
            )
            message_content = str(raw_content).lower().strip()

            # Check workflow state for continuation
            awaiting_confirmation = state.get("awaiting_confirmation", False)
            debt_status = state.get("debt_status")

            # If awaiting confirmation, check for yes/no response
            if awaiting_confirmation:
                if self._is_confirmation(message_content):
                    return {
                        "pharmacy_intent_type": "confirm",
                        "next_agent": PharmacyNodeType.CONFIRMATION,
                        "confirmation_received": True,
                    }
                elif self._is_rejection(message_content):
                    return {
                        "pharmacy_intent_type": "cancelled",
                        "next_agent": "__end__",
                        "is_complete": True,
                        "messages": [
                            AIMessage(
                                content="Entendido. La operacion ha sido cancelada. Hay algo mas en que pueda ayudarte?"
                            )
                        ],
                    }

            # Check for invoice request on confirmed debt
            if debt_status == "confirmed":
                if self._is_invoice_request(message_content):
                    return {
                        "pharmacy_intent_type": "invoice",
                        "next_agent": PharmacyNodeType.INVOICE,
                    }

            # Default: check debt
            intent_type, next_node = self._detect_intent(message_content)

            return {
                "pharmacy_intent_type": intent_type,
                "next_agent": next_node,
                "routing_decision": {
                    "domain": "pharmacy",
                    "intent_type": intent_type,
                    "routed_to": next_node,
                    "timestamp": datetime.now().isoformat(),
                },
            }

        except Exception as e:
            logger.error(f"Error in pharmacy routing: {e}", exc_info=True)
            return {
                "next_agent": PharmacyNodeType.DEBT_CHECK,
                "error_count": state.get("error_count", 0) + 1,
            }

    def _detect_intent(self, message: str) -> tuple[str, str]:
        """
        Detect pharmacy intent from message using keywords.

        Args:
            message: Lowercase user message

        Returns:
            Tuple of (intent_type, next_node)
        """
        # Invoice keywords
        invoice_keywords = [
            "factura",
            "generar factura",
            "facturar",
            "comprobante",
            "recibo",
        ]
        if any(kw in message for kw in invoice_keywords):
            return "invoice", PharmacyNodeType.INVOICE

        # Confirmation keywords
        confirm_keywords = ["confirmo", "confirmar", "acepto", "de acuerdo", "ok"]
        if any(kw in message for kw in confirm_keywords):
            return "confirm", PharmacyNodeType.CONFIRMATION

        # Debt query keywords (default)
        debt_keywords = [
            "deuda",
            "saldo",
            "cuanto debo",
            "estado",
            "cuenta",
            "pendiente",
            "debo",
            "debe",
        ]
        if any(kw in message for kw in debt_keywords):
            return "debt_query", PharmacyNodeType.DEBT_CHECK

        # Default to debt check
        return "debt_query", PharmacyNodeType.DEBT_CHECK

    def _is_confirmation(self, message: str) -> bool:
        """Check if message is a confirmation."""
        confirm_words = [
            "si",
            "sí",
            "confirmo",
            "acepto",
            "ok",
            "de acuerdo",
            "correcto",
            "dale",
            "bueno",
            "listo",
        ]
        # Check for exact match or starts with
        message_clean = message.strip().lower()
        return any(
            message_clean == word or message_clean.startswith(word + " ")
            for word in confirm_words
        )

    def _is_rejection(self, message: str) -> bool:
        """Check if message is a rejection."""
        reject_words = ["no", "cancelar", "rechazar", "incorrecto", "salir", "anular"]
        message_clean = message.strip().lower()
        return any(
            message_clean == word or message_clean.startswith(word + " ")
            for word in reject_words
        )

    def _is_invoice_request(self, message: str) -> bool:
        """Check if message requests invoice."""
        invoice_words = ["factura", "generar", "comprobante", "recibo"]
        return any(word in message for word in invoice_words)

    def _get_next_node(self, state: PharmacyState) -> str:
        """Get the next node from state for conditional routing."""
        next_node = state.get("next_agent")

        if next_node and next_node in self.nodes:
            return next_node

        if next_node == "__end__" or state.get("is_complete"):
            return "__end__"

        return PharmacyNodeType.DEBT_CHECK

    def initialize(self) -> None:
        """Initialize and compile the graph."""
        try:
            self.app = self.graph.compile()
            logger.info("PharmacyGraph compiled successfully")
        except Exception as e:
            logger.error(f"Error compiling PharmacyGraph: {e}", exc_info=True)
            raise

    async def invoke(
        self,
        message: str,
        conversation_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Process a message through the pharmacy graph.

        Args:
            message: User message to process
            conversation_id: Optional conversation ID for threading
            **kwargs: Additional state values to inject

        Returns:
            Final state after graph execution
        """
        if not self.app:
            raise RuntimeError("Graph not initialized. Call initialize() first")

        try:
            initial_state: dict[str, Any] = {
                "messages": [HumanMessage(content=message)],
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat(),
                "is_complete": False,
                "error_count": 0,
                "max_errors": self.config.get("max_errors", 3),
                "has_debt": False,
                "awaiting_confirmation": False,
                "confirmation_received": False,
                "is_bypass_route": kwargs.get("is_bypass_route", False),
                "requires_human": False,
                **kwargs,
            }

            config: dict[str, Any] = {}
            if conversation_id:
                config["configurable"] = {"thread_id": conversation_id}

            result = await self.app.ainvoke(
                initial_state,
                cast(RunnableConfig, config),
            )
            return dict(result)

        except Exception as e:
            logger.error(f"Error invoking PharmacyGraph: {e}", exc_info=True)
            raise

    async def health_check(self) -> dict[str, Any]:
        """
        Check health of the pharmacy graph and its components.

        Returns:
            Health status dictionary
        """
        health: dict[str, Any] = {
            "graph_compiled": self.app is not None,
            "nodes_enabled": list(self.nodes.keys()),
            "erp_client_configured": bool(self._erp_client.base_url),
        }

        # Test ERP connection if configured
        if self._erp_client.base_url:
            try:
                async with self._erp_client:
                    health["erp_connection"] = await self._erp_client.test_connection()
            except Exception as e:
                health["erp_connection"] = False
                health["erp_error"] = str(e)

        return health
