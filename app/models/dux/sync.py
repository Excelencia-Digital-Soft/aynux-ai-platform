"""
Modelos de sincronización DUX
Responsabilidad: Definir estructuras para el proceso de sincronización
"""

from datetime import datetime
from typing import List, Optional

from pydantic import Field

from .base import DuxBaseModel


class DuxSyncResult(DuxBaseModel):
    """Resultado de sincronización con DUX"""

    total_processed: int = 0
    total_created: int = 0
    total_updated: int = 0
    total_errors: int = 0
    errors: List[str] = Field(default_factory=list)
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    def mark_completed(self):
        """Marca la sincronización como completada"""
        self.end_time = datetime.now()
        if self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()

    def add_error(self, error: str):
        """Agrega un error al resultado"""
        self.errors.append(error)
        self.total_errors += 1

    def get_success_rate(self) -> float:
        """Calcula la tasa de éxito"""
        if self.total_processed == 0:
            return 0.0
        return ((self.total_processed - self.total_errors) / self.total_processed) * 100

    def is_successful(self) -> bool:
        """Verifica si la sincronización fue exitosa"""
        return self.total_errors == 0 and self.total_processed > 0

    @property
    def success(self) -> bool:
        """Property alias for is_successful() for compatibility"""
        return self.is_successful()

    def get_summary(self) -> str:
        """Genera un resumen de la sincronización"""
        return (
            f"Procesados: {self.total_processed}, "
            f"Creados: {self.total_created}, "
            f"Actualizados: {self.total_updated}, "
            f"Errores: {self.total_errors}, "
            f"Tasa de éxito: {self.get_success_rate():.1f}%"
        )
