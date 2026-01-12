# ============================================================================
# SCOPE: INFRASTRUCTURE LAYER (Medical Appointments)
# Description: SOAP response parser for HCWeb.
# ============================================================================
"""SOAP Response Parser.

Parses SOAP XML responses from HCWeb API.
Single responsibility: XML response parsing.
"""

import logging
from typing import Any
from xml.etree import ElementTree

from ....application.ports import ExternalResponse

logger = logging.getLogger(__name__)


class SoapResponseParser:
    """Parses SOAP XML responses.

    Extracts data from SOAP envelopes and handles error detection.

    Attributes:
        max_depth: Maximum recursion depth for XML parsing (default: 10).
    """

    def __init__(self, max_depth: int = 10) -> None:
        """Initialize parser.

        Args:
            max_depth: Maximum recursion depth for XML parsing.
                       Prevents stack overflow on malformed responses.
        """
        self.max_depth = max_depth

    def parse(self, xml_text: str, method: str) -> ExternalResponse:
        """Parse a SOAP response.

        Args:
            xml_text: Raw XML response text.
            method: SOAP method name (used to find result element).

        Returns:
            ExternalResponse with parsed data or error.
        """
        try:
            root = ElementTree.fromstring(xml_text)
            result_elem = self._find_result_element(root, method)

            if result_elem is None:
                fault = self._extract_soap_fault(root)
                if fault:
                    return ExternalResponse.error("SOAP_FAULT", fault)
                return ExternalResponse.error(
                    "PARSE_ERROR",
                    "No se encontró resultado en respuesta SOAP",
                )

            error = self._check_result_errors(result_elem)
            if error:
                return error

            data = self._element_to_dict(result_elem)
            return ExternalResponse.ok(data)

        except ElementTree.ParseError as e:
            logger.error(f"Error parsing SOAP XML: {e}")
            return ExternalResponse.error("XML_PARSE_ERROR", str(e))

    def _find_result_element(
        self,
        root: ElementTree.Element,
        method: str,
    ) -> ElementTree.Element | None:
        """Find the result element in SOAP response.

        Args:
            root: XML root element.
            method: Method name.

        Returns:
            Result element or None.
        """
        result_tag = f"{method}Result"
        for elem in root.iter():
            tag_name = self._get_local_tag(elem.tag)
            if tag_name == result_tag:
                return elem
        return None

    def _extract_soap_fault(self, root: ElementTree.Element) -> str | None:
        """Extract SOAP fault message if present.

        Args:
            root: XML root element.

        Returns:
            Fault message or None.
        """
        for elem in root.iter():
            tag_name = self._get_local_tag(elem.tag)
            if tag_name == "Fault":
                for child in elem:
                    child_tag = self._get_local_tag(child.tag)
                    if child_tag == "faultstring":
                        return child.text or ""
        return None

    def _check_result_errors(
        self,
        result_elem: ElementTree.Element,
    ) -> ExternalResponse | None:
        """Check for errors in result element.

        Args:
            result_elem: Result XML element.

        Returns:
            Error response if errors found, None otherwise.
        """
        contains_errors = self._find_child_text(result_elem, "ContainsErrors")
        if contains_errors and contains_errors.lower() == "true":
            error_msg = self._find_child_text(result_elem, "ErrorMessage") or "Error desconocido"
            error_code = self._find_child_text(result_elem, "ErrorCode") or "HCWEB_ERROR"
            return ExternalResponse.error(error_code, error_msg)
        return None

    def _find_child_text(
        self,
        elem: ElementTree.Element,
        tag_name: str,
    ) -> str | None:
        """Find text content of a child element.

        Args:
            elem: Parent element.
            tag_name: Child tag name to find.

        Returns:
            Text content or None.
        """
        for child in elem.iter():
            child_tag = self._get_local_tag(child.tag)
            if child_tag == tag_name:
                return child.text
        return None

    def _element_to_dict(
        self,
        elem: ElementTree.Element,
        current_depth: int = 0,
    ) -> dict[str, Any]:
        """Convert XML element to dictionary recursively.

        Args:
            elem: XML element.
            current_depth: Current recursion depth.

        Returns:
            Dictionary representation.

        Note:
            Recursion is limited by max_depth to prevent stack overflow.
        """
        result: dict[str, Any] = {}

        # Safety check for maximum depth
        if current_depth >= self.max_depth:
            logger.warning(
                f"Max parsing depth ({self.max_depth}) reached. "
                f"Truncating at element: {self._get_local_tag(elem.tag)}"
            )
            return {"_truncated": True, "_tag": self._get_local_tag(elem.tag)}

        for child in elem:
            tag = self._get_local_tag(child.tag)

            if len(child) > 0:
                child_dict = self._element_to_dict(child, current_depth + 1)
                if tag in result:
                    if not isinstance(result[tag], list):
                        result[tag] = [result[tag]]
                    result[tag].append(child_dict)
                else:
                    result[tag] = child_dict
            else:
                result[tag] = child.text

        return result

    @staticmethod
    def _get_local_tag(tag: str) -> str:
        """Get local name from qualified XML tag.

        Args:
            tag: Qualified tag name.

        Returns:
            Local tag name without namespace.
        """
        return tag.split("}")[-1] if "}" in tag else tag
