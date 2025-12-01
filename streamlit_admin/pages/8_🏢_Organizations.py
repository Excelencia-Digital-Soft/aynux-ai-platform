"""
Organizations Management Page

CRUD operations for organizations (multi-tenant management).
"""

import sys
from pathlib import Path

import streamlit as st

# Add paths for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
streamlit_admin_root = Path(__file__).parent.parent
sys.path.insert(0, str(streamlit_admin_root))

from lib.api_client import (
    create_organization,
    delete_organization,
    get_my_organizations,
    get_organization,
    update_organization,
)
from lib.auth import check_auth, render_user_menu, require_auth
from lib.session_state import init_session_state

# Initialize session state
init_session_state()

# Page configuration
st.set_page_config(
    page_title="Organizations - Aynux Admin",
    page_icon="🏢",
    layout="wide",
)

# Auth check
if not require_auth():
    st.stop()


def render_org_list():
    """Render list of organizations."""
    st.subheader("Mis Organizaciones")

    organizations = get_my_organizations()

    if not organizations:
        st.info("No tienes organizaciones. Crea una nueva para comenzar.")
        return

    for org in organizations:
        with st.expander(f"🏢 {org.get('name', 'Sin nombre')}", expanded=False):
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                st.markdown(f"**Slug:** `{org.get('slug', '-')}`")
                st.markdown(f"**Plan:** {org.get('plan', 'free')}")
                st.markdown(f"**Estado:** {'Activo' if org.get('is_active') else 'Inactivo'}")

            with col2:
                st.markdown(f"**Usuarios:** {org.get('user_count', 0)} / {org.get('max_users', 5)}")
                st.markdown(f"**Agentes:** {org.get('agent_count', 0)} / {org.get('max_agents', 10)}")

            with col3:
                org_id = org.get("id")

                if st.button("Editar", key=f"edit_{org_id}"):
                    st.session_state.editing_org_id = org_id
                    st.rerun()

                if st.button("Eliminar", key=f"delete_{org_id}"):
                    st.session_state.confirm_delete_org = org_id


def render_create_form():
    """Render form to create a new organization."""
    st.subheader("Nueva Organizacion")

    with st.form("create_org_form"):
        name = st.text_input("Nombre", placeholder="Mi Empresa")
        slug = st.text_input("Slug (opcional)", placeholder="mi-empresa", help="Se genera automaticamente si no se especifica")

        col1, col2 = st.columns(2)
        with col1:
            plan = st.selectbox("Plan", options=["free", "starter", "professional", "enterprise"], index=0)
        with col2:
            max_users = st.number_input("Max Usuarios", min_value=1, max_value=100, value=5)

        max_agents = st.number_input("Max Agentes", min_value=1, max_value=50, value=10)

        submitted = st.form_submit_button("Crear Organizacion")

        if submitted:
            if not name:
                st.error("El nombre es requerido")
            else:
                data = {
                    "name": name,
                    "plan": plan,
                    "max_users": max_users,
                    "max_agents": max_agents,
                }
                if slug:
                    data["slug"] = slug

                with st.spinner("Creando organizacion..."):
                    result = create_organization(data)
                    if result:
                        st.success(f"Organizacion '{name}' creada exitosamente!")
                        # Refresh user info to get new org
                        from lib.auth import fetch_current_user

                        fetch_current_user()
                        st.rerun()


def render_edit_form(org_id: str):
    """Render form to edit an organization."""
    org = get_organization(org_id)

    if not org:
        st.error("Organizacion no encontrada")
        if st.button("Volver"):
            st.session_state.editing_org_id = None
            st.rerun()
        return

    st.subheader(f"Editar: {org.get('name')}")

    if st.button("← Volver a la lista"):
        st.session_state.editing_org_id = None
        st.rerun()

    with st.form("edit_org_form"):
        name = st.text_input("Nombre", value=org.get("name", ""))

        col1, col2 = st.columns(2)
        with col1:
            plan_options = ["free", "starter", "professional", "enterprise"]
            current_plan = org.get("plan", "free")
            plan_index = plan_options.index(current_plan) if current_plan in plan_options else 0
            plan = st.selectbox("Plan", options=plan_options, index=plan_index)

        with col2:
            is_active = st.checkbox("Activo", value=org.get("is_active", True))

        col3, col4 = st.columns(2)
        with col3:
            max_users = st.number_input("Max Usuarios", min_value=1, max_value=100, value=org.get("max_users", 5))
        with col4:
            max_agents = st.number_input("Max Agentes", min_value=1, max_value=50, value=org.get("max_agents", 10))

        submitted = st.form_submit_button("Guardar Cambios")

        if submitted:
            data = {
                "name": name,
                "plan": plan,
                "is_active": is_active,
                "max_users": max_users,
                "max_agents": max_agents,
            }

            with st.spinner("Guardando..."):
                result = update_organization(org_id, data)
                if result:
                    st.success("Cambios guardados exitosamente!")
                    st.session_state.editing_org_id = None
                    st.rerun()


def render_delete_confirmation(org_id: str):
    """Render delete confirmation dialog."""
    org = get_organization(org_id)

    if not org:
        st.session_state.confirm_delete_org = None
        return

    st.warning(f"¿Estas seguro de eliminar la organizacion '{org.get('name')}'?")
    st.caption("Esta accion no se puede deshacer. Se eliminaran todos los usuarios, configuraciones y datos asociados.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancelar", use_container_width=True):
            st.session_state.confirm_delete_org = None
            st.rerun()

    with col2:
        if st.button("Eliminar", type="primary", use_container_width=True):
            with st.spinner("Eliminando..."):
                if delete_organization(org_id):
                    st.success("Organizacion eliminada")
                    st.session_state.confirm_delete_org = None
                    # Refresh user info
                    from lib.auth import fetch_current_user

                    fetch_current_user()
                    st.rerun()


# Main page
st.title("🏢 Gestion de Organizaciones")
st.markdown("---")

# Initialize state
if "editing_org_id" not in st.session_state:
    st.session_state.editing_org_id = None
if "confirm_delete_org" not in st.session_state:
    st.session_state.confirm_delete_org = None

# Tabs
tab1, tab2 = st.tabs(["📋 Mis Organizaciones", "➕ Nueva Organizacion"])

with tab1:
    if st.session_state.confirm_delete_org:
        render_delete_confirmation(st.session_state.confirm_delete_org)
    elif st.session_state.editing_org_id:
        render_edit_form(st.session_state.editing_org_id)
    else:
        render_org_list()

with tab2:
    render_create_form()

# Render user menu in sidebar
render_user_menu()
