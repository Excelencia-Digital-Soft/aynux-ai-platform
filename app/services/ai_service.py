import asyncio
import json
import logging
import re
from typing import Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from app.config.settings import get_settings
from app.core.shared.deprecation import deprecated
from app.models.chatbot import ChatbotResponse

logger = logging.getLogger(__name__)


@deprecated(
    reason="Legacy AI service replaced by ILLM interface with Clean Architecture",
    replacement="Use ILLM interface (app/core/interfaces/llm.py) and OllamaLLM implementation (app/integrations/llm/ollama.py)",
    removal_version="2.0.0",
)
class AIService:
    """
    Servicio para interactuar con modelos de IA generativa.

    DEPRECATED: Este servicio usa LangChain directamente sin abstracción.
    Ha sido reemplazado por ILLM interface que implementa Clean Architecture:

    Ventajas de ILLM:
    - Interface clara y consistente (Protocol)
    - Dependency Injection (inyectable en Use Cases y Agents)
    - Testeable con mocks (no requiere Ollama real)
    - Soporte para múltiples proveedores (Ollama, OpenAI, etc.)
    - Type-safe con type hints completos

    Migración recomendada:
        # ❌ Antes (legacy)
        from app.services.ai_service import AIService

        ai_service = AIService()
        response = await ai_service._generate_content(prompt="...")

        # ✅ Después (Clean Architecture)
        from app.core.container import get_container

        container = get_container()
        llm = container.get_llm()  # Returns ILLM instance (OllamaLLM)
        response = await llm.generate(prompt="...")

    Para uso en Use Cases o Agents:
        # Use Case con Dependency Injection
        class MyUseCase:
            def __init__(self, llm: ILLM):
                self.llm = llm

            async def execute(self, request):
                response = await self.llm.generate(prompt="...")
                return response
    """

    def __init__(self):
        self.settings = get_settings()
        self.model = self.settings.OLLAMA_API_MODEL or "llama3.1"

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
        # Intentar hasta 3 veces con espera exponencial
        response = ""
        for attempt in range(3):
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
                    base_url=self.settings.OLLAMA_API_URL,
                    request_timeout=30.0,  # Añadir timeout explícito
                )

                # Configurar el prompt
                prompt_template = ChatPromptTemplate.from_messages([("human", "{input}")])

                # Crear cadena con parser
                chain = prompt_template | chat_model | StrOutputParser()

                # Ejecutar
                response = await chain.ainvoke({"input": prompt})

                # Log solo en DEBUG
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Prompt usado: {prompt[:100]}...")
                    logger.debug(f"Respuesta: {response[:100]}...")

                return response

            except Exception as e:
                if attempt < 2:  # Si no es el último intento
                    wait_time = (attempt + 1) * 2  # 2, 4 segundos
                    logger.warning(
                        f"Error en _generate_content (intento {attempt + 1}/3): {e}. Reintentando en {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Error en _generate_content después de 3 intentos: {e}")
                    # En lugar de devolver un error, devolver un string vacío o un fallback

                return ""

        return response

    async def generate_response(self, prompt: str, temperature: float = 0.2) -> str:
        """
        Alias público para _generate_content para mantener compatibilidad
        """
        return await self._generate_content(prompt, temperature=temperature)

    async def detect_intent(self, user_message: str) -> ChatbotResponse:
        """
        Detecta la intención del usuario en el mensaje
        """
        logger.info(f"Detectando intención para mensaje: {user_message[:50]}...")

        # Validación
        if not user_message.strip():
            return ChatbotResponse(
                intent="desconocido", confidence=0.0, mensaje="Mensaje vacío", estado="sin_clasificar"
            )

        # Llamar a Ollama para detectar intent
        prompt = f"""
        Clasifica el siguiente mensaje del usuario en una de estas categorías:
        - 'saludo': saludos o bienvenidas
        - 'consulta_productos': preguntas sobre productos, características, precios
        - 'stock': disponibilidad o existencias
        - 'promociones': ofertas, descuentos, promociones
        - 'recomendaciones': solicitud de sugerencias o recomendaciones
        - 'desconocido': otras consultas

        Mensaje: "{user_message}"

        Responde ÚNICAMENTE con el nombre de la categoría.
        """

        respuesta = await self._generate_content(prompt, temperature=0.0)

        # Parsear respuesta
        respuesta_limpia = respuesta.strip().lower()

        # Mapear respuesta a intención
        intents_validos = ["saludo", "consulta_productos", "stock", "promociones", "recomendaciones", "desconocido"]

        intent = "desconocido"
        for i in intents_validos:
            if i in respuesta_limpia:
                intent = i
                break

        # Calcular confianza basada en la claridad de la respuesta
        confidence = 0.8 if intent != "desconocido" else 0.4

        # Log del resultado
        logger.info(f"Intent detectado: {intent} (confianza: {confidence})")

        # Retornar respuesta estructurada
        return ChatbotResponse(
            intent=intent,
            confidence=confidence,
            mensaje=user_message,
            estado="clasificado",
        )

    async def analyze_json_response(self, respuesta: str) -> Optional[dict]:
        """
        Intenta parsear respuestas JSON del modelo
        """
        try:
            # Buscar JSON en la respuesta
            json_match = re.search(r"\{.*\}", respuesta, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                # Limpiar y parsear
                json_str = re.sub(r"[\n\r\t]", " ", json_str)
                return json.loads(json_str)
        except Exception as e:
            logger.error(f"Error parseando JSON de respuesta: {e}")

        return None

    async def generate_chat_response(
        self, prompt: str, context: Optional[str] = None, model: Optional[str] = None
    ) -> ChatbotResponse:
        """
        Genera una respuesta conversacional más compleja
        """
        try:
            # Construir prompt completo con contexto
            full_prompt = prompt
            if context:
                full_prompt = f"Contexto:\n{context}\n\nUsuario: {prompt}"

            # Generar respuesta
            mensaje = await self._generate_content(full_prompt, model=model)

            # Retornar respuesta estructurada
            return ChatbotResponse(intent="respuesta_generada", confidence=0.9, mensaje=mensaje, estado="completado")

        except Exception as e:
            logger.error(f"Error generando respuesta: {e}")
            return ChatbotResponse(
                intent="error",
                confidence=0.0,
                mensaje="Lo siento, hubo un error en mi respuesta.",
                estado="verificado",
            )
