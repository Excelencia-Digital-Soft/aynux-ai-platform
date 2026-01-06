# ============================================================================
# SCOPE: GLOBAL
# Description: Contenedor base con singletons compartidos (LLM, VectorStore).
#              Recursos costosos creados una vez y reutilizados por todos los tenants.
# Tenant-Aware: No - instancias compartidas sin filtrado por tenant.
# ============================================================================
"""
Base Container - Shared Singletons.

Single Responsibility: Manage expensive shared resources (LLM, VectorStore).

Uses vLLM for LLM inference and TEI for embeddings.
"""

import logging

from app.config.settings import get_settings
from app.core.interfaces.llm import ILLM
from app.core.interfaces.vector_store import IVectorStore
from app.integrations.llm import create_vllm_llm
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

        Returns VllmLLM configured with single model from settings (VLLM_MODEL).

        Returns:
            ILLM instance (VllmLLM)
        """
        if self._llm_instance is None:
            logger.info(
                f"Creating VllmLLM instance: "
                f"base_url={self.settings.VLLM_BASE_URL}, "
                f"model={self.settings.VLLM_MODEL}"
            )
            self._llm_instance = create_vllm_llm()

        return self._llm_instance

    def get_vector_store(self) -> IVectorStore:
        """
        Get Vector Store instance (singleton).

        Returns:
            Vector Store instance (PgVector with 1024-dim embeddings)
        """
        if self._vector_store_instance is None:
            collection_name = self.config.get("vector_collection", "products")
            embedding_dim = self.config.get("embedding_dimension", self.settings.TEI_EMBEDDING_DIMENSION)

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
            "llm_model": self.settings.VLLM_MODEL,
            "vector_collection": self.config.get("vector_collection", "products"),
            "embedding_dimension": self.settings.TEI_EMBEDDING_DIMENSION,
            "domains": ["ecommerce", "credit", "healthcare", "excelencia"],
        }
