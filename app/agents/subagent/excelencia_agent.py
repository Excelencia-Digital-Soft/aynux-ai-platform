"""
Agente especializado en consultas sobre ERP Excelencia con RAG (Retrieval-Augmented Generation)

Este agente maneja:
- Información sobre demos del sistema Excelencia
- Módulos y funcionalidades (Historia clínica, Hospitales, Sanatorios, Turnos, Hoteles, Obras sociales)
- Soporte técnico del ERP
- Capacitación y training
- Catálogo de productos verticales Excelencia
- Consultas corporativas (misión, visión, valores, casos de éxito, etc.) mediante RAG
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.config.settings import get_settings
from app.core.container import DependencyContainer
from app.database.async_db import get_async_db_context

from ..integrations.ollama_integration import OllamaIntegration
from ..utils.tracing import trace_async_method
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)
settings = get_settings()


# Información sobre los módulos y productos de Excelencia
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


class ExcelenciaAgent(BaseAgent):
    """
    Agente especializado en consultas sobre ERP Excelencia.

    Maneja consultas sobre:
    - Demos y presentaciones del sistema
    - Módulos disponibles y funcionalidades
    - Soporte técnico y capacitación
    - Productos verticales (Salud, Hoteles, etc.)
    """

    def __init__(self, ollama=None, postgres=None, config: Optional[Dict[str, Any]] = None):
        super().__init__("excelencia_agent", config or {}, ollama=ollama, postgres=postgres)

        # Configuración específica del agente
        self.ollama = ollama or OllamaIntegration()
        self.model = self.config.get("model", "llama3.1")
        self.temperature = self.config.get("temperature", 0.7)
        self.max_response_length = self.config.get("max_response_length", 500)

        # RAG configuration
        self.use_rag = getattr(settings, "KNOWLEDGE_BASE_ENABLED", True)
        self.rag_max_results = 3  # Number of knowledge base results to retrieve

        # Tipos de consultas que puede manejar
        self.query_types = {
            "demo": ["demo", "demostración", "prueba", "presentación", "mostrar"],
            "modules": ["módulo", "funcionalidad", "características", "qué hace", "para qué sirve"],
            "training": ["capacitación", "curso", "entrenamiento", "aprender", "formación"],
            "support": ["soporte", "ayuda", "problema", "error", "consulta técnica"],
            "products": ["producto", "sistema", "software", "solución", "vertical"],
            "corporate": ["misión", "visión", "valores", "empresa", "quiénes somos", "contacto", "redes"],
            "clients": ["cliente", "caso", "éxito", "referencia", "implementación"],
            "general": ["excelencia", "erp", "información", "qué es"],
        }

        logger.info(f"ExcelenciaAgent initialized successfully (RAG enabled: {self.use_rag})")

    @trace_async_method(
        name="excelencia_agent_process",
        run_type="chain",
        metadata={"agent_type": "excelencia", "domain": "erp"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa consultas sobre Excelencia ERP.

        Args:
            message: Mensaje del usuario
            state_dict: Estado actual como diccionario

        Returns:
            Diccionario con actualizaciones para el estado
        """
        try:
            # 1. Analizar la intención específica del usuario
            query_analysis = await self._analyze_query_intent(message)

            # 2. Generar respuesta basada en el análisis
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
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in excelencia agent: {str(e)}")
            error_response = await self._generate_error_response(message)

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    async def _analyze_query_intent(self, message: str) -> Dict[str, Any]:
        """
        Analiza la intención específica de la consulta sobre Excelencia.

        Args:
            message: Mensaje del usuario

        Returns:
            Diccionario con análisis de la intención
        """
        message_lower = message.lower()

        # Detectar tipo de consulta
        query_type = "general"
        for qtype, keywords in self.query_types.items():
            if any(keyword in message_lower for keyword in keywords):
                query_type = qtype
                break

        # Detectar módulos mencionados
        mentioned_modules = []
        for module_id, module_info in EXCELENCIA_MODULES.items():
            name = str(module_info["name"])
            features = module_info["features"]
            module_keywords = [
                name.lower(),
                module_id.replace("_", " "),
            ] + [str(f).lower() for f in features[:2]]

            if any(keyword in message_lower for keyword in module_keywords):
                mentioned_modules.append(module_id)

        # Usar AI para análisis más profundo
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

            # Intentar parsear como JSON
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
                logger.warning("Could not parse AI analysis as JSON, using fallback")
                return self._create_fallback_analysis(message, query_type, mentioned_modules)

        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            return self._create_fallback_analysis(message, query_type, mentioned_modules)

    def _create_fallback_analysis(self, message: str, query_type: str, modules: List[str]) -> Dict[str, Any]:
        """Crea un análisis de fallback sin AI."""
        return {
            "query_type": query_type,
            "user_intent": "Consulta sobre Excelencia ERP",
            "modules": modules,
            "requires_demo": "demo" in message.lower(),
            "urgency": "medium",
        }

    async def _search_knowledge_base(self, query: str) -> str:
        """
        Search the knowledge base using RAG for relevant corporate information.

        Args:
            query: User's query

        Returns:
            Formatted context from knowledge base or empty string if no results
        """
        if not self.use_rag:
            return ""

        try:
            # Search knowledge base using new Clean Architecture Use Case
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

                # Format results as context
                context_parts = ["\n## INFORMACIÓN CORPORATIVA RELEVANTE (Knowledge Base):"]
                for i, result in enumerate(results, 1):
                    context_parts.append(f"\n### {i}. {result.get('title', 'Sin título')}")
                    content = result.get("content", "")
                    # Limit content to 200 characters to avoid token overflow
                    content_preview = content[:200] + "..." if len(content) > 200 else content
                    context_parts.append(f"{content_preview}")
                    # Add metadata if available
                    doc_type = result.get("document_type", "")
                    if doc_type:
                        context_parts.append(f"*Tipo: {doc_type}*")

                return "\n".join(context_parts)

        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}")
            return ""

    async def _generate_response(
        self, user_message: str, query_analysis: Dict[str, Any], _state_dict: Dict[str, Any]
    ) -> str:
        """
        Genera respuesta personalizada basada en el análisis de la consulta.

        Args:
            user_message: Mensaje original del usuario
            query_analysis: Análisis de la intención
            state_dict: Estado de la conversación

        Returns:
            Respuesta generada
        """
        query_type = query_analysis.get("query_type", "general")
        mentioned_modules = query_analysis.get("modules", [])

        # Search knowledge base for relevant information (RAG)
        rag_context = await self._search_knowledge_base(user_message)

        # Preparar contexto sobre módulos mencionados
        modules_context = ""
        if mentioned_modules:
            modules_context = "\n\nMÓDULOS RELEVANTES:\n"
            for module_id in mentioned_modules[:3]:  # Limitar a 3 módulos
                if module_id in EXCELENCIA_MODULES:
                    module_info = EXCELENCIA_MODULES[module_id]
                    modules_context += f"\n**{module_info['name']}**\n"
                    modules_context += f"- {module_info['description']}\n"
                    modules_context += f"- Características: {', '.join(module_info['features'][:3])}\n"
                    modules_context += f"- Target: {module_info['target']}\n"

        # Preparar prompt para generación de respuesta
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
Excelencia es un ERP modular especializado en diferentes verticales de negocio, con especial
 foco en el sector salud (hospitales, clínicas, obras sociales) y hotelería.

Principales módulos:
1. **Historia Clínica Electrónica** - Gestión integral de historias clínicas
2. **Sistema de Turnos Médicos** - Agendas y turnos automatizados
3. **Gestión Hospitalaria** - Administración completa de hospitales
4. **Obras Sociales** - Gestión de prestaciones y facturación
5. **Hoteles** - Software de gestión hotelera completo
6. **Farmacias** - Sistema especializado para farmacias

## INSTRUCCIONES:
1. Responde de manera amigable y profesional
2. **IMPORTANTE**: Si hay información en la Knowledge Base (sección "INFORMACIÓN CORPORATIVA RELEVANTE"),
   úsala como fuente principal y prioritaria
3. Si pregunta sobre demos: Menciona que pueden solicitar una demo personalizada
4. Si pregunta sobre capacitación: Indica que ofrecen capacitación completa y soporte
5. Si pregunta sobre un módulo específico: Detalla sus características principales
6. Si pregunta sobre productos: Enumera los módulos relevantes
7. Si pregunta sobre misión, visión, valores, contacto, casos de éxito: Usa la información de Knowledge Base
8. Usa máximo 6-7 líneas
9. Usa 1-2 emojis apropiados
10. Si es una consulta general, haz un overview breve
11. NO inventes información, usa solo lo que está en el contexto proporcionado

Genera tu respuesta ahora:"""

        try:
            llm = self.ollama.get_llm(temperature=self.temperature, model=self.model)
            response = await llm.ainvoke(response_prompt)

            # Extraer contenido de la respuesta
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
            return self._generate_fallback_response(user_message, query_type, mentioned_modules)

    def _generate_fallback_response(self, _message: str, query_type: str, modules: List[str]) -> str:
        """
        Genera respuesta de fallback sin AI.

        Args:
            _message: Mensaje del usuario (no utilizado actualmente)
            query_type: Tipo de consulta detectado
            modules: Módulos mencionados

        Returns:
            Respuesta de fallback
        """
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

        # Respuesta general sobre Excelencia (fallback por defecto)
        return (
            "¡Hola! 👋 **Excelencia ERP** es un sistema modular especializado en diferentes verticales.\n\n"
            "**Principales soluciones:**\n"
            "🏥 Salud: Historia Clínica, Hospitales, Turnos, Obras Sociales\n"
            "🏨 Hotelería: Gestión completa de hoteles y alojamientos\n"
            "💊 Farmacias: Sistema especializado para farmacias\n\n"
            "¿Sobre qué módulo te gustaría saber más?"
        )

    async def _generate_error_response(self, _message: str) -> str:
        """Genera respuesta amigable para errores.

        Args:
            _message: Mensaje del usuario (no utilizado actualmente)
        """
        return (
            "Disculpa, tuve un inconveniente procesando tu consulta sobre Excelencia. "
            "¿Podrías reformular tu pregunta? Puedo ayudarte con información sobre:\n"
            "- Demos y presentaciones\n"
            "- Módulos y funcionalidades\n"
            "- Capacitación y soporte\n"
            "- Productos y soluciones"
        )
