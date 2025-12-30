"""
Response Generation Handler

Handles LLM response generation with context building and fallbacks.
Single responsibility: generate responses for Excelencia queries.
"""

from __future__ import annotations

import logging
from typing import Any

from app.integrations.llm import ModelComplexity

from .base_handler import BaseExcelenciaHandler

logger = logging.getLogger(__name__)

# Temperature for response generation (higher for creative responses)
RESPONSE_GENERATION_TEMPERATURE = 0.7


class ResponseGenerationHandler(BaseExcelenciaHandler):
    """
    Generates responses for Excelencia queries.

    Uses LLM for AI-powered responses with fallback support.
    """

    async def generate(
        self,
        user_message: str,
        query_analysis: dict[str, Any],
        state_dict: dict[str, Any],
        modules: dict[str, dict[str, Any]],
        rag_context: str,
    ) -> str:
        """
        Generate AI response with full context.

        Args:
            user_message: Original user message
            query_analysis: Intent analysis result as dict
            state_dict: Current state (contains conversation_summary)
            modules: Available software modules
            rag_context: RAG knowledge base context

        Returns:
            Generated response text
        """
        query_type = query_analysis.get("query_type", "general")
        mentioned_modules = query_analysis.get("modules", [])

        # Build context sections
        modules_context = self._build_modules_context(mentioned_modules, modules)
        modules_list = self._build_modules_list(modules)
        conversation_context = self._build_conversation_context(state_dict)

        # Build prompt
        prompt = self._build_prompt(
            user_message=user_message,
            query_analysis=query_analysis,
            modules_context=modules_context,
            rag_context=rag_context,
            conversation_context=conversation_context,
            modules_list=modules_list,
        )

        try:
            self.logger.info("ResponseGenerationHandler: Generating with COMPLEX LLM...")
            llm = self.get_llm(
                complexity=ModelComplexity.COMPLEX,
                temperature=RESPONSE_GENERATION_TEMPERATURE,
            )
            response = await llm.ainvoke(prompt)
            result = self.extract_response_content(response)
            self.logger.info(f"ResponseGenerationHandler: Generated {len(result)} chars")
            return result

        except Exception as e:
            self.logger.error(f"Error generating AI response: {e}")
            return self.generate_fallback(query_type, mentioned_modules, modules)

    def generate_fallback(
        self,
        query_type: str,
        mentioned_modules: list[str],
        all_modules: dict[str, dict[str, Any]],
    ) -> str:
        """
        Generate fallback response without AI.

        Args:
            query_type: Detected query type
            mentioned_modules: Modules mentioned in query
            all_modules: All available modules

        Returns:
            Fallback response text
        """
        if query_type == "demo":
            demo_list = "\n".join(f"- {info['name']}" for _, info in list(all_modules.items())[:4])
            return (
                f"Hola! 👋 Con gusto te puedo mostrar una demo de Excelencia Software.\n\n"
                f"Ofrecemos demostraciones personalizadas de nuestros sistemas:\n"
                f"{demo_list}\n\n"
                f"Sobre que modulo te gustaria ver la demo?"
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
                    f"**Caracteristicas principales:**\n"
                    f"{features_text}\n\n"
                    f"Ideal para: {module_info.get('target', 'empresas')}"
                )

        if query_type == "training":
            return (
                "📚 **Capacitacion**\n\n"
                "Para informacion sobre capacitaciones, te recomendamos:\n"
                "- Contactar a tu ejecutivo de cuenta\n"
                "- Visitar el portal de capacitaciones\n"
                "- Solicitar una sesion personalizada\n\n"
                "Sobre que modulo necesitas capacitacion?"
            )

        if query_type == "support":
            return (
                "🛠️ **Soporte Tecnico**\n\n"
                "No encontre informacion especifica sobre tu consulta.\n\n"
                "Puedes:\n"
                "- Reformular tu pregunta con mas detalles\n"
                "- Decir 'quiero reportar una incidencia' para crear un ticket\n"
                "- Contactar a soporte tecnico directamente\n\n"
                "En que mas puedo ayudarte?"
            )

        # Default general response
        module_lines = [f"• {info['name']}" for _, info in list(all_modules.items())[:6]]
        modules_text = "\n".join(module_lines) if module_lines else "Multiples soluciones disponibles"

        return (
            f"Hola! 👋 **Excelencia Software** es un sistema modular especializado.\n\n"
            f"**Principales soluciones:**\n"
            f"{modules_text}\n\n"
            f"Sobre que modulo te gustaria saber mas?"
        )

    def generate_error(self) -> str:
        """Generate friendly error response."""
        return (
            "Disculpa, tuve un inconveniente procesando tu consulta sobre Excelencia. "
            "Podrias reformular tu pregunta? Puedo ayudarte con informacion sobre:\n"
            "- Demos y presentaciones\n"
            "- Modulos y funcionalidades\n"
            "- Capacitacion y soporte\n"
            "- Productos y soluciones"
        )

    def _build_modules_context(
        self, mentioned_modules: list[str], modules: dict[str, dict[str, Any]]
    ) -> str:
        """Build context for mentioned modules."""
        if not mentioned_modules:
            return ""

        context = "\n\nMODULOS RELEVANTES:\n"
        for module_code in mentioned_modules[:3]:
            module_info = modules.get(module_code)
            if module_info:
                context += f"\n**{module_info['name']}**\n"
                context += f"- {module_info['description']}\n"
                features = module_info.get("features", [])
                if features:
                    context += f"- Caracteristicas: {', '.join(features[:3])}\n"
                context += f"- Target: {module_info.get('target', 'N/A')}\n"
        return context

    def _build_modules_list(self, modules: dict[str, dict[str, Any]]) -> str:
        """Build list of available modules for prompt."""
        return "\n".join(
            f"{i}. **{info['name']}** - {info['description'][:50]}..."
            for i, (_, info) in enumerate(list(modules.items())[:6], 1)
        )

    def _build_conversation_context(self, state_dict: dict[str, Any]) -> str:
        """Build conversation context section."""
        conversation_summary = state_dict.get("conversation_summary", "")
        if not conversation_summary:
            return ""

        return f"""
## CONTEXTO DE CONVERSACION ANTERIOR:
{conversation_summary}

IMPORTANTE: Usa este contexto para entender referencias como "sus caracteristicas", "ese modulo", etc.
"""

    def _build_prompt(
        self,
        user_message: str,
        query_analysis: dict[str, Any],
        modules_context: str,
        rag_context: str,
        conversation_context: str,
        modules_list: str,
    ) -> str:
        """Build the full response generation prompt."""
        query_type = query_analysis.get("query_type", "general")
        user_intent = query_analysis.get("user_intent", "N/A")
        requires_demo = query_analysis.get("requires_demo", False)

        return f"""Eres un asistente especializado en el Software Excelencia.
{conversation_context}
## CONSULTA ACTUAL DEL USUARIO:
"{user_message}"

## ANALISIS:
- Tipo de consulta: {query_type}
- Intencion: {user_intent}
- Requiere demo: {requires_demo}
{modules_context}
{rag_context}

## INFORMACION GENERAL SOBRE EXCELENCIA:
Excelencia es un ERP modular especializado en diferentes verticales de negocio.

Principales modulos disponibles:
{modules_list}

## INSTRUCCIONES:
1. Responde de manera amigable y profesional
2. Si hay contexto de conversacion anterior, usalo para dar continuidad
3. Si hay informacion en Knowledge Base, usala como fuente principal
4. Usa maximo 6-7 lineas
5. Usa 1-2 emojis apropiados
6. NO inventes informacion

Genera tu respuesta ahora:"""
