"""
Modelo de producto DUX
Responsabilidad: Definir la estructura completa del producto con métodos de utilidad
"""

from decimal import Decimal
from typing import List, Optional

from pydantic import field_validator

from .base import DuxBaseModel
from .entities import DuxMarca, DuxProveedor, DuxRubro, DuxSubRubro
from .pricing import DuxPrecio, DuxStock


class DuxItem(DuxBaseModel):
    """Producto/Item de DUX"""

    cod_item: str
    item: str
    codigos_barra: Optional[List[str]] = None
    rubro: DuxRubro
    sub_rubro: DuxSubRubro
    marca: DuxMarca
    proveedor: DuxProveedor
    costo: str
    porc_iva: str
    precios: List[DuxPrecio]
    stock: List[DuxStock]
    habilitado: Optional[bool] = None
    codigo_externo: Optional[str] = None
    fecha_creacion: Optional[str] = None
    imagen_url: Optional[str] = None

    @field_validator("costo", "porc_iva")
    @classmethod
    def validate_numeric_strings(cls, v: str) -> str:
        """Valida y convierte valores numéricos a string decimal"""
        try:
            return str(Decimal(v))
        except Exception:
            return "0.0"

    @field_validator("fecha_creacion")
    @classmethod
    def validate_fecha_creacion(cls, v: Optional[str]) -> Optional[str]:
        """Valida formato de fecha"""
        if not v:
            return None
        return v

    def get_precio_lista_general(self) -> Optional[Decimal]:
        """Obtiene el precio de la lista general"""
        for precio in self.precios:
            if precio.nombre == "LISTA GENERAL":
                try:
                    return Decimal(precio.precio)
                except Exception:
                    return Decimal("0.0")
        return None

    def get_precio_por_lista(self, nombre_lista: str) -> Optional[Decimal]:
        """Obtiene el precio de una lista específica"""
        for precio in self.precios:
            if precio.nombre == nombre_lista:
                try:
                    return Decimal(precio.precio)
                except Exception:
                    return Decimal("0.0")
        return None

    def get_stock_local_disponible(self) -> Optional[Decimal]:
        """Obtiene el stock disponible del local"""
        for stock in self.stock:
            if stock.nombre == "LOCAL" and stock.stock_disponible:
                try:
                    return Decimal(stock.stock_disponible)
                except Exception:
                    return Decimal("0.0")
        return None

    def get_stock_por_ubicacion(self, nombre_ubicacion: str) -> Optional[Decimal]:
        """Obtiene el stock de una ubicación específica"""
        for stock in self.stock:
            if stock.nombre == nombre_ubicacion and stock.stock_disponible:
                try:
                    return Decimal(stock.stock_disponible)
                except Exception:
                    return Decimal("0.0")
        return None

    def get_stock_total(self) -> Decimal:
        """Calcula el stock total disponible en todas las ubicaciones"""
        total = Decimal("0.0")
        for stock in self.stock:
            if stock.stock_disponible:
                try:
                    total += Decimal(stock.stock_disponible)
                except Exception:
                    pass
        return total

    def has_barcode(self) -> bool:
        """Verifica si el producto tiene código de barras"""
        return bool(self.codigos_barra and len(self.codigos_barra) > 0)

    def is_available(self) -> bool:
        """Verifica si el producto está disponible (tiene stock y precio)"""
        has_stock = self.get_stock_total() > 0
        has_price = self.get_precio_lista_general() is not None and self.get_precio_lista_general() > 0  # type: ignore
        return has_stock and has_price

    def get_primary_barcode(self) -> Optional[str]:
        """Obtiene el código de barras principal"""
        if self.has_barcode():
            return self.codigos_barra[0]  # type: ignore
        return None

