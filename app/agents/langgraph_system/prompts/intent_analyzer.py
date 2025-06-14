import json
import logging
from typing import Any, Dict

from app.schemas import build_intent_prompt_text


def get_system_prompt() -> str:
    intent_text = build_intent_prompt_text()
    prompt = """
    Eres un experto clasificador de intenciones para un asistente de e-commerce. 
    Tu tarea es analizar el contexto y el mensaje del usuario para identificar una única intención principal.

Considera el historial de la conversación. Un mensaje como "¿y para este?" 
depende completamente de los mensajes anteriores.
Usa los datos del cliente para entender mejor su consulta.

Devuelve SIEMPRE un objeto JSON válido en una sola línea, sin explicaciones, intros, o markdown.

Estructura del JSON:
{{
"intent": "una_de_las_intenciones_validas",
"confidence": 0.0,
"reasoning": "Breve explicación de por qué elegiste esa intención."
}}

    {intent_text}

Si no estás seguro, elige "fallback" con una confidence menor a 0.7. La calidad es más importante que la velocidad.
    """

    formatted_prompt = prompt.format(
        intent_text=intent_text,
    )

    return formatted_prompt


def get_build_llm_prompt(message: str, state_dict: Dict[str, Any]) -> str:
    """Construye el prompt completo para el LLM, incluyendo contexto."""

    # Se añaden solo si tienen contenido.
    context_parts = []
    if customer_data := state_dict.get("customer_data"):
        context_parts.append(f"### Datos del Cliente\n{json.dumps(customer_data, indent=2)}")

    if conversation_data := state_dict.get("conversation_data"):
        # conversation_data es un diccionario con metadatos de la conversación, no un historial de mensajes
        # Solo incluimos la información relevante para el análisis de intención
        if isinstance(conversation_data, dict):
            context_info = []
            if channel := conversation_data.get("channel"):
                context_info.append(f"Canal: {channel}")
            if language := conversation_data.get("language"):
                context_info.append(f"Idioma: {language}")
            if context_info:
                context_parts.append(f"### Información de Contexto\n{', '.join(context_info)}")
        elif isinstance(conversation_data, dict):
            # Si es una lista de mensajes (historial real)
            try:
                formatted_history = "\n".join([
                    f"- {turn.get('role', 'unknown')}: {turn.get('content', '')}"
                    for turn in conversation_data if isinstance(turn, dict)
                ])
                if formatted_history:
                    context_parts.append(f"### Historial de la Conversación\n{formatted_history}")
            except Exception as e:
                # Ignorar errores de formateo, no es crítico
                logging.error(f"Error en la consulta: {e}")
                pass

    context_string = "\n\n".join(context_parts)

    user_prompt = f"""
{context_string}

### Mensaje Actual del Usuario
"{message}"

Basado en TODA la información anterior (datos del cliente, historial y mensaje actual), 
responde solo con el JSON de la intención.
"""
    return user_prompt.strip()