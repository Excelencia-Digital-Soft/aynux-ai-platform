from enum import Enum
from typing import Literal

from pydantic import BaseModel


class UserIntent(str, Enum):
    SALUDO_Y_NECESIDADES_INICIALES = "SALUDO_Y_NECESIDADES_INICIALES"
    CONSULTA_PRODUCTO_SERVICIO = "CONSULTA_PRODUCTO_SERVICIO"
    VERIFICACION_STOCK = "VERIFICACION_STOCK"
    PROMOCIONES_DESCUENTOS = "PROMOCIONES_DESCUENTOS"
    SUGERENCIAS_RECOMENDACIONES = "SUGERENCIAS_RECOMENDACIONES"
    MANEJO_DUDAS_OBJECIONES = "MANEJO_DUDAS_OBJECIONES"
    CIERRE_VENTA_PROCESO = "CIERRE_VENTA_PROCESO"
    NO_RELACIONADO_O_CONFUSO = "NO_RELACIONADO_O_CONFUSO"


class ChatbotResponse(BaseModel):
    """Modelo para respuestas del chatbot"""

    intent: str = "desconocido"
    confidence: float = 0.0
    mensaje: str
    estado: Literal["inicio", "clasificado", "procesando", "completado", "sin_clasificar", "error"] = "inicio"
