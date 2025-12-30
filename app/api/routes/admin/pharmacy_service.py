# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Service layer for Pharmacy Admin API.
# ============================================================================
"""
Pharmacy Service - Graph manager and session repository.

Provides singleton graph manager and Redis session repository
for pharmacy test session management.
"""

from __future__ import annotations

import logging
from datetime import datetime
from threading import Lock
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.api.routes.admin.pharmacy_models import PharmacySessionState
from app.domains.pharmacy.agents.graph import PharmacyGraph
from app.repositories.async_redis_repository import AsyncRedisRepository

logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS
# ============================================================

SESSION_TTL = 86400  # 24 hours in seconds
SESSION_PREFIX = "pharmacy_test"


# ============================================================
# GRAPH MANAGER (SINGLETON)
# ============================================================


class PharmacyGraphManager:
    """Singleton manager for PharmacyGraph instance."""

    _instance: PharmacyGraphManager | None = None
    _lock = Lock()

    def __init__(self) -> None:
        self._graph: PharmacyGraph | None = None
        self._initialized = False

    @classmethod
    def get_instance(cls) -> PharmacyGraphManager:
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_graph(self) -> PharmacyGraph:
        """Get or initialize the PharmacyGraph singleton."""
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._graph = PharmacyGraph()
                    self._graph.initialize()
                    self._initialized = True
                    logger.info("PharmacyGraph singleton initialized")
        if self._graph is None:
            raise RuntimeError("PharmacyGraph failed to initialize")
        return self._graph

    def reset(self) -> None:
        """Reset the graph (for testing/debugging)."""
        with self._lock:
            self._graph = None
            self._initialized = False


# Global singleton
_graph_manager = PharmacyGraphManager.get_instance()


def get_graph_manager() -> PharmacyGraphManager:
    """Get the global graph manager instance."""
    return _graph_manager


async def invoke_pharmacy_graph(
    graph_state: dict[str, Any],
    recursion_limit: int = 50,
) -> dict[str, Any]:
    """
    Invoke the pharmacy graph with the given state.

    Args:
        graph_state: Initial state for graph execution
        recursion_limit: Maximum recursion depth for graph

    Returns:
        Graph execution result dictionary
    """
    graph = _graph_manager.get_graph()
    if graph.app is None:
        raise RuntimeError("PharmacyGraph app not initialized")

    invoke_config: RunnableConfig = {"recursion_limit": recursion_limit}
    result: dict[str, Any] = await graph.app.ainvoke(graph_state, invoke_config)
    return result


# ============================================================
# SESSION REPOSITORY
# ============================================================


class PharmacySessionRepository:
    """Repository for pharmacy test session management."""

    def __init__(self) -> None:
        self._repo: AsyncRedisRepository[PharmacySessionState] | None = None
        self._connected = False

    async def _ensure_connected(self) -> None:
        """Ensure Redis connection is established."""
        if self._repo is None:
            self._repo = AsyncRedisRepository[PharmacySessionState](
                model_class=PharmacySessionState,
                prefix=SESSION_PREFIX,
            )
        if not self._connected:
            await self._repo.connect()
            self._connected = True

    async def get(self, session_id: str) -> PharmacySessionState | None:
        """Get session state by ID."""
        await self._ensure_connected()
        if self._repo is None:
            return None
        return await self._repo.get(session_id)

    async def save(self, session: PharmacySessionState) -> bool:
        """Save session state with TTL."""
        await self._ensure_connected()
        if self._repo is None:
            return False
        session.updated_at = datetime.now().isoformat()
        return await self._repo.set(session.session_id, session, expiration=SESSION_TTL)

    async def delete(self, session_id: str) -> bool:
        """Delete session state."""
        await self._ensure_connected()
        if self._repo is None:
            return False
        return await self._repo.delete(session_id)

    async def exists(self, session_id: str) -> bool:
        """Check if session exists."""
        await self._ensure_connected()
        if self._repo is None:
            return False
        return await self._repo.exists(session_id)


# Global repository instance
_session_repo = PharmacySessionRepository()


def get_session_repository() -> PharmacySessionRepository:
    """Get the global session repository instance."""
    return _session_repo
