"""create_soporte_schema_and_tables

Revision ID: t1n6o45p890o
Revises: s0m5n34o789n
Create Date: 2025-12-29

Creates the soporte (support/incidents) schema and all its tables:
- incident_categories: Dynamic categories with SLA and Jira mapping
- incidents: Main incidents/tickets table
- incident_comments: Comments on incidents
- incident_history: Change history (audit trail)
- jira_configs: Per-organization Jira configuration
- pending_tickets: Conversational flow state for ticket creation
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "t1n6o45p890o"
down_revision: Union[str, Sequence[str], None] = "36f513c8cce8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create soporte schema and all tables."""

    # 1. Create soporte schema
    op.execute("CREATE SCHEMA IF NOT EXISTS soporte")

    # 2. Create ENUMs in soporte schema
    # Incident type enum
    op.execute("""
        CREATE TYPE soporte.soporte_incident_type_enum AS ENUM (
            'incident', 'feedback', 'question', 'suggestion'
        )
    """)

    # Incident status enum
    op.execute("""
        CREATE TYPE soporte.soporte_incident_status_enum AS ENUM (
            'draft', 'open', 'in_progress', 'pending_info', 'resolved', 'closed'
        )
    """)

    # Incident priority enum
    op.execute("""
        CREATE TYPE soporte.soporte_incident_priority_enum AS ENUM (
            'low', 'medium', 'high', 'critical'
        )
    """)

    # Incident urgency enum
    op.execute("""
        CREATE TYPE soporte.soporte_incident_urgency_enum AS ENUM (
            'low', 'medium', 'high'
        )
    """)

    # Incident impact enum
    op.execute("""
        CREATE TYPE soporte.soporte_incident_impact_enum AS ENUM (
            'individual', 'group', 'department', 'organization'
        )
    """)

    # Incident source enum
    op.execute("""
        CREATE TYPE soporte.soporte_incident_source_enum AS ENUM (
            'whatsapp', 'email', 'phone', 'web'
        )
    """)

    # Jira sync status enum
    op.execute("""
        CREATE TYPE soporte.soporte_jira_sync_status_enum AS ENUM (
            'pending', 'synced', 'error', 'manual'
        )
    """)

    # Comment author type enum
    op.execute("""
        CREATE TYPE soporte.soporte_comment_author_type_enum AS ENUM (
            'user', 'agent', 'system'
        )
    """)

    # 3. Create incident_categories table (must be first due to FK from incidents)
    op.create_table(
        "incident_categories",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(50), nullable=False, unique=True,
                  comment="Unique category code (TECNICO, FACTURACION, etc.)"),
        sa.Column("name", sa.String(100), nullable=False,
                  comment="Display name for the category"),
        sa.Column("description", sa.Text(), nullable=True,
                  comment="Category description"),
        sa.Column("parent_id", sa.UUID(), nullable=True,
                  comment="Parent category for hierarchical structure"),
        sa.Column("sla_response_hours", sa.Integer(), nullable=True, server_default="24",
                  comment="SLA hours for initial response"),
        sa.Column("sla_resolution_hours", sa.Integer(), nullable=True, server_default="72",
                  comment="SLA hours for resolution"),
        sa.Column("jira_issue_type", sa.String(50), nullable=True, server_default=sa.text("'Bug'"),
                  comment="Mapped Jira issue type"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true",
                  comment="Whether category is active"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0",
                  comment="Display order in lists"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parent_id"], ["soporte.incident_categories.id"],
                                ondelete="SET NULL"),
        schema="soporte",
    )

    op.create_index("idx_incident_category_code", "incident_categories", ["code"],
                    schema="soporte")
    op.create_index("idx_incident_category_active", "incident_categories", ["is_active"],
                    schema="soporte")
    op.create_index("idx_incident_category_parent", "incident_categories", ["parent_id"],
                    schema="soporte")

    # 4. Create incidents table
    op.create_table(
        "incidents",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("folio", sa.String(20), nullable=False, unique=True,
                  comment="Human-readable folio (INC-2024-00001)"),
        sa.Column("organization_id", sa.UUID(), nullable=True,
                  comment="Organization for multi-tenant isolation"),
        sa.Column("user_phone", sa.String(50), nullable=False,
                  comment="WhatsApp phone number of the user"),
        sa.Column("user_name", sa.String(200), nullable=True,
                  comment="Name of the user (if known)"),
        sa.Column("conversation_id", sa.UUID(), nullable=True,
                  comment="Link to the conversation"),
        sa.Column("incident_type",
                  postgresql.ENUM("incident", "feedback", "question", "suggestion",
                                  name="soporte_incident_type_enum", schema="soporte",
                                  create_type=False),
                  nullable=False, server_default=sa.text("'incident'"),
                  comment="Type: incident, feedback, question, suggestion"),
        sa.Column("category_id", sa.UUID(), nullable=True,
                  comment="FK to incident category"),
        sa.Column("subject", sa.String(500), nullable=True,
                  comment="Brief subject/title"),
        sa.Column("description", sa.Text(), nullable=False,
                  comment="Full description of the incident"),
        sa.Column("priority",
                  postgresql.ENUM("low", "medium", "high", "critical",
                                  name="soporte_incident_priority_enum", schema="soporte",
                                  create_type=False),
                  nullable=False, server_default=sa.text("'medium'"),
                  comment="Priority: low, medium, high, critical"),
        sa.Column("urgency",
                  postgresql.ENUM("low", "medium", "high",
                                  name="soporte_incident_urgency_enum", schema="soporte",
                                  create_type=False),
                  nullable=True, server_default=sa.text("'medium'"),
                  comment="Urgency: low, medium, high"),
        sa.Column("impact",
                  postgresql.ENUM("individual", "group", "department", "organization",
                                  name="soporte_incident_impact_enum", schema="soporte",
                                  create_type=False),
                  nullable=True,
                  comment="Impact scope"),
        sa.Column("status",
                  postgresql.ENUM("draft", "open", "in_progress", "pending_info", "resolved", "closed",
                                  name="soporte_incident_status_enum", schema="soporte",
                                  create_type=False),
                  nullable=False, server_default=sa.text("'open'"),
                  comment="Status: draft, open, in_progress, pending_info, resolved, closed"),
        sa.Column("source",
                  postgresql.ENUM("whatsapp", "email", "phone", "web",
                                  name="soporte_incident_source_enum", schema="soporte",
                                  create_type=False),
                  nullable=False, server_default=sa.text("'whatsapp'"),
                  comment="Source channel"),
        sa.Column("environment", sa.String(100), nullable=True,
                  comment="Environment: produccion, pruebas, desarrollo"),
        sa.Column("steps_to_reproduce", sa.Text(), nullable=True),
        sa.Column("expected_behavior", sa.Text(), nullable=True),
        sa.Column("actual_behavior", sa.Text(), nullable=True),
        sa.Column("attachments", postgresql.JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb"),
                  comment="List of attachment URLs"),
        sa.Column("jira_issue_key", sa.String(50), nullable=True,
                  comment="Jira issue key (PROJ-123)"),
        sa.Column("jira_issue_id", sa.String(50), nullable=True),
        sa.Column("jira_project_key", sa.String(20), nullable=True),
        sa.Column("jira_sync_status",
                  postgresql.ENUM("pending", "synced", "error", "manual",
                                  name="soporte_jira_sync_status_enum", schema="soporte",
                                  create_type=False),
                  nullable=True, server_default=sa.text("'pending'")),
        sa.Column("jira_last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("jira_sync_error", sa.Text(), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("resolution_type", sa.String(100), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by", sa.String(200), nullable=True),
        sa.Column("sla_response_due", sa.DateTime(), nullable=True),
        sa.Column("sla_resolution_due", sa.DateTime(), nullable=True),
        sa.Column("sla_response_met", sa.Boolean(), nullable=True),
        sa.Column("sla_resolution_met", sa.Boolean(), nullable=True),
        sa.Column("meta_data", postgresql.JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["core.organizations.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["soporte.incident_categories.id"],
                                ondelete="SET NULL"),
        schema="soporte",
    )

    op.create_index("idx_incidents_folio", "incidents", ["folio"], schema="soporte")
    op.create_index("idx_incidents_status", "incidents", ["status"], schema="soporte")
    op.create_index("idx_incidents_user_phone", "incidents", ["user_phone"], schema="soporte")
    op.create_index("idx_incidents_organization_id", "incidents", ["organization_id"], schema="soporte")
    op.create_index("idx_incidents_jira_issue_key", "incidents", ["jira_issue_key"], schema="soporte")
    op.create_index("idx_incidents_created_at", "incidents", ["created_at"], schema="soporte")
    op.create_index("idx_incidents_priority", "incidents", ["priority"], schema="soporte")
    op.create_index("idx_incidents_category_id", "incidents", ["category_id"], schema="soporte")

    # 5. Create incident_comments table
    op.create_table(
        "incident_comments",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("incident_id", sa.UUID(), nullable=False,
                  comment="FK to incident"),
        sa.Column("author_type",
                  postgresql.ENUM("user", "agent", "system",
                                  name="soporte_comment_author_type_enum", schema="soporte",
                                  create_type=False),
                  nullable=False, server_default=sa.text("'user'"),
                  comment="Type of author: user, agent, system"),
        sa.Column("author_name", sa.String(200), nullable=True,
                  comment="Name of the author"),
        sa.Column("content", sa.Text(), nullable=False,
                  comment="Comment content"),
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default="false",
                  comment="Whether comment is internal-only"),
        sa.Column("jira_comment_id", sa.String(50), nullable=True,
                  comment="Jira comment ID for synchronization"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["incident_id"], ["soporte.incidents.id"],
                                ondelete="CASCADE"),
        schema="soporte",
    )

    op.create_index("idx_incident_comments_incident_id", "incident_comments", ["incident_id"],
                    schema="soporte")
    op.create_index("idx_incident_comments_author_type", "incident_comments", ["author_type"],
                    schema="soporte")
    op.create_index("idx_incident_comments_created_at", "incident_comments", ["created_at"],
                    schema="soporte")

    # 6. Create incident_history table
    op.create_table(
        "incident_history",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("incident_id", sa.UUID(), nullable=False,
                  comment="FK to incident"),
        sa.Column("field_changed", sa.String(100), nullable=False,
                  comment="Name of the field that changed"),
        sa.Column("old_value", sa.Text(), nullable=True,
                  comment="Previous value (as string)"),
        sa.Column("new_value", sa.Text(), nullable=True,
                  comment="New value (as string)"),
        sa.Column("changed_by", sa.String(200), nullable=True,
                  comment="Who made the change"),
        sa.Column("changed_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"),
                  comment="When the change was made"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["incident_id"], ["soporte.incidents.id"],
                                ondelete="CASCADE"),
        schema="soporte",
    )

    op.create_index("idx_incident_history_incident_id", "incident_history", ["incident_id"],
                    schema="soporte")
    op.create_index("idx_incident_history_changed_at", "incident_history", ["changed_at"],
                    schema="soporte")
    op.create_index("idx_incident_history_field", "incident_history", ["field_changed"],
                    schema="soporte")

    # 7. Create jira_configs table
    op.create_table(
        "jira_configs",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", sa.UUID(), nullable=True,
                  comment="Organization for multi-tenant (null for global)"),
        sa.Column("name", sa.String(100), nullable=False,
                  comment="Descriptive name for this configuration"),
        sa.Column("jira_base_url", sa.String(500), nullable=False,
                  comment="Jira instance base URL"),
        sa.Column("jira_project_key", sa.String(20), nullable=False,
                  comment="Default Jira project key"),
        sa.Column("jira_api_token_encrypted", sa.Text(), nullable=True,
                  comment="Encrypted Jira API token"),
        sa.Column("jira_email", sa.String(200), nullable=False,
                  comment="Email for Jira API authentication"),
        sa.Column("webhook_secret", sa.String(200), nullable=True,
                  comment="Secret for verifying Jira webhooks"),
        sa.Column("category_mapping", postgresql.JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb"),
                  comment="Mapping: category_code -> Jira issue type"),
        sa.Column("module_mapping", postgresql.JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb"),
                  comment="Mapping: module_code -> Jira component"),
        sa.Column("priority_mapping", postgresql.JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb"),
                  comment="Mapping: priority -> Jira priority"),
        sa.Column("custom_fields", postgresql.JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb"),
                  comment="Mapping: field_name -> Jira custom field ID"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true",
                  comment="Whether this configuration is active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["core.organizations.id"],
                                ondelete="CASCADE"),
        schema="soporte",
    )

    op.create_index("idx_jira_configs_organization_id", "jira_configs", ["organization_id"],
                    schema="soporte")
    op.create_index("idx_jira_configs_active", "jira_configs", ["is_active"],
                    schema="soporte")
    op.create_index("idx_jira_configs_project_key", "jira_configs", ["jira_project_key"],
                    schema="soporte")

    # 8. Create pending_tickets table
    op.create_table(
        "pending_tickets",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("conversation_id", sa.String(255), nullable=False,
                  comment="WhatsApp conversation ID"),
        sa.Column("user_phone", sa.String(50), nullable=False,
                  comment="User's phone number"),
        sa.Column("current_step", sa.String(50), nullable=False, server_default=sa.text("'description'"),
                  comment="Current step: description, priority, confirmation"),
        sa.Column("collected_data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb"),
                  comment="Data collected so far"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()"),
                  comment="When the ticket creation flow started"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW() + INTERVAL '30 minutes'"),
                  comment="When this pending ticket expires (30 min default)"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true",
                  comment="Whether this pending ticket is still active"),
        sa.PrimaryKeyConstraint("id"),
        schema="soporte",
    )

    op.create_index("idx_pending_tickets_conversation_id", "pending_tickets", ["conversation_id"],
                    schema="soporte")
    op.create_index("idx_pending_tickets_user_phone", "pending_tickets", ["user_phone"],
                    schema="soporte")
    op.create_index("idx_pending_tickets_active", "pending_tickets", ["is_active"],
                    schema="soporte")
    op.create_index("idx_pending_tickets_expires", "pending_tickets", ["expires_at"],
                    schema="soporte")

    # 9. Seed default incident categories
    op.execute("""
        INSERT INTO soporte.incident_categories (code, name, description, jira_issue_type, sla_response_hours, sla_resolution_hours, sort_order)
        VALUES
            ('TECNICO', 'Problema Técnico', 'Problemas técnicos con el software', 'Bug', 4, 24, 1),
            ('FACTURACION', 'Facturación', 'Consultas sobre facturación y pagos', 'Task', 8, 48, 2),
            ('CAPACITACION', 'Capacitación', 'Solicitudes de capacitación', 'Story', 24, 72, 3),
            ('INVENTARIO', 'Inventario', 'Problemas con módulo de inventario', 'Bug', 4, 24, 4),
            ('NOMINA', 'Nómina', 'Problemas con módulo de nómina', 'Task', 8, 48, 5),
            ('CONTABILIDAD', 'Contabilidad', 'Problemas con módulo contable', 'Task', 8, 48, 6),
            ('GENERAL', 'General', 'Consultas generales', 'Task', 24, 72, 99)
        ON CONFLICT (code) DO NOTHING
    """)


def downgrade() -> None:
    """Drop soporte schema and all tables."""

    # Drop tables in reverse order (respect FK constraints)
    op.drop_table("pending_tickets", schema="soporte")
    op.drop_table("jira_configs", schema="soporte")
    op.drop_table("incident_history", schema="soporte")
    op.drop_table("incident_comments", schema="soporte")
    op.drop_table("incidents", schema="soporte")
    op.drop_table("incident_categories", schema="soporte")

    # Drop ENUMs
    op.execute("DROP TYPE IF EXISTS soporte.soporte_comment_author_type_enum")
    op.execute("DROP TYPE IF EXISTS soporte.soporte_jira_sync_status_enum")
    op.execute("DROP TYPE IF EXISTS soporte.soporte_incident_source_enum")
    op.execute("DROP TYPE IF EXISTS soporte.soporte_incident_impact_enum")
    op.execute("DROP TYPE IF EXISTS soporte.soporte_incident_urgency_enum")
    op.execute("DROP TYPE IF EXISTS soporte.soporte_incident_priority_enum")
    op.execute("DROP TYPE IF EXISTS soporte.soporte_incident_status_enum")
    op.execute("DROP TYPE IF EXISTS soporte.soporte_incident_type_enum")

    # Note: We keep the schema as it may be used by other migrations
    # op.execute("DROP SCHEMA IF EXISTS soporte CASCADE")
