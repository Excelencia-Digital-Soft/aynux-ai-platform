"""
Modelos base para la API DUX
Responsabilidad: Definir clases base y tipos compartidos
"""

from datetime import datetime

from pydantic import BaseModel


class DuxBaseModel(BaseModel):
    """Modelo base para todos los modelos DUX"""

    class Config:
        """Configuración base para modelos DUX"""

        validate_assignment = True
        use_enum_values = True
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


class DuxPaginationInfo(BaseModel):
    """Información de paginación de la respuesta DUX"""

    total: int
    offset: int
    limit: int


class DuxApiError(Exception):
    """Error de la API DUX"""

    def __init__(self, error_code: str, error_message: str):
        self.error_code = error_code
        self.error_message = error_message
        self.timestamp = datetime.now()
        super().__init__(f"[{error_code}] {error_message}")

