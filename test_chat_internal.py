#!/usr/bin/env python3
"""
Test interno del chatbot que solo procesa lógica sin enviar por WhatsApp
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.append(str(Path(__file__).parent))

from app.services.ai_service import AIService
from app.services.prompt_service import PromptService

class InternalChatTest:
    """Test del procesamiento interno del chatbot"""
    
    def __init__(self):
        self.ai_service = None
        self.prompt_service = None
        self.conversation_history = []
    
    async def initialize(self):
        """Inicializar servicios básicos"""
        try:
            print("🔧 Inicializando servicios internos...")
            self.ai_service = AIService()
            self.prompt_service = PromptService()
            print("✅ Servicios inicializados correctamente")
            return True
        except Exception as e:
            print(f"❌ Error inicializando servicios: {e}")
            return False
    
    async def test_intent_detection(self, message: str):
        """Probar detección de intención"""
        try:
            print(f"🔍 Detectando intención para: '{message}'")
            
            result = await self.ai_service.detect_intent(message)
            
            print(f"   Intent: {result.intent}")
            print(f"   Confidence: {result.confidence}")
            print(f"   Estado: {result.estado}")
            
            return result
        except Exception as e:
            print(f"❌ Error en detección de intención: {e}")
            return None
    
    async def test_response_generation(self, message: str, intent: str = "consulta_productos"):
        """Probar generación de respuesta"""
        try:
            print(f"💭 Generando respuesta para: '{message}' (intent: {intent})")
            
            # Generar contexto básico
            context = f"Cliente pregunta sobre: {message}. Intent detectado: {intent}"
            
            # Usar el servicio de prompts para generar respuesta
            full_prompt = self.prompt_service._build_improved_prompt(message, "", context)
            
            response = await self.ai_service.generate_response(full_prompt, temperature=0.7)
            
            print(f"🤖 Respuesta generada: {response[:100]}...")
            
            return response
        except Exception as e:
            print(f"❌ Error en generación de respuesta: {e}")
            return None
    
    async def test_conversation_flow(self):
        """Probar flujo completo de conversación"""
        print("💬 PRUEBA DE FLUJO DE CONVERSACIÓN")
        print("=" * 50)
        
        test_messages = [
            "Hola, buenos días",
            "¿Qué laptops gaming tienen?",
            "Necesito algo para trabajar con diseño",
            "¿Cuánto cuesta una RTX 4080?",
            "¿Hacen envíos a Córdoba?"
        ]
        
        successful_tests = 0
        
        for i, message in enumerate(test_messages, 1):
            print(f"\\n--- Test {i}/{len(test_messages)} ---")
            print(f"👤 Mensaje: {message}")
            
            try:
                # 1. Detectar intención
                intent_result = await self.test_intent_detection(message)
                
                if intent_result:
                    # 2. Generar respuesta
                    response = await self.test_response_generation(
                        message, 
                        intent_result.intent
                    )
                    
                    if response:
                        successful_tests += 1
                        print("✅ Test completado exitosamente")
                    else:
                        print("❌ Fallo en generación de respuesta")
                else:
                    print("❌ Fallo en detección de intención")
                
                # Pausa entre tests
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ Error en test {i}: {e}")
        
        print(f"\\n📈 Resultados finales:")
        print(f"Tests exitosos: {successful_tests}/{len(test_messages)}")
        print(f"Tasa de éxito: {(successful_tests/len(test_messages)*100):.1f}%")
        
        return successful_tests > 0
    
    async def test_ollama_connectivity(self):
        """Probar conectividad con Ollama"""
        print("🔗 PRUEBA DE CONECTIVIDAD OLLAMA")
        print("=" * 50)
        
        try:
            # Test simple de generación
            simple_prompt = "Responde brevemente: ¿Cuál es la capital de Argentina?"
            response = await self.ai_service.generate_response(simple_prompt, temperature=0.1)
            
            if response and len(response) > 5:
                print(f"✅ Ollama responde correctamente: {response}")
                return True
            else:
                print("❌ Respuesta de Ollama vacía o muy corta")
                return False
                
        except Exception as e:
            print(f"❌ Error conectando con Ollama: {e}")
            return False

async def main():
    """Función principal"""
    print("🧪 TEST INTERNO DEL CHATBOT")
    print("=" * 60)
    
    test = InternalChatTest()
    
    # Inicializar servicios
    if not await test.initialize():
        print("❌ No se pudieron inicializar los servicios.")
        return
    
    try:
        # 1. Test de Ollama
        print("\\n🎯 FASE 1: Conectividad con Ollama")
        ollama_ok = await test.test_ollama_connectivity()
        
        if not ollama_ok:
            print("⚠️ Ollama no está funcionando. Verificar que esté ejecutándose.")
            return
        
        # 2. Test de flujo de conversación
        print("\\n🎯 FASE 2: Flujo de conversación")
        conversation_ok = await test.test_conversation_flow()
        
        # Resultado final
        print(f"\\n🏁 RESULTADO FINAL")
        print("=" * 50)
        
        if ollama_ok and conversation_ok:
            print("✅ Los servicios internos del chatbot están funcionando")
            print("🎉 El sistema puede procesar mensajes y generar respuestas")
        else:
            print("⚠️ Algunos servicios tienen problemas")
            print("🔍 Revisar logs para más detalles")
        
    except Exception as e:
        print(f"❌ Error durante las pruebas: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())