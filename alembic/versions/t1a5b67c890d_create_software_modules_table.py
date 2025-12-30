"""Create software_modules table for Excelencia domain.

Revision ID: t1a5b67c890d
Revises: s0m5n34o789n
Create Date: 2024-12-29 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "t1a5b67c890d"
down_revision: str | None = "t1n6o45p890o"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXCELENCIA_SCHEMA = "excelencia"


def upgrade() -> None:
    # Create excelencia schema if not exists
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {EXCELENCIA_SCHEMA}")

    # Create software_modules table
    op.create_table(
        "software_modules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False, server_default="general"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("features", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("pricing_tier", sa.String(length=50), nullable=True, server_default="standard"),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("embedding_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("knowledge_doc_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("knowledge_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default="{}"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        schema=EXCELENCIA_SCHEMA,
    )

    # Create indexes
    op.create_index(
        "idx_software_modules_code",
        "software_modules",
        ["code"],
        schema=EXCELENCIA_SCHEMA,
    )
    op.create_index(
        "idx_software_modules_name",
        "software_modules",
        ["name"],
        schema=EXCELENCIA_SCHEMA,
    )
    op.create_index(
        "idx_software_modules_category_status",
        "software_modules",
        ["category", "status"],
        schema=EXCELENCIA_SCHEMA,
    )
    op.create_index(
        "idx_software_modules_active",
        "software_modules",
        ["active"],
        schema=EXCELENCIA_SCHEMA,
    )
    op.create_index(
        "idx_software_modules_org",
        "software_modules",
        ["organization_id"],
        schema=EXCELENCIA_SCHEMA,
    )

    # Create HNSW index for vector similarity search
    op.execute(
        f"""
        CREATE INDEX idx_software_modules_embedding_hnsw
        ON {EXCELENCIA_SCHEMA}.software_modules
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # Seed initial modules (migrate from _FALLBACK_MODULES)
    op.execute(
        f"""
        INSERT INTO {EXCELENCIA_SCHEMA}.software_modules (id, code, name, description, category, status, features, active)
        VALUES
            (gen_random_uuid(), 'HC-001', 'Historia Clínica Electrónica',
             'Sistema de gestión de historias clínicas digitales para instituciones de salud. Permite el registro completo de pacientes, consultas médicas y prescripciones de manera segura y eficiente.',
             'healthcare', 'active',
             ARRAY['Registro de pacientes', 'Consultas médicas', 'Prescripciones', 'Agenda médica', 'Reportes estadísticos'],
             true),
            (gen_random_uuid(), 'TM-001', 'Sistema de Turnos Médicos',
             'Gestión integral de agendas y turnos de pacientes. Incluye turnos online, recordatorios automáticos y gestión de múltiples profesionales.',
             'healthcare', 'active',
             ARRAY['Agenda médica', 'Turnos online', 'Recordatorios SMS/Email', 'Múltiples profesionales', 'Reportes de ocupación'],
             true),
            (gen_random_uuid(), 'HO-001', 'Gestión Hotelera',
             'Software completo para administración de hoteles. Maneja reservas, check-in/out, facturación y gestión de habitaciones.',
             'hospitality', 'active',
             ARRAY['Reservas online', 'Check-in/Check-out', 'Facturación electrónica', 'Gestión de habitaciones', 'Reportes de ocupación'],
             true),
            (gen_random_uuid(), 'FN-001', 'Sistema Financiero',
             'Solución integral para la gestión financiera empresarial. Incluye contabilidad, tesorería, presupuestos y análisis financiero.',
             'finance', 'active',
             ARRAY['Contabilidad general', 'Tesorería', 'Presupuestos', 'Análisis financiero', 'Reportes AFIP'],
             true),
            (gen_random_uuid(), 'GR-001', 'Gestión de Gremios',
             'Sistema especializado para la administración de sindicatos y gremios. Gestión de afiliados, cuotas y servicios.',
             'guilds', 'active',
             ARRAY['Padrón de afiliados', 'Gestión de cuotas', 'Servicios a afiliados', 'Convenios', 'Portal web'],
             true)
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    # Drop indexes first
    op.execute(f"DROP INDEX IF EXISTS {EXCELENCIA_SCHEMA}.idx_software_modules_embedding_hnsw")
    op.drop_index("idx_software_modules_org", table_name="software_modules", schema=EXCELENCIA_SCHEMA)
    op.drop_index("idx_software_modules_active", table_name="software_modules", schema=EXCELENCIA_SCHEMA)
    op.drop_index("idx_software_modules_category_status", table_name="software_modules", schema=EXCELENCIA_SCHEMA)
    op.drop_index("idx_software_modules_name", table_name="software_modules", schema=EXCELENCIA_SCHEMA)
    op.drop_index("idx_software_modules_code", table_name="software_modules", schema=EXCELENCIA_SCHEMA)

    # Drop table
    op.drop_table("software_modules", schema=EXCELENCIA_SCHEMA)

    # Note: We don't drop the schema as it might contain other tables
