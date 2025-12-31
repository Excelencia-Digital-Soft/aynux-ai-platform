"""
Excelencia Promotions Agent - Handles Excelencia software promotions.

This agent manages promotional queries for Excelencia software services:
- Software module discounts
- Implementation offers
- Training deals
- Special pricing for software services

Uses RAG from company_knowledge for promotion-related information.
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

# Default promotions when database is unavailable
_FALLBACK_PROMOTIONS: list[dict[str, Any]] = [
    {
        "name": "Descuento Implementación",
        "description": "20% de descuento en servicios de implementación para nuevos clientes",
        "discount": "20%",
        "applies_to": "Nuevos clientes",
        "valid_until": "Consultar vigencia",
    },
    {
        "name": "Pack Capacitación",
        "description": "Capacitación incluida en la compra de módulos premium",
        "discount": "Capacitación gratis",
        "applies_to": "Módulos premium",
        "valid_until": "Consultar vigencia",
    },
    {
        "name": "Descuento Anual",
        "description": "15% de descuento al contratar licencia anual",
        "discount": "15%",
        "applies_to": "Licencias anuales",
        "valid_until": "Permanente",
    },
]


class ExcelenciaPromotionsAgent(BaseAgent):
    """
    Agent for Excelencia software promotions.

    Handles:
    - Software module discounts
    - Implementation offers
    - Training deals
    - Bundle pricing
    - Special promotions
    """

    # Promotion query type keywords
    QUERY_TYPES = {
        "discount": ["descuento", "rebaja", "reducción", "precio especial", "discount"],
        "offer": ["oferta", "promoción", "promo", "especial", "offer"],
        "bundle": ["paquete", "combo", "bundle", "pack", "conjunto"],
        "training": ["capacitación", "curso", "entrenamiento", "formación"],
        "implementation": ["implementación", "instalación", "puesta en marcha"],
        "license": ["licencia", "suscripción", "mensual", "anual"],
        "general": ["precio", "costo", "cuánto", "valor"],
    }

    def __init__(self, ollama=None, config: dict[str, Any] | None = None):
        super().__init__("excelencia_promotions_agent", config or {}, ollama=ollama)

        self.ollama = ollama or OllamaLLM()
        self.model = self.config.get("model", "llama3.1")
        self.temperature = self.config.get("temperature", 0.7)
        self.max_response_length = self.config.get("max_response_length", 500)

        # RAG configuration
        self.use_rag = getattr(settings, "KNOWLEDGE_BASE_ENABLED", True)
        self.rag_max_results = 3

        # Promotions cache
        self._promotions_cache: list[dict[str, Any]] | None = None

        # Initialize PromptManager for YAML-based prompts
        self.prompt_manager = PromptManager()

        logger.info(f"ExcelenciaPromotionsAgent initialized (RAG enabled: {self.use_rag})")

    async def _get_promotions(self) -> list[dict[str, Any]]:
        """
        Get active promotions from knowledge base with caching.

        Returns:
            List of promotion dictionaries
        """
        if self._promotions_cache is not None:
            return self._promotions_cache

        try:
            from app.core.container import DependencyContainer

            async with get_async_db_context() as db:
                container = DependencyContainer()
                use_case = container.create_search_knowledge_use_case(db)
                results = await use_case.execute(
                    query="promoción descuento oferta precio especial software",
                    max_results=10,
                    document_type="promotion",
                    search_strategy="pgvector_primary",
                )

                if results:
                    self._promotions_cache = [
                        {
                            "name": item.get("title", "Promoción"),
                            "description": item.get("content", "")[:200],
                            "discount": item.get("tags", ["Consultar"])[0] if item.get("tags") else "Consultar",
                            "applies_to": item.get("category", "General"),
                            "valid_until": "Consultar vigencia",
                        }
                        for item in results
                    ]
                    logger.info(f"Loaded {len(self._promotions_cache)} promotions from knowledge base")
                    return self._promotions_cache

        except Exception as e:
            logger.warning(f"Failed to load promotions from knowledge base: {e}, using fallback")

        self._promotions_cache = _FALLBACK_PROMOTIONS.copy()
        return self._promotions_cache

    @trace_async_method(
        name="excelencia_promotions_agent_process",
        run_type="chain",
        metadata={"agent_type": "excelencia_promotions_agent", "domain": "excelencia"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Process Excelencia promotion queries."""
        try:
            logger.info(f"ExcelenciaPromotionsAgent._process_internal START: {message[:50]}...")

            # Analyze query intent
            query_analysis = await self._analyze_query_intent(message)
            logger.info(f"ExcelenciaPromotionsAgent query_analysis done: {query_analysis.get('query_type')}")

            # Generate response
            response_text = await self._generate_response(message, query_analysis, state_dict)
            logger.info(f"ExcelenciaPromotionsAgent response generated: {len(response_text)} chars")

            result = {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "retrieved_data": {
                    "query_type": query_analysis.get("query_type"),
                    "modules_mentioned": query_analysis.get("modules", []),
                    "intent": query_analysis,
                },
                "query_type": query_analysis.get("query_type"),
                "is_complete": True,
            }
            logger.info("ExcelenciaPromotionsAgent._process_internal DONE")
            return result

        except Exception as e:
            logger.error(f"Error in excelencia promotions agent: {e!s}")
            error_response = self._generate_error_response()

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    async def _analyze_query_intent(self, message: str) -> dict[str, Any]:
        """Analyze query intent for promotion queries."""
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
                PromptRegistry.EXCELENCIA_PROMOTIONS_INTENT,
                variables={"message": message},
            )

            logger.info("ExcelenciaPromotionsAgent: Getting SIMPLE LLM for intent analysis...")
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

            if not ai_analysis or not isinstance(ai_analysis, dict):
                logger.warning("ExcelenciaPromotionsAgent: JSON extraction failed, using fallback")
                return self._create_fallback_analysis(query_type)

            return {
                "query_type": ai_analysis.get("query_type", query_type),
                "modules": ai_analysis.get("modules_interested", []),
                "is_new_client": ai_analysis.get("is_new_client"),
                "budget_mentioned": ai_analysis.get("budget_mentioned", False),
                "urgency": ai_analysis.get("urgency", "medium"),
            }

        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            return self._create_fallback_analysis(query_type)

    def _create_fallback_analysis(self, query_type: str) -> dict[str, Any]:
        """Create fallback analysis without AI."""
        return {
            "query_type": query_type,
            "modules": [],
            "is_new_client": None,
            "budget_mentioned": False,
            "urgency": "medium",
        }

    async def _search_knowledge_base(self, query: str) -> str:
        """Search knowledge base for promotion-related information."""
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

                context_parts = ["\n## INFORMACIÓN DE PROMOCIONES (Knowledge Base):"]
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
        self, user_message: str, query_analysis: dict[str, Any], state_dict: dict[str, Any]
    ) -> str:
        """Generate response based on query analysis."""
        query_type = query_analysis.get("query_type", "general")
        modules = query_analysis.get("modules", [])
        is_new_client = query_analysis.get("is_new_client")

        # Get conversation context from state (injected by HistoryAgent)
        conversation_summary = state_dict.get("conversation_summary", "")
        if conversation_summary:
            logger.info(f"ExcelenciaPromotionsAgent: Using conversation context ({len(conversation_summary)} chars)")

        # Get promotions
        promotions = await self._get_promotions()

        # Search knowledge base
        rag_context = await self._search_knowledge_base(user_message)

        # Build promotions context
        promos_text = "\n".join(
            f"- **{p['name']}**: {p['description']} ({p['discount']})"
            for p in promotions[:4]
        )

        # Build response prompt from YAML
        try:
            response_prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.EXCELENCIA_PROMOTIONS_RESPONSE,
                variables={
                    "user_message": user_message,
                    "query_type": query_type,
                    "modules": ", ".join(modules) if modules else "No especificados",
                    "is_new_client": str(is_new_client) if is_new_client is not None else "No especificado",
                    "rag_context": rag_context,
                    "promotions_text": promos_text,
                    "conversation_summary": conversation_summary,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to load YAML prompt: {e}")
            return await self._generate_fallback_response(query_type, promotions)

        try:
            logger.info("ExcelenciaPromotionsAgent: Getting COMPLEX LLM for response generation...")
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
            return await self._generate_fallback_response(query_type, promotions)

    async def _generate_fallback_response(
        self, query_type: str, promotions: list[dict[str, Any]]
    ) -> str:
        """Generate fallback response using YAML prompts."""
        promos_list = "\n".join(
            f"- **{p['name']}**: {p['discount']}" for p in promotions[:3]
        )

        # Map query types to registry keys
        key_mapping = {
            "discount": PromptRegistry.EXCELENCIA_PROMOTIONS_FALLBACK_DISCOUNT,
            "bundle": PromptRegistry.EXCELENCIA_PROMOTIONS_FALLBACK_BUNDLE,
            "training": PromptRegistry.EXCELENCIA_PROMOTIONS_FALLBACK_TRAINING,
            "implementation": PromptRegistry.EXCELENCIA_PROMOTIONS_FALLBACK_IMPLEMENTATION,
        }

        prompt_key = key_mapping.get(query_type, PromptRegistry.EXCELENCIA_PROMOTIONS_FALLBACK_GENERAL)

        try:
            response = await self.prompt_manager.get_prompt(
                prompt_key,
                variables={"promotions_list": promos_list},
            )
            return response
        except Exception as e:
            logger.warning(f"Failed to load YAML fallback prompt: {e}")
            return (
                "Promociones Excelencia Software\n\n"
                f"Promociones activas:\n{promos_list}\n\n"
                "Sobre que promocion te gustaria mas informacion?"
            )

    def _generate_error_response(self) -> str:
        """Generate friendly error response."""
        return (
            "Disculpa, tuve un inconveniente procesando tu consulta de promociones. "
            "¿Podrías reformular tu pregunta? Puedo ayudarte con:\n"
            "- Descuentos en software\n"
            "- Ofertas de implementación\n"
            "- Promociones de capacitación"
        )
