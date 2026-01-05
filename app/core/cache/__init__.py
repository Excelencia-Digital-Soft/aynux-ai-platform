"""
Cache Module - In-memory caching for frequently accessed data.

Provides TTL-based caching for:
- Agent enabled keys (agent_cache)
"""

from .agent_cache import AgentCache, agent_cache

__all__ = [
    "AgentCache",
    "agent_cache",
]
