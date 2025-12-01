"""
Aynux Admin Dashboard - Unified Streamlit Application

Interactive UI for:
- User authentication and organization management
- Chat testing and agent flow visualization
- Knowledge base management (CRUD, search, embeddings)
- Excelencia modules and demos management
- Agent and tenant configuration

Run with: streamlit run streamlit_admin/app.py
"""

import os
import sys
from pathlib import Path

import requests
import streamlit as st

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Initialize session state
from lib.session_state import init_session_state
from lib.auth import check_auth, render_user_menu

init_session_state()

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001")

# Page configuration
st.set_page_config(
    page_title="Aynux Admin",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Home page content
st.title("🚀 Aynux Admin Dashboard")
st.markdown("---")

st.markdown(
    """
### Herramientas Disponibles

Usa el menu lateral para navegar entre las secciones.

| Seccion | Descripcion |
|---------|-------------|
| 🔐 **Login** | Autenticacion y perfil de usuario |
| 🤖 **Chat Visualizer** | Probar chat y visualizar flujo de agentes |
| 📚 **Knowledge Base** | Explorar, editar y buscar documentos RAG |
| 📤 **Upload Documents** | Subir PDFs y texto al knowledge base |
| 🔧 **Embeddings** | Dashboard de embeddings y sincronizacion |
| 🏢 **Excelencia** | Gestion de modulos y demos ERP |
| ⚙️ **Agent Config** | Configuracion de agentes |
| 📊 **Statistics** | Estadisticas del knowledge base |
| 🏢 **Organizations** | Gestion de organizaciones (multi-tenant) |
| 👥 **Users** | Gestion de usuarios por organizacion |
| ⚙️ **Tenant Config** | Configuracion del tenant (dominios, RAG, agentes, prompts) |
"""
)

st.markdown("---")

# Health check
st.subheader("🔌 Estado del Sistema")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**API Backend**")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            st.success("✅ API conectada")
            health_data = response.json()
            if isinstance(health_data, dict):
                st.json(health_data)
        else:
            st.warning(f"⚠️ API respondió con status {response.status_code}")
    except requests.exceptions.ConnectionError:
        st.error("❌ API no disponible - Verifica que el servidor esté corriendo")
    except requests.exceptions.Timeout:
        st.error("❌ API timeout - El servidor está tardando en responder")
    except Exception as e:
        st.error(f"❌ Error: {e}")

with col2:
    st.markdown("**Configuración**")
    st.code(f"API_BASE_URL: {API_BASE_URL}")
    st.code(f"Project Root: {project_root}")

st.markdown("---")

# Quick actions
st.subheader("⚡ Acciones Rápidas")

col_action1, col_action2, col_action3 = st.columns(3)

with col_action1:
    st.markdown("**Knowledge Base**")
    st.page_link("pages/2_📚_Knowledge_Base.py", label="📋 Browse Documents", icon="📋")
    st.page_link("pages/3_📤_Upload_Documents.py", label="📤 Upload New", icon="📤")

with col_action2:
    st.markdown("**Excelencia**")
    st.page_link("pages/5_🏢_Excelencia.py", label="🏢 Manage Modules", icon="🏢")

with col_action3:
    st.markdown("**System**")
    st.page_link("pages/4_🔧_Embeddings.py", label="🔧 Embeddings", icon="🔧")
    st.page_link("pages/7_📊_Statistics.py", label="📊 Statistics", icon="📊")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
        <p>Aynux Admin Dashboard v1.0</p>
        <p>Powered by Aynux Multi-Agent System</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Render user menu in sidebar if authenticated
render_user_menu()
