"""Add ZisMed module to software_modules.

Revision ID: v3d8e90f123g
Revises: u2b6c78d901e
Create Date: 2024-12-29 23:00:00.000000

ZisMed is the commercial name for the integrated medical suite that combines:
- Historia Clínica Electrónica (HC-001)
- Sistema de Turnos Médicos (TM-001)

This fixes the issue where asking about ZisMed returned GR-001 (Gremios) info.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "v3d8e90f123g"
down_revision: str | None = "u2b6c78d901e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXCELENCIA_SCHEMA = "excelencia"


def upgrade() -> None:
    """Add ZisMed as integrated medical suite module."""
    op.execute(
        f"""
        INSERT INTO {EXCELENCIA_SCHEMA}.software_modules
            (id, code, name, description, category, status, features, active)
        VALUES (
            gen_random_uuid(),
            'ZM-001',
            'ZisMed - Sistema Médico Integral',
            'Sistema médico integral ZisMed. Suite completa que incluye Historia Clínica Electrónica y Sistema de Turnos Médicos para clínicas, hospitales y centros de salud. Permite gestión unificada de pacientes, consultas médicas, turnos, prescripciones y reportes estadísticos de manera segura y eficiente.',
            'healthcare',
            'active',
            ARRAY[
                'Historia Clínica Electrónica',
                'Sistema de Turnos Médicos',
                'Registro de Pacientes',
                'Consultas Médicas',
                'Agenda Médica Integrada',
                'Prescripciones Digitales',
                'Recordatorios SMS/Email',
                'Portal Web Pacientes',
                'Reportes Estadísticos',
                'Gestión Multi-profesional'
            ],
            true
        )
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    """Remove ZisMed module."""
    op.execute(
        f"""
        DELETE FROM {EXCELENCIA_SCHEMA}.software_modules
        WHERE code = 'ZM-001'
        """
    )
