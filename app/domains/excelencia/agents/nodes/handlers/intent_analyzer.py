"""
Intent Analysis Handler

Handles query intent detection using LLM analysis with keyword fallback.
Single responsibility: analyze user queries to determine intent and query type.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from app.integrations.llm import ModelComplexity
from app.prompts import PromptRegistry
from app.utils.json_extractor import extract_json_from_text

from .base_handler import BaseExcelenciaHandler

if TYPE_CHECKING:
    from app.prompts import PromptManager

logger = logging.getLogger(__name__)

# Temperature for intent analysis (lower for deterministic JSON)
INTENT_ANALYSIS_TEMPERATURE = 0.3


@dataclass
class IntentResult:
    """Result of intent analysis."""

    query_type: str
    user_intent: str
    modules: list[str] = field(default_factory=list)
    requires_demo: bool = False
    urgency: str = "medium"


class IntentAnalysisHandler(BaseExcelenciaHandler):
    """
    Analyzes user queries to determine intent and query type.

    Uses LLM for deep understanding with keyword-based fallback.
    """

    def __init__(
        self,
        llm=None,
        prompt_manager: "PromptManager | None" = None,
    ):
        """
        Initialize handler with optional PromptManager.

        Args:
            llm: VllmLLM instance
            prompt_manager: PromptManager for loading prompt templates
        """
        super().__init__(llm)
        self._prompt_manager = prompt_manager

    @property
    def prompt_manager(self) -> "PromptManager | None":
        """Get PromptManager instance."""
        return self._prompt_manager

    # Query type keywords for detection
    QUERY_TYPES: ClassVar[dict[str, list[str]]] = {
        "demo": ["demo", "demostracion", "prueba", "presentacion", "mostrar"],
        "modules": ["modulo", "funcionalidad", "caracteristicas", "que hace", "para que sirve"],
        "training": ["capacitacion", "curso", "entrenamiento", "aprender", "formacion"],
        "support": ["soporte", "ayuda", "problema", "error", "consulta tecnica"],
        "products": ["producto", "sistema", "software", "solucion", "vertical"],
        "corporate": [
            "mision", "vision", "valores", "empresa", "quienes somos", "contacto", "redes",
            "ceo", "director", "fundador", "dueño", "propietario", "quien es el", "quién es"
        ],
        "clients": ["cliente", "caso", "exito", "referencia", "implementacion"],
        "general": ["excelencia", "erp", "informacion", "que es"],
        "incident": ["reportar", "incidencia", "levantar ticket", "falla grave", "bug", "no funciona", "se cayo"],
        "feedback": ["sugerencia", "comentario", "opinion", "feedback", "mejorar", "propuesta"],
    }

    async def analyze(
        self,
        message: str,
        state_dict: dict[str, Any],
        available_modules: dict[str, dict[str, Any]],
    ) -> IntentResult:
        """
        Analyze query intent with LLM and keyword fallback.

        Args:
            message: User message to analyze
            state_dict: Current state dictionary (contains conversation_summary)
            available_modules: Available software modules for detection

        Returns:
            IntentResult with query type, intent, modules, etc.
        """
        message_lower = message.lower()

        # Keyword-based query type detection
        query_type = self._detect_query_type(message_lower)

        # Detect mentioned modules
        mentioned_modules = self._detect_modules(message_lower, available_modules)

        # Try AI analysis for deeper understanding
        try:
            ai_result = await self._analyze_with_llm(message, state_dict)
            if ai_result:
                # Ensure specific_modules is a list (LLM might return string)
                specific_modules = ai_result.get("specific_modules", [])
                if isinstance(specific_modules, str):
                    specific_modules = [specific_modules] if specific_modules else []
                elif not isinstance(specific_modules, list):
                    specific_modules = []

                return IntentResult(
                    query_type=ai_result.get("query_type", query_type),
                    user_intent=ai_result.get("user_intent", ""),
                    modules=list(set(mentioned_modules + specific_modules)),
                    requires_demo=ai_result.get("requires_demo", False),
                    urgency=ai_result.get("urgency", "medium"),
                )
        except Exception as e:
            self.logger.error(f"Error in AI analysis: {e}")

        return self._create_fallback(message, query_type, mentioned_modules)

    def _detect_query_type(self, message_lower: str) -> str:
        """Detect query type using keyword matching."""
        for qtype, keywords in self.QUERY_TYPES.items():
            if any(keyword in message_lower for keyword in keywords):
                return qtype
        return "general"

    def _detect_modules(
        self, message_lower: str, modules: dict[str, dict[str, Any]]
    ) -> list[str]:
        """Detect mentioned modules in message."""
        mentioned = []
        for module_code, module_info in modules.items():
            name = str(module_info["name"]).lower()
            module_keywords = [name, module_code.lower()]
            features = module_info.get("features", [])
            if features:
                module_keywords.extend([str(f).lower() for f in features[:2]])

            if any(keyword in message_lower for keyword in module_keywords):
                mentioned.append(module_code)
        return mentioned

    async def _analyze_with_llm(
        self, message: str, state_dict: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Analyze intent using LLM."""
        conversation_summary = state_dict.get("conversation_summary", "")
        context_section = ""
        if conversation_summary:
            context_section = f"""
CONTEXTO DE CONVERSACION ANTERIOR:
{conversation_summary}

Considera este contexto al interpretar la consulta actual.
"""

        # Build prompt from YAML template or fallback to inline
        prompt = await self._build_analysis_prompt(message, context_section)

        self.logger.info("IntentAnalysisHandler: Analyzing with LLM...")
        llm = self.get_llm(complexity=ModelComplexity.SIMPLE, temperature=INTENT_ANALYSIS_TEMPERATURE)
        response = await llm.ainvoke(prompt)

        response_text = self.extract_response_content(response)
        self.logger.info(f"IntentAnalysisHandler: Parsing response: {response_text[:100]}...")

        result = extract_json_from_text(response_text, required_keys=["query_type"], default=None)
        # extract_json_from_text can return list or dict; we only accept dict
        if isinstance(result, dict):
            return result
        return None

    async def _build_analysis_prompt(self, message: str, context_section: str) -> str:
        """Build analysis prompt from YAML template or fallback."""
        if self._prompt_manager:
            try:
                return await self._prompt_manager.get_prompt(
                    PromptRegistry.EXCELENCIA_INTENT_ANALYSIS,
                    variables={
                        "message": message,
                        "context_section": context_section,
                    },
                )
            except Exception as e:
                self.logger.warning(f"Failed to load YAML prompt: {e}, using fallback")

        # Fallback to inline prompt
        return f"""Analiza la siguiente consulta sobre el Software Excelencia:
{context_section}
CONSULTA ACTUAL: "{message}"

Responde SOLO con un objeto JSON valido. Los valores posibles son:
- query_type: elegir UNO de estos valores exactos: "demo", "modules", "training", "support", "products", "general"
- user_intent: texto breve describiendo lo que busca el usuario (considera el contexto previo si existe)
- specific_modules: lista de modulos mencionados o referenciados (puede estar vacia)
- requires_demo: true o false (booleano, no texto)
- urgency: "low", "medium" o "high"

Ejemplo de respuesta valida:
{{"query_type": "support", "user_intent": "consulta sobre facturacion", "specific_modules": [], "requires_demo": false, "urgency": "medium"}}

Responde SOLO con el JSON, sin explicaciones ni texto adicional."""

    def _create_fallback(
        self, message: str, query_type: str, modules: list[str]
    ) -> IntentResult:
        """Create fallback analysis without AI."""
        return IntentResult(
            query_type=query_type,
            user_intent="Consulta sobre Excelencia Software",
            modules=modules,
            requires_demo="demo" in message.lower(),
            urgency="medium",
        )
