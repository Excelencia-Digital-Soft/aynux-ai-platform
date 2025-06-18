"""
Modelos de factura DUX
Responsabilidad: Definir la estructura de facturas y sus componentes
"""

from decimal import Decimal
from typing import List, Optional

from pydantic import field_validator

from .base import DuxBaseModel


class DuxFacturaDetalle(DuxBaseModel):
    """Detalle de línea de factura"""

    id_detalle: Optional[int] = None
    cod_item: Optional[str] = None
    item: Optional[str] = None
    cantidad: Optional[str] = None
    precio_unitario: Optional[str] = None
    subtotal: Optional[str] = None
    descuento_porcentaje: Optional[str] = None
    descuento_importe: Optional[str] = None
    total_linea: Optional[str] = None

    @field_validator(
        "cantidad", "precio_unitario", "subtotal", "descuento_porcentaje", "descuento_importe", "total_linea"
    )
    @classmethod
    def validate_numeric_strings(cls, v: Optional[str]) -> Optional[str]:
        """Valida y convierte valores numéricos a string decimal"""
        if v is None:
            return None
        try:
            return str(Decimal(v))
        except Exception:
            return "0.0"

    def get_cantidad_decimal(self) -> Decimal:
        """Obtiene la cantidad como Decimal"""
        try:
            return Decimal(self.cantidad or "0")
        except Exception:
            return Decimal("0")

    def get_precio_unitario_decimal(self) -> Decimal:
        """Obtiene el precio unitario como Decimal"""
        try:
            return Decimal(self.precio_unitario or "0")
        except Exception:
            return Decimal("0")

    def get_total_linea_decimal(self) -> Decimal:
        """Obtiene el total de línea como Decimal"""
        try:
            return Decimal(self.total_linea or "0")
        except Exception:
            return Decimal("0")


class DuxFacturaCliente(DuxBaseModel):
    """Información del cliente en la factura"""

    id_cliente: Optional[int] = None
    codigo_cliente: Optional[str] = None
    razon_social: Optional[str] = None
    cuit: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None


class DuxFacturaTotales(DuxBaseModel):
    """Totales de la factura"""

    subtotal: Optional[str] = None
    descuento_total: Optional[str] = None
    recargo_total: Optional[str] = None
    iva_total: Optional[str] = None
    total_factura: Optional[str] = None

    @field_validator("subtotal", "descuento_total", "recargo_total", "iva_total", "total_factura")
    @classmethod
    def validate_numeric_strings(cls, v: Optional[str]) -> Optional[str]:
        """Valida y convierte valores numéricos a string decimal"""
        if v is None:
            return None
        try:
            return str(Decimal(v))
        except Exception:
            return "0.0"

    def get_total_factura_decimal(self) -> Decimal:
        """Obtiene el total de factura como Decimal"""
        try:
            return Decimal(self.total_factura or "0")
        except Exception:
            return Decimal("0")

    def get_iva_total_decimal(self) -> Decimal:
        """Obtiene el IVA total como Decimal"""
        try:
            return Decimal(self.iva_total or "0")
        except Exception:
            return Decimal("0")


class DuxFactura(DuxBaseModel):
    """Factura completa de DUX"""

    id_factura: Optional[int] = None
    numero_factura: Optional[str] = None
    tipo_factura: Optional[str] = None
    fecha_factura: Optional[str] = None
    fecha_vencimiento: Optional[str] = None
    estado: Optional[str] = None
    observaciones: Optional[str] = None
    cliente: Optional[DuxFacturaCliente] = None
    detalles: Optional[List[DuxFacturaDetalle]] = None
    totales: Optional[DuxFacturaTotales] = None

    @field_validator("fecha_factura", "fecha_vencimiento")
    @classmethod
    def validate_fecha(cls, v: Optional[str]) -> Optional[str]:
        """Valida formato de fecha"""
        if not v:
            return None
        return v

    def get_total_items(self) -> int:
        """Obtiene el total de items/líneas en la factura"""
        if not self.detalles:
            return 0
        return len(self.detalles)

    def get_total_factura(self) -> Decimal:
        """Obtiene el total de la factura"""
        if self.totales:
            return self.totales.get_total_factura_decimal()
        return Decimal("0")

    def is_paid(self) -> bool:
        """Verifica si la factura está pagada"""
        return self.estado and self.estado.upper() in ["PAGADA", "COBRADA", "PAID"]  # type: ignore

    def is_pending(self) -> bool:
        """Verifica si la factura está pendiente"""
        return self.estado and self.estado.upper() in ["PENDIENTE", "PENDING"]  # type: ignore

    def is_cancelled(self) -> bool:
        """Verifica si la factura está cancelada"""
        return self.estado and self.estado.upper() in ["CANCELADA", "ANULADA", "CANCELLED"]  # type: ignore

    def get_cliente_info(self) -> Optional[str]:
        """Obtiene información resumida del cliente"""
        if not self.cliente:
            return None
        return f"{self.cliente.razon_social or 'Sin nombre'} - {self.cliente.cuit or 'Sin CUIT'}"

    def calculate_total_from_details(self) -> Decimal:
        """Calcula el total basado en los detalles"""
        if not self.detalles:
            return Decimal("0")

        total = Decimal("0")
        for detalle in self.detalles:
            total += detalle.get_total_linea_decimal()
        return total

