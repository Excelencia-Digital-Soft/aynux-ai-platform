# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Servicio que carga configuraciones de agentes desde la base de datos
#              y las fusiona con los defaults builtin. Cache por 5 minutos.
# Tenant-Aware: Yes - carga configuración específica por organization_id.
# ============================================================================
"""
TenantAgentService - Bridge between database and agent system.

Loads tenant agent configurations from database, merges with builtin defaults,
and provides configurations to router and factory.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.builtin_agents import (
    BUILTIN_AGENT_DEFAULTS,
    get_all_builtin_agents,
)
from app.core.schemas.tenant_agent_config import (
    AgentConfig,
    IntentPattern,
    TenantAgentRegistry,
)
from app.models.db.tenancy.tenant_agent import TenantAgent

# TenantConfigCache is planned but not yet implemented
TenantConfigCache = object  # Placeholder type

logger = logging.getLogger(__name__)

# UUID for system/global organization (fallback mode)
SYSTEM_ORG_ID = UUID("00000000-0000-0000-0000-000000000000")


class TenantAgentService:
    """
    Service for loading and managing tenant agent configurations.

    Features:
    - Load tenant agents from database
    - Merge with builtin defaults
    - Provide configuration to router and factory
    - Cache configurations for performance
    """

    # Cache TTL in seconds
    CACHE_TTL = 300  # 5 minutes

    def __init__(
        self,
        db: AsyncSession,
        cache: TenantConfigCache | None = None,
    ):
        """
        Initialize the service.

        Args:
            db: Async database session
            cache: Optional cache for tenant configs
        """
        self._db = db
        self._cache = cache

    async def get_agent_registry(self, org_id: UUID) -> TenantAgentRegistry:
        """
        Load complete agent registry for a tenant.

        Logic:
        1. Load agents from database
        2. Merge with builtin defaults (DB overrides builtins)
        3. Build intent and keyword indexes
        4. Cache result

        Special case: For system org (UUID zeros), loads from global
        catalog (core.agents) instead of tenant_agents.

        Args:
            org_id: Organization ID

        Returns:
            TenantAgentRegistry with all agents and indexes
        """
        # Special case: System org uses global catalog (core.agents)
        if org_id == SYSTEM_ORG_ID:
            logger.info("Loading global catalog for system organization")
            return await self._load_global_catalog_registry()

        cache_key = f"agent_registry:{org_id}"

        # Try cache first
        if self._cache:
            cached = await self._cache.get(cache_key)
            if cached:
                logger.debug(f"Agent registry cache hit for org {org_id}")
                return TenantAgentRegistry.model_validate(cached)

        # Load from database
        db_agents = await self._load_agents_from_db(org_id)

        # Start with builtin defaults
        agents: dict[str, AgentConfig] = {}

        # Add all builtin agents as defaults
        for agent_key, builtin_config in get_all_builtin_agents().items():
            agents[agent_key] = builtin_config

        # Override with database configurations
        for db_agent in db_agents:
            config = self._db_agent_to_config(db_agent)
            agents[config.agent_key] = config
            logger.debug(f"Loaded agent config from DB: {config.agent_key}")

        # Create registry
        registry = TenantAgentRegistry(
            organization_id=org_id,
            agents=agents,
        )

        # Build indexes
        registry.rebuild_indexes()

        # Cache result
        if self._cache:
            await self._cache.set(
                cache_key,
                registry.model_dump(),
                ttl=self.CACHE_TTL,
            )

        logger.info(
            f"Loaded agent registry for org {org_id}: "
            f"{len(agents)} agents, {len(registry.intent_to_agent)} intents"
        )

        return registry

    async def get_enabled_agents(self, org_id: UUID) -> list[AgentConfig]:
        """
        Get list of enabled agents for a tenant.

        Args:
            org_id: Organization ID

        Returns:
            List of enabled AgentConfig sorted by priority
        """
        registry = await self.get_agent_registry(org_id)
        return registry.get_enabled_agents()

    async def get_agent_config(
        self,
        org_id: UUID,
        agent_key: str,
    ) -> AgentConfig | None:
        """
        Get configuration for a specific agent.

        Args:
            org_id: Organization ID
            agent_key: Agent key (e.g., "greeting_agent")

        Returns:
            AgentConfig or None if not found
        """
        registry = await self.get_agent_registry(org_id)
        return registry.get_agent(agent_key)

    async def init_builtin_agents(self, org_id: UUID) -> list[TenantAgent]:
        """
        Initialize builtin agents for an organization.

        Creates database records for all builtin agents if they don't exist.
        This allows tenants to customize builtin agents via the database.

        Args:
            org_id: Organization ID

        Returns:
            List of created TenantAgent records
        """
        created = []

        # Get existing agents
        existing_keys = set()
        stmt = select(TenantAgent.agent_key).where(
            TenantAgent.organization_id == org_id
        )
        result = await self._db.execute(stmt)
        for (key,) in result:
            existing_keys.add(key)

        # Create missing builtin agents
        for agent_key, defaults in BUILTIN_AGENT_DEFAULTS.items():
            if agent_key in existing_keys:
                logger.debug(f"Agent {agent_key} already exists for org {org_id}")
                continue

            # Convert intent patterns
            intent_patterns = [
                {"pattern": p["pattern"], "weight": p.get("weight", 1.0)}
                for p in defaults.get("intent_patterns", [])
            ]

            agent = TenantAgent(
                organization_id=org_id,
                agent_key=agent_key,
                agent_type=defaults.get("agent_type", "builtin"),
                display_name=defaults["display_name"],
                description=defaults.get("description"),
                enabled=True,
                priority=defaults.get("priority", 50),
                domain_key=defaults.get("domain_key"),
                keywords=defaults.get("keywords", []),
                intent_patterns=intent_patterns,
                config=defaults.get("config", {}),
            )

            self._db.add(agent)
            created.append(agent)
            logger.info(f"Created builtin agent {agent_key} for org {org_id}")

        if created:
            await self._db.commit()
            # Invalidate cache
            if self._cache:
                await self._cache.delete(f"agent_registry:{org_id}")

        return created

    async def update_agent(
        self,
        org_id: UUID,
        agent_id: UUID,
        data: dict,
    ) -> TenantAgent | None:
        """
        Update an agent configuration.

        Args:
            org_id: Organization ID
            agent_id: Agent ID
            data: Fields to update

        Returns:
            Updated TenantAgent or None
        """
        stmt = select(TenantAgent).where(
            TenantAgent.id == agent_id,
            TenantAgent.organization_id == org_id,
        )
        result = await self._db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            return None

        # Update allowed fields
        allowed_fields = {
            "display_name",
            "description",
            "enabled",
            "priority",
            "keywords",
            "intent_patterns",
            "config",
        }

        for field, value in data.items():
            if field in allowed_fields and value is not None:
                setattr(agent, field, value)

        await self._db.commit()
        await self._db.refresh(agent)

        # Invalidate cache
        if self._cache:
            await self._cache.delete(f"agent_registry:{org_id}")

        return agent

    async def toggle_agent(
        self,
        org_id: UUID,
        agent_id: UUID,
    ) -> TenantAgent | None:
        """
        Toggle an agent's enabled status.

        Args:
            org_id: Organization ID
            agent_id: Agent ID

        Returns:
            Updated TenantAgent or None
        """
        stmt = select(TenantAgent).where(
            TenantAgent.id == agent_id,
            TenantAgent.organization_id == org_id,
        )
        result = await self._db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            return None

        agent.enabled = not agent.enabled
        await self._db.commit()
        await self._db.refresh(agent)

        # Invalidate cache
        if self._cache:
            await self._cache.delete(f"agent_registry:{org_id}")

        logger.info(
            f"Toggled agent {agent.agent_key} for org {org_id}: "
            f"enabled={agent.enabled}"
        )

        return agent

    async def delete_agent(
        self,
        org_id: UUID,
        agent_id: UUID,
    ) -> bool:
        """
        Delete an agent configuration.

        Note: Builtin agents will revert to defaults on next load.

        Args:
            org_id: Organization ID
            agent_id: Agent ID

        Returns:
            True if deleted
        """
        stmt = select(TenantAgent).where(
            TenantAgent.id == agent_id,
            TenantAgent.organization_id == org_id,
        )
        result = await self._db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            return False

        await self._db.delete(agent)
        await self._db.commit()

        # Invalidate cache
        if self._cache:
            await self._cache.delete(f"agent_registry:{org_id}")

        logger.info(f"Deleted agent {agent.agent_key} for org {org_id}")

        return True

    async def _load_global_catalog_registry(self) -> TenantAgentRegistry:
        """
        Load agents from global catalog (core.agents) for system org.

        Used when organization_id is the system UUID (all zeros).
        This allows using the agent catalog managed via /agent-catalog UI.

        Returns:
            TenantAgentRegistry with agents from global catalog
        """
        from app.models.db.agent import Agent

        # Load only enabled agents from global catalog
        stmt = select(Agent).where(Agent.enabled == True)  # noqa: E712
        result = await self._db.execute(stmt)
        db_agents = result.scalars().all()

        agents: dict[str, AgentConfig] = {}
        for db_agent in db_agents:
            # Use model's to_config_dict() and convert intent_patterns
            config_dict = db_agent.to_config_dict()

            # Convert intent_patterns to IntentPattern objects
            intent_patterns = [
                IntentPattern(**p)
                for p in config_dict.get("intent_patterns", [])
                if isinstance(p, dict)
            ]

            config = AgentConfig(
                id=db_agent.id,
                agent_key=config_dict["agent_key"],
                agent_type=config_dict.get("agent_type", "builtin"),
                display_name=config_dict["display_name"],
                description=config_dict.get("description"),
                enabled=config_dict.get("enabled", True),
                priority=config_dict.get("priority", 50),
                domain_key=config_dict.get("domain_key"),
                keywords=config_dict.get("keywords", []),
                intent_patterns=intent_patterns,
                config=config_dict.get("config", {}),
            )
            agents[config.agent_key] = config

        registry = TenantAgentRegistry(
            organization_id=SYSTEM_ORG_ID,
            agents=agents,
        )
        registry.rebuild_indexes()

        logger.info(f"Loaded global catalog for system org: {len(agents)} agents")
        return registry

    async def _load_agents_from_db(self, org_id: UUID) -> list[TenantAgent]:
        """Load all agents from database for an organization."""
        stmt = select(TenantAgent).where(TenantAgent.organization_id == org_id)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    def _db_agent_to_config(self, db_agent: TenantAgent) -> AgentConfig:
        """Convert database model to AgentConfig schema."""
        # Convert intent_patterns from JSON to IntentPattern objects
        intent_patterns = []
        for p in db_agent.intent_patterns or []:
            if isinstance(p, dict):
                intent_patterns.append(IntentPattern(**p))
            elif isinstance(p, IntentPattern):
                intent_patterns.append(p)

        return AgentConfig(
            id=db_agent.id,
            agent_key=db_agent.agent_key,
            agent_type=db_agent.agent_type or "builtin",
            display_name=db_agent.display_name,
            description=db_agent.description,
            agent_class=db_agent.agent_class,
            enabled=db_agent.enabled,
            priority=db_agent.priority or 50,
            domain_key=db_agent.domain_key,
            keywords=db_agent.keywords or [],
            intent_patterns=intent_patterns,
            config=db_agent.config or {},
        )


__all__ = ["TenantAgentService"]
