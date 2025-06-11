#!/usr/bin/env python3
"""
Script de inicialización del sistema LangGraph multi-agente
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.config.langgraph_config import get_langgraph_config
from app.services.langgraph_chatbot_service import LangGraphChatbotService


async def check_prerequisites():
    """Verifica que todos los prerequisitos estén instalados y configurados"""
    print("🔍 Checking prerequisites...")
    
    prerequisites = []
    
    # Verificar variables de entorno críticas
    required_env_vars = [
        'DATABASE_URL',
        'WHATSAPP_ACCESS_TOKEN',
        'WHATSAPP_VERIFY_TOKEN'
    ]
    
    for var in required_env_vars:
        if not os.getenv(var):
            prerequisites.append(f"❌ Missing environment variable: {var}")
        else:
            prerequisites.append(f"✅ {var} is configured")
    
    # Verificar dependencias opcionales
    optional_vars = [
        'OLLAMA_API_URL',
        'REDIS_URL',
        'CHROMADB_PATH'
    ]
    
    for var in optional_vars:
        if os.getenv(var):
            prerequisites.append(f"✅ {var} is configured")
        else:
            prerequisites.append(f"⚠️  {var} not configured (using defaults)")
    
    for msg in prerequisites:
        print(f"  {msg}")
    
    # Verificar si hay errores críticos
    critical_missing = [msg for msg in prerequisites if msg.startswith("❌")]
    if critical_missing:
        print("\n❌ Critical prerequisites missing. Please configure before continuing.")
        return False
    
    print("\n✅ Prerequisites check passed!")
    return True


async def test_database_connection():
    """Prueba la conexión a la base de datos"""
    print("\n🔍 Testing database connection...")
    
    try:
        from app.database import check_db_connection
        
        db_healthy = await check_db_connection()
        if db_healthy:
            print("✅ Database connection successful!")
            return True
        else:
            print("❌ Database connection failed!")
            return False
            
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False


async def test_ollama_connection():
    """Prueba la conexión a Ollama"""
    print("\n🔍 Testing Ollama connection...")
    
    try:
        from app.agents.langgraph_system.integrations.ollama_integration import OllamaIntegration
        
        ollama = OllamaIntegration()
        health_status = await ollama.comprehensive_test()
        
        if all(health_status.values()):
            print("✅ Ollama connection successful!")
            print(f"  Available models: {', '.join(health_status.get('available_models', []))}")
            return True
        else:
            print("⚠️  Ollama connection issues detected:")
            for test, status in health_status.items():
                icon = "✅" if status else "❌"
                print(f"    {icon} {test}")
            return False
            
    except Exception as e:
        print(f"❌ Ollama connection error: {e}")
        print("  Note: Ollama is optional but recommended for full functionality")
        return False


async def setup_chromadb():
    """Configura ChromaDB con colecciones básicas"""
    print("\n🔍 Setting up ChromaDB...")
    
    try:
        from app.agents.langgraph_system.integrations.chroma_integration import ChromaDBIntegration
        
        chroma = ChromaDBIntegration()
        
        # Configurar colecciones básicas
        collections_config = {
            "products": {
                "metadata": {"description": "Product catalog for e-commerce"}
            },
            "categories": {
                "metadata": {"description": "Product categories"}
            },
            "support_kb": {
                "metadata": {"description": "Support knowledge base"}
            },
            "faq": {
                "metadata": {"description": "Frequently asked questions"}
            }
        }
        
        results = await chroma.initialize_collections(collections_config)
        
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        print(f"✅ ChromaDB setup complete! ({success_count}/{total_count} collections initialized)")
        
        for collection, success in results.items():
            icon = "✅" if success else "❌"
            print(f"  {icon} {collection}")
        
        return True
        
    except Exception as e:
        print(f"❌ ChromaDB setup error: {e}")
        return False


async def test_langgraph_system():
    """Prueba la inicialización completa del sistema LangGraph"""
    print("\n🔍 Testing LangGraph system initialization...")
    
    try:
        # Crear instancia del servicio
        service = LangGraphChatbotService()
        
        # Inicializar
        await service.initialize()
        
        # Verificar health check
        health_status = await service.get_system_health()
        
        if health_status["overall_status"] == "healthy":
            print("✅ LangGraph system initialization successful!")
            
            # Mostrar estado de componentes
            print("  Component status:")
            for component, status in health_status.get("components", {}).items():
                comp_status = status.get("status", "unknown") if isinstance(status, dict) else status
                icon = "✅" if comp_status == "healthy" else "⚠️" if comp_status == "degraded" else "❌"
                print(f"    {icon} {component}: {comp_status}")
        else:
            print(f"⚠️  LangGraph system partially initialized (status: {health_status['overall_status']})")
            return False
        
        # Limpiar recursos
        await service.cleanup()
        
        return True
        
    except Exception as e:
        print(f"❌ LangGraph system initialization error: {e}")
        return False


async def run_test_conversation():
    """Ejecuta una conversación de prueba"""
    print("\n🔍 Running test conversation...")
    
    try:
        from app.models.message import Contact, WhatsAppMessage, TextMessage
        
        # Crear mensaje de prueba
        test_message = WhatsAppMessage(
            id="test_msg_001",
            type="text",
            timestamp="1234567890",
            text=TextMessage(body="Hola, necesito información sobre laptops")
        )
        
        test_contact = Contact(
            wa_id="5491234567890",
            profile={"name": "Usuario de Prueba"}
        )
        
        # Crear servicio y procesar mensaje
        service = LangGraphChatbotService()
        await service.initialize()
        
        result = await service.procesar_mensaje(test_message, test_contact)
        
        if result.status == "success":
            print("✅ Test conversation successful!")
            print(f"  Response: {result.message[:100]}...")
        else:
            print(f"❌ Test conversation failed: {result.message}")
            return False
        
        await service.cleanup()
        return True
        
    except Exception as e:
        print(f"❌ Test conversation error: {e}")
        return False


async def display_system_info():
    """Muestra información del sistema configurado"""
    print("\n📋 System Configuration:")
    
    try:
        config = get_langgraph_config()
        validation_results = config.validate_config()
        
        print(f"  🏗️  Architecture: Multi-agent LangGraph system")
        print(f"  🗄️  Database: {'✅ Configured' if validation_results.get('database') else '❌ Missing'}")
        print(f"  🤖 Ollama: {'✅ Configured' if validation_results.get('ollama') else '❌ Missing'}")
        print(f"  📱 WhatsApp: {'✅ Configured' if validation_results.get('whatsapp') else '❌ Missing'}")
        print(f"  🔒 Security: {'✅ Configured' if validation_results.get('security') else '⚠️  Using defaults'}")
        
        # Mostrar agentes habilitados
        agents_config = config.get_section("agents")
        enabled_agents = [agent for agent, conf in agents_config.items() if conf.get("enabled", True)]
        print(f"  🤖 Enabled Agents ({len(enabled_agents)}):")
        for agent in enabled_agents:
            print(f"    • {agent.replace('_', ' ').title()}")
        
    except Exception as e:
        print(f"❌ Error displaying system info: {e}")


async def main():
    """Función principal de inicialización"""
    print("🚀 LangGraph Multi-Agent System Initialization")
    print("=" * 50)
    
    # Configurar logging
    logging.basicConfig(level=logging.INFO)
    
    # Lista de pasos
    steps = [
        ("Prerequisites Check", check_prerequisites),
        ("Database Connection", test_database_connection),
        ("Ollama Connection", test_ollama_connection),
        ("ChromaDB Setup", setup_chromadb),
        ("LangGraph System", test_langgraph_system),
        ("Test Conversation", run_test_conversation)
    ]
    
    results = []
    
    for step_name, step_func in steps:
        try:
            result = await step_func()
            results.append((step_name, result))
            
            if not result and step_name in ["Prerequisites Check", "Database Connection"]:
                print(f"\n❌ Critical step '{step_name}' failed. Stopping initialization.")
                break
                
        except Exception as e:
            print(f"\n❌ Step '{step_name}' failed with error: {e}")
            results.append((step_name, False))
    
    # Mostrar resumen
    print("\n" + "=" * 50)
    print("📊 Initialization Summary:")
    
    for step_name, success in results:
        icon = "✅" if success else "❌"
        print(f"  {icon} {step_name}")
    
    successful_steps = sum(1 for _, success in results if success)
    total_steps = len(results)
    
    print(f"\n🎯 Success Rate: {successful_steps}/{total_steps} ({successful_steps/total_steps*100:.1f}%)")
    
    # Mostrar información del sistema
    await display_system_info()
    
    # Instrucciones finales
    print("\n" + "=" * 50)
    if successful_steps >= 4:  # Al menos prerequisitos, DB, y sistema básico
        print("🎉 System is ready for production!")
        print("\n📋 Next steps:")
        print("  1. Start your FastAPI server")
        print("  2. Set USE_LANGGRAPH=true environment variable")
        print("  3. Configure WhatsApp webhook URL")
        print("  4. Monitor system health at /webhook/health")
        print("\n🔗 Useful endpoints:")
        print("  • Health check: GET /webhook/health")
        print("  • Conversation history: GET /webhook/conversation/{user_number}")
        print("  • Switch service: POST /webhook/switch-service")
    else:
        print("⚠️  System initialization incomplete!")
        print("  Please resolve the failed steps before production use.")
        print("  The system will fall back to traditional mode if needed.")


if __name__ == "__main__":
    asyncio.run(main())