"""
Modelos de precios y stock DUX
Responsabilidad: Definir estructuras de precios y stock con validaciones
"""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator


class DuxPrecio(BaseModel):
    """Precio de producto en DUX"""
    id: int
    nombre: str
    precio: str

    @field_validator('precio')
    @classmethod
    def validate_precio(cls, v: str) -> str:
        """Convierte el precio a Decimal para manejo preciso"""
        try:
            return str(Decimal(v))
        except:
            return "0.0"


class DuxStock(BaseModel):
    """Stock de producto en DUX"""
    id: int
    nombre: str
    ctd_disponible: Optional[str] = None
    stock_real: Optional[str] = None
    stock_reservado: Optional[str] = None
    stock_disponible: Optional[str] = None
    id_det_item: Optional[int] = None
    talle: Optional[str] = None
    color: Optional[str] = None

    @field_validator('ctd_disponible', 'stock_real', 'stock_reservado', 'stock_disponible')
    @classmethod
    def validate_stock_numbers(cls, v: Optional[str]) -> Optional[str]:
        """Convierte valores de stock a Decimal, manejando None"""
        if v is None:
            return None
        try:
            return str(Decimal(v))
        except:
            return "0.0"