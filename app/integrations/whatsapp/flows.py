"""
WhatsApp Flows (Deprecated)

This module is deprecated. Use flows_service.py instead.
"""

# Re-export from flows_service for backwards compatibility
from app.integrations.whatsapp.flows_service import (
    WhatsAppFlowsService,
    IFlowRepository,
    IFlowHandler,
    InMemoryFlowRepository,
    DefaultOrderFormHandler,
    FlowType,
)

__all__ = [
    "WhatsAppFlowsService",
    "IFlowRepository",
    "IFlowHandler",
    "InMemoryFlowRepository",
    "DefaultOrderFormHandler",
    "FlowType",
]
