"""
Streamlit Knowledge Base & Agent Configuration Manager

Interactive UI for:
- Uploading PDF documents to knowledge base
- Uploading text content to knowledge base
- Managing Excelencia agent configuration
- Viewing and editing agent modules
"""

import streamlit as st
import requests
import json
from typing import Optional
import os
from pathlib import Path

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
DOCUMENT_UPLOAD_URL = f"{API_BASE_URL}/api/v1/admin/documents"
AGENT_CONFIG_URL = f"{API_BASE_URL}/api/v1/admin/agent-config"
KNOWLEDGE_ADMIN_URL = f"{API_BASE_URL}/api/v1/admin/knowledge"


# ============================================================================
# Page Configuration
# ============================================================================

st.set_page_config(
    page_title="Knowledge Base & Agent Manager",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📚 Knowledge Base & Agent Configuration Manager")
st.markdown("---")


# ============================================================================
# Helper Functions
# ============================================================================


def upload_pdf(file, title: Optional[str], document_type: str, category: Optional[str], tags: str):
    """Upload PDF file to knowledge base."""
    try:
        files = {"file": (file.name, file, "application/pdf")}
        data = {
            "document_type": document_type,
        }
        if title:
            data["title"] = title
        if category:
            data["category"] = category
        if tags:
            data["tags"] = tags

        response = requests.post(
            f"{DOCUMENT_UPLOAD_URL}/upload/pdf",
            files=files,
            data=data,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error uploading PDF: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            st.error(f"Response: {e.response.text}")
        return None


def upload_text(content: str, title: str, document_type: str, category: Optional[str], tags: list):
    """Upload text content to knowledge base."""
    try:
        data = {
            "content": content,
            "title": title,
            "document_type": document_type,
            "category": category,
            "tags": tags or [],
        }

        response = requests.post(
            f"{DOCUMENT_UPLOAD_URL}/upload/text",
            json=data,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error uploading text: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            st.error(f"Response: {e.response.text}")
        return None


def get_agent_config():
    """Get current agent configuration."""
    try:
        response = requests.get(f"{AGENT_CONFIG_URL}/excelencia")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error getting agent config: {str(e)}")
        return None


def update_agent_modules(modules: dict, create_backup: bool = True):
    """Update agent modules configuration."""
    try:
        data = {
            "modules": modules,
            "create_backup": create_backup,
        }
        response = requests.put(
            f"{AGENT_CONFIG_URL}/excelencia/modules",
            json=data,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error updating modules: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            st.error(f"Response: {e.response.text}")
        return None


def get_knowledge_list(document_type: Optional[str] = None, page: int = 1, page_size: int = 20):
    """Get list of knowledge documents."""
    try:
        params = {"page": page, "page_size": page_size}
        if document_type:
            params["document_type"] = document_type

        response = requests.get(
            f"{KNOWLEDGE_ADMIN_URL}",
            params=params,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error getting knowledge list: {str(e)}")
        return None


def delete_knowledge(knowledge_id: str, soft_delete: bool = True):
    """Delete knowledge document."""
    try:
        response = requests.delete(
            f"{KNOWLEDGE_ADMIN_URL}/{knowledge_id}",
            params={"soft_delete": soft_delete},
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error deleting knowledge: {str(e)}")
        return None


# ============================================================================
# Sidebar Navigation
# ============================================================================

st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Choose a section:",
    [
        "📄 Upload PDF",
        "✍️ Upload Text",
        "📋 Browse Knowledge",
        "⚙️ Agent Configuration",
        "📊 Statistics",
    ],
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Document Types")
st.sidebar.markdown("""
- **Mission & Vision**: Company values
- **Contact Info**: Contact details
- **Software Catalog**: Products & modules
- **FAQ**: Frequently asked questions
- **Clients**: Client information
- **Success Stories**: Case studies
- **General**: General information
""")


# ============================================================================
# Page: Upload PDF
# ============================================================================

if page == "📄 Upload PDF":
    st.header("📄 Upload PDF Document")
    st.markdown("Upload PDF files to extract text and store in the knowledge base.")

    col1, col2 = st.columns([2, 1])

    with col1:
        uploaded_file = st.file_uploader(
            "Choose a PDF file",
            type=["pdf"],
            help="Select a PDF file to upload",
        )

    with col2:
        document_type = st.selectbox(
            "Document Type",
            [
                "general",
                "mission_vision",
                "contact_info",
                "software_catalog",
                "faq",
                "clients",
                "success_stories",
            ],
        )

    title = st.text_input(
        "Title (optional)",
        help="Leave empty to extract from PDF metadata",
    )

    col3, col4 = st.columns(2)
    with col3:
        category = st.text_input("Category (optional)")
    with col4:
        tags = st.text_input(
            "Tags (comma-separated)",
            placeholder="e.g., product,manual,tutorial",
        )

    if st.button("Upload PDF", type="primary", disabled=uploaded_file is None):
        if uploaded_file is not None:
            with st.spinner("Uploading PDF..."):
                result = upload_pdf(
                    file=uploaded_file,
                    title=title if title else None,
                    document_type=document_type,
                    category=category if category else None,
                    tags=tags,
                )

                if result:
                    st.success("✅ PDF uploaded successfully!")
                    st.json(result)


# ============================================================================
# Page: Upload Text
# ============================================================================

elif page == "✍️ Upload Text":
    st.header("✍️ Upload Text Content")
    st.markdown("Upload plain text or markdown content to the knowledge base.")

    title = st.text_input(
        "Title *",
        placeholder="Document title (required)",
    )

    col1, col2 = st.columns(2)
    with col1:
        document_type = st.selectbox(
            "Document Type",
            [
                "general",
                "mission_vision",
                "contact_info",
                "software_catalog",
                "faq",
                "clients",
                "success_stories",
            ],
        )
    with col2:
        category = st.text_input("Category (optional)")

    tags_input = st.text_input(
        "Tags (comma-separated)",
        placeholder="e.g., product,info,tutorial",
    )

    content = st.text_area(
        "Content *",
        height=300,
        placeholder="Enter your text content here (minimum 50 characters)...",
        help="Plain text or markdown format supported",
    )

    character_count = len(content)
    st.caption(f"Character count: {character_count} (minimum: 50)")

    if st.button("Upload Text", type="primary", disabled=not title or character_count < 50):
        tags_list = [tag.strip() for tag in tags_input.split(",") if tag.strip()]

        with st.spinner("Uploading text..."):
            result = upload_text(
                content=content,
                title=title,
                document_type=document_type,
                category=category if category else None,
                tags=tags_list,
            )

            if result:
                st.success("✅ Text uploaded successfully!")
                st.json(result)


# ============================================================================
# Page: Browse Knowledge
# ============================================================================

elif page == "📋 Browse Knowledge":
    st.header("📋 Browse Knowledge Base")
    st.markdown("View and manage documents in the knowledge base.")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        filter_type = st.selectbox(
            "Filter by type",
            ["All"] + [
                "mission_vision",
                "contact_info",
                "software_catalog",
                "faq",
                "clients",
                "success_stories",
                "general",
            ],
        )
    with col2:
        page_num = st.number_input("Page", min_value=1, value=1)
    with col3:
        page_size = st.selectbox("Per page", [10, 20, 50], index=1)

    if st.button("Refresh List", type="secondary"):
        st.rerun()

    # Get knowledge list
    filter_param = None if filter_type == "All" else filter_type
    knowledge_data = get_knowledge_list(
        document_type=filter_param,
        page=page_num,
        page_size=page_size,
    )

    if knowledge_data:
        documents = knowledge_data.get("documents", [])
        pagination = knowledge_data.get("pagination", {})

        # Display pagination info
        st.info(
            f"📄 Page {pagination.get('page', 1)} of {pagination.get('total_pages', 1)} "
            f"({pagination.get('total_documents', 0)} total documents)"
        )

        # Display documents
        for doc in documents:
            with st.expander(f"📄 {doc['title']} ({doc['document_type']})"):
                st.markdown(f"**ID:** `{doc['id']}`")
                st.markdown(f"**Type:** {doc['document_type']}")
                st.markdown(f"**Category:** {doc.get('category', 'N/A')}")
                st.markdown(f"**Tags:** {', '.join(doc.get('tags', []))}")
                st.markdown(f"**Active:** {'✅' if doc.get('active') else '❌'}")
                st.markdown(f"**Has Embedding:** {'✅' if doc.get('has_embedding') else '❌'}")
                st.markdown(f"**Created:** {doc.get('created_at', 'N/A')}")

                # Show content preview
                content = doc.get('content', '')
                preview = content[:500] + "..." if len(content) > 500 else content
                st.text_area("Content Preview", preview, height=150, disabled=True)

                # Delete button
                if st.button(f"🗑️ Delete", key=f"delete_{doc['id']}"):
                    if st.session_state.get(f"confirm_delete_{doc['id']}", False):
                        result = delete_knowledge(doc['id'], soft_delete=True)
                        if result:
                            st.success("Document deleted successfully!")
                            st.rerun()
                    else:
                        st.session_state[f"confirm_delete_{doc['id']}"] = True
                        st.warning("Click again to confirm deletion")


# ============================================================================
# Page: Agent Configuration
# ============================================================================

elif page == "⚙️ Agent Configuration":
    st.header("⚙️ Excelencia Agent Configuration")
    st.markdown("View and edit Excelencia agent modules and settings.")

    # Get current configuration
    config = get_agent_config()

    if config:
        tab1, tab2 = st.tabs(["🔧 Modules", "⚙️ Settings"])

        # Tab: Modules
        with tab1:
            st.subheader("Agent Modules")
            st.info("⚠️ Changes to modules require application restart!")

            modules = config.get("modules", {})

            # Display modules in cards
            for module_id, module_data in modules.items():
                with st.expander(f"🏥 {module_data['name']}", expanded=False):
                    new_name = st.text_input(
                        "Name",
                        value=module_data["name"],
                        key=f"name_{module_id}",
                    )
                    new_desc = st.text_area(
                        "Description",
                        value=module_data["description"],
                        key=f"desc_{module_id}",
                    )
                    new_target = st.text_input(
                        "Target Audience",
                        value=module_data["target"],
                        key=f"target_{module_id}",
                    )

                    # Features list
                    features_text = "\n".join(module_data["features"])
                    new_features = st.text_area(
                        "Features (one per line)",
                        value=features_text,
                        key=f"features_{module_id}",
                        height=150,
                    )

                    if st.button(f"Save {module_data['name']}", key=f"save_{module_id}"):
                        updated_module = {
                            "name": new_name,
                            "description": new_desc,
                            "target": new_target,
                            "features": [
                                f.strip() for f in new_features.split("\n") if f.strip()
                            ],
                        }

                        result = update_agent_modules(
                            {module_id: updated_module},
                            create_backup=True,
                        )

                        if result:
                            st.success("✅ Module updated successfully!")
                            st.warning("⚠️ Restart the application for changes to take effect")
                            st.json(result)

        # Tab: Settings
        with tab2:
            st.subheader("Agent Settings")

            settings = config.get("settings", {})

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Model", settings.get("model", "N/A"))
                st.metric("Temperature", settings.get("temperature", "N/A"))
                st.metric("Max Response Length", settings.get("max_response_length", "N/A"))

            with col2:
                st.metric("Use RAG", "✅" if settings.get("use_rag") else "❌")
                st.metric("RAG Max Results", settings.get("rag_max_results", "N/A"))

            st.info("💡 Settings update functionality coming soon!")


# ============================================================================
# Page: Statistics
# ============================================================================

elif page == "📊 Statistics":
    st.header("📊 Knowledge Base Statistics")

    try:
        response = requests.get(f"{KNOWLEDGE_ADMIN_URL}/stats")
        response.raise_for_status()
        stats = response.json()

        # Database stats
        db_stats = stats.get("database", {})
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("📄 Active Documents", db_stats.get("total_active", 0))
        with col2:
            st.metric("🗂️ Inactive Documents", db_stats.get("total_inactive", 0))
        with col3:
            st.metric("⚠️ Missing Embeddings", db_stats.get("missing_embeddings", 0))
        with col4:
            coverage = db_stats.get("embedding_coverage", 0)
            st.metric("✅ Embedding Coverage", f"{coverage}%")

        # ChromaDB collections
        st.subheader("ChromaDB Collections")
        chroma_stats = stats.get("chromadb_collections", {})

        if chroma_stats:
            for collection_name, count in chroma_stats.items():
                st.metric(f"Collection: {collection_name}", count)
        else:
            st.info("No ChromaDB collection stats available")

        # Model info
        st.subheader("Embedding Model")
        st.code(stats.get("embedding_model", "N/A"))

    except requests.exceptions.RequestException as e:
        st.error(f"Error getting statistics: {str(e)}")


# ============================================================================
# Footer
# ============================================================================

st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
        <p>Knowledge Base & Agent Configuration Manager</p>
        <p>Powered by Aynux Multi-Agent System</p>
    </div>
    """,
    unsafe_allow_html=True,
)
