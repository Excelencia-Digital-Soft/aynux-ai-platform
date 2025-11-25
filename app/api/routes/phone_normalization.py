from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from app.core.shared.utils.phone_normalizer import (
    PhoneNumberRequest,
    PhoneNumberResponse,
    PydanticPhoneNumberNormalizer,
    SupportedCountry,
    pydantic_phone_normalizer,
)

router = APIRouter(tags=["phone-normalization"])


@router.post("/normalize", response_model=PhoneNumberResponse)
async def normalize_phone_number(
    request: PhoneNumberRequest,
    normalizer: PydanticPhoneNumberNormalizer = Depends(lambda: pydantic_phone_normalizer),  # noqa: B008
):
    """
    Normaliza un número de teléfono para WhatsApp

    - **phone_number**: Número a normalizar (requerido)
    - **country**: País del número (opcional, se detecta automáticamente)
    - **force_test_mode**: Forzar modo de prueba para sandbox

    Returns información completa del número normalizado
    """
    try:
        response = normalizer.normalize_phone_number(request)

        if not response.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Normalization failed",
                    "message": response.error_message,
                    "warnings": response.warnings,
                },
            )

        return response

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "Validation error", "details": e.errors()},
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Internal server error", "message": str(e)},
        ) from e


@router.post("/batch-normalize", response_model=List[PhoneNumberResponse])
async def normalize_batch_phone_numbers(
    requests: List[PhoneNumberRequest],
    normalizer: PydanticPhoneNumberNormalizer = Depends(lambda: pydantic_phone_normalizer),  # noqa: B008
):
    """
    Normaliza múltiples números de teléfono en lote

    Útil para procesar listas de contactos
    """
    if len(requests) > 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum 100 phone numbers per batch")

    responses = []
    for request in requests:
        try:
            response = normalizer.normalize_phone_number(request)
            responses.append(response)
        except Exception as e:
            # En lote, no falla todo si uno falla
            responses.append(
                PhoneNumberResponse(
                    success=False,
                    phone_info=None,
                    normalized_number=None,
                    error_message=f"Error processing {request.phone_number}: {str(e)}",
                )
            )

    return responses


@router.get("/validate/{phone_number}")
async def quick_validate(
    phone_number: str,
    country: SupportedCountry | None = None,
    test_mode: bool = True,
    normalizer: PydanticPhoneNumberNormalizer = Depends(lambda: pydantic_phone_normalizer),  # noqa: B008
):
    """
    Validación rápida de un número de teléfono (GET request)

    Útil para validaciones en tiempo real desde frontend
    """
    try:
        request = PhoneNumberRequest(phone_number=phone_number, country=country, force_test_mode=test_mode)

        response = normalizer.normalize_phone_number(request)

        # Respuesta simplificada para GET
        return {
            "valid": response.success,
            "normalized": response.normalized_number,
            "country": response.phone_info.country if response.phone_info else None,
            "is_mobile": response.phone_info.is_mobile if response.phone_info else False,
            "test_compatible": response.phone_info.is_test_compatible if response.phone_info else False,
            "errors": response.phone_info.validation_errors if response.phone_info else [],
        }

    except ValidationError as e:
        return {"valid": False, "errors": [error["msg"] for error in e.errors()]}


@router.post("/add-test-number")
async def add_test_number(
    phone_number: str, normalizer: PydanticPhoneNumberNormalizer = Depends(lambda: pydantic_phone_normalizer)  # noqa: B008
):
    """
    Agrega un número a la lista de números de prueba autorizados

    Útil para configurar el sandbox de WhatsApp
    """
    success = normalizer.add_test_number(phone_number)

    if success:
        return {"message": f"Test number {phone_number} added successfully"}
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to add test number")


@router.get("/supported-countries")
async def get_supported_countries():
    """
    Obtiene la lista de países soportados
    """
    return {
        "countries": PydanticPhoneNumberNormalizer.get_supported_countries(),
        "total": len(PydanticPhoneNumberNormalizer.get_supported_countries()),
    }


@router.get("/test-numbers")
async def get_test_numbers(normalizer: PydanticPhoneNumberNormalizer = Depends(lambda: pydantic_phone_normalizer)):  # noqa: B008
    """
    Obtiene la lista de números de prueba configurados
    """
    return {"test_numbers": list(normalizer.test_numbers), "total": len(normalizer.test_numbers)}
