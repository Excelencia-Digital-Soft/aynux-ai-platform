"""
Base Container - Shared Singletons.

Single Responsibility: Manage expensive shared resources (LLM, VectorStore).
"""

import logging

from app.config.settings import get_settings
from app.core.interfaces.llm import ILLM
from app.core.interfaces.vector_store import IVectorStore
from app.integrations.llm import create_ollama_llm
from app.integrations.vector_stores import create_pgvector_store

logger = logging.getLogger(__name__)


class BaseContainer:
    """
    Base container for shared singletons.

    Single Responsibility: Create and cache expensive shared resources.
    """

    def __init__(self, config: dict | None = None):
        """
        Initialize base container.

        Args:
            config: Optional configuration dict (overrides settings)
        """
        self.settings = get_settings()
        self.config = config or {}

        # Singletons (expensive to create)
        self._llm_instance: ILLM | None = None
        self._vector_store_instance: IVectorStore | None = None

        logger.info("BaseContainer initialized")

    def get_llm(self) -> ILLM:
        """
        Get LLM instance (singleton).

        Returns:
            ILLM instance (Ollama)
        """
        if self._llm_instance is None:
            model_name = self.config.get("llm_model") or getattr(
                self.settings, "OLLAMA_API_MODEL", "deepseek-r1:7b"
            )

            logger.info(f"Creating LLM instance with model: {model_name}")
            self._llm_instance = create_ollama_llm(model_name=model_name)

        return self._llm_instance

    def get_vector_store(self) -> IVectorStore:
        """
        Get Vector Store instance (singleton).

        Returns:
            Vector Store instance (PgVector)
        """
        if self._vector_store_instance is None:
            collection_name = self.config.get("vector_collection", "products")
            embedding_dim = self.config.get("embedding_dimension", 768)

            logger.info(f"Creating Vector Store: {collection_name} (dim: {embedding_dim})")
            self._vector_store_instance = create_pgvector_store(
                collection_name=collection_name,
                embedding_dimension=embedding_dim,
            )
            assert self._vector_store_instance is not None, "Failed to create vector store"

        return self._vector_store_instance

    def get_config(self) -> dict:
        """Get current configuration."""
        return {
            "llm_model": self.config.get("llm_model", "deepseek-r1:7b"),
            "vector_collection": self.config.get("vector_collection", "products"),
            "embedding_dimension": self.config.get("embedding_dimension", 768),
            "domains": ["ecommerce", "credit", "healthcare", "excelencia"],
        }
