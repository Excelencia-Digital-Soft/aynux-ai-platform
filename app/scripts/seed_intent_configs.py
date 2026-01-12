# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Seed data for intent configuration tables.
# Tenant-Aware: Used to seed per-organization intent configs.
# Domain-Aware: Configs can be scoped by domain_key.
# ============================================================================
"""
Intent Config Seed Data - Default configurations for intent routing.

This module provides seed data for the three intent configuration tables:
- IntentAgentMapping: Maps intents to target agents
- FlowAgentConfig: Configures agents with multi-turn flows
- KeywordAgentMapping: Keyword-based fallback routing

Usage:
    from app.scripts.seed_intent_configs import (
        get_intent_agent_mappings,
        get_flow_agent_configs,
        get_keyword_agent_mappings,
    )

    # Get default seed data
    mappings = get_intent_agent_mappings()
    flows = get_flow_agent_configs()
    keywords = get_keyword_agent_mappings()
"""

from __future__ import annotations

from typing import Any


def get_intent_agent_mappings() -> list[dict[str, Any]]:
    """
    Get seed data for intent_agent_mappings table.

    Maps agent names to valid intents. Used when LLM returns agent name
    instead of intent name, and for intent-to-agent routing.

    Returns:
        List of mapping dictionaries with intent and agent config.
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


def get_flow_agent_configs() -> list[dict[str, Any]]:
    """
    Get seed data for flow_agent_configs table.

    Configures agents that have multi-turn conversational flows.
    These agents continue handling conversation until flow completes.

    Returns:
        List of flow agent configuration dictionaries.
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


def get_keyword_agent_mappings() -> list[dict[str, Any]]:
    """
    Get seed data for keyword_agent_mappings table.

    Keyword-based routing used as fallback when follow_up is detected
    but no previous agent exists.

    Returns:
        List of keyword mapping dictionaries.
    """
    mappings = []

    # Pharmacy operations agent keywords
    pharmacy_keywords = [
        "receta",
        "medicamento",
        "farmacia",
        "medicamentos",
        "pedido farmacia",
        "deuda farmacia",
        "urgente receta",
        "envie receta",
        "mande receta",
    ]
    for kw in pharmacy_keywords:
        mappings.append(
            {
                "agent_key": "pharmacy_operations_agent",
                "keyword": kw,
                "match_type": "contains",
                "case_sensitive": False,
                "priority": 60,
            }
        )

    # Excelencia support agent keywords
    support_keywords = [
        "problema",
        "error",
        "falla",
        "no funciona",
        "ayuda",
        "soporte",
        "incidente",
        "bug",
        "ticket",
    ]
    for kw in support_keywords:
        mappings.append(
            {
                "agent_key": "excelencia_support_agent",
                "keyword": kw,
                "match_type": "contains",
                "case_sensitive": False,
                "priority": 55,
            }
        )

    # Excelencia invoice agent keywords
    invoice_keywords = [
        "factura",
        "facturacion",
        "cobro",
        "pago",
        "cuenta",
        "deuda",
    ]
    for kw in invoice_keywords:
        mappings.append(
            {
                "agent_key": "excelencia_invoice_agent",
                "keyword": kw,
                "match_type": "contains",
                "case_sensitive": False,
                "priority": 50,
            }
        )

    # Greeting agent keywords
    greeting_keywords = [
        "hola",
        "buenos dias",
        "buenas tardes",
        "buenas noches",
        "hi",
        "hello",
    ]
    for kw in greeting_keywords:
        mappings.append(
            {
                "agent_key": "greeting_agent",
                "keyword": kw,
                "match_type": "exact" if len(kw.split()) == 1 else "contains",
                "case_sensitive": False,
                "priority": 70,
            }
        )

    # Farewell agent keywords
    farewell_keywords = [
        "adios",
        "chao",
        "bye",
        "hasta luego",
        "gracias",
        "nos vemos",
    ]
    for kw in farewell_keywords:
        mappings.append(
            {
                "agent_key": "farewell_agent",
                "keyword": kw,
                "match_type": "exact" if len(kw.split()) == 1 else "contains",
                "case_sensitive": False,
                "priority": 65,
            }
        )

    return mappings


__all__ = [
    "get_intent_agent_mappings",
    "get_flow_agent_configs",
    "get_keyword_agent_mappings",
]
