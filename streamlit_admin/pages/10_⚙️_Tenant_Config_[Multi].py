"""
Tenant Configuration Page

Configure domains, RAG, agents, and prompts for the current organization.
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
    create_tenant_agent,
    create_tenant_prompt,
    delete_tenant_agent,
    delete_tenant_prompt,
    get_tenant_agents,
    get_tenant_config,
    get_tenant_prompts,
    init_builtin_agents,
    toggle_tenant_agent,
    update_rag_config,
    update_domains_config,
    update_tenant_agent,
    update_tenant_config,
    update_tenant_prompt,
)
from lib.auth import (
    get_current_org_id,
    render_user_menu,
    require_role,
)
from lib.session_state import init_session_state

# Initialize session state
init_session_state()

# Page configuration
st.set_page_config(
    page_title="Tenant Config - Aynux Admin",
    page_icon="⚙️",
    layout="wide",
)

# Require admin role
if not require_role("admin"):
    st.stop()

org_id = get_current_org_id()


def render_general_config():
    """Render general tenant configuration."""
    st.subheader("Configuracion General")

    config = get_tenant_config(org_id)

    if not config:
        st.error("No se pudo cargar la configuracion")
        return

    with st.form("general_config_form"):
        col1, col2 = st.columns(2)

        with col1:
            # Domains
            st.markdown("**Dominios**")
            all_domains = ["ecommerce", "healthcare", "credit", "excelencia"]
            enabled_domains = config.get("enabled_domains", ["ecommerce"])

            selected_domains = st.multiselect(
                "Dominios habilitados",
                options=all_domains,
                default=enabled_domains,
                help="Selecciona los dominios de negocio activos",
            )

            default_domain = st.selectbox(
                "Dominio por defecto",
                options=selected_domains if selected_domains else ["ecommerce"],
                index=0,
            )

        with col2:
            # Agent settings
            st.markdown("**Agentes**")
            agent_timeout = st.number_input(
                "Timeout de agente (segundos)",
                min_value=5,
                max_value=300,
                value=config.get("agent_timeout_seconds", 30),
            )

            prompt_scope = st.selectbox(
                "Scope de prompts",
                options=["system", "global", "org"],
                index=["system", "global", "org"].index(config.get("prompt_scope", "org")),
                help="system: prompts del sistema, global: prompts globales, org: prompts de la organizacion",
            )

        st.markdown("---")

        # WhatsApp settings
        st.markdown("**WhatsApp (opcional)**")
        col3, col4 = st.columns(2)

        with col3:
            whatsapp_phone_id = st.text_input(
                "WhatsApp Phone Number ID",
                value=config.get("whatsapp_phone_number_id") or "",
                type="password",
            )

        with col4:
            whatsapp_verify_token = st.text_input(
                "WhatsApp Verify Token",
                value=config.get("whatsapp_verify_token") or "",
                type="password",
            )

        submitted = st.form_submit_button("Guardar Configuracion")

        if submitted:
            if not selected_domains:
                st.error("Debes seleccionar al menos un dominio")
            else:
                data = {
                    "enabled_domains": selected_domains,
                    "default_domain": default_domain,
                    "agent_timeout_seconds": agent_timeout,
                    "prompt_scope": prompt_scope,
                }
                if whatsapp_phone_id:
                    data["whatsapp_phone_number_id"] = whatsapp_phone_id
                if whatsapp_verify_token:
                    data["whatsapp_verify_token"] = whatsapp_verify_token

                with st.spinner("Guardando..."):
                    result = update_tenant_config(org_id, data)
                    if result:
                        st.success("Configuracion guardada!")
                        st.rerun()


def render_rag_config():
    """Render RAG configuration."""
    st.subheader("Configuracion RAG")

    config = get_tenant_config(org_id)

    if not config:
        st.error("No se pudo cargar la configuracion")
        return

    with st.form("rag_config_form"):
        rag_enabled = st.checkbox(
            "RAG Habilitado",
            value=config.get("rag_enabled", True),
            help="Habilita la busqueda semantica en el knowledge base",
        )

        col1, col2 = st.columns(2)

        with col1:
            similarity_threshold = st.slider(
                "Umbral de similaridad",
                min_value=0.0,
                max_value=1.0,
                value=config.get("rag_similarity_threshold", 0.7),
                step=0.05,
                help="Mayor valor = resultados mas relevantes pero menos resultados",
            )

        with col2:
            max_results = st.number_input(
                "Resultados maximos",
                min_value=1,
                max_value=50,
                value=config.get("rag_max_results", 10),
                help="Numero maximo de documentos a retornar",
            )

        submitted = st.form_submit_button("Guardar Configuracion RAG")

        if submitted:
            data = {
                "rag_enabled": rag_enabled,
                "rag_similarity_threshold": similarity_threshold,
                "rag_max_results": max_results,
            }

            with st.spinner("Guardando..."):
                result = update_rag_config(org_id, data)
                if result:
                    st.success("Configuracion RAG guardada!")


def render_agents_config():
    """Render agents configuration."""
    st.subheader("Configuracion de Agentes")

    # Initialize builtin agents button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("Inicializar Agentes Builtin"):
            with st.spinner("Inicializando..."):
                result = init_builtin_agents(org_id)
                if result:
                    st.success(f"Se inicializaron {result.get('total', 0)} agentes")
                    st.rerun()

    agents = get_tenant_agents(org_id)

    if not agents:
        st.info("No hay agentes configurados. Haz click en 'Inicializar Agentes Builtin' para crear los agentes por defecto.")
        return

    # Agent list
    for agent in agents:
        agent_id = agent.get("id")
        agent_key = agent.get("agent_key")
        display_name = agent.get("display_name")
        enabled = agent.get("enabled", True)
        agent_type = agent.get("agent_type", "specialized")
        priority = agent.get("priority", 0)

        with st.expander(f"{'✅' if enabled else '❌'} {display_name} ({agent_key})", expanded=False):
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                st.markdown(f"**Tipo:** {agent_type}")
                st.markdown(f"**Prioridad:** {priority}")
                if agent.get("description"):
                    st.caption(agent.get("description"))

            with col2:
                keywords = agent.get("keywords", [])
                if keywords:
                    st.markdown("**Keywords:**")
                    st.caption(", ".join(keywords[:5]))

            with col3:
                # Toggle enabled
                if st.button("Toggle", key=f"toggle_{agent_id}"):
                    with st.spinner("Actualizando..."):
                        result = toggle_tenant_agent(org_id, agent_id)
                        if result:
                            st.rerun()

                # Delete (not for builtin)
                if agent_type == "custom":
                    if st.button("Eliminar", key=f"delete_agent_{agent_id}"):
                        with st.spinner("Eliminando..."):
                            if delete_tenant_agent(org_id, agent_id):
                                st.success("Agente eliminado")
                                st.rerun()


def render_prompts_config():
    """Render prompts configuration."""
    st.subheader("Prompts Personalizados")

    # Tabs for list and create
    tab_list, tab_create = st.tabs(["📋 Prompts", "➕ Nuevo Prompt"])

    with tab_list:
        prompts = get_tenant_prompts(org_id)

        if not prompts:
            st.info("No hay prompts personalizados. Los prompts del sistema se usaran por defecto.")
        else:
            for prompt in prompts:
                prompt_id = prompt.get("id")
                prompt_key = prompt.get("prompt_key")
                scope = prompt.get("scope")
                template = prompt.get("template", "")
                is_active = prompt.get("is_active", True)
                version = prompt.get("version", 1)

                with st.expander(f"{'✅' if is_active else '❌'} {prompt_key} (v{version})", expanded=False):
                    st.markdown(f"**Scope:** {scope}")

                    # Show template preview
                    st.text_area(
                        "Template",
                        value=template[:500] + ("..." if len(template) > 500 else ""),
                        height=100,
                        disabled=True,
                        key=f"preview_{prompt_id}",
                    )

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Editar", key=f"edit_prompt_{prompt_id}"):
                            st.session_state.editing_prompt_id = prompt_id

                    with col2:
                        if st.button("Eliminar", key=f"delete_prompt_{prompt_id}"):
                            with st.spinner("Eliminando..."):
                                if delete_tenant_prompt(org_id, prompt_id):
                                    st.success("Prompt eliminado")
                                    st.rerun()

    with tab_create:
        with st.form("create_prompt_form"):
            prompt_key = st.text_input(
                "Clave del prompt",
                placeholder="greeting.welcome",
                help="Identificador unico del prompt",
            )

            template = st.text_area(
                "Template",
                height=200,
                placeholder="Hola {nombre}, bienvenido a {empresa}...",
                help="Usa {variable} para variables dinamicas",
            )

            col1, col2 = st.columns(2)
            with col1:
                scope = st.selectbox("Scope", options=["org", "user"], index=0)
            with col2:
                description = st.text_input("Descripcion (opcional)")

            submitted = st.form_submit_button("Crear Prompt")

            if submitted:
                if not prompt_key or not template:
                    st.error("La clave y el template son requeridos")
                else:
                    data = {
                        "prompt_key": prompt_key,
                        "template": template,
                        "scope": scope,
                    }
                    if description:
                        data["description"] = description

                    with st.spinner("Creando..."):
                        result = create_tenant_prompt(org_id, data)
                        if result:
                            st.success("Prompt creado!")
                            st.rerun()


# Main page
st.title("⚙️ Configuracion del Tenant")
st.markdown(f"**Organizacion:** {st.session_state.current_org_name}")
st.markdown("---")

# Initialize state
if "editing_prompt_id" not in st.session_state:
    st.session_state.editing_prompt_id = None

# Tabs for different config sections
tab1, tab2, tab3, tab4 = st.tabs(["🌐 General", "🔍 RAG", "🤖 Agentes", "💬 Prompts"])

with tab1:
    render_general_config()

with tab2:
    render_rag_config()

with tab3:
    render_agents_config()

with tab4:
    render_prompts_config()

# Render user menu in sidebar
render_user_menu()
