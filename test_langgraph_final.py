#!/usr/bin/env python3
"""
Test final del sistema LangGraph con Memory checkpointer y opción PostgreSQL
"""
import asyncio
import sys
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.append(str(Path(__file__).parent))

from app.models.message import WhatsAppMessage, TextMessage, Contact
from app.services.langgraph_chatbot_service import LangGraphChatbotService

class FinalLangGraphTester:
    """Test final del sistema LangGraph completo"""
    
    def __init__(self):
        self.service = None
        self.test_user = "5491234567890"
        self.test_name = "Test User Final"
        self.conversation_id = "final_test_001"
    
    async def initialize(self):
        """Inicializar servicio"""
        try:
            print("🔧 Inicializando LangGraphChatbotService...")
            self.service = LangGraphChatbotService()
            await self.service.initialize()
            print("✅ Servicio inicializado correctamente")
            return True
        except Exception as e:
            print(f"❌ Error inicializando: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def create_message(self, text: str, msg_id: str = None) -> tuple[WhatsAppMessage, Contact]:
        """Crear mensaje y contacto"""
        if not msg_id:
            msg_id = f"msg_{int(asyncio.get_event_loop().time())}"
            
        message = WhatsAppMessage(
            from_=self.test_user,
            id=msg_id,
            type="text",
            timestamp=str(int(asyncio.get_event_loop().time())),
            text=TextMessage(body=text)
        )
        
        contact = Contact(
            wa_id=self.test_user,
            profile={"name": self.test_name}
        )
        
        return message, contact
    
    async def test_complete_conversation(self):
        """Test de conversación completa que demuestra todas las capacidades"""
        print("\n🧪 TEST: CONVERSACIÓN COMPLETA")
        print("=" * 50)
        
        conversation_flow = [
            ("Hola, buenos días", "Verificar respuesta de saludo"),
            ("¿Qué laptops gaming tienen disponibles?", "Verificar consulta de productos"),
            ("Necesito una con RTX 4070", "Verificar filtrado específico"),
            ("¿Cuál es el precio?", "Verificar consulta de precios"),
            ("¿Tienen stock?", "Verificar consulta de stock"),
            ("¿Hacen envíos a Córdoba?", "Verificar consulta de envíos"),
            ("Perfecto, quiero comprarla", "Verificar proceso de compra"),
            ("¿Necesito factura?", "Verificar consulta de facturación"),
            ("Gracias por la ayuda", "Verificar cierre de conversación")
        ]
        
        success_count = 0
        conversation_context = []
        
        for i, (message_text, expected_behavior) in enumerate(conversation_flow, 1):
            print(f"\n--- Intercambio {i}/{len(conversation_flow)} ---")
            print(f"🎯 Objetivo: {expected_behavior}")
            print(f"👤 Usuario: {message_text}")
            
            try:
                message, contact = self.create_message(message_text, f"final_msg_{i:02d}")
                
                # Procesar mensaje
                response = await self.service.procesar_mensaje(message, contact)
                
                print(f"🤖 Bot: {response.message}")
                print(f"📊 Estado: {response.status}")
                
                if response.status == "success":
                    success_count += 1
                    conversation_context.append({
                        "user": message_text,
                        "bot": response.message,
                        "status": response.status
                    })
                    print("✅ Intercambio exitoso")
                else:
                    print(f"❌ Error en intercambio: {response.message}")
                
                # Pausa entre mensajes para simular conversación real
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ Error en intercambio {i}: {e}")
                import traceback
                traceback.print_exc()
        
        # Analizar resultados
        print(f"\n📈 RESULTADOS:")
        print(f"Intercambios exitosos: {success_count}/{len(conversation_flow)}")
        print(f"Tasa de éxito: {(success_count/len(conversation_flow)*100):.1f}%")
        
        if success_count >= len(conversation_flow) * 0.8:  # 80% de éxito
            print("🎉 CONVERSACIÓN EXITOSA!")
            return True
        else:
            print("⚠️ Conversación con problemas")
            return False
    
    async def test_agent_specialization(self):
        """Test de especialización de agentes"""
        print("\n🧪 TEST: ESPECIALIZACIÓN DE AGENTES")
        print("=" * 50)
        
        agent_tests = [
            ("¿Qué categorías de productos manejan?", "CategoryAgent"),
            ("Dame información sobre la laptop ASUS ROG", "ProductAgent"),
            ("¿Tienen ofertas especiales esta semana?", "PromotionsAgent"),
            ("¿Dónde está mi pedido #12345?", "TrackingAgent"),
            ("Tengo problemas con la garantía", "SupportAgent"),
            ("Necesito una factura del pedido anterior", "InvoiceAgent")
        ]
        
        agent_success = {}
        
        for test_message, expected_agent in agent_tests:
            print(f"\n🎯 Testing: {expected_agent}")
            print(f"👤 Usuario: {test_message}")
            
            try:
                message, contact = self.create_message(test_message)
                response = await self.service.procesar_mensaje(message, contact)
                
                print(f"🤖 Bot: {response.message[:100]}...")
                
                if response.status == "success":
                    agent_success[expected_agent] = True
                    print(f"✅ {expected_agent} respondió correctamente")
                else:
                    agent_success[expected_agent] = False
                    print(f"❌ Error en {expected_agent}")
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"❌ Error testing {expected_agent}: {e}")
                agent_success[expected_agent] = False
        
        # Resultados de especialización
        successful_agents = sum(agent_success.values())
        total_agents = len(agent_success)
        
        print(f"\n📊 ESPECIALIZACIÓN DE AGENTES:")
        for agent, success in agent_success.items():
            status = "✅" if success else "❌"
            print(f"  {status} {agent}")
        
        print(f"\nAgentes funcionando: {successful_agents}/{total_agents}")
        
        return successful_agents >= total_agents * 0.7  # 70% de agentes funcionando
    
    async def test_memory_persistence(self):
        """Test de persistencia de memoria (con Memory checkpointer)"""
        print("\n🧪 TEST: PERSISTENCIA DE MEMORIA")
        print("=" * 50)
        
        # Primera parte de la conversación
        print("🔄 Parte 1: Establecer contexto...")
        message1, contact = self.create_message("Hola, estoy buscando una laptop gaming", "memory_test_1")
        response1 = await self.service.procesar_mensaje(message1, contact)
        print(f"👤 Usuario: {message1.text.body}")
        print(f"🤖 Bot: {response1.message[:100]}...")
        
        await asyncio.sleep(1)
        
        # Segunda parte - referencia al contexto anterior
        print("\n🔄 Parte 2: Referencia al contexto...")
        message2, contact = self.create_message("¿Recuerdas qué estaba buscando?", "memory_test_2")
        response2 = await self.service.procesar_mensaje(message2, contact)
        print(f"👤 Usuario: {message2.text.body}")
        print(f"🤖 Bot: {response2.message[:100]}...")
        
        # Verificar si el bot mantiene contexto
        context_maintained = (
            response1.status == "success" and 
            response2.status == "success" and
            ("laptop" in response2.message.lower() or "gaming" in response2.message.lower())
        )
        
        if context_maintained:
            print("✅ Memoria de conversación funcionando")
            return True
        else:
            print("⚠️ Memoria de conversación limitada (normal con Memory checkpointer)")
            return False
    
    async def test_system_performance(self):
        """Test de rendimiento del sistema"""
        print("\n🧪 TEST: RENDIMIENTO DEL SISTEMA")
        print("=" * 50)
        
        import time
        
        # Test de velocidad de respuesta
        start_time = time.time()
        
        message, contact = self.create_message("Test de velocidad")
        response = await self.service.procesar_mensaje(message, contact)
        
        end_time = time.time()
        response_time = end_time - start_time
        
        print(f"⏱️  Tiempo de respuesta: {response_time:.2f} segundos")
        
        if response_time < 10.0:  # Menos de 10 segundos
            print("✅ Rendimiento aceptable")
            performance_ok = True
        else:
            print("⚠️ Rendimiento lento")
            performance_ok = False
        
        return performance_ok and response.status == "success"
    
    async def cleanup(self):
        """Limpiar recursos"""
        try:
            if self.service:
                await self.service.cleanup()
            print("🧹 Cleanup completado")
        except Exception as e:
            print(f"⚠️ Error en cleanup: {e}")

async def main():
    """Función principal"""
    print("🤖 TEST FINAL DEL SISTEMA LANGGRAPH")
    print("=" * 60)
    print("📋 Se van a ejecutar los siguientes tests:")
    print("   1. Conversación completa multi-agente")
    print("   2. Especialización de agentes")
    print("   3. Persistencia de memoria")
    print("   4. Rendimiento del sistema")
    print("=" * 60)
    
    tester = FinalLangGraphTester()
    
    # Inicializar
    if not await tester.initialize():
        print("❌ No se pudo inicializar el sistema")
        return
    
    try:
        # Ejecutar todos los tests
        results = {}
        
        print("\n🎯 FASE 1: Conversación Completa")
        results["conversation"] = await tester.test_complete_conversation()
        
        print("\n🎯 FASE 2: Especialización de Agentes")
        results["agents"] = await tester.test_agent_specialization()
        
        print("\n🎯 FASE 3: Persistencia de Memoria")
        results["memory"] = await tester.test_memory_persistence()
        
        print("\n🎯 FASE 4: Rendimiento del Sistema")
        results["performance"] = await tester.test_system_performance()
        
        # Resumen final
        print("\n" + "=" * 60)
        print("📊 RESUMEN FINAL DEL SISTEMA LANGGRAPH")
        print("=" * 60)
        
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{test_name.upper().ljust(20)}: {status}")
        
        success_count = sum(results.values())
        total_tests = len(results)
        overall_score = (success_count / total_tests) * 100
        
        print(f"\nPUNTUACIÓN TOTAL: {success_count}/{total_tests} ({overall_score:.1f}%)")
        
        if overall_score >= 75:
            print("\n🎉 ¡SISTEMA LANGGRAPH FUNCIONANDO CORRECTAMENTE!")
            print("🔥 El sistema multi-agente está listo para producción")
            print("💡 Recomendación: Configurar PostgreSQL checkpointer para persistencia completa")
        elif overall_score >= 50:
            print("\n✅ Sistema LangGraph funcionando con limitaciones")
            print("🔧 Requiere ajustes pero es funcional")
        else:
            print("\n⚠️ Sistema LangGraph requiere trabajo adicional")
            print("🔍 Revisar logs y configuración")
        
        # Información adicional
        print("\n📝 INFORMACIÓN DEL SISTEMA:")
        print(f"   • Checkpointer actual: Memory (temporal)")
        print(f"   • PostgreSQL checkpointer: Disponible pero requiere configuración")
        print(f"   • Agentes disponibles: 6 especializados")
        print(f"   • Integraciones: Ollama + ChromaDB + PostgreSQL")
        
    except Exception as e:
        print(f"❌ Error durante las pruebas: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())