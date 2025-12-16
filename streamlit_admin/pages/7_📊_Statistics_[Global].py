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

st.title("📊 Estadísticas de la Base de Conocimiento")
st.markdown("Visualiza estadísticas y métricas de la base de conocimiento.")

# Refresh button
if st.button("🔄 Actualizar Estadísticas"):
    st.rerun()

stats = get_knowledge_stats()

if stats:
    # Database stats
    db_stats = stats.get("database", {})

    st.subheader("📊 Estadísticas de Documentos")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("📄 Documentos Activos", db_stats.get("total_active", 0))

    with col2:
        st.metric("🗂️ Documentos Inactivos", db_stats.get("total_inactive", 0))

    with col3:
        missing = db_stats.get("missing_embeddings", 0)
        st.metric(
            "⚠️ Embeddings Faltantes",
            missing,
            delta=-missing if missing > 0 else None,
            delta_color="inverse",
        )

    with col4:
        coverage = db_stats.get("embedding_coverage", 0)
        st.metric("✅ Cobertura de Embeddings", f"{coverage}%")

    # Coverage visualization
    st.markdown("---")
    st.subheader("📈 Cobertura de Embeddings")
    st.progress(coverage / 100)

    if coverage < 100:
        st.warning(f"⚠️ {100 - coverage:.1f}% de los documentos no tienen embeddings")
    else:
        st.success("✅ ¡Todos los documentos tienen embeddings!")

    # Model info
    st.markdown("---")
    st.subheader("🤖 Modelo de Embedding")
    st.code(stats.get("embedding_model", "N/A"))

    # By document type (if available)
    by_type = db_stats.get("by_type", {})
    if by_type:
        st.markdown("---")
        st.subheader("📋 Documentos por Tipo")

        import pandas as pd

        df = pd.DataFrame(list(by_type.items()), columns=["Tipo", "Cantidad"])
        st.bar_chart(df.set_index("Tipo"))

    # Raw stats
    st.markdown("---")
    with st.expander("🔍 Ver Estadísticas Completas"):
        st.json(stats)

else:
    st.error("❌ No se pudieron obtener las estadísticas. ¿Está corriendo la API?")

# Sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Estadísticas")
st.sidebar.markdown(
    """
Visualiza métricas de salud y uso de la base
de conocimiento.

**Métricas principales:**
- 📄 Total de documentos activos/inactivos
- 🔄 Cobertura de embeddings
- 📋 Distribución por tipo de documento
- 🤖 Modelo de embedding en uso

Usa esta información para identificar
documentos sin procesar o problemas de cobertura.
"""
)

st.sidebar.subheader("📖 Acerca de Estadísticas")
st.sidebar.markdown(
    """
- **Documentos Activos**: Disponibles para búsqueda
- **Documentos Inactivos**: Desactivados del sistema
- **Embeddings Faltantes**: Sin representación vectorial
- **Cobertura**: % de documentos con embeddings

**Modelo de Embedding** muestra el modelo usado
para generar embeddings de documentos.
"""
)
