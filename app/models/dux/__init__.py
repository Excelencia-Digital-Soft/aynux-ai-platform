"""
Modelos DUX - Estructuras de datos para la API DUX organizadas por responsabilidad
"""

# Base
from .base import DuxApiError, DuxBaseModel, DuxPaginationInfo

# Entidades
from .entities import DuxMarca, DuxProveedor, DuxRubro, DuxSubRubro

# Precios y Stock
from .pricing import DuxPrecio, DuxStock

# Producto
from .product import DuxItem

# Facturas
from .invoice import DuxFactura, DuxFacturaCliente, DuxFacturaDetalle, DuxFacturaTotales

# Respuestas
from .response_items import DuxItemsResponse
from .response_rubros import DuxRubrosResponse
from .response_facturas import DuxFacturasResponse

# Sincronización
from .sync import DuxSyncResult

__all__ = [
    # Base
    "DuxBaseModel",
    "DuxPaginationInfo",
    "DuxApiError",
    # Entidades
    "DuxRubro",
    "DuxSubRubro",
    "DuxMarca",
    "DuxProveedor",
    # Precios y Stock
    "DuxPrecio",
    "DuxStock",
    # Producto
    "DuxItem",
    # Facturas
    "DuxFactura",
    "DuxFacturaCliente",
    "DuxFacturaDetalle",
    "DuxFacturaTotales",
    # Respuestas
    "DuxItemsResponse",
    "DuxRubrosResponse",
    "DuxFacturasResponse",
    # Sincronización
    "DuxSyncResult",
]
