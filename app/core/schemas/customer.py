from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class CustomerContext(BaseModel):
    """Contexto del cliente para personalización"""

    customer_id: str
    name: str
    email: Optional[str] = None
    phone: str
    tier: Literal["basic", "premium", "vip"] = "basic"
    purchase_history: List[Dict[str, Any]] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Obtiene una preferencia del cliente"""
        return self.preferences.get(key, default)

    def is_premium(self) -> bool:
        """Verifica si el cliente es premium o VIP"""
        return self.tier in ["premium", "vip"]

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para compatibilidad con TypedDict"""
        return {
            "customer_id": self.customer_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "tier": self.tier,
            "purchase_history": self.purchase_history,
            "preferences": self.preferences,
        }
