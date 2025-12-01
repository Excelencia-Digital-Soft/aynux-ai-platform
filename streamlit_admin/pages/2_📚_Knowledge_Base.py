"""
Knowledge Base - Browse, Edit, and Search Documents

Interactive UI for:
- Browsing knowledge documents
- Inline editing with save/cancel
- Semantic search with similarity scores
- Soft delete (deactivate) and hard delete (permanent)
"""

import sys
from pathlib import Path

import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from lib.api_client import (
    delete_knowledge,
    get_knowledge_list,
    regenerate_embedding,
    search_knowledge,
    update_knowledge,
)
from lib.session_state import init_session_state

init_session_state()

st.title("📚 Knowledge Base")
st.markdown("Browse, edit, and search documents in the knowledge base.")

# Tabs
tab_browse, tab_search = st.tabs(["📋 Browse Documents", "🔍 Semantic Search"])

# ============================================================================
# Tab: Browse Documents
# ============================================================================

with tab_browse:
    st.subheader("📋 Browse & Edit Documents")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        filter_type = st.selectbox(
            "Filter by type",
            ["All", "mission_vision", "contact_info", "software_catalog", "faq", "clients", "success_stories", "general"],
        )
    with col2:
        page_num = st.number_input("Page", min_value=1, value=1)
    with col3:
        page_size = st.selectbox("Per page", [10, 20, 50], index=1)

    if st.button("🔄 Refresh List", type="secondary"):
        st.rerun()

    filter_param = None if filter_type == "All" else filter_type
    knowledge_data = get_knowledge_list(document_type=filter_param, page=page_num, page_size=page_size)

    if knowledge_data:
        documents = knowledge_data.get("documents", [])
        pagination = knowledge_data.get("pagination", {})

        st.info(
            f"📄 Page {pagination.get('page', 1)} of {pagination.get('total_pages', 1)} "
            f"({pagination.get('total_documents', 0)} total documents)"
        )

        for doc in documents:
            doc_id = doc["id"]
            is_editing = st.session_state.editing_doc_id == doc_id

            with st.expander(f"📄 {doc['title']} ({doc['document_type']})", expanded=is_editing):
                if is_editing:
                    st.markdown("### ✏️ Editing Document")

                    edit_title = st.text_input("Title", value=doc["title"], key=f"edit_title_{doc_id}")
                    edit_type = st.selectbox(
                        "Document Type",
                        ["general", "mission_vision", "contact_info", "software_catalog", "faq", "clients", "success_stories"],
                        index=["general", "mission_vision", "contact_info", "software_catalog", "faq", "clients", "success_stories"].index(
                            doc.get("document_type", "general")
                        ),
                        key=f"edit_type_{doc_id}",
                    )
                    edit_category = st.text_input("Category", value=doc.get("category") or "", key=f"edit_category_{doc_id}")
                    edit_tags = st.text_input(
                        "Tags (comma-separated)", value=", ".join(doc.get("tags", [])), key=f"edit_tags_{doc_id}"
                    )
                    edit_content = st.text_area(
                        "Content", value=doc.get("content", ""), height=300, key=f"edit_content_{doc_id}"
                    )
                    regenerate = st.checkbox("Regenerate embedding after save", value=True, key=f"regenerate_{doc_id}")

                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        if st.button("💾 Save", key=f"save_{doc_id}", type="primary"):
                            update_data = {
                                "title": edit_title,
                                "document_type": edit_type,
                                "category": edit_category if edit_category else None,
                                "tags": [t.strip() for t in edit_tags.split(",") if t.strip()],
                                "content": edit_content,
                            }
                            result = update_knowledge(doc_id, update_data, regenerate)
                            if result:
                                st.success("✅ Document updated!")
                                st.session_state.editing_doc_id = None
                                st.rerun()
                    with col_cancel:
                        if st.button("❌ Cancel", key=f"cancel_{doc_id}"):
                            st.session_state.editing_doc_id = None
                            st.rerun()

                else:
                    st.markdown(f"**ID:** `{doc['id']}`")
                    st.markdown(f"**Type:** {doc['document_type']}")
                    st.markdown(f"**Category:** {doc.get('category', 'N/A')}")
                    st.markdown(f"**Tags:** {', '.join(doc.get('tags', []))}")
                    st.markdown(f"**Active:** {'✅' if doc.get('active') else '❌'}")
                    st.markdown(f"**Has Embedding:** {'✅' if doc.get('has_embedding') else '❌'}")

                    content = doc.get("content", "")
                    preview = content[:500] + "..." if len(content) > 500 else content
                    st.text_area("Content Preview", preview, height=150, disabled=True, key=f"preview_{doc_id}")

                    col_edit, col_regen, col_soft, col_hard = st.columns(4)

                    with col_edit:
                        if st.button("✏️ Edit", key=f"edit_{doc_id}"):
                            st.session_state.editing_doc_id = doc_id
                            st.rerun()

                    with col_regen:
                        if st.button("🔄 Regen", key=f"regen_{doc_id}"):
                            with st.spinner("Regenerating..."):
                                if regenerate_embedding(doc_id):
                                    st.success("Embedding regenerated!")
                                    st.rerun()

                    with col_soft:
                        if st.button("🗑️ Deactivate", key=f"soft_{doc_id}"):
                            result = delete_knowledge(doc_id, hard_delete=False)
                            if result:
                                st.success("Document deactivated")
                                st.rerun()

                    with col_hard:
                        if st.session_state.confirm_hard_delete == doc_id:
                            st.warning("⚠️ IRREVERSIBLE!")
                            if st.button("Confirm Delete", key=f"confirm_hard_{doc_id}", type="primary"):
                                result = delete_knowledge(doc_id, hard_delete=True)
                                if result:
                                    st.success("Document permanently deleted")
                                    st.session_state.confirm_hard_delete = None
                                    st.rerun()
                            if st.button("Cancel", key=f"cancel_hard_{doc_id}"):
                                st.session_state.confirm_hard_delete = None
                                st.rerun()
                        else:
                            if st.button("❌ Delete", key=f"hard_{doc_id}", type="secondary"):
                                st.session_state.confirm_hard_delete = doc_id
                                st.rerun()

# ============================================================================
# Tab: Semantic Search
# ============================================================================

with tab_search:
    st.subheader("🔍 Semantic Search")
    st.markdown("Search the knowledge base using semantic similarity.")

    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input(
            "Search Query", placeholder="Enter your search query...", help="Minimum 3 characters"
        )
    with col2:
        max_results = st.slider("Max Results", 1, 20, 5)

    col3, col4 = st.columns(2)
    with col3:
        search_type = st.selectbox(
            "Filter by Type",
            ["All", "mission_vision", "contact_info", "software_catalog", "faq", "clients", "success_stories", "general"],
            key="search_filter_type",
        )
    with col4:
        search_category = st.text_input("Filter by Category", placeholder="Optional", key="search_filter_category")

    if st.button("🔎 Search", type="primary", disabled=len(search_query) < 3):
        with st.spinner("Searching..."):
            results = search_knowledge(
                query=search_query,
                max_results=max_results,
                document_type=None if search_type == "All" else search_type,
                category=search_category if search_category else None,
            )
            st.session_state.search_results = results

    if st.session_state.search_results:
        st.markdown(f"### Found {len(st.session_state.search_results)} results")

        for result in st.session_state.search_results:
            similarity = result.get("similarity", 0)

            with st.expander(f"📄 {result.get('title', 'Untitled')} - Score: {similarity:.2%}"):
                st.progress(similarity)
                st.markdown(f"**ID:** `{result.get('id')}`")
                st.markdown(f"**Type:** {result.get('document_type', 'N/A')}")
                st.markdown(f"**Category:** {result.get('category', 'N/A')}")

                content = result.get("content", "")
                preview = content[:1000] + "..." if len(content) > 1000 else content
                st.text_area("Content", preview, height=200, disabled=True, key=f"search_content_{result.get('id')}")

                if st.button("✏️ Edit this document", key=f"search_edit_{result.get('id')}"):
                    st.session_state.editing_doc_id = result.get("id")
                    st.info("Navigate to 'Browse Documents' tab to edit this document")
