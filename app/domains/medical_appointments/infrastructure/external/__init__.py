# ============================================================================
# SCOPE: INFRASTRUCTURE LAYER (Medical Appointments)
# Description: External service clients module.
# ============================================================================
"""External Service Clients.

Provides clients for external medical systems.

Components:
- HCWebSOAPClient: SOAP client for HCWeb medical system
- SoapRequestBuilder: SOAP envelope builder
- SoapResponseParser: SOAP response parser
"""

from .hcweb import HCWebSOAPClient, SoapRequestBuilder, SoapResponseParser

__all__ = [
    "HCWebSOAPClient",
    "SoapRequestBuilder",
    "SoapResponseParser",
]
