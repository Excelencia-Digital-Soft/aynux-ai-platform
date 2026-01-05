"""
Pharmacy Domain Graph

LangGraph StateGraph implementation for the pharmacy domain.
Handles customer identification, debt checking, confirmation, and receipt generation.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Hashable, cast

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from app.clients.plex_client import PlexClient
from app.domains.pharmacy.agents.intent_analyzer import PharmacyIntentAnalyzer
from app.domains.pharmacy.agents.nodes import (
    ConfirmationNode,
    CustomerIdentificationNode,
    CustomerRegistrationNode,
    DebtCheckNode,
    InvoiceGenerationNode,
    PaymentLinkNode,
)
from app.domains.pharmacy.agents.nodes.fallback_handler import PharmacyFallbackHandler
from app.domains.pharmacy.agents.state import PharmacyState

logger = logging.getLogger(__name__)


class PharmacyNodeType:
    """Pharmacy domain node types."""

    CUSTOMER_IDENTIFICATION = "customer_identification_node"
    CUSTOMER_REGISTRATION = "customer_registration_node"
    ROUTER = "pharmacy_router"
    DEBT_CHECK = "debt_check_node"
    CONFIRMATION = "confirmation_node"
    INVOICE = "invoice_generation_node"
    PAYMENT_LINK = "payment_link_node"


# Node registry: node_type -> (node_class, config_key)
NODE_REGISTRY: dict[str, tuple[type, str]] = {
    PharmacyNodeType.CUSTOMER_IDENTIFICATION: (CustomerIdentificationNode, "customer_identification"),
    PharmacyNodeType.CUSTOMER_REGISTRATION: (CustomerRegistrationNode, "customer_registration"),
    PharmacyNodeType.DEBT_CHECK: (DebtCheckNode, "debt_check"),
    PharmacyNodeType.CONFIRMATION: (ConfirmationNode, "confirmation"),
    PharmacyNodeType.INVOICE: (InvoiceGenerationNode, "invoice"),
    PharmacyNodeType.PAYMENT_LINK: (PaymentLinkNode, "payment_link"),
}

# Intent to node mapping
INTENT_NODE_MAP: dict[str, str] = {
    "debt_query": PharmacyNodeType.DEBT_CHECK,
    "confirm": PharmacyNodeType.CONFIRMATION,
    "invoice": PharmacyNodeType.INVOICE,
    "payment_link": PharmacyNodeType.PAYMENT_LINK,
    "register": PharmacyNodeType.CUSTOMER_REGISTRATION,
}

# Intents handled by fallback handler
FALLBACK_INTENTS = frozenset({"greeting", "reject", "unknown", "summary", "data_query", "info_query"})


class PharmacyGraph:
    """
    Pharmacy domain LangGraph implementation.

    Flow:
    1. Customer Identification -> Identify user from WhatsApp phone
    2. (Optional) Customer Registration -> Register new customers
    3. Debt Check -> Show debt to customer
    4. Confirmation -> Customer confirms debt
    5. Invoice/Receipt Generation -> Generate receipt for payment
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize pharmacy graph."""
        self.config = config or {}
        self.enabled_nodes = self.config.get("enabled_nodes", list(NODE_REGISTRY.keys()))

        self._plex_client = PlexClient()
        self._intent_analyzer = PharmacyIntentAnalyzer(
            use_llm_fallback=self.config.get("use_llm_fallback", True),
        )
        self._fallback_handler = PharmacyFallbackHandler()

        self._init_nodes()
        self.graph = self._build_graph()
        self.app = None

        logger.info(f"PharmacyGraph initialized with nodes: {self.enabled_nodes}")

    def _init_nodes(self) -> None:
        """Initialize pharmacy domain nodes using registry."""
        self.nodes: dict[str, Any] = {}
        node_config = self.config.get("node_config", {})

        for node_type, (node_class, config_key) in NODE_REGISTRY.items():
            if node_type in self.enabled_nodes:
                self.nodes[node_type] = node_class(
                    plex_client=self._plex_client,
                    config=node_config.get(config_key, {}),
                )

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph StateGraph for pharmacy domain."""
        workflow = StateGraph(PharmacyState)

        # Add all nodes
        for node_name, node_instance in self.nodes.items():
            workflow.add_node(node_name, self._create_node_executor(node_instance))
        workflow.add_node(PharmacyNodeType.ROUTER, self._route_query)

        # Set entry point
        workflow.set_entry_point(PharmacyNodeType.CUSTOMER_IDENTIFICATION)

        # Customer Identification edges
        workflow.add_conditional_edges(
            PharmacyNodeType.CUSTOMER_IDENTIFICATION,
            self._route_after_identification,
            {
                "router": PharmacyNodeType.ROUTER,
                "identification": PharmacyNodeType.CUSTOMER_IDENTIFICATION,
                "registration": PharmacyNodeType.CUSTOMER_REGISTRATION,
                "__end__": END,
            },
        )

        # Customer Registration edges
        workflow.add_conditional_edges(
            PharmacyNodeType.CUSTOMER_REGISTRATION,
            self._route_after_registration,
            {"router": PharmacyNodeType.ROUTER, "registration": PharmacyNodeType.CUSTOMER_REGISTRATION, "__end__": END},
        )

        # Router edges
        routing_map: dict[Hashable, str] = {
            PharmacyNodeType.DEBT_CHECK: PharmacyNodeType.DEBT_CHECK,
            PharmacyNodeType.CONFIRMATION: PharmacyNodeType.CONFIRMATION,
            PharmacyNodeType.INVOICE: PharmacyNodeType.INVOICE,
            PharmacyNodeType.PAYMENT_LINK: PharmacyNodeType.PAYMENT_LINK,
            "__end__": END,
        }
        workflow.add_conditional_edges(
            PharmacyNodeType.ROUTER, self._get_next_node, cast(dict[Hashable, str], routing_map)
        )

        # Operation nodes edges (debt_check, confirmation -> router or end)
        for node in [PharmacyNodeType.DEBT_CHECK, PharmacyNodeType.CONFIRMATION]:
            workflow.add_conditional_edges(
                node,
                self._route_after_operation,
                {
                    "router": PharmacyNodeType.ROUTER,
                    "payment_link": PharmacyNodeType.PAYMENT_LINK,
                    "__end__": END,
                },
            )
        workflow.add_edge(PharmacyNodeType.INVOICE, END)
        workflow.add_edge(PharmacyNodeType.PAYMENT_LINK, END)

        return workflow

    def _create_node_executor(self, node_instance: Any):
        """Create async executor wrapper for a node."""

        async def executor(state: PharmacyState) -> dict[str, Any]:
            try:
                messages = state.get("messages", [])
                if not messages:
                    return {"error_count": state.get("error_count", 0) + 1}

                last_message = messages[-1]
                content = last_message.content if hasattr(last_message, "content") else str(last_message)

                result = await node_instance.process(str(content), dict(state))

                if "messages" in result:
                    result["messages"] = self._format_result_messages(result["messages"])
                return result

            except Exception as e:
                logger.error(f"Error in pharmacy node executor: {e}", exc_info=True)
                return {
                    "error_count": state.get("error_count", 0) + 1,
                    "messages": [AIMessage(content="Disculpa, tuve un problema. ¿Podrías intentar de nuevo?")],
                }

        return executor

    def _format_result_messages(self, messages: list) -> list[AIMessage | HumanMessage]:
        """Convert dict messages to LangChain message objects."""
        formatted = []
        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get("content", "")
                formatted.append(
                    AIMessage(content=content) if msg.get("role") == "assistant" else HumanMessage(content=content)
                )
            else:
                formatted.append(msg)
        return formatted

    def _check_termination(self, state: PharmacyState) -> str | None:
        """Check common termination conditions."""
        if state.get("is_complete"):
            return "__end__"
        if state.get("error_count", 0) >= state.get("max_errors", 3):
            return "__end__"
        return None

    def _route_after_identification(self, state: PharmacyState) -> str:
        """Route based on customer identification result."""
        if state.get("customer_identified") and state.get("plex_customer_id"):
            return "router"
        if state.get("requires_disambiguation") or state.get("awaiting_document_input"):
            return "__end__"
        if state.get("pharmacy_intent_type") == "register_prompt":
            return "registration"
        if term := self._check_termination(state):
            return term
        return "identification"

    def _route_after_registration(self, state: PharmacyState) -> str:
        """Route based on customer registration result."""
        if state.get("customer_identified") and state.get("plex_customer_id"):
            return "router"
        if state.get("awaiting_registration_data"):
            return "__end__"
        if term := self._check_termination(state):
            return term
        return "registration"

    def _route_after_operation(self, state: PharmacyState) -> str:
        """Route after debt check or confirmation."""
        # Check for explicit next_agent routing (e.g., from confirmation to payment_link)
        next_agent = state.get("next_agent")
        if next_agent == "payment_link_node":
            return "payment_link"

        if state.get("is_complete") or state.get("awaiting_confirmation"):
            return "__end__"

        # If debt is confirmed but not awaiting payment, continue flow
        if state.get("debt_status") == "confirmed" and not state.get("awaiting_payment"):
            return "payment_link"

        return "router"

    def _extract_last_human_message(self, state: PharmacyState) -> str | None:
        """Extract content from last HumanMessage in state."""
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, HumanMessage):
                content = msg.content if hasattr(msg, "content") else str(msg)
                return str(content).strip()
        return None

    def _format_recent_history(self, state: PharmacyState, max_turns: int = 5) -> str:
        """Format recent conversation turns for context.

        Args:
            state: Current pharmacy state with messages
            max_turns: Maximum conversation turns to include (default: 5)

        Returns:
            Formatted string with recent conversation history
        """
        messages = state.get("messages", [])
        if len(messages) <= 1:  # Only current message
            return ""

        # Exclude current message, take last N*2 (user+assistant pairs)
        history_messages = messages[:-1][-(max_turns * 2) :]
        if not history_messages:
            return ""

        formatted = []
        for msg in history_messages:
            if isinstance(msg, HumanMessage):
                formatted.append(f"Usuario: {msg.content}")
            elif isinstance(msg, AIMessage):
                # Truncate long responses
                content = str(msg.content)
                if len(content) > 150:
                    content = content[:150] + "..."
                formatted.append(f"Asistente: {content}")

        return "\n".join(formatted) if formatted else ""

    async def _route_query(self, state: PharmacyState) -> dict[str, Any]:
        """Route incoming query to appropriate pharmacy node using hybrid NLU."""
        try:
            message_content = self._extract_last_human_message(state)
            if not message_content:
                return {"next_agent": "__end__", "is_complete": True}

            # Extract recent conversation history for context
            conversation_history = self._format_recent_history(state, max_turns=5)

            context = {
                "customer_identified": state.get("customer_identified", False),
                "awaiting_confirmation": state.get("awaiting_confirmation", False),
                "debt_status": state.get("debt_status"),
                "has_debt": state.get("has_debt", False),
                "conversation_history": conversation_history,
            }

            intent_result = await self._intent_analyzer.analyze(message_content, context)
            logger.info(
                f"Intent: {intent_result.intent} (conf: {intent_result.confidence:.2f}, method: {intent_result.method})"
            )

            # Handle fallback intents (greeting, reject, unknown, summary, data_query)
            # data_query will auto-fetch debt internally in handle_data_query() if needed
            if intent_result.is_out_of_scope or intent_result.intent in FALLBACK_INTENTS:
                return await self._handle_fallback_intent(intent_result.intent, message_content, state)

            # Auto-fetch debt for invoice intent if debt_id not available
            intent = intent_result.intent
            if intent == "invoice" and not state.get("debt_id"):
                logger.info("Invoice intent without debt_id - auto-fetching debt first")
                return {
                    "pharmacy_intent_type": "debt_query",
                    "next_agent": PharmacyNodeType.DEBT_CHECK,
                    "auto_proceed_to_invoice": True,
                    "intent_confidence": intent_result.confidence,
                    "extracted_entities": intent_result.entities,
                }

            next_node = INTENT_NODE_MAP.get(intent, PharmacyNodeType.DEBT_CHECK)

            # Build base updates
            updates: dict[str, Any] = {
                "pharmacy_intent_type": intent_result.intent,
                "next_agent": next_node,
                "intent_confidence": intent_result.confidence,
                "intent_method": intent_result.method,
                "extracted_entities": intent_result.entities,
                "confirmation_received": intent_result.intent == "confirm",
                "routing_decision": {
                    "domain": "pharmacy",
                    "intent_type": intent_result.intent,
                    "confidence": intent_result.confidence,
                    "method": intent_result.method,
                    "routed_to": next_node,
                    "timestamp": datetime.now().isoformat(),
                },
            }

            # Extract and propagate payment amount for partial payments
            extracted_amount = intent_result.entities.get("amount")
            total_debt = state.get("total_debt", 0) or 0

            if extracted_amount and extracted_amount > 0:
                # Cap payment amount at total debt (can't pay more than owed)
                payment_amount = min(extracted_amount, total_debt) if total_debt > 0 else extracted_amount
                updates["payment_amount"] = payment_amount
                updates["is_partial_payment"] = payment_amount < total_debt if total_debt > 0 else False
                logger.info(
                    f"Partial payment detected: requested=${extracted_amount}, "
                    f"total_debt=${total_debt}, payment_amount=${payment_amount}"
                )

            return updates

        except Exception as e:
            logger.error(f"Error in pharmacy routing: {e}", exc_info=True)
            error_response = await self._fallback_handler.handle_error(e, dict(state))
            error_response["next_agent"] = PharmacyNodeType.DEBT_CHECK
            return error_response

    async def _handle_fallback_intent(self, intent: str, message: str, state: PharmacyState) -> dict[str, Any]:
        """Handle fallback intents (greeting, reject, unknown, summary, data_query, info_query)."""
        state_dict = dict(state)
        if intent == "greeting":
            return await self._fallback_handler.handle_greeting(message, state_dict)
        if intent == "reject":
            return await self._fallback_handler.handle_cancelled(state_dict)
        if intent == "summary":
            return await self._fallback_handler.handle_summary(message, state_dict)
        if intent == "data_query":
            return await self._fallback_handler.handle_data_query(message, state_dict)
        if intent == "info_query":
            return await self._fallback_handler.handle_info_query(message, state_dict)
        return await self._fallback_handler.handle_unknown(message, state_dict)

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

    async def invoke(self, message: str, conversation_id: str | None = None, **kwargs: Any) -> dict[str, Any]:
        """Process a message through the pharmacy graph."""
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
                "customer_identified": False,
                "requires_disambiguation": False,
                "awaiting_document_input": False,
                "awaiting_registration_data": False,
                "is_bypass_route": kwargs.get("is_bypass_route", False),
                "requires_human": False,
                **kwargs,
            }

            config: dict[str, Any] = {}
            if conversation_id:
                config["configurable"] = {"thread_id": conversation_id}

            result = await self.app.ainvoke(initial_state, cast(RunnableConfig, config))
            return dict(result)

        except Exception as e:
            logger.error(f"Error invoking PharmacyGraph: {e}", exc_info=True)
            raise

    async def health_check(self) -> dict[str, Any]:
        """Check health of the pharmacy graph and its components."""
        health: dict[str, Any] = {
            "graph_compiled": self.app is not None,
            "nodes_enabled": list(self.nodes.keys()),
            "plex_client_configured": bool(self._plex_client.base_url),
            "intent_analyzer": self._intent_analyzer.get_model_info(),
        }

        if self._plex_client.base_url:
            try:
                async with self._plex_client:
                    health["plex_connection"] = await self._plex_client.test_connection()
            except Exception as e:
                health["plex_connection"] = False
                health["plex_error"] = str(e)

        return health
