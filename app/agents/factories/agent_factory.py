"""
Factory for initializing and managing agents
"""

import logging
from typing import Any, Dict

from ..subagent import (
    CategoryAgent,
    DataInsightsAgent,
    FallbackAgent,
    FarewellAgent,
    InvoiceAgent,
    OrchestratorAgent,
    ProductAgent,
    PromotionsAgent,
    SupervisorAgent,
    SupportAgent,
    TrackingAgent,
)

logger = logging.getLogger(__name__)


class AgentFactory:
    """Factory class for creating and managing agent instances"""

    def __init__(self, ollama, chroma, postgres, config: Dict[str, Any]):
        self.ollama = ollama
        self.chroma = chroma
        self.postgres = postgres
        self.config = config
        self.agents = {}
        
    def initialize_all_agents(self) -> Dict[str, Any]:
        """Initialize all agents and return mapping"""
        try:
            agent_configs = self.config.get("agents", {})
            
            # Initialize orchestrator and supervisor
            self.agents["orchestrator"] = OrchestratorAgent(
                ollama=self.ollama, 
                config={}
            )
            
            supervisor_config = self._get_supervisor_config()
            self.agents["supervisor"] = SupervisorAgent(
                ollama=self.ollama, 
                config=supervisor_config
            )
            
            # Initialize specialized agents
            self.agents["product_agent"] = ProductAgent(
                ollama=self.ollama,
                postgres=self.postgres,
                config=self._extract_config(agent_configs, "product")
            )
            
            self.agents["category_agent"] = CategoryAgent(
                ollama=self.ollama,
                chroma=self.chroma,
                config=self._extract_config(agent_configs, "category")
            )
            
            self.agents["data_insights_agent"] = DataInsightsAgent(
                ollama=self.ollama,
                postgres=self.postgres,
                config=self._extract_config(agent_configs, "data_insights")
            )
            
            self.agents["promotions_agent"] = PromotionsAgent(
                ollama=self.ollama,
                chroma=self.chroma,
                config=self._extract_config(agent_configs, "promotions")
            )
            
            self.agents["tracking_agent"] = TrackingAgent(
                ollama=self.ollama,
                chroma=self.chroma,
                config=self._extract_config(agent_configs, "tracking")
            )
            
            self.agents["support_agent"] = SupportAgent(
                ollama=self.ollama,
                chroma=self.chroma,
                config=self._extract_config(agent_configs, "support")
            )
            
            self.agents["invoice_agent"] = InvoiceAgent(
                ollama=self.ollama,
                chroma=self.chroma,
                config=self._extract_config(agent_configs, "invoice")
            )
            
            self.agents["fallback_agent"] = FallbackAgent(
                ollama=self.ollama,
                postgres=self.postgres,
                config={}
            )
            
            self.agents["farewell_agent"] = FarewellAgent(
                ollama=self.ollama,
                postgres=self.postgres,
                config={}
            )
            
            logger.info("All agents initialized successfully")
            return self.agents
            
        except Exception as e:
            logger.error(f"Error initializing agents: {e}")
            raise
    
    def _get_supervisor_config(self) -> Dict[str, Any]:
        """Extract supervisor configuration"""
        supervisor_config = self.config.get("supervisor", {})
        if hasattr(supervisor_config, "model_dump"):
            return supervisor_config.model_dump()
        return supervisor_config
    
    def _extract_config(self, agent_configs: Dict, agent_name: str) -> Dict[str, Any]:
        """Extract configuration for a specific agent"""
        config = agent_configs.get(agent_name, {})
        if hasattr(config, "model_dump"):
            return config.model_dump()
        return {}
    
    def get_agent(self, agent_name: str) -> Any:
        """Get a specific agent instance"""
        return self.agents.get(agent_name)
    
    def get_all_agents(self) -> Dict[str, Any]:
        """Get all agent instances"""
        return self.agents