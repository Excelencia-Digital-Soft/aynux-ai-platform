"""Seed domain intents for System Organization.

Revision ID: ll1m2n3o4p5q
Revises: 34f3a657ec4e
Create Date: 2026-01-12

Seeds ALL pharmacy domain intent patterns for the System Organization
(00000000-0000-0000-0000-000000000000) used in production.

This migration complements 34f3a657ec4e which only seeded 4 debt_menu intents.
Now we seed all 21+ pharmacy intents with their ~423 patterns.

Uses ON CONFLICT DO UPDATE to update existing intents with their patterns.
"""

import json
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ll1m2n3o4p5q"
down_revision: Union[str, Sequence[str], None] = "34f3a657ec4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# System Organization UUID (used in production)
SYSTEM_ORG_ID = "00000000-0000-0000-0000-000000000000"
DOMAIN_KEY = "pharmacy"


def upgrade() -> None:
    """Seed domain intents for System Organization pharmacy domain."""
    intents = _get_pharmacy_intents()

    for intent_key, data in intents.items():
        # Escape single quotes for SQL
        name = data.get("name", intent_key).replace("'", "''")
        description = (data.get("description") or "").replace("'", "''")

        # Convert lists to JSON strings
        lemmas = json.dumps(data.get("lemmas", []))
        phrases = json.dumps(data.get("phrases", []))
        confirmation_patterns = json.dumps(data.get("confirmation_patterns", []))
        keywords = json.dumps(data.get("keywords", []))

        # Use ON CONFLICT DO UPDATE to update existing intents with patterns
        op.execute(f"""
            INSERT INTO core.domain_intents (
                organization_id, domain_key, intent_key,
                name, description, weight, exact_match, priority, is_enabled,
                lemmas, phrases, confirmation_patterns, keywords
            ) VALUES (
                '{SYSTEM_ORG_ID}',
                '{DOMAIN_KEY}',
                '{intent_key}',
                '{name}',
                '{description}',
                {data.get('weight', 1.0)},
                {str(data.get('exact_match', False)).lower()},
                {data.get('priority', 50)},
                {str(data.get('is_enabled', True)).lower()},
                '{lemmas}'::jsonb,
                '{phrases}'::jsonb,
                '{confirmation_patterns}'::jsonb,
                '{keywords}'::jsonb
            )
            ON CONFLICT (organization_id, domain_key, intent_key) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                weight = EXCLUDED.weight,
                exact_match = EXCLUDED.exact_match,
                priority = EXCLUDED.priority,
                is_enabled = EXCLUDED.is_enabled,
                lemmas = EXCLUDED.lemmas,
                phrases = EXCLUDED.phrases,
                confirmation_patterns = EXCLUDED.confirmation_patterns,
                keywords = EXCLUDED.keywords,
                updated_at = NOW()
        """)


def downgrade() -> None:
    """Remove domain intents for System Organization (except debt_menu intents)."""
    # Only remove intents that were added by this migration
    # Keep debt_menu_* intents as they were added by 34f3a657ec4e
    intents = _get_pharmacy_intents()
    intent_keys = [f"'{k}'" for k in intents.keys()]
    intent_list = ", ".join(intent_keys)

    op.execute(f"""
        DELETE FROM core.domain_intents
        WHERE organization_id = '{SYSTEM_ORG_ID}'
        AND domain_key = '{DOMAIN_KEY}'
        AND intent_key IN ({intent_list})
    """)


def _get_pharmacy_intents() -> dict:
    """
    Get pharmacy domain intent patterns.

    Duplicated from seed_domain_intents.py to make migration self-contained.
    """
    return {
        "capability_question": {
            "name": "Pregunta de Capacidades",
            "description": "Preguntas sobre que puede hacer el bot, sus funciones y servicios",
            "weight": 1.5,
            "exact_match": False,
            "priority": 75,
            "lemmas": ["poder", "hacer", "servir", "funcionar", "ayudar", "ofrecer", "servicio"],
            "phrases": [
                {"phrase": "que puedes hacer", "match_type": "contains"},
                {"phrase": "que puedes hacer", "match_type": "contains"},
                {"phrase": "que haces", "match_type": "contains"},
                {"phrase": "que haces", "match_type": "contains"},
                {"phrase": "que sabes", "match_type": "contains"},
                {"phrase": "que sabes", "match_type": "contains"},
                {"phrase": "para que sirves", "match_type": "contains"},
                {"phrase": "para que sirves", "match_type": "contains"},
                {"phrase": "que servicios", "match_type": "contains"},
                {"phrase": "que servicios", "match_type": "contains"},
                {"phrase": "que ofreces", "match_type": "contains"},
                {"phrase": "que ofreces", "match_type": "contains"},
                {"phrase": "en que me ayudas", "match_type": "contains"},
                {"phrase": "en que me ayudas", "match_type": "contains"},
                {"phrase": "como funciona", "match_type": "contains"},
                {"phrase": "como funciona", "match_type": "contains"},
                {"phrase": "me puedes ayudar", "match_type": "contains"},
            ],
            "keywords": [
                "que puedes", "que puedes", "puedes hacer", "que haces", "que haces",
                "para que sirves", "para que sirves", "que servicios", "que servicios",
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
                {"phrase": "cuanto debo", "match_type": "contains"},
                {"phrase": "cuanto debo", "match_type": "contains"},
                {"phrase": "mi deuda", "match_type": "contains"},
                {"phrase": "mi saldo", "match_type": "contains"},
                {"phrase": "estado de cuenta", "match_type": "contains"},
            ],
            "keywords": ["deuda", "saldo", "debo", "cuenta", "pendiente"],
        },
        "confirm": {
            "name": "Confirmacion",
            "description": "Confirmaciones positivas del usuario (si, ok, dale, etc.)",
            "weight": 1.0,
            "exact_match": True,
            "priority": 95,
            "lemmas": ["confirmar", "aceptar", "acordar"],
            "phrases": [],
            "confirmation_patterns": [
                {"pattern": "si", "pattern_type": "exact"},
                {"pattern": "si", "pattern_type": "exact"},
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
                {"pattern": "confirmo", "pattern_type": "contains"},
                {"pattern": "acepto", "pattern_type": "contains"},
                {"pattern": "de acuerdo", "pattern_type": "contains"},
                {"pattern": "correcto", "pattern_type": "contains"},
                {"pattern": "esta bien", "pattern_type": "contains"},
                {"pattern": "esta bien", "pattern_type": "contains"},
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
                {"pattern": "no", "pattern_type": "exact"},
                {"pattern": "n", "pattern_type": "exact"},
                {"pattern": "2", "pattern_type": "exact"},
                {"pattern": "cancelar", "pattern_type": "contains"},
                {"pattern": "rechazar", "pattern_type": "contains"},
                {"pattern": "incorrecto", "pattern_type": "contains"},
                {"pattern": "salir", "pattern_type": "contains"},
                {"pattern": "anular", "pattern_type": "contains"},
                {"pattern": "no quiero", "pattern_type": "contains"},
                {"pattern": "quiero cancelar", "pattern_type": "contains"},
                {"pattern": "no es correcto", "pattern_type": "contains"},
                {"pattern": "esta mal", "pattern_type": "contains"},
                {"pattern": "esta mal", "pattern_type": "contains"},
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
            "description": "Saludos iniciales (hola, buenos dias, etc.)",
            "weight": 1.0,
            "exact_match": False,
            "priority": 60,
            "lemmas": ["hola", "saludar", "saludo", "buenas", "buenos"],
            "phrases": [
                {"phrase": "hola", "match_type": "exact"},
                {"phrase": "hey", "match_type": "exact"},
                {"phrase": "buenas", "match_type": "exact"},
                {"phrase": "buenos dias", "match_type": "exact"},
                {"phrase": "buenos dias", "match_type": "exact"},
                {"phrase": "buenas tardes", "match_type": "exact"},
                {"phrase": "buenas noches", "match_type": "exact"},
                {"phrase": "hola ", "match_type": "prefix"},
                {"phrase": "buenas ", "match_type": "prefix"},
                {"phrase": "buenos ", "match_type": "prefix"},
            ],
            "keywords": ["hola", "buenos dias", "buenas tardes", "buenas noches", "buenas"],
        },
        "summary": {
            "name": "Resumen",
            "description": "Solicitud de resumen o detalle de informacion",
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
            "description": "Consultas sobre medicamentos, productos, compras y analisis de datos",
            "weight": 1.2,
            "exact_match": False,
            "priority": 50,
            "lemmas": [
                "medicamento", "producto", "consumir", "gastar", "comprar",
                "caro", "barato", "mayor", "menor", "mas", "menos",
                "precio", "costo", "cantidad", "remedio",
            ],
            "phrases": [
                {"phrase": "que medicamento", "match_type": "contains"},
                {"phrase": "que producto", "match_type": "contains"},
                {"phrase": "mis medicamentos", "match_type": "contains"},
                {"phrase": "cuanto gaste", "match_type": "contains"},
                {"phrase": "cuanto gaste", "match_type": "contains"},
                {"phrase": "el mas caro", "match_type": "contains"},
                {"phrase": "el mas caro", "match_type": "contains"},
                {"phrase": "mayor deuda", "match_type": "contains"},
                {"phrase": "cuanto cuesta", "match_type": "contains"},
                {"phrase": "cuanto cuesta", "match_type": "contains"},
                {"phrase": "precio de", "match_type": "contains"},
            ],
            "keywords": [
                "precio", "costo", "cuanto cuesta", "cuanto cuesta", "vale",
                "medicamento", "producto", "remedio", "mas caro", "mas caro",
                "factura", "deuda total", "cuantos", "cuantos",
            ],
        },
        "info_query": {
            "name": "Consulta de Informacion",
            "description": "Consultas sobre direccion, telefono, horario y datos de contacto",
            "weight": 1.3,
            "exact_match": False,
            "priority": 50,
            "lemmas": [
                "direccion", "ubicar", "ubicacion", "telefono", "horario",
                "hora", "abrir", "cerrar", "email", "correo", "web",
                "pagina", "canal", "informacion", "informacion", "contacto",
            ],
            "phrases": [
                {"phrase": "donde queda", "match_type": "contains"},
                {"phrase": "donde queda", "match_type": "contains"},
                {"phrase": "donde esta", "match_type": "contains"},
                {"phrase": "donde esta", "match_type": "contains"},
                {"phrase": "la direccion", "match_type": "contains"},
                {"phrase": "la direccion", "match_type": "contains"},
                {"phrase": "a que hora abren", "match_type": "contains"},
                {"phrase": "a que hora abren", "match_type": "contains"},
                {"phrase": "horario de atencion", "match_type": "contains"},
                {"phrase": "horario de atencion", "match_type": "contains"},
                {"phrase": "el telefono", "match_type": "contains"},
                {"phrase": "el telefono", "match_type": "contains"},
                {"phrase": "info de contacto", "match_type": "contains"},
                {"phrase": "informacion de contacto", "match_type": "contains"},
            ],
            "keywords": [
                "direccion", "direccion", "donde queda", "donde queda",
                "horario", "hora", "abierto", "cierran", "abren",
                "telefono", "telefono", "llamar", "email", "correo", "web",
            ],
        },
        "document_input": {
            "name": "Entrada de Documento",
            "description": "Usuario proporciona numero de documento (DNI)",
            "weight": 1.5,
            "exact_match": False,
            "priority": 80,
            "lemmas": ["documento", "dni", "identidad", "cedula", "numero", "nro"],
            "phrases": [
                {"phrase": "mi documento", "match_type": "contains"},
                {"phrase": "mi dni", "match_type": "contains"},
                {"phrase": "numero de documento", "match_type": "contains"},
                {"phrase": "numero de documento", "match_type": "contains"},
            ],
            "keywords": ["dni", "documento", "identidad", "cedula", "cedula"],
        },
        "welcome_existing_client": {
            "name": "Opcion Cliente Existente",
            "description": "Usuario indica que es cliente existente en menu de bienvenida",
            "weight": 1.0,
            "exact_match": False,
            "is_enabled": True,
            "priority": 100,
            "lemmas": [],
            "phrases": [],
            "confirmation_patterns": [
                {"pattern": "1", "pattern_type": "exact"},
                {"pattern": "1", "pattern_type": "exact"},
                {"pattern": "si", "pattern_type": "exact"},
                {"pattern": "si", "pattern_type": "exact"},
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
            "name": "Opcion Nuevo Cliente",
            "description": "Usuario indica que quiere registrarse como nuevo cliente",
            "weight": 1.0,
            "exact_match": False,
            "is_enabled": True,
            "priority": 100,
            "lemmas": [],
            "phrases": [],
            "confirmation_patterns": [
                {"pattern": "2", "pattern_type": "exact"},
                {"pattern": "2", "pattern_type": "exact"},
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
            "name": "Opcion Solo Informacion",
            "description": "Usuario solo quiere informacion general sin identificarse",
            "weight": 1.0,
            "exact_match": False,
            "is_enabled": True,
            "priority": 100,
            "lemmas": [],
            "phrases": [],
            "confirmation_patterns": [
                {"pattern": "3", "pattern_type": "exact"},
                {"pattern": "3", "pattern_type": "exact"},
                {"pattern": "info", "pattern_type": "exact"},
                {"pattern": "informacion", "pattern_type": "exact"},
                {"pattern": "informacion", "pattern_type": "exact"},
                {"pattern": "solo info", "pattern_type": "contains"},
                {"pattern": "contactar", "pattern_type": "exact"},
                {"pattern": "contactar a la farmacia", "pattern_type": "contains"},
                {"pattern": "contactar farmacia", "pattern_type": "contains"},
                {"pattern": "horario", "pattern_type": "exact"},
                {"pattern": "horarios", "pattern_type": "exact"},
                {"pattern": "ubicacion", "pattern_type": "exact"},
                {"pattern": "ubicacion", "pattern_type": "exact"},
                {"pattern": "direccion", "pattern_type": "exact"},
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
            "name": "Pregunta de Verificacion",
            "description": "Usuario pregunta por que se necesita verificacion de identidad",
            "weight": 1.0,
            "exact_match": False,
            "is_enabled": True,
            "priority": 85,
            "lemmas": ["verificar", "identidad", "verificacion", "validar"],
            "phrases": [
                {"phrase": "para que", "match_type": "contains"},
                {"phrase": "para que", "match_type": "contains"},
                {"phrase": "por que", "match_type": "contains"},
                {"phrase": "por que", "match_type": "contains"},
                {"phrase": "que es", "match_type": "contains"},
                {"phrase": "que es", "match_type": "contains"},
                {"phrase": "como", "match_type": "contains"},
                {"phrase": "como", "match_type": "contains"},
                {"phrase": "que significa", "match_type": "contains"},
                {"phrase": "que significa", "match_type": "contains"},
            ],
            "confirmation_patterns": [
                {"pattern": "?", "pattern_type": "contains"},
                {"pattern": "verificar", "pattern_type": "contains"},
                {"pattern": "identidad", "pattern_type": "contains"},
                {"pattern": "verificacion", "pattern_type": "contains"},
                {"pattern": "verificacion", "pattern_type": "contains"},
                {"pattern": "validar", "pattern_type": "contains"},
            ],
            "keywords": ["verificar", "identidad", "verificacion", "validar", "para que"],
        },
        "own_or_other_own": {
            "name": "Opcion Deuda Propia",
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
                {"pattern": "mia", "pattern_type": "exact"},
                {"pattern": "yo", "pattern_type": "exact"},
            ],
            "keywords": [],
        },
        "own_or_other_other": {
            "name": "Opcion Deuda de Tercero",
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
    }
