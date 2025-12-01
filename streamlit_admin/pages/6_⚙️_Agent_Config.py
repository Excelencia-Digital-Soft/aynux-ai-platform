"""
Agent Configuration - Excelencia Agent Settings

Interactive UI for:
- Viewing and editing agent modules
- Viewing agent settings
"""

import sys
from pathlib import Path

import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from lib.api_client import get_agent_config, update_agent_modules
from lib.session_state import init_session_state

init_session_state()

st.title("⚙️ Agent Configuration")
st.markdown("View and edit Excelencia agent modules and settings.")

# Get current configuration
config = get_agent_config()

if config:
    tab_modules, tab_settings = st.tabs(["🔧 Modules", "⚙️ Settings"])

    # Tab: Modules
    with tab_modules:
        st.subheader("Agent Modules")
        st.info("⚠️ Changes to modules require application restart!")

        modules = config.get("modules", {})

        for module_id, module_data in modules.items():
            with st.expander(f"🏥 {module_data['name']}", expanded=False):
                new_name = st.text_input("Name", value=module_data["name"], key=f"name_{module_id}")
                new_desc = st.text_area("Description", value=module_data["description"], key=f"desc_{module_id}")
                new_target = st.text_input("Target Audience", value=module_data["target"], key=f"target_{module_id}")

                features_text = "\n".join(module_data["features"])
                new_features = st.text_area(
                    "Features (one per line)", value=features_text, key=f"features_{module_id}", height=150
                )

                if st.button(f"💾 Save {module_data['name']}", key=f"save_{module_id}"):
                    updated_module = {
                        "name": new_name,
                        "description": new_desc,
                        "target": new_target,
                        "features": [f.strip() for f in new_features.split("\n") if f.strip()],
                    }

                    result = update_agent_modules({module_id: updated_module}, create_backup=True)

                    if result:
                        st.success("✅ Module updated successfully!")
                        st.warning("⚠️ Restart the application for changes to take effect")
                        st.json(result)

    # Tab: Settings
    with tab_settings:
        st.subheader("Agent Settings")

        settings = config.get("settings", {})

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Model", settings.get("model", "N/A"))
            st.metric("Temperature", settings.get("temperature", "N/A"))
            st.metric("Max Response Length", settings.get("max_response_length", "N/A"))

        with col2:
            st.metric("Use RAG", "✅" if settings.get("use_rag") else "❌")
            st.metric("RAG Max Results", settings.get("rag_max_results", "N/A"))

        st.info("💡 Settings update functionality coming soon!")

        # Show raw config
        with st.expander("View Raw Configuration"):
            st.json(config)

else:
    st.error("❌ Unable to fetch agent configuration. Is the API running?")

# Sidebar info
st.sidebar.subheader("💡 About Agent Config")
st.sidebar.markdown(
    """
This page allows you to configure the Excelencia agent's:

**Modules:**
- Name and description
- Target audience
- Features list

**Settings:**
- LLM model selection
- Temperature
- Response length limits
- RAG configuration

**Note:** Changes require an application restart to take effect.
"""
)
