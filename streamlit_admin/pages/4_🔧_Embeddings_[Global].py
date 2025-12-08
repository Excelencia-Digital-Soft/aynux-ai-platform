"""
Embeddings - Embedding Management Dashboard

Interactive UI for:
- Viewing embedding statistics
- Syncing embeddings
- Monitoring coverage
"""

import sys
from pathlib import Path

import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from lib.api_client import get_knowledge_stats, sync_all_embeddings
from lib.session_state import init_session_state

init_session_state()

st.title("🔧 Embedding Management")
st.markdown("Monitor and manage document embeddings.")

# Get stats
stats = get_knowledge_stats()

if stats:
    db_stats = stats.get("database", {})

    # Metrics
    st.subheader("📊 Embedding Statistics")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("📄 Active Documents", db_stats.get("total_active", 0))

    with col2:
        missing = db_stats.get("missing_embeddings", 0)
        st.metric(
            "⚠️ Missing Embeddings",
            missing,
            delta=-missing if missing > 0 else None,
            delta_color="inverse",
        )

    with col3:
        coverage = db_stats.get("embedding_coverage", 0)
        st.metric("✅ Coverage", f"{coverage}%")

    with col4:
        st.metric("🤖 Model", stats.get("embedding_model", "N/A"))

    # Coverage progress bar
    st.progress(coverage / 100)

    st.markdown("---")

    # Health status
    if missing > 0:
        st.warning(f"⚠️ {missing} documents are missing embeddings")
    else:
        st.success("✅ All documents have embeddings")

    # Actions
    st.subheader("🛠️ Actions")

    col_sync, col_info = st.columns([1, 2])

    with col_sync:
        if st.button("🔄 Sync All Embeddings", type="primary", use_container_width=True):
            with st.spinner("Syncing all embeddings... This may take a while."):
                result = sync_all_embeddings()
                if result:
                    st.success(
                        f"✅ Synced! Processed: {result.get('details', {}).get('processed_documents', 'N/A')} documents"
                    )
                    st.rerun()

    with col_info:
        st.info(
            """
            **When to regenerate embeddings:**
            - After changing embedding models
            - After bulk content updates
            - When search quality degrades
            """
        )

    # Inactive documents
    st.markdown("---")
    st.subheader("📴 Inactive Documents")
    inactive = db_stats.get("total_inactive", 0)

    if inactive > 0:
        st.warning(f"📴 {inactive} documents are inactive")
    else:
        st.success("✅ No inactive documents")

    # Detailed stats
    st.markdown("---")
    st.subheader("📋 Detailed Statistics")

    with st.expander("View raw statistics"):
        st.json(stats)

else:
    st.error("❌ Unable to fetch statistics. Is the API running?")

# Sidebar tips
st.sidebar.subheader("💡 Tips")
st.sidebar.markdown(
    """
**Embeddings** are vector representations of your documents
that enable semantic search.

- **Coverage**: Percentage of documents with embeddings
- **Missing**: Documents that need embedding generation
- **Sync**: Generate embeddings for all missing documents

**When to regenerate:**
1. After changing the embedding model
2. After significant content updates
3. If search results seem off
"""
)
