"""
Healthcare Domain Graph

LangGraph StateGraph implementation for the healthcare domain.
Handles patient appointments, medical records, triage, and healthcare queries.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Hashable, cast

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from app.integrations.llm import OllamaLLM

from .state import HealthcareState

logger = logging.getLogger(__name__)


class HealthcareNodeType:
    """Healthcare domain node types."""

    ROUTER = "healthcare_router"
    APPOINTMENT = "appointment_node"
    PATIENT_RECORDS = "patient_records_node"
    TRIAGE = "triage_node"
    DOCTOR_SEARCH = "doctor_search_node"


class HealthcareGraph:
    """
    Healthcare domain LangGraph implementation.

    Handles routing and processing for all healthcare related queries:
    - Appointment booking and management
    - Patient records access
    - Emergency triage
    - Doctor search and availability
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the healthcare domain graph.

        Args:
            config: Configuration dictionary with:
                - integrations: Ollama settings
                - enabled_nodes: List of enabled node names
                - max_errors: Maximum errors before failing
        """
        self.config = config or {}
        self.enabled_nodes = self.config.get(
            "enabled_nodes",
            [
                HealthcareNodeType.APPOINTMENT,
                HealthcareNodeType.PATIENT_RECORDS,
                HealthcareNodeType.TRIAGE,
                HealthcareNodeType.DOCTOR_SEARCH,
            ],
        )

        # Initialize integrations
        self._init_integrations()

        # Initialize nodes
        self._init_nodes()

        # Build graph
        self.graph = self._build_graph()
        self.app = None

        logger.info(f"HealthcareGraph initialized with nodes: {self.enabled_nodes}")

    def _init_integrations(self):
        """Initialize integrations (Ollama)."""
        self.ollama = OllamaLLM()

    def _init_nodes(self):
        """Initialize healthcare domain nodes."""
        self.nodes: dict[str, Any] = {}
        logger.info(f"Initialized healthcare nodes: {list(self.nodes.keys())}")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph StateGraph for healthcare domain."""
        workflow: StateGraph[HealthcareState] = StateGraph(HealthcareState)

        # Add router node
        workflow.add_node(HealthcareNodeType.ROUTER, self._route_query)

        # Add placeholder handlers for enabled nodes
        if HealthcareNodeType.APPOINTMENT in self.enabled_nodes:
            workflow.add_node(HealthcareNodeType.APPOINTMENT, self._handle_appointment)

        if HealthcareNodeType.PATIENT_RECORDS in self.enabled_nodes:
            workflow.add_node(HealthcareNodeType.PATIENT_RECORDS, self._handle_patient_records)

        if HealthcareNodeType.TRIAGE in self.enabled_nodes:
            workflow.add_node(HealthcareNodeType.TRIAGE, self._handle_triage)

        if HealthcareNodeType.DOCTOR_SEARCH in self.enabled_nodes:
            workflow.add_node(HealthcareNodeType.DOCTOR_SEARCH, self._handle_doctor_search)

        # Set entry point
        workflow.set_entry_point(HealthcareNodeType.ROUTER)

        # Add conditional edges from router to nodes
        routing_map: dict[Hashable, str] = {
            HealthcareNodeType.APPOINTMENT: HealthcareNodeType.APPOINTMENT,
            HealthcareNodeType.PATIENT_RECORDS: HealthcareNodeType.PATIENT_RECORDS,
            HealthcareNodeType.TRIAGE: HealthcareNodeType.TRIAGE,
            HealthcareNodeType.DOCTOR_SEARCH: HealthcareNodeType.DOCTOR_SEARCH,
            "__end__": END,
        }

        workflow.add_conditional_edges(
            HealthcareNodeType.ROUTER,
            self._get_next_node,
            cast(dict[Hashable, str], routing_map),
        )

        # Add edges from nodes to END
        for node_type in [
            HealthcareNodeType.APPOINTMENT,
            HealthcareNodeType.PATIENT_RECORDS,
            HealthcareNodeType.TRIAGE,
            HealthcareNodeType.DOCTOR_SEARCH,
        ]:
            if node_type in self.enabled_nodes:
                workflow.add_edge(node_type, END)

        return workflow

    async def _route_query(self, state: HealthcareState) -> dict[str, Any]:
        """Route incoming query to appropriate healthcare node."""
        try:
            messages = state.get("messages", [])
            if not messages:
                return {"next_agent": "__end__", "is_complete": True}

            last_message = messages[-1]
            raw_content = (
                last_message.content if hasattr(last_message, "content") else str(last_message)
            )
            message_content = str(raw_content).lower()

            intent_type, next_node, is_emergency = self._detect_intent(message_content)

            return {
                "healthcare_intent_type": intent_type,
                "next_agent": next_node,
                "is_emergency": is_emergency,
                "routing_decision": {
                    "domain": "healthcare",
                    "intent_type": intent_type,
                    "routed_to": next_node,
                    "is_emergency": is_emergency,
                    "timestamp": datetime.now().isoformat(),
                },
            }

        except Exception as e:
            logger.error(f"Error in routing: {e}")
            return {
                "next_agent": HealthcareNodeType.APPOINTMENT,
                "error_count": state.get("error_count", 0) + 1,
            }

    def _detect_intent(self, message: str) -> tuple[str, str, bool]:
        """Detect healthcare intent from message."""
        # Emergency keywords - highest priority
        emergency_keywords = [
            "emergencia", "urgente", "grave", "dolor fuerte",
            "no puedo respirar", "accidente", "sangre", "desmayo",
            "infarto", "ataque",
        ]
        if any(kw in message for kw in emergency_keywords):
            return "emergency_triage", HealthcareNodeType.TRIAGE, True

        # Triage keywords
        triage_keywords = [
            "sintoma", "me duele", "dolor", "fiebre",
            "enfermo", "malestar", "nausea", "mareo",
        ]
        if any(kw in message for kw in triage_keywords):
            return "triage", HealthcareNodeType.TRIAGE, False

        # Appointment keywords
        appointment_keywords = [
            "cita", "turno", "reservar", "agendar",
            "cancelar cita", "reprogramar", "disponibilidad", "horario",
        ]
        if any(kw in message for kw in appointment_keywords):
            return "appointment", HealthcareNodeType.APPOINTMENT, False

        # Doctor search keywords
        doctor_keywords = [
            "doctor", "medico", "especialista", "cardiologo",
            "dermatologo", "pediatra", "buscar doctor",
        ]
        if any(kw in message for kw in doctor_keywords):
            return "doctor_search", HealthcareNodeType.DOCTOR_SEARCH, False

        # Patient records keywords
        records_keywords = [
            "historia", "historial", "registro", "resultado",
            "analisis", "estudio", "receta", "prescripcion",
        ]
        if any(kw in message for kw in records_keywords):
            return "patient_records", HealthcareNodeType.PATIENT_RECORDS, False

        return "appointment", HealthcareNodeType.APPOINTMENT, False

    def _get_next_node(self, state: HealthcareState) -> str:
        """Get the next node from state for conditional routing."""
        next_node = state.get("next_agent")

        if next_node and next_node in self.enabled_nodes:
            return next_node

        if next_node == "__end__" or state.get("is_complete"):
            return "__end__"

        return HealthcareNodeType.APPOINTMENT

    async def _handle_appointment(self, state: HealthcareState) -> dict[str, Any]:
        """Handle appointment-related queries."""
        try:
            messages = state.get("messages", [])
            if not messages:
                return {"error_count": state.get("error_count", 0) + 1}

            last_message = messages[-1]
            message_content = (
                last_message.content if hasattr(last_message, "content") else str(last_message)
            )

            prompt = f"""You are a healthcare appointment assistant.
            The patient asked: {message_content}
            Provide a helpful response about appointment booking, availability, or scheduling.
            Respond in Spanish. Be professional and empathetic."""

            response = await self.ollama.generate(prompt, temperature=0.7)

            return {
                "agent_responses": [{
                    "node": HealthcareNodeType.APPOINTMENT,
                    "response": response,
                    "timestamp": datetime.now().isoformat(),
                }],
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in appointment handler: {e}")
            return {
                "error_count": state.get("error_count", 0) + 1,
                "agent_responses": [{
                    "node": HealthcareNodeType.APPOINTMENT,
                    "response": "Lo siento, hubo un problema. Por favor, intenta de nuevo.",
                    "error": str(e),
                }],
            }

    async def _handle_patient_records(self, state: HealthcareState) -> dict[str, Any]:
        """Handle patient records queries."""
        try:
            messages = state.get("messages", [])
            if not messages:
                return {"error_count": state.get("error_count", 0) + 1}

            last_message = messages[-1]
            message_content = (
                last_message.content if hasattr(last_message, "content") else str(last_message)
            )

            prompt = f"""You are a healthcare records assistant.
            The patient asked: {message_content}
            Provide helpful information about accessing medical records.
            Remind them about privacy and verification requirements.
            Respond in Spanish. Be professional."""

            response = await self.ollama.generate(prompt, temperature=0.7)

            return {
                "agent_responses": [{
                    "node": HealthcareNodeType.PATIENT_RECORDS,
                    "response": response,
                    "timestamp": datetime.now().isoformat(),
                }],
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in patient records handler: {e}")
            return {"error_count": state.get("error_count", 0) + 1}

    async def _handle_triage(self, state: HealthcareState) -> dict[str, Any]:
        """Handle triage and symptom assessment."""
        try:
            messages = state.get("messages", [])
            if not messages:
                return {"error_count": state.get("error_count", 0) + 1}

            last_message = messages[-1]
            message_content = (
                last_message.content if hasattr(last_message, "content") else str(last_message)
            )

            is_emergency = state.get("is_emergency", False)

            if is_emergency:
                response = """ATENCION: Esto parece una emergencia medica.

Por favor, sigue estos pasos inmediatamente:
1. Llama al numero de emergencias (107 o 911)
2. No te muevas si es una lesion fisica
3. Permanece en linea con los servicios de emergencia
4. Si estas con alguien, pideles que llamen mientras tu recibes atencion

Tu salud es lo primero. Busca atencion medica de inmediato."""
            else:
                prompt = f"""You are a medical triage assistant.
                The patient described: {message_content}
                Provide: 1. Initial assessment 2. Recommended urgency 3. Next steps
                Always recommend seeing a doctor. Respond in Spanish."""

                response = await self.ollama.generate(prompt, temperature=0.5)

            return {
                "agent_responses": [{
                    "node": HealthcareNodeType.TRIAGE,
                    "response": response,
                    "is_emergency": is_emergency,
                    "timestamp": datetime.now().isoformat(),
                }],
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in triage handler: {e}")
            return {
                "error_count": state.get("error_count", 0) + 1,
                "agent_responses": [{
                    "node": HealthcareNodeType.TRIAGE,
                    "response": "Si tienes una emergencia medica, llama al 107 inmediatamente.",
                    "error": str(e),
                }],
            }

    async def _handle_doctor_search(self, state: HealthcareState) -> dict[str, Any]:
        """Handle doctor search queries."""
        try:
            messages = state.get("messages", [])
            if not messages:
                return {"error_count": state.get("error_count", 0) + 1}

            last_message = messages[-1]
            message_content = (
                last_message.content if hasattr(last_message, "content") else str(last_message)
            )

            prompt = f"""You are a healthcare staff assistant.
            The patient asked: {message_content}
            Provide helpful information about finding doctors or specialists.
            Respond in Spanish. Be helpful."""

            response = await self.ollama.generate(prompt, temperature=0.7)

            return {
                "agent_responses": [{
                    "node": HealthcareNodeType.DOCTOR_SEARCH,
                    "response": response,
                    "timestamp": datetime.now().isoformat(),
                }],
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in doctor search handler: {e}")
            return {"error_count": state.get("error_count", 0) + 1}

    def initialize(self):
        """Initialize and compile the graph."""
        try:
            self.app = self.graph.compile()
            logger.info("HealthcareGraph compiled successfully")
        except Exception as e:
            logger.error(f"Error compiling HealthcareGraph: {e}")
            raise

    async def invoke(
        self,
        input_data: str | dict[str, Any],
        conversation_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Process a message through the healthcare graph."""
        if not self.app:
            raise RuntimeError("Graph not initialized. Call initialize() first")

        try:
            # Handle both string and dict inputs
            if isinstance(input_data, str):
                message = input_data
            elif isinstance(input_data, dict):
                # Extract message from state dict
                messages = input_data.get("messages", [])
                if messages:
                    last_msg = messages[-1]
                    message = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                else:
                    message = ""
            else:
                message = str(input_data)

            initial_state: dict[str, Any] = {
                "messages": [HumanMessage(content=message)],
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat(),
                "is_complete": False,
                "is_emergency": False,
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
            logger.error(f"Error invoking HealthcareGraph: {e}")
            raise

    async def health_check(self) -> dict[str, Any]:
        """Check health of the graph."""
        return {
            "healthy": True,
            "enabled_nodes": self.enabled_nodes,
            "ollama_available": self.ollama is not None,
        }

    def get_enabled_nodes(self) -> list[str]:
        """Get list of enabled node names."""
        return self.enabled_nodes


# Alias for compatibility
HealthcareDomainGraph = HealthcareGraph
