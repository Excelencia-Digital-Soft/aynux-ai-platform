"""
Upload Documents - PDF and Text Upload

Interactive UI for:
- Uploading PDF documents
- Uploading text content
"""

import sys
from pathlib import Path

import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from lib.api_client import upload_pdf, upload_text
from lib.session_state import init_session_state

init_session_state()

st.title("📤 Upload Documents")
st.markdown("Upload PDF files or text content to the knowledge base.")

# Tabs
tab_pdf, tab_text = st.tabs(["📄 Upload PDF", "✍️ Upload Text"])

# ============================================================================
# Tab: Upload PDF
# ============================================================================

with tab_pdf:
    st.subheader("📄 Upload PDF Document")
    st.markdown("Upload PDF files to extract text and store in the knowledge base.")

    col1, col2 = st.columns([2, 1])

    with col1:
        uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"], help="Select a PDF file to upload")

    with col2:
        document_type = st.selectbox(
            "Document Type",
            ["general", "mission_vision", "contact_info", "software_catalog", "faq", "clients", "success_stories"],
            key="pdf_doc_type",
        )

    title = st.text_input("Title (optional)", help="Leave empty to extract from PDF metadata", key="pdf_title")

    col3, col4 = st.columns(2)
    with col3:
        category = st.text_input("Category (optional)", key="pdf_category")
    with col4:
        tags = st.text_input("Tags (comma-separated)", placeholder="e.g., product,manual,tutorial", key="pdf_tags")

    if st.button("📤 Upload PDF", type="primary", disabled=uploaded_file is None):
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
# Tab: Upload Text
# ============================================================================

with tab_text:
    st.subheader("✍️ Upload Text Content")
    st.markdown("Upload plain text or markdown content to the knowledge base.")

    title = st.text_input("Title *", placeholder="Document title (required)", key="text_title")

    col1, col2 = st.columns(2)
    with col1:
        document_type = st.selectbox(
            "Document Type",
            ["general", "mission_vision", "contact_info", "software_catalog", "faq", "clients", "success_stories"],
            key="text_doc_type",
        )
    with col2:
        category = st.text_input("Category (optional)", key="text_category")

    tags_input = st.text_input("Tags (comma-separated)", placeholder="e.g., product,info,tutorial", key="text_tags")

    content = st.text_area(
        "Content *",
        height=300,
        placeholder="Enter your text content here (minimum 50 characters)...",
        help="Plain text or markdown format supported",
        key="text_content",
    )

    character_count = len(content)
    st.caption(f"Character count: {character_count} (minimum: 50)")

    if st.button("📤 Upload Text", type="primary", disabled=not title or character_count < 50):
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

# Sidebar info
st.sidebar.markdown("### Document Types")
st.sidebar.markdown(
    """
- **Mission & Vision**: Company values
- **Contact Info**: Contact details
- **Software Catalog**: Products & modules
- **FAQ**: Frequently asked questions
- **Clients**: Client information
- **Success Stories**: Case studies
- **General**: General information
"""
)
