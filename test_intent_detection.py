#!/usr/bin/env python3
"""
Script para probar específicamente la detección de intenciones
"""

import asyncio
import logging
from typing import Dict, List, Tuple

from app.agents.langgraph_system.intelligence.intent_router import IntentRouter

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class IntentTester:
    """Clase para probar la detección de intenciones"""
    
    def __init__(self):
        self.router = IntentRouter()
    
    def test_intent_detection(self, test_cases: List[Tuple[str, str]]):
        """
        Prueba la detección de intenciones con casos de prueba
        
        Args:
            test_cases: Lista de tuplas (mensaje, intención_esperada)
        """
        print("\n" + "="*80)
        print("🧠 PRUEBA DE DETECCIÓN DE INTENCIONES")
        print("="*80)
        
        correct_predictions = 0
        total_cases = len(test_cases)
        
        for i, (message, expected_intent) in enumerate(test_cases, 1):
            print(f"\n--- Caso {i}/{total_cases} ---")
            print(f"📱 Mensaje: '{message}'")
            print(f"🎯 Intención esperada: {expected_intent}")
            
            # Detectar intención
            result = self.router.determine_intent(message)
            detected_intent = result["primary_intent"]
            confidence = result["confidence"]
            target_agent = result["target_agent"]
            
            print(f"🤖 Intención detectada: {detected_intent} (confianza: {confidence:.2f})")
            print(f"🎭 Agente asignado: {target_agent}")
            
            # Verificar si es correcto
            is_correct = detected_intent == expected_intent
            if is_correct:
                print("✅ CORRECTO")
                correct_predictions += 1
            else:
                print("❌ INCORRECTO")
            
        # Mostrar estadísticas
        accuracy = (correct_predictions / total_cases) * 100
        print(f"\n" + "="*80)
        print("📊 ESTADÍSTICAS DE DETECCIÓN")
        print("="*80)
        print(f"Casos totales: {total_cases}")
        print(f"Predicciones correctas: {correct_predictions}")
        print(f"Precisión: {accuracy:.1f}%")
        
        if accuracy >= 80:
            print("🎉 ¡Excelente detección de intenciones!")
        elif accuracy >= 60:
            print("👍 Buena detección, pero puede mejorar")
        else:
            print("⚠️ La detección necesita mejoras")


def main():
    """Función principal que ejecuta las pruebas de intención"""
    
    tester = IntentTester()
    
    # Casos de prueba: (mensaje, intención_esperada)
    test_cases = [
        # Casos de categoría/productos generales
        ("Hola, ¿qué productos ofreces?", "categoria"),
        ("¿Qué tienen disponible?", "categoria"),
        ("Mostrar catálogo", "categoria"),
        
        # Casos de productos específicos
        ("¿Cuánto cuesta una laptop gaming?", "producto"),
        ("Me interesan las laptops", "producto"),
        ("¿Cuáles son las especificaciones?", "producto"),
        ("Busco una laptop para diseño gráfico", "producto"),
        ("Precio de iPhone", "producto"),
        
        # Casos de promociones
        ("¿Tienen ofertas disponibles?", "promociones"),
        ("Me interesa el descuento para estudiantes", "promociones"),
        ("¿Cómo aplico el cupón?", "promociones"),
        ("¿Hay alguna rebaja?", "promociones"),
        
        # Casos de soporte técnico
        ("Tengo un problema con mi laptop", "soporte"),
        ("No enciende", "soporte"),
        ("¿Puedo hacer una devolución?", "soporte"),
        ("Problema con la garantía", "soporte"),
        
        # Casos de seguimiento
        ("¿Dónde está mi pedido #123456?", "seguimiento"),
        ("¿Cuándo llega mi orden?", "seguimiento"),
        ("Tracking del envío", "seguimiento"),
        ("Necesito cambiar dirección de entrega", "seguimiento"),
        
        # Casos de facturación
        ("Necesito la factura del pedido", "facturacion"),
        ("¿Puedo pagar con tarjeta?", "facturacion"),
        ("¿Aceptan transferencia bancaria?", "facturacion"),
        ("Métodos de pago", "facturacion"),
    ]
    
    # Ejecutar pruebas
    tester.test_intent_detection(test_cases)
    
    print(f"\n" + "="*80)
    print("🏁 PRUEBA COMPLETADA")
    print("="*80)


if __name__ == "__main__":
    main()