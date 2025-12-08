"""
Statistics - Knowledge Base Statistics

Interactive UI for:
- Viewing knowledge base statistics
- Monitoring database and embedding coverage
"""

import sys
from pathlib import Path

import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from lib.api_client import get_knowledge_stats
from lib.session_state import init_session_state

init_session_state()

st.title("📊 Knowledge Base Statistics")
st.markdown("View statistics and metrics for the knowledge base.")

# Refresh button
if st.button("🔄 Refresh Statistics"):
    st.rerun()

stats = get_knowledge_stats()

if stats:
    # Database stats
    db_stats = stats.get("database", {})

    st.subheader("📊 Document Statistics")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("📄 Active Documents", db_stats.get("total_active", 0))

    with col2:
        st.metric("🗂️ Inactive Documents", db_stats.get("total_inactive", 0))

    with col3:
        missing = db_stats.get("missing_embeddings", 0)
        st.metric(
            "⚠️ Missing Embeddings",
            missing,
            delta=-missing if missing > 0 else None,
            delta_color="inverse",
        )

    with col4:
        coverage = db_stats.get("embedding_coverage", 0)
        st.metric("✅ Embedding Coverage", f"{coverage}%")

    # Coverage visualization
    st.markdown("---")
    st.subheader("📈 Embedding Coverage")
    st.progress(coverage / 100)

    if coverage < 100:
        st.warning(f"⚠️ {100 - coverage:.1f}% of documents are missing embeddings")
    else:
        st.success("✅ All documents have embeddings!")

    # ChromaDB collections
    st.markdown("---")
    st.subheader("🗃️ ChromaDB Collections")
    chroma_stats = stats.get("chromadb_collections", {})

    if chroma_stats:
        cols = st.columns(len(chroma_stats))
        for idx, (collection_name, count) in enumerate(chroma_stats.items()):
            with cols[idx]:
                st.metric(f"Collection: {collection_name}", count)
    else:
        st.info("No ChromaDB collection stats available")

    # Model info
    st.markdown("---")
    st.subheader("🤖 Embedding Model")
    st.code(stats.get("embedding_model", "N/A"))

    # By document type (if available)
    by_type = db_stats.get("by_type", {})
    if by_type:
        st.markdown("---")
        st.subheader("📋 Documents by Type")

        import pandas as pd

        df = pd.DataFrame(list(by_type.items()), columns=["Type", "Count"])
        st.bar_chart(df.set_index("Type"))

    # Raw stats
    st.markdown("---")
    with st.expander("🔍 View Raw Statistics"):
        st.json(stats)

else:
    st.error("❌ Unable to fetch statistics. Is the API running?")

# Sidebar
st.sidebar.subheader("📊 About Statistics")
st.sidebar.markdown(
    """
This page shows:

- **Active Documents**: Documents available for search
- **Inactive Documents**: Deactivated documents
- **Missing Embeddings**: Documents without vector representations
- **Embedding Coverage**: Percentage of documents with embeddings

**ChromaDB Collections** shows the document counts in the vector database.

**Embedding Model** shows which model is used to generate document embeddings.
"""
)
