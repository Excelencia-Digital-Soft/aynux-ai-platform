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

st.title("🔧 Gestión de Embeddings")
st.markdown("Monitorea y gestiona los embeddings de documentos.")

# Get stats
stats = get_knowledge_stats()

if stats:
    db_stats = stats.get("database", {})

    # Metrics
    st.subheader("📊 Estadísticas de Embeddings")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("📄 Documentos Activos", db_stats.get("total_active", 0))

    with col2:
        missing = db_stats.get("missing_embeddings", 0)
        st.metric(
            "⚠️ Embeddings Faltantes",
            missing,
            delta=-missing if missing > 0 else None,
            delta_color="inverse",
        )

    with col3:
        coverage = db_stats.get("embedding_coverage", 0)
        st.metric("✅ Cobertura", f"{coverage}%")

    with col4:
        st.metric("🤖 Modelo", stats.get("embedding_model", "N/A"))

    # Coverage progress bar
    st.progress(coverage / 100)

    st.markdown("---")

    # Health status
    if missing > 0:
        st.warning(f"⚠️ {missing} documentos no tienen embeddings")
    else:
        st.success("✅ Todos los documentos tienen embeddings")

    # Actions
    st.subheader("🛠️ Acciones")

    col_sync, col_info = st.columns([1, 2])

    with col_sync:
        if st.button("🔄 Sincronizar Todos los Embeddings", type="primary", use_container_width=True):
            with st.spinner("Sincronizando todos los embeddings... Esto puede tomar un momento."):
                result = sync_all_embeddings()
                if result:
                    st.success(
                        f"✅ ¡Sincronizado! Procesados: {result.get('details', {}).get('processed_documents', 'N/A')} documentos"
                    )
                    st.rerun()

    with col_info:
        st.info(
            """
            **Cuándo regenerar embeddings:**
            - Después de cambiar modelos de embedding
            - Después de actualizaciones masivas de contenido
            - Cuando la calidad de búsqueda se degrada
            """
        )

    # Inactive documents
    st.markdown("---")
    st.subheader("📴 Documentos Inactivos")
    inactive = db_stats.get("total_inactive", 0)

    if inactive > 0:
        st.warning(f"📴 {inactive} documentos están inactivos")
    else:
        st.success("✅ No hay documentos inactivos")

    # Detailed stats
    st.markdown("---")
    st.subheader("📋 Estadísticas Detalladas")

    with st.expander("Ver estadísticas completas"):
        st.json(stats)

else:
    st.error("❌ No se pudieron obtener las estadísticas. ¿Está corriendo la API?")

# Sidebar tips
st.sidebar.markdown("---")
st.sidebar.subheader("🔧 Gestión de Embeddings")
st.sidebar.markdown(
    """
Los embeddings son representaciones vectoriales de documentos
que permiten la búsqueda semántica inteligente.

**Indicadores:**
- ✅ **Cobertura**: % de documentos con embedding
- ⚠️ **Faltantes**: Documentos sin procesar
- 📴 **Inactivos**: Documentos desactivados

**Acciones:**
- 🔄 **Sincronizar**: Genera embeddings faltantes
- Esta operación puede tomar varios minutos
"""
)

st.sidebar.subheader("💡 Consejos")
st.sidebar.markdown(
    """
**Cuándo regenerar embeddings:**
1. Después de cambiar el modelo de embedding
2. Después de actualizaciones masivas de contenido
3. Si los resultados de búsqueda parecen incorrectos

**Modelo actual:** `nomic-embed-text:v1.5` (768 dimensiones)
"""
)
