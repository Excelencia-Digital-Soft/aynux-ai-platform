# ============================================================================
# SCOPE: GLOBAL
# Description: Implementación Ollama de interfaces ILLM e IEmbeddingModel.
#              Instancias cacheadas y compartidas entre todos los tenants.
# Tenant-Aware: No directamente - pero BaseAgent.apply_tenant_config() puede
#              pasar model/temperature específicos del tenant.
# ============================================================================
"""
Ollama implementation of ILLM and IEmbeddingModel interfaces

Provides local LLM capabilities using Ollama service.
Implements standard interfaces for maximum flexibility and testability.

Features:
- Model tiering (SIMPLE, COMPLEX, REASONING)
- Configurable streaming support
- Automatic deepseek-r1 <think> tag cleaning
- LRU caching of ChatOllama instances
"""

import logging
import re
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
from app.integrations.llm.model_provider import ModelComplexity, get_model_name_for_complexity

logger = logging.getLogger(__name__)

# Regex pattern for cleaning deepseek-r1 think tags
DEEPSEEK_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL)


class OllamaLLM(ILLM, IChatLLM):
    """
    Ollama implementation of ILLM interface.
    Provides local LLM capabilities using Ollama service with langchain integration.
    Supports chat, text generation, and streaming.
    """

    # Class-level cache for ChatOllama instances (shared across all OllamaLLM instances)
    _llm_cache: dict[tuple[str, float], ChatOllama] = {}

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.7,
        **kwargs,
    ):
        """
        Initialize Ollama LLM wrapper.
        Note: A ChatOllama instance is NOT created here, but on-demand with caching.
        """
        self.settings = get_settings()
        self._model_name = model_name or self.settings.OLLAMA_API_MODEL_COMPLEX
        self._base_url = base_url or self.settings.OLLAMA_API_URL
        self._temperature = temperature
        self._kwargs = kwargs
        self._conversations: Dict[str, List[Dict[str, str]]] = {}
        logger.info(f"Initialized OllamaLLM wrapper: default_model={self._model_name}, base_url={self._base_url}")

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.OLLAMA

    @property
    def model_name(self) -> str:
        return self._model_name

    async def generate(
        self,
        prompt: str,
        *,
        complexity: ModelComplexity = ModelComplexity.COMPLEX,
        temperature: float = 0.7,
        max_tokens: int = 500,
        **kwargs,
    ) -> str:
        """Generate text from a simple prompt."""
        try:
            llm = self.get_llm(complexity=complexity, temperature=temperature, num_predict=max_tokens, **kwargs)
            messages = [HumanMessage(content=prompt)]
            response = await llm.ainvoke(messages)
            return response.content if isinstance(response.content, str) else str(response.content)
        except httpx.ConnectError as e:
            logger.error(f"Connection error to Ollama: {e}")
            raise LLMConnectionError(f"Could not connect to Ollama at {self._base_url}") from e
        except Exception as e:
            logger.error(f"Error generating text: {e}")
            raise LLMGenerationError(f"Failed to generate text: {e}") from e

    async def generate_chat(
        self,
        messages: List[Dict[str, str]],
        *,
        complexity: ModelComplexity = ModelComplexity.COMPLEX,
        temperature: float = 0.7,
        max_tokens: int = 500,
        **kwargs,
    ) -> str:
        """Generate a response in a chat format."""
        try:
            llm = self.get_llm(complexity=complexity, temperature=temperature, num_predict=max_tokens, **kwargs)
            lc_messages = [
                SystemMessage(content=msg["content"])
                if msg.get("role") == "system"
                else AIMessage(content=msg["content"])
                if msg.get("role") == "assistant"
                else HumanMessage(content=msg.get("content", ""))
                for msg in messages
            ]
            response = await llm.ainvoke(lc_messages)
            return response.content if isinstance(response.content, str) else str(response.content)
        except Exception as e:
            logger.error(f"Error in chat generation: {e}")
            raise LLMGenerationError(f"Failed to generate chat response: {e}") from e

    def generate_stream(
        self,
        prompt: str,
        *,
        complexity: ModelComplexity = ModelComplexity.COMPLEX,
        temperature: float = 0.7,
        max_tokens: int = 500,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Generate text in streaming mode."""
        return self._stream_generator(prompt, complexity, temperature, max_tokens, **kwargs)

    async def _stream_generator(
        self,
        prompt: str,
        complexity: ModelComplexity,
        temperature: float,
        max_tokens: int,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Internal async generator for streaming."""
        try:
            llm = self.get_llm(complexity=complexity, temperature=temperature, num_predict=max_tokens, **kwargs)
            messages = [HumanMessage(content=prompt)]
            async for chunk in llm.astream(messages):
                yield chunk.content if isinstance(chunk.content, str) else str(chunk.content)
        except Exception as e:
            logger.error(f"Error in streaming generation: {e}")
            raise LLMGenerationError(f"Failed to stream text: {e}") from e

    async def chat(self, message: str, conversation_id: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Chat with conversation history."""
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []
            if system_prompt:
                self._conversations[conversation_id].append({"role": "system", "content": system_prompt})
        self._conversations[conversation_id].append({"role": "user", "content": message})
        response = await self.generate_chat(messages=self._conversations[conversation_id], **kwargs)
        self._conversations[conversation_id].append({"role": "assistant", "content": response})
        return response

    async def reset_conversation(self, conversation_id: str) -> None:
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            logger.info(f"Reset conversation: {conversation_id}")

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self._base_url}/api/tags", timeout=5.0)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False

    @staticmethod
    def clean_deepseek_response(response: str) -> str:
        """
        Remove deepseek-r1 <think> tags from response.

        Args:
            response: Raw response from deepseek model

        Returns:
            Cleaned response without think tags
        """
        if not response:
            return response
        cleaned = DEEPSEEK_THINK_PATTERN.sub("", response)
        return cleaned.strip()

    async def generate_with_streaming_option(
        self,
        prompt: str,
        complexity: ModelComplexity = ModelComplexity.COMPLEX,
        temperature: float = 0.7,
        max_tokens: int = 500,
        streaming: bool | None = None,
        clean_deepseek_tags: bool = True,
        **kwargs,
    ) -> str | AsyncIterator[str]:
        """
        Generate response with configurable streaming based on context.

        Uses settings to determine streaming mode if not explicitly specified:
        - LLM_STREAMING_ENABLED for web requests
        - LLM_STREAMING_FOR_WEBHOOK for webhook requests

        Args:
            prompt: The prompt to generate from
            complexity: Model complexity tier (SIMPLE, COMPLEX, REASONING)
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate
            streaming: Override streaming setting (None = use settings)
            clean_deepseek_tags: Whether to clean <think> tags from response
            **kwargs: Additional arguments

        Returns:
            String response if streaming=False, AsyncIterator if streaming=True
        """
        # Determine streaming mode from settings if not explicitly set
        if streaming is None:
            streaming = self.settings.LLM_STREAMING_ENABLED

        if streaming:
            # Return async generator for streaming
            async def stream_with_cleaning():
                async for chunk in self.generate_stream(
                    prompt, complexity=complexity, temperature=temperature, max_tokens=max_tokens, **kwargs
                ):
                    if clean_deepseek_tags:
                        # For streaming, we can't clean mid-stream effectively
                        # Just yield chunks as-is, caller can clean final result
                        yield chunk
                    else:
                        yield chunk

            return stream_with_cleaning()
        else:
            # Non-streaming: wait for full response
            response = await self.generate(
                prompt, complexity=complexity, temperature=temperature, max_tokens=max_tokens, **kwargs
            )
            if clean_deepseek_tags:
                response = self.clean_deepseek_response(response)
            return response

    def get_llm(
        self,
        complexity: ModelComplexity = ModelComplexity.COMPLEX,
        temperature: float = 0.7,
        model: str | None = None,
        **kwargs,
    ) -> ChatOllama:
        """
        Get a cached ChatOllama instance.

        Instances are cached by (model, temperature) to avoid repeated initialization.
        Uses settings for keep_alive and num_thread for optimal performance.
        """
        if model:
            logger.warning(
                "The 'model' parameter in get_llm is deprecated. "
                "Use the 'complexity' parameter instead. "
                f"Forcing model to: {model}"
            )
            model_to_use = model
        else:
            model_to_use = get_model_name_for_complexity(complexity)

        # Cache key based on model and temperature
        cache_key = (model_to_use, temperature)

        # Return cached instance if available
        if cache_key in OllamaLLM._llm_cache:
            return OllamaLLM._llm_cache[cache_key]

        # Combine kwargs from init and the method call
        final_kwargs = {**self._kwargs, **kwargs}

        # Create new instance with performance-optimized settings
        # Note: ChatOllama doesn't have a 'streaming' init param - streaming is controlled
        # via stream() vs invoke() method calls
        llm_instance = ChatOllama(
            model=model_to_use,
            base_url=self._base_url,
            temperature=temperature,
            num_gpu=final_kwargs.get("num_gpu", 1),
            num_thread=final_kwargs.get("num_thread", self.settings.OLLAMA_NUM_THREAD),
            repeat_penalty=final_kwargs.get("repeat_penalty", 1.1),
            top_k=final_kwargs.get("top_k", 40),
            top_p=final_kwargs.get("top_p", 0.9),
            keep_alive=final_kwargs.get("keep_alive", self.settings.OLLAMA_KEEP_ALIVE),
            num_predict=final_kwargs.get("num_predict"),
        )

        # Cache the instance
        OllamaLLM._llm_cache[cache_key] = llm_instance
        logger.info(f"Created and cached ChatOllama instance: model={model_to_use}, temp={temperature}")

        return llm_instance

    def get_embeddings(self, model: str | None = None) -> OllamaEmbeddings:
        embedding_model = model or self.settings.OLLAMA_API_MODEL_EMBEDDING
        return OllamaEmbeddings(model=embedding_model, base_url=self._base_url)

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        complexity: ModelComplexity = ModelComplexity.COMPLEX,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        model: str | None = None,  # For full backward compatibility
    ) -> str:
        """(Backward-compatible) Generate a response using system and user prompts."""
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            # This method now correctly uses the dynamic instance creation
            # by calling generate_chat. We pass complexity through.
            # We also pass the model parameter for full backward compatibility.
            if model:
                logger.warning("The 'model' parameter in generate_response is deprecated. Use 'complexity' instead.")

            # Here we decide which parameter to use for get_llm, complexity has priority
            llm = self.get_llm(complexity=complexity, temperature=temperature, model=model, num_predict=max_tokens)

            lc_messages = [
                SystemMessage(content=msg["content"])
                if msg.get("role") == "system"
                else AIMessage(content=msg["content"])
                if msg.get("role") == "assistant"
                else HumanMessage(content=msg.get("content", ""))
                for msg in messages
            ]

            response = await llm.ainvoke(lc_messages)
            return response.content if isinstance(response.content, str) else str(response.content)

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
