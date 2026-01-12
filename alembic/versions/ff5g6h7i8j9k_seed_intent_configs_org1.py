"""Seed intent configs for organization 1.

Revision ID: ff5g6h7i8j9k
Revises: ee4f5g6h7i8j
Create Date: 2026-01-11

Seeds the intent configuration tables for organization
00000000-0000-0000-0000-000000000001 (Org 1):
- intent_agent_mappings: Maps intents to target agents
- flow_agent_configs: Configures agents with multi-turn flows
- keyword_agent_mappings: Keyword-based fallback routing

This migration uses the data from app/scripts/seed_intent_configs.py.
"""

import json
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ff5g6h7i8j9k"
down_revision: Union[str, Sequence[str], None] = "ee4f5g6h7i8j"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Organization UUID for seed data
ORG_1_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    """Seed intent configs for organization 1."""
    _seed_intent_agent_mappings()
    _seed_flow_agent_configs()
    _seed_keyword_agent_mappings()


def downgrade() -> None:
    """Remove intent configs for organization 1."""
    op.execute(f"""
        DELETE FROM core.keyword_agent_mappings
        WHERE organization_id = '{ORG_1_ID}'
    """)
    op.execute(f"""
        DELETE FROM core.flow_agent_configs
        WHERE organization_id = '{ORG_1_ID}'
    """)
    op.execute(f"""
        DELETE FROM core.intent_agent_mappings
        WHERE organization_id = '{ORG_1_ID}'
    """)


def _seed_intent_agent_mappings() -> None:
    """Seed intent-to-agent mappings."""
    mappings = _get_intent_agent_mappings()

    for m in mappings:
        domain_key = f"'{m['domain_key']}'" if m.get("domain_key") else "NULL"
        intent_name = m["intent_name"].replace("'", "''")
        intent_desc = (m.get("intent_description") or "").replace("'", "''")
        examples = json.dumps(m.get("examples", []))

        op.execute(f"""
            INSERT INTO core.intent_agent_mappings (
                organization_id, domain_key, intent_key, intent_name, intent_description,
                agent_key, confidence_threshold, requires_handoff, priority, is_enabled, examples
            ) VALUES (
                '{ORG_1_ID}',
                {domain_key},
                '{m["intent_key"]}',
                '{intent_name}',
                '{intent_desc}',
                '{m["agent_key"]}',
                {m.get("confidence_threshold", 0.75)},
                {str(m.get("requires_handoff", False)).lower()},
                {m.get("priority", 50)},
                true,
                '{examples}'::jsonb
            )
            ON CONFLICT (organization_id, domain_key, intent_key) DO NOTHING
        """)


def _seed_flow_agent_configs() -> None:
    """Seed flow agent configurations."""
    configs = _get_flow_agent_configs()

    for c in configs:
        flow_desc = (c.get("flow_description") or "").replace("'", "''")
        config_json = json.dumps(c.get("config", {}))

        op.execute(f"""
            INSERT INTO core.flow_agent_configs (
                organization_id, agent_key, is_flow_agent, flow_description,
                max_turns, timeout_seconds, is_enabled, config
            ) VALUES (
                '{ORG_1_ID}',
                '{c["agent_key"]}',
                {str(c.get("is_flow_agent", True)).lower()},
                '{flow_desc}',
                {c.get("max_turns", 10)},
                {c.get("timeout_seconds", 300)},
                true,
                '{config_json}'::jsonb
            )
            ON CONFLICT (organization_id, agent_key) DO NOTHING
        """)


def _seed_keyword_agent_mappings() -> None:
    """Seed keyword-to-agent mappings."""
    mappings = _get_keyword_agent_mappings()

    for m in mappings:
        keyword = m["keyword"].replace("'", "''")

        op.execute(f"""
            INSERT INTO core.keyword_agent_mappings (
                organization_id, agent_key, keyword, match_type, case_sensitive, priority, is_enabled
            ) VALUES (
                '{ORG_1_ID}',
                '{m["agent_key"]}',
                '{keyword}',
                '{m.get("match_type", "contains")}',
                {str(m.get("case_sensitive", False)).lower()},
                {m.get("priority", 50)},
                true
            )
            ON CONFLICT (organization_id, agent_key, keyword) DO NOTHING
        """)


def _get_intent_agent_mappings() -> list:
    """
    Get seed data for intent_agent_mappings table.

    Duplicated from seed_intent_configs.py to make migration self-contained.
    """
    return [
        # Excelencia domain agents
        {
            "domain_key": "excelencia",
            "intent_key": "excelencia",
            "intent_name": "Excelencia General",
            "intent_description": "Consultas generales sobre el sistema Excelencia",
            "agent_key": "excelencia_agent",
            "confidence_threshold": 0.75,
            "requires_handoff": False,
            "priority": 50,
            "examples": ["como funciona excelencia", "que modulos tiene"],
        },
        {
            "domain_key": "excelencia",
            "intent_key": "excelencia_soporte",
            "intent_name": "Soporte Excelencia",
            "intent_description": "Solicitudes de soporte y creacion de tickets",
            "agent_key": "excelencia_support_agent",
            "confidence_threshold": 0.75,
            "requires_handoff": True,
            "priority": 60,
            "examples": ["tengo un problema", "necesito ayuda", "reportar error"],
        },
        {
            "domain_key": "excelencia",
            "intent_key": "excelencia_facturacion",
            "intent_name": "Facturacion Excelencia",
            "intent_description": "Consultas de facturas y pagos de Excelencia",
            "agent_key": "excelencia_invoice_agent",
            "confidence_threshold": 0.75,
            "requires_handoff": False,
            "priority": 55,
            "examples": ["ver mi factura", "estado de pago", "historial de facturacion"],
        },
        {
            "domain_key": "excelencia",
            "intent_key": "excelencia_promociones",
            "intent_name": "Promociones Excelencia",
            "intent_description": "Consultas sobre promociones y ofertas de Excelencia",
            "agent_key": "excelencia_promotions_agent",
            "confidence_threshold": 0.75,
            "requires_handoff": False,
            "priority": 45,
            "examples": ["hay promociones", "descuentos disponibles"],
        },
        # Global agents (domain_key = NULL)
        {
            "domain_key": None,
            "intent_key": "soporte",
            "intent_name": "Soporte General",
            "intent_description": "Solicitudes de soporte tecnico general",
            "agent_key": "support_agent",
            "confidence_threshold": 0.75,
            "requires_handoff": True,
            "priority": 50,
            "examples": ["necesito soporte", "ayuda tecnica"],
        },
        {
            "domain_key": None,
            "intent_key": "saludo",
            "intent_name": "Saludo",
            "intent_description": "Saludos iniciales del usuario",
            "agent_key": "greeting_agent",
            "confidence_threshold": 0.80,
            "requires_handoff": False,
            "priority": 70,
            "examples": ["hola", "buenos dias", "buenas tardes"],
        },
        {
            "domain_key": None,
            "intent_key": "fallback",
            "intent_name": "Fallback",
            "intent_description": "Intent no reconocido o ambiguo",
            "agent_key": "fallback_agent",
            "confidence_threshold": 0.0,
            "requires_handoff": False,
            "priority": 10,
            "examples": [],
        },
        {
            "domain_key": None,
            "intent_key": "despedida",
            "intent_name": "Despedida",
            "intent_description": "Despedidas y finalizacion de conversacion",
            "agent_key": "farewell_agent",
            "confidence_threshold": 0.80,
            "requires_handoff": False,
            "priority": 65,
            "examples": ["adios", "hasta luego", "gracias chao"],
        },
        # Ecommerce domain
        {
            "domain_key": "ecommerce",
            "intent_key": "producto",
            "intent_name": "Consulta de Producto",
            "intent_description": "Consultas sobre productos y catalogo",
            "agent_key": "product_agent",
            "confidence_threshold": 0.75,
            "requires_handoff": False,
            "priority": 50,
            "examples": ["buscar producto", "ver catalogo"],
        },
        {
            "domain_key": "ecommerce",
            "intent_key": "ecommerce",
            "intent_name": "Ecommerce General",
            "intent_description": "Consultas generales de ecommerce",
            "agent_key": "ecommerce_agent",
            "confidence_threshold": 0.75,
            "requires_handoff": False,
            "priority": 45,
            "examples": ["comprar", "agregar al carrito"],
        },
        # Data insights
        {
            "domain_key": None,
            "intent_key": "datos",
            "intent_name": "Consulta de Datos",
            "intent_description": "Consultas de datos y reportes",
            "agent_key": "data_insights_agent",
            "confidence_threshold": 0.75,
            "requires_handoff": False,
            "priority": 50,
            "examples": ["ver estadisticas", "reporte de ventas"],
        },
        # Pharmacy domain
        {
            "domain_key": "pharmacy",
            "intent_key": "pharmacy",
            "intent_name": "Operaciones Farmacia",
            "intent_description": "Operaciones del dominio farmacia (deuda, pagos, etc.)",
            "agent_key": "pharmacy_operations_agent",
            "confidence_threshold": 0.75,
            "requires_handoff": False,
            "priority": 60,
            "examples": ["consultar deuda", "quiero pagar", "mi saldo"],
        },
    ]


def _get_flow_agent_configs() -> list:
    """
    Get seed data for flow_agent_configs table.

    Duplicated from seed_intent_configs.py to make migration self-contained.
    """
    return [
        {
            "agent_key": "excelencia_support_agent",
            "is_flow_agent": True,
            "flow_description": "3-step incident creation: description -> priority -> confirm",
            "max_turns": 10,
            "timeout_seconds": 300,
            "config": {
                "steps": ["collect_description", "select_priority", "confirm_creation"],
                "allow_cancel": True,
            },
        },
        {
            "agent_key": "excelencia_invoice_agent",
            "is_flow_agent": True,
            "flow_description": "Invoice lookup and payment flow",
            "max_turns": 8,
            "timeout_seconds": 300,
            "config": {
                "steps": ["search_invoice", "display_details", "process_action"],
                "allow_cancel": True,
            },
        },
        {
            "agent_key": "pharmacy_operations_agent",
            "is_flow_agent": True,
            "flow_description": "Pharmacy operations: debt query, payment, registration",
            "max_turns": 15,
            "timeout_seconds": 600,
            "config": {
                "steps": [
                    "identify_user",
                    "resolve_person",
                    "show_debt",
                    "process_payment",
                ],
                "allow_cancel": True,
                "requires_identification": True,
            },
        },
    ]


def _get_keyword_agent_mappings() -> list:
    """
    Get seed data for keyword_agent_mappings table.

    Duplicated from seed_intent_configs.py to make migration self-contained.
    """
    mappings = []

    # Pharmacy operations agent keywords
    pharmacy_keywords = [
        "receta", "medicamento", "farmacia", "medicamentos", "pedido farmacia",
        "deuda farmacia", "urgente receta", "envie receta", "mande receta",
    ]
    for kw in pharmacy_keywords:
        mappings.append({
            "agent_key": "pharmacy_operations_agent",
            "keyword": kw,
            "match_type": "contains",
            "case_sensitive": False,
            "priority": 60,
        })

    # Excelencia support agent keywords
    support_keywords = [
        "problema", "error", "falla", "no funciona", "ayuda", "soporte",
        "incidente", "bug", "ticket",
    ]
    for kw in support_keywords:
        mappings.append({
            "agent_key": "excelencia_support_agent",
            "keyword": kw,
            "match_type": "contains",
            "case_sensitive": False,
            "priority": 55,
        })

    # Excelencia invoice agent keywords
    invoice_keywords = [
        "factura", "facturacion", "cobro", "pago", "cuenta", "deuda",
    ]
    for kw in invoice_keywords:
        mappings.append({
            "agent_key": "excelencia_invoice_agent",
            "keyword": kw,
            "match_type": "contains",
            "case_sensitive": False,
            "priority": 50,
        })

    # Greeting agent keywords
    greeting_keywords = [
        "hola", "buenos dias", "buenas tardes", "buenas noches", "hi", "hello",
    ]
    for kw in greeting_keywords:
        mappings.append({
            "agent_key": "greeting_agent",
            "keyword": kw,
            "match_type": "exact" if len(kw.split()) == 1 else "contains",
            "case_sensitive": False,
            "priority": 70,
        })

    # Farewell agent keywords
    farewell_keywords = [
        "adios", "chao", "bye", "hasta luego", "gracias", "nos vemos",
    ]
    for kw in farewell_keywords:
        mappings.append({
            "agent_key": "farewell_agent",
            "keyword": kw,
            "match_type": "exact" if len(kw.split()) == 1 else "contains",
            "case_sensitive": False,
            "priority": 65,
        })

    return mappings
