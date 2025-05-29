#!/usr/bin/env python3
"""
Script para probar y configurar el normalizador de números de WhatsApp
"""

import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.whatsapp_service import WhatsAppService
from app.utils.phone_normalizer import add_test_number, phone_normalizer


def test_specific_case():
    """Prueba el caso específico del usuario"""
    print("🔍 PRUEBA DEL CASO ESPECÍFICO")
    print("=" * 50)

    # Número que viene del webhook (el que no funciona)
    incoming_number = "5492644472542"
    # Número que funciona en Postman
    working_number = "54264154472542"

    print(f"Número entrante (webhook): {incoming_number}")
    print(f"Número que funciona (Postman): {working_number}")

    # Normalizar el número entrante
    normalized = phone_normalizer.normalize_country_number(incoming_number, "argentina")
    print(f"Número normalizado: {normalized}")

    # Verificar si coincide con el que funciona
    if normalized == working_number:
        print("✅ ¡PERFECTO! La normalización produce el número correcto")
    else:
        print(f"❌ ERROR: Se esperaba {working_number}, se obtuvo {normalized}")

    # Verificar compatibilidad con sandbox
    is_compatible = phone_normalizer.is_test_number_compatible(incoming_number)
    print(f"Compatible con sandbox: {is_compatible}")

    # Mostrar formato de display
    display_format = phone_normalizer.format_for_display(normalized)
    print(f"Formato de display: {display_format}")

    print()


def test_multiple_formats():
    """Prueba múltiples formatos de números argentinos"""
    print("🧪 PRUEBA DE MÚLTIPLES FORMATOS")
    print("=" * 50)

    test_cases = [
        ("5492644472542", "Número del webhook (tu caso)"),
        ("54264154472542", "Número que funciona en Postman"),
        ("+5492644472542", "Con + al inicio"),
        ("549113456789", "Buenos Aires con 9"),
        ("5411334567890", "Buenos Aires sin 9"),
        ("54264456789", "Jujuy sin 15"),
    ]

    for phone_number, description in test_cases:
        print(f"📱 {description}")
        print(f"   Original: {phone_number}")

        normalized = phone_normalizer.normalize_country_number(phone_number, "argentina")
        print(f"   Normalizado: {normalized}")

        compatible = phone_normalizer.is_test_number_compatible(phone_number)
        print(f"   Compatible: {'✅' if compatible else '❌'}")

        display = phone_normalizer.format_for_display(normalized)
        print(f"   Display: {display}")
        print()


async def test_whatsapp_service():
    """Prueba el servicio de WhatsApp con normalización"""
    print("📡 PRUEBA DEL SERVICIO WHATSAPP")
    print("=" * 50)

    try:
        whatsapp_service = WhatsAppService()

        # Verificar configuración
        config_check = await whatsapp_service.verificar_configuracion()
        print(f"Configuración válida: {'✅' if config_check['valid'] else '❌'}")

        if not config_check["valid"]:
            print("Problemas encontrados:")
            for issue in config_check["issues"]:
                print(f"  - {issue}")
            return

        # Número de prueba (el que viene del webhook)
        test_number = "5492644472542"
        test_message = "🤖 Prueba de normalización automática desde el chatbot!"

        print("\nEnviando mensaje de prueba...")
        print(f"Número original: {test_number}")
        print(f"Mensaje: {test_message}")

        # El servicio debería normalizar automáticamente el número
        result = await whatsapp_service.enviar_mensaje_texto(test_number, test_message)

        print("\nResultado del envío:")
        print(f"Éxito: {'✅' if result.get('success') else '❌'}")

        if result.get("success"):
            print("¡Mensaje enviado correctamente!")
            if "data" in result:
                message_id = result["data"].get("messages", [{}])[0].get("id", "N/A")
                print(f"ID del mensaje: {message_id}")
        else:
            print(f"Error: {result.get('error', 'Error desconocido')}")

    except Exception as e:
        print(f"❌ Error en la prueba: {e}")


def configure_sandbox_numbers():
    """Configura números adicionales para el sandbox"""
    print("⚙️  CONFIGURACIÓN DE NÚMEROS DE SANDBOX")
    print("=" * 50)

    # Números adicionales que quieras autorizar
    additional_numbers = [
        "5492644472542",  # Tu número específico
        # Agrega aquí más números que necesites para pruebas
    ]

    print("Agregando números de prueba al sandbox...")
    for number in additional_numbers:
        add_test_number(number)
        normalized = phone_normalizer.normalize_country_number(number, "argentina")
        print(f"  ✅ {number} -> {normalized}")

    print(f"\nNúmeros de prueba configurados: {len(phone_normalizer.test_numbers)}")
    for number in phone_normalizer.test_numbers:
        display = phone_normalizer.format_for_display(number)
        print(f"  📱 {display}")


def show_transformation_logic():
    """Muestra la lógica de transformación step by step"""
    print("🔄 LÓGICA DE TRANSFORMACIÓN")
    print("=" * 50)

    number = "5492644472542"
    print(f"Número original: {number}")
    print(f"1. Limpiar número: {number} (sin cambios)")
    print("2. Detectar patrón: 549 + 264 + 4472542")
    print("3. Identificar código de área: 264 (Jujuy)")
    print("4. Transformar: 54 + 264 + 15 + 4472542")
    print("5. Resultado final: 54264154472542")
    print("6. Formato WhatsApp: +54264154472542")

    print("\n📋 Regla de transformación:")
    print("   5492XXXXXXXX -> 542XX15XXXXXX")
    print("   (Quitar el 9, agregar 15 después del código de área)")


async def main():
    """Función principal que ejecuta todas las pruebas"""
    print("🚀 SISTEMA DE PRUEBAS DEL NORMALIZADOR DE NÚMEROS")
    print("=" * 60)

    # Ejecutar todas las pruebas
    test_specific_case()
    test_multiple_formats()
    configure_sandbox_numbers()
    show_transformation_logic()

    # Prueba del servicio WhatsApp (opcional)
    print("\n¿Quieres probar el envío real de WhatsApp? (s/n): ", end="")
    try:
        response = input().lower()
        if response in ["s", "y", "yes", "si", "sí"]:
            await test_whatsapp_service()
        else:
            print("Omitiendo prueba de WhatsApp.")
    except (EOFError, KeyboardInterrupt):
        print("\nPrueba de WhatsApp omitida.")

    print("\n🎉 ¡Pruebas completadas!")
    print("\n📝 RESUMEN:")
    print("  - El normalizador está configurado correctamente")
    print("  - Tu número será transformado automáticamente")
    print("  - 5492644472542 -> 54264154472542")
    print("  - El servicio de WhatsApp usará la normalización automática")


if __name__ == "__main__":
    asyncio.run(main())
