"""Seed intent configs for System Organization.

Revision ID: rr7s8t9u0v1w
Revises: qq6r7s8t9u0v
Create Date: 2026-01-12

Seeds the intent configuration tables for System Organization
00000000-0000-0000-0000-000000000000 (Production):
- intent_agent_mappings: Maps intents to target agents
- flow_agent_configs: Configures agents with multi-turn flows
- keyword_agent_mappings: Keyword-based fallback routing

This mirrors the data in Org 1 (Test Pharmacy) from migration ff5g6h7i8j9k.
"""

from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "rr7s8t9u0v1w"
down_revision: Union[str, Sequence[str], None] = "qq6r7s8t9u0v"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# System Organization UUID (Production)
SYSTEM_ORG_ID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    """Seed intent configs for System Organization."""
    _seed_intent_agent_mappings()
    _seed_flow_agent_configs()
    _seed_keyword_agent_mappings()


def downgrade() -> None:
    """Remove intent configs for System Organization."""
    connection = op.get_bind()

    connection.execute(
        sa.text(f"DELETE FROM core.keyword_agent_mappings WHERE organization_id = '{SYSTEM_ORG_ID}'")
    )
    connection.execute(
        sa.text(f"DELETE FROM core.flow_agent_configs WHERE organization_id = '{SYSTEM_ORG_ID}'")
    )
    connection.execute(
        sa.text(f"DELETE FROM core.intent_agent_mappings WHERE organization_id = '{SYSTEM_ORG_ID}'")
    )


def _seed_intent_agent_mappings() -> None:
    """Seed intent-to-agent mappings."""
    connection = op.get_bind()
    mappings = _get_intent_agent_mappings()

    for m in mappings:
        # Check if already exists
        result = connection.execute(
            sa.text("""
                SELECT id FROM core.intent_agent_mappings
                WHERE organization_id = :org_id
                AND COALESCE(domain_key, '') = COALESCE(:domain_key, '')
                AND intent_key = :intent_key
            """),
            {
                "org_id": SYSTEM_ORG_ID,
                "domain_key": m.get("domain_key"),
                "intent_key": m["intent_key"],
            },
        )
        if result.fetchone():
            continue

        connection.execute(
            sa.text("""
                INSERT INTO core.intent_agent_mappings (
                    organization_id, domain_key, intent_key, intent_name, intent_description,
                    agent_key, confidence_threshold, requires_handoff, priority, is_enabled, examples
                ) VALUES (
                    :org_id, :domain_key, :intent_key, :intent_name, :intent_desc,
                    :agent_key, :confidence, :handoff, :priority, true, :examples
                )
            """),
            {
                "org_id": SYSTEM_ORG_ID,
                "domain_key": m.get("domain_key"),
                "intent_key": m["intent_key"],
                "intent_name": m["intent_name"],
                "intent_desc": m.get("intent_description", ""),
                "agent_key": m["agent_key"],
                "confidence": m.get("confidence_threshold", 0.75),
                "handoff": m.get("requires_handoff", False),
                "priority": m.get("priority", 50),
                "examples": json.dumps(m.get("examples", [])),
            },
        )


def _seed_flow_agent_configs() -> None:
    """Seed flow agent configurations."""
    connection = op.get_bind()
    configs = _get_flow_agent_configs()

    for c in configs:
        # Check if already exists
        result = connection.execute(
            sa.text("""
                SELECT id FROM core.flow_agent_configs
                WHERE organization_id = :org_id
                AND agent_key = :agent_key
            """),
            {
                "org_id": SYSTEM_ORG_ID,
                "agent_key": c["agent_key"],
            },
        )
        if result.fetchone():
            continue

        connection.execute(
            sa.text("""
                INSERT INTO core.flow_agent_configs (
                    organization_id, agent_key, is_flow_agent, flow_description,
                    max_turns, timeout_seconds, is_enabled, config
                ) VALUES (
                    :org_id, :agent_key, :is_flow, :flow_desc,
                    :max_turns, :timeout, true, :config
                )
            """),
            {
                "org_id": SYSTEM_ORG_ID,
                "agent_key": c["agent_key"],
                "is_flow": c.get("is_flow_agent", True),
                "flow_desc": c.get("flow_description", ""),
                "max_turns": c.get("max_turns", 10),
                "timeout": c.get("timeout_seconds", 300),
                "config": json.dumps(c.get("config", {})),
            },
        )


def _seed_keyword_agent_mappings() -> None:
    """Seed keyword-to-agent mappings."""
    connection = op.get_bind()
    mappings = _get_keyword_agent_mappings()

    for m in mappings:
        # Check if already exists
        result = connection.execute(
            sa.text("""
                SELECT id FROM core.keyword_agent_mappings
                WHERE organization_id = :org_id
                AND agent_key = :agent_key
                AND keyword = :keyword
            """),
            {
                "org_id": SYSTEM_ORG_ID,
                "agent_key": m["agent_key"],
                "keyword": m["keyword"],
            },
        )
        if result.fetchone():
            continue

        connection.execute(
            sa.text("""
                INSERT INTO core.keyword_agent_mappings (
                    organization_id, agent_key, keyword, match_type, case_sensitive, priority, is_enabled
                ) VALUES (
                    :org_id, :agent_key, :keyword, :match_type, :case_sensitive, :priority, true
                )
            """),
            {
                "org_id": SYSTEM_ORG_ID,
                "agent_key": m["agent_key"],
                "keyword": m["keyword"],
                "match_type": m.get("match_type", "contains"),
                "case_sensitive": m.get("case_sensitive", False),
                "priority": m.get("priority", 50),
            },
        )


def _get_intent_agent_mappings() -> list:
    """Get seed data for intent_agent_mappings table."""
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
    """Get seed data for flow_agent_configs table."""
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
    """Get seed data for keyword_agent_mappings table."""
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
