"""
Constants for smart input interpretation.

Extensible mappings for priority, confirmation, and incident detection.
"""

# Priority direct mapping (expandable)
PRIORITY_DIRECT_MAP: dict[str, str] = {
    # Numbers
    "1": "critical",
    "2": "high",
    "3": "medium",
    "4": "low",
    # Spanish keywords - Critical
    "critico": "critical",
    "critica": "critical",
    "crítico": "critical",
    "crítica": "critical",
    "urgente": "critical",
    "urgentisimo": "critical",
    "urgentísimo": "critical",
    "emergencia": "critical",
    # Spanish keywords - High
    "alto": "high",
    "alta": "high",
    "importante": "high",
    "serio": "high",
    "seria": "high",
    # Spanish keywords - Medium
    "medio": "medium",
    "media": "medium",
    "normal": "medium",
    "moderado": "medium",
    "moderada": "medium",
    # Spanish keywords - Low
    "bajo": "low",
    "baja": "low",
    "menor": "low",
    "leve": "low",
    "minimo": "low",
    "mínimo": "low",
    # English keywords
    "critical": "critical",
    "urgent": "critical",
    "high": "high",
    "important": "high",
    "medium": "medium",
    "low": "low",
    "minor": "low",
}

# Priority display names
PRIORITY_DISPLAY: dict[str, str] = {
    "critical": "Critico",
    "high": "Alto",
    "medium": "Medio",
    "low": "Bajo",
}

# Confirmation patterns - YES
CONFIRMATION_YES: list[str] = [
    "si",
    "sí",
    "yes",
    "ok",
    "confirmar",
    "correcto",
    "bien",
    "adelante",
    "perfecto",
    "exacto",
    "afirmativo",
    "claro",
    "esta bien",
    "está bien",
    "de acuerdo",
    "listo",
    "dale",
    "confirmo",
    "procede",
    "hazlo",
    "crear",
    "registrar",
    "acepto",
    "aceptar",
    "eso es",
    "asi es",
    "así es",
]

# Confirmation patterns - NO
CONFIRMATION_NO: list[str] = [
    "no",
    "corregir",
    "cambiar",
    "editar",
    "modificar",
    "incorrecto",
    "mal",
    "error",
    "arreglar",
    "ajustar",
    "equivocado",
    "equivocada",
    "quiero cambiar",
    "esta mal",
    "está mal",
]

# Confirmation patterns - CANCEL
CONFIRMATION_CANCEL: list[str] = [
    "cancelar",
    "cancel",
    "salir",
    "exit",
    "descartar",
    "olvidalo",
    "olvídalo",
    "dejalo",
    "déjalo",
    "nada",
    "no quiero",
    "no gracias",
    "abortar",
    "terminar",
]

# Incident intent keywords (additional to query_types.yaml)
INCIDENT_INTENT_KEYWORDS: list[str] = [
    "reportar incidencia",
    "crear incidencia",
    "levantar ticket",
    "tengo un problema",
    "algo no funciona",
    "necesito reportar",
    "quiero reportar",
    "registrar incidencia",
    "abrir ticket",
    "bug",
    "falla",
    "error grave",
    "sistema caido",
    "sistema caído",
    "no funciona",
    "me esta fallando",
    "me está fallando",
    "hay un error",
    "me sale error",
    "se trabo",
    "se trabó",
    "esta trabado",
    "está trabado",
    "no me deja",
    "no puedo",
    "se congela",
    "se cuelga",
]

# Edit target keywords
EDIT_TARGET_DESCRIPTION: list[str] = [
    "descripcion",
    "descripción",
    "problema",
    "detalle",
    "detalles",
]

EDIT_TARGET_PRIORITY: list[str] = [
    "prioridad",
    "urgencia",
    "importancia",
]
