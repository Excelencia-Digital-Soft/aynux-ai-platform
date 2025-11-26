"""
Shared Agents Module

Contains domain-agnostic agents that can be used across multiple domains.
Agents follow BaseAgent pattern for compatibility with AgentFactory.
"""

from app.domains.shared.agents.data_insights_agent import DataInsightsAgent
from app.domains.shared.agents.excelencia_agent import ExcelenciaAgent
from app.domains.shared.agents.fallback_agent import FallbackAgent
from app.domains.shared.agents.farewell_agent import FarewellAgent
from app.domains.shared.agents.greeting_agent import GreetingAgent
from app.domains.shared.agents.supervisor_agent import SupervisorAgent
from app.domains.shared.agents.support_agent import SupportAgent

__all__ = [
    "DataInsightsAgent",
    "ExcelenciaAgent",
    "FallbackAgent",
    "FarewellAgent",
    "GreetingAgent",
    "SupervisorAgent",
    "SupportAgent",
]
