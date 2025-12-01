"""
Excelencia Node - Main node for ERP Excelencia queries.

Migrated from app/agents/subagent/excelencia_agent.py
Handles information about demos, modules, support, training and corporate queries via RAG.

Modules are loaded dynamically from PostgreSQL (erp_modules table) instead of hardcoded.
"""

import json
import logging
from typing import Any

from app.config.settings import get_settings
from app.core.agents import BaseAgent
from app.core.utils.tracing import trace_async_method
from app.database.async_db import get_async_db_context
from app.integrations.llm import OllamaLLM

logger = logging.getLogger(__name__)
settings = get_settings()


# Fallback modules when database is unavailable
_FALLBACK_MODULES: dict[str, dict[str, Any]] = {
    "HC-001": {
        "name": "Historia Clínica Electrónica",
        "description": "Sistema de gestión de historias clínicas digitales",
        "features": ["Registro de pacientes", "Consultas médicas", "Prescripciones"],
        "target": "healthcare",
    },
    "TM-001": {
        "name": "Sistema de Turnos Médicos",
        "description": "Gestión de agendas y turnos de pacientes",
        "features": ["Agenda médica", "Turnos online", "Recordatorios"],
        "target": "healthcare",
    },
    "HO-001": {
        "name": "Gestión Hotelera",
        "description": "Software para administración de hoteles",
        "features": ["Reservas", "Check-in/out", "Facturación"],
        "target": "hospitality",
    },
}


class ExcelenciaNode(BaseAgent):
    """
    Node for ERP Excelencia queries.

    Handles:
    - Demo and presentation requests
    - Module information
    - Training and support queries
    - Corporate information via RAG
    """

    # Query type keywords
    QUERY_TYPES = {
        "demo": ["demo", "demostración", "prueba", "presentación", "mostrar"],
        "modules": ["módulo", "funcionalidad", "características", "qué hace", "para qué sirve"],
        "training": ["capacitación", "curso", "entrenamiento", "aprender", "formación"],
        "support": ["soporte", "ayuda", "problema", "error", "consulta técnica"],
        "products": ["producto", "sistema", "software", "solución", "vertical"],
        "corporate": ["misión", "visión", "valores", "empresa", "quiénes somos", "contacto", "redes"],
        "clients": ["cliente", "caso", "éxito", "referencia", "implementación"],
        "general": ["excelencia", "erp", "información", "qué es"],
    }

    def __init__(self, ollama=None, config: dict[str, Any] | None = None):
        super().__init__("excelencia_node", config or {}, ollama=ollama)

        self.ollama = ollama or OllamaLLM()
        self.model = self.config.get("model", "llama3.1")
        self.temperature = self.config.get("temperature", 0.7)
        self.max_response_length = self.config.get("max_response_length", 500)

        # RAG configuration
        self.use_rag = getattr(settings, "KNOWLEDGE_BASE_ENABLED", True)
        self.rag_max_results = 3

        # Module cache (loaded on first use from DB)
        self._modules_cache: dict[str, dict[str, Any]] | None = None

        logger.info(f"ExcelenciaNode initialized (RAG enabled: {self.use_rag})")

    async def _get_modules(self) -> dict[str, dict[str, Any]]:
        """
        Get ERP modules from database with caching.

        Returns:
            Dict of module_code -> module_info
        """
        if self._modules_cache is not None:
            return self._modules_cache

        try:
            from app.core.container import DependencyContainer

            async with get_async_db_context() as db:
                container = DependencyContainer()
                use_case = container.create_get_modules_use_case(db)
                result = await use_case.execute(only_available=True)

                self._modules_cache = result.modules_dict
                logger.info(f"Loaded {len(self._modules_cache)} ERP modules from database")
                return self._modules_cache

        except Exception as e:
            logger.warning(f"Failed to load modules from DB: {e}, using fallback")
            self._modules_cache = _FALLBACK_MODULES.copy()
            return self._modules_cache

    @trace_async_method(
        name="excelencia_node_process",
        run_type="chain",
        metadata={"agent_type": "excelencia_node", "domain": "excelencia"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Process Excelencia ERP queries."""
        try:
            # Analyze query intent
            query_analysis = await self._analyze_query_intent(message)

            # Generate response
            response_text = await self._generate_response(message, query_analysis, state_dict)

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "retrieved_data": {
                    "query_type": query_analysis.get("query_type"),
                    "modules_mentioned": query_analysis.get("modules", []),
                    "intent": query_analysis,
                },
                "query_type": query_analysis.get("query_type"),
                "mentioned_modules": query_analysis.get("modules", []),
                "requires_demo": query_analysis.get("requires_demo", False),
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in excelencia node: {str(e)}")
            error_response = await self._generate_error_response()

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    async def _analyze_query_intent(self, message: str) -> dict[str, Any]:
        """Analyze query intent for Excelencia."""
        message_lower = message.lower()

        # Detect query type
        query_type = "general"
        for qtype, keywords in self.QUERY_TYPES.items():
            if any(keyword in message_lower for keyword in keywords):
                query_type = qtype
                break

        # Get modules from database
        modules = await self._get_modules()

        # Detect mentioned modules
        mentioned_modules = []
        for module_code, module_info in modules.items():
            name = str(module_info["name"]).lower()
            module_keywords = [name, module_code.lower()]
            features = module_info.get("features", [])
            if features:
                module_keywords.extend([str(f).lower() for f in features[:2]])

            if any(keyword in message_lower for keyword in module_keywords):
                mentioned_modules.append(module_code)

        # Try AI analysis for deeper understanding
        try:
            prompt = f"""Analiza la siguiente consulta sobre el ERP Excelencia:

"{message}"

Responde en JSON con esta estructura:
{{
  "query_type": "demo|modules|training|support|products|general",
  "user_intent": "breve descripción de lo que busca el usuario",
  "specific_modules": ["módulo1", "módulo2"],
  "requires_demo": true|false,
  "urgency": "low|medium|high"
}}

Responde solo con el JSON, sin texto adicional."""

            llm = self.ollama.get_llm(temperature=0.3, model=self.model)
            response = await llm.ainvoke(prompt)

            try:
                response_text = response.content if isinstance(response.content, str) else str(response.content)
                ai_analysis = json.loads(response_text)
                return {
                    "query_type": ai_analysis.get("query_type", query_type),
                    "user_intent": ai_analysis.get("user_intent", ""),
                    "modules": list(set(mentioned_modules + ai_analysis.get("specific_modules", []))),
                    "requires_demo": ai_analysis.get("requires_demo", False),
                    "urgency": ai_analysis.get("urgency", "medium"),
                }
            except json.JSONDecodeError:
                return self._create_fallback_analysis(message, query_type, mentioned_modules)

        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            return self._create_fallback_analysis(message, query_type, mentioned_modules)

    def _create_fallback_analysis(self, message: str, query_type: str, modules: list[str]) -> dict[str, Any]:
        """Create fallback analysis without AI."""
        return {
            "query_type": query_type,
            "user_intent": "Consulta sobre Excelencia ERP",
            "modules": modules,
            "requires_demo": "demo" in message.lower(),
            "urgency": "medium",
        }

    async def _search_knowledge_base(self, query: str) -> str:
        """Search knowledge base for relevant corporate information."""
        if not self.use_rag:
            return ""

        try:
            # Lazy import to avoid circular dependency
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

                context_parts = ["\n## INFORMACIÓN CORPORATIVA RELEVANTE (Knowledge Base):"]
                for i, result in enumerate(results, 1):
                    context_parts.append(f"\n### {i}. {result.get('title', 'Sin título')}")
                    content = result.get("content", "")
                    content_preview = content[:200] + "..." if len(content) > 200 else content
                    context_parts.append(f"{content_preview}")
                    doc_type = result.get("document_type", "")
                    if doc_type:
                        context_parts.append(f"*Tipo: {doc_type}*")

                return "\n".join(context_parts)

        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}")
            return ""

    async def _generate_response(
        self, user_message: str, query_analysis: dict[str, Any], _state_dict: dict[str, Any]
    ) -> str:
        """Generate response based on query analysis."""
        query_type = query_analysis.get("query_type", "general")
        mentioned_modules = query_analysis.get("modules", [])

        # Get modules from database
        modules = await self._get_modules()

        # Search knowledge base
        rag_context = await self._search_knowledge_base(user_message)

        # Prepare module context from DB
        modules_context = ""
        if mentioned_modules:
            modules_context = "\n\nMÓDULOS RELEVANTES:\n"
            for module_code in mentioned_modules[:3]:
                module_info = modules.get(module_code)
                if module_info:
                    modules_context += f"\n**{module_info['name']}**\n"
                    modules_context += f"- {module_info['description']}\n"
                    features = module_info.get("features", [])
                    if features:
                        modules_context += f"- Características: {', '.join(features[:3])}\n"
                    modules_context += f"- Target: {module_info.get('target', 'N/A')}\n"

        # Build dynamic modules list for prompt
        modules_list = "\n".join(
            f"{i}. **{info['name']}** - {info['description'][:50]}..."
            for i, (_, info) in enumerate(list(modules.items())[:6], 1)
        )

        # Generate response with AI
        response_prompt = f"""Eres un asistente especializado en el ERP Excelencia.

## CONSULTA DEL USUARIO:
"{user_message}"

## ANÁLISIS:
- Tipo de consulta: {query_type}
- Intención: {query_analysis.get("user_intent", "N/A")}
- Requiere demo: {query_analysis.get("requires_demo", False)}
{modules_context}
{rag_context}

## INFORMACIÓN GENERAL SOBRE EXCELENCIA:
Excelencia es un ERP modular especializado en diferentes verticales de negocio.

Principales módulos disponibles:
{modules_list}

## INSTRUCCIONES:
1. Responde de manera amigable y profesional
2. Si hay información en Knowledge Base, úsala como fuente principal
3. Usa máximo 6-7 líneas
4. Usa 1-2 emojis apropiados
5. NO inventes información

Genera tu respuesta ahora:"""

        try:
            llm = self.ollama.get_llm(temperature=self.temperature, model=self.model)
            response = await llm.ainvoke(response_prompt)

            if hasattr(response, "content"):
                content = response.content
                if isinstance(content, str):
                    return content.strip()
                elif isinstance(content, list):
                    return " ".join(str(item) for item in content).strip()
                else:
                    return str(content).strip()
            else:
                return str(response).strip()

        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return self._generate_fallback_response(query_type, mentioned_modules, modules)

    def _generate_fallback_response(
        self, query_type: str, mentioned_modules: list[str], all_modules: dict[str, dict[str, Any]]
    ) -> str:
        """Generate fallback response without AI using cached modules."""
        if query_type == "demo":
            # Build dynamic demo list
            demo_list = "\n".join(
                f"- {info['name']}" for _, info in list(all_modules.items())[:4]
            )
            return (
                f"¡Hola! 👋 Con gusto te puedo mostrar una demo de Excelencia ERP.\n\n"
                f"Ofrecemos demostraciones personalizadas de nuestros sistemas:\n"
                f"{demo_list}\n\n"
                f"¿Sobre qué módulo te gustaría ver la demo?"
            )

        if query_type == "modules" and mentioned_modules:
            module_code = mentioned_modules[0]
            module_info = all_modules.get(module_code)
            if module_info:
                features = module_info.get("features", [])
                features_text = chr(10).join(f"- {f}" for f in features[:4]) if features else ""
                return (
                    f"**{module_info['name']}** 🏥\n\n"
                    f"{module_info['description']}\n\n"
                    f"**Características principales:**\n"
                    f"{features_text}\n\n"
                    f"Ideal para: {module_info.get('target', 'empresas')}"
                )

        if query_type == "training":
            return (
                "📚 **Capacitación Excelencia ERP**\n\n"
                "Ofrecemos capacitación completa que incluye:\n"
                "- Capacitación inicial personalizada\n"
                "- Material didáctico y manuales\n"
                "- Soporte técnico permanente\n"
                "- Actualizaciones y mejoras continuas\n\n"
                "¿Sobre qué módulo necesitas capacitación?"
            )

        if query_type == "support":
            return (
                "🛠️ **Soporte Técnico Excelencia**\n\n"
                "Contamos con soporte técnico completo:\n"
                "- Soporte telefónico y por email\n"
                "- Asistencia remota\n"
                "- Actualizaciones automáticas\n"
                "- Mesa de ayuda especializada\n\n"
                "¿En qué podemos ayudarte?"
            )

        # Default general response using dynamic modules
        module_lines = []
        for _, info in list(all_modules.items())[:6]:
            module_lines.append(f"• {info['name']}")

        modules_text = "\n".join(module_lines) if module_lines else "Múltiples soluciones disponibles"

        return (
            f"¡Hola! 👋 **Excelencia ERP** es un sistema modular especializado.\n\n"
            f"**Principales soluciones:**\n"
            f"{modules_text}\n\n"
            f"¿Sobre qué módulo te gustaría saber más?"
        )

    async def _generate_error_response(self) -> str:
        """Generate friendly error response."""
        return (
            "Disculpa, tuve un inconveniente procesando tu consulta sobre Excelencia. "
            "¿Podrías reformular tu pregunta? Puedo ayudarte con información sobre:\n"
            "- Demos y presentaciones\n"
            "- Módulos y funcionalidades\n"
            "- Capacitación y soporte\n"
            "- Productos y soluciones"
        )


# Alias for backward compatibility
ExcelenciaAgent = ExcelenciaNode
