"""create_agents_table

Revision ID: x5f0g12h345i
Revises: w4e9f01g234h
Create Date: 2025-12-31

Creates agents table for global agent registry:
- Stores agent catalog with configuration defaults
- Seeds from BUILTIN_AGENT_DEFAULTS
- Enables admin control over which agents are available
- Replaces ENABLED_AGENTS environment variable
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "x5f0g12h345i"
down_revision: Union[str, Sequence[str], None] = "w4e9f01g234h"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create agents table and seed builtin agents."""

    # ==========================================================================
    # 1. Clean up any leftover artifacts from failed migrations
    # ==========================================================================
    op.execute("DROP TABLE IF EXISTS core.agents CASCADE")

    # ==========================================================================
    # 2. Create agents table
    # ==========================================================================
    op.create_table(
        "agents",
        # Primary key
        sa.Column(
            "id",
            UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique agent identifier",
        ),
        # Agent identification
        sa.Column(
            "agent_key",
            sa.String(100),
            nullable=False,
            comment="Unique agent key (e.g., 'greeting_agent', 'support_agent')",
        ),
        # Display information
        sa.Column(
            "name",
            sa.String(255),
            nullable=False,
            comment="Human-readable name for UI display",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Agent description and purpose",
        ),
        # Classification
        sa.Column(
            "agent_type",
            sa.String(50),
            nullable=False,
            server_default="builtin",
            comment="Agent type: builtin, specialized, supervisor, orchestrator, custom",
        ),
        # Domain association
        sa.Column(
            "domain_key",
            sa.String(50),
            nullable=True,
            comment="Associated domain: None (global), excelencia, ecommerce, pharmacy, credit",
        ),
        # Status and ordering
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether agent is enabled globally",
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("50"),
            comment="Routing priority (100 = highest, 0 = lowest)",
        ),
        # Intent matching
        sa.Column(
            "keywords",
            ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
            comment="Keywords for intent matching",
        ),
        sa.Column(
            "intent_patterns",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Intent patterns with weights: [{pattern: str, weight: float}]",
        ),
        # Flexible configuration
        sa.Column(
            "config",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Agent-specific configuration",
        ),
        # Sync tracking
        sa.Column(
            "sync_source",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'seed'"),
            comment="How agent was added: seed, manual",
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
        sa.UniqueConstraint("agent_key", name="uq_agents_agent_key"),
        schema="core",
    )

    # ==========================================================================
    # 3. Create indexes
    # ==========================================================================
    op.create_index(
        "idx_agents_agent_key",
        "agents",
        ["agent_key"],
        schema="core",
    )
    op.create_index(
        "idx_agents_agent_type",
        "agents",
        ["agent_type"],
        schema="core",
    )
    op.create_index(
        "idx_agents_domain_key",
        "agents",
        ["domain_key"],
        schema="core",
    )
    op.create_index(
        "idx_agents_enabled",
        "agents",
        ["enabled"],
        schema="core",
    )
    op.create_index(
        "idx_agents_priority",
        "agents",
        ["priority"],
        schema="core",
    )
    op.create_index(
        "idx_agents_enabled_priority",
        "agents",
        ["enabled", "priority"],
        schema="core",
        postgresql_ops={"priority": "DESC"},
    )

    # ==========================================================================
    # 4. Seed builtin agents from BUILTIN_AGENT_DEFAULTS
    # ==========================================================================
    conn = op.get_bind()

    # Define all builtin agents (from app/core/agents/builtin_agents.py)
    builtin_agents = [
        {
            "agent_key": "greeting_agent",
            "name": "Greeting Agent",
            "description": "Handles greetings and provides system capabilities overview",
            "agent_type": "builtin",
            "domain_key": None,
            "enabled": True,
            "priority": 100,
            "keywords": ["hola", "hello", "hi", "buenos dias", "buenas tardes", "buenas noches",
                        "good morning", "good afternoon", "good evening", "hey", "que tal"],
            "intent_patterns": [{"pattern": "saludo", "weight": 1.0}],
            "config": {"response_style": "friendly", "show_capabilities": True, "max_greeting_length": 200},
        },
        {
            "agent_key": "farewell_agent",
            "name": "Farewell Agent",
            "description": "Manages conversation closure and farewells",
            "agent_type": "builtin",
            "domain_key": None,
            "enabled": True,
            "priority": 90,
            "keywords": ["adios", "chau", "hasta luego", "gracias", "bye", "goodbye", "thanks"],
            "intent_patterns": [{"pattern": "despedida", "weight": 1.0}],
            "config": {"show_survey_link": False, "save_conversation": True},
        },
        {
            "agent_key": "support_agent",
            "name": "Support Agent",
            "description": "Provides technical support and troubleshooting assistance",
            "agent_type": "builtin",
            "domain_key": None,
            "enabled": True,
            "priority": 65,
            "keywords": ["ayuda", "problema", "error", "falla", "soporte", "tecnico", "reclamo", "queja"],
            "intent_patterns": [{"pattern": "soporte", "weight": 1.0}],
            "config": {"enable_ticket_creation": True, "escalation_threshold": 2, "requires_handoff": True},
        },
        {
            "agent_key": "fallback_agent",
            "name": "Fallback Agent",
            "description": "Handles general inquiries and provides fallback responses",
            "agent_type": "builtin",
            "domain_key": None,
            "enabled": True,
            "priority": 10,
            "keywords": [],
            "intent_patterns": [{"pattern": "fallback", "weight": 1.0}],
            "config": {"suggest_alternatives": True, "max_fallback_count": 3, "escalate_after_fallbacks": True},
        },
        {
            "agent_key": "excelencia_agent",
            "name": "Excelencia Software Agent",
            "description": "Handles queries about Excelencia Software: demos, modules, training, verticals",
            "agent_type": "builtin",
            "domain_key": "excelencia",
            "enabled": True,
            "priority": 70,
            "keywords": ["excelencia", "erp", "historia clinica", "turnos", "hotel", "obra social",
                        "modulo", "demo", "capacitacion", "mision", "vision"],
            "intent_patterns": [{"pattern": "excelencia", "weight": 1.0}],
            "config": {"enable_rag": True, "show_demo_links": True,
                      "vertical_products": ["healthcare", "hotels", "social_security"]},
        },
        {
            "agent_key": "excelencia_invoice_agent",
            "name": "Excelencia Invoice Agent",
            "description": "Handles client invoicing, account statements, and collections for Excelencia",
            "agent_type": "builtin",
            "domain_key": "excelencia",
            "enabled": True,
            "priority": 72,
            "keywords": ["factura cliente", "estado de cuenta", "cobranza", "deuda cliente",
                        "cobrar", "pago cliente", "saldo pendiente", "cuenta por cobrar"],
            "intent_patterns": [{"pattern": "excelencia_facturacion", "weight": 1.0}],
            "config": {"enable_rag": True, "require_client_id": False, "can_generate_statement": True},
        },
        {
            "agent_key": "excelencia_promotions_agent",
            "name": "Excelencia Promotions Agent",
            "description": "Handles software promotions, module discounts, and implementation offers",
            "agent_type": "builtin",
            "domain_key": "excelencia",
            "enabled": True,
            "priority": 71,
            "keywords": ["promocion software", "descuento modulo", "oferta implementacion",
                        "descuento capacitacion", "promocion excelencia", "oferta software"],
            "intent_patterns": [{"pattern": "excelencia_promociones", "weight": 1.0}],
            "config": {"enable_rag": True, "show_active_only": True, "max_promotions": 5},
        },
        {
            "agent_key": "excelencia_support_agent",
            "name": "Excelencia Support Agent",
            "description": "Handles Excelencia software technical support and troubleshooting",
            "agent_type": "builtin",
            "domain_key": "excelencia",
            "enabled": True,
            "priority": 68,
            "keywords": ["soporte excelencia", "problema software", "error modulo", "falla sistema",
                        "no funciona", "bug", "actualizacion"],
            "intent_patterns": [{"pattern": "excelencia_soporte", "weight": 1.0}],
            "config": {"enable_rag": True, "create_ticket": True, "escalation_enabled": True},
        },
        {
            "agent_key": "data_insights_agent",
            "name": "Data Insights Agent",
            "description": "Provides analytics, reports, and data insights for Excelencia domain",
            "agent_type": "builtin",
            "domain_key": "excelencia",
            "enabled": True,
            "priority": 60,
            "keywords": ["estadistica", "reporte", "analisis", "datos", "ventas", "metricas", "dashboard"],
            "intent_patterns": [{"pattern": "datos", "weight": 1.0}],
            "config": {"allow_export": False, "max_date_range_days": 30},
        },
        {
            "agent_key": "ecommerce_agent",
            "name": "E-commerce Agent",
            "description": "Handles all e-commerce queries: products, promotions, tracking, billing",
            "agent_type": "builtin",
            "domain_key": "ecommerce",
            "enabled": False,  # Disabled by default
            "priority": 80,
            "keywords": ["producto", "precio", "compra", "pedido", "orden", "factura", "promocion",
                        "descuento", "oferta", "seguimiento", "envio", "entrega", "stock", "disponible", "catalogo"],
            "intent_patterns": [{"pattern": "producto", "weight": 1.0}, {"pattern": "promociones", "weight": 0.9},
                               {"pattern": "seguimiento", "weight": 0.9}, {"pattern": "facturacion", "weight": 0.9},
                               {"pattern": "ecommerce", "weight": 1.0}],
            "config": {"enable_search": True, "max_results": 5, "enable_promotions": True,
                      "enable_tracking": True, "enable_billing": True},
        },
        {
            "agent_key": "credit_agent",
            "name": "Credit Agent",
            "description": "Handles credit-related queries: accounts, payments, collections",
            "agent_type": "builtin",
            "domain_key": "credit",
            "enabled": False,  # Disabled by default
            "priority": 75,
            "keywords": ["credito", "cuenta", "deuda", "pago", "cuota", "mora", "cobranza"],
            "intent_patterns": [{"pattern": "credito", "weight": 1.0}],
            "config": {"require_account_verification": True, "show_payment_options": True},
        },
        {
            "agent_key": "pharmacy_operations_agent",
            "name": "Pharmacy Operations Agent",
            "description": "Handles pharmacy debt queries, confirmations, and invoice generation",
            "agent_type": "builtin",
            "domain_key": "pharmacy",
            "enabled": True,
            "priority": 75,
            "keywords": ["deuda", "farmacia", "saldo", "factura", "confirmar", "cuenta", "pendiente", "debo"],
            "intent_patterns": [{"pattern": "pharmacy", "weight": 1.0}],
            "config": {"enable_bypass": True, "require_confirmation": True, "max_workflow_steps": 3},
        },
        # Legacy agents (disabled by default, deprecated)
        {
            "agent_key": "product_agent",
            "name": "Product Agent (Legacy)",
            "description": "[DEPRECATED] Use ecommerce_agent. Handles product inquiries.",
            "agent_type": "builtin",
            "domain_key": "ecommerce",
            "enabled": False,
            "priority": 70,
            "keywords": ["producto", "precio", "stock", "disponible", "catalogo", "buscar"],
            "intent_patterns": [{"pattern": "producto", "weight": 0.8}],
            "config": {"enable_search": True, "max_results": 5, "deprecated": True},
        },
        {
            "agent_key": "promotions_agent",
            "name": "Promotions Agent (Legacy)",
            "description": "[DEPRECATED] Use ecommerce_agent. Internal node for promotions.",
            "agent_type": "builtin",
            "domain_key": "ecommerce",
            "enabled": False,
            "priority": 70,
            "keywords": ["promocion", "descuento", "oferta", "cupon", "rebaja", "sale"],
            "intent_patterns": [{"pattern": "promociones", "weight": 0.8}],
            "config": {"show_active_only": True, "max_promotions": 3, "deprecated": True},
        },
        {
            "agent_key": "tracking_agent",
            "name": "Tracking Agent (Legacy)",
            "description": "[DEPRECATED] Use ecommerce_agent. Internal node for order tracking.",
            "agent_type": "builtin",
            "domain_key": "ecommerce",
            "enabled": False,
            "priority": 75,
            "keywords": ["seguimiento", "envio", "entrega", "pedido", "donde", "rastreo", "tracking"],
            "intent_patterns": [{"pattern": "seguimiento", "weight": 0.8}],
            "config": {"require_order_id": False, "show_estimated_delivery": True, "deprecated": True},
        },
        {
            "agent_key": "invoice_agent",
            "name": "Invoice Agent (Legacy)",
            "description": "[DEPRECATED] Use ecommerce_agent. Internal node for e-commerce billing.",
            "agent_type": "builtin",
            "domain_key": "ecommerce",
            "enabled": False,
            "priority": 75,
            "keywords": ["factura", "pago", "recibo", "comprobante", "devolucion", "reembolso"],
            "intent_patterns": [{"pattern": "facturacion", "weight": 0.8}],
            "config": {"require_order_id": False, "can_generate_invoice": True, "deprecated": True},
        },
    ]

    import json

    for agent in builtin_agents:
        conn.execute(
            sa.text("""
                INSERT INTO core.agents (
                    agent_key, name, description, agent_type, domain_key,
                    enabled, priority, keywords, intent_patterns, config, sync_source
                ) VALUES (
                    :agent_key, :name, :description, :agent_type, :domain_key,
                    :enabled, :priority, CAST(:keywords AS text[]), CAST(:intent_patterns AS jsonb),
                    CAST(:config AS jsonb), 'seed'
                )
                ON CONFLICT (agent_key) DO NOTHING
            """),
            {
                "agent_key": agent["agent_key"],
                "name": agent["name"],
                "description": agent["description"],
                "agent_type": agent["agent_type"],
                "domain_key": agent["domain_key"],
                "enabled": agent["enabled"],
                "priority": agent["priority"],
                "keywords": "{" + ",".join(f'"{k}"' for k in agent["keywords"]) + "}",
                "intent_patterns": json.dumps(agent["intent_patterns"]),
                "config": json.dumps(agent["config"]),
            },
        )

    # Add table comment
    op.execute("""
        COMMENT ON TABLE core.agents IS
        'Registry of available agents in the system. Admin controls visibility via enabled flag. Replaces ENABLED_AGENTS env var.'
    """)


def downgrade() -> None:
    """Remove agents table."""

    # Drop indexes
    op.drop_index("idx_agents_enabled_priority", table_name="agents", schema="core")
    op.drop_index("idx_agents_priority", table_name="agents", schema="core")
    op.drop_index("idx_agents_enabled", table_name="agents", schema="core")
    op.drop_index("idx_agents_domain_key", table_name="agents", schema="core")
    op.drop_index("idx_agents_agent_type", table_name="agents", schema="core")
    op.drop_index("idx_agents_agent_key", table_name="agents", schema="core")

    # Drop table
    op.drop_table("agents", schema="core")
