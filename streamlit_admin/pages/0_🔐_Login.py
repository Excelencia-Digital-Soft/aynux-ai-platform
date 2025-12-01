"""
Login Page - User Authentication

Provides login form and user session management.
"""

import os
import sys
from pathlib import Path

import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Add streamlit_admin to path for lib imports
streamlit_admin_root = Path(__file__).parent.parent
sys.path.insert(0, str(streamlit_admin_root))

from lib.auth import check_auth, login, logout, render_user_menu
from lib.session_state import init_session_state

# Initialize session state
init_session_state()

# Page configuration
st.set_page_config(
    page_title="Login - Aynux Admin",
    page_icon="🔐",
    layout="centered",
)


def render_login_form():
    """Render the login form."""
    st.title("🔐 Iniciar Sesion")
    st.markdown("---")

    # Show error if exists
    if st.session_state.get("login_error"):
        st.error(st.session_state.login_error)

    with st.form("login_form"):
        email = st.text_input("Email", placeholder="usuario@ejemplo.com")
        password = st.text_input("Password", type="password", placeholder="Tu password")

        col1, col2 = st.columns([1, 1])
        with col1:
            submitted = st.form_submit_button("Iniciar Sesion", use_container_width=True)

        if submitted:
            if not email or not password:
                st.error("Por favor ingresa email y password")
            else:
                with st.spinner("Autenticando..."):
                    if login(email, password):
                        st.success("Login exitoso!")
                        st.rerun()
                    # Error is shown via st.error from login_error state

    st.markdown("---")
    st.caption("Sistema de administracion multi-tenant de Aynux")


def render_user_profile():
    """Render user profile when logged in."""
    st.title("🔐 Perfil de Usuario")
    st.markdown("---")

    # User info
    st.subheader("Informacion de Usuario")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**Usuario:** {st.session_state.username}")
        st.markdown(f"**ID:** `{st.session_state.user_id}`")

    with col2:
        if st.session_state.current_org_name:
            st.markdown(f"**Organizacion:** {st.session_state.current_org_name}")
            st.markdown(f"**Rol:** {st.session_state.current_role}")

    st.markdown("---")

    # Organizations
    st.subheader("Mis Organizaciones")

    if st.session_state.organizations:
        for org in st.session_state.organizations:
            org_id = org.get("organization_id")
            org_name = org.get("organization_name")
            role = org.get("role")
            is_current = org_id == st.session_state.current_org_id

            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                if is_current:
                    st.markdown(f"**{org_name}** ✓")
                else:
                    st.markdown(org_name)
            with col2:
                role_colors = {"owner": "🟢", "admin": "🔵", "member": "⚪"}
                st.markdown(f"{role_colors.get(role, '⚪')} {role}")
            with col3:
                if not is_current:
                    if st.button("Seleccionar", key=f"select_org_{org_id}"):
                        from lib.auth import switch_organization

                        switch_organization(org_id)
                        st.rerun()
    else:
        st.info("No perteneces a ninguna organizacion.")

    st.markdown("---")

    # Logout button
    if st.button("🚪 Cerrar Sesion", use_container_width=True):
        logout()
        st.rerun()


# Main render
if check_auth():
    render_user_profile()
    render_user_menu()
else:
    render_login_form()
