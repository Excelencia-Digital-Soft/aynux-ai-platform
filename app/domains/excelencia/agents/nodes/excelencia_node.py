"""
Excelencia Node - Main node for ERP Excelencia queries.

Migrated from app/agents/subagent/excelencia_agent.py
Handles information about demos, modules, support, training and corporate queries via RAG.
"""

import json
import logging
from typing import Any

from app.core.agents import BaseAgent
from app.integrations.llm import OllamaLLM
from app.core.utils.tracing import trace_async_method
from app.config.settings import get_settings
from app.database.async_db import get_async_db_context

logger = logging.getLogger(__name__)
settings = get_settings()


# Module information for Excelencia ERP
EXCELENCIA_MODULES = {
    "historia_clinica": {
        "name": "Historia Clínica Electrónica",
        "description": "Sistema completo de gestión de historias clínicas digitales con cumplimiento normativo",
        "features": [
            "Registro de pacientes",
            "Consultas médicas",
            "Prescripciones",
            "Informes",
            "Cumplimiento normativo",
        ],
        "target": "Hospitales, Clínicas, Centros médicos",
    },
    "turnos_medicos": {
        "name": "Sistema de Turnos Médicos",
        "description": "Gestión integral de agendas médicas y turnos de pacientes",
        "features": ["Agenda médica", "Turnos online", "Recordatorios", "Confirmaciones automáticas", "App móvil"],
        "target": "Consultorios, Centros médicos, Especialistas",
    },
    "hospitales": {
        "name": "Gestión Hospitalaria",
        "description": "Sistema integral para administración de hospitales y sanatorios",
        "features": ["Admisión", "Internación", "Quirófanos", "Farmacia", "Facturación", "Stock"],
        "target": "Hospitales, Sanatorios, Clínicas",
    },
    "obras_sociales": {
        "name": "Gestión de Obras Sociales",
        "description": "Sistema para administración de obras sociales y prepagas",
        "features": ["Afiliaciones", "Prestaciones", "Facturación", "Autorización", "Cobranzas"],
        "target": "Obras sociales, Prepagas, Mutuales",
    },
    "hoteles": {
        "name": "Sistema de Gestión Hotelera",
        "description": "Software completo para administración de hoteles y alojamientos",
        "features": ["Reservas", "Check-in/out", "Housekeeping", "POS", "Revenue Management"],
        "target": "Hoteles, Apart, Hostels, Complejos",
    },
    "farmacias": {
        "name": "Gestión de Farmacias",
        "description": "Sistema especializado para administración de farmacias",
        "features": ["Ventas", "Stock", "Recetas", "Obras sociales", "Trazabilidad"],
        "target": "Farmacias, Droguerías",
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

        logger.info(f"ExcelenciaNode initialized (RAG enabled: {self.use_rag})")

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

        # Detect mentioned modules
        mentioned_modules = []
        for module_id, module_info in EXCELENCIA_MODULES.items():
            name = str(module_info["name"]).lower()
            module_keywords = [name, module_id.replace("_", " ")]
            module_keywords.extend([str(f).lower() for f in module_info["features"][:2]])

            if any(keyword in message_lower for keyword in module_keywords):
                mentioned_modules.append(module_id)

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

        # Search knowledge base
        rag_context = await self._search_knowledge_base(user_message)

        # Prepare module context
        modules_context = ""
        if mentioned_modules:
            modules_context = "\n\nMÓDULOS RELEVANTES:\n"
            for module_id in mentioned_modules[:3]:
                if module_id in EXCELENCIA_MODULES:
                    module_info = EXCELENCIA_MODULES[module_id]
                    modules_context += f"\n**{module_info['name']}**\n"
                    modules_context += f"- {module_info['description']}\n"
                    modules_context += f"- Características: {', '.join(module_info['features'][:3])}\n"
                    modules_context += f"- Target: {module_info['target']}\n"

        # Generate response with AI
        response_prompt = f"""Eres un asistente especializado en el ERP Excelencia.

## CONSULTA DEL USUARIO:
"{user_message}"

## ANÁLISIS:
- Tipo de consulta: {query_type}
- Intención: {query_analysis.get('user_intent', 'N/A')}
- Requiere demo: {query_analysis.get('requires_demo', False)}
{modules_context}
{rag_context}

## INFORMACIÓN GENERAL SOBRE EXCELENCIA:
Excelencia es un ERP modular especializado en diferentes verticales de negocio.

Principales módulos:
1. **Historia Clínica Electrónica** - Gestión integral de historias clínicas
2. **Sistema de Turnos Médicos** - Agendas y turnos automatizados
3. **Gestión Hospitalaria** - Administración completa de hospitales
4. **Obras Sociales** - Gestión de prestaciones y facturación
5. **Hoteles** - Software de gestión hotelera completo
6. **Farmacias** - Sistema especializado para farmacias

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
            return self._generate_fallback_response(query_type, mentioned_modules)

    def _generate_fallback_response(self, query_type: str, modules: list[str]) -> str:
        """Generate fallback response without AI."""
        if query_type == "demo":
            return (
                "¡Hola! 👋 Con gusto te puedo mostrar una demo de Excelencia ERP.\n\n"
                "Ofrecemos demostraciones personalizadas de nuestros sistemas:\n"
                "- Historia Clínica Electrónica\n"
                "- Gestión Hospitalaria\n"
                "- Sistema de Turnos\n"
                "- Gestión Hotelera\n\n"
                "¿Sobre qué módulo te gustaría ver la demo?"
            )

        if query_type == "modules" and modules:
            module_id = modules[0]
            if module_id in EXCELENCIA_MODULES:
                module_info = EXCELENCIA_MODULES[module_id]
                return (
                    f"**{module_info['name']}** 🏥\n\n"
                    f"{module_info['description']}\n\n"
                    f"**Características principales:**\n"
                    f"{chr(10).join(f'- {feature}' for feature in module_info['features'][:4])}\n\n"
                    f"Ideal para: {module_info['target']}"
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

        # Default general response
        return (
            "¡Hola! 👋 **Excelencia ERP** es un sistema modular especializado en diferentes verticales.\n\n"
            "**Principales soluciones:**\n"
            "🏥 Salud: Historia Clínica, Hospitales, Turnos, Obras Sociales\n"
            "🏨 Hotelería: Gestión completa de hoteles y alojamientos\n"
            "💊 Farmacias: Sistema especializado para farmacias\n\n"
            "¿Sobre qué módulo te gustaría saber más?"
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
