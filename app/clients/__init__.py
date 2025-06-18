"""
Clientes para APIs externas
"""

from .dux_api_client import DuxApiClient, DuxApiClientFactory

__all__ = [
    "DuxApiClient",
    "DuxApiClientFactory",
]