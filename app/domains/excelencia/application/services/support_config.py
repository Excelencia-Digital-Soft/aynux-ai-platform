"""
Support configuration for Excelencia domain.

Centralizes configuration that was previously hardcoded in the agent.
"""


class SupportConfig:
    """Configuration for support services."""

    # Document types to search for support queries
    DOCUMENT_TYPES: list[str] = [
        "support_faq",
        "support_guide",
        "support_contact",
        "support_training",
        "support_module",
        "faq",
    ]

    # Excelencia Software modules
    MODULES: dict[str, str] = {
        "inventario": "Modulo de Inventario y Control de Stock",
        "facturacion": "Modulo de Facturacion Electronica (CFDI)",
        "contabilidad": "Modulo de Contabilidad",
        "nomina": "Modulo de Nomina",
        "compras": "Modulo de Compras",
        "ventas": "Modulo de Ventas (POS)",
        "crm": "Modulo CRM",
        "produccion": "Modulo de Produccion",
        "bancos": "Modulo de Bancos y Conciliacion",
        "reportes": "Modulo de Reportes y BI",
    }

    # Urgency keywords
    HIGH_URGENCY_KEYWORDS: list[str] = [
        "urgente",
        "critico",
        "no funciona",
        "se cayo",
        "bloqueado",
    ]

    @classmethod
    def detect_module(cls, message: str) -> str | None:
        """Detect mentioned module from message."""
        message_lower = message.lower()
        for mod_key in cls.MODULES:
            if mod_key in message_lower:
                return mod_key
        return None

    @classmethod
    def detect_urgency(cls, message: str) -> str:
        """Detect urgency level from message."""
        message_lower = message.lower()
        if any(word in message_lower for word in cls.HIGH_URGENCY_KEYWORDS):
            return "high"
        return "medium"

    @classmethod
    def get_module_name(cls, module_key: str) -> str:
        """Get full module name from key."""
        return cls.MODULES.get(module_key, module_key)
