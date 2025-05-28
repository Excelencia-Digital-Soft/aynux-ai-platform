from typing import Literal

from pydantic import BaseModel


class ChatbotResponse(BaseModel):
    """Modelo para respuestas del chatbot"""

    mensaje: str
    estado: Literal[
        "inicio",
        "verificar",
        "verificado",
        "tramites",
        "reclamos",
        "turnos",
        "certificados",
    ] = "inicio"
