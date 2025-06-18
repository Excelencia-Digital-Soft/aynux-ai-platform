"""
Modelos de respuesta de la API DUX
Responsabilidad: Definir estructuras de respuesta y resultados
"""

from typing import List, Optional

from .base import DuxBaseModel, DuxPaginationInfo
from .entities import DuxRubro
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


class DuxRubrosResponse(DuxBaseModel):
    """Respuesta de la API de rubros (categorías)"""

    rubros: List[DuxRubro]

    def get_total_rubros(self) -> int:
        """Obtiene el total de rubros"""
        return len(self.rubros)

    def find_rubro_by_id(self, id_rubro: int) -> Optional[DuxRubro]:
        """Busca un rubro por su ID"""
        for rubro in self.rubros:
            if rubro.id_rubro == id_rubro:  # type: ignore
                return rubro
        return None

    def find_rubro_by_name(self, nombre: str) -> Optional[DuxRubro]:
        """Busca un rubro por su nombre (case insensitive)"""
        nombre_lower = nombre.lower()
        for rubro in self.rubros:
            if rubro.rubro.lower() == nombre_lower:  # type: ignore
                return rubro
        return None

    def get_rubro_names(self) -> List[str]:
        """Obtiene una lista con todos los nombres de rubros"""
        return [rubro.rubro for rubro in self.rubros]  # type: ignore

    def get_sorted_rubros(self, by_name: bool = True) -> List[DuxRubro]:
        """Obtiene rubros ordenados por nombre o ID"""
        if by_name:
            return sorted(self.rubros, key=lambda r: r.rubro)  # type: ignore
        return sorted(self.rubros, key=lambda r: r.id_rubro)  # type: ignore

