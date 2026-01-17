"""create_ai_models_table

Revision ID: q8k3m12n567l
Revises: p7j2l01m456k
Create Date: 2025-12-28

Creates ai_models table for dynamic AI model management:
- Supports Ollama (local) and external providers (OpenAI, Anthropic, DeepSeek)
- Tracks model capabilities, provider, and metadata
- Enables admin control over which models are available to users
- Seeds initial external models (disabled by default)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "q8k3m12n567l"
down_revision: Union[str, Sequence[str], None] = "p7j2l01m456k"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create ai_models table and seed external models."""

    # ==========================================================================
    # 1. Clean up any leftover types from failed migrations
    # ==========================================================================
    op.execute("DROP TYPE IF EXISTS core.model_type CASCADE")
    op.execute("DROP TYPE IF EXISTS core.model_provider CASCADE")
    op.execute("DROP TABLE IF EXISTS core.ai_models CASCADE")

    # ==========================================================================
    # 2. Create ai_models table
    # ==========================================================================
    op.create_table(
        "ai_models",
        # Primary key
        sa.Column(
            "id",
            UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique model identifier",
        ),
        # Model identification
        sa.Column(
            "model_id",
            sa.String(255),
            nullable=False,
            comment="Provider-specific model ID (e.g., 'gpt-4', 'llama3.2:3b')",
        ),
        sa.Column(
            "provider",
            sa.String(50),
            nullable=False,
            comment="Model provider: ollama, openai, anthropic, deepseek",
        ),
        sa.Column(
            "model_type",
            sa.String(20),
            nullable=False,
            server_default="llm",
            comment="Model type: llm or embedding",
        ),
        # Display information
        sa.Column(
            "display_name",
            sa.String(255),
            nullable=False,
            comment="Human-readable name for UI display",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Model description",
        ),
        # Model specifications
        sa.Column(
            "family",
            sa.String(100),
            nullable=True,
            comment="Model family (e.g., 'llama', 'gpt', 'claude')",
        ),
        sa.Column(
            "parameter_size",
            sa.String(50),
            nullable=True,
            comment="Model size (e.g., '8B', '70B')",
        ),
        sa.Column(
            "quantization_level",
            sa.String(50),
            nullable=True,
            comment="Quantization level (e.g., 'Q4_K_M', 'F16')",
        ),
        sa.Column(
            "context_window",
            sa.Integer(),
            nullable=True,
            comment="Maximum context window in tokens",
        ),
        sa.Column(
            "max_output_tokens",
            sa.Integer(),
            nullable=True,
            server_default=sa.text("4096"),
            comment="Maximum output tokens",
        ),
        # Capabilities
        sa.Column(
            "supports_streaming",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether model supports streaming responses",
        ),
        sa.Column(
            "supports_functions",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether model supports function/tool calling",
        ),
        sa.Column(
            "supports_vision",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether model supports image input",
        ),
        # Status and ordering
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether model is enabled for user selection",
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether this is a default model",
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("100"),
            comment="Display order in UI (lower = first)",
        ),
        # Flexible capabilities
        sa.Column(
            "capabilities",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Additional capabilities and metadata",
        ),
        # Sync tracking
        sa.Column(
            "sync_source",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'manual'"),
            comment="How model was added: manual, ollama_sync, seed",
        ),
        sa.Column(
            "last_synced_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last sync from provider",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_id", name="uq_ai_models_model_id"),
        schema="core",
    )

    # ==========================================================================
    # 3. Create indexes
    # ==========================================================================
    op.create_index(
        "idx_ai_models_model_id",
        "ai_models",
        ["model_id"],
        schema="core",
    )
    op.create_index(
        "idx_ai_models_provider",
        "ai_models",
        ["provider"],
        schema="core",
    )
    op.create_index(
        "idx_ai_models_type",
        "ai_models",
        ["model_type"],
        schema="core",
    )
    op.create_index(
        "idx_ai_models_enabled",
        "ai_models",
        ["is_enabled"],
        schema="core",
    )
    op.create_index(
        "idx_ai_models_sort",
        "ai_models",
        ["sort_order"],
        schema="core",
    )
    op.create_index(
        "idx_ai_models_enabled_type",
        "ai_models",
        ["is_enabled", "model_type"],
        schema="core",
    )

    # ==========================================================================
    # 4. Seed external models (disabled by default)
    # ==========================================================================
    conn = op.get_bind()

    external_models = [
        # OpenAI
        {
            "model_id": "gpt-4o",
            "provider": "openai",
            "display_name": "GPT-4o",
            "description": "OpenAI's most capable model for complex tasks",
            "family": "gpt",
            "context_window": 128000,
            "max_output_tokens": 4096,
            "supports_functions": True,
            "supports_vision": True,
            "sort_order": 10,
        },
        {
            "model_id": "gpt-4o-mini",
            "provider": "openai",
            "display_name": "GPT-4o Mini",
            "description": "Fast and cost-effective for simpler tasks",
            "family": "gpt",
            "context_window": 128000,
            "max_output_tokens": 16384,
            "supports_functions": True,
            "supports_vision": True,
            "sort_order": 20,
        },
        {
            "model_id": "gpt-4-turbo",
            "provider": "openai",
            "display_name": "GPT-4 Turbo",
            "description": "Previous generation high-capability model",
            "family": "gpt",
            "context_window": 128000,
            "max_output_tokens": 4096,
            "supports_functions": True,
            "supports_vision": True,
            "sort_order": 25,
        },
        # Anthropic
        {
            "model_id": "claude-sonnet-4-20250514",
            "provider": "anthropic",
            "display_name": "Claude Sonnet 4",
            "description": "Anthropic's balanced model for most tasks",
            "family": "claude",
            "context_window": 200000,
            "max_output_tokens": 8192,
            "supports_functions": True,
            "supports_vision": True,
            "sort_order": 30,
        },
        {
            "model_id": "claude-3-5-haiku-20241022",
            "provider": "anthropic",
            "display_name": "Claude 3.5 Haiku",
            "description": "Fast and efficient for quick tasks",
            "family": "claude",
            "context_window": 200000,
            "max_output_tokens": 8192,
            "supports_functions": True,
            "supports_vision": True,
            "sort_order": 40,
        },
        {
            "model_id": "claude-opus-4-20250514",
            "provider": "anthropic",
            "display_name": "Claude Opus 4",
            "description": "Anthropic's most powerful model for complex reasoning",
            "family": "claude",
            "context_window": 200000,
            "max_output_tokens": 8192,
            "supports_functions": True,
            "supports_vision": True,
            "sort_order": 35,
        },
        # DeepSeek
        {
            "model_id": "deepseek-chat",
            "provider": "deepseek",
            "display_name": "DeepSeek Chat",
            "description": "Cost-effective model for general tasks",
            "family": "deepseek",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "supports_functions": True,
            "supports_vision": False,
            "sort_order": 50,
        },
        {
            "model_id": "deepseek-reasoner",
            "provider": "deepseek",
            "display_name": "DeepSeek Reasoner",
            "description": "Optimized for complex multi-step reasoning",
            "family": "deepseek",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "supports_functions": False,
            "supports_vision": False,
            "sort_order": 55,
        },
    ]

    for model in external_models:
        conn.execute(
            sa.text("""
                INSERT INTO core.ai_models (
                    model_id, provider, model_type, display_name, description,
                    family, context_window, max_output_tokens,
                    supports_functions, supports_vision, sort_order,
                    is_enabled, sync_source
                ) VALUES (
                    :model_id, :provider, 'llm',
                    :display_name, :description, :family, :context_window,
                    :max_output_tokens, :supports_functions, :supports_vision,
                    :sort_order, false, 'seed'
                )
                ON CONFLICT (model_id) DO NOTHING
            """),
            model,
        )

    # Add table comment
    op.execute("""
        COMMENT ON TABLE core.ai_models IS
        'Registry of available AI models from various providers. Admin controls visibility via is_enabled.'
    """)


def downgrade() -> None:
    """Remove ai_models table."""

    # Drop indexes
    op.drop_index("idx_ai_models_enabled_type", table_name="ai_models", schema="core")
    op.drop_index("idx_ai_models_sort", table_name="ai_models", schema="core")
    op.drop_index("idx_ai_models_enabled", table_name="ai_models", schema="core")
    op.drop_index("idx_ai_models_type", table_name="ai_models", schema="core")
    op.drop_index("idx_ai_models_provider", table_name="ai_models", schema="core")
    op.drop_index("idx_ai_models_model_id", table_name="ai_models", schema="core")

    # Drop table
    op.drop_table("ai_models", schema="core")
