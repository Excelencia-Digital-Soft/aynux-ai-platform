# ============================================================================
# SCOPE: INFRASTRUCTURE LAYER (Medical Appointments)
# Description: SOAP request builder for HCWeb.
# ============================================================================
"""SOAP Request Builder.

Builds SOAP XML envelopes for HCWeb API calls.
Single responsibility: XML envelope construction.
"""

from typing import Any


class SoapRequestBuilder:
    """Builds SOAP XML envelopes.

    Handles XML escaping and parameter serialization for SOAP requests.
    """

    NAMESPACE = "http://tempuri.org/"

    def build_envelope(self, method: str, params: dict[str, Any]) -> str:
        """Build a SOAP envelope for a method call.

        Args:
            method: SOAP method name.
            params: Dictionary of parameters.

        Returns:
            Complete SOAP XML envelope as string.
        """
        params_xml = "\n      ".join(self._serialize_param(k, v) for k, v in params.items())

        return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <soap:Body>
    <{method} xmlns="{self.NAMESPACE}">
      {params_xml}
    </{method}>
  </soap:Body>
</soap:Envelope>"""

    def _serialize_param(self, key: str, value: Any) -> str:
        """Serialize a parameter to XML.

        Args:
            key: Parameter name.
            value: Parameter value.

        Returns:
            XML string for the parameter.
        """
        if value is None:
            return f'<{key} xsi:nil="true" />'
        if isinstance(value, list):
            items = "".join(f"<int>{item}</int>" for item in value)
            return f"<{key}>{items}</{key}>"
        if isinstance(value, bool):
            return f"<{key}>{str(value).lower()}</{key}>"
        return f"<{key}>{self._escape_xml(value)}</{key}>"

    @staticmethod
    def _escape_xml(value: Any) -> str:
        """Escape XML special characters.

        Args:
            value: Value to escape.

        Returns:
            XML-safe string.
        """
        if value is None:
            return ""
        s = str(value)
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )
