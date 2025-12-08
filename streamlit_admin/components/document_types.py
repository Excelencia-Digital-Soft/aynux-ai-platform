"""
Document Types - Unified document type definitions for global and tenant contexts.

This module provides a single source of truth for document type definitions,
supporting both global (system-wide) and tenant-specific contexts.
"""

from typing import Literal

# Unified document types with metadata
DOCUMENT_TYPES: dict[str, dict] = {
    # Common types (available in both contexts)
    "general": {
        "label": "General",
        "label_es": "General",
        "icon": "📄",
        "description": "General purpose documents",
        "global": True,
        "tenant": True,
    },
    "faq": {
        "label": "FAQ",
        "label_es": "Preguntas Frecuentes",
        "icon": "❓",
        "description": "Frequently asked questions",
        "global": True,
        "tenant": True,
    },
    # Global-only types (Excelencia knowledge base)
    "mission_vision": {
        "label": "Mission & Vision",
        "label_es": "Mision y Vision",
        "icon": "🎯",
        "description": "Company mission and vision statements",
        "global": True,
        "tenant": False,
    },
    "contact_info": {
        "label": "Contact Info",
        "label_es": "Informacion de Contacto",
        "icon": "📞",
        "description": "Contact information and locations",
        "global": True,
        "tenant": False,
    },
    "software_catalog": {
        "label": "Software Catalog",
        "label_es": "Catalogo de Software",
        "icon": "💻",
        "description": "Software products and services catalog",
        "global": True,
        "tenant": False,
    },
    "clients": {
        "label": "Clients",
        "label_es": "Clientes",
        "icon": "👥",
        "description": "Client information and testimonials",
        "global": True,
        "tenant": False,
    },
    "success_stories": {
        "label": "Success Stories",
        "label_es": "Casos de Exito",
        "icon": "🏆",
        "description": "Success stories and case studies",
        "global": True,
        "tenant": False,
    },
    # Tenant-only types
    "guide": {
        "label": "Guide",
        "label_es": "Guia",
        "icon": "📖",
        "description": "User guides and manuals",
        "global": False,
        "tenant": True,
    },
    "policy": {
        "label": "Policy",
        "label_es": "Politica",
        "icon": "📜",
        "description": "Company policies and procedures",
        "global": False,
        "tenant": True,
    },
    "product_info": {
        "label": "Product Info",
        "label_es": "Info de Producto",
        "icon": "🛒",
        "description": "Product information and specifications",
        "global": False,
        "tenant": True,
    },
    "uploaded_pdf": {
        "label": "Uploaded PDF",
        "label_es": "PDF Subido",
        "icon": "📑",
        "description": "Uploaded PDF documents",
        "global": False,
        "tenant": True,
    },
    "training": {
        "label": "Training",
        "label_es": "Capacitacion",
        "icon": "🎓",
        "description": "Training materials and tutorials",
        "global": False,
        "tenant": True,
    },
    "support": {
        "label": "Support",
        "label_es": "Soporte",
        "icon": "🛟",
        "description": "Support documentation and troubleshooting",
        "global": False,
        "tenant": True,
    },
}


def get_types_for_context(
    context: Literal["global", "tenant"],
    *,
    include_common: bool = True,
) -> list[str]:
    """
    Get document types available for a specific context.

    Args:
        context: Either "global" or "tenant"
        include_common: Whether to include types available in both contexts

    Returns:
        List of document type keys
    """
    types = []
    for key, config in DOCUMENT_TYPES.items():
        if context == "global" and config["global"]:
            types.append(key)
        elif context == "tenant" and config["tenant"]:
            types.append(key)
    return types


def get_type_options(
    context: Literal["global", "tenant"],
    *,
    language: Literal["en", "es"] = "en",
) -> list[tuple[str, str]]:
    """
    Get document type options for selectbox/dropdown.

    Args:
        context: Either "global" or "tenant"
        language: Language for labels ("en" or "es")

    Returns:
        List of (key, label) tuples
    """
    types = get_types_for_context(context)
    label_key = "label" if language == "en" else "label_es"

    return [
        (key, f"{DOCUMENT_TYPES[key]['icon']} {DOCUMENT_TYPES[key][label_key]}")
        for key in types
    ]


def get_type_label(
    doc_type: str,
    *,
    language: Literal["en", "es"] = "en",
    include_icon: bool = True,
) -> str:
    """
    Get the display label for a document type.

    Args:
        doc_type: Document type key
        language: Language for label
        include_icon: Whether to include the icon

    Returns:
        Display label string
    """
    if doc_type not in DOCUMENT_TYPES:
        return doc_type

    config = DOCUMENT_TYPES[doc_type]
    label_key = "label" if language == "en" else "label_es"
    label = config[label_key]

    if include_icon:
        return f"{config['icon']} {label}"
    return label


def get_type_icon(doc_type: str) -> str:
    """Get the icon for a document type."""
    if doc_type not in DOCUMENT_TYPES:
        return "📄"
    return DOCUMENT_TYPES[doc_type]["icon"]


__all__ = [
    "DOCUMENT_TYPES",
    "get_types_for_context",
    "get_type_options",
    "get_type_label",
    "get_type_icon",
]
