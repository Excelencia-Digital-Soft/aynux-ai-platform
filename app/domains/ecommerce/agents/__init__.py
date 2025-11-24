"""
E-commerce Domain Agents

Agents specific to the e-commerce domain.
All agents implement IAgent interface from app.core.interfaces.agent
"""

from .product_agent import ProductAgent

__all__ = [
    "ProductAgent",
]
