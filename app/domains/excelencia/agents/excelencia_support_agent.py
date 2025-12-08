"""
Excelencia Support Agent - Handles Excelencia ERP software support.

This agent manages support queries for Excelencia software:
- Technical incidents and bug reports
- Module troubleshooting
- Ticket creation and tracking
- Error resolution

Uses RAG from company_knowledge for support-related information.
"""

import json
import logging
import uuid
from typing import Any

from app.config.settings import get_settings
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
RESPONSE_GENERATION_TEMPERATURE = 0.6


class ExcelenciaSupportAgent(BaseAgent):
    """
    Agent for Excelencia software support and incidents.

    Handles:
    - Technical incidents and bug reports
    - Module-specific troubleshooting
    - Ticket creation and tracking
    - Error resolution guidance
    """

    # Support query type keywords
    QUERY_TYPES = {
        "incident": [
            "incidencia",
            "reportar",
            "levantar ticket",
            "falla grave",
            "bug",
            "no funciona",
            "se cayó",
        ],
        "feedback": [
            "sugerencia",
            "comentario",
            "opinión",
            "feedback",
            "mejorar",
            "propuesta",
        ],
        "error": ["error", "fallo", "crash", "pantalla", "mensaje de error"],
        "module": ["módulo", "funcionalidad", "feature", "característica"],
        "performance": ["lento", "slow", "timeout", "demora", "tarda"],
        "configuration": ["configurar", "setup", "configure", "parámetro"],
        "data": ["datos", "sincronización", "sync", "respaldo", "backup"],
        "training": ["capacitación", "curso", "entrenamiento", "aprender"],
        "general": ["ayuda", "help", "soporte", "support", "consulta"],
    }

    # Document types to search for support queries
    SUPPORT_DOCUMENT_TYPES = [
        "support_faq",
        "support_guide",
        "support_contact",
        "support_training",
        "support_module",
        "faq",
    ]

    # Excelencia modules for context
    EXCELENCIA_MODULES = {
        "inventario": "Módulo de Inventario y Control de Stock",
        "facturacion": "Módulo de Facturación Electrónica (CFDI)",
        "contabilidad": "Módulo de Contabilidad",
        "nomina": "Módulo de Nómina",
        "compras": "Módulo de Compras",
        "ventas": "Módulo de Ventas (POS)",
        "crm": "Módulo CRM",
        "produccion": "Módulo de Producción",
        "bancos": "Módulo de Bancos y Conciliación",
        "reportes": "Módulo de Reportes y BI",
    }

    def __init__(self, ollama=None, config: dict[str, Any] | None = None):
        super().__init__("excelencia_support_agent", config or {}, ollama=ollama)

        self.ollama = ollama or OllamaLLM()
        self.model = self.config.get("model", "llama3.1")
        self.temperature = self.config.get("temperature", 0.6)
        self.max_response_length = self.config.get("max_response_length", 500)

        # RAG configuration
        self.use_rag = getattr(settings, "KNOWLEDGE_BASE_ENABLED", True)
        self.rag_max_results = 3

        # Initialize PromptManager for YAML-based prompts
        self.prompt_manager = PromptManager()

        logger.info(f"ExcelenciaSupportAgent initialized (RAG enabled: {self.use_rag})")

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
            logger.info(f"ExcelenciaSupportAgent._process_internal START: {message[:50]}...")

            # Analyze query intent
            query_analysis = await self._analyze_query_intent(message)
            query_type = query_analysis.get("query_type", "general")
            logger.info(f"ExcelenciaSupportAgent query_analysis done: {query_type}")

            # Handle incident/feedback ticket creation
            if query_type in ["incident", "feedback"]:
                response_text = await self._handle_ticket_creation(
                    message, query_type, query_analysis, state_dict
                )
            else:
                # Generate support response with RAG
                response_text = await self._generate_response(
                    message, query_analysis, state_dict
                )

            logger.info(f"ExcelenciaSupportAgent response generated: {len(response_text)} chars")

            result = {
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
            logger.info("ExcelenciaSupportAgent._process_internal DONE")
            return result

        except Exception as e:
            logger.error(f"Error in excelencia support agent: {e!s}")
            error_response = self._generate_error_response()

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    async def _analyze_query_intent(self, message: str) -> dict[str, Any]:
        """Analyze query intent for support operations."""
        message_lower = message.lower()

        # Detect query type
        query_type = "general"
        for qtype, keywords in self.QUERY_TYPES.items():
            if any(keyword in message_lower for keyword in keywords):
                query_type = qtype
                break

        # Detect mentioned module
        module = None
        for mod_key, mod_name in self.EXCELENCIA_MODULES.items():
            if mod_key in message_lower:
                module = mod_key
                break

        return {
            "query_type": query_type,
            "module": module,
            "urgency": self._detect_urgency(message_lower),
        }

    def _detect_urgency(self, message: str) -> str:
        """Detect urgency level from message."""
        high_urgency = ["urgente", "crítico", "no funciona", "se cayó", "bloqueado"]
        if any(word in message for word in high_urgency):
            return "high"
        return "medium"

    async def _handle_ticket_creation(
        self,
        message: str,
        ticket_type: str,
        query_analysis: dict[str, Any],
        state_dict: dict[str, Any],
    ) -> str:
        """Handle ticket creation for incidents and feedback."""
        try:
            from app.core.container import DependencyContainer

            async with get_async_db_context() as db:
                container = DependencyContainer()
                use_case = container.create_support_ticket_use_case(db)

                ticket = await use_case.execute(
                    user_phone=state_dict.get("user_phone", "unknown"),
                    ticket_type=ticket_type,
                    description=message,
                    category=self._infer_category(message, ticket_type),
                    module=query_analysis.get("module"),
                    conversation_id=state_dict.get("conversation_id"),
                )

                return self._generate_ticket_confirmation(ticket, ticket_type)

        except Exception as e:
            logger.error(f"Error creating support ticket: {e}")
            return self._generate_ticket_error_response()

    def _infer_category(self, description: str, ticket_type: str) -> str:
        """Infer ticket category from description."""
        description_lower = description.lower()

        if ticket_type == "feedback":
            return "sugerencias"

        # Technical keywords
        if any(w in description_lower for w in ["error", "fallo", "bug", "crash", "no funciona"]):
            return "tecnico"

        # Billing keywords
        if any(w in description_lower for w in ["factura", "cfdi", "timbrado", "sat"]):
            return "facturacion"

        # Training keywords
        if any(w in description_lower for w in ["capacitación", "curso", "entrenamiento"]):
            return "capacitacion"

        return "general"

    def _generate_ticket_confirmation(self, ticket: dict, ticket_type: str) -> str:
        """Generate confirmation message for created ticket."""
        ticket_id = ticket.get("ticket_id_short", ticket.get("id", "")[:8].upper())
        status = ticket.get("status", "open")
        category = ticket.get("category", "general")

        if ticket_type == "incident":
            status_text = "Abierto" if status == "open" else status.capitalize()
            return (
                f"🎫 **Incidencia Registrada**\n\n"
                f"Tu reporte ha sido creado con el folio: **{ticket_id}**\n\n"
                f"**Resumen:**\n"
                f"- Categoría: {category}\n"
                f"- Estado: {status_text}\n\n"
                f"Nuestro equipo de soporte lo revisará y te contactará pronto.\n\n"
                f"¿Hay algo más en lo que pueda ayudarte?"
            )
        else:  # feedback
            return (
                f"💬 **Gracias por tu Feedback**\n\n"
                f"Tu comentario ha sido registrado (Ref: {ticket_id}).\n\n"
                f"Tu opinión es muy valiosa para nosotros y nos ayuda a mejorar "
                f"continuamente nuestros servicios y productos.\n\n"
                f"¿Hay algo más que quieras compartir?"
            )

    def _generate_ticket_error_response(self) -> str:
        """Generate error response when ticket creation fails."""
        return (
            "🛠️ Disculpa, hubo un problema al registrar tu incidencia.\n\n"
            "Por favor, contacta directamente a soporte técnico:\n"
            "- Teléfono: 800-XXX-XXXX\n"
            "- Email: soporte@excelencia.com\n\n"
            "¿Puedo ayudarte con algo más?"
        )

    async def _search_knowledge_base(self, query: str, query_type: str) -> str:
        """Search knowledge base for support-related information."""
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

                context_parts = ["\n## INFORMACIÓN DE SOPORTE (Knowledge Base):"]
                for i, result in enumerate(results, 1):
                    context_parts.append(f"\n### {i}. {result.get('title', 'Sin título')}")
                    content = result.get("content", "")
                    content_preview = content[:300] + "..." if len(content) > 300 else content
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
        module = query_analysis.get("module")
        urgency = query_analysis.get("urgency", "medium")

        # Search knowledge base
        rag_context = await self._search_knowledge_base(user_message, query_type)

        # Build response prompt from YAML
        try:
            response_prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.EXCELENCIA_SUPPORT_RESPONSE,
                variables={
                    "user_message": user_message,
                    "query_type": query_type,
                    "modules": module or "No especificado",
                    "urgency": urgency,
                    "rag_context": rag_context,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to load YAML prompt: {e}")
            return await self._generate_fallback_response(query_type, module)

        try:
            logger.info("ExcelenciaSupportAgent: Getting LLM for response generation...")
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
            return await self._generate_fallback_response(query_type, module)

    async def _generate_fallback_response(
        self, query_type: str, module: str | None = None
    ) -> str:
        """Generate fallback response using YAML prompts or hardcoded fallback."""
        module_text = f" del módulo {module}" if module else ""

        # Try to load YAML fallback
        try:
            if query_type == "training":
                response = await self.prompt_manager.get_prompt(
                    PromptRegistry.EXCELENCIA_SUPPORT_TRAINING_FALLBACK,
                )
                return response
            else:
                response = await self.prompt_manager.get_prompt(
                    PromptRegistry.EXCELENCIA_SUPPORT_FALLBACK,
                )
                return response
        except Exception as e:
            logger.warning(f"Failed to load YAML fallback prompt: {e}")

        # Hardcoded fallback
        return (
            f"🛠️ **Soporte Técnico Excelencia**\n\n"
            f"Disculpa, no encontré información específica{module_text} en este momento.\n\n"
            f"Puedes:\n"
            f"- Reformular tu pregunta con más detalles\n"
            f"- Contactar a nuestro equipo de soporte directamente\n"
            f"- Decirme \"quiero reportar una incidencia\" para crear un ticket\n\n"
            f"¿En qué más puedo ayudarte?"
        )

    def _generate_error_response(self) -> str:
        """Generate friendly error response."""
        return (
            "Disculpa, tuve un inconveniente procesando tu consulta de soporte. "
            "¿Podrías reformular tu pregunta? Puedo ayudarte con:\n"
            "- Incidencias y problemas técnicos\n"
            "- Información de módulos\n"
            "- Capacitación y guías"
        )
