import logging
import re
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

logger = logging.getLogger(__name__)

# Definir los tipos literales para países soportados
SupportedCountry = Literal["argentina", "mexico"]

SUPPORTED_COUNTRIES: Tuple[SupportedCountry, ...] = ("argentina", "mexico")


class PhoneNumberInfo(BaseModel):
    """Información detallada de un número de teléfono"""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    raw_number: str = Field(..., description="Número original sin procesar")
    clean_number: str = Field(..., description="Número limpio (solo dígitos)")
    normalized_number: str = Field(..., description="Número normalizado para WhatsApp")
    country: SupportedCountry = Field(..., description="País detectado/especificado")
    country_code: str = Field(..., description="Código de país")
    area_code: Optional[str] = Field(None, description="Código de área")
    local_number: Optional[str] = Field(None, description="Número local")
    formatted_display: str = Field(..., description="Formato amigable para mostrar")
    is_mobile: bool = Field(False, description="Si es número móvil")
    is_valid: bool = Field(False, description="Si el número es válido")
    is_test_compatible: bool = Field(False, description="Si es compatible con modo prueba")
    validation_errors: List[str] = Field(default_factory=list, description="Errores de validación")


class PhoneNumberRequest(BaseModel):
    """Modelo para solicitudes de normalización de números"""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    phone_number: str = Field(
        ...,
        min_length=8,
        max_length=20,
        description="Número de teléfono a normalizar",
        examples=["5491123456789", "+54 9 11 2345-6789", "549112345678"],
    )
    country: Optional[SupportedCountry] = Field(
        None, description="País del número (se detecta automáticamente si no se especifica)"
    )
    force_test_mode: bool = Field(True, description="Forzar modo de prueba (sandbox)")

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Valida el formato básico del número de teléfono"""

        if not v or not v.strip():
            raise PydanticCustomError("phone_empty", "El número de teléfono no puede estar vacío", {})

        # Limpiar el número
        clean = re.sub(r"[^\d]", "", v.lstrip("+"))

        if len(clean) < 8:
            raise PydanticCustomError(
                "phone_too_short",
                "El número de teléfono es demasiado corto (mínimo 8 dígitos)",
                {"min_length": 8, "actual_length": len(clean)},
            )

        if len(clean) > 20:
            raise PydanticCustomError(
                "phone_too_long",
                "El número de teléfono es demasiado largo (máximo 20 dígitos)",
                {"max_length": 20, "actual_length": len(clean)},
            )

        # Validar que solo contenga dígitos después de limpiar
        if not re.match(r"^\d+$", clean):
            raise PydanticCustomError("phone_invalid_chars", "El número de teléfono contiene caracteres inválidos", {})

        return v

    @model_validator(mode="after")
    def validate_country_phone_compatibility(self) -> "PhoneNumberRequest":
        """Valida que el país sea compatible con el número"""
        if self.country:
            clean_number = re.sub(r"[^\d]", "", self.phone_number.lstrip("+"))

            # Verificar compatibilidad básica
            if self.country == "argentina" and not clean_number.startswith("54"):
                if not clean_number.startswith("9") and len(clean_number) < 12:
                    logger.warning(f"Número {clean_number} puede no ser argentino válido")

            elif self.country == "mexico" and not clean_number.startswith("52"):
                if len(clean_number) < 10:
                    logger.warning(f"Número {clean_number} puede no ser mexicano válido")

        return self


class PhoneNumberResponse(BaseModel):
    """Respuesta de normalización de números"""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    success: bool = Field(..., description="Si la normalización fue exitosa")
    phone_info: Optional[PhoneNumberInfo] = Field(None, description="Información del número")
    normalized_number: Optional[str] = Field(None, description="Número normalizado (acceso rápido)")
    error_message: Optional[str] = Field(None, description="Mensaje de error si falló")
    warnings: List[str] = Field(default_factory=list, description="Advertencias durante la normalización")


class PydanticPhoneNumberNormalizer(BaseModel):
    """
    Normalizador de números de teléfono con validación Pydantic
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True, extra="forbid")

    # Datos de configuración
    country_patterns: Dict[SupportedCountry, Dict[str, Any]] = Field(
        default_factory=lambda: {
            "argentina": {
                "country_code": "54",
                "mobile_prefix": "9",
                "area_codes": {
                    "11": "Buenos Aires",
                    "351": "Córdoba",
                    "3543": "Córdoba",
                    "388": "Jujuy",
                    "379": "Corrientes",
                    "221": "La Plata",
                    "380": "La Rioja",
                    "3885": "Jujuy Interior",
                    "220": "La Plata",
                    "261": "Mendoza",
                    "264": "San Juan",
                    "266": "San Luis",
                    "376": "Posadas",
                    "2804": "Rawson",
                    "362": "Resistencia",
                    "2966": "Río Gallegos",
                    "381": "Tucumán",
                    "387": "Salta",
                    "383": "Catamarca",
                    "299": "Neuquén",
                    "280": "Río Negro",
                    "297": "Santa Cruz",
                    "2901": "Tierra del Fuego",
                    "343": "Paraná",
                    "342": "Santa Fé",
                    "2954": "Santa Rosa",
                    "385": "Santiago del Estero",
                    "2920": "Viedma",
                },
                "patterns": {
                    "mobile_with_9": re.compile(r"^549(\d{2,4})(\d{6,8})$"),
                    "mobile_without_9": re.compile(r"^54(\d{2,4})(\d{6,10})$"),
                    "international": re.compile(r"^\+?54(\d{2,4})(\d{6,10})$"),
                },
            },
            "mexico": {
                "country_code": "52",
                "mobile_prefix": "1",
                "area_codes": {"55": "Ciudad de México", "33": "Guadalajara", "81": "Monterrey"},
                "patterns": {
                    "mobile_with_1": re.compile(r"^521(\d{2,3})(\d{7,8})$"),
                    "mobile_without_1": re.compile(r"^52(\d{2,3})(\d{7,8})$"),
                    "international": re.compile(r"^\+?52(\d{2,3})(\d{7,8})$"),
                },
            },
        }
    )

    test_numbers: Set[str] = Field(
        default_factory=lambda: {"54264154472542"}, description="Números de prueba autorizados"
    )

    def __init__(self, **data):
        super().__init__(**data)
        self._load_additional_test_numbers()

    def _load_additional_test_numbers(self) -> None:
        """Carga números de prueba adicionales si es necesario"""
        # Aquí puedes cargar desde base de datos, archivo, etc.
        pass

    def normalize_phone_number(self, request: PhoneNumberRequest) -> PhoneNumberResponse:
        """
        Normaliza un número de teléfono usando validación Pydantic

        Args:
            request: Solicitud de normalización validada por Pydantic

        Returns:
            Respuesta con información completa del número
        """
        try:
            # Limpiar número
            clean_number = re.sub(r"[^\d]", "", request.phone_number.lstrip("+"))

            # Detectar país si no se especificó
            detected_country = self._detect_country(clean_number, request.country)

            # Normalizar según el país
            phone_info = self._create_phone_info(
                raw_number=request.phone_number,
                clean_number=clean_number,
                country=detected_country,
            )

            # Realizar normalización
            normalized = self._normalize_by_country(phone_info)

            return PhoneNumberResponse(
                success=True,
                phone_info=normalized,
                normalized_number=normalized.normalized_number,
                warnings=normalized.validation_errors if normalized.validation_errors else [],
            )

        except Exception as e:
            logger.error(f"Error normalizando número {request.phone_number}: {e}")
            return PhoneNumberResponse(
                success=False, error_message=str(e), warnings=[f"Error durante la normalización: {str(e)}"]
            )

    def _detect_country(self, clean_number: str, specified_country: Optional[SupportedCountry]) -> SupportedCountry:
        """Detecta el país del número si no se especificó"""
        if specified_country:
            return specified_country

        # Detectar por código de país
        if clean_number.startswith("54"):
            return "argentina"
        elif clean_number.startswith("52"):
            return "mexico"

        # Default a Argentina si no se puede detectar
        logger.warning(f"No se pudo detectar país para {clean_number}, usando Argentina por defecto")
        return "argentina"

    def _create_phone_info(
        self,
        raw_number: str,
        clean_number: str,
        country: SupportedCountry,
    ) -> PhoneNumberInfo:
        """Crea la información base del número"""
        country_config = self.country_patterns[country]

        return PhoneNumberInfo(
            raw_number=raw_number,
            clean_number=clean_number,
            normalized_number=clean_number,  # Se actualizará después
            country=country,
            country_code=country_config["country_code"],
            formatted_display=f"+{clean_number}",  # Se mejorará después
            is_valid=False,  # Se actualizará después
            is_test_compatible=clean_number in self.test_numbers,
        )

    def _normalize_by_country(self, phone_info: PhoneNumberInfo) -> PhoneNumberInfo:
        """Normaliza el número según el país específico"""
        if phone_info.country == "argentina":
            return self._normalize_argentina(phone_info)
        elif phone_info.country == "mexico":
            return self._normalize_mexico(phone_info)
        else:
            phone_info.validation_errors.append(f"País {phone_info.country} no soportado")
            return phone_info

    def _normalize_argentina(self, phone_info: PhoneNumberInfo) -> PhoneNumberInfo:
        """Normalización específica para Argentina"""
        patterns = self.country_patterns["argentina"]["patterns"]
        area_codes = self.country_patterns["argentina"]["area_codes"]
        clean_number = phone_info.clean_number

        # Patrón 1: 5492XXXXXXXXX (formato con 9)
        match = patterns["mobile_with_9"].match(clean_number)
        if match:
            area_and_local = match.group(1) + match.group(2)
            
            # Buscar código de área válido
            area_code_found = None
            local_number = None
            
            for area_code in sorted(area_codes.keys(), key=len, reverse=True):
                if area_and_local.startswith(area_code):
                    area_code_found = area_code
                    local_number = area_and_local[len(area_code):]
                    break
            
            if area_code_found and local_number and len(local_number) >= 6:
                # Transformar: 549 + AREA + NUMBER -> 54 + AREA + 15 + NUMBER
                normalized = f"54{area_code_found}15{local_number}"
                phone_info.normalized_number = normalized
                phone_info.area_code = area_code_found
                phone_info.local_number = f"15{local_number}"
                phone_info.is_mobile = True
                phone_info.is_valid = True
                phone_info.formatted_display = f"+54 ({area_code_found}) 15 {local_number[:4]}-{local_number[4:]}"

                logger.info(f"Número argentino normalizado (con 9): {clean_number} -> {normalized}")
            else:
                phone_info.validation_errors.append(f"No se pudo identificar código de área válido en {area_and_local}")

        # Patrón 2: 54XXXXXXXXXX (sin 9, verificar si ya tiene 15)
        else:
            match = patterns["mobile_without_9"].match(clean_number)
            if match:
                area_and_rest = match.group(1) + match.group(2)

                # Buscar código de área válido
                for area_code in sorted(area_codes.keys(), key=len, reverse=True):
                    if area_and_rest.startswith(area_code):
                        remaining = area_and_rest[len(area_code) :]

                        # Si ya tiene 15, está normalizado
                        if remaining.startswith("15"):
                            phone_info.normalized_number = clean_number
                            phone_info.area_code = area_code
                            phone_info.local_number = remaining
                            phone_info.is_mobile = True
                            phone_info.is_valid = True
                            phone_info.formatted_display = (
                                f"+54 ({area_code}) {remaining[:2]} {remaining[2:6]}-{remaining[6:]}"
                            )
                            logger.info(f"Número argentino ya normalizado: {clean_number}")
                            break

                        # Si no tiene 15, agregarlo
                        else:
                            normalized = f"54{area_code}15{remaining}"
                            phone_info.normalized_number = normalized
                            phone_info.area_code = area_code
                            phone_info.local_number = f"15{remaining}"
                            phone_info.is_mobile = True
                            phone_info.is_valid = True
                            phone_info.formatted_display = f"+54 ({area_code}) 15 {remaining[:4]}-{remaining[4:]}"
                            logger.info(f"Número argentino normalizado (sin 15): {clean_number} -> {normalized}")
                            break
                else:
                    phone_info.validation_errors.append("No se pudo identificar código de área argentino válido")
            else:
                phone_info.validation_errors.append("Formato de número argentino no reconocido")

        return phone_info

    def _normalize_mexico(self, phone_info: PhoneNumberInfo) -> PhoneNumberInfo:
        """Normalización específica para México"""
        # Implementación básica para México
        # Puedes expandir según las reglas específicas mexicanas
        clean_number = phone_info.clean_number

        if clean_number.startswith("52"):
            phone_info.normalized_number = clean_number
            phone_info.is_valid = True
            phone_info.formatted_display = f"+{clean_number}"
            logger.info(f"Número mexicano procesado: {clean_number}")
        else:
            phone_info.validation_errors.append("Número mexicano debe comenzar con 52")

        return phone_info

    def add_test_number(self, phone_number: str) -> bool:
        """Agrega un número a la lista de prueba"""
        try:
            request = PhoneNumberRequest(phone_number=phone_number, force_test_mode=False)
            response = self.normalize_phone_number(request)

            if response.success and response.phone_info:
                self.test_numbers.add(response.phone_info.normalized_number)
                logger.info(f"Número de prueba agregado: {response.phone_info.normalized_number}")
                return True
            else:
                logger.error(f"No se pudo agregar número de prueba: {response.error_message}")
                return False

        except Exception as e:
            logger.error(f"Error agregando número de prueba: {e}")
            return False

    def validate_for_whatsapp(self, phone_number: str, test_mode: bool = True) -> PhoneNumberResponse:
        """Método de conveniencia para validar números para WhatsApp"""
        try:
            request = PhoneNumberRequest(phone_number=phone_number, force_test_mode=test_mode)
            return self.normalize_phone_number(request)
        except Exception as e:
            return PhoneNumberResponse(success=False, error_message=f"Error de validación: {str(e)}")

    @classmethod
    def get_supported_countries(cls) -> List[SupportedCountry]:
        """Retorna la lista de países soportados"""
        return list(SUPPORTED_COUNTRIES)


# Instancia global del normalizador con Pydantic
pydantic_phone_normalizer = PydanticPhoneNumberNormalizer()


# Funciones de conveniencia para mantener compatibilidad
def normalize_whatsapp_number_pydantic(phone_number: str, test_mode: bool = True) -> PhoneNumberResponse:
    """
    Función de conveniencia para normalizar números con Pydantic

    Args:
        phone_number: Número a normalizar
        test_mode: Si está en modo de prueba

    Returns:
        Respuesta completa con validación Pydantic
    """
    return pydantic_phone_normalizer.validate_for_whatsapp(phone_number, test_mode)


def get_normalized_number_only(phone_number: str, test_mode: bool = True) -> Optional[str]:
    """
    Obtiene solo el número normalizado (compatibilidad con versión anterior)

    Args:
        phone_number: Número a normalizar
        test_mode: Si está en modo de prueba

    Returns:
        Número normalizado o None si falla
    """
    response = normalize_whatsapp_number_pydantic(phone_number, test_mode)
    return response.normalized_number if response.success else None
