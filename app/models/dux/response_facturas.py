"""
Modelos de respuesta para facturas de la API DUX
Responsabilidad: Definir estructuras de respuesta específicas para facturas
"""

from typing import List, Optional
from decimal import Decimal

from .base import DuxBaseModel, DuxPaginationInfo
from .invoice import DuxFactura


class DuxFacturasResponse(DuxBaseModel):
    """Respuesta de la API de facturas"""

    facturas: List[DuxFactura]
    paging: Optional[DuxPaginationInfo] = None

    def get_total_facturas(self) -> int:
        """Obtiene el total de facturas"""
        if self.paging:
            return self.paging.total
        return len(self.facturas)

    def get_current_batch_size(self) -> int:
        """Obtiene el tamaño del lote actual"""
        return len(self.facturas)

    def has_more_pages(self) -> bool:
        """Verifica si hay más páginas disponibles"""
        if not self.paging:
            return False
        return (self.paging.offset + self.paging.limit) < self.paging.total

    def get_next_offset(self) -> Optional[int]:
        """Calcula el offset para la siguiente página"""
        if not self.has_more_pages() or not self.paging:
            return None
        return self.paging.offset + self.paging.limit

    def find_factura_by_id(self, id_factura: int) -> Optional[DuxFactura]:
        """Busca una factura por su ID"""
        for factura in self.facturas:
            if factura.id_factura == id_factura:
                return factura
        return None

    def find_factura_by_numero(self, numero_factura: str) -> Optional[DuxFactura]:
        """Busca una factura por su número"""
        for factura in self.facturas:
            if factura.numero_factura == numero_factura:
                return factura
        return None

    def get_facturas_by_estado(self, estado: str) -> List[DuxFactura]:
        """Obtiene facturas filtradas por estado"""
        estado_lower = estado.lower()
        return [f for f in self.facturas if f.estado and f.estado.lower() == estado_lower]

    def get_facturas_pendientes(self) -> List[DuxFactura]:
        """Obtiene facturas pendientes de pago"""
        return [f for f in self.facturas if f.is_pending()]

    def get_facturas_pagadas(self) -> List[DuxFactura]:
        """Obtiene facturas pagadas"""
        return [f for f in self.facturas if f.is_paid()]

    def get_facturas_canceladas(self) -> List[DuxFactura]:
        """Obtiene facturas canceladas"""
        return [f for f in self.facturas if f.is_cancelled()]

    def calculate_total_amount(self) -> Decimal:
        """Calcula el total de todas las facturas"""
        total = Decimal("0")
        for factura in self.facturas:
            total += factura.get_total_factura()
        return total

    def calculate_pending_amount(self) -> Decimal:
        """Calcula el total pendiente de cobro"""
        total = Decimal("0")
        for factura in self.get_facturas_pendientes():
            total += factura.get_total_factura()
        return total

    def get_facturas_by_cliente(self, cliente_id: int) -> List[DuxFactura]:
        """Obtiene facturas de un cliente específico"""
        return [
            f for f in self.facturas 
            if f.cliente and f.cliente.id_cliente == cliente_id
        ]

    def get_sorted_facturas(self, by_date: bool = True, ascending: bool = False) -> List[DuxFactura]:
        """Obtiene facturas ordenadas por fecha o número"""
        if by_date:
            return sorted(
                self.facturas, 
                key=lambda f: f.fecha_factura or "", 
                reverse=not ascending
            )
        return sorted(
            self.facturas, 
            key=lambda f: f.numero_factura or "", 
            reverse=not ascending
        )

    def get_facturas_by_date_range(self, fecha_desde: str, fecha_hasta: str) -> List[DuxFactura]:
        """Obtiene facturas dentro de un rango de fechas"""
        return [
            f for f in self.facturas 
            if f.fecha_factura and fecha_desde <= f.fecha_factura <= fecha_hasta
        ]

    def get_facturas_by_amount_range(self, min_amount: Decimal, max_amount: Decimal) -> List[DuxFactura]:
        """Obtiene facturas dentro de un rango de montos"""
        return [
            f for f in self.facturas 
            if min_amount <= f.get_total_factura() <= max_amount
        ]

    def get_top_facturas_by_amount(self, top_n: int = 10) -> List[DuxFactura]:
        """Obtiene las facturas con mayor monto"""
        return sorted(
            self.facturas, 
            key=lambda f: f.get_total_factura(), 
            reverse=True
        )[:top_n]

    def calculate_statistics(self) -> dict:
        """Calcula estadísticas básicas de las facturas"""
        if not self.facturas:
            return {
                "total_facturas": 0,
                "total_amount": Decimal("0"),
                "average_amount": Decimal("0"),
                "min_amount": Decimal("0"),
                "max_amount": Decimal("0"),
                "pending_count": 0,
                "paid_count": 0,
                "cancelled_count": 0
            }

        amounts = [f.get_total_factura() for f in self.facturas]
        
        return {
            "total_facturas": len(self.facturas),
            "total_amount": self.calculate_total_amount(),
            "average_amount": sum(amounts) / len(amounts) if amounts else Decimal("0"),
            "min_amount": min(amounts) if amounts else Decimal("0"),
            "max_amount": max(amounts) if amounts else Decimal("0"),
            "pending_count": len(self.get_facturas_pendientes()),
            "paid_count": len(self.get_facturas_pagadas()),
            "cancelled_count": len(self.get_facturas_canceladas())
        }