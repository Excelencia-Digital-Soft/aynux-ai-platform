"""
Users Management Page

Manage users within the current organization.
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
    get_org_users,
    invite_user,
    remove_user,
    update_user_role,
)
from lib.auth import (
    check_auth,
    get_current_org_id,
    is_admin_or_owner,
    is_owner,
    render_user_menu,
    require_org,
    require_role,
)
from lib.session_state import init_session_state

# Initialize session state
init_session_state()

# Page configuration
st.set_page_config(
    page_title="Users - Aynux Admin",
    page_icon="👥",
    layout="wide",
)

# Auth and org check
if not require_org():
    st.stop()

# Require at least admin role
if not require_role("admin"):
    st.stop()

org_id = get_current_org_id()


def render_users_list():
    """Render list of users in the organization."""
    st.subheader("Usuarios de la Organizacion")

    users = get_org_users(org_id)

    if not users:
        st.info("No hay usuarios en esta organizacion.")
        return

    # Create a table-like display
    for user in users:
        user_id = user.get("user_id")
        username = user.get("username", "N/A")
        email = user.get("email", "N/A")
        role = user.get("role", "member")
        joined_at = user.get("joined_at", "")

        col1, col2, col3, col4 = st.columns([2, 2, 1, 1])

        with col1:
            st.markdown(f"**{username}**")
            st.caption(email)

        with col2:
            role_colors = {"owner": "🟢 Owner", "admin": "🔵 Admin", "member": "⚪ Member"}
            st.markdown(role_colors.get(role, role))
            if joined_at:
                st.caption(f"Desde: {joined_at[:10]}")

        with col3:
            # Role change (only owner can change roles)
            if is_owner() and role != "owner":
                new_role = st.selectbox(
                    "Rol",
                    options=["member", "admin"],
                    index=0 if role == "member" else 1,
                    key=f"role_{user_id}",
                    label_visibility="collapsed",
                )
                if new_role != role:
                    if st.button("Guardar", key=f"save_role_{user_id}"):
                        with st.spinner("Actualizando..."):
                            result = update_user_role(org_id, user_id, new_role)
                            if result:
                                st.success("Rol actualizado")
                                st.rerun()

        with col4:
            # Remove user (cannot remove self or owner)
            current_user_id = st.session_state.get("user_id")
            if user_id != current_user_id and role != "owner":
                if st.button("Eliminar", key=f"remove_{user_id}"):
                    st.session_state.confirm_remove_user = user_id
                    st.session_state.confirm_remove_username = username

        st.markdown("---")


def render_invite_form():
    """Render form to invite a new user."""
    st.subheader("Invitar Usuario")

    with st.form("invite_user_form"):
        email = st.text_input("Email del usuario", placeholder="usuario@ejemplo.com")

        role = st.selectbox(
            "Rol",
            options=["member", "admin"],
            index=0,
            help="Member: acceso basico. Admin: puede gestionar usuarios y configuracion.",
        )

        submitted = st.form_submit_button("Enviar Invitacion")

        if submitted:
            if not email:
                st.error("El email es requerido")
            elif "@" not in email:
                st.error("Email invalido")
            else:
                data = {"email": email, "role": role}

                with st.spinner("Enviando invitacion..."):
                    result = invite_user(org_id, data)
                    if result:
                        st.success(f"Invitacion enviada a {email}")
                        st.rerun()

    st.markdown("---")
    st.caption("El usuario debe tener una cuenta existente para ser agregado a la organizacion.")


def render_remove_confirmation():
    """Render remove user confirmation."""
    user_id = st.session_state.confirm_remove_user
    username = st.session_state.confirm_remove_username

    st.warning(f"¿Estas seguro de eliminar al usuario '{username}' de la organizacion?")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Cancelar", use_container_width=True):
            st.session_state.confirm_remove_user = None
            st.session_state.confirm_remove_username = None
            st.rerun()

    with col2:
        if st.button("Eliminar", type="primary", use_container_width=True):
            with st.spinner("Eliminando..."):
                if remove_user(org_id, user_id):
                    st.success(f"Usuario '{username}' eliminado de la organizacion")
                    st.session_state.confirm_remove_user = None
                    st.session_state.confirm_remove_username = None
                    st.rerun()


# Main page
st.title("👥 Gestion de Usuarios")
st.markdown(f"**Organizacion:** {st.session_state.current_org_name}")
st.markdown("---")

# Initialize state
if "confirm_remove_user" not in st.session_state:
    st.session_state.confirm_remove_user = None
if "confirm_remove_username" not in st.session_state:
    st.session_state.confirm_remove_username = None

# Show confirmation dialog if needed
if st.session_state.confirm_remove_user:
    render_remove_confirmation()
    st.stop()

# Tabs
tab1, tab2 = st.tabs(["📋 Usuarios", "➕ Invitar Usuario"])

with tab1:
    render_users_list()

with tab2:
    render_invite_form()

# Render user menu in sidebar
render_user_menu()
