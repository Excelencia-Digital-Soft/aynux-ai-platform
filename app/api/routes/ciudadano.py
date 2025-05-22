from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Path

from app.services.ciudadano_service import CiudadanoService

router = APIRouter(prefix="/contribuyentes", tags=["contribuyentes"])
ciudadano_service = CiudadanoService()


@router.get("/celular/{numero}", response_model=Dict[str, Any])
async def get_ciudadano_by_telefono(
    numero: str = Path(..., description="Número de teléfono del ciudadano"),
):
    """
    Obtiene la información de un ciudadano a partir de su número de teléfono
    """
    result = await ciudadano_service.get_info_ciudadano(numero)
    if not result.get("success", False):
        raise HTTPException(
            status_code=404, detail=result.get("message", "Ciudadano no encontrado")
        )
    return result


@router.get("/documento/{numero}", response_model=Dict[str, Any])
async def get_ciudadano_by_dni(
    numero: str = Path(..., description="Número de documento del ciudadano"),
):
    """
    Obtiene la información de un ciudadano a partir de su número de documento
    """
    result = await ciudadano_service.get_ciudadano_by_dni(numero)
    if not result.get("success", False):
        raise HTTPException(
            status_code=404, detail=result.get("message", "Ciudadano no encontrado")
        )
    return result


@router.post("/actualizar-celular", response_model=Dict[str, Any])
async def actualizar_celular(documento: str, telefono: str):
    """
    Actualiza el número de teléfono de un ciudadano
    """
    # Necesitamos implementar este método en el servicio
    # Por ahora lo simulamos con una actualización
    try:
        # Primero buscamos el ciudadano por DNI para obtener su ID
        info_ciudadano = await ciudadano_service.get_ciudadano_by_dni(documento)

        if not info_ciudadano.get("success", False):
            raise HTTPException(
                status_code=404, detail="Ciudadano no encontrado con ese documento"
            )

        # Extraemos el ID del ciudadano
        ciudadano_data = info_ciudadano.get("data", {})
        if isinstance(ciudadano_data, list) and ciudadano_data:
            ciudadano_data = ciudadano_data[0]

        id_ciudadano = ciudadano_data.get("id_ciudadano")  # type: ignore

        if not id_ciudadano:
            raise HTTPException(
                status_code=404, detail="No se pudo determinar el ID del ciudadano"
            )

        # Actualizamos los datos del ciudadano
        result = await ciudadano_service.actualizar_ciudadano(
            id_ciudadano, {"telefono": telefono}
        )

        if not result.get("success", False):
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "Error al actualizar el teléfono"),
            )

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
