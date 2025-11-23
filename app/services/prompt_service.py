"""
PromptService - Legacy wrapper for the new UnifiedPromptService.

This module maintains backward compatibility while using the new YAML-based prompt system.
"""

from typing import Any, Dict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.prompts.service import UnifiedPromptService


class PromptService:
    """
    Legacy PromptService that delegates to UnifiedPromptService.

    Maintains backward compatibility for existing code while using
    the new YAML-based prompt system under the hood.
    """

    def __init__(self):
        self.output_parser = StrOutputParser()
        self._unified_service = UnifiedPromptService.get_instance()

    def _convert_to_chat_prompt(self, message: str, context: Dict[str, Any]) -> str:
        """
        Convierte un string en un prompt de chat.

        Args:
            message: El string a convertir.
            context: Variables de conversación

        Returns:
            Un string con el prompt de chat.
        """
        return self._unified_service.convert_to_chat_prompt(message, context)

    def _build_improved_prompt(self, message: str, historial: str, contexto: str) -> str:
        """
        Construye un prompt mejorado y detallado para un asistente de ventas de WhatsApp.

        Now uses YAML-based prompts from the UnifiedPromptService.

        Args:
            message: El último mensaje del usuario.
            historial: El historial de la conversación actual.
            contexto: La información sobre los productos, precios y promociones.

        Returns:
            Un string con el prompt completo y estructurado.
        """
        return self._unified_service.build_improved_prompt(message, historial, contexto)

    def _orquestator_prompt(self, message: str, historial: str) -> str:
        """
        Construye un prompt para orquestar según la intención del usuario y generar una salida JSON
        estructurada.

        Now uses YAML-based prompts from the UnifiedPromptService.

        Args:
            message: El último mensaje del usuario.
            historial: El historial de la conversación actual.

        Returns:
            Un string con el prompt completo y estructurado.
        """
        return self._unified_service.orquestator_prompt(message, historial)
