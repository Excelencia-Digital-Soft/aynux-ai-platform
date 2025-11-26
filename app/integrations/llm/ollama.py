"""
Ollama implementation of ILLM and IEmbeddingModel interfaces

Provides local LLM capabilities using Ollama service.
Implements standard interfaces for maximum flexibility and testability.
"""

import logging
from typing import AsyncIterator, Dict, List, Optional

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama, OllamaEmbeddings

from app.config.settings import get_settings
from app.core.interfaces.llm import (
    ILLM,
    IChatLLM,
    IEmbeddingModel,
    LLMConnectionError,
    LLMError,
    LLMGenerationError,
    LLMProvider,
)

logger = logging.getLogger(__name__)


class OllamaLLM(ILLM, IChatLLM):
    """
    Ollama implementation of ILLM interface.

    Provides local LLM capabilities using Ollama service with langchain integration.
    Supports chat, text generation, and streaming.

    Example:
        ```python
        llm = OllamaLLM(model_name="deepseek-r1:7b")

        # Simple generation
        response = await llm.generate("Tell me about Python")

        # Chat with history
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello!"}
        ]
        response = await llm.generate_chat(messages)

        # Streaming
        async for token in llm.generate_stream("Tell me a story"):
            print(token, end="", flush=True)
        ```
    """

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.7,
        **kwargs,
    ):
        """
        Initialize Ollama LLM.

        Args:
            model_name: Name of Ollama model (e.g., "deepseek-r1:7b", "llama2")
            base_url: Ollama API URL (default from settings)
            temperature: Temperature for generation (0.0-1.0)
            **kwargs: Additional parameters for ChatOllama
        """
        self.settings = get_settings()
        self._model_name = model_name or self.settings.OLLAMA_API_MODEL
        self._base_url = base_url or self.settings.OLLAMA_API_URL
        self._temperature = temperature

        # Initialize ChatOllama instance with explicit parameters
        self._llm = ChatOllama(
            model=self._model_name,
            base_url=self._base_url,
            temperature=temperature,
            num_gpu=kwargs.get("num_gpu", 1),
            num_thread=kwargs.get("num_thread", 4),
            repeat_penalty=kwargs.get("repeat_penalty", 1.1),
            top_k=kwargs.get("top_k", 40),
            top_p=kwargs.get("top_p", 0.9),
            keep_alive=kwargs.get("keep_alive", "5m"),
        )

        # Conversation history storage (for IChatLLM)
        self._conversations: Dict[str, List[Dict[str, str]]] = {}

        logger.info(f"Initialized OllamaLLM: model={self._model_name}, base_url={self._base_url}")

    @property
    def provider(self) -> LLMProvider:
        """Returns Ollama provider"""
        return LLMProvider.OLLAMA

    @property
    def model_name(self) -> str:
        """Returns current model name"""
        return self._model_name

    async def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 500, **kwargs) -> str:
        """
        Generate text from prompt.

        Args:
            prompt: Input prompt
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Generated text

        Raises:
            LLMGenerationError: If generation fails
        """
        try:
            # Update temperature if different
            if temperature != self._temperature:
                self._llm.temperature = temperature

            # Set max_tokens if provided
            if max_tokens:
                self._llm.num_predict = max_tokens

            # Generate
            messages = [HumanMessage(content=prompt)]
            response = await self._llm.ainvoke(messages)

            # Ensure we always return str (response.content can be str | list)
            if isinstance(response.content, str):
                return response.content
            elif isinstance(response.content, list):
                # Convert list to string representation
                return " ".join(str(item) for item in response.content)
            else:
                return str(response.content)

        except httpx.ConnectError as e:
            logger.error(f"Connection error to Ollama: {e}")
            raise LLMConnectionError(f"Could not connect to Ollama at {self._base_url}") from e
        except Exception as e:
            logger.error(f"Error generating text: {e}")
            raise LLMGenerationError(f"Failed to generate text: {e}") from e

    async def generate_chat(
        self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 500, **kwargs
    ) -> str:
        """
        Generate response in chat format.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Generation temperature
            max_tokens: Maximum tokens
            **kwargs: Additional parameters

        Returns:
            Generated response

        Raises:
            LLMGenerationError: If generation fails
        """
        try:
            # Convert messages to LangChain format
            lc_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "system":
                    lc_messages.append(SystemMessage(content=content))
                elif role == "assistant":
                    lc_messages.append(AIMessage(content=content))
                else:  # user
                    lc_messages.append(HumanMessage(content=content))

            # Update temperature if different
            if temperature != self._temperature:
                self._llm.temperature = temperature

            # Set max_tokens
            if max_tokens:
                self._llm.num_predict = max_tokens

            # Generate
            response = await self._llm.ainvoke(lc_messages)

            # Ensure we always return str (response.content can be str | list)
            if isinstance(response.content, str):
                return response.content
            elif isinstance(response.content, list):
                # Convert list to string representation
                return " ".join(str(item) for item in response.content)
            else:
                return str(response.content)

        except Exception as e:
            logger.error(f"Error in chat generation: {e}")
            raise LLMGenerationError(f"Failed to generate chat response: {e}") from e

    async def generate_stream(  # type: ignore[override]
        self, prompt: str, temperature: float = 0.7, max_tokens: int = 500, **kwargs
    ) -> AsyncIterator[str]:
        """
        Generate text in streaming mode.

        Args:
            prompt: Input prompt
            temperature: Generation temperature
            max_tokens: Maximum tokens
            **kwargs: Additional parameters

        Yields:
            Generated tokens one by one

        Raises:
            LLMGenerationError: If generation fails
        """
        try:
            # Update temperature if different
            if temperature != self._temperature:
                self._llm.temperature = temperature

            # Set max_tokens
            if max_tokens:
                self._llm.num_predict = max_tokens

            # Stream
            messages = [HumanMessage(content=prompt)]
            async for chunk in self._llm.astream(messages):
                if hasattr(chunk, "content"):
                    # Ensure we always yield str (chunk.content can be str | list)
                    if isinstance(chunk.content, str):
                        yield chunk.content
                    elif isinstance(chunk.content, list):
                        # Convert list to string representation
                        yield " ".join(str(item) for item in chunk.content)
                    else:
                        yield str(chunk.content)

        except Exception as e:
            logger.error(f"Error in streaming generation: {e}")
            raise LLMGenerationError(f"Failed to stream text: {e}") from e

    # IChatLLM implementation
    async def chat(self, message: str, conversation_id: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """
        Chat with conversation history.

        Args:
            message: User message
            conversation_id: ID to track conversation
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Returns:
            Assistant response
        """
        # Initialize conversation if new
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []

            # Add system prompt if provided
            if system_prompt:
                self._conversations[conversation_id].append({"role": "system", "content": system_prompt})

        # Add user message
        self._conversations[conversation_id].append({"role": "user", "content": message})

        # Generate response
        response = await self.generate_chat(messages=self._conversations[conversation_id], **kwargs)

        # Add assistant response to history
        self._conversations[conversation_id].append({"role": "assistant", "content": response})

        return response

    async def reset_conversation(self, conversation_id: str) -> None:
        """Reset conversation history"""
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            logger.info(f"Reset conversation: {conversation_id}")

    async def health_check(self) -> bool:
        """
        Check if Ollama service is available.

        Returns:
            True if service is reachable
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self._base_url}/api/tags", timeout=5.0)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False

    # Backward-compatible methods for migration from OllamaIntegration
    def get_llm(self, temperature: float = 0.7, model: str | None = None, **kwargs) -> ChatOllama:
        """
        Get a ChatOllama instance (backward-compatible with OllamaIntegration).

        This method provides compatibility with code that was using OllamaIntegration.get_llm().
        For new code, prefer using generate() or generate_chat() methods directly.

        Args:
            temperature: Generation temperature (0.0-1.0)
            model: Optional model name override
            **kwargs: Additional parameters for ChatOllama

        Returns:
            ChatOllama instance
        """
        model_to_use = model or self._model_name

        # Create a new ChatOllama instance with the specified parameters
        return ChatOllama(
            model=model_to_use,
            base_url=self._base_url,
            temperature=temperature,
            num_gpu=kwargs.get("num_gpu", 1),
            num_thread=kwargs.get("num_thread", 4),
            repeat_penalty=kwargs.get("repeat_penalty", 1.1),
            top_k=kwargs.get("top_k", 40),
            top_p=kwargs.get("top_p", 0.9),
            keep_alive=kwargs.get("keep_alive", "5m"),
            num_predict=kwargs.get("num_predict"),
        )

    def get_embeddings(self, model: str | None = None) -> OllamaEmbeddings:
        """
        Get an OllamaEmbeddings instance (backward-compatible with OllamaIntegration).

        This method provides compatibility with code that was using OllamaIntegration.get_embeddings().
        For new code, prefer using OllamaEmbeddingModel class directly.

        Args:
            model: Optional embedding model name override

        Returns:
            OllamaEmbeddings instance
        """
        embedding_model = model or self.settings.OLLAMA_API_MODEL_EMBEDDING
        return OllamaEmbeddings(model=embedding_model, base_url=self._base_url)

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """
        Generate a response using system and user prompts (backward-compatible).

        This method provides compatibility with code that was using OllamaIntegration.generate_response().
        For new code, prefer using generate_chat() with proper message formatting.

        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            model: Optional model name override
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate

        Returns:
            Generated response text
        """
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # Use generate_chat for proper message handling
            return await self.generate_chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens or 500,
            )

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "Lo siento, no pude procesar tu solicitud en este momento."


class OllamaEmbeddingModel(IEmbeddingModel):
    """
    Ollama implementation of IEmbeddingModel.

    Provides text embeddings using Ollama embedding models.

    Example:
        ```python
        embedder = OllamaEmbeddingModel(model_name="nomic-embed-text:v1.5")

        # Single embedding
        embedding = await embedder.embed_text("laptop gaming")
        # embedding = [0.123, -0.456, ...] (768 dimensions)

        # Batch embeddings
        embeddings = await embedder.embed_batch(["laptop", "mouse", "keyboard"])
        ```
    """

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
        embedding_dimension: int = 768,
    ):
        """
        Initialize Ollama embedding model.

        Args:
            model_name: Embedding model name (e.g., "nomic-embed-text:v1.5")
            base_url: Ollama API URL
            embedding_dimension: Expected dimension of embeddings
        """
        self.settings = get_settings()
        self._model_name = model_name or self.settings.OLLAMA_API_MODEL_EMBEDDING
        self._base_url = base_url or self.settings.OLLAMA_API_URL
        self._embedding_dimension = embedding_dimension

        # Initialize OllamaEmbeddings
        self._embedder = OllamaEmbeddings(model=self._model_name, base_url=self._base_url)

        logger.info(f"Initialized OllamaEmbeddingModel: model={self._model_name}")

    @property
    def embedding_dimension(self) -> int:
        """Returns embedding dimension"""
        return self._embedding_dimension

    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector

        Raises:
            LLMError: If embedding generation fails
        """
        try:
            # OllamaEmbeddings uses sync methods, wrap in async
            embedding = await self._embedder.aembed_query(text)
            return embedding

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise LLMError(f"Failed to generate embedding: {e}") from e

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors

        Raises:
            LLMError: If batch embedding fails
        """
        try:
            # Use batch embedding method
            embeddings = await self._embedder.aembed_documents(texts)
            return embeddings

        except Exception as e:
            logger.error(f"Error in batch embedding: {e}")
            raise LLMError(f"Failed to generate batch embeddings: {e}") from e


# Factory function for convenience
def create_ollama_llm(model_name: str | None = None, temperature: float = 0.7, **kwargs) -> OllamaLLM:
    """
    Factory function to create OllamaLLM instance.

    Args:
        model_name: Model name
        temperature: Generation temperature
        **kwargs: Additional parameters

    Returns:
        Configured OllamaLLM instance
    """
    return OllamaLLM(model_name=model_name, temperature=temperature, **kwargs)


def create_ollama_embedder(model_name: str | None = None, **kwargs) -> OllamaEmbeddingModel:
    """
    Factory function to create OllamaEmbeddingModel instance.

    Args:
        model_name: Embedding model name
        **kwargs: Additional parameters

    Returns:
        Configured OllamaEmbeddingModel instance
    """
    return OllamaEmbeddingModel(model_name=model_name, **kwargs)
