from typing import Any, Dict, List, Optional

from app.services.municipio_api_service import MunicipioAPIService


class ReclamosService:
    """
    Servicio para gestionar reclamos municipales
    """

    def __init__(self):
        self.api_service = MunicipioAPIService()

    async def get_tipos_reclamo(self) -> Optional[Dict[str, Any]]:
        """
        Obtiene los tipos de reclamos disponibles

        Returns:
            Lista de tipos de reclamos
        """
        return await self.api_service.get("reclamos/tipos")

    async def crear_reclamo(
        self,
        id_ciudadano: str,
        tipo_reclamo: str,
        descripcion: str,
        ubicacion: Optional[Dict[str, float]] = None,
        imagenes: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Crea un nuevo reclamo en el sistema

        Args:
            id_ciudadano: ID del ciudadano que realiza el reclamo
            tipo_reclamo: Tipo de reclamo (ej: "alumbrado", "basura")
            descripcion: Descripción detallada del reclamo
            ubicacion: Coordenadas de la ubicación (opcional)
            imagenes: Lista de URLs de imágenes (opcional)

        Returns:
            Resultado de la creación del reclamo
        """
        payload = {
            "id_ciudadano": id_ciudadano,
            "tipo_reclamo": tipo_reclamo,
            "descripcion": descripcion,
            "ubicacion": None,
            "imagenes": None,
        }

        if ubicacion:
            payload["ubicacion"] = ubicacion

        if imagenes:
            payload["imagenes"] = imagenes

        return await self.api_service.post("reclamos", payload)

    async def get_reclamos_ciudadano(
        self, id_ciudadano: str
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene los reclamos realizados por un ciudadano

        Args:
            id_ciudadano: ID del ciudadano

        Returns:
            Lista de reclamos del ciudadano
        """
        return await self.api_service.get(f"ciudadanos/{id_ciudadano}/reclamos")

    async def get_estado_reclamo(self, id_reclamo: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene el estado actual de un reclamo

        Args:
            id_reclamo: ID del reclamo

        Returns:
            Estado actual del reclamo
        """
        return await self.api_service.get(f"reclamos/{id_reclamo}")
