from typing import Any, Dict, Optional

from app.services.municipio_api_service import MunicipioAPIService


class CiudadanoService:
    """
    Servicio para gestionar ciudadanos del municipio
    """

    def __init__(self):
        self.api_service = MunicipioAPIService()

    async def get_info_ciudadano(self, celular: str) -> Dict[str, Any] | None:
        """
        Obtiene la información de un ciudadano por su número de teléfono

        Args:
            telefono: Número de teléfono del ciudadano

        Returns:
            Información del ciudadano
        """
        try:
            # Intentar buscar ciudadano por celular
            response = await self.api_service.get(f"contribuyentes/celular/{celular}")

            if response.get("esExitoso", False) and response.get("datos"):
                return response

            # Si no se encuentra, devolvemos un error
            return {
                "success": False,
                "message": "No se encontró un ciudadano con ese número de teléfono",
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Error al obtener información del ciudadano: {str(e)}",
            }

    async def get_ciudadano_by_dni(self, documento: str) -> Dict[str, Any] | None:
        """
        Obtiene la información de un ciudadano por su número de documento

        Args:
            documento: DNI del ciudadano

        Returns:
            Información del ciudadano
        """
        try:
            response = await self.api_service.get(
                "contribuyentes/documento", params={"documento": documento}
            )

            return response
        except Exception as e:
            return {
                "success": False,
                "message": f"Error al obtener información del ciudadano: {str(e)}",
            }

    async def registrar_ciudadano(
        self,
        nombre: str,
        apellido: str,
        documento: str,
        telefono: str,
        email: Optional[str] = None,
        direccion: Optional[str] = None,
    ) -> Dict[str, Any] | None:
        """
        Registra un nuevo ciudadano en el sistema

        Args:
            nombre: Nombre del ciudadano
            apellido: Apellido del ciudadano
            documento: Número de documento
            telefono: Número de teléfono
            email: Correo electrónico (opcional)
            direccion: Dirección (opcional)

        Returns:
            Resultado de la operación de registro
        """
        try:
            datos = {
                "nombre": nombre,
                "apellido": apellido,
                "documento": documento,
                "telefono": telefono,
            }

            if email:
                datos["email"] = email

            if direccion:
                datos["direccion"] = direccion

            response = await self.api_service.post("ciudadanos", datos)
            return response

        except Exception as e:
            return {
                "success": False,
                "message": f"Error al registrar ciudadano: {str(e)}",
            }

    async def actualizar_ciudadano(
        self, id_ciudadano: str, datos: Dict[str, Any]
    ) -> Dict[str, Any] | None:
        """
        Actualiza los datos de un ciudadano

        Args:
            id_ciudadano: ID del ciudadano
            datos: Datos a actualizar

        Returns:
            Resultado de la operación de actualización
        """
        try:
            # Para actualizar el teléfono específicamente
            if "telefono" in datos:
                telefono = datos["telefono"]
                response = await self.api_service.post(
                    "contribuyentes/actualizar-celular",
                    {"id_ciudadano": id_ciudadano, "telefono": telefono},
                )
                return response
            else:
                # Para otras actualizaciones generales
                response = await self.api_service.put(
                    f"contribuyentes/{id_ciudadano}", datos
                )
                return response
        except Exception as e:
            return {
                "success": False,
                "message": f"Error al actualizar ciudadano: {str(e)}",
            }
