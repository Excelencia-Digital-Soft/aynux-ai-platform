#!/usr/bin/env python3

"""
Script de prueba para el normalizador de números de teléfono argentinos
Prueba específica: 5492644472542 -> 54264154472542
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.phone_normalizer_pydantic import (
    PhoneNumberRequest,
    get_normalized_number_only,
    pydantic_phone_normalizer,
)


def test_specific_conversion():
    """Prueba la conversión específica del usuario"""
    print("🔧 PRUEBA DE CONVERSIÓN ESPECÍFICA")
    print("=" * 50)
    # Tu caso específico
    input_number = "5492644472542"
    expected_output = "54264154472542"

    print(f"📱 Número de entrada: {input_number}")
    print(f"🎯 Resultado esperado: {expected_output}")
    print()

    try:
        # Crear request con validación Pydantic
        request = PhoneNumberRequest(phone_number=input_number, country="argentina", force_test_mode=False)

        print("✅ Request creado exitosamente")
        print(f"   - Número: {request.phone_number}")
        print(f"   - País: {request.country}")
        print(f"   - Modo test: {request.force_test_mode}")
        print()

        # Normalizar usando el servicio Pydantic
        response = pydantic_phone_normalizer.normalize_phone_number(request)

        if response.success:
            print("🎉 NORMALIZACIÓN EXITOSA!")
            print(f"   ✅ Número normalizado: {response.phone_info.normalized_number}")
            print(f"   📍 País detectado: {response.phone_info.country}")
            print(f"   📞 Código de área: {response.phone_info.area_code}")
            print(f"   📱 Número local: {response.phone_info.local_number}")
            print(f"   📋 Formato display: {response.phone_info.formatted_display}")
            print(f"   🏷️ Es móvil: {response.phone_info.is_mobile}")
            print(f"   🧪 Test compatible: {response.phone_info.is_test_compatible}")

            # Verificar si la conversión es correcta
            actual_output = response.phone_info.normalized_number

            print("\n🔍 VERIFICACIÓN:")
            if actual_output == expected_output:
                print("   ✅ ¡PERFECTO! Conversión correcta")
                print(f"   ✅ {input_number} -> {actual_output}")
                return True
            else:
                print("   ❌ Conversión incorrecta")
                print(f"   ❌ Se obtuvo: {actual_output}")
                print(f"   ❌ Se esperaba: {expected_output}")
                return False

        else:
            print("❌ ERROR EN LA NORMALIZACIÓN:")
            print(f"   Error: {response.error_message}")
            if response.warnings:
                print(f"   Advertencias: {response.warnings}")
            return False

    except Exception as e:
        print(f"❌ EXCEPCIÓN: {str(e)}")
        return False


def test_multiple_argentina_cases():
    """Prueba múltiples casos argentinos"""
    print("\n🧪 PRUEBAS MÚLTIPLES - NÚMEROS ARGENTINOS")
    print("=" * 50)

    test_cases = [
        # (input, expected_output, description)
        ("5492644472542", "54264154472542", "San Juan - Tu caso específico"),
        ("549113456789", "5411153456789", "Buenos Aires con 9"),  # Sin agregar 0
        ("5411156789012", "5411156789012", "Buenos Aires ya normalizado"),
        ("549351123456", "5435115123456", "Córdoba con 9"),  # Sin agregar 0
        ("+5492644472542", "54264154472542", "Con símbolo +"),
        ("54 9 264 447-2542", "54264154472542", "Con formato espaciado"),
    ]

    results = []

    for input_num, expected, description in test_cases:
        print(f"\n📋 {description}")
        print(f"   Input: {input_num}")
        print(f"   Expected: {expected}")

        try:
            # Usar la función de conveniencia
            normalized = get_normalized_number_only(input_num, test_mode=False)

            if normalized:
                print(f"   Output: {normalized}")
                if normalized == expected:
                    print("   ✅ CORRECTO")
                    results.append(True)
                else:
                    print("   ❌ INCORRECTO")
                    results.append(False)
            else:
                print("   ❌ FALLÓ LA NORMALIZACIÓN")
                results.append(False)

        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            results.append(False)

    # Resumen
    print("\n📊 RESUMEN DE PRUEBAS:")
    print(f"   Total: {len(results)}")
    print(f"   Exitosas: {sum(results)}")
    print(f"   Fallidas: {len(results) - sum(results)}")
    print(f"   Tasa de éxito: {sum(results) / len(results) * 100:.1f}%")

    return results


def analyze_normalization_logic():
    """Analiza la lógica de normalización paso a paso"""
    print("\n🔍 ANÁLISIS PASO A PASO")
    print("=" * 50)

    number = "5492644472542"
    print(f"Número original: {number}")

    # Simular los pasos del normalizador
    print("\n🔄 Pasos de normalización:")
    print("1. Limpiar número (quitar espacios, +, etc.)")
    clean = number.replace("+", "").replace(" ", "").replace("-", "")
    print(f"   -> {clean}")

    print("2. Detectar país (comienza con 54)")
    print("   -> Argentina detectada")

    print("3. Aplicar patrón argentino con 9: 549XXXXXXXXX")
    print("   -> Patrón coincide: 549 + 264 + 4472542")

    print("4. Identificar código de área: 264 (San Juan)")
    area_code = "264"
    local_number = "4472542"
    print(f"   -> Área: {area_code}, Local: {local_number}")

    print("5. Transformar: 54 + ÁREA + 15 + LOCAL")
    transformed = f"54{area_code}15{local_number}"
    print(f"   -> {transformed}")

    print(f"\n🎯 Resultado final esperado: {transformed}")


def main():
    """Función principal"""
    print("🚀 PROBADOR DEL NORMALIZADOR DE NÚMEROS ARGENTINOS")
    print("=" * 60)

    # Prueba específica del usuario
    success = test_specific_conversion()

    # Análisis de la lógica
    analyze_normalization_logic()

    # Pruebas múltiples
    test_multiple_argentina_cases()

    # Conclusión
    print("\n" + "=" * 60)
    if success:
        print("🎉 ¡El normalizador funciona correctamente para tu caso!")
        print("   Tu número se convierte perfectamente.")
    else:
        print("⚠️  El normalizador necesita ajustes.")
        print("   Revisa la lógica de normalización argentina.")

    print("\n📝 PRÓXIMOS PASOS:")
    if success:
        print("   1. ✅ La normalización funciona")
        print("   2. ✅ Puedes usar el normalizador en producción")
        print("   3. 🔧 Considera agregar más números de prueba")
    else:
        print("   1. 🔧 Revisar método _normalize_argentina()")
        print("   2. 🔧 Verificar patrones regex")
        print("   3. 🔧 Ajustar lógica de códigos de área")


if __name__ == "__main__":
    main()
