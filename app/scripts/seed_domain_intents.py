"""
Seed domain intent patterns from hardcoded values to database.

Multi-domain support: pharmacy, excelencia, ecommerce, healthcare, etc.

Usage:
    # Via API endpoint (recommended)
    POST /api/v1/admin/domains/{domain_key}/intents/seed?organization_id={uuid}

    # Direct script execution
    python -m app.scripts.seed_domain_intents --org-id {uuid} --domain pharmacy

Field Defaults (applied by repository if not specified):
    - is_enabled: True (all intents active by default)
    - priority: 50 (default evaluation order)

Priority Guide:
    - 90-100: Exact match intents (confirm, reject) - evaluated first
    - 70-80: High priority intents (document_input, capability_question)
    - 50-60: Standard intents (debt_query, invoice, greeting, etc.)
    - 40-49: Lower priority intents (register, summary)
"""

from __future__ import annotations

from typing import Any

# =============================================================================
# DOMAIN SEED DATA REGISTRY
# =============================================================================

DOMAIN_SEED_DATA: dict[str, dict[str, dict[str, Any]]] = {}


def get_seed_data_for_domain(domain_key: str) -> dict[str, dict[str, Any]] | None:
    """
    Get seed data for a specific domain.

    Args:
        domain_key: Domain identifier (e.g., "pharmacy", "excelencia")

    Returns:
        Dict of intent patterns or None if domain not found
    """
    return DOMAIN_SEED_DATA.get(domain_key)


def get_available_seed_domains() -> list[str]:
    """Get list of domains with available seed data."""
    return list(DOMAIN_SEED_DATA.keys())


# =============================================================================
# PHARMACY DOMAIN SEED DATA
# Migrated from seed_pharmacy_intents.py
# =============================================================================

PHARMACY_INTENTS: dict[str, dict[str, Any]] = {
    "capability_question": {
        "name": "Pregunta de Capacidades",
        "description": "Preguntas sobre qué puede hacer el bot, sus funciones y servicios",
        "weight": 1.5,
        "exact_match": False,
        "priority": 75,
        "lemmas": ["poder", "hacer", "servir", "funcionar", "ayudar", "ofrecer", "servicio"],
        "phrases": [
            {"phrase": "que puedes hacer", "match_type": "contains"},
            {"phrase": "qué puedes hacer", "match_type": "contains"},
            {"phrase": "que haces", "match_type": "contains"},
            {"phrase": "qué haces", "match_type": "contains"},
            {"phrase": "que sabes", "match_type": "contains"},
            {"phrase": "qué sabes", "match_type": "contains"},
            {"phrase": "para que sirves", "match_type": "contains"},
            {"phrase": "para qué sirves", "match_type": "contains"},
            {"phrase": "que servicios", "match_type": "contains"},
            {"phrase": "qué servicios", "match_type": "contains"},
            {"phrase": "que ofreces", "match_type": "contains"},
            {"phrase": "qué ofreces", "match_type": "contains"},
            {"phrase": "en que me ayudas", "match_type": "contains"},
            {"phrase": "en qué me ayudas", "match_type": "contains"},
            {"phrase": "como funciona", "match_type": "contains"},
            {"phrase": "cómo funciona", "match_type": "contains"},
            {"phrase": "me puedes ayudar", "match_type": "contains"},
        ],
        "keywords": [
            "que puedes", "qué puedes", "puedes hacer", "que haces", "qué haces",
            "para que sirves", "para qué sirves", "que servicios", "qué servicios",
        ],
    },
    "debt_query": {
        "name": "Consulta de Deuda",
        "description": "Consultas sobre deuda, saldo pendiente o estado de cuenta",
        "weight": 1.0,
        "exact_match": False,
        "priority": 55,
        "lemmas": ["deuda", "deber", "saldo", "cuenta", "pendiente", "consultar", "estado"],
        "phrases": [
            {"phrase": "cuánto debo", "match_type": "contains"},
            {"phrase": "cuanto debo", "match_type": "contains"},
            {"phrase": "mi deuda", "match_type": "contains"},
            {"phrase": "mi saldo", "match_type": "contains"},
            {"phrase": "estado de cuenta", "match_type": "contains"},
        ],
        "keywords": ["deuda", "saldo", "debo", "cuenta", "pendiente"],
    },
    "confirm": {
        "name": "Confirmación",
        "description": "Confirmaciones positivas del usuario (sí, ok, dale, etc.)",
        "weight": 1.0,
        "exact_match": True,
        "priority": 95,
        "lemmas": ["confirmar", "aceptar", "acordar"],
        "phrases": [],
        "confirmation_patterns": [
            # Exact matches - high confidence
            {"pattern": "si", "pattern_type": "exact"},
            {"pattern": "sí", "pattern_type": "exact"},
            {"pattern": "s", "pattern_type": "exact"},
            {"pattern": "ok", "pattern_type": "exact"},
            {"pattern": "dale", "pattern_type": "exact"},
            {"pattern": "bueno", "pattern_type": "exact"},
            {"pattern": "listo", "pattern_type": "exact"},
            {"pattern": "claro", "pattern_type": "exact"},
            {"pattern": "perfecto", "pattern_type": "exact"},
            {"pattern": "bien", "pattern_type": "exact"},
            {"pattern": "yes", "pattern_type": "exact"},
            {"pattern": "1", "pattern_type": "exact"},
            # Contains matches - phrase detection
            {"pattern": "confirmo", "pattern_type": "contains"},
            {"pattern": "acepto", "pattern_type": "contains"},
            {"pattern": "de acuerdo", "pattern_type": "contains"},
            {"pattern": "correcto", "pattern_type": "contains"},
            {"pattern": "esta bien", "pattern_type": "contains"},
            {"pattern": "está bien", "pattern_type": "contains"},
        ],
        "keywords": [],
    },
    "reject": {
        "name": "Rechazo",
        "description": "Rechazos o cancelaciones del usuario (no, cancelar, etc.)",
        "weight": 1.0,
        "exact_match": True,
        "priority": 95,
        "lemmas": ["cancelar", "rechazar", "anular", "salir"],
        "phrases": [],
        "confirmation_patterns": [
            # Exact matches - high confidence
            {"pattern": "no", "pattern_type": "exact"},
            {"pattern": "n", "pattern_type": "exact"},
            {"pattern": "2", "pattern_type": "exact"},
            # Contains matches - phrase detection
            {"pattern": "cancelar", "pattern_type": "contains"},
            {"pattern": "rechazar", "pattern_type": "contains"},
            {"pattern": "incorrecto", "pattern_type": "contains"},
            {"pattern": "salir", "pattern_type": "contains"},
            {"pattern": "anular", "pattern_type": "contains"},
            {"pattern": "no quiero", "pattern_type": "contains"},
            {"pattern": "quiero cancelar", "pattern_type": "contains"},
            {"pattern": "no es correcto", "pattern_type": "contains"},
            {"pattern": "esta mal", "pattern_type": "contains"},
            {"pattern": "está mal", "pattern_type": "contains"},
        ],
        "keywords": [],
    },
    "invoice": {
        "name": "Factura/Pago",
        "description": "Solicitudes de generar factura, recibo o realizar pago",
        "weight": 1.0,
        "exact_match": False,
        "priority": 55,
        "lemmas": [
            "factura", "recibo", "comprobante", "pagar", "pago", "facturar", "abonar",
            "abono", "depositar", "pagae", "pagr", "pagra", "paga", "paagr", "pgar",
        ],
        "phrases": [
            {"phrase": "generar factura", "match_type": "contains"},
            {"phrase": "quiero pagar", "match_type": "contains"},
            {"phrase": "mi factura", "match_type": "contains"},
            {"phrase": "pagar mi deuda", "match_type": "contains"},
            {"phrase": "pagar la deuda", "match_type": "contains"},
            {"phrase": "hacer un pago", "match_type": "contains"},
            {"phrase": "realizar pago", "match_type": "contains"},
            {"phrase": "voy a pagar", "match_type": "contains"},
            {"phrase": "necesito pagar", "match_type": "contains"},
            {"phrase": "link de pago", "match_type": "contains"},
            {"phrase": "enlace de pago", "match_type": "contains"},
        ],
        "keywords": ["factura", "recibo", "comprobante", "pagar", "abonar", "depositar"],
    },
    "register": {
        "name": "Registro",
        "description": "Solicitud de registro como nuevo cliente",
        "weight": 0.9,
        "exact_match": False,
        "priority": 45,
        "lemmas": ["registrar", "inscribir", "nuevo"],
        "phrases": [
            {"phrase": "soy nuevo", "match_type": "contains"},
            {"phrase": "registrarme", "match_type": "contains"},
            {"phrase": "nuevo cliente", "match_type": "contains"},
            {"phrase": "crear cuenta", "match_type": "contains"},
        ],
        "keywords": [],
    },
    "greeting": {
        "name": "Saludo",
        "description": "Saludos iniciales (hola, buenos días, etc.)",
        "weight": 1.0,
        "exact_match": False,
        "priority": 60,
        "lemmas": ["hola", "saludar", "saludo", "buenas", "buenos"],
        "phrases": [
            {"phrase": "hola", "match_type": "exact"},
            {"phrase": "hey", "match_type": "exact"},
            {"phrase": "buenas", "match_type": "exact"},
            {"phrase": "buenos dias", "match_type": "exact"},
            {"phrase": "buenos días", "match_type": "exact"},
            {"phrase": "buenas tardes", "match_type": "exact"},
            {"phrase": "buenas noches", "match_type": "exact"},
            {"phrase": "hola ", "match_type": "prefix"},
            {"phrase": "buenas ", "match_type": "prefix"},
            {"phrase": "buenos ", "match_type": "prefix"},
        ],
        "keywords": ["hola", "buenos días", "buenas tardes", "buenas noches", "buenas"],
    },
    "summary": {
        "name": "Resumen",
        "description": "Solicitud de resumen o detalle de información",
        "weight": 0.9,
        "exact_match": False,
        "priority": 45,
        "lemmas": ["resumen", "resumir", "detalle", "detallar"],
        "phrases": [
            {"phrase": "resumen de", "match_type": "contains"},
            {"phrase": "detalle de", "match_type": "contains"},
            {"phrase": "dame un resumen", "match_type": "contains"},
        ],
        "keywords": [],
    },
    "data_query": {
        "name": "Consulta de Datos",
        "description": "Consultas sobre medicamentos, productos, compras y análisis de datos",
        "weight": 1.2,
        "exact_match": False,
        "priority": 50,
        "lemmas": [
            "medicamento", "producto", "consumir", "gastar", "comprar",
            "caro", "barato", "mayor", "menor", "más", "menos",
            "precio", "costo", "cantidad", "remedio",
        ],
        "phrases": [
            {"phrase": "que medicamento", "match_type": "contains"},
            {"phrase": "que producto", "match_type": "contains"},
            {"phrase": "mis medicamentos", "match_type": "contains"},
            {"phrase": "cuanto gaste", "match_type": "contains"},
            {"phrase": "cuánto gasté", "match_type": "contains"},
            {"phrase": "el más caro", "match_type": "contains"},
            {"phrase": "el mas caro", "match_type": "contains"},
            {"phrase": "mayor deuda", "match_type": "contains"},
            {"phrase": "cuanto cuesta", "match_type": "contains"},
            {"phrase": "cuánto cuesta", "match_type": "contains"},
            {"phrase": "precio de", "match_type": "contains"},
        ],
        "keywords": [
            "precio", "costo", "cuanto cuesta", "cuánto cuesta", "vale",
            "medicamento", "producto", "remedio", "más caro", "mas caro",
            "factura", "deuda total", "cuántos", "cuantos",
        ],
    },
    "info_query": {
        "name": "Consulta de Información",
        "description": "Consultas sobre dirección, teléfono, horario y datos de contacto",
        "weight": 1.3,
        "exact_match": False,
        "priority": 50,
        "lemmas": [
            "direccion", "ubicar", "ubicacion", "telefono", "horario",
            "hora", "abrir", "cerrar", "email", "correo", "web",
            "pagina", "canal", "informacion", "información", "contacto",
        ],
        "phrases": [
            {"phrase": "donde queda", "match_type": "contains"},
            {"phrase": "dónde queda", "match_type": "contains"},
            {"phrase": "donde esta", "match_type": "contains"},
            {"phrase": "dónde está", "match_type": "contains"},
            {"phrase": "la direccion", "match_type": "contains"},
            {"phrase": "la dirección", "match_type": "contains"},
            {"phrase": "a que hora abren", "match_type": "contains"},
            {"phrase": "a qué hora abren", "match_type": "contains"},
            {"phrase": "horario de atencion", "match_type": "contains"},
            {"phrase": "horario de atención", "match_type": "contains"},
            {"phrase": "el telefono", "match_type": "contains"},
            {"phrase": "el teléfono", "match_type": "contains"},
            {"phrase": "info de contacto", "match_type": "contains"},
            {"phrase": "información de contacto", "match_type": "contains"},
        ],
        "keywords": [
            "direccion", "dirección", "donde queda", "dónde queda",
            "horario", "hora", "abierto", "cierran", "abren",
            "telefono", "teléfono", "llamar", "email", "correo", "web",
        ],
    },
    "document_input": {
        "name": "Entrada de Documento",
        "description": "Usuario proporciona número de documento (DNI)",
        "weight": 1.5,
        "exact_match": False,
        "priority": 80,
        "lemmas": ["documento", "dni", "identidad", "cedula", "numero", "nro"],
        "phrases": [
            {"phrase": "mi documento", "match_type": "contains"},
            {"phrase": "mi dni", "match_type": "contains"},
            {"phrase": "numero de documento", "match_type": "contains"},
            {"phrase": "número de documento", "match_type": "contains"},
        ],
        "keywords": ["dni", "documento", "identidad", "cedula", "cédula"],
    },
}

# Register pharmacy domain
DOMAIN_SEED_DATA["pharmacy"] = PHARMACY_INTENTS


# =============================================================================
# EXCELENCIA DOMAIN SEED DATA (Future)
# =============================================================================

EXCELENCIA_INTENTS: dict[str, dict[str, Any]] = {
    "greeting": {
        "name": "Saludo",
        "description": "Saludos iniciales",
        "weight": 1.0,
        "exact_match": False,
        "priority": 60,
        "lemmas": ["hola", "saludar", "buenas", "buenos"],
        "phrases": [
            {"phrase": "hola", "match_type": "exact"},
            {"phrase": "buenos dias", "match_type": "exact"},
            {"phrase": "buenos días", "match_type": "exact"},
            {"phrase": "buenas tardes", "match_type": "exact"},
            {"phrase": "hola ", "match_type": "prefix"},
        ],
        "keywords": ["hola", "buenos días", "buenas tardes"],
    },
    "confirm": {
        "name": "Confirmación",
        "description": "Confirmaciones positivas",
        "weight": 1.0,
        "exact_match": True,
        "priority": 95,
        "lemmas": ["confirmar", "aceptar"],
        "phrases": [],
        "confirmation_patterns": [
            # Exact matches
            {"pattern": "si", "pattern_type": "exact"},
            {"pattern": "sí", "pattern_type": "exact"},
            {"pattern": "s", "pattern_type": "exact"},
            {"pattern": "ok", "pattern_type": "exact"},
            {"pattern": "dale", "pattern_type": "exact"},
            {"pattern": "bueno", "pattern_type": "exact"},
            {"pattern": "listo", "pattern_type": "exact"},
            {"pattern": "yes", "pattern_type": "exact"},
            {"pattern": "1", "pattern_type": "exact"},
            # Contains matches
            {"pattern": "confirmo", "pattern_type": "contains"},
            {"pattern": "de acuerdo", "pattern_type": "contains"},
        ],
        "keywords": [],
    },
    "reject": {
        "name": "Rechazo",
        "description": "Rechazos o cancelaciones",
        "weight": 1.0,
        "exact_match": True,
        "priority": 95,
        "lemmas": ["cancelar", "rechazar"],
        "phrases": [],
        "confirmation_patterns": [
            # Exact matches
            {"pattern": "no", "pattern_type": "exact"},
            {"pattern": "n", "pattern_type": "exact"},
            {"pattern": "2", "pattern_type": "exact"},
            # Contains matches
            {"pattern": "cancelar", "pattern_type": "contains"},
            {"pattern": "no quiero", "pattern_type": "contains"},
            {"pattern": "quiero cancelar", "pattern_type": "contains"},
        ],
        "keywords": [],
    },
    "module_query": {
        "name": "Consulta de Módulo",
        "description": "Preguntas sobre módulos de software de Excelencia",
        "weight": 1.2,
        "exact_match": False,
        "priority": 55,
        "lemmas": ["modulo", "módulo", "sistema", "funcionalidad", "caracteristica"],
        "phrases": [
            {"phrase": "como funciona", "match_type": "contains"},
            {"phrase": "cómo funciona", "match_type": "contains"},
            {"phrase": "que hace el modulo", "match_type": "contains"},
            {"phrase": "qué hace el módulo", "match_type": "contains"},
            {"phrase": "para que sirve", "match_type": "contains"},
            {"phrase": "para qué sirve", "match_type": "contains"},
        ],
        "keywords": ["módulo", "modulo", "sistema", "funcionalidad"],
    },
}

# Register excelencia domain
DOMAIN_SEED_DATA["excelencia"] = EXCELENCIA_INTENTS


# =============================================================================
# BACKWARD COMPATIBILITY
# =============================================================================

# Alias for backward compatibility with old seed script
INTENT_PATTERNS_SEED = PHARMACY_INTENTS
