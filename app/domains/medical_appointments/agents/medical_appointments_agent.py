"""Medical Appointments Agent.

Main agent for handling medical appointment booking conversations.
Extends BaseAgent and wraps MedicalAppointmentsGraph.

IMPORTANT: This agent requires institution configuration from the database.
Configuration must be provided via:
1. State dict at runtime (institution_config from bypass routing) - PREFERRED
2. Cached DB config (from load_config_from_db call)
3. Constructor config dict (from container)

The agent will raise ValueError if no configuration is found.
"""

import logging
from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage

from app.core.agents.base_agent import BaseAgent

from .graph import MedicalAppointmentsGraph
from .state import get_initial_state

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.tenancy.institution_config_service import InstitutionConfig

logger = logging.getLogger(__name__)


class MedicalAppointmentsAgent(BaseAgent):
    """Agente de turnos médicos.

    Handles the complete flow of booking, confirming, and
    cancelling medical appointments. Supports multiple institutions
    (Patología Digestiva, Mercedario, etc.) via database configuration.

    Configuration Priority:
    1. Runtime state (institution_config from webhook/bypass routing)
    2. Constructor config (from container/settings)
    3. Database lookup (if institution_key provided)
    """

    def __init__(
        self,
        name: str = "medical_appointments_agent",
        config: dict[str, Any] | None = None,
        **integrations,
    ):
        """Initialize medical appointments agent.

        Args:
            name: Agent name identifier.
            config: Optional agent configuration dictionary. If provided, should contain:
                - institution: Institution key (e.g., "patologia_digestiva")
                - institution_name: Human-readable institution name
                - base_url: API base URL (SOAP or REST)
                - connection_type: "soap" or "rest"
                - timeout_seconds: Request timeout
                - timezone: Timezone for scheduling
            **integrations: Additional integrations (vLLM, postgres, etc.).

        NOTE: If config is not provided, institution_config MUST be injected
        via state dict at runtime (from bypass routing).
        """
        super().__init__(name=name, config=config or {}, **integrations)

        self._graph: MedicalAppointmentsGraph | None = None
        self._cached_db_config: "InstitutionConfig | None" = None

        # Check if constructor config was provided (from container)
        self._has_constructor_config = bool(self.config.get("institution"))

        self.logger.info(
            f"MedicalAppointmentsAgent initialized " f"(has_constructor_config={self._has_constructor_config})"
        )

    def _get_institution_config(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Get institution configuration from state, cache, or constructor.

        Priority:
        1. institution_config in state (from DB via webhook/bypass) - PREFERRED
        2. Cached DB config (from load_config_from_db call)
        3. Constructor config (from container)

        Args:
            state_dict: Current state dictionary.

        Returns:
            Configuration dict with institution, base_url, connection settings, etc.

        Raises:
            ValueError: If no configuration is found from any source.
        """
        # Priority 1: Runtime config from state (loaded by webhook/bypass)
        if "institution_config" in state_dict:
            inst_config = state_dict["institution_config"]
            return self._extract_config_from_source(inst_config)

        # Priority 2: Cached DB config
        if self._cached_db_config:
            return self._extract_config_from_source(self._cached_db_config)

        # Priority 3: Constructor config (from container)
        if self._has_constructor_config:
            return self._extract_config_from_source(self.config)

        # NO FALLBACK - raise error with clear instructions
        raise ValueError(
            "No institution configuration found. "
            "Medical appointments agent requires configuration from one of:\n"
            "1. institution_config in state (from bypass routing)\n"
            "2. Cached DB config (call load_config_from_db first)\n"
            "3. Constructor config (from container)\n\n"
            "To fix: Configure the institution in tenant_institution_configs table "
            "and create a bypass rule that routes to this agent."
        )

    def _extract_config_from_source(self, inst_config: Any) -> dict[str, Any]:
        """Extract configuration from InstitutionConfig dataclass or dict.

        Handles both the new InstitutionConfig dataclass with settings
        and raw dict formats for backward compatibility.

        Args:
            inst_config: InstitutionConfig dataclass or dict.

        Returns:
            Normalized configuration dict.

        Raises:
            ValueError: If inst_config is invalid or missing required fields.
        """
        # Handle InstitutionConfig dataclass (preferred format)
        if hasattr(inst_config, "institution_key"):
            return {
                "institution": inst_config.institution_key,
                "institution_id": inst_config.institution_key,
                "institution_name": inst_config.institution_name,
                "base_url": inst_config.base_url,
                "connection_type": inst_config.connection_type,
                "timeout_seconds": inst_config.timeout_seconds,
                "auth_type": inst_config.auth_type,
                "timezone": inst_config.timezone,
                "custom": inst_config.config,
                # Legacy aliases
                "soap_url": inst_config.soap_url or inst_config.base_url,
                "api_type": inst_config.api_type,
            }

        # Handle raw dict
        if isinstance(inst_config, dict):
            # Check if it's the new settings structure (from DB JSONB)
            if "settings" in inst_config or "connection" in inst_config:
                settings = inst_config.get("settings", inst_config)
                connection = settings.get("connection", {})
                scheduler = settings.get("scheduler", {})
                branding = settings.get("branding", {})
                institution_key = inst_config.get("institution_key", inst_config.get("institution", ""))
                return {
                    "institution": institution_key,
                    "institution_id": institution_key,
                    "institution_name": inst_config.get("institution_name", branding.get("display_name", "")),
                    "base_url": connection.get("base_url", ""),
                    "connection_type": connection.get("type", "soap"),
                    "timeout_seconds": connection.get("timeout_seconds", 30),
                    "auth_type": settings.get("auth", {}).get("type", "none"),
                    "timezone": scheduler.get("timezone", "UTC"),
                    "custom": settings.get("custom", {}),
                    # Legacy aliases
                    "soap_url": connection.get("base_url", ""),
                    "api_type": connection.get("type", "soap"),
                }

            # Simple dict format (from constructor config or legacy)
            institution = inst_config.get("institution", inst_config.get("institution_key", ""))
            return {
                "institution": institution,
                "institution_id": institution,
                "institution_name": inst_config.get("institution_name", ""),
                "base_url": inst_config.get("base_url", inst_config.get("soap_url", "")),
                "connection_type": inst_config.get("connection_type", inst_config.get("api_type", "soap")),
                "timeout_seconds": inst_config.get("timeout_seconds", inst_config.get("soap_timeout", 30)),
                "auth_type": inst_config.get("auth_type", "none"),
                "timezone": inst_config.get("timezone", inst_config.get("reminder_timezone", "UTC")),
                "custom": inst_config.get("custom", inst_config.get("config", {})),
                # Legacy aliases
                "soap_url": inst_config.get("soap_url", inst_config.get("base_url", "")),
                "api_type": inst_config.get("api_type", inst_config.get("connection_type", "soap")),
            }

        # Invalid config type
        raise ValueError(
            f"Invalid institution config type: {type(inst_config)}. " f"Expected InstitutionConfig dataclass or dict."
        )

    async def load_config_from_db(
        self,
        db: "AsyncSession",
        institution_key: str | None = None,
        whatsapp_phone_number_id: str | None = None,
    ) -> "InstitutionConfig":
        """Load institution configuration from database.

        Call this method before processing if you need DB config.
        The loaded config will be cached for subsequent calls.

        Args:
            db: SQLAlchemy async session.
            institution_key: Institution key to look up (e.g., "patologia_digestiva").
            whatsapp_phone_number_id: WhatsApp phone number ID for lookup.

        Returns:
            InstitutionConfig from database.

        Raises:
            ValueError: If no config found.
        """
        from app.core.tenancy.institution_config_service import InstitutionConfigService

        service = InstitutionConfigService(db)

        if whatsapp_phone_number_id:
            self._cached_db_config = await service.get_config_by_whatsapp_phone(whatsapp_phone_number_id)
        elif institution_key:
            self._cached_db_config = await service.get_config_by_key(institution_key)
        else:
            raise ValueError(
                "Either institution_key or whatsapp_phone_number_id must be provided. "
                "Cannot load institution config without an identifier."
            )

        self.logger.info(f"Loaded DB config for institution: {self._cached_db_config.institution_key}")
        return self._cached_db_config

    async def _ensure_graph_initialized(
        self,
        institution_config: dict[str, Any],
    ) -> MedicalAppointmentsGraph:
        """Lazy initialization of the LangGraph.

        Args:
            institution_config: Configuration dict from _get_institution_config.
                               This is REQUIRED - no defaults.

        Returns:
            Initialized MedicalAppointmentsGraph.

        Raises:
            ValueError: If institution_config is not provided.
        """
        if not institution_config:
            raise ValueError(
                "institution_config is required for graph initialization. " "Call _get_institution_config first."
            )

        # Reinitialize if config changed
        if self._graph is not None:
            current_institution = getattr(self._graph, "_institution", None)
            if current_institution != institution_config.get("institution"):
                new_institution = institution_config.get("institution")
                self.logger.debug(
                    f"Institution changed from {current_institution} to {new_institution}, " "reinitializing graph"
                )
                await self._graph.close()
                self._graph = None

        if self._graph is None:
            self._graph = MedicalAppointmentsGraph(config=institution_config)
            self._graph.initialize()
            self.logger.debug(f"MedicalAppointmentsGraph initialized for {institution_config.get('institution')}")

        return self._graph

    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Process message through the appointment graph.

        Args:
            message: User message.
            state_dict: Current conversation state (may include institution_config from bypass).

        Returns:
            Updated state dictionary.
        """
        # Get institution config (from state, cached DB, or defaults)
        institution_config = self._get_institution_config(state_dict)

        # Initialize graph with config
        graph = await self._ensure_graph_initialized(institution_config)

        # Merge existing state with new message
        graph_state = self._prepare_graph_state(message, state_dict, institution_config)

        # Invoke graph
        result = await graph.invoke(graph_state)

        # Format response for agent framework
        return self._format_response(result, institution_config)

    def _prepare_graph_state(
        self,
        message: str,
        state_dict: dict[str, Any],
        institution_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Prepare state for graph invocation.

        Args:
            message: User message.
            state_dict: Current state dictionary.
            institution_config: Institution configuration dict.

        Returns:
            State dictionary for graph.
        """
        # Get initial state structure with institution from config
        # Note: institution_config is already validated by _get_institution_config
        graph_state = get_initial_state(
            institution=institution_config["institution"],
            user_phone=state_dict.get("user_phone") or state_dict.get("wa_id"),
        )

        # Carry over persistent state
        persistent_keys = [
            "patient_document",
            "patient_data",
            "patient_id",
            "patient_name",
            "is_registered",
            "selected_specialty",
            "selected_specialty_name",
            "selected_provider",
            "selected_provider_id",
            "selected_provider_name",
            "selected_date",
            "selected_time",
            "specialties_list",
            "providers_list",
            "available_dates",
            "available_times",
            "appointment_id",
            "suggested_appointment",
            "awaiting_confirmation",
            "needs_registration",
            "error_count",
        ]

        for key in persistent_keys:
            if key in state_dict and state_dict[key] is not None:
                graph_state[key] = state_dict[key]

        # Add new message - ensure messages list exists
        existing_messages = state_dict.get("messages", [])
        messages_list: list = list(existing_messages) if existing_messages else []
        messages_list.append(HumanMessage(content=message))
        graph_state["messages"] = messages_list

        # Add RAG context if available
        if state_dict.get("agent_knowledge_context"):
            graph_state["agent_knowledge_context"] = state_dict["agent_knowledge_context"]

        # TypedDict is compatible with dict[str, Any] at runtime
        return graph_state  # type: ignore[return-value]

    def _format_response(
        self,
        result: dict[str, Any],
        institution_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Format graph result for agent framework.

        Args:
            result: Graph output state.
            institution_config: Institution configuration dict.

        Returns:
            Formatted response dictionary.
        """
        # Extract response text
        messages = result.get("messages", [])
        response_text = ""
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, "content"):
                response_text = last_message.content
            elif isinstance(last_message, dict):
                response_text = last_message.get("content", "")
            else:
                response_text = str(last_message)

        # Build response
        response = {
            "messages": messages,
            "current_agent": self.name,
            "response_text": response_text,
            "is_complete": result.get("is_complete", False),
            # Include institution info for state persistence
            "institution": institution_config.get("institution"),
            "institution_config": institution_config,
        }

        # Carry forward state for next turn
        state_keys = [
            "patient_document",
            "patient_data",
            "patient_id",
            "patient_name",
            "is_registered",
            "selected_specialty",
            "selected_specialty_name",
            "selected_provider",
            "selected_provider_id",
            "selected_provider_name",
            "selected_date",
            "selected_time",
            "specialties_list",
            "providers_list",
            "available_dates",
            "available_times",
            "appointment_id",
            "suggested_appointment",
            "awaiting_confirmation",
            "needs_registration",
            "error_count",
            "current_node",
        ]

        for key in state_keys:
            if key in result:
                response[key] = result[key]

        return response

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute agent with state.

        This is the main entry point called by the orchestrator or bypass routing.

        Args:
            state: Conversation state dictionary.

        Returns:
            Updated state dictionary.
        """
        # Extract message from state
        messages = state.get("messages", [])
        if messages:
            last = messages[-1]
            if hasattr(last, "content"):
                message = last.content
            elif isinstance(last, dict):
                message = last.get("content", "")
            else:
                message = str(last)
        else:
            message = ""

        # Process through base agent (includes RAG retrieval)
        return await self.process(message, state)

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self._graph:
            await self._graph.close()
            self._graph = None
            self.logger.debug("MedicalAppointmentsAgent cleaned up")

    def __repr__(self) -> str:
        cached_inst = self._cached_db_config.institution_key if self._cached_db_config else "none"
        return f"MedicalAppointmentsAgent(name={self.name}, cached_institution={cached_inst})"
