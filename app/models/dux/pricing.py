"""
Modelos de precios y stock DUX
Responsabilidad: Definir estructuras de precios y stock con validaciones
"""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator


class DuxPrecio(BaseModel):
    """Precio de producto en DUX"""
    id: int = -1
    nombre: str = "Sin nombre"  
    precio: str = "0.0"

    @field_validator('id', mode='before')
    @classmethod
    def validate_id(cls, v: Optional[int]) -> int:
        """Valida el ID del precio, proporciona valor por defecto si es None"""
        return v if v is not None else -1

    @field_validator('nombre', mode='before')
    @classmethod
    def validate_nombre(cls, v: Optional[str]) -> str:
        """Valida el nombre del precio, proporciona valor por defecto si es None"""
        return v.strip() if v else "Sin nombre"

    @field_validator('precio', mode='before')
    @classmethod
    def validate_precio(cls, v: Optional[str]) -> str:
        """Convierte el precio a Decimal para manejo preciso"""
        if v is None:
            return "0.0"
        try:
            return str(Decimal(v))
        except:
            return "0.0"


class DuxStock(BaseModel):
    """Stock de producto en DUX"""
    id: int = -1
    nombre: str = "Sin ubicación"
    ctd_disponible: Optional[str] = None
    stock_real: Optional[str] = None
    stock_reservado: Optional[str] = None
    stock_disponible: Optional[str] = None
    id_det_item: Optional[int] = None
    talle: Optional[str] = None
    color: Optional[str] = None

    @field_validator('id', mode='before')
    @classmethod
    def validate_id(cls, v: Optional[int]) -> int:
        """Valida el ID del stock, proporciona valor por defecto si es None"""
        return v if v is not None else -1

    @field_validator('nombre', mode='before')
    @classmethod
    def validate_nombre(cls, v: Optional[str]) -> str:
        """Valida el nombre del stock, proporciona valor por defecto si es None"""
        return v.strip() if v else "Sin ubicación"

    @field_validator('ctd_disponible', 'stock_real', 'stock_reservado', 'stock_disponible', mode='before')
    @classmethod
    def validate_stock_numbers(cls, v: Optional[str]) -> Optional[str]:
        """Convierte valores de stock a Decimal, manejando None"""
        if v is None:
            return None
        try:
            return str(Decimal(v))
        except:
            return "0.0"