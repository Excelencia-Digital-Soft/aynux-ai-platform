"""
WhatsApp Catalog (Deprecated)

This module is deprecated. Use catalog_service.py instead.
"""

# Re-export from catalog_service for backwards compatibility
from app.integrations.whatsapp.catalog_service import (
    DefaultCatalogDecisionEngine,
    DefaultCatalogRepository,
    ICatalogDecisionEngine,
    ICatalogRepository,
    WhatsAppCatalogService,
)

__all__ = [
    "WhatsAppCatalogService",
    "ICatalogRepository",
    "ICatalogDecisionEngine",
    "DefaultCatalogRepository",
    "DefaultCatalogDecisionEngine",
]
