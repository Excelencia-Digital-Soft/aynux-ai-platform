"""
Excelencia - Software Catalog Management

Interactive UI for managing software products (from company_knowledge).
"""

import sys
from pathlib import Path

import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from lib.api_client import (
    create_module,
    delete_module,
    get_modules,
    update_module,
)
from lib.session_state import init_session_state

init_session_state()

st.title("🏢 Excelencia Management")
st.markdown("Manage software products from company_knowledge.")

# ============================================================================
# Software Catalog Section
# ============================================================================

st.subheader("🔧 Software Catalog")
st.caption("Software products from company_knowledge (document_type: software_catalog)")

sub_tab_list, sub_tab_create = st.tabs(["📋 Module List", "➕ Create Module"])

# Sub-tab: Module List
with sub_tab_list:
    col_filter1, col_filter2, col_refresh = st.columns([2, 2, 1])
    with col_filter1:
        filter_category = st.selectbox(
            "Filter by Category",
            ["All", "salud", "hotelería", "financiero", "gremios", "productos", "servicios públicos"],
        )
    with col_filter2:
        filter_status = st.selectbox("Filter by Status", ["All", "active", "deprecated"])
    with col_refresh:
        if st.button("🔄 Refresh", key="refresh_modules"):
            st.rerun()

    modules = get_modules(
        category=None if filter_category == "All" else filter_category,
        status=None if filter_status == "All" else filter_status,
    )

    if modules:
        for mod in modules:
            mod_id = mod.get("id") or mod.get("code")
            is_editing = st.session_state.editing_module_id == mod_id

            with st.expander(f"🔧 {mod['name']} ({mod['code']})", expanded=is_editing):
                if is_editing:
                    st.markdown("### ✏️ Editing Module")

                    edit_name = st.text_input("Name", value=mod["name"], key=f"mod_name_{mod_id}")
                    edit_desc = st.text_area("Description", value=mod.get("description", ""), key=f"mod_desc_{mod_id}")

                    categories = ["salud", "hotelería", "financiero", "gremios", "productos", "servicios públicos", "general"]
                    edit_category = st.selectbox(
                        "Category",
                        categories,
                        index=categories.index(mod.get("category", "general")) if mod.get("category") in categories else 6,
                        key=f"mod_cat_{mod_id}",
                    )

                    statuses = ["active", "beta", "coming_soon", "deprecated"]
                    edit_status = st.selectbox(
                        "Status",
                        statuses,
                        index=statuses.index(mod.get("status", "active")) if mod.get("status") in statuses else 0,
                        key=f"mod_status_{mod_id}",
                    )

                    edit_features = st.text_area(
                        "Features (one per line)",
                        value="\n".join(mod.get("features", [])),
                        height=150,
                        key=f"mod_features_{mod_id}",
                    )

                    tiers = ["standard", "premium", "enterprise"]
                    edit_tier = st.selectbox(
                        "Pricing Tier",
                        tiers,
                        index=tiers.index(mod.get("pricing_tier", "standard")) if mod.get("pricing_tier") in tiers else 0,
                        key=f"mod_tier_{mod_id}",
                    )

                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        if st.button("💾 Save", key=f"mod_save_{mod_id}", type="primary"):
                            update_data = {
                                "name": edit_name,
                                "description": edit_desc,
                                "category": edit_category,
                                "status": edit_status,
                                "features": [f.strip() for f in edit_features.split("\n") if f.strip()],
                                "pricing_tier": edit_tier,
                            }
                            result = update_module(mod_id, update_data)
                            if result:
                                st.success("✅ Module updated!")
                                st.session_state.editing_module_id = None
                                st.rerun()
                    with col_cancel:
                        if st.button("❌ Cancel", key=f"mod_cancel_{mod_id}"):
                            st.session_state.editing_module_id = None
                            st.rerun()

                else:
                    st.markdown(f"**Code:** `{mod['code']}`")
                    st.markdown(f"**Category:** {mod['category']}")
                    st.markdown(f"**Status:** {mod['status']}")
                    st.markdown(f"**Pricing Tier:** {mod.get('pricing_tier', 'standard')}")
                    st.markdown(f"**Description:** {mod.get('description', 'N/A')}")

                    features = mod.get("features", [])
                    if features:
                        st.markdown("**Features:**")
                        for feat in features:
                            st.markdown(f"  - {feat}")

                    col_edit, col_soft, col_hard = st.columns(3)

                    with col_edit:
                        if st.button("✏️ Edit", key=f"mod_edit_{mod_id}"):
                            st.session_state.editing_module_id = mod_id
                            st.rerun()

                    with col_soft:
                        if st.button("🗑️ Deprecate", key=f"mod_soft_{mod_id}"):
                            if delete_module(mod_id, hard_delete=False):
                                st.success("Module deprecated")
                                st.rerun()

                    with col_hard:
                        if st.button("❌ Delete", key=f"mod_hard_{mod_id}", type="secondary"):
                            if delete_module(mod_id, hard_delete=True):
                                st.success("Module deleted")
                                st.rerun()
    else:
        st.info("No modules found")

# Sub-tab: Create Module
with sub_tab_create:
    st.subheader("Create New Software Product")
    st.caption("Creates a new entry in company_knowledge with document_type: software_catalog")

    new_code = st.text_input("Code *", placeholder="e.g., MEDBOT-001", help="Unique product code")
    new_name = st.text_input("Name *", placeholder="Product name")
    new_category = st.selectbox(
        "Category *",
        ["salud", "hotelería", "financiero", "gremios", "productos", "servicios públicos", "general"],
        key="new_mod_category",
    )
    new_description = st.text_area("Description", placeholder="Product description (will be stored as content)")
    new_status = st.selectbox("Status", ["active", "deprecated"], key="new_mod_status")
    new_features = st.text_area("Tags (one per line)", placeholder="chatbot\nwhatsapp\nsalud", help="Will be stored as tags")
    new_tier = st.selectbox("Pricing Tier", ["standard", "premium", "enterprise"], key="new_mod_tier")

    if st.button("➕ Create Module", type="primary", disabled=not new_code or not new_name):
        module_data = {
            "code": new_code,
            "name": new_name,
            "category": new_category,
            "description": new_description,
            "status": new_status,
            "features": [f.strip() for f in new_features.split("\n") if f.strip()],
            "pricing_tier": new_tier,
        }
        result = create_module(module_data)
        if result:
            st.success(f"✅ Module '{new_name}' created!")
            st.json(result)
