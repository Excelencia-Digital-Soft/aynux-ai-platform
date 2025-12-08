"""
Document Browser Component.

Reusable document browser/manager component for both global and tenant contexts.
Includes listing, filtering, pagination, and document actions.
"""

from typing import Callable, Literal

import streamlit as st

from streamlit_admin.components.document_types import (
    get_type_label,
    get_type_options,
)


def render_document_browser(
    *,
    context: Literal["global", "tenant"],
    org_id: str | None = None,
    key_prefix: str = "browser",
    language: Literal["en", "es"] = "es",
    show_search: bool = True,
    show_filters: bool = True,
    editable: bool = True,
    page_size_options: list[int] | None = None,
    on_delete: Callable[[str], None] | None = None,
) -> None:
    """
    Render document browser with filtering, pagination, and actions.

    Args:
        context: Either "global" or "tenant"
        org_id: Required for tenant context
        key_prefix: Prefix for Streamlit widget keys
        language: UI language
        show_search: Whether to show semantic search
        show_filters: Whether to show type/category filters
        editable: Whether to allow edit/delete actions
        page_size_options: Page size options for pagination
        on_delete: Optional callback when document is deleted
    """
    # Validate context requirements
    if context == "tenant" and not org_id:
        st.error("Organization ID required for tenant context")
        return

    # Labels based on language
    labels = _get_labels(language)

    if page_size_options is None:
        page_size_options = [10, 25, 50]

    # Section header
    st.subheader(labels["header"])

    # Search section (only for global context currently)
    if show_search and context == "global":
        _render_search_section(key_prefix, labels, language)
        st.markdown("---")

    # Filters
    filter_type = None
    filter_category = None
    filter_active = "Activos" if language == "es" else "Active"
    page_size = page_size_options[0]

    if show_filters:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            type_options = get_type_options(context, language=language)
            type_keys = [""] + [opt[0] for opt in type_options]
            type_labels_list = [labels["all"]] + [opt[1] for opt in type_options]

            filter_type_idx = st.selectbox(
                labels["filter_type"],
                options=range(len(type_keys)),
                format_func=lambda i: type_labels_list[i],
                index=0,
                key=f"{key_prefix}_filter_type",
            )
            filter_type = type_keys[filter_type_idx] if filter_type_idx > 0 else None

        with col2:
            filter_category = st.text_input(
                labels["filter_category"],
                placeholder=labels["filter_placeholder"],
                key=f"{key_prefix}_filter_category",
            )

        with col3:
            filter_active = st.selectbox(
                labels["filter_status"],
                options=[labels["all"], labels["active"], labels["inactive"]],
                index=1,
                key=f"{key_prefix}_filter_status",
            )

        with col4:
            page_size = st.selectbox(
                labels["per_page"],
                options=page_size_options,
                index=0,
                key=f"{key_prefix}_page_size",
            )

    # Pagination state
    page_key = f"{key_prefix}_page"
    if page_key not in st.session_state:
        st.session_state[page_key] = 0

    # Build query params
    doc_type = filter_type if filter_type else None
    category = filter_category if filter_category else None

    # Determine active_only based on filter
    if filter_active == labels["active"]:
        active_only = True
    elif filter_active == labels["inactive"]:
        active_only = False
    else:
        active_only = None

    # Fetch documents
    documents, total = _fetch_documents(
        context=context,
        org_id=org_id,
        document_type=doc_type,
        category=category,
        active_only=active_only,
        skip=st.session_state[page_key] * page_size,
        limit=page_size,
    )

    if not documents:
        st.info(labels["no_documents"])
        return

    st.caption(labels["showing"].format(count=len(documents), total=total))

    # Documents list
    for doc in documents:
        _render_document_item(
            doc=doc,
            context=context,
            org_id=org_id,
            key_prefix=key_prefix,
            language=language,
            editable=editable,
            labels=labels,
            on_delete=on_delete,
        )

    # Pagination controls
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.session_state[page_key] > 0:
            if st.button(labels["previous"], key=f"{key_prefix}_prev"):
                st.session_state[page_key] -= 1
                st.rerun()

    with col2:
        total_pages = (total + page_size - 1) // page_size
        st.markdown(
            f"**{labels['page']} {st.session_state[page_key] + 1} {labels['of']} {total_pages}**"
        )

    with col3:
        if (st.session_state[page_key] + 1) * page_size < total:
            if st.button(labels["next"], key=f"{key_prefix}_next"):
                st.session_state[page_key] += 1
                st.rerun()


def _render_search_section(
    key_prefix: str,
    labels: dict,
    language: str,
) -> None:
    """Render semantic search section."""
    col1, col2 = st.columns([3, 1])

    with col1:
        search_query = st.text_input(
            labels["search_label"],
            placeholder=labels["search_placeholder"],
            key=f"{key_prefix}_search_query",
        )

    with col2:
        max_results = st.number_input(
            labels["max_results"],
            min_value=1,
            max_value=20,
            value=5,
            key=f"{key_prefix}_max_results",
        )

    if st.button(labels["search_button"], key=f"{key_prefix}_search_btn"):
        if search_query:
            with st.spinner(labels["searching"]):
                from lib.api_client import search_knowledge

                results = search_knowledge(
                    query=search_query,
                    max_results=max_results,
                )

                if results:
                    st.success(labels["search_found"].format(count=len(results)))
                    for r in results:
                        score = r.get("score", 0)
                        title = r.get("title", "Sin titulo")
                        content = r.get("content", "")[:200]

                        with st.expander(f"📄 {title} (Score: {score:.3f})"):
                            st.text(content + "..." if len(content) == 200 else content)
                else:
                    st.warning(labels["no_results"])


def _render_document_item(
    *,
    doc: dict,
    context: str,
    org_id: str | None,
    key_prefix: str,
    language: str,
    editable: bool,
    labels: dict,
    on_delete: Callable | None,
) -> None:
    """Render a single document item with actions."""
    doc_id = doc.get("id")
    title = doc.get("title", labels["no_title"])
    doc_type = doc.get("document_type", "general")
    is_active = doc.get("active", True)
    has_embedding = doc.get("has_embedding", False)
    content = doc.get("content", "")
    content_preview = content[:100] + "..." if len(content) > 100 else content

    status_icon = "✅" if is_active else "❌"
    type_label = get_type_label(doc_type, language=language)

    with st.expander(f"{status_icon} {title} ({type_label})", expanded=False):
        col1, col2 = st.columns([3, 1])

        with col1:
            st.markdown(f"**ID:** `{doc_id}`")

            if doc.get("category"):
                st.markdown(f"**{labels['category']}:** {doc.get('category')}")

            tags = doc.get("tags", [])
            if tags:
                st.markdown(f"**Tags:** {', '.join(tags)}")

            st.markdown(f"**{labels['content_preview']}:**")
            st.text(content_preview)

            # Embedding status
            if has_embedding:
                st.success(labels["embedding_available"], icon="✅")
            else:
                st.warning(labels["no_embedding"], icon="⚠️")

        with col2:
            if editable:
                st.markdown(f"**{labels['actions']}**")

                # Toggle active
                toggle_label = labels["deactivate"] if is_active else labels["activate"]
                if st.button(toggle_label, key=f"{key_prefix}_toggle_{doc_id}"):
                    _toggle_document(context, org_id, doc_id, is_active, labels)

                # Regenerate embedding
                if st.button(
                    labels["regenerate"],
                    key=f"{key_prefix}_embed_{doc_id}",
                ):
                    _regenerate_embedding(context, org_id, doc_id, labels)

                # Delete
                if st.button(
                    labels["delete"],
                    key=f"{key_prefix}_delete_{doc_id}",
                    type="secondary",
                ):
                    _delete_document(context, org_id, doc_id, labels, on_delete)


def _fetch_documents(
    *,
    context: str,
    org_id: str | None,
    document_type: str | None,
    category: str | None,
    active_only: bool | None,
    skip: int,
    limit: int,
) -> tuple[list, int]:
    """Fetch documents from appropriate API."""
    if context == "global":
        from lib.api_client import get_knowledge_list

        result = get_knowledge_list(
            document_type=document_type,
            page=skip // limit + 1,
            page_size=limit,
        )
        if result:
            return result.get("documents", result.get("items", [])), result.get(
                "total", 0
            )
        return [], 0
    else:
        from lib.api_client import get_tenant_documents

        result = get_tenant_documents(
            org_id=org_id,
            document_type=document_type,
            category=category,
            active_only=active_only if active_only is not None else True,
            skip=skip,
            limit=limit,
        )
        return result.get("documents", []), result.get("total", 0)


def _toggle_document(
    context: str,
    org_id: str | None,
    doc_id: str,
    current_active: bool,
    labels: dict,
) -> None:
    """Toggle document active status."""
    with st.spinner(labels["updating"]):
        if context == "global":
            from lib.api_client import update_knowledge

            result = update_knowledge(doc_id, {"active": not current_active})
        else:
            from lib.api_client import update_tenant_document

            result = update_tenant_document(org_id, doc_id, {"active": not current_active})

        if result:
            st.rerun()


def _regenerate_embedding(
    context: str,
    org_id: str | None,
    doc_id: str,
    labels: dict,
) -> None:
    """Regenerate document embedding."""
    with st.spinner(labels["regenerating"]):
        if context == "global":
            from lib.api_client import regenerate_embedding

            result = regenerate_embedding(doc_id)
        else:
            from lib.api_client import regenerate_document_embedding

            result = regenerate_document_embedding(org_id, doc_id)

        if result:
            st.success(labels["regenerate_success"])
            st.rerun()


def _delete_document(
    context: str,
    org_id: str | None,
    doc_id: str,
    labels: dict,
    on_delete: Callable | None,
) -> None:
    """Delete document."""
    with st.spinner(labels["deleting"]):
        if context == "global":
            from lib.api_client import delete_knowledge

            success = delete_knowledge(doc_id)
        else:
            from lib.api_client import delete_tenant_document

            success = delete_tenant_document(org_id, doc_id)

        if success:
            st.success(labels["delete_success"])
            if on_delete:
                on_delete(doc_id)
            st.rerun()


def _get_labels(language: Literal["en", "es"]) -> dict:
    """Get UI labels based on language."""
    if language == "es":
        return {
            "header": "Documentos",
            "all": "Todos",
            "active": "Activos",
            "inactive": "Inactivos",
            "filter_type": "Tipo",
            "filter_category": "Categoria",
            "filter_placeholder": "Filtrar...",
            "filter_status": "Estado",
            "per_page": "Por pagina",
            "no_documents": "No hay documentos que coincidan con los filtros",
            "showing": "Mostrando {count} de {total} documentos",
            "previous": "← Anterior",
            "next": "Siguiente →",
            "page": "Pagina",
            "of": "de",
            "no_title": "Sin titulo",
            "category": "Categoria",
            "content_preview": "Contenido (preview)",
            "embedding_available": "Embedding disponible",
            "no_embedding": "Sin embedding",
            "actions": "Acciones",
            "deactivate": "Desactivar",
            "activate": "Activar",
            "regenerate": "Regenerar Embedding",
            "delete": "Eliminar",
            "updating": "Actualizando...",
            "regenerating": "Regenerando embedding...",
            "regenerate_success": "Embedding regenerado!",
            "deleting": "Eliminando...",
            "delete_success": "Documento eliminado",
            "search_label": "Busqueda semantica",
            "search_placeholder": "Escribe tu consulta...",
            "max_results": "Max resultados",
            "search_button": "Buscar",
            "searching": "Buscando...",
            "search_found": "Se encontraron {count} resultados",
            "no_results": "No se encontraron resultados",
        }
    else:
        return {
            "header": "Documents",
            "all": "All",
            "active": "Active",
            "inactive": "Inactive",
            "filter_type": "Type",
            "filter_category": "Category",
            "filter_placeholder": "Filter...",
            "filter_status": "Status",
            "per_page": "Per page",
            "no_documents": "No documents match the filters",
            "showing": "Showing {count} of {total} documents",
            "previous": "← Previous",
            "next": "Next →",
            "page": "Page",
            "of": "of",
            "no_title": "No title",
            "category": "Category",
            "content_preview": "Content (preview)",
            "embedding_available": "Embedding available",
            "no_embedding": "No embedding",
            "actions": "Actions",
            "deactivate": "Deactivate",
            "activate": "Activate",
            "regenerate": "Regenerate Embedding",
            "delete": "Delete",
            "updating": "Updating...",
            "regenerating": "Regenerating embedding...",
            "regenerate_success": "Embedding regenerated!",
            "deleting": "Deleting...",
            "delete_success": "Document deleted",
            "search_label": "Semantic search",
            "search_placeholder": "Enter your query...",
            "max_results": "Max results",
            "search_button": "Search",
            "searching": "Searching...",
            "search_found": "Found {count} results",
            "no_results": "No results found",
        }


__all__ = ["render_document_browser"]
