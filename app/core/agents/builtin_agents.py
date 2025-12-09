# ============================================================================
# SCOPE: GLOBAL
# Description: Configuraciones por defecto de todos los agentes builtin.
#              Estos defaults pueden ser sobrescritos por tenant via tenant_agents.
# Tenant-Aware: No directamente, pero provee base que TenantAgentService usa.
# ============================================================================
"""
Builtin Agent Defaults.

Default configurations for all builtin agents. These serve as the base
configuration that can be overridden per-tenant via the tenant_agents table.

Each agent definition includes:
- agent_type: Always "builtin" for these
- display_name: Human-readable name
- description: What the agent does
- priority: Routing priority (100 = highest, 0 = lowest)
- domain_key: Associated domain (for domain-specific agents)
- keywords: Keywords for intent matching
- intent_patterns: Patterns with weights for routing
- config: Agent-specific settings (prompts, model params, etc.)
"""

from __future__ import annotations

from app.core.schemas.tenant_agent_config import AgentConfig, IntentPattern

# Default configurations for all builtin agents
BUILTIN_AGENT_DEFAULTS: dict[str, dict] = {
    "greeting_agent": {
        "agent_type": "builtin",
        "display_name": "Greeting Agent",
        "description": "Handles greetings and provides system capabilities overview",
        "priority": 100,
        "domain_key": None,
        "keywords": [
            "hola",
            "hello",
            "hi",
            "buenos dias",
            "buenas tardes",
            "buenas noches",
            "good morning",
            "good afternoon",
            "good evening",
            "hey",
            "que tal",
        ],
        "intent_patterns": [
            {"pattern": "saludo", "weight": 1.0},
        ],
        "config": {
            "response_style": "friendly",
            "show_capabilities": True,
            "max_greeting_length": 200,
        },
    },
    "ecommerce_agent": {
        "agent_type": "builtin",
        "display_name": "E-commerce Agent",
        "description": "Handles all e-commerce queries: products, promotions, tracking, billing",
        "priority": 80,
        "domain_key": "ecommerce",
        "keywords": [
            "producto",
            "precio",
            "compra",
            "pedido",
            "orden",
            "factura",
            "promocion",
            "descuento",
            "oferta",
            "seguimiento",
            "envio",
            "entrega",
            "stock",
            "disponible",
            "catalogo",
        ],
        "intent_patterns": [
            {"pattern": "producto", "weight": 1.0},
            {"pattern": "promociones", "weight": 0.9},
            {"pattern": "seguimiento", "weight": 0.9},
            {"pattern": "facturacion", "weight": 0.9},
            {"pattern": "ecommerce", "weight": 1.0},
        ],
        "config": {
            "enable_search": True,
            "max_results": 5,
            "enable_promotions": True,
            "enable_tracking": True,
            "enable_billing": True,
        },
    },
    "product_agent": {
        "agent_type": "builtin",
        "display_name": "Product Agent (Legacy)",
        "description": "[DEPRECATED] Use ecommerce_agent. Handles product inquiries.",
        "priority": 70,
        "domain_key": "ecommerce",
        "keywords": [
            "producto",
            "precio",
            "stock",
            "disponible",
            "catalogo",
            "buscar",
        ],
        "intent_patterns": [
            {"pattern": "producto", "weight": 0.8},
        ],
        "config": {
            "enable_search": True,
            "max_results": 5,
            "deprecated": True,
        },
    },
    # DEPRECATED: Use ecommerce_agent instead
    "promotions_agent": {
        "agent_type": "builtin",
        "display_name": "Promotions Agent (Legacy)",
        "description": "[DEPRECATED] Use ecommerce_agent. Internal node for promotions.",
        "priority": 70,
        "domain_key": "ecommerce",
        "keywords": [
            "promocion",
            "descuento",
            "oferta",
            "cupon",
            "rebaja",
            "sale",
        ],
        "intent_patterns": [
            {"pattern": "promociones", "weight": 0.8},
        ],
        "config": {
            "show_active_only": True,
            "max_promotions": 3,
            "deprecated": True,
        },
    },
    # DEPRECATED: Use ecommerce_agent instead
    "tracking_agent": {
        "agent_type": "builtin",
        "display_name": "Tracking Agent (Legacy)",
        "description": "[DEPRECATED] Use ecommerce_agent. Internal node for order tracking.",
        "priority": 75,
        "domain_key": "ecommerce",
        "keywords": [
            "seguimiento",
            "envio",
            "entrega",
            "pedido",
            "donde",
            "rastreo",
            "tracking",
        ],
        "intent_patterns": [
            {"pattern": "seguimiento", "weight": 0.8},
        ],
        "config": {
            "require_order_id": False,
            "show_estimated_delivery": True,
            "deprecated": True,
        },
    },
    # DEPRECATED: Use ecommerce_agent instead
    "invoice_agent": {
        "agent_type": "builtin",
        "display_name": "Invoice Agent (Legacy)",
        "description": "[DEPRECATED] Use ecommerce_agent. Internal node for e-commerce billing.",
        "priority": 75,
        "domain_key": "ecommerce",
        "keywords": [
            "factura",
            "pago",
            "recibo",
            "comprobante",
            "devolucion",
            "reembolso",
        ],
        "intent_patterns": [
            {"pattern": "facturacion", "weight": 0.8},
        ],
        "config": {
            "require_order_id": False,
            "can_generate_invoice": True,
            "deprecated": True,
        },
    },
    "data_insights_agent": {
        "agent_type": "builtin",
        "display_name": "Data Insights Agent",
        "description": "Provides analytics, reports, and data insights for Excelencia domain",
        "priority": 60,
        "domain_key": "excelencia",  # Updated: now part of Excelencia domain
        "keywords": [
            "estadistica",
            "reporte",
            "analisis",
            "datos",
            "ventas",
            "metricas",
            "dashboard",
        ],
        "intent_patterns": [
            {"pattern": "datos", "weight": 1.0},
        ],
        "config": {
            "allow_export": False,
            "max_date_range_days": 30,
        },
    },
    "support_agent": {
        "agent_type": "builtin",
        "display_name": "Support Agent",
        "description": "Provides technical support and troubleshooting assistance",
        "priority": 65,
        "domain_key": None,
        "keywords": [
            "ayuda",
            "problema",
            "error",
            "falla",
            "soporte",
            "tecnico",
            "reclamo",
            "queja",
        ],
        "intent_patterns": [
            {"pattern": "soporte", "weight": 1.0},
        ],
        "config": {
            "enable_ticket_creation": True,
            "escalation_threshold": 2,
            "requires_handoff": True,
        },
    },
    "excelencia_agent": {
        "agent_type": "builtin",
        "display_name": "Excelencia ERP Agent",
        "description": "Handles queries about Excelencia ERP: demos, modules, training, verticals",
        "priority": 70,
        "domain_key": "excelencia",
        "keywords": [
            "excelencia",
            "erp",
            "historia clinica",
            "turnos",
            "hotel",
            "obra social",
            "modulo",
            "demo",
            "capacitacion",
            "mision",
            "vision",
        ],
        "intent_patterns": [
            {"pattern": "excelencia", "weight": 1.0},
        ],
        "config": {
            "enable_rag": True,
            "show_demo_links": True,
            "vertical_products": [
                "healthcare",
                "hotels",
                "social_security",
            ],
        },
    },
    # NEW: Excelencia Invoice Agent
    "excelencia_invoice_agent": {
        "agent_type": "builtin",
        "display_name": "Excelencia Invoice Agent",
        "description": "Handles client invoicing, account statements, and collections for Excelencia",
        "priority": 72,
        "domain_key": "excelencia",
        "keywords": [
            "factura cliente",
            "estado de cuenta",
            "cobranza",
            "deuda cliente",
            "cobrar",
            "pago cliente",
            "saldo pendiente",
            "cuenta por cobrar",
        ],
        "intent_patterns": [
            {"pattern": "excelencia_facturacion", "weight": 1.0},
        ],
        "config": {
            "enable_rag": True,
            "require_client_id": False,
            "can_generate_statement": True,
        },
    },
    # NEW: Excelencia Promotions Agent
    "excelencia_promotions_agent": {
        "agent_type": "builtin",
        "display_name": "Excelencia Promotions Agent",
        "description": "Handles software promotions, module discounts, and implementation offers",
        "priority": 71,
        "domain_key": "excelencia",
        "keywords": [
            "promocion software",
            "descuento modulo",
            "oferta implementacion",
            "descuento capacitacion",
            "promocion excelencia",
            "oferta software",
        ],
        "intent_patterns": [
            {"pattern": "excelencia_promociones", "weight": 1.0},
        ],
        "config": {
            "enable_rag": True,
            "show_active_only": True,
            "max_promotions": 5,
        },
    },
    "fallback_agent": {
        "agent_type": "builtin",
        "display_name": "Fallback Agent",
        "description": "Handles general inquiries and provides fallback responses",
        "priority": 10,
        "domain_key": None,
        "keywords": [],
        "intent_patterns": [
            {"pattern": "fallback", "weight": 1.0},
        ],
        "config": {
            "suggest_alternatives": True,
            "max_fallback_count": 3,
            "escalate_after_fallbacks": True,
        },
    },
    "farewell_agent": {
        "agent_type": "builtin",
        "display_name": "Farewell Agent",
        "description": "Manages conversation closure and farewells",
        "priority": 90,
        "domain_key": None,
        "keywords": [
            "adios",
            "chau",
            "hasta luego",
            "gracias",
            "bye",
            "goodbye",
            "thanks",
        ],
        "intent_patterns": [
            {"pattern": "despedida", "weight": 1.0},
        ],
        "config": {
            "show_survey_link": False,
            "save_conversation": True,
        },
    },
    "credit_agent": {
        "agent_type": "builtin",
        "display_name": "Credit Agent",
        "description": "Handles credit-related queries: accounts, payments, collections",
        "priority": 75,
        "domain_key": "credit",
        "keywords": [
            "credito",
            "cuenta",
            "deuda",
            "pago",
            "cuota",
            "mora",
            "cobranza",
        ],
        "intent_patterns": [
            {"pattern": "credito", "weight": 1.0},
        ],
        "config": {
            "require_account_verification": True,
            "show_payment_options": True,
        },
    },
    # Pharmacy domain agent
    "pharmacy_operations_agent": {
        "agent_type": "builtin",
        "display_name": "Pharmacy Operations Agent",
        "description": "Handles pharmacy debt queries, confirmations, and invoice generation",
        "priority": 75,
        "domain_key": "pharmacy",
        "keywords": [
            "deuda",
            "farmacia",
            "saldo",
            "factura",
            "confirmar",
            "cuenta",
            "pendiente",
            "debo",
        ],
        "intent_patterns": [
            {"pattern": "pharmacy", "weight": 1.0},
        ],
        "config": {
            "enable_bypass": True,
            "require_confirmation": True,
            "max_workflow_steps": 3,
        },
    },
}


def get_builtin_agent_config(agent_key: str) -> AgentConfig | None:
    """
    Get the default configuration for a builtin agent.

    Args:
        agent_key: The agent key (e.g., "greeting_agent")

    Returns:
        AgentConfig or None if not found
    """
    if agent_key not in BUILTIN_AGENT_DEFAULTS:
        return None

    defaults = BUILTIN_AGENT_DEFAULTS[agent_key]

    # Convert intent_patterns dicts to IntentPattern objects
    intent_patterns = [
        IntentPattern(**p) if isinstance(p, dict) else p
        for p in defaults.get("intent_patterns", [])
    ]

    return AgentConfig(
        agent_key=agent_key,
        agent_type=defaults["agent_type"],
        display_name=defaults["display_name"],
        description=defaults.get("description"),
        priority=defaults.get("priority", 50),
        domain_key=defaults.get("domain_key"),
        keywords=defaults.get("keywords", []),
        intent_patterns=intent_patterns,
        config=defaults.get("config", {}),
        enabled=True,
    )


def get_all_builtin_agents() -> dict[str, AgentConfig]:
    """
    Get all builtin agent configurations.

    Returns:
        Dict of agent_key -> AgentConfig
    """
    result: dict[str, AgentConfig] = {}
    for key in BUILTIN_AGENT_DEFAULTS:
        config = get_builtin_agent_config(key)
        if config is not None:
            result[key] = config
    return result


def get_builtin_agent_keys() -> list[str]:
    """Get list of all builtin agent keys."""
    return list(BUILTIN_AGENT_DEFAULTS.keys())


__all__ = [
    "BUILTIN_AGENT_DEFAULTS",
    "get_builtin_agent_config",
    "get_all_builtin_agents",
    "get_builtin_agent_keys",
]
