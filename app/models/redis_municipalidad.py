from typing import Optional, Union

from pydantic import BaseModel


class AuthToken(BaseModel):
    token: str
    expires_at: Union[float, int]
    created_at: Union[float, int]
    id: Optional[str] = None
    nombre_usuario: Optional[str] = None
    nombre_completo: Optional[str] = None
    activo: Optional[bool] = None
