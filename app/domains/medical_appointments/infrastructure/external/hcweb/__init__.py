# ============================================================================
# SCOPE: INFRASTRUCTURE LAYER (Medical Appointments)
# Description: HCWeb SOAP client module.
# ============================================================================
"""HCWeb SOAP Client Module.

Provides async SOAP client for interacting with HCWeb medical system.

Components:
- HCWebSOAPClient: Main client implementing IMedicalSystemClient
- SoapRequestBuilder: Builds SOAP XML envelopes
- SoapResponseParser: Parses SOAP XML responses
- MethodRegistry: Extensible method configuration (OCP)

Usage:
    from app.domains.medical_appointments.infrastructure.external.hcweb import (
        HCWebSOAPClient,
    )

    client = HCWebSOAPClient(
        base_url="http://host/WsHcweb.asmx",
        institution_id="123",
    )
    result = await client.buscar_paciente_dni("12345678")

OCP Extension:
    from app.domains.medical_appointments.infrastructure.external.hcweb import (
        MethodRegistry,
        get_default_registry,
    )

    # Extend without modifying client
    registry = get_default_registry()
    registry.register("nuevo_metodo", "NuevoMetodoSOAP", ["param1"])
"""

from .client import HCWebSOAPClient
from .method_registry import MethodConfig, MethodRegistry, get_default_registry
from .response_parser import SoapResponseParser
from .soap_builder import SoapRequestBuilder

__all__ = [
    "HCWebSOAPClient",
    "SoapRequestBuilder",
    "SoapResponseParser",
    "MethodRegistry",
    "MethodConfig",
    "get_default_registry",
]
