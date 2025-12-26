import json
import logging
from typing import Any, Dict

from app.core.schemas import build_intent_prompt_text
from app.prompts.manager import PromptManager

# Initialize the prompt manager
prompt_manager = PromptManager()


async def get_system_prompt() -> str:
    intent_text = build_intent_prompt_text()
    
    # Load the system prompt from the YAML file
    system_prompt_template = await prompt_manager.get_prompt(
        "intent.analyzer.system",
        variables={"intent_text": intent_text}
    )
    
    return system_prompt_template


async def get_build_llm_prompt(message: str, state_dict: Dict[str, Any]) -> str:
    """Build complete LLM prompt including context."""

    # Add context only if available
    context_parts = []
    last_bot_message = ""
    previous_agent = ""

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

            # Extract follow-up detection context
            last_bot_message = conversation_data.get("last_bot_message", "")
            previous_agent = conversation_data.get("previous_agent", "")

            # Format recent messages for context
            if recent_messages := conversation_data.get("recent_messages"):
                try:
                    formatted_history = "\n".join(
                        [
                            f"- {turn.get('role', 'unknown')}: {turn.get('content', '')[:200]}"
                            for turn in recent_messages
                            if isinstance(turn, dict)
                        ]
                    )
                    if formatted_history:
                        context_parts.append(f"### Recent Conversation\n{formatted_history}")
                except Exception as e:
                    logging.error(f"Error formatting recent messages: {e}")

        elif isinstance(conversation_data, list):
            # If it's a list of messages (actual history)
            try:
                formatted_history = "\n".join(
                    [
                        f"- {turn.get('role', 'unknown')}: {turn.get('content', '')}"
                        for turn in conversation_data
                        if isinstance(turn, dict)
                    ]
                )
                if formatted_history:
                    context_parts.append(f"### Conversation History\n{formatted_history}")
            except Exception as e:
                # Ignore formatting errors, not critical
                logging.error(f"Error in query: {e}")
                pass

    context_string = "\n\n".join(context_parts)

    # Get conversation_summary from conversation_data or state_dict
    conversation_data = state_dict.get("conversation_data", {})
    conversation_summary = ""
    if isinstance(conversation_data, dict):
        conversation_summary = conversation_data.get("conversation_summary", "")
    if not conversation_summary:
        conversation_summary = state_dict.get("conversation_summary", "")

    # Load the user prompt from the YAML file
    user_prompt_template = await prompt_manager.get_prompt(
        "intent.analyzer.user",
        variables={
            "context_string": context_string,
            "message": message,
            "last_bot_message": last_bot_message or "No previous bot message",
            "previous_agent": previous_agent or "None",
            "conversation_summary": conversation_summary or "No conversation summary available",
        }
    )

    return user_prompt_template
