# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Configuration dataclass for LangGraph nodes
# ============================================================================
"""Node configuration for Medical Appointments agents.

Provides typed configuration for LangGraph nodes, replacing
the weakly-typed dict-based configuration.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NodeConfig:
    """Typed configuration for LangGraph nodes.

    Provides type-safe access to configuration values, replacing
    the weakly-typed dict[str, Any] pattern.

    Attributes:
        institution: Institution key (e.g., "patologia_digestiva").
        institution_name: Human-readable institution name.
        institution_id: External system institution ID.
        soap_url: SOAP API endpoint URL.
        did: WhatsApp DID for the institution.
        timezone: Timezone for date/time operations.
        timeout_seconds: API call timeout in seconds.
        connection_type: Connection type ("soap" or "rest").

    Example:
        >>> config = NodeConfig.from_dict({"institution": "test", ...})
        >>> config.institution
        "test"
    """

    institution: str
    institution_name: str
    institution_id: str
    soap_url: str
    did: str
    timezone: str = "America/Argentina/Buenos_Aires"
    timeout_seconds: int = 30
    connection_type: str = "soap"

    # Required fields that must be present in input dict
    _REQUIRED_FIELDS: tuple[str, ...] = field(
        default=("institution", "institution_name", "institution_id", "soap_url", "did"),
        init=False,
        repr=False,
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NodeConfig":
        """Create NodeConfig from a dictionary with validation.

        Args:
            data: Configuration dictionary.

        Returns:
            NodeConfig instance.

        Raises:
            ValueError: If required fields are missing.

        Example:
            >>> config = NodeConfig.from_dict({
            ...     "institution": "patologia_digestiva",
            ...     "institution_name": "Patología Digestiva",
            ...     "institution_id": "123",
            ...     "soap_url": "http://host/WsHcweb.asmx",
            ...     "did": "5492645668671",
            ... })
        """
        required = ("institution", "institution_name", "institution_id", "soap_url", "did")
        missing = [k for k in required if not data.get(k)]

        if missing:
            raise ValueError(f"Missing required config keys: {missing}")

        return cls(
            institution=str(data["institution"]),
            institution_name=str(data["institution_name"]),
            institution_id=str(data["institution_id"]),
            soap_url=str(data["soap_url"]),
            did=str(data["did"]),
            timezone=str(data.get("timezone", "America/Argentina/Buenos_Aires")),
            timeout_seconds=int(data.get("timeout_seconds", 30)),
            connection_type=str(data.get("connection_type", "soap")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert NodeConfig back to dictionary.

        Returns:
            Dictionary representation of the config.
        """
        return {
            "institution": self.institution,
            "institution_name": self.institution_name,
            "institution_id": self.institution_id,
            "soap_url": self.soap_url,
            "did": self.did,
            "timezone": self.timezone,
            "timeout_seconds": self.timeout_seconds,
            "connection_type": self.connection_type,
        }


@dataclass(frozen=True)
class WhatsAppConfig:
    """WhatsApp-specific configuration.

    Attributes:
        flow_id: WhatsApp Flow ID for registration.
        screen: Default screen for flow.
        message_max_length: Maximum message length.
    """

    flow_id: str = "2244089509373557"
    screen: str = "Screen_A"
    message_max_length: int = 4096

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WhatsAppConfig":
        """Create WhatsAppConfig from dictionary."""
        return cls(
            flow_id=str(data.get("flow_id", cls.flow_id)),
            screen=str(data.get("screen", cls.screen)),
            message_max_length=int(data.get("message_max_length", cls.message_max_length)),
        )
