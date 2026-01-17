"""Add workflow schema for configurable workflows.

Revision ID: 002_workflow_schema
Revises: 001_baseline
Create Date: 2026-01-16

This migration creates the workflow schema with tables for:
- node_definitions: Registry of available node types
- workflow_definitions: Workflow configurations per institution
- node_instances: Configured nodes within workflows
- workflow_transitions: Transitions between nodes
- routing_rules: Configurable routing rules (human handoff, etc.)
- reminder_schedules: Reminder timing configuration
- message_templates: Configurable message templates

Schema: workflow
"""

from pathlib import Path
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_workflow_schema"
down_revision: Union[str, Sequence[str], None] = "001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Path to SQL files
SQL_DIR = Path(__file__).parent.parent / "sql"


def _execute_sql_file(filename: str) -> None:
    """Execute SQL from file."""
    sql_path = SQL_DIR / filename
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_path}")

    content = sql_path.read_text(encoding="utf-8")

    # Split by semicolons but handle functions with $$ delimiters
    statements = []
    current_stmt = []
    in_function = False

    for line in content.split("\n"):
        # Skip comments and empty lines
        if line.startswith("--") or not line.strip():
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
    """Create workflow schema and tables."""
    _execute_sql_file("002_workflow_schema.sql")
    _execute_sql_file("002_workflow_seed_data.sql")


def downgrade() -> None:
    """Drop workflow schema."""
    op.execute("DROP SCHEMA IF EXISTS workflow CASCADE")
