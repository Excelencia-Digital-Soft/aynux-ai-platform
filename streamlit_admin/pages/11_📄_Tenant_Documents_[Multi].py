"""
Tenant Documents Page

Manage knowledge base documents for the current organization.
Upload PDFs, create text documents, and manage embeddings.

Refactored to use shared components from streamlit_admin/components/
"""

import sys
from pathlib import Path

import streamlit as st

# Add paths for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
streamlit_admin_root = Path(__file__).parent.parent
sys.path.insert(0, str(streamlit_admin_root))

from lib.api_client import get_tenant_documents_stats
from lib.auth import (
    get_current_org_id,
    render_user_menu,
    require_role,
)
from lib.session_state import init_session_state

# Import shared components
from streamlit_admin.components import (
    render_document_browser,
    render_pdf_uploader,
    render_text_uploader,
)

# Initialize session state
init_session_state()

# Page configuration
st.set_page_config(
    page_title="Tenant Documents - Aynux Admin",
    page_icon="📄",
    layout="wide",
)

# Require admin role
if not require_role("admin"):
    st.stop()

org_id = get_current_org_id()


def render_stats():
    """Render document statistics."""
    stats = get_tenant_documents_stats(org_id)

    if not stats:
        return

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Documentos", stats.get("total_documents", 0))

    with col2:
        st.metric("Activos", stats.get("active_documents", 0))

    with col3:
        st.metric("Con Embedding", stats.get("documents_with_embedding", 0))

    with col4:
        coverage = stats.get("embedding_coverage", 0)
        st.metric("Cobertura", f"{coverage:.1f}%")


# Main page
st.title("📄 Documentos del Tenant")
st.markdown(f"**Organizacion:** {st.session_state.current_org_name}")
st.markdown("---")

# Stats
render_stats()
st.markdown("---")

# Tabs
tab1, tab2, tab3 = st.tabs(["📋 Documentos", "📤 Subir PDF", "✏️ Crear Texto"])

with tab1:
    render_document_browser(
        context="tenant",
        org_id=org_id,
        key_prefix="tenant_docs",
        language="es",
        show_search=False,  # Tenant context doesn't have semantic search yet
        show_filters=True,
        editable=True,
    )

with tab2:
    render_pdf_uploader(
        context="tenant",
        org_id=org_id,
        key_prefix="tenant_pdf",
        language="es",
    )

with tab3:
    render_text_uploader(
        context="tenant",
        org_id=org_id,
        key_prefix="tenant_text",
        language="es",
    )

# Render user menu in sidebar
render_user_menu()
