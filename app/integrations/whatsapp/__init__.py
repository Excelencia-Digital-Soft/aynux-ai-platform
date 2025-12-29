"""
WhatsApp Integration Services

Integration services for WhatsApp Business API:
- WhatsAppService: Core API client for sending messages
- WhatsAppCatalogService: Product catalog operations
- WhatsAppFlowsService: WhatsApp Flows management

Following Clean Architecture, these are infrastructure services
that integrate with external WhatsApp Business API.
"""

from app.integrations.whatsapp.catalog_service import (
    DefaultCatalogDecisionEngine,
    DefaultCatalogRepository,
    ICatalogDecisionEngine,
    ICatalogRepository,
    WhatsAppCatalogService,
)
from app.integrations.whatsapp.flows_service import (
    DefaultOrderFormHandler,
    FlowType,
    IFlowHandler,
    IFlowRepository,
    InMemoryFlowRepository,
    WhatsAppFlowsService,
)
from app.integrations.whatsapp.service import (
    ChattigoMessagingService,
    WhatsAppService,
    get_messaging_service,
)

__all__ = [
    # Core Service
    "WhatsAppService",
    # Chattigo Support
    "ChattigoMessagingService",
    "get_messaging_service",
    # Catalog Service
    "WhatsAppCatalogService",
    "ICatalogRepository",
    "ICatalogDecisionEngine",
    "DefaultCatalogRepository",
    "DefaultCatalogDecisionEngine",
    # Flows Service
    "WhatsAppFlowsService",
    "IFlowRepository",
    "IFlowHandler",
    "InMemoryFlowRepository",
    "DefaultOrderFormHandler",
    "FlowType",
]
