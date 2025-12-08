"""
Excelencia - Modules and Demos Management

Interactive UI for:
- Managing ERP modules (CRUD)
- Managing demo requests
- Scheduling demos
"""

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from lib.api_client import (
    create_module,
    delete_module,
    get_demos,
    get_modules,
    schedule_demo,
    update_demo_status,
    update_module,
)
from lib.session_state import init_session_state

init_session_state()

st.title("🏢 Excelencia Management")
st.markdown("Manage ERP modules and demo requests.")

# Tabs
tab_modules, tab_demos = st.tabs(["🔧 Modules", "📅 Demos"])

# ============================================================================
# Tab: Modules
# ============================================================================

with tab_modules:
    st.subheader("🔧 ERP Modules")

    sub_tab_list, sub_tab_create = st.tabs(["📋 Module List", "➕ Create Module"])

    # Sub-tab: Module List
    with sub_tab_list:
        col_filter1, col_filter2, col_refresh = st.columns([2, 2, 1])
        with col_filter1:
            filter_category = st.selectbox(
                "Filter by Category",
                ["All", "finance", "inventory", "sales", "purchasing", "hr", "production", "crm", "reporting", "healthcare", "hospitality"],
            )
        with col_filter2:
            filter_status = st.selectbox("Filter by Status", ["All", "active", "beta", "coming_soon", "deprecated"])
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

                        categories = ["finance", "inventory", "sales", "purchasing", "hr", "production", "crm", "reporting", "healthcare", "hospitality"]
                        edit_category = st.selectbox(
                            "Category",
                            categories,
                            index=categories.index(mod.get("category", "finance")) if mod.get("category") in categories else 0,
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
        st.subheader("Create New Module")

        new_code = st.text_input("Code *", placeholder="e.g., FIN-001", help="Unique module code")
        new_name = st.text_input("Name *", placeholder="Module name")
        new_category = st.selectbox(
            "Category *",
            ["finance", "inventory", "sales", "purchasing", "hr", "production", "crm", "reporting", "healthcare", "hospitality"],
            key="new_mod_category",
        )
        new_description = st.text_area("Description", placeholder="Module description")
        new_status = st.selectbox("Status", ["active", "beta", "coming_soon", "deprecated"], key="new_mod_status")
        new_features = st.text_area("Features (one per line)", placeholder="Feature 1\nFeature 2\nFeature 3")
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

# ============================================================================
# Tab: Demos
# ============================================================================

with tab_demos:
    st.subheader("📅 Demo Management")
    st.markdown("View and manage demo requests.")

    status_icons = {
        "pending": "🟡",
        "scheduled": "🔵",
        "completed": "🟢",
        "cancelled": "🔴",
        "no_show": "⚫",
    }

    col_filter, col_company, col_refresh = st.columns([2, 2, 1])
    with col_filter:
        filter_demo_status = st.selectbox(
            "Filter by Status", ["All", "pending", "scheduled", "completed", "cancelled", "no_show"]
        )
    with col_company:
        filter_company = st.text_input("Filter by Company", placeholder="Company name...")
    with col_refresh:
        if st.button("🔄 Refresh", key="refresh_demos"):
            st.rerun()

    demos = get_demos(
        status=None if filter_demo_status == "All" else filter_demo_status,
        company=filter_company if filter_company else None,
    )

    if demos:
        for demo in demos:
            demo_id = demo.get("id")
            status = demo.get("status", "pending")
            icon = status_icons.get(status, "⚪")

            with st.expander(f"{icon} {demo.get('company_name', 'Unknown')} - {demo.get('contact_name', 'N/A')}"):
                col_info, col_details = st.columns(2)

                with col_info:
                    st.markdown("### Contact Information")
                    st.markdown(f"**Company:** {demo.get('company_name', 'N/A')}")
                    st.markdown(f"**Contact:** {demo.get('contact_name', 'N/A')}")
                    st.markdown(f"**Email:** {demo.get('contact_email', 'N/A')}")
                    st.markdown(f"**Phone:** {demo.get('contact_phone', 'N/A')}")

                with col_details:
                    st.markdown("### Demo Details")
                    st.markdown(f"**Type:** {demo.get('demo_type', 'general')}")
                    st.markdown(f"**Status:** {icon} {status}")
                    st.markdown(f"**Scheduled:** {demo.get('scheduled_at', 'Not scheduled')}")
                    st.markdown(f"**Duration:** {demo.get('duration_minutes', 60)} min")
                    st.markdown(f"**Assigned To:** {demo.get('assigned_to', 'Unassigned')}")

                modules = demo.get("modules_of_interest", [])
                if modules:
                    st.markdown(f"**Modules of Interest:** {', '.join(modules)}")

                notes = demo.get("notes") or demo.get("request_notes")
                if notes:
                    st.markdown(f"**Notes:** {notes}")

                meeting_link = demo.get("meeting_link")
                if meeting_link:
                    st.markdown(f"**Meeting Link:** [{meeting_link}]({meeting_link})")

                st.markdown("---")

                # Status Update
                st.markdown("### Update Status")
                col_status, col_notes = st.columns(2)

                with col_status:
                    new_status = st.selectbox(
                        "New Status",
                        ["pending", "scheduled", "completed", "cancelled", "no_show"],
                        index=["pending", "scheduled", "completed", "cancelled", "no_show"].index(status),
                        key=f"demo_status_{demo_id}",
                    )
                with col_notes:
                    status_notes = st.text_input("Notes", placeholder="Optional notes", key=f"demo_notes_{demo_id}")

                if st.button("📝 Update Status", key=f"update_status_{demo_id}"):
                    result = update_demo_status(demo_id, new_status, status_notes)
                    if result:
                        st.success("Status updated!")
                        st.rerun()

                # Schedule Demo
                if status == "pending":
                    st.markdown("### Schedule Demo")
                    col_date, col_time = st.columns(2)

                    with col_date:
                        sched_date = st.date_input("Date", key=f"sched_date_{demo_id}")
                    with col_time:
                        sched_time = st.time_input("Time", key=f"sched_time_{demo_id}")

                    col_assign, col_duration = st.columns(2)
                    with col_assign:
                        assigned = st.text_input("Assign To *", placeholder="Sales rep name", key=f"assign_{demo_id}")
                    with col_duration:
                        duration = st.number_input(
                            "Duration (min)", min_value=15, max_value=480, value=60, key=f"duration_{demo_id}"
                        )

                    meeting = st.text_input(
                        "Meeting Link", placeholder="https://meet.google.com/...", key=f"meeting_{demo_id}"
                    )

                    if st.button("📅 Schedule Demo", key=f"schedule_{demo_id}", type="primary", disabled=not assigned):
                        scheduled_dt = datetime.combine(sched_date, sched_time)
                        result = schedule_demo(
                            demo_id=demo_id,
                            scheduled_at=scheduled_dt,
                            assigned_to=assigned,
                            duration_minutes=duration,
                            meeting_link=meeting if meeting else None,
                        )
                        if result:
                            st.success("Demo scheduled!")
                            st.rerun()
    else:
        st.info("No demos found")
