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
# Hardcoded API URL for Streamlit admin (not configurable via .env)
API_BASE_URL = "http://localhost:8001"

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

Usa el menú lateral para navegar entre las secciones.

#### 🌐 Modo Global (Sistema Excelencia)

| Sección | Descripción |
|---------|-------------|
| 🔐 **Login** | Autenticación de usuarios y gestión de sesiones |
| 🤖 **Chat Visualizer** | Prueba el chatbot en tiempo real. Visualiza el flujo de ejecución de agentes, razonamiento del orquestador y métricas de rendimiento |
| 📚 **Knowledge Base** | Gestiona la base de conocimiento RAG. Explora, edita, busca y elimina documentos con búsqueda semántica |
| 📤 **Upload Documents** | Sube archivos PDF o texto plano a la base de conocimiento con extracción automática de contenido |
| 🔧 **Embeddings** | Dashboard de gestión de embeddings vectoriales. Monitorea cobertura y sincroniza embeddings faltantes |
| 🏢 **Excelencia** | Gestiona el catálogo de software Excelencia: módulos, demos, precios y categorías de productos ERP |
| ⚙️ **Agent Config** | Configura agentes del sistema: habilita/deshabilita, ajusta prioridades y parámetros |
| 📊 **Statistics** | Estadísticas completas de la base de conocimiento: documentos por tipo, cobertura de embeddings |

#### 🏢 Modo Multi-Tenant (SaaS)

| Sección | Descripción |
|---------|-------------|
| 🏢 **Organizations** | Gestiona organizaciones: crear, editar, asignar planes y límites de uso |
| 👥 **Users** | Gestiona usuarios por organización: roles, permisos y acceso |
| ⚙️ **Tenant Config** | Configuración por tenant: dominios habilitados, RAG, agentes y prompts personalizados |
| 📄 **Tenant Documents** | Documentos aislados por organización con búsqueda semántica independiente |
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
    st.markdown("**Base de Conocimiento**")
    st.page_link("pages/2_📚_Knowledge_Base_[Global].py", label="📋 Explorar Documentos", icon="📋")
    st.page_link("pages/3_📤_Upload_Documents_[Global].py", label="📤 Subir Nuevo", icon="📤")

with col_action2:
    st.markdown("**Excelencia**")
    st.page_link("pages/5_🏢_Excelencia_[Global].py", label="🏢 Gestionar Módulos", icon="🏢")

with col_action3:
    st.markdown("**Sistema**")
    st.page_link("pages/4_🔧_Embeddings_[Global].py", label="🔧 Embeddings", icon="🔧")
    st.page_link("pages/7_📊_Statistics_[Global].py", label="📊 Estadísticas", icon="📊")

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
