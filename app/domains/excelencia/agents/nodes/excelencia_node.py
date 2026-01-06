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
from app.domains.excelencia.application.services.support_response import (
    KnowledgeBaseSearch,
    RagQueryLogger,
    SearchMetrics,
)
from app.integrations.llm import VllmLLM
from app.prompts.manager import PromptManager

from .handlers import (
    IntentAnalysisHandler,
    IntentResult,
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

    def __init__(self, llm: VllmLLM | None = None, config: dict[str, Any] | None = None):
        super().__init__("excelencia_node", config or {}, llm=llm)

        self.llm = llm or VllmLLM()

        # Initialize PromptManager for YAML-based prompts (critical for RAG response)
        self._prompt_manager = PromptManager()

        # Initialize handlers (pass prompt_manager to response handler for RAG prompts)
        self._module_manager = ModuleManager()
        self._intent_analyzer = IntentAnalysisHandler(self.llm, self._prompt_manager)
        self._ticket_handler = TicketHandler(self.llm)
        self._response_handler = ResponseGenerationHandler(self.llm, self._prompt_manager)

        # Knowledge search service
        self._knowledge_search = KnowledgeBaseSearch(agent_key="excelencia_agent")

        # RAG logging service (SRP: separate logging responsibility)
        self._rag_logger = RagQueryLogger(agent_key="excelencia_agent")

        # RAG configuration
        self.use_rag = getattr(settings, "KNOWLEDGE_BASE_ENABLED", True)

        # RAG metrics for last search (exposed to frontend and for logging)
        self._last_rag_metrics: dict[str, Any] | None = None
        self._last_search_metrics: SearchMetrics | None = None

        logger.info(f"ExcelenciaNode initialized (RAG enabled: {self.use_rag})")

    def _try_reuse_orchestrator_intent(
        self, message: str, state_dict: dict[str, Any], modules: dict[str, Any]
    ) -> IntentResult | None:
        """
        Reuse intent from orchestrator to avoid duplicate LLM call.

        The orchestrator already analyzed the intent and stored it in:
        - state["orchestrator_analysis"]["detected_intent"]
        - state["routing_decision"]["intent"]

        Returns IntentResult if we can reuse, None if we need fresh analysis.
        """
        try:
            orchestrator = state_dict.get("orchestrator_analysis", {})
            routing = state_dict.get("routing_decision", {})

            detected_intent = orchestrator.get("detected_intent")
            confidence = orchestrator.get("confidence_score", 0.0)

            # Only reuse if high confidence and valid intent
            if not detected_intent or confidence < 0.7:
                logger.debug(
                    f"Cannot reuse orchestrator intent: detected={detected_intent}, confidence={confidence}"
                )
                return None

            # Map orchestrator intent to ExcelenciaNode query types
            query_type_map = {
                "excelencia": "general",
                "support": "support",
                "demo": "demo",
                "training": "training",
                "products": "products",
                "corporate": "corporate",
                "modules": "modules",
                "clients": "clients",
                "incident": "incident",
                "feedback": "feedback",
            }
            query_type = query_type_map.get(detected_intent, "general")

            # Fast module detection (no LLM - keyword matching only)
            mentioned = []
            msg_lower = message.lower()
            for code, info in modules.items():
                name = str(info.get("name", "")).lower()
                if name and name in msg_lower:
                    mentioned.append(code)
                elif code.lower() in msg_lower:
                    mentioned.append(code)

            return IntentResult(
                query_type=query_type,
                user_intent=routing.get("reason", "Excelencia query"),
                modules=mentioned,
                requires_demo="demo" in detected_intent.lower() if detected_intent else False,
                urgency="medium",
            )
        except Exception as e:
            logger.debug(f"Could not reuse orchestrator intent: {e}")
            return None

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

            # 2. Try to reuse intent from orchestrator (OPTIMIZATION: skip duplicate LLM call)
            intent_result = self._try_reuse_orchestrator_intent(message, state_dict, modules)

            if intent_result:
                logger.info(f"ExcelenciaNode: Reusing orchestrator intent: {intent_result.query_type}")
            else:
                # Fallback: analyze with LLM (only if orchestrator didn't provide intent)
                intent_result = await self._intent_analyzer.analyze(message, state_dict, modules)
                logger.info(f"ExcelenciaNode intent analysis done (LLM): {intent_result.query_type}")

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

            # 6. Log RAG query with response (fire-and-forget)
            if self._last_search_metrics and self._last_search_metrics.result_count > 0:
                # Calculate approximate token count from context
                token_count = len(rag_context.split()) if rag_context else 0
                self._rag_logger.log_async(
                    query=message,
                    metrics=self._last_search_metrics,
                    response=response_text,
                    token_count=token_count,
                )

            # 7. Build and return result
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
        self._last_search_metrics = None

        if not self.use_rag:
            logger.info("RAG disabled for this agent (use_rag=False)")
            return ""

        try:
            logger.info(f"Searching RAG for: '{message[:50]}...' (query_type={query_type})")
            search_result = await self._knowledge_search.search(message, query_type)
            self._last_search_metrics = search_result.metrics

            # Log search results for debugging
            logger.info(
                f"RAG search completed: result_count={search_result.metrics.result_count}, "
                f"relevance={search_result.metrics.relevance_score}, "
                f"context_used={search_result.metrics.context_used}, "
                f"latency={search_result.metrics.latency_ms:.1f}ms"
            )

            if search_result.metrics.result_count > 0:
                logger.info(f"RAG context preview: {search_result.context[:200]}...")
            else:
                logger.warning(f"RAG returned NO results for query: '{message[:50]}...'")

            self._last_rag_metrics = {
                "used": bool(search_result.context),
                "query": message,
                "has_results": search_result.metrics.result_count > 0,
                "result_count": search_result.metrics.result_count,  # Add explicit count
                "latency_ms": search_result.metrics.latency_ms,
                "relevance_score": search_result.metrics.relevance_score,
            }
            return search_result.context
        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}", exc_info=True)
            self._last_rag_metrics["error"] = str(e)
            return ""

    def _build_result(self, response_text: str, intent_result: Any) -> dict[str, Any]:
        """Build the final result dictionary.

        Note: is_complete is NOT set here. The supervisor evaluates the response
        quality and decides whether to complete or re-route.
        """
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
            # is_complete is decided by supervisor, not here
            "rag_metrics": self._last_rag_metrics,
        }


# Alias for backward compatibility
ExcelenciaAgent = ExcelenciaNode
