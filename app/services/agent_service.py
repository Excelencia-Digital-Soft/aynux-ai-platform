# ============================================================================
# SCOPE: GLOBAL
# Description: Servicio coordinador para gestión de agentes. Orquesta
#              operaciones entre Repository, Cache y BUILTIN_AGENT_DEFAULTS.
# Tenant-Aware: No - agentes son globales. Per-tenant via tenant_agents.
# ============================================================================
"""
Agent Service - Thin coordinator for agent operations.

Orchestrates operations between specialized services:
- AgentRepository: Data persistence
- AgentCache: In-memory caching for enabled agents
- BUILTIN_AGENT_DEFAULTS: Seed data source

Single Responsibility: Coordinate and orchestrate agent operations.
No direct DB access - delegates to specialized services.

Usage:
    # With explicit dependencies
    service = AgentService(repository)

    # Or use factory with just DB session
    service = AgentService.with_session(db)

    agents = await service.list_agents()
    keys = await service.get_enabled_keys()
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.builtin_agents import BUILTIN_AGENT_DEFAULTS
from app.models.db.agent import Agent
from app.repositories.agent_repository import AgentRepository

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class AgentServiceError(Exception):
    """Base exception for agent service errors."""

    pass


class AgentNotFoundError(AgentServiceError):
    """Raised when an agent is not found."""

    pass


class AgentAlreadyExistsError(AgentServiceError):
    """Raised when attempting to create a duplicate agent."""

    pass


# =============================================================================
# Service
# =============================================================================


class AgentService:
    """
    Agent Service - Thin coordinator.

    Single Responsibility: Orchestrate agent operations.
    Delegates to specialized services for actual work.
    """

    def __init__(self, repository: AgentRepository) -> None:
        """Initialize service with dependencies.

        Args:
            repository: AgentRepository for data access
        """
        self._repository = repository

    @classmethod
    def with_session(cls, db: AsyncSession) -> "AgentService":
        """Factory method to create service with all dependencies.

        Convenience method when you only have a DB session.

        Args:
            db: AsyncSession for database access

        Returns:
            Fully configured AgentService
        """
        repository = AgentRepository(db)
        return cls(repository=repository)

    # =========================================================================
    # Read Operations (delegated to repository)
    # =========================================================================

    async def list_agents(
        self,
        agent_type: str | None = None,
        domain_key: str | None = None,
        enabled_only: bool = False,
    ) -> list[Agent]:
        """List agents with optional filtering.

        Args:
            agent_type: Filter by type (builtin, specialized, custom)
            domain_key: Filter by domain (excelencia, ecommerce, etc.)
            enabled_only: Only return enabled agents

        Returns:
            List of Agent instances
        """
        return await self._repository.find_all(
            agent_type=agent_type,
            domain_key=domain_key,
            enabled_only=enabled_only,
        )

    async def get_enabled_keys(self) -> list[str]:
        """Get list of enabled agent keys.

        This is the primary method used by the graph and routing system.

        Returns:
            List of agent_key strings for enabled agents
        """
        return await self._repository.get_enabled_keys()

    async def get_enabled_configs(self) -> list[dict]:
        """Get enabled agents formatted for configuration.

        Returns:
            List of agent config dicts
        """
        return await self._repository.get_enabled_for_config()

    async def get_by_id(self, agent_id: UUID) -> Agent | None:
        """Get agent by UUID."""
        return await self._repository.get_by_id(agent_id)

    async def get_by_key(self, agent_key: str) -> Agent | None:
        """Get agent by unique key."""
        return await self._repository.get_by_key(agent_key)

    # =========================================================================
    # Write Operations (delegated to repository)
    # =========================================================================

    async def create(self, agent_data: dict) -> Agent:
        """Create a new agent.

        Args:
            agent_data: Agent data dict

        Returns:
            Created Agent

        Raises:
            AgentAlreadyExistsError: If agent_key already exists
        """
        # Check for duplicate
        if await self._repository.exists(agent_data.get("agent_key", "")):
            raise AgentAlreadyExistsError(
                f"Agent with key '{agent_data.get('agent_key')}' already exists"
            )

        agent = Agent(**agent_data)
        created = await self._repository.create(agent)

        # Invalidate cache
        self._invalidate_cache()

        logger.info(f"Created agent: {created.agent_key}")
        return created

    async def update(self, agent_id: UUID, update_data: dict) -> Agent | None:
        """Update an existing agent.

        Args:
            agent_id: Agent UUID
            update_data: Fields to update

        Returns:
            Updated Agent or None if not found
        """
        agent = await self._repository.get_by_id(agent_id)
        if not agent:
            return None

        for key, value in update_data.items():
            if hasattr(agent, key) and value is not None:
                setattr(agent, key, value)

        updated = await self._repository.update(agent)

        # Invalidate cache if enabled status changed
        if "enabled" in update_data:
            self._invalidate_cache()

        logger.info(f"Updated agent: {updated.agent_key}")
        return updated

    async def delete(self, agent_id: UUID) -> bool:
        """Delete an agent.

        Args:
            agent_id: Agent UUID to delete

        Returns:
            True if deleted, False if not found
        """
        agent = await self._repository.get_by_id(agent_id)
        if agent:
            agent_key = agent.agent_key
            deleted = await self._repository.delete(agent_id)
            if deleted:
                self._invalidate_cache()
                logger.info(f"Deleted agent: {agent_key}")
            return deleted
        return False

    async def toggle_enabled(self, agent_id: UUID) -> Agent | None:
        """Toggle agent enabled status.

        Args:
            agent_id: Agent UUID

        Returns:
            Updated Agent or None if not found
        """
        agent = await self._repository.get_by_id(agent_id)
        if not agent:
            return None

        agent.enabled = not agent.enabled  # type: ignore[assignment]
        updated = await self._repository.update(agent)

        # Invalidate cache
        self._invalidate_cache()

        logger.info(
            f"Agent {updated.agent_key} is now "
            f"{'enabled' if updated.enabled else 'disabled'}"
        )
        return updated

    async def set_enabled(self, agent_id: UUID, enabled: bool) -> Agent | None:
        """Set agent enabled status explicitly."""
        result = await self.update(agent_id, {"enabled": enabled})
        if result:
            self._invalidate_cache()
        return result

    # =========================================================================
    # Seed Operations
    # =========================================================================

    async def seed_builtin_agents(self) -> dict[str, int]:
        """Seed agents from BUILTIN_AGENT_DEFAULTS.

        Adds all builtin agents that don't already exist.
        Does NOT modify existing agents.

        Returns:
            Dict with added and skipped counts
        """
        added = 0
        skipped = 0

        for agent_key, defaults in BUILTIN_AGENT_DEFAULTS.items():
            if await self._repository.exists(agent_key):
                skipped += 1
                continue

            agent = Agent.from_builtin_defaults(agent_key, defaults)
            await self._repository.create(agent)
            added += 1
            logger.info(f"Seeded builtin agent: {agent_key}")

        self._invalidate_cache()

        logger.info(f"Seed complete: {added} added, {skipped} skipped")
        return {"added": added, "skipped": skipped}

    async def reset_to_builtin_defaults(self, agent_key: str) -> Agent | None:
        """Reset an agent to its builtin defaults.

        Args:
            agent_key: Agent key to reset

        Returns:
            Updated Agent or None if not a builtin agent
        """
        if agent_key not in BUILTIN_AGENT_DEFAULTS:
            return None

        agent = await self._repository.get_by_key(agent_key)
        if not agent:
            return None

        defaults = BUILTIN_AGENT_DEFAULTS[agent_key]

        agent.name = defaults.get("display_name", agent_key)
        agent.description = defaults.get("description")
        agent.priority = defaults.get("priority", 50)
        agent.keywords = defaults.get("keywords", [])
        agent.intent_patterns = defaults.get("intent_patterns", [])
        agent.config = defaults.get("config", {})
        agent.updated_at = datetime.now(UTC)

        updated = await self._repository.update(agent)
        logger.info(f"Reset agent to defaults: {agent_key}")
        return updated

    # =========================================================================
    # Bulk Operations (delegated to repository)
    # =========================================================================

    async def enable_agents(self, agent_ids: list[UUID]) -> int:
        """Enable multiple agents."""
        count = await self._repository.bulk_update_enabled(agent_ids, enabled=True)
        self._invalidate_cache()
        return count

    async def disable_agents(self, agent_ids: list[UUID]) -> int:
        """Disable multiple agents."""
        count = await self._repository.bulk_update_enabled(agent_ids, enabled=False)
        self._invalidate_cache()
        return count

    async def update_priorities(self, agent_priorities: list[dict]) -> int:
        """Update priority for multiple agents."""
        return await self._repository.bulk_update_priority(agent_priorities)

    # =========================================================================
    # Cache Management
    # =========================================================================

    def _invalidate_cache(self) -> None:
        """Invalidate the agent cache.

        Called whenever agent enabled status changes.
        """
        try:
            from app.core.cache.agent_cache import agent_cache
            agent_cache.invalidate()
            logger.debug("Agent cache invalidated")
        except ImportError:
            # Cache module not yet created or not available
            pass
