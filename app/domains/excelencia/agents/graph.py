"""
Excelencia Domain Graph

LangGraph StateGraph implementation for the Excelencia Software domain.
Handles ERP information queries, demos, modules, support, and corporate information.
"""

import logging
from datetime import datetime
from typing import Any, Hashable, cast

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from app.integrations.llm import OllamaLLM

from .nodes import ExcelenciaNode
from .state import ExcelenciaState

logger = logging.getLogger(__name__)


class ExcelenciaNodeType:
    """Excelencia domain node types."""

    ROUTER = "excelencia_router"
    MAIN = "excelencia_node"


class ExcelenciaGraph:
    """
    Excelencia domain LangGraph implementation.

    Handles routing and processing for all Excelencia Software queries:
    - Module information
    - Demo requests
    - Training and support
    - Corporate information (via RAG)
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the Excelencia domain graph.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.enabled_nodes = self.config.get(
            "enabled_nodes",
            [ExcelenciaNodeType.MAIN],
        )

        # Initialize integrations
        self._init_integrations()

        # Initialize nodes
        self._init_nodes()

        # Build graph
        self.graph = self._build_graph()
        self.app = None

        logger.info(f"ExcelenciaGraph initialized with nodes: {self.enabled_nodes}")

    def _init_integrations(self):
        """Initialize integrations."""
        # integrations_config reserved for future use (e.g., external calendar API)
        _ = self.config.get("integrations", {})
        self.ollama = OllamaLLM()

    def _init_nodes(self):
        """Initialize Excelencia domain nodes."""
        self.nodes: dict[str, Any] = {}

        node_config = self.config.get("node_config", {})

        # Main Excelencia node
        if ExcelenciaNodeType.MAIN in self.enabled_nodes:
            self.nodes[ExcelenciaNodeType.MAIN] = ExcelenciaNode(
                ollama=self.ollama,
                config=node_config.get("excelencia", {}),
            )

        logger.info(f"Initialized {len(self.nodes)} Excelencia nodes")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph StateGraph for Excelencia domain."""
        workflow = StateGraph(ExcelenciaState)

        # Add router node
        workflow.add_node(ExcelenciaNodeType.ROUTER, self._route_query)

        # Add domain nodes
        for node_name, node_instance in self.nodes.items():
            workflow.add_node(node_name, self._create_node_executor(node_instance))

        # Set entry point
        workflow.set_entry_point(ExcelenciaNodeType.ROUTER)

        # Add conditional edges from router to nodes
        routing_map: dict[Hashable, str] = {
            ExcelenciaNodeType.MAIN: ExcelenciaNodeType.MAIN,
            "__end__": END,
        }

        workflow.add_conditional_edges(
            ExcelenciaNodeType.ROUTER,
            self._get_next_node,
            cast(dict[Hashable, str], routing_map),
        )

        # Add edge from main node to END
        workflow.add_edge(ExcelenciaNodeType.MAIN, END)

        return workflow

    def _create_node_executor(self, node_instance):
        """Create async executor wrapper for a node."""

        async def executor(state: ExcelenciaState) -> dict[str, Any]:
            try:
                logger.info(f"ExcelenciaGraph node_executor START for {node_instance.name}")
                messages = state.get("messages", [])
                if not messages:
                    logger.warning("No messages in state")
                    return {"error_count": state.get("error_count", 0) + 1}

                last_message = messages[-1]
                message_content = (
                    last_message.content if hasattr(last_message, "content") else str(last_message)
                )
                logger.info(f"ExcelenciaGraph calling node.process: {message_content[:50]}...")

                result = await node_instance.process(message_content, state)
                logger.info(f"ExcelenciaGraph node.process returned, keys: {list(result.keys())}")
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

    async def _route_query(self, state: ExcelenciaState) -> dict[str, Any]:
        """Route incoming query to appropriate Excelencia node."""
        try:
            messages = state.get("messages", [])
            if not messages:
                return {"next_agent": "__end__", "is_complete": True}

            last_message = messages[-1]
            raw_content = last_message.content if hasattr(last_message, "content") else str(last_message)
            # Handle case where content might be a list (e.g., multimodal messages)
            if isinstance(raw_content, list):
                message_content = " ".join(str(item) for item in raw_content).lower()
            else:
                message_content = str(raw_content).lower()

            intent_type = self._detect_intent(message_content)

            return {
                "excelencia_intent_type": intent_type,
                "next_agent": ExcelenciaNodeType.MAIN,
                "routing_decision": {
                    "domain": "excelencia",
                    "intent_type": intent_type,
                    "routed_to": ExcelenciaNodeType.MAIN,
                    "timestamp": datetime.now().isoformat(),
                },
            }

        except Exception as e:
            logger.error(f"Error in routing: {e}")
            return {
                "next_agent": ExcelenciaNodeType.MAIN,
                "error_count": state.get("error_count", 0) + 1,
            }

    def _detect_intent(self, message: str) -> str:
        """Detect Excelencia intent from message."""
        # Demo keywords
        if any(kw in message for kw in ["demo", "demostracion", "prueba", "presentacion"]):
            return "demo"

        # Training keywords
        if any(kw in message for kw in ["capacitacion", "curso", "entrenamiento", "formacion"]):
            return "training"

        # Support keywords
        if any(kw in message for kw in ["soporte", "ayuda", "problema", "error"]):
            return "support"

        # Module keywords
        if any(kw in message for kw in ["modulo", "funcionalidad", "caracteristicas"]):
            return "modules"

        # Corporate keywords
        if any(kw in message for kw in ["mision", "vision", "valores", "empresa", "contacto"]):
            return "corporate"

        return "general"

    def _get_next_node(self, state: dict[str, Any]) -> str:
        """Get the next node from state for conditional routing."""
        next_node = state.get("next_agent")

        if next_node and next_node in self.nodes:
            return next_node

        if next_node == "__end__" or state.get("is_complete"):
            return "__end__"

        return ExcelenciaNodeType.MAIN

    def initialize(self):
        """Initialize and compile the graph."""
        try:
            self.app = self.graph.compile()
            logger.info("ExcelenciaGraph compiled successfully")
        except Exception as e:
            logger.error(f"Error compiling ExcelenciaGraph: {e}")
            raise

    async def invoke(
        self,
        input_data: str | dict[str, Any],
        conversation_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Process input through the Excelencia graph.

        Args:
            input_data: Either a message string or a full state dict
            conversation_id: Optional conversation ID for threading
            **kwargs: Additional state fields

        Returns:
            Processed state dict
        """
        if not self.app:
            raise RuntimeError("Graph not initialized. Call initialize() first")

        try:
            # Handle both string messages and full state dicts
            if isinstance(input_data, str):
                initial_state: dict[str, Any] = {
                    "messages": [HumanMessage(content=input_data)],
                    "conversation_id": conversation_id,
                    "timestamp": datetime.now().isoformat(),
                    "is_complete": False,
                    "error_count": 0,
                    "max_errors": self.config.get("max_errors", 3),
                    **kwargs,
                }
            else:
                # Use provided state dict, ensuring required fields
                initial_state = {
                    "timestamp": datetime.now().isoformat(),
                    "is_complete": False,
                    "error_count": 0,
                    "max_errors": self.config.get("max_errors", 3),
                    **input_data,
                    **kwargs,
                }
                if conversation_id:
                    initial_state["conversation_id"] = conversation_id

            config: dict[str, Any] = {}
            thread_id = conversation_id or initial_state.get("conversation_id")
            if thread_id:
                config["configurable"] = {"thread_id": thread_id}

            logger.info("ExcelenciaGraph.invoke calling app.ainvoke...")
            result = await self.app.ainvoke(initial_state, cast(RunnableConfig, config))
            logger.info(f"ExcelenciaGraph.invoke complete, result keys: {list(result.keys())}")
            return result

        except Exception as e:
            logger.error(f"Error invoking ExcelenciaGraph: {e}")
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
ExcelenciaDomainGraph = ExcelenciaGraph
