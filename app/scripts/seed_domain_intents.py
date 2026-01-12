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
        "lemmas": [
            "deuda", "deber", "saldo", "cuenta", "pendiente",
            "consultar", "estado", "ver", "mostrar", "revisar",
        ],
        "phrases": [
            {"phrase": "cuánto debo", "match_type": "contains"},
            {"phrase": "cuanto debo", "match_type": "contains"},
            {"phrase": "mi deuda", "match_type": "contains"},
            {"phrase": "mi saldo", "match_type": "contains"},
            {"phrase": "estado de cuenta", "match_type": "contains"},
            # Patterns with "ver" - common user expressions
            {"phrase": "ver deuda", "match_type": "contains"},
            {"phrase": "ver saldo", "match_type": "contains"},
            {"phrase": "ver mi deuda", "match_type": "contains"},
            {"phrase": "ver mi saldo", "match_type": "contains"},
            # Patterns with "consultar"
            {"phrase": "consultar deuda", "match_type": "contains"},
            {"phrase": "consultar saldo", "match_type": "contains"},
            {"phrase": "consultar mi deuda", "match_type": "contains"},
            # Patterns with "mostrar"
            {"phrase": "mostrar deuda", "match_type": "contains"},
            {"phrase": "mostrar saldo", "match_type": "contains"},
            # Patterns with "revisar"
            {"phrase": "revisar deuda", "match_type": "contains"},
            {"phrase": "revisar saldo", "match_type": "contains"},
            # Patterns with "quiero"
            {"phrase": "quiero ver mi deuda", "match_type": "contains"},
            {"phrase": "quiero saber mi deuda", "match_type": "contains"},
            {"phrase": "quiero saber cuanto debo", "match_type": "contains"},
            {"phrase": "quiero saber cuánto debo", "match_type": "contains"},
        ],
        "keywords": [
            "deuda", "saldo", "debo", "cuenta", "pendiente",
            "ver deuda", "ver saldo", "consultar deuda",
        ],
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
    # =========================================================================
    # WELCOME FLOW OPTIONS (Person Resolution)
    # Migrated from constants.py WELCOME_OPTIONS
    # =========================================================================
    "welcome_existing_client": {
        "name": "Opción Cliente Existente",
        "description": "Usuario indica que es cliente existente en menú de bienvenida",
        "weight": 1.0,
        "exact_match": False,
        "is_enabled": True,
        "priority": 100,
        "lemmas": [],
        "phrases": [],
        "confirmation_patterns": [
            {"pattern": "1", "pattern_type": "exact"},
            {"pattern": "1️⃣", "pattern_type": "exact"},
            {"pattern": "si", "pattern_type": "exact"},
            {"pattern": "sí", "pattern_type": "exact"},
            {"pattern": "cliente", "pattern_type": "exact"},
            {"pattern": "soy cliente", "pattern_type": "contains"},
            {"pattern": "verificar", "pattern_type": "exact"},
            {"pattern": "verificar identidad", "pattern_type": "contains"},
            {"pattern": "identidad", "pattern_type": "exact"},
            {"pattern": "dni", "pattern_type": "exact"},
            {"pattern": "tengo cuenta", "pattern_type": "contains"},
            {"pattern": "ya soy cliente", "pattern_type": "contains"},
            {"pattern": "existente", "pattern_type": "exact"},
        ],
        "keywords": [],
    },
    "welcome_new_client": {
        "name": "Opción Nuevo Cliente",
        "description": "Usuario indica que quiere registrarse como nuevo cliente",
        "weight": 1.0,
        "exact_match": False,
        "is_enabled": True,
        "priority": 100,
        "lemmas": [],
        "phrases": [],
        "confirmation_patterns": [
            {"pattern": "2", "pattern_type": "exact"},
            {"pattern": "2️⃣", "pattern_type": "exact"},
            {"pattern": "registrar", "pattern_type": "exact"},
            {"pattern": "registrarme", "pattern_type": "exact"},
            {"pattern": "nuevo", "pattern_type": "exact"},
            {"pattern": "no soy cliente", "pattern_type": "contains"},
            {"pattern": "quiero registrarme", "pattern_type": "contains"},
            {"pattern": "crear cuenta", "pattern_type": "contains"},
        ],
        "keywords": [],
    },
    "welcome_info_only": {
        "name": "Opción Solo Información",
        "description": "Usuario solo quiere información general sin identificarse",
        "weight": 1.0,
        "exact_match": False,
        "is_enabled": True,
        "priority": 100,
        "lemmas": [],
        "phrases": [],
        "confirmation_patterns": [
            {"pattern": "3", "pattern_type": "exact"},
            {"pattern": "3️⃣", "pattern_type": "exact"},
            {"pattern": "info", "pattern_type": "exact"},
            {"pattern": "información", "pattern_type": "exact"},
            {"pattern": "informacion", "pattern_type": "exact"},
            {"pattern": "solo info", "pattern_type": "contains"},
            {"pattern": "contactar", "pattern_type": "exact"},
            {"pattern": "contactar a la farmacia", "pattern_type": "contains"},
            {"pattern": "contactar farmacia", "pattern_type": "contains"},
            {"pattern": "horario", "pattern_type": "exact"},
            {"pattern": "horarios", "pattern_type": "exact"},
            {"pattern": "ubicación", "pattern_type": "exact"},
            {"pattern": "ubicacion", "pattern_type": "exact"},
            {"pattern": "dirección", "pattern_type": "exact"},
        ],
        "keywords": [],
    },
    "welcome_decline": {
        "name": "Rechazo de Opciones de Bienvenida",
        "description": "Usuario rechaza todas las opciones de bienvenida (no, ninguna, etc.)",
        "weight": 0.9,
        "exact_match": False,
        "is_enabled": True,
        "priority": 90,
        "lemmas": [],
        "phrases": [],
        "confirmation_patterns": [
            {"pattern": "no", "pattern_type": "exact"},
            {"pattern": "ninguna", "pattern_type": "exact"},
            {"pattern": "ninguno", "pattern_type": "exact"},
            {"pattern": "no gracias", "pattern_type": "exact"},
            {"pattern": "nada", "pattern_type": "exact"},
            {"pattern": "otra cosa", "pattern_type": "contains"},
            {"pattern": "nada de eso", "pattern_type": "contains"},
            {"pattern": "no me interesa", "pattern_type": "contains"},
        ],
        "keywords": [],
    },
    "verification_question": {
        "name": "Pregunta de Verificación",
        "description": "Usuario pregunta por qué se necesita verificación de identidad",
        "weight": 1.0,
        "exact_match": False,
        "is_enabled": True,
        "priority": 85,
        "lemmas": ["verificar", "identidad", "verificación", "validar"],
        "phrases": [
            {"phrase": "para qué", "match_type": "contains"},
            {"phrase": "para que", "match_type": "contains"},
            {"phrase": "por qué", "match_type": "contains"},
            {"phrase": "por que", "match_type": "contains"},
            {"phrase": "qué es", "match_type": "contains"},
            {"phrase": "que es", "match_type": "contains"},
            {"phrase": "cómo", "match_type": "contains"},
            {"phrase": "como", "match_type": "contains"},
            {"phrase": "qué significa", "match_type": "contains"},
            {"phrase": "que significa", "match_type": "contains"},
        ],
        "confirmation_patterns": [
            {"pattern": "?", "pattern_type": "contains"},
            {"pattern": "verificar", "pattern_type": "contains"},
            {"pattern": "identidad", "pattern_type": "contains"},
            {"pattern": "verificación", "pattern_type": "contains"},
            {"pattern": "verificacion", "pattern_type": "contains"},
            {"pattern": "validar", "pattern_type": "contains"},
        ],
        "keywords": ["verificar", "identidad", "verificación", "validar", "para qué"],
    },
    # =========================================================================
    # OWN/OTHER FLOW OPTIONS (Person Resolution)
    # Migrated from constants.py OWN_INDICATORS/OTHER_INDICATORS
    # =========================================================================
    "own_or_other_own": {
        "name": "Opción Deuda Propia",
        "description": "Usuario consulta su propia deuda (no de otra persona)",
        "weight": 1.0,
        "exact_match": False,
        "is_enabled": True,
        "priority": 100,
        "lemmas": [],
        "phrases": [],
        "confirmation_patterns": [
            {"pattern": "1", "pattern_type": "exact"},
            {"pattern": "mi deuda", "pattern_type": "contains"},
            {"pattern": "propia", "pattern_type": "exact"},
            {"pattern": "mia", "pattern_type": "exact"},
            {"pattern": "mía", "pattern_type": "exact"},
            {"pattern": "yo", "pattern_type": "exact"},
        ],
        "keywords": [],
    },
    "own_or_other_other": {
        "name": "Opción Deuda de Tercero",
        "description": "Usuario consulta deuda de otra persona (familiar, tercero)",
        "weight": 1.0,
        "exact_match": False,
        "is_enabled": True,
        "priority": 100,
        "lemmas": [],
        "phrases": [],
        "confirmation_patterns": [
            {"pattern": "2", "pattern_type": "exact"},
            {"pattern": "otra persona", "pattern_type": "contains"},
            {"pattern": "otro", "pattern_type": "exact"},
            {"pattern": "otra", "pattern_type": "exact"},
            {"pattern": "familiar", "pattern_type": "exact"},
            {"pattern": "tercero", "pattern_type": "exact"},
        ],
        "keywords": [],
    },
    # =========================================================================
    # DEBT MENU OPTIONS (Post-debt display menu - CASO 3)
    # Options shown after displaying debt: 1-Pagar total, 2-Pagar parcial,
    # 3-Ver detalle, 4-Volver al menú
    # =========================================================================
    "debt_menu_pay_total": {
        "name": "Debt Menu - Pagar Total",
        "description": "Usuario selecciona opción 1 para pagar deuda total",
        "weight": 1.0,
        "exact_match": True,
        "is_enabled": True,
        "priority": 90,
        "lemmas": [],
        "phrases": [],
        "confirmation_patterns": [
            # Exact matches (single words/numbers)
            {"pattern": "1", "pattern_type": "exact"},
            {"pattern": "1️⃣", "pattern_type": "exact"},
            {"pattern": "uno", "pattern_type": "exact"},
            {"pattern": "total", "pattern_type": "exact"},
            {"pattern": "pagar todo", "pattern_type": "exact"},
            {"pattern": "pagar total", "pattern_type": "exact"},
            # Contains matches (phrases)
            {"pattern": "pagar todo", "pattern_type": "contains"},
            {"pattern": "pagar el total", "pattern_type": "contains"},
            {"pattern": "pago total", "pattern_type": "contains"},
            {"pattern": "todo el monto", "pattern_type": "contains"},
            {"pattern": "monto total", "pattern_type": "contains"},
        ],
        "keywords": [],
    },
    "debt_menu_pay_partial": {
        "name": "Debt Menu - Pagar Parcial",
        "description": "Usuario selecciona opción 2 para pagar deuda parcial",
        "weight": 1.0,
        "exact_match": True,
        "is_enabled": True,
        "priority": 90,
        "lemmas": [],
        "phrases": [],
        "confirmation_patterns": [
            # Exact matches (single words/numbers)
            {"pattern": "2", "pattern_type": "exact"},
            {"pattern": "2️⃣", "pattern_type": "exact"},
            {"pattern": "dos", "pattern_type": "exact"},
            {"pattern": "parcial", "pattern_type": "exact"},
            {"pattern": "pagar parcial", "pattern_type": "exact"},
            {"pattern": "mitad", "pattern_type": "exact"},
            {"pattern": "medio", "pattern_type": "exact"},
            # Contains matches (phrases)
            {"pattern": "pago parcial", "pattern_type": "contains"},
            {"pattern": "pagar parte", "pattern_type": "contains"},
            {"pattern": "pagar una parte", "pattern_type": "contains"},
            {"pattern": "pagar la mitad", "pattern_type": "contains"},
        ],
        "keywords": [],
    },
    "debt_menu_view_details": {
        "name": "Debt Menu - Ver Detalle",
        "description": "Usuario selecciona opción 3 para ver detalle de facturas",
        "weight": 1.0,
        "exact_match": True,
        "is_enabled": True,
        "priority": 90,
        "lemmas": [],
        "phrases": [],
        "confirmation_patterns": [
            # Exact matches (single words/numbers)
            {"pattern": "3", "pattern_type": "exact"},
            {"pattern": "3️⃣", "pattern_type": "exact"},
            {"pattern": "tres", "pattern_type": "exact"},
            {"pattern": "detalle", "pattern_type": "exact"},
            {"pattern": "detalles", "pattern_type": "exact"},
            {"pattern": "facturas", "pattern_type": "exact"},
            {"pattern": "ver detalle", "pattern_type": "exact"},
            # Contains matches (phrases)
            {"pattern": "ver detalle", "pattern_type": "contains"},
            {"pattern": "ver detalles", "pattern_type": "contains"},
            {"pattern": "ver facturas", "pattern_type": "contains"},
            {"pattern": "ver comprobantes", "pattern_type": "contains"},
            {"pattern": "detalle de", "pattern_type": "contains"},
        ],
        "keywords": [],
    },
    "debt_menu_return": {
        "name": "Debt Menu - Volver al Menú",
        "description": "Usuario selecciona opción 4 para volver al menú principal",
        "weight": 1.0,
        "exact_match": True,
        "is_enabled": True,
        "priority": 90,
        "lemmas": [],
        "phrases": [],
        "confirmation_patterns": [
            # Exact matches (single words/numbers)
            {"pattern": "4", "pattern_type": "exact"},
            {"pattern": "4️⃣", "pattern_type": "exact"},
            {"pattern": "cuatro", "pattern_type": "exact"},
            {"pattern": "menu", "pattern_type": "exact"},
            {"pattern": "menú", "pattern_type": "exact"},
            {"pattern": "volver", "pattern_type": "exact"},
            {"pattern": "salir", "pattern_type": "exact"},
            {"pattern": "atras", "pattern_type": "exact"},
            {"pattern": "atrás", "pattern_type": "exact"},
            # Contains matches (phrases) - KEY FIX for "volver al menu"
            {"pattern": "volver al menu", "pattern_type": "contains"},
            {"pattern": "volver al menú", "pattern_type": "contains"},
            {"pattern": "ir al menu", "pattern_type": "contains"},
            {"pattern": "ir al menú", "pattern_type": "contains"},
            {"pattern": "volver atras", "pattern_type": "contains"},
            {"pattern": "volver atrás", "pattern_type": "contains"},
            {"pattern": "menu principal", "pattern_type": "contains"},
            {"pattern": "menú principal", "pattern_type": "contains"},
            {"pattern": "regresar", "pattern_type": "contains"},
            {"pattern": "al menu", "pattern_type": "contains"},
            {"pattern": "al menú", "pattern_type": "contains"},
        ],
        "keywords": [],
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
