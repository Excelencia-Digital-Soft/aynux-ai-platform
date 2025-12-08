"""
PDF Uploader Component.

Reusable PDF upload component for both global and tenant contexts.
"""

from typing import Callable, Literal

import streamlit as st

from streamlit_admin.components.document_types import get_type_options


def render_pdf_uploader(
    *,
    context: Literal["global", "tenant"],
    org_id: str | None = None,
    on_success: Callable[[dict], None] | None = None,
    key_prefix: str = "pdf",
    language: Literal["en", "es"] = "es",
) -> dict | None:
    """
    Render PDF upload form with appropriate API calls.

    Args:
        context: Either "global" or "tenant"
        org_id: Required for tenant context
        on_success: Callback function called with result on success
        key_prefix: Prefix for Streamlit widget keys
        language: UI language

    Returns:
        Upload result dict or None
    """
    # Validate context requirements
    if context == "tenant" and not org_id:
        st.error("Organization ID required for tenant context")
        return None

    # Labels based on language
    labels = _get_labels(language)

    # Section header
    st.subheader(labels["header"])

    # File uploader
    uploaded_file = st.file_uploader(
        labels["file_label"],
        type=["pdf"],
        help=labels["file_help"],
        key=f"{key_prefix}_file_uploader",
    )

    if not uploaded_file:
        return None

    # Form fields
    col1, col2 = st.columns(2)

    with col1:
        title = st.text_input(
            labels["title_label"],
            value=uploaded_file.name.replace(".pdf", ""),
            help=labels["title_help"],
            key=f"{key_prefix}_title",
        )

        type_options = get_type_options(context, language=language)
        type_keys = [opt[0] for opt in type_options]
        type_labels = [opt[1] for opt in type_options]

        # Default to "uploaded_pdf" for tenant, "general" for global
        default_type = "uploaded_pdf" if context == "tenant" else "general"
        default_idx = type_keys.index(default_type) if default_type in type_keys else 0

        document_type = st.selectbox(
            labels["type_label"],
            options=type_keys,
            format_func=lambda x: type_labels[type_keys.index(x)],
            index=default_idx,
            key=f"{key_prefix}_type",
        )

    with col2:
        category = st.text_input(
            labels["category_label"],
            placeholder=labels["category_placeholder"],
            key=f"{key_prefix}_category",
        )

        tags = st.text_input(
            labels["tags_label"],
            placeholder=labels["tags_placeholder"],
            key=f"{key_prefix}_tags",
        )

    # Upload button
    if st.button(labels["button"], type="primary", key=f"{key_prefix}_upload_btn"):
        with st.spinner(labels["uploading"]):
            result = _upload_pdf(
                context=context,
                org_id=org_id,
                file=uploaded_file,
                title=title,
                document_type=document_type,
                category=category if category else None,
                tags=tags if tags else None,
            )

            if result:
                st.success(f"{labels['success']} ID: {result.get('id')}")
                if result.get("has_embedding"):
                    st.info(labels["embedding_success"])

                if on_success:
                    on_success(result)

                return result

    return None


def _upload_pdf(
    *,
    context: Literal["global", "tenant"],
    org_id: str | None,
    file,
    title: str | None,
    document_type: str,
    category: str | None,
    tags: str | None,
) -> dict | None:
    """Internal function to call appropriate upload API."""
    if context == "global":
        from lib.api_client import upload_pdf

        return upload_pdf(
            file=file,
            title=title,
            document_type=document_type,
            category=category,
            tags=tags,
        )
    else:
        from lib.api_client import upload_tenant_pdf

        return upload_tenant_pdf(
            org_id=org_id,
            file=file,
            title=title,
            document_type=document_type,
            category=category,
            tags=tags,
        )


def _get_labels(language: Literal["en", "es"]) -> dict:
    """Get UI labels based on language."""
    if language == "es":
        return {
            "header": "Subir PDF",
            "file_label": "Selecciona un archivo PDF",
            "file_help": "Maximo 10MB por archivo",
            "title_label": "Titulo (opcional)",
            "title_help": "Si no se especifica, se usara el nombre del archivo",
            "type_label": "Tipo de documento",
            "category_label": "Categoria (opcional)",
            "category_placeholder": "ej: manuales, politicas, productos",
            "tags_label": "Tags (separados por coma)",
            "tags_placeholder": "ej: manual, usuario, inicio",
            "button": "Subir PDF",
            "uploading": "Subiendo y procesando PDF...",
            "success": "PDF subido exitosamente!",
            "embedding_success": "Embedding generado correctamente",
        }
    else:
        return {
            "header": "Upload PDF",
            "file_label": "Choose a PDF file",
            "file_help": "Maximum 10MB per file",
            "title_label": "Title (optional)",
            "title_help": "If not specified, the file name will be used",
            "type_label": "Document Type",
            "category_label": "Category (optional)",
            "category_placeholder": "e.g.: manuals, policies, products",
            "tags_label": "Tags (comma-separated)",
            "tags_placeholder": "e.g.: manual, user, getting-started",
            "button": "Upload PDF",
            "uploading": "Uploading and processing PDF...",
            "success": "PDF uploaded successfully!",
            "embedding_success": "Embedding generated successfully",
        }


__all__ = ["render_pdf_uploader"]
