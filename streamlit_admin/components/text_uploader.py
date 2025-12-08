"""
Text Uploader Component.

Reusable text document creation component for both global and tenant contexts.
"""

from typing import Callable, Literal

import streamlit as st

from streamlit_admin.components.document_types import get_type_options


def render_text_uploader(
    *,
    context: Literal["global", "tenant"],
    org_id: str | None = None,
    on_success: Callable[[dict], None] | None = None,
    key_prefix: str = "text",
    language: Literal["en", "es"] = "es",
    min_content_length: int = 50,
) -> dict | None:
    """
    Render text document creation form.

    Args:
        context: Either "global" or "tenant"
        org_id: Required for tenant context
        on_success: Callback function called with result on success
        key_prefix: Prefix for Streamlit widget keys
        language: UI language
        min_content_length: Minimum content length required

    Returns:
        Creation result dict or None
    """
    # Validate context requirements
    if context == "tenant" and not org_id:
        st.error("Organization ID required for tenant context")
        return None

    # Labels based on language
    labels = _get_labels(language)

    # Section header
    st.subheader(labels["header"])

    # Use form for better UX
    with st.form(f"{key_prefix}_form", clear_on_submit=True):
        title = st.text_input(
            labels["title_label"],
            placeholder=labels["title_placeholder"],
            key=f"{key_prefix}_title",
        )

        content = st.text_area(
            labels["content_label"],
            height=200,
            placeholder=labels["content_placeholder"],
            key=f"{key_prefix}_content",
        )

        col1, col2 = st.columns(2)

        with col1:
            type_options = get_type_options(context, language=language)
            type_keys = [opt[0] for opt in type_options]
            type_labels = [opt[1] for opt in type_options]

            document_type = st.selectbox(
                labels["type_label"],
                options=type_keys,
                format_func=lambda x: type_labels[type_keys.index(x)],
                index=0,
                key=f"{key_prefix}_type",
            )

            category = st.text_input(
                labels["category_label"],
                placeholder=labels["category_placeholder"],
                key=f"{key_prefix}_category",
            )

        with col2:
            tags_input = st.text_input(
                labels["tags_label"],
                placeholder=labels["tags_placeholder"],
                key=f"{key_prefix}_tags",
            )

            active = st.checkbox(
                labels["active_label"],
                value=True,
                key=f"{key_prefix}_active",
            )

        submitted = st.form_submit_button(labels["button"], type="primary")

        if submitted:
            # Validation
            if not title:
                st.error(labels["error_title_required"])
                return None

            if not content:
                st.error(labels["error_content_required"])
                return None

            if len(content) < min_content_length:
                st.error(labels["error_content_short"].format(min=min_content_length))
                return None

            # Parse tags
            tags = [t.strip() for t in tags_input.split(",") if t.strip()] if tags_input else []

            # Build data
            data = {
                "title": title,
                "content": content,
                "document_type": document_type,
                "tags": tags,
                "active": active,
            }

            if category:
                data["category"] = category

            # Upload
            with st.spinner(labels["creating"]):
                result = _create_document(
                    context=context,
                    org_id=org_id,
                    data=data,
                )

                if result:
                    st.success(f"{labels['success']} ID: {result.get('id')}")
                    if result.get("has_embedding"):
                        st.info(labels["embedding_success"])

                    if on_success:
                        on_success(result)

                    return result

    return None


def _create_document(
    *,
    context: Literal["global", "tenant"],
    org_id: str | None,
    data: dict,
) -> dict | None:
    """Internal function to call appropriate create API."""
    if context == "global":
        from lib.api_client import upload_text

        return upload_text(
            content=data["content"],
            title=data["title"],
            document_type=data["document_type"],
            category=data.get("category"),
            tags=data.get("tags", []),
        )
    else:
        from lib.api_client import create_tenant_document

        return create_tenant_document(org_id=org_id, data=data)


def _get_labels(language: Literal["en", "es"]) -> dict:
    """Get UI labels based on language."""
    if language == "es":
        return {
            "header": "Crear Documento de Texto",
            "title_label": "Titulo *",
            "title_placeholder": "ej: Politica de devoluciones",
            "content_label": "Contenido *",
            "content_placeholder": "Escribe el contenido del documento aqui...",
            "type_label": "Tipo de documento",
            "category_label": "Categoria (opcional)",
            "category_placeholder": "ej: politicas",
            "tags_label": "Tags (separados por coma)",
            "tags_placeholder": "ej: devolucion, garantia",
            "active_label": "Activo",
            "button": "Crear Documento",
            "creating": "Creando documento...",
            "success": "Documento creado!",
            "embedding_success": "Embedding generado correctamente",
            "error_title_required": "El titulo es requerido",
            "error_content_required": "El contenido es requerido",
            "error_content_short": "El contenido debe tener al menos {min} caracteres",
        }
    else:
        return {
            "header": "Create Text Document",
            "title_label": "Title *",
            "title_placeholder": "e.g.: Return Policy",
            "content_label": "Content *",
            "content_placeholder": "Write the document content here...",
            "type_label": "Document Type",
            "category_label": "Category (optional)",
            "category_placeholder": "e.g.: policies",
            "tags_label": "Tags (comma-separated)",
            "tags_placeholder": "e.g.: return, warranty",
            "active_label": "Active",
            "button": "Create Document",
            "creating": "Creating document...",
            "success": "Document created!",
            "embedding_success": "Embedding generated successfully",
            "error_title_required": "Title is required",
            "error_content_required": "Content is required",
            "error_content_short": "Content must have at least {min} characters",
        }


__all__ = ["render_text_uploader"]
