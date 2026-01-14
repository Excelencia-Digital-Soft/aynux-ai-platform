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

import asyncio
import logging
from datetime import datetime
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.api.routes.admin.pharmacy_models import PharmacySessionState
from app.domains.pharmacy.agents.graph_v2 import PharmacyGraphV2
from app.integrations.databases import PostgreSQLIntegration
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
    """Singleton manager for PharmacyGraphV2 instance with async initialization."""

    _instance: PharmacyGraphManager | None = None
    _init_lock: asyncio.Lock | None = None

    def __init__(self) -> None:
        self._graph: PharmacyGraphV2 | None = None
        self._postgres: PostgreSQLIntegration | None = None
        self._initialized = False

    @classmethod
    def get_instance(cls) -> PharmacyGraphManager:
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def get_graph(self) -> PharmacyGraphV2:
        """Get or initialize the PharmacyGraphV2 singleton with async checkpointer."""
        if not self._initialized:
            # Use async lock for thread-safe async initialization
            if PharmacyGraphManager._init_lock is None:
                PharmacyGraphManager._init_lock = asyncio.Lock()

            async with PharmacyGraphManager._init_lock:
                if not self._initialized:
                    # Create PostgreSQL integration for checkpointer
                    self._postgres = PostgreSQLIntegration()
                    self._graph = PharmacyGraphV2()
                    await self._graph.initialize(postgres=self._postgres)
                    self._initialized = True
                    logger.info("PharmacyGraphV2 singleton initialized with PostgreSQL checkpointer")

        if self._graph is None:
            raise RuntimeError("PharmacyGraphV2 failed to initialize")
        return self._graph

    async def reset(self) -> None:
        """Reset the graph (for testing/debugging)."""
        if PharmacyGraphManager._init_lock is None:
            PharmacyGraphManager._init_lock = asyncio.Lock()

        async with PharmacyGraphManager._init_lock:
            self._graph = None
            self._postgres = None
            self._initialized = False


# Global singleton
_graph_manager = PharmacyGraphManager.get_instance()


def get_graph_manager() -> PharmacyGraphManager:
    """Get the global graph manager instance."""
    return _graph_manager


async def invoke_pharmacy_graph(
    graph_state: dict[str, Any],
    conversation_id: str | None = None,
    recursion_limit: int = 50,
) -> dict[str, Any]:
    """
    Invoke the pharmacy graph with the given state.

    Args:
        graph_state: Initial state for graph execution
        conversation_id: Thread ID for checkpointer state persistence
        recursion_limit: Maximum recursion depth for graph

    Returns:
        Graph execution result dictionary
    """
    graph = await _graph_manager.get_graph()
    if graph.app is None:
        raise RuntimeError("PharmacyGraphV2 app not initialized")

    # DEBUG: Print graph ASCII representation
    try:
        ascii_graph = graph.app.get_graph().draw_ascii()
        logger.debug(f"[DEBUG] PharmacyGraphV2 ASCII:\n{ascii_graph}")
        print(f"\n[DEBUG] PharmacyGraphV2 ASCII:\n{ascii_graph}\n")
    except Exception as e:
        logger.warning(f"[DEBUG] Could not draw graph ASCII: {e}")

    # Build config with thread_id for checkpointer
    invoke_config: RunnableConfig = {"recursion_limit": recursion_limit}
    if conversation_id:
        invoke_config["configurable"] = {"thread_id": conversation_id}

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
