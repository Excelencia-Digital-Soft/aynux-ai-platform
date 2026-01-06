"""add_qwen3b_internal_model

Revision ID: c9l5n67o890p
Revises: b9j4k56m789n
Create Date: 2026-01-06

Adds the internal qwen-3b model (Qwen/Qwen2.5-3B-Instruct-AWQ) served via vLLM.
This is the primary system model - enabled by default with is_default=True.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9l5n67o890p"
down_revision: Union[str, Sequence[str], None] = "b9j4k56m789n"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add qwen-3b internal model to ai_models table."""
    conn = op.get_bind()

    conn.execute(
        sa.text("""
            INSERT INTO core.ai_models (
                model_id, provider, model_type, display_name, description,
                family, parameter_size, quantization_level, context_window,
                max_output_tokens, supports_streaming, supports_functions,
                supports_vision, is_enabled, is_default, sort_order, sync_source
            ) VALUES (
                'qwen-3b', 'vllm', 'llm', 'Qwen 2.5 3B',
                'Internal vLLM model - Qwen2.5-3B-Instruct-AWQ for general tasks',
                'qwen', '3B', 'AWQ', 32768, 4096, true, true, false,
                true, true, 1, 'migration'
            )
            ON CONFLICT (model_id) DO UPDATE SET
                is_enabled = true,
                is_default = true,
                sort_order = 1
        """)
    )


def downgrade() -> None:
    """Remove qwen-3b model."""
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM core.ai_models WHERE model_id = 'qwen-3b'"))
