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
VALID_INTENTS = frozenset({
    "debt_query", "confirm", "reject", "invoice", "register", "greeting",
    "summary", "data_query", "info_query", "unknown", "document_input",
})

# Pharmacy domain capabilities
PHARMACY_CAPABILITIES = [
    "consultar deuda/saldo pendiente",
    "confirmar deuda para pago",
    "generar recibo/factura",
    "registrarse como cliente nuevo",
    "consultar información de la farmacia (dirección, teléfono, horario)",
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
    "invoice": ["factura", "recibo", "comprobante"],  # Removed "pagar", "pago" - too ambiguous
    "greeting": ["hola", "buenos días", "buenas tardes", "buenas noches", "buenas"],
    "info_query": [
        "direccion", "dirección", "donde queda", "dónde queda", "ubicacion",
        "ubicación", "telefono", "teléfono", "horario", "hora", "abierto",
        "cierran", "abren", "email", "correo", "web", "pagina", "página",
        # Información de la farmacia
        "informacion de la farmacia", "información de la farmacia",
        "info de la farmacia", "datos de la farmacia", "contacto de la farmacia",
        # Canales de contacto
        "otros canales", "que canales", "canales", "otros medios",
        "otras formas", "como contactar", "contactarlos",
        # Preguntas sobre capacidades del bot (CRITICAL - high priority)
        "que puedes", "qué puedes", "puedes hacer", "que haces", "qué haces",
        "que sabes", "qué sabes", "para que sirves", "para qué sirves",
        "que mas puedes", "qué más puedes", "que servicios", "qué servicios",
        "como funciona", "cómo funciona", "que ofreces", "qué ofreces",
    ],
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

# Payment detection verbs and phrases (includes common typos)
PAYMENT_VERBS: set[str] = {
    "pagar", "pago", "abonar", "abono", "depositar",
    # Common typos for "pagar"
    "pagae", "pagr", "pagra", "paga", "paagr", "pgar",
    # Common typos for "abonar"
    "aboanr", "abonar", "abonr",
}
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
    "info_query": {
        "lemmas": {
            "direccion",
            "ubicar",
            "ubicacion",
            "telefono",
            "horario",
            "hora",
            "abrir",
            "cerrar",
            "email",
            "correo",
            "web",
            "pagina",
            "canal",
            "medio",
            "forma",
            # Capacidades del bot
            "servicio",
            "ofrecer",
            "funcionar",
            # Info de farmacia
            "informacion",
            "información",
            "contacto",
            "datos",
        },
        "phrases": [
            "donde queda",
            "dónde queda",
            "donde esta",
            "dónde está",
            "donde estan",
            "dónde están",
            "cual es la direccion",
            "cuál es la dirección",
            "a que hora abren",
            "a qué hora abren",
            "a que hora cierran",
            "a qué hora cierran",
            "estan abiertos",
            "están abiertos",
            "telefono de la farmacia",
            "teléfono de la farmacia",
            "horario de atencion",
            "horario de atención",
            "pagina web",
            "página web",
            "como los contacto",
            "cómo los contacto",
            # Solicitudes directas de información (CRITICAL)
            "la direccion",
            "la dirección",
            "el telefono",
            "el teléfono",
            "el horario",
            "los horarios",
            "necesito la direccion",
            "necesito la dirección",
            "necesito el telefono",
            "necesito el teléfono",
            "dame la direccion",
            "dame la dirección",
            "dame el telefono",
            "dame el teléfono",
            "quiero la direccion",
            "quiero la dirección",
            "direccion necesito",
            "dirección necesito",
            "direccion por favor",
            "dirección por favor",
            # Información de la farmacia (CRITICAL)
            "informacion de la farmacia",
            "información de la farmacia",
            "info de la farmacia",
            "datos de la farmacia",
            "contacto de la farmacia",
            "datos de contacto",
            "informacion de contacto",
            "información de contacto",
            # Canales de contacto
            "otros canales",
            "que canales",
            "canales de",
            "otros medios",
            "otras formas",
            "como contactar",
            "como comunicar",
            "formas de contacto",
            # Preguntas sobre capacidades del bot (CRITICAL - priority detection)
            "que puedes hacer",
            "qué puedes hacer",
            "que puedes",
            "qué puedes",
            "puedes hacer",
            "que haces",
            "qué haces",
            "que sabes hacer",
            "qué sabes hacer",
            "para que sirves",
            "para qué sirves",
            "que mas puedes",
            "qué más puedes",
            "que servicios",
            "qué servicios",
            "servicios ofreces",
            "como funciona",
            "cómo funciona",
            "que ofreces",
            "qué ofreces",
            "en que me ayudas",
            "en qué me ayudas",
            "como me ayudas",
            "cómo me ayudas",
        ],
        "weight": 1.3,  # Higher weight to beat invoice detection
    },
    "document_input": {
        "lemmas": {"documento", "dni", "identidad", "cedula", "numero", "nro"},
        "phrases": [
            "mi documento",
            "mi dni",
            "documento es",
            "dni es",
            "el documento",
            "mi numero",
            "numero de documento",
            "número de documento",
            "mi documento es",
            "mi dni es",
            "documento:",
            "dni:",
        ],
        "weight": 1.5,  # High priority when user provides document
    },
}
