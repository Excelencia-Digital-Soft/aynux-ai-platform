"""
Support response generator.

Generates support responses using RAG and LLM.
"""

import logging
from typing import Any

from app.integrations.llm import OllamaLLM
from app.integrations.llm.model_provider import ModelComplexity
from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry

from .knowledge_search import KnowledgeBaseSearch

logger = logging.getLogger(__name__)

# Temperature for response generation
RESPONSE_TEMPERATURE = 0.6


class SupportResponseGenerator:
    """Generates support responses using RAG and LLM."""

    def __init__(
        self,
        ollama: OllamaLLM | None = None,
        prompt_manager: PromptManager | None = None,
        knowledge_search: KnowledgeBaseSearch | None = None,
    ):
        """Initialize the response generator."""
        self._ollama = ollama or OllamaLLM()
        self._pm = prompt_manager or PromptManager()
        self._knowledge = knowledge_search or KnowledgeBaseSearch()

    async def generate(
        self,
        message: str,
        query_analysis: dict[str, Any],
        state_dict: dict[str, Any],
    ) -> str:
        """Generate support response using RAG and LLM."""
        query_type = query_analysis.get("query_type", "general")
        module = query_analysis.get("module")
        urgency = query_analysis.get("urgency", "medium")

        # Get RAG context
        search_result = await self._knowledge.search(message, query_type)

        # CRITICAL: Check for empty RAG results before LLM call
        if search_result.is_empty():
            logger.info(f"No RAG context found for query: {message[:50]}...")
            return await self.generate_fallback(query_type, module)

        # Format conversation history
        history = self._format_history(state_dict)

        # Build prompt with validated context
        try:
            prompt = await self._pm.get_prompt(
                PromptRegistry.EXCELENCIA_SUPPORT_RESPONSE,
                variables={
                    "user_message": message,
                    "query_type": query_type,
                    "modules": module or "No especificado",
                    "urgency": urgency,
                    "rag_context": search_result.context,
                    "conversation_history": history,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to load prompt: {e}")
            return await self.generate_fallback(query_type, module)

        # Generate response
        try:
            llm = self._ollama.get_llm(
                complexity=ModelComplexity.COMPLEX,
                temperature=RESPONSE_TEMPERATURE,
            )
            response = await llm.ainvoke(prompt)

            content = self._extract_content(response)
            return OllamaLLM.clean_deepseek_response(content)

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return await self.generate_fallback(query_type, module)

    def _format_history(self, state_dict: dict[str, Any]) -> str:
        """Format conversation history for LLM context.

        Prioritizes:
        1. conversation_summary - Rolling summary generated every N turns
        2. conversation_context - Last exchange from context
        3. messages - Direct messages (fallback, rarely has history)
        """
        # Priority 1: Use conversation_summary (rolling summary from HistoryAgent)
        summary = state_dict.get("conversation_summary", "")
        if summary and summary.strip():
            return summary.strip()

        # Priority 2: Extract last exchange from conversation_context
        context = state_dict.get("conversation_context", {})
        if context:
            # Try rolling_summary first
            rolling_summary = context.get("rolling_summary", "")
            if rolling_summary:
                return rolling_summary

            # Build from last exchange
            last_user = context.get("last_user_message", "")
            last_bot = context.get("last_bot_response", "")
            if last_user or last_bot:
                parts = []
                if last_user:
                    parts.append(f"Usuario: {last_user}")
                if last_bot:
                    parts.append(f"Agente: {last_bot}")
                return "\n".join(parts)

        # Priority 3: Fallback to messages array (rarely useful)
        messages = state_dict.get("messages", [])
        if messages and len(messages) > 1:
            recent = messages[-10:]
            formatted = []
            for msg in recent:
                if hasattr(msg, "content"):
                    content = msg.content
                    msg_type = getattr(msg, "type", "")
                    if msg_type in ("human", "user"):
                        formatted.append(f"Usuario: {content}")
                    elif msg_type in ("ai", "assistant"):
                        formatted.append(f"Agente: {content}")
            return "\n".join(formatted) if formatted else ""

        return ""

    def _extract_content(self, response: Any) -> str:
        """Extract content from LLM response."""
        if hasattr(response, "content"):
            content = response.content
            if isinstance(content, str):
                return content.strip()
            elif isinstance(content, list):
                return " ".join(str(item) for item in content).strip()
            else:
                return str(content).strip()
        return str(response).strip()

    async def generate_fallback(self, query_type: str, module: str | None = None) -> str:
        """Generate fallback response using prompts or hardcoded fallback."""
        try:
            if query_type == "training":
                return await self._pm.get_prompt(
                    PromptRegistry.EXCELENCIA_SUPPORT_TRAINING_FALLBACK,
                )
            else:
                return await self._pm.get_prompt(
                    PromptRegistry.EXCELENCIA_SUPPORT_FALLBACK,
                )
        except Exception as e:
            logger.warning(f"Failed to load fallback prompt: {e}")

        module_text = f" del modulo {module}" if module else ""
        return (
            f"Soporte Tecnico Excelencia\n\n"
            f"Disculpa, no encontre informacion especifica{module_text} en este momento.\n\n"
            f"Puedes:\n"
            f"- Reformular tu pregunta con mas detalles\n"
            f"- Contactar a nuestro equipo de soporte directamente\n"
            f"- Decirme 'quiero reportar una incidencia' para crear un ticket\n\n"
            f"En que mas puedo ayudarte?"
        )
