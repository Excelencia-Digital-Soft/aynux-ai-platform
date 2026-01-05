# ============================================================================
# SCOPE: GLOBAL
# Description: Repository para persistencia de agentes. Proporciona
#              operaciones CRUD y bulk sobre la tabla agents.
# Tenant-Aware: No - agentes son globales. Per-tenant via tenant_agents.
# ============================================================================
"""
Agent Repository - Data persistence layer for Agent entity.

Provides async CRUD operations, filtering, and bulk updates.
Follows Single Responsibility Principle - only handles data persistence.

Usage:
    repository = AgentRepository(db)
    agents = await repository.find_all(enabled_only=True)
    agent = await repository.get_by_key("greeting_agent")
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.agent import Agent

logger = logging.getLogger(__name__)


class AgentRepository:
    """
    Async repository for Agent persistence.

    Single Responsibility: Data access layer for agents table.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize repository with async database session.

        Args:
            db: SQLAlchemy async session
        """
        self._db = db

    # =========================================================================
    # Read Operations
    # =========================================================================

    async def find_all(
        self,
        agent_type: str | None = None,
        domain_key: str | None = None,
        enabled_only: bool = False,
    ) -> list[Agent]:
        """Find all agents with optional filtering.

        Args:
            agent_type: Filter by type (e.g., "builtin", "specialized", "custom")
            domain_key: Filter by domain (e.g., "excelencia", "ecommerce")
            enabled_only: Only return enabled agents

        Returns:
            List of Agent instances ordered by priority (desc), name
        """
        stmt = select(Agent)

        if agent_type:
            stmt = stmt.where(Agent.agent_type == agent_type)
        if domain_key is not None:
            if domain_key == "":
                # Empty string means global agents (domain_key IS NULL)
                stmt = stmt.where(Agent.domain_key.is_(None))
            else:
                stmt = stmt.where(Agent.domain_key == domain_key)
        if enabled_only:
            stmt = stmt.where(Agent.enabled == True)  # noqa: E712

        stmt = stmt.order_by(Agent.priority.desc(), Agent.name)

        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, agent_id: UUID) -> Agent | None:
        """Get agent by UUID.

        Args:
            agent_id: Agent UUID

        Returns:
            Agent or None if not found
        """
        stmt = select(Agent).where(Agent.id == agent_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_key(self, agent_key: str) -> Agent | None:
        """Get agent by unique key.

        Args:
            agent_key: Agent key (e.g., "greeting_agent", "support_agent")

        Returns:
            Agent or None if not found
        """
        stmt = select(Agent).where(Agent.agent_key == agent_key)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def exists(self, agent_key: str) -> bool:
        """Check if agent exists by key.

        Args:
            agent_key: Agent key

        Returns:
            True if exists, False otherwise
        """
        agent = await self.get_by_key(agent_key)
        return agent is not None

    async def get_enabled_keys(self) -> list[str]:
        """Get list of enabled agent keys.

        Returns:
            List of agent_key strings for enabled agents, ordered by priority
        """
        stmt = (
            select(Agent.agent_key)
            .where(Agent.enabled == True)  # noqa: E712
            .order_by(Agent.priority.desc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    # =========================================================================
    # Write Operations
    # =========================================================================

    async def create(self, agent: Agent) -> Agent:
        """Create a new agent.

        Args:
            agent: Agent instance to persist

        Returns:
            Persisted Agent with generated ID
        """
        self._db.add(agent)
        await self._db.commit()
        await self._db.refresh(agent)
        return agent

    async def update(self, agent: Agent) -> Agent:
        """Update an existing agent.

        Args:
            agent: Agent instance with updated fields

        Returns:
            Updated Agent
        """
        agent.updated_at = datetime.now(UTC)
        await self._db.commit()
        await self._db.refresh(agent)
        return agent

    async def delete(self, agent_id: UUID) -> bool:
        """Delete an agent by UUID.

        Args:
            agent_id: Agent UUID to delete

        Returns:
            True if deleted, False if not found
        """
        agent = await self.get_by_id(agent_id)
        if not agent:
            return False

        await self._db.delete(agent)
        await self._db.commit()
        return True

    async def save(self, agent: Agent) -> Agent:
        """Save agent (create or update).

        Args:
            agent: Agent to save

        Returns:
            Saved Agent
        """
        if agent.id:
            return await self.update(agent)
        return await self.create(agent)

    # =========================================================================
    # Bulk Operations
    # =========================================================================

    async def bulk_update_enabled(
        self,
        agent_ids: list[UUID],
        enabled: bool,
    ) -> int:
        """Bulk update enabled status for multiple agents.

        Args:
            agent_ids: List of agent UUIDs
            enabled: New enabled status

        Returns:
            Number of rows updated
        """
        stmt = (
            update(Agent)
            .where(Agent.id.in_(agent_ids))
            .values(enabled=enabled, updated_at=datetime.now(UTC))
        )
        result = await self._db.execute(stmt)
        await self._db.commit()
        return result.rowcount

    async def bulk_update_priority(self, priorities: list[dict]) -> int:
        """Bulk update priority for multiple agents.

        Args:
            priorities: List of {"id": UUID, "priority": int}

        Returns:
            Number of rows updated
        """
        updated = 0
        for item in priorities:
            agent = await self.get_by_id(item["id"])
            if agent:
                agent.priority = item["priority"]
                agent.updated_at = datetime.now(UTC)
                updated += 1

        await self._db.commit()
        return updated

    async def bulk_create(self, agents: list[Agent]) -> int:
        """Bulk create multiple agents.

        Args:
            agents: List of Agent instances

        Returns:
            Number of agents created
        """
        for agent in agents:
            self._db.add(agent)
        await self._db.commit()
        return len(agents)

    # =========================================================================
    # Query Helpers
    # =========================================================================

    async def count(
        self,
        agent_type: str | None = None,
        enabled_only: bool = False,
    ) -> int:
        """Count agents with optional filtering.

        Args:
            agent_type: Filter by type
            enabled_only: Only count enabled agents

        Returns:
            Number of matching agents
        """
        agents = await self.find_all(agent_type=agent_type, enabled_only=enabled_only)
        return len(agents)

    async def get_enabled_for_config(self) -> list[dict]:
        """Get enabled agents formatted for configuration.

        Returns:
            List of agent config dicts
        """
        agents = await self.find_all(enabled_only=True)
        return [agent.to_config_dict() for agent in agents]
