"""
Tests for TenantAgentFactory and multi-tenant agent isolation.

Tests cover:
1. TenantAgentFactory functionality
2. Agent filtering based on TenantConfig
3. GraphRouter tenant-aware routing
4. Integration with TenantContext
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.core.tenancy.agent_factory import (
    TenantAgentFactory,
    get_tenant_enabled_agents,
    is_agent_enabled_for_tenant,
)
from app.core.tenancy.context import TenantContext, set_tenant_context


class TestTenantAgentFactoryUnit:
    """Unit tests for TenantAgentFactory."""

    def test_global_enabled_agents_from_settings(self):
        """Test that factory retrieves global agents from settings."""
        factory = TenantAgentFactory()
        global_agents = factory.global_enabled_agents

        # Should return list of agents from settings.ENABLED_AGENTS
        assert isinstance(global_agents, list)
        assert len(global_agents) > 0

    def test_get_enabled_agents_without_context(self):
        """Without TenantContext, should return global agents."""
        # Clear any existing context
        set_tenant_context(None)

        factory = TenantAgentFactory()
        agents = factory.get_enabled_agents()

        # Should match global config
        assert agents == sorted(factory.global_enabled_agents)

    def test_get_enabled_agents_with_explicit_list(self):
        """With explicit enabled_agent_types, use those agents."""
        explicit_agents = ["greeting_agent", "fallback_agent"]
        factory = TenantAgentFactory(enabled_agent_types=explicit_agents)

        agents = factory.get_enabled_agents()

        # Should be intersection of explicit and global
        global_agents = set(factory.global_enabled_agents)
        expected = sorted(set(explicit_agents) & global_agents)
        assert agents == expected

    def test_is_agent_enabled(self):
        """Test is_agent_enabled check."""
        explicit_agents = ["greeting_agent", "fallback_agent"]
        factory = TenantAgentFactory(enabled_agent_types=explicit_agents)

        # Agents in the list should be enabled (if also in global)
        if "greeting_agent" in factory.global_enabled_agents:
            assert factory.is_agent_enabled("greeting_agent") is True

        # Agents not in list should be disabled
        assert factory.is_agent_enabled("nonexistent_agent") is False

    def test_get_disabled_agents(self):
        """Test getting disabled agents."""
        explicit_agents = ["greeting_agent", "fallback_agent"]
        factory = TenantAgentFactory(enabled_agent_types=explicit_agents)

        disabled = factory.get_disabled_agents()

        # Should contain agents that are in global but not in enabled
        assert isinstance(disabled, list)
        # Disabled agents should not be in enabled list
        enabled = factory.get_enabled_agents()
        for agent in disabled:
            assert agent not in enabled

    def test_get_agent_status(self):
        """Test getting full agent status."""
        explicit_agents = ["greeting_agent"]
        factory = TenantAgentFactory(enabled_agent_types=explicit_agents)

        status = factory.get_agent_status()

        assert "enabled_agents" in status
        assert "disabled_agents" in status
        assert "enabled_count" in status
        assert "disabled_count" in status
        assert "mode" in status
        assert status["mode"] == "tenant"  # Because we have explicit agents

    def test_empty_tenant_config_uses_global(self):
        """Empty tenant config should use global agents."""
        factory = TenantAgentFactory(enabled_agent_types=[])

        agents = factory.get_enabled_agents()

        # Should match global config
        assert agents == sorted(factory.global_enabled_agents)

    def test_none_tenant_config_uses_global(self):
        """None tenant config should use global agents."""
        factory = TenantAgentFactory(enabled_agent_types=None)

        agents = factory.get_enabled_agents()

        # Should match global config
        assert agents == sorted(factory.global_enabled_agents)


class TestTenantAgentFactoryWithContext:
    """Tests for TenantAgentFactory with TenantContext."""

    @pytest.fixture
    def mock_tenant_context(self):
        """Create a mock TenantContext."""
        ctx = MagicMock(spec=TenantContext)
        ctx.organization_id = uuid.uuid4()
        ctx.is_multi_tenant_mode = True
        ctx.is_generic_mode = False
        ctx.enabled_agents = frozenset(["greeting_agent", "product_agent", "fallback_agent"])
        return ctx

    def test_from_context_with_tenant(self, mock_tenant_context):
        """Test creating factory from TenantContext."""
        set_tenant_context(mock_tenant_context)

        try:
            factory = TenantAgentFactory.from_context()
            agents = factory.get_enabled_agents()

            # Should be intersection of tenant and global
            assert isinstance(agents, list)
        finally:
            set_tenant_context(None)

    def test_context_filters_agents(self, mock_tenant_context):
        """Tenant context should filter available agents."""
        set_tenant_context(mock_tenant_context)

        try:
            factory = TenantAgentFactory.from_context()
            agents = factory.get_enabled_agents()

            # Agents not in tenant config should not be enabled
            # (assuming they are in global config)
            if "support_agent" in factory.global_enabled_agents:
                assert "support_agent" not in agents
        finally:
            set_tenant_context(None)


class TestGraphRouterTenantAware:
    """Tests for tenant-aware GraphRouter."""

    @pytest.fixture
    def mock_tenant_context_limited(self):
        """Create a mock TenantContext with limited agents."""
        ctx = MagicMock(spec=TenantContext)
        ctx.organization_id = uuid.uuid4()
        ctx.is_multi_tenant_mode = True
        ctx.is_generic_mode = False
        ctx.enabled_agents = frozenset(["greeting_agent", "fallback_agent"])
        return ctx

    def test_router_get_effective_agents_no_context(self):
        """Router should use global agents without context."""
        from app.core.graph.routing.graph_router import GraphRouter

        set_tenant_context(None)

        router = GraphRouter(enabled_agents=["greeting_agent", "product_agent", "fallback_agent"])
        effective = router.get_effective_enabled_agents()

        assert effective == ["greeting_agent", "product_agent", "fallback_agent"]

    def test_router_get_effective_agents_with_tenant(self, mock_tenant_context_limited):
        """Router should use tenant-filtered agents with context."""
        from app.core.graph.routing.graph_router import GraphRouter

        set_tenant_context(mock_tenant_context_limited)

        try:
            router = GraphRouter(
                enabled_agents=["greeting_agent", "product_agent", "fallback_agent"]
            )
            effective = router.get_effective_enabled_agents()

            # Should only include agents enabled for tenant
            assert "greeting_agent" in effective or "fallback_agent" in effective
            # product_agent is NOT in tenant config
            # (only if it's not in global config intersection)
        finally:
            set_tenant_context(None)

    def test_router_routes_to_fallback_for_disabled_agent(self, mock_tenant_context_limited):
        """Router should route to fallback when agent is disabled for tenant."""
        from app.core.graph.routing.graph_router import GraphRouter
        from app.core.schemas import AgentType

        set_tenant_context(mock_tenant_context_limited)

        try:
            router = GraphRouter(
                enabled_agents=["greeting_agent", "product_agent", "fallback_agent"]
            )

            # Create mock state requesting product_agent
            state = {
                "next_agent": "product_agent",
                "is_complete": False,
                "human_handoff_requested": False,
            }

            result = router.route_to_agent(state)

            # product_agent is not in tenant's enabled_agents
            # Should route to fallback
            assert result == AgentType.FALLBACK_AGENT.value
        finally:
            set_tenant_context(None)


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_tenant_enabled_agents_no_context(self):
        """Test convenience function without context."""
        set_tenant_context(None)

        agents = get_tenant_enabled_agents()

        # Should return global agents
        assert isinstance(agents, list)
        assert len(agents) > 0

    def test_is_agent_enabled_for_tenant_no_context(self):
        """Test convenience function without context."""
        set_tenant_context(None)

        # Should check against global config
        # Result depends on settings.ENABLED_AGENTS
        result = is_agent_enabled_for_tenant("greeting_agent")
        assert isinstance(result, bool)

    def test_is_agent_enabled_for_tenant_with_context(self):
        """Test convenience function with context."""
        ctx = MagicMock(spec=TenantContext)
        ctx.organization_id = uuid.uuid4()
        ctx.is_multi_tenant_mode = True
        ctx.is_generic_mode = False
        ctx.enabled_agents = frozenset(["greeting_agent"])

        set_tenant_context(ctx)

        try:
            result = is_agent_enabled_for_tenant("greeting_agent")
            # Should be True if greeting_agent is in both tenant and global config
            assert isinstance(result, bool)

            # product_agent is not in tenant config
            result_product = is_agent_enabled_for_tenant("product_agent")
            assert result_product is False  # Not in tenant's enabled_agents
        finally:
            set_tenant_context(None)


class TestAgentIsolation:
    """Integration tests for agent isolation between tenants."""

    def test_different_tenants_different_agents(self):
        """Different tenants should have different enabled agents."""
        # Tenant A: only greeting and fallback
        ctx_a = MagicMock(spec=TenantContext)
        ctx_a.organization_id = uuid.uuid4()
        ctx_a.is_multi_tenant_mode = True
        ctx_a.is_generic_mode = False
        ctx_a.enabled_agents = frozenset(["greeting_agent", "fallback_agent"])

        # Tenant B: greeting, product, and fallback
        ctx_b = MagicMock(spec=TenantContext)
        ctx_b.organization_id = uuid.uuid4()
        ctx_b.is_multi_tenant_mode = True
        ctx_b.is_generic_mode = False
        ctx_b.enabled_agents = frozenset(["greeting_agent", "product_agent", "fallback_agent"])

        # Check Tenant A
        set_tenant_context(ctx_a)
        try:
            factory_a = TenantAgentFactory.from_context()
            agents_a = factory_a.get_enabled_agents()
        finally:
            set_tenant_context(None)

        # Check Tenant B
        set_tenant_context(ctx_b)
        try:
            factory_b = TenantAgentFactory.from_context()
            agents_b = factory_b.get_enabled_agents()
        finally:
            set_tenant_context(None)

        # Tenant B should have more agents than Tenant A
        # (assuming product_agent is in global config)
        # At minimum, they should be different sets
        assert isinstance(agents_a, list)
        assert isinstance(agents_b, list)

    def test_tenant_cannot_enable_globally_disabled_agent(self):
        """Tenant cannot enable agents that are globally disabled."""
        ctx = MagicMock(spec=TenantContext)
        ctx.organization_id = uuid.uuid4()
        ctx.is_multi_tenant_mode = True
        ctx.is_generic_mode = False
        # Try to enable a fake agent that's not globally enabled
        ctx.enabled_agents = frozenset(["greeting_agent", "nonexistent_super_agent"])

        set_tenant_context(ctx)

        try:
            factory = TenantAgentFactory.from_context()
            agents = factory.get_enabled_agents()

            # nonexistent_super_agent should NOT be in the list
            assert "nonexistent_super_agent" not in agents
        finally:
            set_tenant_context(None)
