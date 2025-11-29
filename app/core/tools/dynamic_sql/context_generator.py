"""
SQL Context Generator.

Single Responsibility: Generate embedding-ready context from SQL results.
"""

import json
import logging
from typing import Any, Dict, List

from app.integrations.llm import OllamaLLM

logger = logging.getLogger(__name__)


class SQLContextGenerator:
    """
    Generates embedding-ready context from query results.

    Single Responsibility: Transform SQL results into AI-consumable context.
    """

    def __init__(self, ollama: OllamaLLM | None = None):
        """
        Initialize context generator.

        Args:
            ollama: OllamaLLM instance for AI-powered summarization
        """
        self.ollama = ollama or OllamaLLM()

    async def generate(
        self, user_query: str, results: List[Dict[str, Any]], intent_analysis: Dict[str, Any]
    ) -> str:
        """
        Generate embedding-ready context from query results.

        Args:
            user_query: Original user query
            results: SQL query results
            intent_analysis: Intent analysis data (unused but kept for API compatibility)

        Returns:
            Contextual summary suitable for AI agents
        """
        if not results:
            return f"No se encontraron resultados para la consulta: {user_query}"

        # Summarize results for embedding
        context_prompt = f"""# CONTEXTO DE DATOS PARA AGENTE AI

CONSULTA ORIGINAL: "{user_query}"

RESULTADOS ENCONTRADOS: {len(results)} registros

DATOS RELEVANTES:
{json.dumps(results[:10], indent=2, default=str)}

RESUMEN EJECUTIVO:
Genera un resumen conciso y estructurado de estos datos que permita a un agente AI
responder de manera informativa y util. Incluye:
- Numeros clave y estadisticas
- Patrones o tendencias importantes
- Respuesta directa a la pregunta original
- Contexto adicional relevante

Respuesta en espanol, maximo 300 palabras:"""

        try:
            context_summary = await self.ollama.generate_response(
                system_prompt="Eres un analista de datos experto que resume informacion de manera "
                "clara y util para agentes AI.",
                user_prompt=context_prompt,
                temperature=0.3,
            )

            return context_summary

        except Exception as e:
            logger.warning(f"Error generating embedding context: {e}")
            # Fallback to simple formatting
            return self._generate_fallback_context(user_query, results)

    def _generate_fallback_context(self, user_query: str, results: List[Dict[str, Any]]) -> str:
        """
        Generate simple fallback context when AI summary fails.

        Args:
            user_query: Original user query
            results: SQL query results

        Returns:
            Simple formatted context string
        """
        if not results:
            return f"No se encontraron datos para: {user_query}"

        summary = f"Encontrados {len(results)} registros para la consulta: {user_query}\n\n"

        # Add first few results
        for i, record in enumerate(results[:3]):
            summary += f"Registro {i + 1}: {json.dumps(record, default=str)}\n"

        if len(results) > 3:
            summary += f"... y {len(results) - 3} registros mas."

        return summary
