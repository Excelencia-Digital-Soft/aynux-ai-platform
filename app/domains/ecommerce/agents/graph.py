"""
E-commerce Domain Graph

LangGraph StateGraph implementation for the e-commerce domain.
Handles product queries, orders, promotions, tracking, and billing.
"""

import logging
from datetime import datetime
from typing import Any, Hashable, cast

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from app.integrations.llm import OllamaLLM
from app.integrations.databases import PostgreSQLIntegration

from .nodes import InvoiceNode, ProductNode, PromotionsNode, TrackingNode
from .state import EcommerceState

logger = logging.getLogger(__name__)


class EcommerceNodeType:
    """E-commerce domain node types."""

    ROUTER = "ecommerce_router"
    PRODUCT = "product_node"
    PROMOTIONS = "promotions_node"
    TRACKING = "tracking_node"
    INVOICE = "invoice_node"


class EcommerceGraph:
    """
    E-commerce domain LangGraph implementation.

    Handles routing and processing for all e-commerce related queries:
    - Product search and catalog
    - Promotions and discounts
    - Order tracking
    - Billing and invoices
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the e-commerce domain graph.

        Args:
            config: Configuration dictionary with:
                - integrations: Ollama and PostgreSQL settings
                - enabled_nodes: List of enabled node names
                - max_errors: Maximum errors before failing
        """
        self.config = config or {}
        self.enabled_nodes = self.config.get(
            "enabled_nodes",
            [
                EcommerceNodeType.PRODUCT,
                EcommerceNodeType.PROMOTIONS,
                EcommerceNodeType.TRACKING,
                EcommerceNodeType.INVOICE,
            ],
        )

        # Initialize integrations
        self._init_integrations()

        # Initialize nodes
        self._init_nodes()

        # Build graph
        self.graph = self._build_graph()
        self.app = None

        logger.info(f"EcommerceGraph initialized with nodes: {self.enabled_nodes}")

    def _init_integrations(self):
        """Initialize integrations (Ollama, PostgreSQL)."""
        integrations_config = self.config.get("integrations", {})

        self.ollama = OllamaLLM()
        self.postgres = PostgreSQLIntegration(integrations_config.get("postgres", {}))

    def _init_nodes(self):
        """Initialize e-commerce domain nodes."""
        self.nodes: dict[str, Any] = {}

        node_config = self.config.get("node_config", {})

        # Product node
        if EcommerceNodeType.PRODUCT in self.enabled_nodes:
            self.nodes[EcommerceNodeType.PRODUCT] = ProductNode(
                ollama=self.ollama,
                postgres=self.postgres,
                config=node_config.get("product", {}),
            )

        # Promotions node
        if EcommerceNodeType.PROMOTIONS in self.enabled_nodes:
            self.nodes[EcommerceNodeType.PROMOTIONS] = PromotionsNode(
                ollama=self.ollama,
                config=node_config.get("promotions", {}),
            )

        # Tracking node
        if EcommerceNodeType.TRACKING in self.enabled_nodes:
            self.nodes[EcommerceNodeType.TRACKING] = TrackingNode(
                ollama=self.ollama,
                config=node_config.get("tracking", {}),
            )

        # Invoice node
        if EcommerceNodeType.INVOICE in self.enabled_nodes:
            self.nodes[EcommerceNodeType.INVOICE] = InvoiceNode(
                ollama=self.ollama,
                config=node_config.get("invoice", {}),
            )

        logger.info(f"Initialized {len(self.nodes)} e-commerce nodes")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph StateGraph for e-commerce domain."""
        workflow = StateGraph(EcommerceState)

        # Add router node
        workflow.add_node(EcommerceNodeType.ROUTER, self._route_query)

        # Add domain nodes
        for node_name, node_instance in self.nodes.items():
            workflow.add_node(node_name, self._create_node_executor(node_instance))

        # Set entry point
        workflow.set_entry_point(EcommerceNodeType.ROUTER)

        # Add conditional edges from router to nodes
        routing_map: dict[Hashable, str] = {
            EcommerceNodeType.PRODUCT: EcommerceNodeType.PRODUCT,
            EcommerceNodeType.PROMOTIONS: EcommerceNodeType.PROMOTIONS,
            EcommerceNodeType.TRACKING: EcommerceNodeType.TRACKING,
            EcommerceNodeType.INVOICE: EcommerceNodeType.INVOICE,
            "__end__": END,
        }

        workflow.add_conditional_edges(
            EcommerceNodeType.ROUTER,
            self._get_next_node,
            cast(dict[Hashable, str], routing_map),
        )

        # Add edges from nodes to END
        for node_name in self.nodes:
            workflow.add_edge(node_name, END)

        return workflow

    def _create_node_executor(self, node_instance):
        """Create async executor wrapper for a node."""

        async def executor(state: EcommerceState) -> dict[str, Any]:
            try:
                # Extract user message
                messages = state.get("messages", [])
                if not messages:
                    return {"error_count": state.get("error_count", 0) + 1}

                last_message = messages[-1]
                message_content = (
                    last_message.content if hasattr(last_message, "content") else str(last_message)
                )

                # Process through node
                result = await node_instance.process(message_content, state)

                return result

            except Exception as e:
                logger.error(f"Error in node executor: {e}")
                return {
                    "error_count": state.get("error_count", 0) + 1,
                    "messages": [
                        {
                            "role": "assistant",
                            "content": "Disculpa, tuve un problema procesando tu consulta. ¿Podrías intentar de nuevo?",
                        }
                    ],
                }

        return executor

    async def _route_query(self, state: EcommerceState) -> dict[str, Any]:
        """
        Route incoming query to appropriate e-commerce node.

        Analyzes the user message and determines which node should handle it.
        """
        try:
            messages = state.get("messages", [])
            if not messages:
                return {"next_agent": "__end__", "is_complete": True}

            last_message = messages[-1]
            raw_content = last_message.content if hasattr(last_message, "content") else str(last_message)
            message_content = str(raw_content).lower()

            # Simple keyword-based routing
            intent_type, next_node = self._detect_intent(message_content)

            return {
                "ecommerce_intent_type": intent_type,
                "next_agent": next_node,
                "routing_decision": {
                    "domain": "ecommerce",
                    "intent_type": intent_type,
                    "routed_to": next_node,
                    "timestamp": datetime.now().isoformat(),
                },
            }

        except Exception as e:
            logger.error(f"Error in routing: {e}")
            return {
                "next_agent": EcommerceNodeType.PRODUCT,  # Default to product
                "error_count": state.get("error_count", 0) + 1,
            }

    def _detect_intent(self, message: str) -> tuple[str, str]:
        """
        Detect e-commerce intent from message.

        Returns:
            Tuple of (intent_type, target_node)
        """
        # Tracking keywords
        tracking_keywords = [
            "rastrear",
            "tracking",
            "donde esta",
            "pedido",
            "envio",
            "entrega",
            "paquete",
            "seguimiento",
        ]
        if any(kw in message for kw in tracking_keywords):
            return "order_tracking", EcommerceNodeType.TRACKING

        # Promotions keywords
        promo_keywords = [
            "promocion",
            "descuento",
            "oferta",
            "cupon",
            "codigo",
            "rebaja",
            "promo",
            "sale",
        ]
        if any(kw in message for kw in promo_keywords):
            return "promotions", EcommerceNodeType.PROMOTIONS

        # Invoice/billing keywords
        invoice_keywords = [
            "factura",
            "pago",
            "cobro",
            "invoice",
            "recibo",
            "cuenta",
            "reembolso",
            "impuesto",
        ]
        if any(kw in message for kw in invoice_keywords):
            return "billing", EcommerceNodeType.INVOICE

        # Default to product search
        return "product_search", EcommerceNodeType.PRODUCT

    def _get_next_node(self, state: EcommerceState) -> str:
        """Get the next node from state for conditional routing."""
        next_node = state.get("next_agent")

        # Validate node exists
        if next_node and next_node in self.nodes:
            return next_node

        # Check if should end
        if next_node == "__end__" or state.get("is_complete"):
            return "__end__"

        # Default fallback
        return EcommerceNodeType.PRODUCT

    def initialize(self):
        """Initialize and compile the graph."""
        try:
            self.app = self.graph.compile()
            logger.info("EcommerceGraph compiled successfully")
        except Exception as e:
            logger.error(f"Error compiling EcommerceGraph: {e}")
            raise

    async def invoke(
        self,
        message: str,
        conversation_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Process a message through the e-commerce graph.

        Args:
            message: User message
            conversation_id: Optional conversation ID
            **kwargs: Additional context (customer, cart, etc.)

        Returns:
            Graph processing result
        """
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
            logger.error(f"Error invoking EcommerceGraph: {e}")
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
                    health["nodes"][node_name] = {"healthy": True, "note": "No health check"}
            except Exception as e:
                health["nodes"][node_name] = {"healthy": False, "error": str(e)}
                health["healthy"] = False

        return health

    def get_enabled_nodes(self) -> list[str]:
        """Get list of enabled node names."""
        return list(self.nodes.keys())


# Alias for compatibility
EcommerceDomainGraph = EcommerceGraph
