import logging
import re
from typing import Dict, Literal, Optional, Pattern, Set, TypedDict, cast

logger = logging.getLogger(__name__)

# Definir los tipos literales para países soportados
SupportedCountry = Literal["argentina", "mexico"]


# TypedDict para la estructura de patrones de país
class CountryPattern(TypedDict):
    country_code: str
    pattern: str
    mobile_prefix: str
    add_15_pattern: Optional[str]
    mobile_with_9: Pattern[str]
    mobile_without_9: Pattern[str]
    full_international: Pattern[str]


class PhoneNumberNormalizer:
    """
    Normalizador de números de teléfono para WhatsApp
    Especialmente diseñado para números argentinos
    """

    COUNTRY_PATTERNS = {
        # Argentina: Código de país 54, seguido opcionalmente de 9, luego área y número
        "argentina": {
            "country_code": "54",
            "pattern": r"^54(9)?(\d{2,4})(\d{6,10})$",
            "mobile_prefix": "9",
            "add_15_pattern": r"^549(\d{2})(\d{6,8})$",  # Para agregar 15 si falta
            "mobile_with_9": re.compile(r"^549(\d{2,4})(\d{6,8})$"),  # Formato: 5492XXXXXXXXX -> 542XX15XXXXXXX
            # Formato: 54XXXXXXXXXX -> verificar si ya tiene 15
            "mobile_without_9": re.compile(r"^54(\d{2,4})(\d{8,10})$"),
            # Formato internacional completo
            "full_international": re.compile(r"^\+?54(\d{2,4})(\d{6,10})$"),
        },
        # México: Se puede expandir según necesidades
        "mexico": {
            "country_code": "52",
            "pattern": r"^52(1)?(\d{2,3})(\d{7,8})$",
            "mobile_prefix": "1",
            "add_15_pattern": None,
            "mobile_with_9": re.compile(r"^521(\d{2,3})(\d{7,8})$"),
            "mobile_without_9": re.compile(r"^52(\d{2,3})(\d{7,8})$"),
            "full_international": re.compile(r"^\+?52(\d{2,3})(\d{7,8})$"),
        },
    }

    # Códigos de área argentinos más comunes
    ARGENTINA_AREA_CODES: Dict[str, str] = {
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
    }

    def __init__(self):
        self.test_numbers: Set[str] = set()  # Números de prueba autorizados
        self.load_test_numbers()

    def load_test_numbers(self):
        """Carga números de prueba conocidos"""
        # Agregar números que sabemos que funcionan en sandbox
        self.test_numbers.add("54264154472542")  # El número que funciona
        # Puedes agregar más números de prueba aquí

    def normalize_country_number(self, phone_number: str, country: SupportedCountry = "argentina") -> str:
        """
        Normaliza números argentinos para WhatsApp

        Args:
            phone_number: Número de teléfono original
            country: País del número

        Returns:
            Número normalizado en formato WhatsApp

        Raises:
            ValueError: Si el país no está soportado
        """
        # Limpiar el número de espacios y caracteres especiales
        clean_number = re.sub(r"[^\d]", "", phone_number)

        logger.debug(f"Normalizando número {country}: {phone_number} -> {clean_number}")

        # Obtener patrones del país específico
        patterns_raw = self.COUNTRY_PATTERNS.get(country.lower())
        if not patterns_raw:
            supported_countries = ", ".join(self.COUNTRY_PATTERNS.keys())
            raise ValueError(f"❗️País '{country}' no soportado. Países disponibles: {supported_countries}")

        # Cast to CountryPattern since we validated it exists
        patterns = cast(CountryPattern, patterns_raw)

        # Lógica específica para Argentina
        if country == "argentina":
            return self._normalize_argentina_number(clean_number, patterns)

        # Lógica específica para México
        elif country == "mexico":
            return self._normalize_mexico_number(clean_number, patterns)

    def _normalize_argentina_number(self, clean_number: str, patterns: CountryPattern) -> str:
        """Normaliza números argentinos específicamente"""
        # Patrón 1: 5492XXXXXXXXX (formato con 9)
        match = patterns["mobile_with_9"].match(clean_number)
        if match:
            area_code = match.group(1)
            local_number = match.group(2)

            # Transformar: 549 + AREA + NUMBER -> 54 + AREA + 15 + NUMBER
            normalized = f"54{area_code}15{local_number}"
            logger.info(f"Número transformado (patrón 9): {clean_number} -> {normalized}")
            return normalized

        # Patrón 2: 54XXXXXXXXXX (sin 9, verificar si ya tiene 15)
        match = patterns["mobile_without_9"].match(clean_number)
        if match:
            area_and_rest = match.group(1) + match.group(2)

            # Verificar si ya tiene 15 después del código de área
            for area_code in sorted(self.ARGENTINA_AREA_CODES.keys(), key=len, reverse=True):
                if area_and_rest.startswith(area_code):
                    remaining = area_and_rest[len(area_code) :]

                    # Si ya tiene 15, no modificar
                    if remaining.startswith("15"):
                        logger.info(f"Número ya normalizado: {clean_number}")
                        return clean_number

                    # Si no tiene 15, agregarlo
                    normalized = f"54{area_code}15{remaining}"
                    logger.info(f"Número transformado (sin 15): {clean_number} -> {normalized}")
                    return normalized

        return clean_number

    def _normalize_mexico_number(self, clean_number: str, patterns: CountryPattern) -> str:
        """Normaliza números mexicanos específicamente"""
        # Implementar lógica específica para México según necesidades
        # Por ahora, lógica básica
        if clean_number.startswith("52"):
            logger.info(f"Número mexicano detectado: {clean_number} patterns: {patterns}")
            return clean_number

        return clean_number

    def normalize_international_number(self, phone_number: str) -> str:
        """
        Normaliza números internacionales detectando automáticamente el país

        Args:
            phone_number: Número en cualquier formato

        Returns:
            Número normalizado
        """
        # Limpiar número
        clean_number = re.sub(r"[^\d]", "", phone_number.lstrip("+"))

        # Detectar país por código
        if clean_number.startswith("54"):
            return self.normalize_country_number(clean_number, "argentina")
        elif clean_number.startswith("52"):
            return self.normalize_country_number(clean_number, "mexico")

        # Para otros países, usar formato original
        logger.info(f"Número internacional no soportado: {phone_number}")
        return clean_number

    def is_test_number_compatible(self, phone_number: str) -> bool:
        """
        Verifica si un número es compatible con el modo de prueba
        """
        normalized = self.normalize_country_number(phone_number, "argentina")
        is_compatible = normalized in self.test_numbers

        logger.info(f"Verificación modo prueba: {phone_number} -> {normalized} -> Compatible: {is_compatible}")
        return is_compatible

    def get_normalized_number(self, phone_number: str, force_test_mode: bool = True) -> str:
        """
        Obtiene el número normalizado, con opción de forzar modo de prueba

        Args:
            phone_number: Número original
            force_test_mode: Si True, solo permite números de prueba

        Returns:
            Número normalizado listo para WhatsApp
        """
        normalized = self.normalize_international_number(phone_number)

        if force_test_mode:
            if not self.is_test_number_compatible(phone_number):
                logger.warning(f"Número {phone_number} no está en modo de prueba. Usando número de prueba por defecto.")
                # Retornar un número de prueba por defecto
                return list(self.test_numbers)[0]  # El primer número de prueba

        return normalized

    def add_test_number(self, phone_number: str):
        """Agrega un número a la lista de números de prueba"""
        normalized = self.normalize_country_number(phone_number, "argentina")
        self.test_numbers.add(normalized)
        logger.info(f"Número de prueba agregado: {normalized}")

    def format_for_display(self, phone_number: str) -> str:
        """
        Formatea un número para mostrar de forma amigable
        """
        clean_number = re.sub(r"[^\d]", "", phone_number)

        # Si es argentino
        if clean_number.startswith("54"):
            # Formato: +54 (área) 15 XXXX-XXXX
            for area_code in sorted(self.ARGENTINA_AREA_CODES.keys(), key=len, reverse=True):
                pattern = re.compile(r"^54{area_code}15(\d{{4}})(\d{{4}})$")
                match = re.match(pattern, clean_number)
                if match:
                    return f"+54 ({area_code}) 15 {match.group(1)}-{match.group(2)}"

        return f"+{clean_number}"


# Instancia global del normalizador
phone_normalizer = PhoneNumberNormalizer()


def normalize_whatsapp_number(phone_number: str, test_mode: bool = True) -> str:
    """
    Función de conveniencia para normalizar números de WhatsApp

    Args:
        phone_number: Número a normalizar
        test_mode: Si está en modo de prueba (sandbox)

    Returns:
        Número normalizado
    """
    return phone_normalizer.get_normalized_number(phone_number, force_test_mode=test_mode)


def add_test_number(phone_number: str):
    """Agrega un número a la lista de prueba"""
    phone_normalizer.add_test_number(phone_number)


def is_test_compatible(phone_number: str) -> bool:
    """Verifica si un número es compatible con modo de prueba"""
    return phone_normalizer.is_test_number_compatible(phone_number)
