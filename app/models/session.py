from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SessionData(BaseModel):
    """Modelo base para datos de sesión"""

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    data: Dict[str, Any] = Field(default_factory=dict)


class SessionItem(BaseModel):
    """Modelo para un elemento específico en la sesión"""

    key: str
    value: Any
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class UserSession(BaseModel):
    """Modelo para la sesión completa de un usuario"""

    user_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    items: Dict[str, SessionData] = Field(default_factory=dict)

    def get_item(self, key: str) -> Optional[Dict[str, Any]]:
        """Obtiene un elemento de la sesión por su clave"""
        if key in self.items:
            return self.items[key].data
        return None

    def set_item(self, key: str, data: Dict[str, Any]) -> None:
        """Establece un elemento en la sesión"""
        if key in self.items:
            # Actualizar existente
            self.items[key].data.update(data)
            self.items[key].updated_at = datetime.now()
        else:
            # Crear nuevo
            self.items[key] = SessionData(created_at=datetime.now(), updated_at=datetime.now(), data=data)
        self.updated_at = datetime.now()

    def delete_item(self, key: str) -> bool:
        """Elimina un elemento de la sesión"""
        if key in self.items:
            del self.items[key]
            self.updated_at = datetime.now()
            return True
        return False
