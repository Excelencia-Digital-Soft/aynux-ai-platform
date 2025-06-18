"""
Modelos de respuesta para rubros/categorías de la API DUX
Responsabilidad: Definir estructuras de respuesta específicas para rubros
"""

from typing import List, Optional

from .base import DuxBaseModel
from .entities import DuxRubro


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

    def search_rubros_by_pattern(self, pattern: str) -> List[DuxRubro]:
        """Busca rubros que contengan el patrón en su nombre"""
        pattern_lower = pattern.lower()
        return [
            rubro for rubro in self.rubros 
            if pattern_lower in rubro.rubro.lower()  # type: ignore
        ]

    def get_rubros_by_id_range(self, min_id: int, max_id: int) -> List[DuxRubro]:
        """Obtiene rubros dentro de un rango de IDs"""
        return [
            rubro for rubro in self.rubros 
            if min_id <= rubro.id_rubro <= max_id  # type: ignore
        ]