"""
Response Enhancer.

Enhances agent responses using LLM for better customer service quality.
"""

import logging
import re
from typing import Any

from app.integrations.llm.model_provider import ModelComplexity
from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry

logger = logging.getLogger(__name__)


class ResponseEnhancer:
    """
    Enhances agent responses using LLM.

    Responsibilities:
    - Improve response tone and clarity
    - Add customer-friendly formatting
    - Maintain factual accuracy
    - Support multiple languages
    """

    def __init__(self, ollama=None):
        """
        Initialize the response enhancer.

        Args:
            ollama: Ollama LLM instance
        """
        self.ollama = ollama
        self._language_instructions = {
            "es": "IMPORTANT: You MUST answer ONLY in SPANISH language.",
            "en": "IMPORTANT: You MUST answer ONLY in ENGLISH language.",
            "pt": "IMPORTANT: You MUST answer ONLY in PORTUGUESE language.",
        }

        # Initialize PromptManager for YAML-based prompts
        self.prompt_manager = PromptManager()

    async def enhance(
        self,
        original_response: str,
        user_message: str,
        language: str,
        context: dict[str, Any],
    ) -> str | None:
        """
        Enhance a response using LLM.

        Args:
            original_response: Original agent response
            user_message: User's message
            language: Detected language code
            context: Conversation context

        Returns:
            Enhanced response or None if enhancement fails
        """
        if not self.ollama:
            return None

        try:
            prompt = await self._build_enhancement_prompt(
                original_response=original_response,
                user_message=user_message,
                language=language,
                context=context,
            )

            # Use SIMPLE model for faster enhancement
            logger.info("ResponseEnhancer: Getting LLM for enhancement...")
            llm = self.ollama.get_llm(complexity=ModelComplexity.SIMPLE, temperature=0.7)
            logger.info("ResponseEnhancer: Calling ainvoke...")
            response = await llm.ainvoke(prompt)
            logger.info(f"ResponseEnhancer: ainvoke completed, response type: {type(response)}")
            enhanced_response = response.content if response else None
            resp_len = len(enhanced_response) if enhanced_response else 0
            logger.info(f"ResponseEnhancer: enhanced_response length: {resp_len}")

            if enhanced_response:
                enhanced_response = self._clean_response(enhanced_response)

                if len(enhanced_response) > 20:
                    logger.info(f"Response enhanced successfully for language: {language}")
                    return enhanced_response
                else:
                    logger.warning(f"Enhanced response too short: {len(enhanced_response)} chars")
                    return None

            return None

        except Exception as e:
            logger.error(f"Error enhancing response with Ollama: {str(e)}")
            return None

    async def _build_enhancement_prompt(
        self,
        original_response: str,
        user_message: str,
        language: str,
        context: dict[str, Any],
    ) -> str:
        """Build the enhancement prompt using YAML."""
        language_instruction = self._language_instructions.get(
            language,
            self._language_instructions["es"],
        )

        # Get customer name from context
        customer_name = ""
        if context.get("customer_data"):
            customer_data = context["customer_data"]
            if isinstance(customer_data, dict):
                customer_name = customer_data.get("name", "")

        # Build conversation summary
        conversation_summary = self._build_conversation_summary(context)

        # Build customer name section
        customer_name_section = f"- Customer name: {customer_name}" if customer_name else ""

        try:
            return await self.prompt_manager.get_prompt(
                PromptRegistry.AGENTS_SUPERVISOR_ENHANCEMENT,
                variables={
                    "user_message": user_message,
                    "original_response": original_response,
                    "customer_name_section": customer_name_section,
                    "conversation_summary": conversation_summary,
                    "language_instruction": language_instruction,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to load YAML prompt: {e}")
            # Fallback to hardcoded prompt
            return (
                "You are a customer service assistant. Transform this response:\n"
                f'Original: "{original_response}"\n'
                f'For question: "{user_message}"\n'
                f"{language_instruction}\n"
                "Make it warm and professional."
            )

    def _build_conversation_summary(self, context: dict[str, Any]) -> str:
        """Build a summary of recent conversation."""
        messages = context.get("messages", [])
        if len(messages) <= 2:
            return ""

        # Include recent messages for context
        recent_messages = messages[-4:] if len(messages) > 4 else messages
        conversation_summary = "Recent conversation:\n"

        for msg in recent_messages[:-1]:  # Exclude last response being enhanced
            role = msg.get("role", "")
            content = msg.get("content", "")[:100]
            if role and content:
                conversation_summary += f"- {role}: {content}...\n"

        return conversation_summary

    def _clean_response(self, response: str) -> str:
        """Clean the enhanced response."""
        response = response.strip()

        # Remove deepseek-r1 think tags
        response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL)
        response = response.strip()

        # Remove common prefixes
        prefixes_to_remove = [
            "Enhanced response:",
            "Here's the enhanced response:",
            "Enhanced customer service response:",
            "Response:",
        ]
        for prefix in prefixes_to_remove:
            if response.lower().startswith(prefix.lower()):
                response = response[len(prefix):].strip()

        return response
