#!/usr/bin/env python3
"""
Test de LangGraph con MemorySaver como checkpointer temporal
"""
import asyncio
import sys
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.append(str(Path(__file__).parent))

from langgraph.checkpoint.memory import MemorySaver
from app.models.message import WhatsAppMessage, TextMessage, Contact
from app.services.langgraph_chatbot_service import LangGraphChatbotService

# Modificar temporalmente el graph para usar MemorySaver
import app.agents.langgraph_system.graph as graph_module

# Monkey patch para testing
original_init = graph_module.EcommerceAssistantGraph.__init__
original_initialize = graph_module.EcommerceAssistantGraph.initialize

def patched_init(self, config):
    """Init modificado para usar MemorySaver"""
    original_init(self, config)
    # Usar MemorySaver en lugar de PostgreSQL
    self.memory_saver = MemorySaver()
    print("🔄 Using MemorySaver for testing")

async def patched_initialize(self):
    """Initialize modificado para usar MemorySaver"""
    try:
        # Compilar con MemorySaver
        print("🔧 Compiling graph with MemorySaver...")
        self.app = self.graph.compile(checkpointer=self.memory_saver)
        print("✅ Graph compiled successfully with MemorySaver")
    except Exception as e:
        print(f"❌ Error during initialization: {e}")
        raise

# Aplicar patches
graph_module.EcommerceAssistantGraph.__init__ = patched_init
graph_module.EcommerceAssistantGraph.initialize = patched_initialize

class LangGraphTester:
    """Tester para LangGraph con checkpointer en memoria"""
    
    def __init__(self):
        self.service = None
        self.test_user = "5491234567890"
        self.test_name = "Test User LangGraph"
        self.conversation_id = "test_conversation_001"
    
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
    
    async def test_single_interaction(self):
        """Test de una interacción simple"""
        print("\n🧪 TEST: Interacción Simple")
        print("=" * 50)
        
        message, contact = self.create_message("Hola, ¿qué laptops gaming tienen disponibles?")
        
        print(f"👤 Usuario: {message.text.body}")
        
        try:
            response = await self.service.procesar_mensaje(message, contact)
            print(f"🤖 Bot: {response.message}")
            print(f"📊 Estado: {response.status}")
            
            return response.status == "success"
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    async def test_conversation_flow(self):
        """Test de conversación con múltiples turnos"""
        print("\n🧪 TEST: Conversación Multi-turno")
        print("=" * 50)
        
        conversation = [
            "Hola, buenos días",
            "Busco una laptop para gaming",
            "Mi presupuesto es de 200,000 pesos",
            "¿Qué me recomiendas con RTX 4070?",
            "¿Tienen stock de esa?",
            "Perfecto, ¿cómo puedo comprarla?"
        ]
        
        success_count = 0
        
        for i, text in enumerate(conversation):
            print(f"\n--- Turno {i+1} ---")
            message, contact = self.create_message(text, f"conv_msg_{i}")
            
            print(f"👤 Usuario: {text}")
            
            try:
                response = await self.service.procesar_mensaje(message, contact)
                print(f"🤖 Bot: {response.message[:150]}...")
                
                if response.status == "success":
                    success_count += 1
                    
                # Pequeña pausa entre mensajes
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"❌ Error en turno {i+1}: {e}")
        
        print(f"\n📊 Resumen: {success_count}/{len(conversation)} turnos exitosos")
        return success_count == len(conversation)
    
    async def test_agent_routing(self):
        """Test de routing a diferentes agentes"""
        print("\n🧪 TEST: Routing de Agentes")
        print("=" * 50)
        
        test_cases = [
            ("¿Qué categorías de productos tienen?", "CategoryAgent"),
            ("¿Cuál es el precio de la RTX 4080?", "ProductAgent"),
            ("¿Tienen ofertas especiales?", "PromotionsAgent"),
            ("¿Dónde está mi pedido #12345?", "TrackingAgent"),
            ("Necesito ayuda con la garantía", "SupportAgent"),
            ("Quiero una factura", "InvoiceAgent")
        ]
        
        for text, expected_agent in test_cases:
            print(f"\n🎯 Testing: {expected_agent}")
            message, contact = self.create_message(text)
            
            print(f"👤 Usuario: {text}")
            
            try:
                response = await self.service.procesar_mensaje(message, contact)
                print(f"🤖 Bot: {response.message[:100]}...")
                print(f"✅ Procesado exitosamente")
            except Exception as e:
                print(f"❌ Error: {e}")
    
    async def cleanup(self):
        """Limpiar recursos"""
        if self.service:
            try:
                await self.service.cleanup()
                print("🧹 Cleanup completado")
            except Exception as e:
                print(f"⚠️ Error en cleanup: {e}")

async def main():
    """Función principal"""
    print("🤖 TEST DE LANGGRAPH CON MEMORY CHECKPOINTER")
    print("=" * 60)
    
    tester = LangGraphTester()
    
    # Inicializar
    if not await tester.initialize():
        print("❌ No se pudo inicializar el sistema")
        return
    
    try:
        # Test 1: Interacción simple
        test1_ok = await tester.test_single_interaction()
        
        # Test 2: Conversación multi-turno  
        test2_ok = await tester.test_conversation_flow()
        
        # Test 3: Agent routing
        await tester.test_agent_routing()
        
        # Resumen
        print("\n📊 RESUMEN FINAL")
        print("=" * 50)
        print(f"✅ Interacción simple: {'PASS' if test1_ok else 'FAIL'}")
        print(f"✅ Conversación multi-turno: {'PASS' if test2_ok else 'FAIL'}")
        print(f"✅ Agent routing: Ver resultados arriba")
        
        if test1_ok and test2_ok:
            print("\n🎉 LangGraph está funcionando correctamente con MemorySaver!")
        
    except Exception as e:
        print(f"❌ Error durante las pruebas: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())