"""
Modelos de respuesta para items/productos de la API DUX
Responsabilidad: Definir estructuras de respuesta específicas para productos
"""

from typing import List

from .base import DuxBaseModel, DuxPaginationInfo
from .product import DuxItem


class DuxItemsResponse(DuxBaseModel):
    """Respuesta completa de la API de items DUX"""

    paging: DuxPaginationInfo
    results: List[DuxItem]

    def get_total_items(self) -> int:
        """Obtiene el total de items disponibles"""
        return self.paging.total

    def get_current_batch_size(self) -> int:
        """Obtiene el tamaño del lote actual"""
        return len(self.results)

    def has_more_pages(self) -> bool:
        """Verifica si hay más páginas disponibles"""
        return (self.paging.offset + self.paging.limit) < self.paging.total

    def get_next_offset(self) -> int:
        """Calcula el offset para la siguiente página"""
        return self.paging.offset + self.paging.limit

    def get_page_number(self) -> int:
        """Calcula el número de página actual (1-based)"""
        if self.paging.limit == 0:
            return 1
        return (self.paging.offset // self.paging.limit) + 1

    def get_total_pages(self) -> int:
        """Calcula el total de páginas disponibles"""
        if self.paging.limit == 0:
            return 0
        return (self.paging.total + self.paging.limit - 1) // self.paging.limit

    def find_item_by_code(self, cod_item: str) -> DuxItem | None:
        """Busca un item por su código"""
        for item in self.results:
            if item.cod_item == cod_item:
                return item
        return None

    def find_items_by_rubro(self, rubro_nombre: str) -> List[DuxItem]:
        """Obtiene items filtrados por rubro"""
        return [item for item in self.results if item.rubro.rubro.lower() == rubro_nombre.lower()]

    def find_items_by_marca(self, marca_nombre: str) -> List[DuxItem]:
        """Obtiene items filtrados por marca"""
        return [item for item in self.results if item.marca.marca.lower() == marca_nombre.lower()]

    def get_available_items(self) -> List[DuxItem]:
        """Obtiene solo los items disponibles (con stock y precio)"""
        return [item for item in self.results if item.is_available()]

    def get_items_with_barcode(self) -> List[DuxItem]:
        """Obtiene items que tienen código de barras"""
        return [item for item in self.results if item.has_barcode()]
