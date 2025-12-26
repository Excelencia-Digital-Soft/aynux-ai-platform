"""
Excelencia Node - Main node for Software Excelencia queries.

Migrated from app/agents/subagent/excelencia_agent.py
Handles information about demos, modules, support, training and corporate queries via RAG.

Software catalog is loaded from company_knowledge table (document_type: software_catalog).

Optimizations:
- Uses SIMPLE model for intent analysis (fast)
- Uses COMPLEX model for response generation (quality)
- Automatic cleaning of deepseek-r1 <think> tags
"""

import logging
import time
from typing import Any

from app.config.settings import get_settings
from app.utils.json_extractor import extract_json_from_text
from app.core.agents import BaseAgent
from app.core.utils.tracing import trace_async_method
from app.database.async_db import get_async_db_context
from app.integrations.llm import OllamaLLM
from app.integrations.llm.model_provider import ModelComplexity

logger = logging.getLogger(__name__)
settings = get_settings()

# Temperature settings for ExcelenciaNode
INTENT_ANALYSIS_TEMPERATURE = 0.3  # Lower for deterministic JSON parsing
RESPONSE_GENERATION_TEMPERATURE = 0.7  # Higher for creative responses


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
    Node for Software Excelencia queries.

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
        # Support ticket creation triggers
        "incident": ["reportar", "incidencia", "levantar ticket", "falla grave", "bug", "no funciona", "se cayó"],
        "feedback": ["sugerencia", "comentario", "opinión", "feedback", "mejorar", "propuesta"],
    }

    # Document types to search for support queries
    SUPPORT_DOCUMENT_TYPES = [
        "support_faq",
        "support_guide",
        "support_contact",
        "support_training",
        "support_module",
        "faq",  # Fallback to general FAQ
    ]

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

        # RAG metrics for last search (exposed to frontend)
        self._last_rag_metrics: dict[str, Any] | None = None

        logger.info(f"ExcelenciaNode initialized (RAG enabled: {self.use_rag})")

    async def _get_modules(self) -> dict[str, dict[str, Any]]:
        """
        Get software catalog from company_knowledge table with caching.

        Returns:
            Dict of module_code -> module_info
        """
        if self._modules_cache is not None:
            return self._modules_cache

        try:
            from app.core.container import DependencyContainer

            async with get_async_db_context() as db:
                container = DependencyContainer()
                # Use knowledge search to get software_catalog items
                use_case = container.create_search_knowledge_use_case(db)
                results = await use_case.execute(
                    query="software productos módulos sistemas soluciones",
                    max_results=20,
                    document_type="software_catalog",
                    search_strategy="pgvector_primary",
                )

                # Convert to modules dict format
                self._modules_cache = {}
                for item in results:
                    # Use first 8 chars of id as code
                    code = item.get("id", "")[:8].upper() if item.get("id") else f"MOD-{len(self._modules_cache)+1:03d}"
                    self._modules_cache[code] = {
                        "name": item.get("title", ""),
                        "description": item.get("content", "")[:300],
                        "features": item.get("tags", []),
                        "target": item.get("category", "general"),
                    }

                logger.info(f"Loaded {len(self._modules_cache)} software products from company_knowledge")
                return self._modules_cache

        except Exception as e:
            logger.warning(f"Failed to load modules from company_knowledge: {e}, using fallback")
            self._modules_cache = _FALLBACK_MODULES.copy()
            return self._modules_cache

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

            # Analyze query intent
            query_analysis = await self._analyze_query_intent(message)
            logger.info(f"ExcelenciaNode query_analysis done: {query_analysis.get('query_type')}")

            # Generate response
            response_text = await self._generate_response(message, query_analysis, state_dict)
            logger.info(f"ExcelenciaNode response generated: {len(response_text)} chars")

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
                "mentioned_modules": query_analysis.get("modules", []),
                "requires_demo": query_analysis.get("requires_demo", False),
                "is_complete": True,
                # RAG metrics for frontend visualization
                "rag_metrics": self._last_rag_metrics,
            }
            logger.info(f"ExcelenciaNode._process_internal DONE, returning result (RAG: {self._last_rag_metrics})")
            return result

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
            prompt = f"""Analiza la siguiente consulta sobre el Software Excelencia:

"{message}"

Responde SOLO con un objeto JSON válido. Los valores posibles son:
- query_type: elegir UNO de estos valores exactos: "demo", "modules", "training", "support", "products", "general"
- user_intent: texto breve describiendo lo que busca el usuario
- specific_modules: lista de módulos mencionados (puede estar vacía)
- requires_demo: true o false (booleano, no texto)
- urgency: "low", "medium" o "high"

Ejemplo de respuesta válida:
{{"query_type": "support", "user_intent": "consulta sobre facturación", "specific_modules": [], "requires_demo": false, "urgency": "medium"}}

Responde SOLO con el JSON, sin explicaciones ni texto adicional."""

            logger.info("ExcelenciaNode: Getting SIMPLE LLM for intent analysis...")
            llm = self.ollama.get_llm(
                complexity=ModelComplexity.SIMPLE,
                temperature=INTENT_ANALYSIS_TEMPERATURE,
            )
            logger.info("ExcelenciaNode: Calling LLM.ainvoke for intent analysis...")
            response = await llm.ainvoke(prompt)
            logger.info(f"ExcelenciaNode: LLM response received, type: {type(response)}")

            response_text = response.content if isinstance(response.content, str) else str(response.content)
            logger.info(f"ExcelenciaNode: Parsing JSON response: {response_text[:100]}...")

            # Use robust JSON extractor that handles <think> tags, markdown, and Python booleans
            ai_analysis = extract_json_from_text(
                response_text,
                required_keys=["query_type"],
                default=None,
            )

            if not ai_analysis:
                logger.warning("ExcelenciaNode: JSON extraction failed, using fallback")
                return self._create_fallback_analysis(message, query_type, mentioned_modules)

            logger.info(f"ExcelenciaNode: Intent analysis complete: {ai_analysis.get('query_type')}")
            return {
                "query_type": ai_analysis.get("query_type", query_type),
                "user_intent": ai_analysis.get("user_intent", ""),
                "modules": list(set(mentioned_modules + ai_analysis.get("specific_modules", []))),
                "requires_demo": ai_analysis.get("requires_demo", False),
                "urgency": ai_analysis.get("urgency", "medium"),
            }

        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            return self._create_fallback_analysis(message, query_type, mentioned_modules)

    def _create_fallback_analysis(self, message: str, query_type: str, modules: list[str]) -> dict[str, Any]:
        """Create fallback analysis without AI."""
        return {
            "query_type": query_type,
            "user_intent": "Consulta sobre Excelencia Software",
            "modules": modules,
            "requires_demo": "demo" in message.lower(),
            "urgency": "medium",
        }

    async def _search_knowledge_base(self, query: str) -> str:
        """Search knowledge base for relevant corporate information."""
        # Reset RAG metrics
        self._last_rag_metrics = {"used": False, "query": query}

        if not self.use_rag:
            return ""

        try:
            # Lazy import to avoid circular dependency
            from app.core.container import DependencyContainer

            start_time = time.time()

            async with get_async_db_context() as db:
                container = DependencyContainer()
                use_case = container.create_search_knowledge_use_case(db)
                results = await use_case.execute(
                    query=query,
                    max_results=self.rag_max_results,
                    search_strategy="pgvector_primary",
                )

                duration_ms = int((time.time() - start_time) * 1000)

                # Capture RAG metrics
                self._last_rag_metrics = {
                    "used": True,
                    "query": query,
                    "results_count": len(results) if results else 0,
                    "duration_ms": duration_ms,
                    "sources": [r.get("title", "")[:50] for r in results[:5]] if results else [],
                }
                logger.info(f"RAG search completed: {len(results) if results else 0} results in {duration_ms}ms")

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
            self._last_rag_metrics["error"] = str(e)
            return ""

    async def _search_support_knowledge(
        self,
        query: str,
        query_type: str,
        mentioned_modules: list[str] | None = None,
    ) -> str:
        """
        Search knowledge base for support-specific content.

        Filters by support document types and optionally by module tags.

        Args:
            query: User's support query
            query_type: Detected query type (support, training, etc.)
            mentioned_modules: List of mentioned module codes for tag filtering

        Returns:
            Formatted RAG context string or empty string
        """
        # Reset RAG metrics
        self._last_rag_metrics = {"used": False, "query": query}

        if not self.use_rag:
            return ""

        try:
            from app.core.container import DependencyContainer

            start_time = time.time()

            # Determine which document types to search based on query type
            doc_types_to_search = []
            if query_type == "training":
                doc_types_to_search = ["support_training", "faq"]
            elif query_type == "support":
                doc_types_to_search = ["support_faq", "support_guide", "support_contact"]
            else:
                doc_types_to_search = self.SUPPORT_DOCUMENT_TYPES

            async with get_async_db_context() as db:
                container = DependencyContainer()
                use_case = container.create_search_knowledge_use_case(db)

                all_results = []
                # Search each support document type
                for doc_type in doc_types_to_search[:3]:  # Limit to 3 types
                    try:
                        results = await use_case.execute(
                            query=query,
                            max_results=2,
                            document_type=doc_type,
                            search_strategy="pgvector_primary",
                        )
                        all_results.extend(results)
                    except Exception as doc_e:
                        logger.warning(f"Error searching {doc_type}: {doc_e}")
                        continue

                if not all_results:
                    # Fallback to general search
                    all_results = await use_case.execute(
                        query=query,
                        max_results=self.rag_max_results,
                        search_strategy="pgvector_primary",
                    )

                duration_ms = int((time.time() - start_time) * 1000)

                # Capture RAG metrics
                unique_results = []
                seen_ids = set()
                for r in all_results:
                    rid = r.get("id", "")
                    if rid not in seen_ids:
                        seen_ids.add(rid)
                        unique_results.append(r)

                self._last_rag_metrics = {
                    "used": True,
                    "query": query,
                    "results_count": len(unique_results),
                    "duration_ms": duration_ms,
                    "sources": [r.get("title", "")[:50] for r in unique_results[:5]],
                }
                logger.info(f"Support RAG search completed: {len(unique_results)} results in {duration_ms}ms")

                if not all_results:
                    return ""

                # Format results
                context_parts = ["\n## INFORMACION DE SOPORTE (Knowledge Base):"]
                for result in unique_results[:self.rag_max_results]:
                    title = result.get("title", "Sin titulo")
                    content = result.get("content", "")
                    content_preview = content[:300] + "..." if len(content) > 300 else content
                    doc_type = result.get("document_type", "")

                    context_parts.append(f"\n### {title}")
                    context_parts.append(content_preview)
                    if doc_type:
                        context_parts.append(f"*Tipo: {doc_type}*")

                return "\n".join(context_parts)

        except Exception as e:
            logger.error(f"Error searching support knowledge: {e}")
            self._last_rag_metrics["error"] = str(e)
            return ""

    async def _create_support_ticket(
        self,
        user_phone: str,
        ticket_type: str,
        description: str,
        category: str | None = None,
        module: str | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a support ticket from user's chat message.

        Args:
            user_phone: WhatsApp phone number
            ticket_type: Type of ticket (incident, feedback)
            description: Full description from user message
            category: Optional category
            module: Optional affected module
            conversation_id: Optional conversation link

        Returns:
            Dictionary with ticket info (id, status, etc.)
        """
        try:
            from app.core.container import DependencyContainer

            async with get_async_db_context() as db:
                container = DependencyContainer()
                use_case = container.create_support_ticket_use_case(db)
                return await use_case.execute(
                    user_phone=user_phone,
                    ticket_type=ticket_type,
                    description=description,
                    category=category,
                    module=module,
                    conversation_id=conversation_id,
                )

        except Exception as e:
            logger.error(f"Error creating support ticket: {e}")
            # Return minimal info so we can still show a message
            return {
                "id": "error",
                "ticket_id_short": "ERROR",
                "status": "failed",
                "error": str(e),
            }

    def _generate_ticket_confirmation(self, ticket: dict[str, Any], ticket_type: str) -> str:
        """
        Generate confirmation message for created ticket.

        Args:
            ticket: Ticket info dict from use case
            ticket_type: Type of ticket (incident, feedback)

        Returns:
            Formatted confirmation message
        """
        ticket_id = ticket.get("ticket_id_short", ticket.get("id", "")[:8].upper())
        status = ticket.get("status", "open")

        if status == "failed":
            return (
                "Lo siento, hubo un problema al registrar tu solicitud. "
                "Por favor, contacta directamente a soporte tecnico o intenta nuevamente. "
                "¿Hay algo mas en lo que pueda ayudarte?"
            )

        if ticket_type == "incident":
            category = ticket.get("category", "general")
            return (
                f"🎫 **Incidencia Registrada**\n\n"
                f"Tu reporte ha sido creado con el folio: **{ticket_id}**\n\n"
                f"- Categoria: {category}\n"
                f"- Estado: Abierto\n\n"
                f"Nuestro equipo de soporte lo revisara y te contactara pronto.\n"
                f"¿Hay algo mas en lo que pueda ayudarte?"
            )
        else:  # feedback
            return (
                f"💬 **Gracias por tu Feedback**\n\n"
                f"Tu comentario ha sido registrado (Ref: {ticket_id}).\n\n"
                f"Valoramos mucho tu opinion para mejorar nuestros servicios.\n"
                f"¿Hay algo mas que quieras compartir?"
            )

    async def _generate_response(
        self, user_message: str, query_analysis: dict[str, Any], state_dict: dict[str, Any]
    ) -> str:
        """Generate response based on query analysis."""
        query_type = query_analysis.get("query_type", "general")
        mentioned_modules = query_analysis.get("modules", [])

        # === HANDLE INCIDENT/FEEDBACK TICKET CREATION ===
        if query_type in ("incident", "feedback"):
            user_phone = state_dict.get("user_phone", state_dict.get("sender", "unknown"))
            conversation_id = state_dict.get("conversation_id")
            module = mentioned_modules[0] if mentioned_modules else None

            ticket = await self._create_support_ticket(
                user_phone=user_phone,
                ticket_type=query_type,
                description=user_message,
                module=module,
                conversation_id=conversation_id,
            )

            return self._generate_ticket_confirmation(ticket, query_type)

        # Get modules from database
        modules = await self._get_modules()

        # === USE SUPPORT-SPECIFIC RAG FOR SUPPORT/TRAINING QUERIES ===
        if query_type in ("support", "training"):
            rag_context = await self._search_support_knowledge(
                user_message, query_type, mentioned_modules
            )
        else:
            # Use general knowledge base search for other query types
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
        response_prompt = f"""Eres un asistente especializado en el Software Excelencia.

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
            logger.info("ExcelenciaNode: Getting COMPLEX LLM for response generation...")
            # Use COMPLEX model for quality responses (deepseek-r1:7b)
            llm = self.ollama.get_llm(
                complexity=ModelComplexity.COMPLEX,
                temperature=RESPONSE_GENERATION_TEMPERATURE,
            )
            logger.info("ExcelenciaNode: Calling LLM.ainvoke for response generation...")
            response = await llm.ainvoke(response_prompt)
            logger.info(f"ExcelenciaNode: LLM response generation completed, type: {type(response)}")

            if hasattr(response, "content"):
                content = response.content
                if isinstance(content, str):
                    result = content.strip()
                elif isinstance(content, list):
                    result = " ".join(str(item) for item in content).strip()
                else:
                    result = str(content).strip()

                # Clean deepseek-r1 <think> tags from response
                result = OllamaLLM.clean_deepseek_response(result)
                logger.info(f"ExcelenciaNode: Returning response ({len(result)} chars)")
                return result
            else:
                result = str(response).strip()
                # Clean deepseek-r1 <think> tags from response
                result = OllamaLLM.clean_deepseek_response(result)
                logger.info(f"ExcelenciaNode: Returning raw response ({len(result)} chars)")
                return result

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
                f"¡Hola! 👋 Con gusto te puedo mostrar una demo de Excelencia Software.\n\n"
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
            # Generic fallback - encourage user to try again or get more details
            return (
                "📚 **Capacitacion**\n\n"
                "Para informacion sobre capacitaciones, te recomendamos:\n"
                "- Contactar a tu ejecutivo de cuenta\n"
                "- Visitar el portal de capacitaciones\n"
                "- Solicitar una sesion personalizada\n\n"
                "¿Sobre que modulo necesitas capacitacion?"
            )

        if query_type == "support":
            # Generic fallback - suggest creating a ticket
            return (
                "🛠️ **Soporte Tecnico**\n\n"
                "No encontre informacion especifica sobre tu consulta.\n\n"
                "Puedes:\n"
                "- Reformular tu pregunta con mas detalles\n"
                "- Decir 'quiero reportar una incidencia' para crear un ticket\n"
                "- Contactar a soporte tecnico directamente\n\n"
                "¿En que mas puedo ayudarte?"
            )

        # Default general response using dynamic modules
        module_lines = []
        for _, info in list(all_modules.items())[:6]:
            module_lines.append(f"• {info['name']}")

        modules_text = "\n".join(module_lines) if module_lines else "Múltiples soluciones disponibles"

        return (
            f"¡Hola! 👋 **Excelencia Software** es un sistema modular especializado.\n\n"
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
