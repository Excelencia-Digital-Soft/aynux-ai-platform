import json
import logging
from typing import Any, Dict

from app.schemas import build_intent_prompt_text


def get_system_prompt() -> str:
    intent_text = build_intent_prompt_text()
    prompt = """
You are an expert intent classifier for an e-commerce assistant.
Your task is to analyze the context and user message to identify a single primary intent.

Consider conversation history. A message like "what about this one?" depends completely on previous messages.
Use customer data to better understand their query.

ALWAYS return a valid JSON object in a single line, without explanations, intros, or markdown.

JSON structure:
{{
"intent": "one_of_the_valid_intents",
"confidence": 0.0,
"reasoning": "Brief explanation of why you chose this intent."
}}

{intent_text}

If unsure, choose "fallback" with confidence < 0.7. Quality is more important than speed.
    """

    formatted_prompt = prompt.format(
        intent_text=intent_text,
    )

    return formatted_prompt


def get_build_llm_prompt(message: str, state_dict: Dict[str, Any]) -> str:
    """Build complete LLM prompt including context."""

    # Add context only if available
    context_parts = []
    if customer_data := state_dict.get("customer_data"):
        context_parts.append(f"### Customer Data\n{json.dumps(customer_data, indent=2)}")

    if conversation_data := state_dict.get("conversation_data"):
        # conversation_data is a dict with conversation metadata, not message history
        # Only include information relevant for intent analysis
        if isinstance(conversation_data, dict):
            context_info = []
            if channel := conversation_data.get("channel"):
                context_info.append(f"Channel: {channel}")
            if language := conversation_data.get("language"):
                context_info.append(f"Language: {language}")
            if context_info:
                context_parts.append(f"### Context Information\n{', '.join(context_info)}")
        elif isinstance(conversation_data, dict):
            # If it's a list of messages (actual history)
            try:
                formatted_history = "\n".join([
                    f"- {turn.get('role', 'unknown')}: {turn.get('content', '')}"
                    for turn in conversation_data if isinstance(turn, dict)
                ])
                if formatted_history:
                    context_parts.append(f"### Conversation History\n{formatted_history}")
            except Exception as e:
                # Ignore formatting errors, not critical
                logging.error(f"Error in query: {e}")
                pass

    context_string = "\n\n".join(context_parts)

    user_prompt = f"""
{context_string}

### Current User Message
"{message}"

Based on ALL the information above (customer data, history and current message), 
respond only with the intent JSON.
"""
    return user_prompt.strip()