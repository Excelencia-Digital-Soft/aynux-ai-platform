"""
Pharmacy Intent Patterns

Constants, thresholds, and pattern definitions for pharmacy intent analysis.
"""

from __future__ import annotations

from typing import Any

# Confidence thresholds (single source of truth)
CONFIDENCE_THRESHOLD = 0.6  # LLM fallback threshold
CONFIDENCE_OUT_OF_SCOPE = 0.3
CONFIDENCE_MAX_SPACY = 0.95
CONFIDENCE_EXACT_MATCH = 0.95
CONFIDENCE_CONTAINS = 0.85

# Valid pharmacy intents
VALID_INTENTS = frozenset(
    {"debt_query", "confirm", "reject", "invoice", "register", "greeting", "summary", "data_query", "unknown"}
)

# Pharmacy domain capabilities
PHARMACY_CAPABILITIES = [
    "consultar deuda/saldo pendiente",
    "confirmar deuda para pago",
    "generar recibo/factura",
    "registrarse como cliente nuevo",
]

# Confirmation/rejection patterns (single source of truth)
CONFIRMATION_PATTERNS: dict[str, dict[str, set[str]]] = {
    "confirm": {
        "exact": {"si", "sí", "ok", "dale", "bueno", "listo", "claro", "perfecto", "bien"},
        "contains": {"confirmo", "acepto", "de acuerdo", "correcto", "afirmativo"},
    },
    "reject": {
        "exact": {"no"},
        "contains": {"cancelar", "rechazar", "incorrecto", "salir", "anular", "no quiero", "negar"},
    },
}

# Keyword patterns for fallback (when spaCy unavailable)
KEYWORD_PATTERNS: dict[str, list[str]] = {
    "debt_query": ["deuda", "saldo", "debo", "cuenta", "pendiente"],
    "invoice": ["factura", "recibo", "pagar", "pago", "comprobante"],
    "greeting": ["hola", "buenos días", "buenas tardes", "buenas noches", "buenas"],
}

# Greeting patterns for priority detection (exact match or prefix)
GREETING_EXACT: frozenset[str] = frozenset(
    {
        "hola",
        "hey",
        "buenas",
        "buenos dias",
        "buen dia",
        "buen día",
        "buenos días",
        "buenas tardes",
        "buenas noches",
        "saludos",
        "que tal",
        "qué tal",
        "como estas",
        "cómo estás",
        "hi",
        "hello",
    }
)
GREETING_PREFIXES: tuple[str, ...] = ("hola ", "buenas ", "buenos ", "hey ", "saludos ")

# Payment detection verbs and phrases
PAYMENT_VERBS: set[str] = {"pagar", "pago", "abonar", "abono", "depositar"}
PAYMENT_PHRASES: list[str] = [
    "quiero pagar",
    "voy a pagar",
    "necesito pagar",
    "hacer pago",
    "pagar mi deuda",
    "pagar la deuda",
    "pagar todo",
]

# Intent patterns for spaCy analysis
INTENT_PATTERNS: dict[str, dict[str, Any]] = {
    "debt_query": {
        "lemmas": {"deuda", "deber", "saldo", "cuenta", "pendiente", "consultar", "estado"},
        "phrases": ["cuánto debo", "cuanto debo", "mi deuda", "mi saldo", "estado de cuenta"],
        "weight": 1.0,
    },
    "confirm": {
        "lemmas": {"confirmar", "aceptar", "acordar"},
        "phrases": [],
        "weight": 1.0,
        "exact_match": True,
    },
    "reject": {
        "lemmas": {"cancelar", "rechazar", "anular", "salir"},
        "phrases": [],
        "weight": 1.0,
        "exact_match": True,
    },
    "invoice": {
        "lemmas": {"factura", "recibo", "comprobante", "pagar", "pago", "facturar", "abonar"},
        "phrases": [
            "generar factura",
            "quiero pagar",
            "mi factura",
            "generar recibo",
            "pagar mi deuda",
            "pagar la deuda",
            "pagar todo",
            "hacer un pago",
            "realizar pago",
            "abonar deuda",
        ],
        "weight": 1.0,
    },
    "register": {
        "lemmas": {"registrar", "inscribir", "nuevo"},
        "phrases": ["soy nuevo", "registrarme", "nuevo cliente", "crear cuenta"],
        "weight": 0.9,
    },
    "greeting": {
        "lemmas": {"hola", "saludar", "saludo", "buenas", "buenos"},
        "phrases": ["hola", "buenos días", "buenas tardes", "buenas noches", "buen día", "hey", "buenas"],
        "weight": 1.0,
    },
    "summary": {
        "lemmas": {"resumen", "resumir", "detalle", "detallar"},
        "phrases": ["resumen de", "detalle de", "dame un resumen"],
        "weight": 0.9,
    },
    "data_query": {
        "lemmas": {
            "medicamento",
            "producto",
            "consumir",
            "gastar",
            "comprar",
            "caro",
            "barato",
            "mayor",
            "menor",
            "más",
            "menos",
            "compra",
            "valor",
            "importe",
            "análisis",
        },
        "phrases": [
            "que medicamento",
            "cual medicamento",
            "cuál medicamento",
            "que producto",
            "cual producto",
            "cuál producto",
            "mis medicamentos",
            "mis productos",
            "cuanto gaste",
            "cuánto gasté",
            "que compre",
            "qué compré",
            "que he comprado",
            "que he gastado",
            "analizar mis",
            "el más caro",
            "el mas caro",
            "el más barato",
            "debo más",
            "debo mas",
            "mayor deuda",
            "mayor importe",
            "compras de mayor valor",
            "producto de mayor",
            "medicamento que más",
            "mayor valor",
            "cuantos productos",
            "cuántos productos",
            "cuantos medicamentos",
            "cuántos medicamentos",
        ],
        "weight": 1.2,  # Priority over debt_query when overlap
    },
}
