"""
Excelencia Support Agent - Handles Excelencia Software software support.

This agent manages support queries for Excelencia software:
- Technical incidents and bug reports
- Module troubleshooting
- Ticket creation and tracking
- Error resolution

Delegates to specialized services for:
- Incident flow management
- Response generation with RAG
- Query analysis
"""

import logging
from typing import Any

from app.core.agents import BaseAgent
from app.core.utils.tracing import trace_async_method
from app.domains.excelencia.application.services.incident_flow import IncidentFlowManager
from app.domains.excelencia.application.services.query_type_detector import (
    CompositeQueryTypeDetector,
)
from app.domains.excelencia.application.services.query_type_loader import (
    create_query_type_detector,
)
from app.domains.excelencia.application.services.support_config import SupportConfig
from app.domains.excelencia.application.services.support_response import (
    SupportResponseGenerator,
)
from app.integrations.llm import VllmLLM
from app.prompts.manager import PromptManager

logger = logging.getLogger(__name__)


class ExcelenciaSupportAgent(BaseAgent):
    """
    Agent for Excelencia software support and incidents.

    Handles:
    - Technical incidents and bug reports
    - Module-specific troubleshooting
    - Ticket creation and tracking
    - Error resolution guidance

    Delegates to:
    - IncidentFlowManager: Multi-step incident creation
    - SupportResponseGenerator: RAG-based response generation
    - SupportConfig: Centralized configuration
    """

    def __init__(
        self,
        llm: VllmLLM | None = None,
        config: dict[str, Any] | None = None,
        query_type_detector: CompositeQueryTypeDetector | None = None,
    ):
        """Initialize ExcelenciaSupportAgent.

        Args:
            llm: VllmLLM instance for language model calls
            config: Optional configuration dictionary
            query_type_detector: Optional detector for DIP (Dependency Injection)
        """
        super().__init__("excelencia_support_agent", config or {}, llm=llm)

        self._llm = llm or VllmLLM()
        self._prompt_manager = PromptManager()

        # Query type detector (DIP)
        self._query_detector = query_type_detector or create_query_type_detector()

        # Incident flow manager (handles multi-step flow)
        self._flow_manager = IncidentFlowManager(
            llm=self._llm,
            prompt_manager=self._prompt_manager,
        )

        # Response generator (RAG + LLM)
        self._response_generator = SupportResponseGenerator(
            llm=self._llm,
            prompt_manager=self._prompt_manager,
        )

        logger.info("ExcelenciaSupportAgent initialized (services injected)")

    @trace_async_method(
        name="excelencia_support_agent_process",
        run_type="chain",
        metadata={"agent_type": "excelencia_support_agent", "domain": "excelencia"},
        extract_state=True,
    )
    async def _process_internal(
        self, message: str, state_dict: dict[str, Any]
    ) -> dict[str, Any]:
        """Process Excelencia support queries."""
        try:
            logger.info(f"ExcelenciaSupportAgent processing: {message[:50]}...")

            # Check for active incident flow
            pending_ticket = await self._flow_manager.get_active_flow(state_dict)
            if pending_ticket:
                logger.info(f"Active incident flow, step: {pending_ticket.current_step}")
                response = await self._flow_manager.handle_step(
                    message, pending_ticket, state_dict
                )
                return self._build_response(response, "incident_flow", state_dict)

            # Analyze query intent
            query_analysis = self._analyze_query(message)
            query_type = query_analysis.get("query_type", "general")
            logger.info(f"Query type: {query_type}")

            # Start incident flow if needed
            if query_type in ["incident", "feedback"]:
                response = await self._flow_manager.start_flow(state_dict)
                return self._build_response(response, query_type, state_dict)

            # Generate support response with RAG
            response = await self._response_generator.generate(
                message, query_analysis, state_dict
            )

            return self._build_full_response(response, query_type, query_analysis, state_dict)

        except Exception as e:
            logger.error(f"Error in excelencia support agent: {e!s}")
            return self._build_error_response(state_dict)

    def _analyze_query(self, message: str) -> dict[str, Any]:
        """Analyze query intent using detector and config."""
        match = self._query_detector.detect(message)

        logger.info(
            f"Query detected: {match.query_type} "
            f"(confidence: {match.confidence:.2f}, matched: {match.matched_keyword})"
        )

        return {
            "query_type": match.query_type,
            "query_type_confidence": match.confidence,
            "matched_keyword": match.matched_keyword,
            "module": SupportConfig.detect_module(message),
            "urgency": SupportConfig.detect_urgency(message),
        }

    def _build_response(
        self, response_text: str, query_type: str, state_dict: dict[str, Any]
    ) -> dict[str, Any]:
        """Build standard response dict."""
        return {
            "messages": [{"role": "assistant", "content": response_text}],
            "current_agent": self.name,
            "agent_history": [self.name],
            "query_type": query_type,
            "is_complete": True,
        }

    def _build_full_response(
        self,
        response_text: str,
        query_type: str,
        query_analysis: dict[str, Any],
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Build full response with retrieved data."""
        return {
            "messages": [{"role": "assistant", "content": response_text}],
            "current_agent": self.name,
            "agent_history": [self.name],
            "retrieved_data": {
                "query_type": query_type,
                "module_mentioned": query_analysis.get("module"),
                "intent": query_analysis,
            },
            "query_type": query_type,
            "is_complete": True,
        }

    def _build_error_response(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Build error response."""
        error_message = (
            "Disculpa, tuve un inconveniente procesando tu consulta de soporte. "
            "Podrias reformular tu pregunta? Puedo ayudarte con:\n"
            "- Incidencias y problemas tecnicos\n"
            "- Informacion de modulos\n"
            "- Capacitacion y guias"
        )
        return {
            "messages": [{"role": "assistant", "content": error_message}],
            "error_count": state_dict.get("error_count", 0) + 1,
            "current_agent": self.name,
        }
