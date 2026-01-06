# ============================================================================
# SCOPE: GLOBAL
# Description: TEI (Text Embeddings Inference) client for BAAI/bge-m3 (1024 dims).
#              Uses native /embed endpoint for simplicity and performance.
# Tenant-Aware: No - configuration via settings.
# ============================================================================
"""
TEI (Text Embeddings Inference) embedding service client.

TEI is a high-performance embedding server from Hugging Face that supports
BAAI/bge-m3 model (1024 dimensions).

Features:
- Native /embed endpoint (simpler than OpenAI-compatible)
- Batch embedding support
- 1024-dimensional vectors for semantic search
- Health check functionality
- Connection pooling with httpx
"""

import logging
from typing import List

import httpx

from app.config.settings import get_settings
from app.core.interfaces.llm import IEmbeddingModel, LLMConnectionError, LLMError

logger = logging.getLogger(__name__)


class TEIEmbeddingModel(IEmbeddingModel):
    """
    TEI embedding service implementation.

    Uses BAAI/bge-m3 model with 1024 dimensions for high-quality
    multilingual semantic search.

    TEI uses a native endpoint format:
    - Request: POST /embed {"inputs": "text" | ["text1", "text2"]}
    - Response: [[float, float, ...]] (array of embedding arrays)

    Example:
        ```python
        # Using settings (recommended)
        embedder = TEIEmbeddingModel()

        # Generate single embedding
        embedding = await embedder.embed_text("Hello world")
        # embedding = [0.123, -0.456, ...] (1024 dimensions)

        # Batch embedding
        embeddings = await embedder.embed_batch(["Hello", "World", "Test"])
        # embeddings = [[...], [...], [...]]
        ```
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        embedding_dimension: int | None = None,
        timeout: float | None = None,
    ):
        """
        Initialize TEI embedding client.

        Args:
            base_url: TEI server URL. Uses TEI_BASE_URL from settings if not provided.
            model: Embedding model name. Uses TEI_MODEL from settings if not provided.
            embedding_dimension: Vector dimension. Uses TEI_EMBEDDING_DIMENSION from settings.
            timeout: Request timeout in seconds. Uses TEI_REQUEST_TIMEOUT from settings.
        """
        settings = get_settings()

        self._base_url = base_url or settings.TEI_BASE_URL
        self._model = model or settings.TEI_MODEL
        self._embedding_dimension = embedding_dimension or settings.TEI_EMBEDDING_DIMENSION
        self._timeout = timeout or float(settings.TEI_REQUEST_TIMEOUT)

        logger.info(
            f"Initialized TEIEmbeddingModel: "
            f"url={self._base_url}, model={self._model}, dims={self._embedding_dimension}"
        )

    @property
    def embedding_dimension(self) -> int:
        """Return the embedding dimension (1024 for BAAI/bge-m3)."""
        return self._embedding_dimension

    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to convert to embedding vector.

        Returns:
            List of floats representing the embedding (1024 dimensions).

        Raises:
            LLMConnectionError: If connection to TEI fails.
            LLMError: If embedding generation fails.

        Example:
            ```python
            embedding = await embedder.embed_text("laptop gaming")
            # Returns [0.123, -0.456, 0.789, ...] (1024 floats)
            ```
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base_url}/embed",
                    json={"inputs": text},
                    timeout=self._timeout,
                )
                response.raise_for_status()
                data = response.json()

                # TEI returns [[float, float, ...]] for single input
                embedding = data[0]

                if len(embedding) != self._embedding_dimension:
                    logger.warning(
                        f"Embedding dimension mismatch: got {len(embedding)}, "
                        f"expected {self._embedding_dimension}"
                    )

                return embedding

        except httpx.TimeoutException as e:
            logger.error(f"Timeout calling TEI API: {e}")
            raise LLMConnectionError(f"Timeout calling TEI at {self._base_url}") from e
        except httpx.ConnectError as e:
            logger.error(f"Connection error to TEI: {e}")
            raise LLMConnectionError(f"Could not connect to TEI at {self._base_url}") from e
        except httpx.HTTPStatusError as e:
            logger.error(f"TEI API error: {e.response.status_code} - {e.response.text}")
            raise LLMError(f"TEI embedding failed: {e}") from e
        except Exception as e:
            logger.error(f"Error generating TEI embedding: {e}")
            raise LLMError(f"Failed to generate embedding: {e}") from e

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch.

        More efficient than calling embed_text() multiple times
        as it sends all texts in a single request.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors, one per input text.

        Raises:
            LLMConnectionError: If connection to TEI fails.
            LLMError: If embedding generation fails.

        Example:
            ```python
            embeddings = await embedder.embed_batch([
                "laptop gaming",
                "mechanical keyboard",
                "wireless mouse"
            ])
            # Returns [[...], [...], [...]] (3 vectors of 1024 floats each)
            ```
        """
        if not texts:
            return []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base_url}/embed",
                    json={"inputs": texts},
                    timeout=self._timeout * 2,  # Longer timeout for batch
                )
                response.raise_for_status()
                embeddings = response.json()

                # TEI returns [[...], [...], ...] directly (no sorting needed)

                # Validate dimensions
                for i, emb in enumerate(embeddings):
                    if len(emb) != self._embedding_dimension:
                        logger.warning(
                            f"Embedding {i} dimension mismatch: got {len(emb)}, "
                            f"expected {self._embedding_dimension}"
                        )

                return embeddings

        except httpx.TimeoutException as e:
            logger.error(f"Timeout calling TEI API (batch): {e}")
            raise LLMConnectionError(f"Timeout calling TEI at {self._base_url}") from e
        except httpx.ConnectError as e:
            logger.error(f"Connection error to TEI (batch): {e}")
            raise LLMConnectionError(f"Could not connect to TEI at {self._base_url}") from e
        except httpx.HTTPStatusError as e:
            logger.error(f"TEI API error (batch): {e.response.status_code}")
            raise LLMError(f"TEI batch embedding failed: {e}") from e
        except Exception as e:
            logger.error(f"Error in batch embedding: {e}")
            raise LLMError(f"Failed to generate batch embeddings: {e}") from e

    async def health_check(self) -> bool:
        """
        Check if TEI service is healthy.

        Returns:
            True if service is responding, False otherwise.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/health",
                    timeout=5.0,
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"TEI health check failed: {e}")
            return False


def create_tei_embedder(**kwargs) -> TEIEmbeddingModel:
    """
    Factory function to create TEIEmbeddingModel instance.

    Args:
        **kwargs: Additional parameters for TEIEmbeddingModel.

    Returns:
        Configured TEIEmbeddingModel instance.

    Example:
        ```python
        # Using settings (recommended)
        embedder = create_tei_embedder()

        # With custom timeout
        embedder = create_tei_embedder(timeout=60.0)

        # Override base URL
        embedder = create_tei_embedder(base_url="http://192.168.0.140:7997")
        ```
    """
    return TEIEmbeddingModel(**kwargs)
