"""
Response Enhancer.

Enhances agent responses using LLM for better customer service quality.
"""

import logging
import re
from typing import Any

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
            "es": "IMPORTANT: You MUST answer ONLY in SPANISH language. Your entire response must be in Spanish.",
            "en": "IMPORTANT: You MUST answer ONLY in ENGLISH language. Your entire response must be in English.",
            "pt": "IMPORTANT: You MUST answer ONLY in PORTUGUESE language. Your entire response must be in Portuguese.",
        }

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
            prompt = self._build_enhancement_prompt(
                original_response=original_response,
                user_message=user_message,
                language=language,
                context=context,
            )

            # Use capable model for enhancement
            llm = self.ollama.get_llm(temperature=0.7, model="deepseek-r1:7b")
            response = await llm.ainvoke(prompt)
            enhanced_response = response.content if response else None

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

    def _build_enhancement_prompt(
        self,
        original_response: str,
        user_message: str,
        language: str,
        context: dict[str, Any],
    ) -> str:
        """Build the enhancement prompt."""
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

        return f"""You are a friendly and professional customer service assistant for Aynux, an e-commerce platform.

CONTEXT:
- Customer's current question: {user_message}
- Agent's response with information: {original_response}
{f"- Customer name: {customer_name}" if customer_name else ""}
{conversation_summary if conversation_summary else ""}

YOUR TASK:
Transform the agent's response into a warm, friendly, and professional customer service message.

GUIDELINES:
1. Start with a personalized greeting if this seems to be the beginning of a conversation
2. Rephrase the information to be conversational and natural
3. Maintain ALL factual information (prices, product details, availability, etc.) exactly as provided
4. Use a warm and empathetic tone
5. Format product information clearly with bullet points or numbered lists when appropriate
6. End with an invitation for further questions or assistance
7. Keep the response concise but complete (2-4 paragraphs maximum)

IMPORTANT RULES:
- DO NOT invent or add any information not present in the original response
- DO NOT change prices, quantities, or product specifications
- DO NOT make promises or commitments not in the original response
- If the original response indicates something is not available or possible, maintain that clearly
- Use 1-2 emojis maximum and only if they enhance the message naturally

{language_instruction}

Now, provide the enhanced customer service response:"""

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
