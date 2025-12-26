"""
Excelencia Invoice Agent - Handles Excelencia client invoicing.

This agent manages invoice queries for Excelencia software clients:
- Client invoice generation and queries
- Account statements
- Collections and pending payments
- Payment status tracking

Uses RAG from company_knowledge for invoice-related information.
"""

import logging
from typing import Any

from app.config.settings import get_settings
from app.utils.json_extractor import extract_json_from_text
from app.core.agents import BaseAgent
from app.core.utils.tracing import trace_async_method
from app.database.async_db import get_async_db_context
from app.integrations.llm import OllamaLLM
from app.integrations.llm.model_provider import ModelComplexity
from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry

logger = logging.getLogger(__name__)
settings = get_settings()

# Temperature settings
INTENT_ANALYSIS_TEMPERATURE = 0.3
RESPONSE_GENERATION_TEMPERATURE = 0.7


class ExcelenciaInvoiceAgent(BaseAgent):
    """
    Agent for Excelencia client invoicing.

    Handles:
    - Client invoice queries and generation
    - Account statements
    - Collections management
    - Payment tracking for software services
    """

    # Invoice query type keywords
    QUERY_TYPES = {
        "invoice": ["factura", "facturar", "facturación", "comprobante", "invoice"],
        "statement": ["estado de cuenta", "saldo", "balance", "deuda", "adeuda"],
        "collection": ["cobranza", "cobrar", "pendiente", "vencido", "mora"],
        "payment": ["pago", "pagó", "abono", "deposito", "transferencia"],
        "history": ["historial", "facturas anteriores", "movimientos", "histórico"],
        "general": ["cliente", "cuenta", "consulta"],
    }

    def __init__(self, ollama=None, config: dict[str, Any] | None = None):
        super().__init__("excelencia_invoice_agent", config or {}, ollama=ollama)

        self.ollama = ollama or OllamaLLM()
        self.model = self.config.get("model", "llama3.1")
        self.temperature = self.config.get("temperature", 0.7)
        self.max_response_length = self.config.get("max_response_length", 500)

        # RAG configuration
        self.use_rag = getattr(settings, "KNOWLEDGE_BASE_ENABLED", True)
        self.rag_max_results = 3

        # Initialize PromptManager for YAML-based prompts
        self.prompt_manager = PromptManager()

        logger.info(f"ExcelenciaInvoiceAgent initialized (RAG enabled: {self.use_rag})")

    @trace_async_method(
        name="excelencia_invoice_agent_process",
        run_type="chain",
        metadata={"agent_type": "excelencia_invoice_agent", "domain": "excelencia"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Process Excelencia invoice queries."""
        try:
            logger.info(f"ExcelenciaInvoiceAgent._process_internal START: {message[:50]}...")

            # Analyze query intent
            query_analysis = await self._analyze_query_intent(message)
            logger.info(f"ExcelenciaInvoiceAgent query_analysis done: {query_analysis.get('query_type')}")

            # Generate response
            response_text = await self._generate_response(message, query_analysis, state_dict)
            logger.info(f"ExcelenciaInvoiceAgent response generated: {len(response_text)} chars")

            result = {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "retrieved_data": {
                    "query_type": query_analysis.get("query_type"),
                    "client_mentioned": query_analysis.get("client_name"),
                    "intent": query_analysis,
                },
                "query_type": query_analysis.get("query_type"),
                "is_complete": True,
            }
            logger.info("ExcelenciaInvoiceAgent._process_internal DONE")
            return result

        except Exception as e:
            logger.error(f"Error in excelencia invoice agent: {e!s}")
            error_response = self._generate_error_response()

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    async def _analyze_query_intent(self, message: str) -> dict[str, Any]:
        """Analyze query intent for invoice operations."""
        message_lower = message.lower()

        # Detect query type
        query_type = "general"
        for qtype, keywords in self.QUERY_TYPES.items():
            if any(keyword in message_lower for keyword in keywords):
                query_type = qtype
                break

        # Try AI analysis for deeper understanding
        try:
            # Load prompt from YAML
            prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.EXCELENCIA_INVOICE_INTENT,
                variables={"message": message},
            )

            logger.info("ExcelenciaInvoiceAgent: Getting SIMPLE LLM for intent analysis...")
            llm = self.ollama.get_llm(
                complexity=ModelComplexity.SIMPLE,
                temperature=INTENT_ANALYSIS_TEMPERATURE,
            )
            response = await llm.ainvoke(prompt)

            response_text = response.content if isinstance(response.content, str) else str(response.content)

            # Use robust JSON extractor that handles <think> tags, markdown, and Python booleans
            ai_analysis = extract_json_from_text(
                response_text,
                required_keys=["query_type"],
                default=None,
            )

            if not ai_analysis:
                logger.warning("ExcelenciaInvoiceAgent: JSON extraction failed, using fallback")
                return self._create_fallback_analysis(query_type)

            return {
                "query_type": ai_analysis.get("query_type", query_type),
                "client_name": ai_analysis.get("client_name"),
                "action_requested": ai_analysis.get("action_requested", "consultar"),
                "period": ai_analysis.get("period"),
                "urgency": ai_analysis.get("urgency", "medium"),
            }

        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            return self._create_fallback_analysis(query_type)

    def _create_fallback_analysis(self, query_type: str) -> dict[str, Any]:
        """Create fallback analysis without AI."""
        return {
            "query_type": query_type,
            "client_name": None,
            "action_requested": "consultar",
            "period": None,
            "urgency": "medium",
        }

    async def _search_knowledge_base(self, query: str) -> str:
        """Search knowledge base for invoice-related information."""
        if not self.use_rag:
            return ""

        try:
            from app.core.container import DependencyContainer

            async with get_async_db_context() as db:
                container = DependencyContainer()
                use_case = container.create_search_knowledge_use_case(db)
                results = await use_case.execute(
                    query=query,
                    max_results=self.rag_max_results,
                    search_strategy="pgvector_primary",
                )

                if not results:
                    return ""

                context_parts = ["\n## INFORMACIÓN DE FACTURACIÓN (Knowledge Base):"]
                for i, result in enumerate(results, 1):
                    context_parts.append(f"\n### {i}. {result.get('title', 'Sin título')}")
                    content = result.get("content", "")
                    content_preview = content[:200] + "..." if len(content) > 200 else content
                    context_parts.append(f"{content_preview}")

                return "\n".join(context_parts)

        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}")
            return ""

    async def _generate_response(
        self, user_message: str, query_analysis: dict[str, Any], _state_dict: dict[str, Any]
    ) -> str:
        """Generate response based on query analysis."""
        query_type = query_analysis.get("query_type", "general")
        client_name = query_analysis.get("client_name")
        action = query_analysis.get("action_requested", "consultar")

        # Search knowledge base
        rag_context = await self._search_knowledge_base(user_message)

        # Build response prompt from YAML
        try:
            response_prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.EXCELENCIA_INVOICE_RESPONSE,
                variables={
                    "user_message": user_message,
                    "query_type": query_type,
                    "client_name": client_name or "No especificado",
                    "action": action,
                    "period": query_analysis.get("period") or "No especificado",
                    "rag_context": rag_context,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to load YAML prompt: {e}")
            return await self._generate_fallback_response(query_type, client_name)

        try:
            logger.info("ExcelenciaInvoiceAgent: Getting COMPLEX LLM for response generation...")
            llm = self.ollama.get_llm(
                complexity=ModelComplexity.COMPLEX,
                temperature=RESPONSE_GENERATION_TEMPERATURE,
            )
            response = await llm.ainvoke(response_prompt)

            if hasattr(response, "content"):
                content = response.content
                if isinstance(content, str):
                    result = content.strip()
                elif isinstance(content, list):
                    result = " ".join(str(item) for item in content).strip()
                else:
                    result = str(content).strip()

                result = OllamaLLM.clean_deepseek_response(result)
                return result
            else:
                result = str(response).strip()
                result = OllamaLLM.clean_deepseek_response(result)
                return result

        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return await self._generate_fallback_response(query_type, client_name)

    async def _generate_fallback_response(self, query_type: str, client_name: str | None = None) -> str:
        """Generate fallback response using YAML prompts."""
        client_text = f" para el cliente {client_name}" if client_name else ""

        # Map query types to registry keys
        key_mapping = {
            "invoice": PromptRegistry.EXCELENCIA_INVOICE_FALLBACK_INVOICE,
            "statement": PromptRegistry.EXCELENCIA_INVOICE_FALLBACK_STATEMENT,
            "collection": PromptRegistry.EXCELENCIA_INVOICE_FALLBACK_COLLECTION,
            "payment": PromptRegistry.EXCELENCIA_INVOICE_FALLBACK_PAYMENT,
        }

        prompt_key = key_mapping.get(query_type, PromptRegistry.EXCELENCIA_INVOICE_FALLBACK_GENERAL)

        try:
            response = await self.prompt_manager.get_prompt(
                prompt_key,
                variables={"client_text": client_text},
            )
            return response
        except Exception as e:
            logger.warning(f"Failed to load YAML fallback prompt: {e}")
            return (
                "Facturacion de Clientes Excelencia\n\n"
                "Puedo ayudarte con:\n"
                "- Generacion de facturas\n"
                "- Estados de cuenta\n"
                "- Gestion de cobranzas\n"
                "- Registro de pagos\n\n"
                "Que necesitas consultar?"
            )

    def _generate_error_response(self) -> str:
        """Generate friendly error response."""
        return (
            "Disculpa, tuve un inconveniente procesando tu consulta de facturación. "
            "¿Podrías reformular tu pregunta? Puedo ayudarte con:\n"
            "- Facturas de clientes\n"
            "- Estados de cuenta\n"
            "- Cobranzas y pagos"
        )
