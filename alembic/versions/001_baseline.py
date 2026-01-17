"""Baseline migration - consolidated initial schema and data.

Revision ID: 001_baseline
Revises: None
Create Date: 2026-01-15

This migration contains the complete database schema and seed data,
consolidated from 68 previous migrations. The SQL files are stored
in alembic/sql/ for better maintainability.

Schemas created:
- core: Multi-tenant shared tables
- ecommerce: Product catalog, orders
- healthcare: Medical records
- credit: Financial accounts
- soporte: Support tickets
- pharmacy: Pharmacy-specific config

Seed data includes:
- 2 organizations (system, test-pharmacy)
- Builtin agents configuration
- Domain intents and response configs
- Routing configurations
"""

from pathlib import Path
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Path to SQL files
SQL_DIR = Path(__file__).parent.parent / "sql"


def _execute_sql_file(filename: str) -> None:
    """Execute SQL from file, handling pg_dump specific syntax."""
    sql_path = SQL_DIR / filename
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_path}")

    content = sql_path.read_text(encoding="utf-8")

    # Split by semicolons but handle functions with $$ delimiters
    # pg_dump output has clean statement separation
    statements = []
    current_stmt = []
    in_function = False

    for line in content.split("\n"):
        # Skip pg_dump metadata lines
        if line.startswith("--") or line.startswith("\\") or not line.strip():
            continue

        # Skip SET statements that don't work in alembic context
        if line.strip().startswith("SET ") or line.strip().startswith("SELECT pg_catalog"):
            continue

        current_stmt.append(line)

        # Track function bodies
        if "$$" in line:
            in_function = not in_function

        # Statement complete when we hit ; and not in function
        if line.rstrip().endswith(";") and not in_function:
            stmt = "\n".join(current_stmt).strip()
            if stmt and not stmt.startswith("--"):
                statements.append(stmt)
            current_stmt = []

    # Execute each statement
    for stmt in statements:
        if stmt.strip():
            op.execute(stmt)


def upgrade() -> None:
    """Apply baseline schema and seed data."""
    # 1. Create required extensions (must be done first)
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Execute schema DDL (creates schemas, tables, indexes, triggers)
    _execute_sql_file("001_schema.sql")

    # 3. Execute seed data (inserts initial configuration)
    _execute_sql_file("001_seed_data.sql")


def downgrade() -> None:
    """
    Drop all managed schemas.

    WARNING: This is destructive and will delete all data!
    """
    schemas = ["pharmacy", "soporte", "credit", "healthcare", "ecommerce", "core"]
    for schema in schemas:
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
