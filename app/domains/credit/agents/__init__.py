"""
Credit Domain Agents

Agents specific to the credit domain.
All agents implement IAgent interface from app.core.interfaces.agent
"""

from .credit_agent import CreditAgent

__all__ = [
    "CreditAgent",
]
