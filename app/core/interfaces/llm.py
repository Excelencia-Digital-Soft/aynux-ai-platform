"""
Interfaces para LLM providers

Define contratos para proveedores de Language Models (vLLM, OpenAI, etc.)
"""

from abc import abstractmethod
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Protocol, runtime_checkable


class LLMProvider(str, Enum):
    """Proveedores de LLM soportados"""

    VLLM = "vllm"  # Primary provider - OpenAI-compatible API
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    DEEPSEEK = "deepseek"  # OpenAI-compatible API
    KIMI = "kimi"  # OpenAI-compatible API (Moonshot)


@runtime_checkable
class ILLM(Protocol):
    """
    Interface base para proveedores de LLM.

    Abstrae la generación de texto con diferentes modelos.
    Permite cambiar de provider (vLLM, OpenAI, etc.) sin modificar código.

    Example:
        ```python
        class VllmLLM(ILLM):
            async def generate(self, prompt: str, **kwargs) -> str:
                response = await self.client.chat.completions.create(
                    model="Qwen/Qwen2.5-7B-Instruct",
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.choices[0].message.content
        ```
    """

    @property
    @abstractmethod
    def provider(self) -> LLMProvider:
        """Proveedor de LLM"""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Nombre del modelo actual"""
        ...

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 500,
        **kwargs,
    ) -> str:
        """
        Genera texto basado en el prompt.

        Args:
            prompt: Texto de entrada para el modelo
            temperature: Control de creatividad (0.0 = determinístico, 1.0 = creativo)
            max_tokens: Número máximo de tokens a generar
            **kwargs: Parámetros adicionales específicos del provider (e.g., complexity)

        Returns:
            Texto generado por el modelo

        Raises:
            LLMError: Si hay error en la generación
        """
        ...

    @abstractmethod
    async def generate_chat(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 500,
        **kwargs,
    ) -> str:
        """
        Genera respuesta en formato chat.

        Args:
            messages: Lista de mensajes con formato {"role": "user/assistant", "content": "..."}
            temperature: Control de creatividad
            max_tokens: Número máximo de tokens
            **kwargs: Parámetros adicionales (e.g., complexity)

        Returns:
            Respuesta del modelo

        Example:
            ```python
            messages = [
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello!"},
                {"role": "assistant", "content": "Hi! How can I help?"},
                {"role": "user", "content": "Tell me about Python"}
            ]
            response = await llm.generate_chat(messages)
            ```
        """
        ...

    @abstractmethod
    def generate_stream(
        self,
        prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 500,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Genera texto en streaming (token por token).

        Args:
            prompt: Texto de entrada
            temperature: Control de creatividad
            max_tokens: Número máximo de tokens
            **kwargs: Parámetros adicionales (e.g., complexity)

        Yields:
            Tokens generados uno por uno

        Example:
            ```python
            async for token in llm.generate_stream("Tell me a story"):
                print(token, end="", flush=True)
            ```
        """
        ...


@runtime_checkable
class IEmbeddingModel(Protocol):
    """
    Interface para modelos de embeddings.

    Convierte texto en vectores numéricos para búsqueda semántica.
    """

    @property
    @abstractmethod
    def embedding_dimension(self) -> int:
        """Dimensión de los embeddings generados"""
        ...

    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """
        Genera embedding para un texto.

        Args:
            text: Texto a convertir en embedding

        Returns:
            Vector de números flotantes

        Example:
            ```python
            embedding = await model.embed_text("laptop gaming")
            # embedding = [0.123, -0.456, 0.789, ...] (1024 dimensiones)
            ```
        """
        ...

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Genera embeddings para múltiples textos en batch.

        Más eficiente que llamar embed_text() múltiples veces.

        Args:
            texts: Lista de textos

        Returns:
            Lista de vectores

        Example:
            ```python
            texts = ["laptop", "mouse", "keyboard"]
            embeddings = await model.embed_batch(texts)
            # embeddings = [[0.1, 0.2, ...], [0.3, 0.4, ...], ...]
            ```
        """
        ...


@runtime_checkable
class IChatLLM(Protocol):
    """
    Interface específica para modelos de chat con historial.

    Maneja conversaciones multi-turn con contexto.
    """

    @abstractmethod
    async def chat(self, message: str, conversation_id: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """
        Genera respuesta manteniendo historial de conversación.

        Args:
            message: Mensaje del usuario
            conversation_id: ID de la conversación (para mantener contexto)
            system_prompt: Prompt de sistema opcional
            **kwargs: Parámetros adicionales

        Returns:
            Respuesta del modelo

        Example:
            ```python
            # Primera interacción
            response1 = await llm.chat(
                "Hola, soy Juan",
                conversation_id="conv-123"
            )
            # Response: "Hola Juan, ¿en qué puedo ayudarte?"

            # Segunda interacción (recuerda el nombre)
            response2 = await llm.chat(
                "¿Cuál es mi nombre?",
                conversation_id="conv-123"
            )
            # Response: "Tu nombre es Juan"
            ```
        """
        ...

    @abstractmethod
    async def reset_conversation(self, conversation_id: str) -> None:
        """
        Reinicia el historial de una conversación.

        Args:
            conversation_id: ID de la conversación a resetear
        """
        ...


@runtime_checkable
class IStructuredLLM(Protocol):
    """
    Interface para LLMs con salida estructurada (JSON).

    Útil para extraer información específica de forma confiable.
    """

    @abstractmethod
    async def generate_json(self, prompt: str, schema: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Genera respuesta en formato JSON según schema.

        Args:
            prompt: Texto de entrada
            schema: Schema JSON que define la estructura esperada
            **kwargs: Parámetros adicionales

        Returns:
            Diccionario con datos estructurados

        Example:
            ```python
            schema = {
                "type": "object",
                "properties": {
                    "product_name": {"type": "string"},
                    "price": {"type": "number"},
                    "category": {"type": "string"}
                }
            }

            result = await llm.generate_json(
                "Extract info: Laptop HP for $899",
                schema=schema
            )
            # result = {"product_name": "Laptop HP", "price": 899, "category": "electronics"}
            ```
        """
        ...


@runtime_checkable
class ILLMFactory(Protocol):
    """
    Interface para factories de LLM.

    Permite crear instances de LLM según provider.
    """

    @abstractmethod
    def create_llm(self, provider: LLMProvider, model_name: str, config: Optional[Dict[str, Any]] = None) -> ILLM:
        """
        Crea instance de LLM.

        Args:
            provider: Proveedor a usar
            model_name: Nombre del modelo
            config: Configuración adicional

        Returns:
            Instancia de ILLM

        Example:
            ```python
            factory = LLMFactory()

            # Ollama
            ollama_llm = factory.create_llm(
                LLMProvider.OLLAMA,
                "deepseek-r1:7b",
                config={"api_url": "http://localhost:11434"}
            )

            # OpenAI
            openai_llm = factory.create_llm(
                LLMProvider.OPENAI,
                "gpt-4",
                config={"api_key": "sk-..."}
            )
            ```
        """
        ...


# Excepciones
class LLMError(Exception):
    """Error base para LLM"""

    pass


class LLMConnectionError(LLMError):
    """Error de conexión con el provider"""

    pass


class LLMGenerationError(LLMError):
    """Error durante generación"""

    pass


class LLMRateLimitError(LLMError):
    """Rate limit excedido"""

    pass
