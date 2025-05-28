import json
import logging
import re
from typing import Optional

import httpx
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from app.config.settings import get_settings
from app.models.chatbot import ChatbotResponse

logger = logging.getLogger(__name__)


class AIService:
    """
    Servicio para interactuar con modelos de IA generativa
    """

    def __init__(self):
        self.settings = get_settings()
        self.model = self.settings.OLLAMA_API_MODEL

    async def _generate_content(self, prompt: str, model: Optional[str] = None, temperature: float = 0.2) -> str:
        """
        Procesa una consulta con Ollama de forma simplificada y devuelve el resultado completo.

        Args:
            prompt: Texto completo del prompt
            model: Modelo a utilizar (opcional, usa el predeterminado si no se especifica)
            temperature: Nivel de creatividad (0.0 a 1.0)

        Returns:
            Respuesta completa del modelo
        """
        try:
            # Usar modelo predeterminado si no se especifica
            if not model:
                model = self.model

            # Configurar el modelo Ollama
            chat_model = ChatOllama(
                model=model,
                temperature=temperature,
                top_k=0,
                top_p=0,
                num_gpu=50,
                verbose=False,  # Cambiado a False para reducir logs
            )

            # Intentar ejecutar el modelo
            try:
                # Crear el prompt template simple
                prompt_template = ChatPromptTemplate.from_template(prompt)

                # Configurar la cadena simple sin historial ni streaming
                chain = prompt_template | chat_model | StrOutputParser()

                # Ejecutar la cadena y retornar el resultado completo
                result = await chain.ainvoke({})
                return result
            except httpx.ConnectError:
                return "ERROR_OLLAMA_CONNECTION_FAILED: No se pudo establecer conexión con el servicio Ollama."
            except httpx.ReadTimeout:
                return "ERROR_OLLAMA_TIMEOUT: Tiempo de espera agotado al comunicarse con Ollama."

        except Exception as e:
            error_msg = f"Error procesando consulta con Ollama: {str(e)}"
            logger.error(error_msg)
            return f"ERROR_OLLAMA_GENERAL: {error_msg}"

    @staticmethod
    def _procesar_respuesta(mensaje: str) -> ChatbotResponse:
        """
        Procesa la respuesta del modelo de IA
        """
        try:
            if not mensaje.strip():
                raise ValueError("La respuesta del chatbot está vacía.")

            # Buscar si el mensaje contiene JSON en formato de bloque de código
            json_match = re.search(r"```json\s*(\{.*?})\s*```", mensaje, re.DOTALL)
            if json_match:
                mensaje = json_match.group(1)

            # Decodificar el JSON
            response_data = json.loads(mensaje)

            # Validar y crear el objeto ChatbotResponse
            return ChatbotResponse(
                mensaje=response_data.get("mensaje", "Lo siento, hubo un error en mi respuesta."),
                estado=response_data.get("estado", "verificado"),
            )
        except (json.JSONDecodeError, KeyError) as e:
            # En caso de error, devolver una respuesta por defecto
            print(f"Error al procesar la respuesta del chatbot: {e}")
            return ChatbotResponse(
                mensaje=mensaje if mensaje else "Lo siento, hubo un error en mi respuesta.",
                estado="verificado",
            )
