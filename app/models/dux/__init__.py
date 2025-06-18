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

# Respuestas
from .response import DuxItemsResponse, DuxRubrosResponse

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
    # Respuestas
    "DuxItemsResponse",
    "DuxRubrosResponse",
    # Sincronización
    "DuxSyncResult",
]

