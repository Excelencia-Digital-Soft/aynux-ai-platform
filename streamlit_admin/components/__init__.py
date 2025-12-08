"""
Streamlit Admin Components Library.

Reusable components for document management across global and tenant contexts.
"""

from streamlit_admin.components.document_browser import render_document_browser
from streamlit_admin.components.document_types import (
    DOCUMENT_TYPES,
    get_type_icon,
    get_type_label,
    get_type_options,
    get_types_for_context,
)
from streamlit_admin.components.pdf_uploader import render_pdf_uploader
from streamlit_admin.components.text_uploader import render_text_uploader

__all__ = [
    # Document types
    "DOCUMENT_TYPES",
    "get_types_for_context",
    "get_type_options",
    "get_type_label",
    "get_type_icon",
    # Components
    "render_pdf_uploader",
    "render_text_uploader",
    "render_document_browser",
]
