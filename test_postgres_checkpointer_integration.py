#!/usr/bin/env python3
"""
Test de integración del PostgreSQL checkpointer con LangGraph
"""
import asyncio
import sys
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.append(str(Path(__file__).parent))

from app.agents.langgraph_system.integrations.postgres_checkpointer import (
    get_checkpointer_manager,
    initialize_checkpointer,
    MonitoredAsyncPostgresSaver
)
from app.models.message import WhatsAppMessage, TextMessage, Contact
from app.services.langgraph_chatbot_service import LangGraphChatbotService

class PostgresCheckpointerTester:
    """Tester específico para PostgreSQL checkpointer"""
    
    def __init__(self):
        self.checkpointer_manager = None
        self.service = None
        self.test_user = "5491234567890"
        self.test_name = "Test User PostgreSQL"
        self.conversation_id = "postgres_test_001"
    
    async def test_checkpointer_health(self):
        """Test básico de salud del checkpointer"""
        print("🏥 HEALTH CHECK DEL CHECKPOINTER")
        print("=" * 50)
        
        try:
            # Obtener manager
            self.checkpointer_manager = get_checkpointer_manager()
            
            # Verificar inicialización
            health_ok = await initialize_checkpointer()
            
            if health_ok:
                print("✅ Checkpointer PostgreSQL inicializado correctamente")
                
                # Test específico de salud
                health_check = await self.checkpointer_manager.health_check()
                
                if health_check:
                    print("✅ Health check del checkpointer PASSED")
                    return True
                else:
                    print("❌ Health check del checkpointer FAILED")
                    return False
            else:
                print("❌ Error en inicialización del checkpointer")
                return False
                
        except Exception as e:
            print(f"❌ Error en health check: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_checkpointer_operations(self):
        """Test de operaciones básicas del checkpointer"""
        print("\n🔧 TEST DE OPERACIONES BÁSICAS")
        print("=" * 50)
        
        try:
            async with self.checkpointer_manager.get_async_checkpointer() as checkpointer:
                # Test de configuración
                config = {"configurable": {"thread_id": "test_basic_ops"}}
                
                print("📝 Test 1: Obtener checkpoint vacío...")
                empty_tuple = await checkpointer.aget_tuple(config)
                print(f"   Resultado: {empty_tuple}")
                
                print("💾 Test 2: Guardar checkpoint...")
                test_checkpoint = {
                    "messages": ["Hola", "¿Cómo estás?"],
                    "state": {"intent": "greeting", "step": 1}
                }
                
                # Simular estructura de checkpoint de LangGraph
                checkpoint_data = {
                    "v": 1,
                    "ts": "2024-01-01T00:00:00Z",
                    "id": "test_checkpoint_001",
                    "channel_values": test_checkpoint,
                    "channel_versions": {"__root__": 1},
                    "versions_seen": {"__root__": {"__root__": 1}}
                }
                
                await checkpointer.aput(
                    config=config,
                    checkpoint=checkpoint_data,
                    metadata={"test": True},
                    new_versions={"__root__": 2}
                )
                print("   ✅ Checkpoint guardado")
                
                print("📖 Test 3: Recuperar checkpoint...")
                saved_tuple = await checkpointer.aget_tuple(config)
                print(f"   Checkpoint recuperado: {saved_tuple is not None}")
                
                if saved_tuple:
                    print(f"   Metadata: {saved_tuple.metadata}")
                    return True
                else:
                    print("   ❌ No se pudo recuperar el checkpoint")
                    return False
                    
        except Exception as e:
            print(f"❌ Error en operaciones básicas: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_monitored_checkpointer(self):
        """Test del checkpointer con monitoreo"""
        print("\n📊 TEST DEL CHECKPOINTER MONITOREADO")
        print("=" * 50)
        
        try:
            # Crear checkpointer monitoreado
            async with self.checkpointer_manager.get_async_checkpointer() as base_checkpointer:
                # Usar el monitoreado directamente
                from psycopg_pool import AsyncConnectionPool
                from app.config.settings import get_settings
                
                settings = get_settings()
                pool = AsyncConnectionPool(
                    conninfo=settings.database_url,
                    max_size=5,
                    min_size=2
                )
                
                monitored_checkpointer = MonitoredAsyncPostgresSaver(pool)
                await monitored_checkpointer.setup()
                
                config = {"configurable": {"thread_id": "test_monitored"}}
                
                print("🔍 Test de monitoreo en operaciones...")
                
                # Test de escritura con monitoreo
                checkpoint_data = {
                    "v": 1,
                    "ts": "2024-01-01T00:00:00Z", 
                    "id": "monitored_test_001",
                    "channel_values": {"test": "monitored_data"},
                    "channel_versions": {"__root__": 1},
                    "versions_seen": {"__root__": {"__root__": 1}}
                }
                
                await monitored_checkpointer.aput(
                    config=config,
                    checkpoint=checkpoint_data,
                    metadata={"monitored": True},
                    new_versions={"__root__": 2}
                )
                print("   ✅ Escritura monitoreada completada")
                
                # Test de lectura con monitoreo
                result = await monitored_checkpointer.aget_tuple(config)
                print(f"   ✅ Lectura monitoreada completada: {result is not None}")
                
                await pool.close()
                return True
                
        except Exception as e:
            print(f"❌ Error en checkpointer monitoreado: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_with_langgraph_service(self):
        """Test de integración con el servicio LangGraph"""
        print("\n🤖 TEST DE INTEGRACIÓN CON LANGGRAPH")
        print("=" * 50)
        
        try:
            # Temporarily patch to use PostgreSQL checkpointer
            import app.agents.langgraph_system.graph as graph_module
            
            original_init = graph_module.EcommerceAssistantGraph.__init__
            original_initialize = graph_module.EcommerceAssistantGraph.initialize
            
            def patched_init(self, config):
                """Init modificado para forzar PostgreSQL checkpointer"""
                original_init(self, config)
                self.use_postgres_checkpointer = True
                print("🔧 Forced PostgreSQL checkpointer usage")
            
            async def patched_initialize(self):
                """Initialize modificado para testear PostgreSQL"""
                try:
                    from app.agents.langgraph_system.integrations.postgres_checkpointer import get_checkpointer_manager
                    
                    # Forzar uso de PostgreSQL checkpointer
                    print("🔧 Initializing with PostgreSQL checkpointer...")
                    self.checkpointer_manager = get_checkpointer_manager()
                    
                    # Verificar salud
                    health_ok = await self.checkpointer_manager.health_check()
                    
                    if health_ok:
                        print("✅ PostgreSQL checkpointer healthy, compiling graph...")
                        
                        # Crear un checkpointer duradero para la compilación
                        self.persistent_checkpointer = self.checkpointer_manager.get_sync_checkpointer()
                        self.app = self.graph.compile(checkpointer=self.persistent_checkpointer)
                        
                        print("✅ Graph compiled with PostgreSQL checkpointer")
                    else:
                        print("❌ PostgreSQL checkpointer unhealthy")
                        raise Exception("PostgreSQL checkpointer not healthy")
                        
                except Exception as e:
                    print(f"❌ Error in PostgreSQL initialization: {e}")
                    raise
            
            # Aplicar patches
            graph_module.EcommerceAssistantGraph.__init__ = patched_init
            graph_module.EcommerceAssistantGraph.initialize = patched_initialize
            
            print("🔧 Inicializando LangGraphChatbotService con PostgreSQL...")
            self.service = LangGraphChatbotService()
            await self.service.initialize()
            print("✅ Servicio inicializado con PostgreSQL checkpointer")
            
            # Test de conversación con persistencia
            message, contact = self.create_test_message("Hola, esta es una prueba con PostgreSQL checkpointer")
            
            print(f"👤 Enviando mensaje: {message.text.body}")
            response = await self.service.procesar_mensaje(message, contact)
            
            if response.status == "success":
                print(f"🤖 Respuesta: {response.message[:100]}...")
                print("✅ Conversación procesada exitosamente con PostgreSQL checkpointer")
                return True
            else:
                print("❌ Error procesando conversación")
                return False
                
        except Exception as e:
            print(f"❌ Error en integración con LangGraph: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def create_test_message(self, text: str) -> tuple[WhatsAppMessage, Contact]:
        """Crear mensaje de prueba"""
        message = WhatsAppMessage(
            from_=self.test_user,
            id=f"postgres_test_{int(asyncio.get_event_loop().time())}",
            type="text",
            timestamp=str(int(asyncio.get_event_loop().time())),
            text=TextMessage(body=text)
        )
        
        contact = Contact(
            wa_id=self.test_user,
            profile={"name": self.test_name}
        )
        
        return message, contact
    
    async def cleanup(self):
        """Limpiar recursos"""
        try:
            if self.service:
                await self.service.cleanup()
                
            if self.checkpointer_manager:
                await self.checkpointer_manager.close()
                
            print("🧹 Cleanup completado")
            
        except Exception as e:
            print(f"⚠️ Error en cleanup: {e}")

async def main():
    """Función principal"""
    print("🧪 TEST DE INTEGRACIÓN POSTGRESQL CHECKPOINTER")
    print("=" * 60)
    
    tester = PostgresCheckpointerTester()
    
    try:
        results = {}
        
        # Test 1: Health check básico
        print("\n🎯 FASE 1: Health Check")
        results["health"] = await tester.test_checkpointer_health()
        
        if not results["health"]:
            print("❌ No se puede continuar sin checkpointer funcionando")
            return
        
        # Test 2: Operaciones básicas
        print("\n🎯 FASE 2: Operaciones Básicas")
        results["operations"] = await tester.test_checkpointer_operations()
        
        # Test 3: Checkpointer monitoreado
        print("\n🎯 FASE 3: Checkpointer Monitoreado")
        results["monitored"] = await tester.test_monitored_checkpointer()
        
        # Test 4: Integración con LangGraph
        print("\n🎯 FASE 4: Integración con LangGraph")
        results["integration"] = await tester.test_with_langgraph_service()
        
        # Resumen final
        print("\n📊 RESUMEN FINAL")
        print("=" * 50)
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{test_name.upper()}: {status}")
        
        success_count = sum(results.values())
        total_tests = len(results)
        
        print(f"\nTotal: {success_count}/{total_tests} tests passed")
        
        if success_count == total_tests:
            print("\n🎉 TODOS LOS TESTS PASARON!")
            print("🔥 PostgreSQL checkpointer está funcionando correctamente")
        else:
            print(f"\n⚠️ {total_tests - success_count} tests fallaron")
            print("🔍 Revisar logs para más detalles")
        
    except Exception as e:
        print(f"❌ Error general en los tests: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())