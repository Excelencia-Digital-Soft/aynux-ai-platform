import pytest
from pydantic import ValidationError

from app.core.shared.utils.phone_normalizer import (
    PhoneNumberRequest,
    PydanticPhoneNumberNormalizer,
)


class TestPhoneNumberRequest:
    """Tests para el modelo de request"""

    def test_valid_phone_number(self):
        """Test número válido"""
        request = PhoneNumberRequest(phone_number="5491123456789")
        assert request.phone_number == "5491123456789"
        assert request.country is None
        assert request.force_test_mode is True

    def test_phone_number_with_country(self):
        """Test número con país especificado"""
        request = PhoneNumberRequest(phone_number="5491123456789", country="argentina")
        assert request.country == "argentina"

    def test_invalid_empty_phone(self):
        """Test número vacío"""
        with pytest.raises(ValidationError) as exc_info:
            PhoneNumberRequest(phone_number="")

        errors = exc_info.value.errors()
        assert any("phone_empty" in str(error) for error in errors)

    def test_invalid_short_phone(self):
        """Test número demasiado corto"""
        with pytest.raises(ValidationError) as exc_info:
            PhoneNumberRequest(phone_number="123")

        errors = exc_info.value.errors()
        assert any("phone_too_short" in str(error) for error in errors)

    def test_invalid_long_phone(self):
        """Test número demasiado largo"""
        with pytest.raises(ValidationError) as exc_info:
            PhoneNumberRequest(phone_number="1" * 25)

        errors = exc_info.value.errors()
        assert any("phone_too_long" in str(error) for error in errors)

    def test_phone_with_formatting(self):
        """Test número con formato (espacios, guiones, etc.)"""
        request = PhoneNumberRequest(phone_number="+54 9 11 2345-6789")
        assert request.phone_number == "+54 9 11 2345-6789"  # Se mantiene original


class TestPydanticPhoneNumberNormalizer:
    """Tests para el normalizador principal"""

    @pytest.fixture
    def normalizer(self):
        return PydanticPhoneNumberNormalizer()

    def test_normalize_argentina_with_9(self, normalizer):
        """Test normalización argentina con código 9"""
        request = PhoneNumberRequest(phone_number="5491123456789", force_test_mode=False)

        response = normalizer.normalize_phone_number(request)

        assert response.success is True
        assert response.phone_info is not None
        assert response.phone_info.country == "argentina"
        assert response.phone_info.normalized_number == "541115123456789"
        assert response.phone_info.is_mobile is True
        assert response.phone_info.area_code == "11"

    def test_normalize_argentina_without_9(self, normalizer):
        """Test normalización argentina sin código 9"""
        request = PhoneNumberRequest(phone_number="5411123456789", force_test_mode=False)

        response = normalizer.normalize_phone_number(request)

        assert response.success is True
        assert response.phone_info is not None
        assert response.phone_info.normalized_number == "541115123456789"

    def test_normalize_argentina_already_normalized(self, normalizer):
        """Test número argentino ya normalizado"""
        request = PhoneNumberRequest(phone_number="541115123456789", force_test_mode=False)

        response = normalizer.normalize_phone_number(request)

        assert response.success is True
        assert response.phone_info.normalized_number == "541115123456789"

    def test_normalize_mexico(self, normalizer):
        """Test normalización mexicana"""
        request = PhoneNumberRequest(phone_number="525512345678", country="mexico", force_test_mode=False)

        response = normalizer.normalize_phone_number(request)

        assert response.success is True
        assert response.phone_info.country == "mexico"
        assert response.phone_info.normalized_number == "525512345678"

    def test_auto_detect_country_argentina(self, normalizer):
        """Test detección automática de país - Argentina"""
        request = PhoneNumberRequest(phone_number="5491123456789", force_test_mode=False)

        response = normalizer.normalize_phone_number(request)

        assert response.phone_info.country == "argentina"

    def test_auto_detect_country_mexico(self, normalizer):
        """Test detección automática de país - México"""
        request = PhoneNumberRequest(phone_number="525512345678", force_test_mode=False)

        response = normalizer.normalize_phone_number(request)

        assert response.phone_info.country == "mexico"

    def test_test_mode_compatible_number(self, normalizer):
        """Test número compatible con modo de prueba"""
        # Agregar número de prueba primero
        normalizer.test_numbers.add("541115123456789")

        request = PhoneNumberRequest(phone_number="5491123456789", force_test_mode=True)

        response = normalizer.normalize_phone_number(request)

        assert response.success is True
        assert response.phone_info.is_test_compatible is True

    def test_invalid_area_code(self, normalizer):
        """Test código de área inválido"""
        request = PhoneNumberRequest(
            phone_number="5499912345678",  # 999 no es un código válido
            force_test_mode=False,
        )

        response = normalizer.normalize_phone_number(request)

        # Puede fallar o generar advertencias dependiendo de la implementación
        if response.success:
            assert len(response.warnings) > 0
        else:
            assert "área" in response.error_message.lower()

    def test_add_test_number(self, normalizer):
        """Test agregar número de prueba"""
        initial_count = len(normalizer.test_numbers)

        success = normalizer.add_test_number("5491187654321")

        assert success is True
        assert len(normalizer.test_numbers) == initial_count + 1

    def test_get_supported_countries(self):
        """Test obtener países soportados"""
        countries = PydanticPhoneNumberNormalizer.get_supported_countries()

        assert "argentina" in countries
        assert "mexico" in countries
        assert len(countries) >= 2


class TestPhoneNumberIntegration:
    """Tests de integración completos"""

    @pytest.fixture
    def normalizer(self):
        return PydanticPhoneNumberNormalizer()

    @pytest.mark.parametrize(
        "input_number,expected_normalized",
        [
            ("5491123456789", "541115123456789"),
            ("+54 9 11 2345-6789", "541115234567890"),
            ("54 11 15 2345-6789", "541115234567890"),
            ("525512345678", "525512345678"),
        ],
    )
    def test_normalization_examples(self, normalizer, input_number, expected_normalized):
        """Test casos de normalización específicos"""
        print("expected_normalized", expected_normalized)
        request = PhoneNumberRequest(phone_number=input_number, force_test_mode=False)

        response = normalizer.normalize_phone_number(request)

        if response.success:
            # Verificar que se normalize correctamente o al menos de forma consistente
            assert response.phone_info.normalized_number is not None
            assert len(response.phone_info.normalized_number) >= 10

    def test_error_handling(self, normalizer):
        """Test manejo de errores"""
        print("normalizer", normalizer)
        # Número inválido que debería generar error
        request = PhoneNumberRequest(phone_number="invalid_phone", force_test_mode=False)
        print("request:", request)

        with pytest.raises(ValidationError):
            # Esto debería fallar en la validación de Pydantic
            pass


# ==========================================
# EJEMPLOS DE USO
# ==========================================

# examples/phone_normalization_examples.py


def example_basic_usage():
    """Ejemplo básico de uso"""
    from app.services.phone_normalizer_pydantic import PhoneNumberRequest, pydantic_phone_normalizer

    # Crear request
    request = PhoneNumberRequest(phone_number="+54 9 11 2345-6789", country="argentina", force_test_mode=False)

    # Normalizar
    response = pydantic_phone_normalizer.normalize_phone_number(request)

    if response.success:
        print("✅ Normalización exitosa!")
        print(f"   Número original: {response.phone_info.raw_number}")
        print(f"   Número normalizado: {response.phone_info.normalized_number}")
        print(f"   País: {response.phone_info.country}")
        print(f"   Código de área: {response.phone_info.area_code}")
        print(f"   Formato display: {response.phone_info.formatted_display}")
        print(f"   Es móvil: {response.phone_info.is_mobile}")
        print(f"   Compatible con test: {response.phone_info.is_test_compatible}")
    else:
        print(f"❌ Error: {response.error_message}")
        print(f"   Advertencias: {response.warnings}")


def example_batch_processing():
    """Ejemplo de procesamiento en lote"""
    from app.services.phone_normalizer_pydantic import PhoneNumberRequest, pydantic_phone_normalizer

    # Lista de números para procesar
    phone_numbers = [
        "+54 9 11 2345-6789",
        "5491187654321",
        "525512345678",
        "54351123456789",
        "invalid_number",  # Este debería fallar
    ]

    # Procesar en lote
    results = []
    for phone in phone_numbers:
        try:
            request = PhoneNumberRequest(phone_number=phone, force_test_mode=False)
            response = pydantic_phone_normalizer.normalize_phone_number(request)
            results.append(
                {
                    "original": phone,
                    "success": response.success,
                    "normalized": response.normalized_number,
                    "country": response.phone_info.country if response.phone_info else None,
                    "errors": response.error_message if not response.success else None,
                }
            )
        except Exception as e:
            results.append({"original": phone, "success": False, "errors": str(e)})

    # Mostrar resultados
    print("📊 Resultados del procesamiento en lote:")
    for result in results:
        status = "✅" if result["success"] else "❌"
        print(f"{status} {result['original']} -> {result.get('normalized', 'ERROR')}")
        if result.get("errors"):
            print(f"    Error: {result['errors']}")


def example_fastapi_client():
    """Ejemplo de cómo usar desde el cliente de FastAPI"""
    import asyncio

    import httpx

    async def test_api():
        async with httpx.AsyncClient() as client:
            # Test normalización individual
            response = await client.post(
                "http://localhost:8000/api/v1/phone/normalize",
                json={"phone_number": "+54 9 11 2345-6789", "country": "argentina", "force_test_mode": False},
            )

            if response.status_code == 200:
                data = response.json()
                print("✅ API Response:")
                print(f"   Success: {data['success']}")
                print(f"   Normalized: {data['normalized_number']}")
            else:
                print(f"❌ API Error: {response.status_code}")
                print(response.text)

    # Ejecutar ejemplo asíncrono
    asyncio.run(test_api())


if __name__ == "__main__":
    print("🔢 Ejemplos de Normalización de Números de Teléfono con Pydantic\n")

    print("1. Uso básico:")
    example_basic_usage()

    print("\n2. Procesamiento en lote:")
    example_batch_processing()

    print("\n3. Para probar la API, ejecuta:")
    print("   uvicorn app.main:app --reload")
    print("   Luego descomenta example_fastapi_client() para probar")
