"""
Excelencia Node - Main node for Software Excelencia queries.

Orchestrates handlers for intent analysis, knowledge search,
ticket creation, and response generation.

Refactored from 773-line monolith to ~150-line orchestrator following SRP.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from app.config.settings import get_settings
from app.core.agents import BaseAgent
from app.core.utils.tracing import trace_async_method
from app.domains.excelencia.application.services.support_response.knowledge_search import (
    KnowledgeBaseSearch,
)
from app.integrations.llm import OllamaLLM

from .handlers import (
    IntentAnalysisHandler,
    ModuleManager,
    ResponseGenerationHandler,
    TicketHandler,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class ExcelenciaNode(BaseAgent):
    """
    Node for Software Excelencia queries.

    Orchestrates handlers for:
    - Intent analysis (query type detection)
    - Module management (software catalog)
    - Ticket creation (incidents/feedback)
    - Response generation (LLM-powered)

    Uses KnowledgeBaseSearch service for RAG.
    """

    def __init__(self, ollama: OllamaLLM | None = None, config: dict[str, Any] | None = None):
        super().__init__("excelencia_node", config or {}, ollama=ollama)

        self.ollama = ollama or OllamaLLM()

        # Initialize handlers
        self._module_manager = ModuleManager()
        self._intent_analyzer = IntentAnalysisHandler(self.ollama)
        self._ticket_handler = TicketHandler(self.ollama)
        self._response_handler = ResponseGenerationHandler(self.ollama)

        # Knowledge search service
        self._knowledge_search = KnowledgeBaseSearch(agent_key="excelencia_agent")

        # RAG configuration
        self.use_rag = getattr(settings, "KNOWLEDGE_BASE_ENABLED", True)

        # RAG metrics for last search (exposed to frontend)
        self._last_rag_metrics: dict[str, Any] | None = None

        logger.info(f"ExcelenciaNode initialized (RAG enabled: {self.use_rag})")

    @trace_async_method(
        name="excelencia_node_process",
        run_type="chain",
        metadata={"agent_type": "excelencia_node", "domain": "excelencia"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Process Excelencia Software queries."""
        try:
            logger.info(f"ExcelenciaNode._process_internal START: {message[:50]}...")

            # 1. Get modules
            modules = await self._module_manager.get_modules()

            # 2. Analyze query intent
            intent_result = await self._intent_analyzer.analyze(message, state_dict, modules)
            logger.info(f"ExcelenciaNode intent analysis done: {intent_result.query_type}")

            # 3. Handle ticket creation if needed
            if intent_result.query_type in ("incident", "feedback"):
                return await self._handle_ticket_creation(message, intent_result, state_dict)

            # 4. Search knowledge base
            rag_context = await self._get_rag_context(message, intent_result.query_type)

            # 5. Generate response
            response_text = await self._response_handler.generate(
                user_message=message,
                query_analysis=asdict(intent_result),
                state_dict=state_dict,
                modules=modules,
                rag_context=rag_context,
            )
            logger.info(f"ExcelenciaNode response generated: {len(response_text)} chars")

            # 6. Build and return result
            return self._build_result(response_text, intent_result)

        except Exception as e:
            logger.error(f"Error in excelencia node: {str(e)}")
            error_response = self._response_handler.generate_error()

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    async def _handle_ticket_creation(
        self, message: str, intent_result: Any, state_dict: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle incident/feedback ticket creation."""
        user_phone = state_dict.get("user_phone", state_dict.get("sender", "unknown"))
        conversation_id = state_dict.get("conversation_id")
        module = intent_result.modules[0] if intent_result.modules else None

        ticket_result = await self._ticket_handler.create_ticket(
            user_phone=user_phone,
            ticket_type=intent_result.query_type,
            description=message,
            module=module,
            conversation_id=conversation_id,
        )

        return {
            "messages": [{"role": "assistant", "content": ticket_result.confirmation_message}],
            "current_agent": self.name,
            "agent_history": [self.name],
            "retrieved_data": {
                "query_type": intent_result.query_type,
                "ticket_id": ticket_result.ticket_id,
                "ticket_success": ticket_result.success,
            },
            "query_type": intent_result.query_type,
            "is_complete": True,
        }

    async def _get_rag_context(self, message: str, query_type: str) -> str:
        """Get RAG context from knowledge base."""
        self._last_rag_metrics = {"used": False, "query": message}

        if not self.use_rag:
            return ""

        try:
            context = await self._knowledge_search.search(message, query_type)
            self._last_rag_metrics = {
                "used": bool(context),
                "query": message,
                "has_results": bool(context),
            }
            return context
        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}")
            self._last_rag_metrics["error"] = str(e)
            return ""

    def _build_result(self, response_text: str, intent_result: Any) -> dict[str, Any]:
        """Build the final result dictionary."""
        return {
            "messages": [{"role": "assistant", "content": response_text}],
            "current_agent": self.name,
            "agent_history": [self.name],
            "retrieved_data": {
                "query_type": intent_result.query_type,
                "modules_mentioned": intent_result.modules,
                "intent": asdict(intent_result),
            },
            "query_type": intent_result.query_type,
            "mentioned_modules": intent_result.modules,
            "requires_demo": intent_result.requires_demo,
            "is_complete": True,
            "rag_metrics": self._last_rag_metrics,
        }


# Alias for backward compatibility
ExcelenciaAgent = ExcelenciaNode
