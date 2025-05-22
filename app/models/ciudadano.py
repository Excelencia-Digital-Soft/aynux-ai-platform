from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field
from pydantic.functional_serializers import PlainSerializer

# Definir un tipo personalizado para datetime con serialización
DateTimeIso = Annotated[
    datetime,
    PlainSerializer(
        lambda dt: dt.isoformat() if dt else None, return_type=str, when_used="json"
    ),
]


class Ciudadano(BaseModel):
    """Modelo para ciudadanos del municipio"""

    id_ciudadano: str
    nombre: str
    apellido: str
    documento: str
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None


class UserState(BaseModel):
    """Modelo para el estado del usuario en la conversación"""

    state: Literal[
        "inicio",
        "verificar",
        "verificado",
        "tramites",
        "consulta_deuda",
        "reclamos",
        "turnos",
        "certificados",
    ] = "inicio"
    verificado: bool = False
    id_ciudadano: Optional[str] = None
    last_interaction: DateTimeIso = Field(default_factory=datetime.now)


class User(BaseModel):
    """Modelo para usuarios"""

    phone_number: str
    state: UserState = Field(default_factory=UserState)
    ciudadano: Optional[Ciudadano] = None


class ChatbotResponse(BaseModel):
    """Modelo para respuestas del chatbot"""

    mensaje: str
    estado: Literal[
        "inicio",
        "verificar",
        "verificado",
        "tramites",
        "consulta_deuda",
        "reclamos",
        "turnos",
        "certificados",
    ] = "inicio"
