"""
Tests for agent enablement/disablement functionality

Tests verify:
- AgentFactory only creates enabled agents
- AynuxGraph only adds enabled agent nodes
- GraphRouter routes disabled agents to fallback
- Admin API endpoints return correct agent status
"""

import pytest
from unittest.mock import MagicMock, patch

from app.core.graph.factories.agent_factory import AgentFactory
from app.core.graph.routing.graph_router import GraphRouter
from app.core.schemas import AgentType


class TestAgentFactory:
    """Tests for AgentFactory agent enablement"""

    def test_factory_creates_only_enabled_agents(self):
        """Test that factory only creates agents in enabled_agents list"""
        # Setup mocks
        mock_llm = MagicMock()
        mock_pgvector = MagicMock()
        mock_postgres = MagicMock()

        # Test with only 2 agents enabled
        config = {"enabled_agents": ["greeting_agent", "fallback_agent"], "agents": {}}

        factory = AgentFactory(llm=mock_llm, postgres=mock_postgres, config=config)
        agents = factory.initialize_all_agents()

        # Should have orchestrator, supervisor, greeting_agent, and fallback_agent (4 total)
        assert len(agents) == 4
        assert "orchestrator" in agents
        assert "supervisor" in agents
        assert "greeting_agent" in agents
        assert "fallback_agent" in agents

        # Should NOT have other agents
        assert "product_agent" not in agents
        assert "promotions_agent" not in agents

    def test_factory_creates_all_agents_when_all_enabled(self):
        """Test that factory creates all agents when all are enabled"""
        mock_llm = MagicMock()
        mock_pgvector = MagicMock()
        mock_postgres = MagicMock()

        # All agents enabled
        config = {
            "enabled_agents": [
                "greeting_agent",
                "product_agent",
                "data_insights_agent",
                "promotions_agent",
                "tracking_agent",
                "support_agent",
                "invoice_agent",
                "excelencia_agent",
                "fallback_agent",
                "farewell_agent",
            ],
            "agents": {},
        }

        factory = AgentFactory(llm=mock_llm, postgres=mock_postgres, config=config)
        agents = factory.initialize_all_agents()

        # Should have all 12 agents (10 specialized + orchestrator + supervisor)
        assert len(agents) == 12

    def test_factory_get_enabled_agent_names(self):
        """Test get_enabled_agent_names method"""
        mock_llm = MagicMock()
        mock_pgvector = MagicMock()
        mock_postgres = MagicMock()

        config = {"enabled_agents": ["greeting_agent", "product_agent"], "agents": {}}

        factory = AgentFactory(llm=mock_llm, postgres=mock_postgres, config=config)
        factory.initialize_all_agents()

        enabled = factory.get_enabled_agent_names()

        # Should return only specialized agents (not orchestrator/supervisor)
        assert "greeting_agent" in enabled
        assert "product_agent" in enabled
        assert "orchestrator" not in enabled
        assert "supervisor" not in enabled

    def test_factory_get_disabled_agent_names(self):
        """Test get_disabled_agent_names method.

        Note: get_disabled_agent_names() now uses BUILTIN_AGENT_CLASSES keys,
        so only agents with real class definitions are included.
        Legacy agents like 'product_agent' that aren't in BUILTIN_AGENT_CLASSES
        won't appear in the disabled list.
        """
        mock_llm = MagicMock()
        mock_pgvector = MagicMock()
        mock_postgres = MagicMock()

        config = {"enabled_agents": ["greeting_agent"], "agents": {}}

        factory = AgentFactory(llm=mock_llm, postgres=mock_postgres, config=config)
        factory.initialize_all_agents()

        disabled = factory.get_disabled_agent_names()

        # Should return all agents from BUILTIN_AGENT_CLASSES that are NOT enabled
        # These are agents with real class definitions
        assert "fallback_agent" in disabled
        assert "excelencia_agent" in disabled
        assert "medical_appointments_agent" in disabled  # Now in BUILTIN_AGENT_CLASSES
        assert "greeting_agent" not in disabled

    def test_factory_is_agent_enabled(self):
        """Test is_agent_enabled method"""
        mock_llm = MagicMock()
        mock_pgvector = MagicMock()
        mock_postgres = MagicMock()

        config = {"enabled_agents": ["greeting_agent", "product_agent"], "agents": {}}

        factory = AgentFactory(llm=mock_llm, postgres=mock_postgres, config=config)
        factory.initialize_all_agents()

        assert factory.is_agent_enabled("greeting_agent") is True
        assert factory.is_agent_enabled("product_agent") is True
        assert factory.is_agent_enabled("promotions_agent") is False
        assert factory.is_agent_enabled("unknown_agent") is False


class TestGraphRouter:
    """Tests for GraphRouter agent validation"""

    def test_router_routes_disabled_agent_to_fallback(self):
        """Test that router redirects disabled agents to fallback"""
        # Only greeting_agent enabled
        enabled_agents = ["greeting_agent", "fallback_agent"]
        router = GraphRouter(enabled_agents=enabled_agents)

        # Try to route to disabled product_agent
        state = {"next_agent": "product_agent", "is_complete": False, "human_handoff_requested": False}

        result = router.route_to_agent(state)

        # Should route to fallback_agent instead
        assert result == AgentType.FALLBACK_AGENT.value

    def test_router_allows_enabled_agent(self):
        """Test that router allows routing to enabled agents"""
        enabled_agents = ["greeting_agent", "product_agent", "fallback_agent"]
        router = GraphRouter(enabled_agents=enabled_agents)

        # Try to route to enabled product_agent
        state = {"next_agent": "product_agent", "is_complete": False, "human_handoff_requested": False}

        result = router.route_to_agent(state)

        # Should allow routing to product_agent
        assert result == "product_agent"

    def test_router_always_allows_orchestrator_and_supervisor(self):
        """Test that orchestrator and supervisor are always allowed"""
        enabled_agents = ["fallback_agent"]  # Only fallback enabled
        router = GraphRouter(enabled_agents=enabled_agents)

        # Orchestrator should always be allowed
        state1 = {"next_agent": "orchestrator", "is_complete": False, "human_handoff_requested": False}
        result1 = router.route_to_agent(state1)
        assert result1 == "orchestrator"

        # Supervisor should always be allowed
        state2 = {"next_agent": "supervisor", "is_complete": False, "human_handoff_requested": False}
        result2 = router.route_to_agent(state2)
        assert result2 == "supervisor"

    def test_router_handles_missing_next_agent(self):
        """Test that router handles missing next_agent gracefully"""
        enabled_agents = ["greeting_agent"]
        router = GraphRouter(enabled_agents=enabled_agents)

        # No next_agent in state
        state = {"is_complete": False, "human_handoff_requested": False}

        result = router.route_to_agent(state)

        # Should route to fallback
        assert result == AgentType.FALLBACK_AGENT.value

    def test_router_handles_invalid_agent(self):
        """Test that router handles invalid agent names"""
        enabled_agents = ["greeting_agent"]
        router = GraphRouter(enabled_agents=enabled_agents)

        # Invalid agent name
        state = {"next_agent": "invalid_agent_name", "is_complete": False, "human_handoff_requested": False}

        result = router.route_to_agent(state)

        # Should route to fallback
        assert result == AgentType.FALLBACK_AGENT.value


class TestAynuxGraphAgentManagement:
    """Tests for AynuxGraph agent management methods"""

    @pytest.fixture
    def mock_graph(self):
        """Create a mock AynuxGraph for testing"""
        with patch("app.core.graph.graph.VllmLLM"), patch(
            "app.core.graph.graph.PostgreSQLIntegration"
        ), patch("app.core.graph.graph.AgentFactory") as mock_factory:

            # Mock factory to return specific agents
            mock_factory_instance = MagicMock()
            mock_factory_instance.get_enabled_agent_names.return_value = ["greeting_agent", "product_agent"]
            mock_factory_instance.get_disabled_agent_names.return_value = [
                "promotions_agent",
                "tracking_agent",
                "support_agent",
                "invoice_agent",
                "excelencia_agent",
                "data_insights_agent",
                "fallback_agent",
                "farewell_agent",
            ]
            mock_factory_instance.initialize_all_agents.return_value = {
                "orchestrator": MagicMock(),
                "supervisor": MagicMock(),
                "greeting_agent": MagicMock(),
                "product_agent": MagicMock(),
            }
            mock_factory.return_value = mock_factory_instance

            from app.core.graph import AynuxGraph

            config = {"enabled_agents": ["greeting_agent", "product_agent"], "integrations": {}}

            # Create graph without building (to avoid state graph compilation)
            graph = AynuxGraph.__new__(AynuxGraph)
            graph.config = config
            graph.enabled_agents = config["enabled_agents"]
            graph.agent_factory = mock_factory_instance
            graph.agents = mock_factory_instance.initialize_all_agents()

            # Initialize status_manager (required after SRP refactoring)
            from app.core.graph.factories.agent_status_manager import AgentStatusManager

            graph.status_manager = AgentStatusManager(
                enabled_agents=graph.enabled_agents,
                agents=graph.agents,
                agent_factory=graph.agent_factory,
            )

            return graph

    def test_graph_is_agent_enabled(self, mock_graph):
        """Test is_agent_enabled method"""
        assert mock_graph.is_agent_enabled("greeting_agent") is True
        assert mock_graph.is_agent_enabled("product_agent") is True
        assert mock_graph.is_agent_enabled("promotions_agent") is False

    def test_graph_get_enabled_agents(self, mock_graph):
        """Test get_enabled_agents method"""
        enabled = mock_graph.get_enabled_agents()
        assert "greeting_agent" in enabled
        assert "product_agent" in enabled

    def test_graph_get_disabled_agents(self, mock_graph):
        """Test get_disabled_agents method"""
        disabled = mock_graph.get_disabled_agents()
        assert "promotions_agent" in disabled
        assert len(disabled) > 0

    def test_graph_get_agent_status(self, mock_graph):
        """Test get_agent_status method"""
        status = mock_graph.get_agent_status()

        assert "enabled_agents" in status
        assert "disabled_agents" in status
        assert "enabled_count" in status
        assert "disabled_count" in status
        assert "total_possible_agents" in status

        assert isinstance(status["enabled_count"], int)
        assert isinstance(status["disabled_count"], int)
        assert status["total_possible_agents"] == status["enabled_count"] + status["disabled_count"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
