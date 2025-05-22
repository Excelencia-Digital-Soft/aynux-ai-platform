from typing import Any, Dict

from app.services.municipio_api_service import MunicipioAPIService


class TramitesService:
    """
    Servicio para gestionar trámites municipales
    """

    def __init__(self):
        self.api_service = MunicipioAPIService()

    async def get_tramites_disponibles(self) -> Dict[str, Any]:
        """
        Obtiene la lista de trámites disponibles en el municipio

        Returns:
            Diccionario con información de trámites disponibles
        """
        return await self.api_service.get("tramites")  # type: ignore

    async def iniciar_tramite(
        self, tipo_tramite: str, datos_ciudadano: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Inicia un nuevo trámite en el sistema municipal

        Args:
            tipo_tramite: Tipo de trámite a iniciar
            datos_ciudadano: Datos del ciudadano que inicia el trámite

        Returns:
            Resultado de la operación de inicio de trámite
        """
        payload = {"tipo_tramite": tipo_tramite, "ciudadano": datos_ciudadano}
        return await self.api_service.post("tramites", payload)  # type: ignore

    async def consultar_estado_tramite(self, id_tramite: str) -> Dict[str, Any]:
        """
        Consulta el estado de un trámite

        Args:
            id_tramite: Identificador del trámite

        Returns:
            Estado actual del trámite
        """
        return await self.api_service.get(f"tramites/{id_tramite}")  # type: ignore

    async def obtener_deuda_contribuyente(
        self, id_contribuyente: str
    ) -> Dict[str, Any]:
        """
        Obtiene la deuda actual de un contribuyente

        Args:
            id_contribuyente: Identificador del contribuyente

        Returns:
            Información sobre la deuda del contribuyente
        """
        return await self.api_service.get(f"contribuyentes/{id_contribuyente}/deuda")  # type: ignore

    async def generar_comprobante_pago(self, id_deuda: str) -> Dict[str, Any]:
        """
        Genera un comprobante de pago para una deuda específica

        Args:
            id_deuda: Identificador de la deuda

        Returns:
            Información del comprobante generado
        """
        return await self.api_service.post(
            "pagos/generar_comprobante", {"id_deuda": id_deuda}
        )  # type: ignore

    async def verificar_ciudadano(self, documento: str) -> Dict[str, Any]:
        """
        Verifica la existencia de un ciudadano en el sistema

        Args:
            documento: Número de documento del ciudadano

        Returns:
            Información del ciudadano si existe
        """
        result = await self.api_service.get_contribuyentes(documento=documento, limit=1)

        if result.get("success", False) and result.get("data", []):
            return {"success": True, "data": result["data"][0]}

        return {"success": False, "message": "Ciudadano no encontrado"}
