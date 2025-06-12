#!/usr/bin/env python3
"""
Script para probar el health check del sistema LangGraph
"""

import asyncio
import json
import logging
from pprint import pprint

from app.agents.langgraph_system.graph import EcommerceAssistantGraph
from app.config.langgraph_config import get_langgraph_config
from app.services.langgraph_chatbot_service import LangGraphChatbotService

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_health_check():
    """Prueba el health check del sistema"""
    
    print("="*80)
    print("🏥 PRUEBA DE HEALTH CHECK DEL SISTEMA LANGGRAPH")
    print("="*80)
    
    try:
        # Test 1: Health check directo del EcommerceAssistantGraph
        print("\n🔍 Test 1: Health Check del EcommerceAssistantGraph")
        print("-" * 50)
        
        config = get_langgraph_config()
        graph = EcommerceAssistantGraph(config.model_dump())
        await graph.initialize()
        
        health_status = await graph.health_check()
        
        print(f"Estado general: {health_status['overall_status']}")
        print(f"Timestamp: {health_status['timestamp']}")
        
        # Mostrar componentes
        print("\n📊 Estado de Componentes:")
        for component, status in health_status["components"].items():
            if isinstance(status, dict):
                component_status = status.get("status", "unknown")
                print(f"  • {component}: {component_status}")
            else:
                print(f"  • {component}: {status}")
        
        # Mostrar métricas
        print(f"\n📈 Métricas:")
        metrics = health_status.get("metrics", {})
        for metric, value in metrics.items():
            print(f"  • {metric}: {value}")
        
        # Mostrar errores si existen
        if health_status.get("errors"):
            print(f"\n⚠️ Errores detectados:")
            for error in health_status["errors"]:
                print(f"  • {error}")
        else:
            print("\n✅ No se detectaron errores")
        
        print("\n" + "="*50)
        print("🎯 JSON completo del health check:")
        print("="*50)
        print(json.dumps(health_status, indent=2, ensure_ascii=False))
        
    except Exception as e:
        logger.error(f"Error en Test 1: {e}")
        print(f"❌ Error en Test 1: {e}")
    
    try:
        # Test 2: Health check a través del LangGraphChatbotService
        print("\n\n🔍 Test 2: Health Check del LangGraphChatbotService")
        print("-" * 50)
        
        service = LangGraphChatbotService()
        await service.initialize()
        
        service_health = await service.get_system_health()
        
        print(f"Estado del servicio: {service_health.get('overall_status', 'unknown')}")
        
        if isinstance(service_health, dict):
            print("\n📊 Detalles del servicio:")
            print(json.dumps(service_health, indent=2, ensure_ascii=False))
        else:
            print(f"Estado simple: {service_health}")
        
    except Exception as e:
        logger.error(f"Error en Test 2: {e}")
        print(f"❌ Error en Test 2: {e}")
    
    try:
        # Test 3: Simular health check de API
        print("\n\n🔍 Test 3: Simulación del Health Check de API")
        print("-" * 50)
        
        # Esto simula lo que haría el endpoint de la API
        service = LangGraphChatbotService()
        await service.initialize()
        
        health_status = await service.get_system_health()
        
        # Simular la lógica del endpoint
        overall_status = health_status.get("overall_status", "unknown") if isinstance(health_status, dict) else ("healthy" if health_status else "unhealthy")
        
        api_response = {
            "service_type": "langgraph",
            "status": overall_status,
            "details": health_status
        }
        
        print("📡 Respuesta simulada de la API:")
        print(json.dumps(api_response, indent=2, ensure_ascii=False))
        
        # Verificar que funciona como se espera
        if overall_status in ["healthy", "degraded"]:
            print("✅ API response: Sistema operativo")
        else:
            print("⚠️ API response: Sistema con problemas")
            
    except Exception as e:
        logger.error(f"Error en Test 3: {e}")
        print(f"❌ Error en Test 3: {e}")
    
    print("\n" + "="*80)
    print("🏁 PRUEBAS DE HEALTH CHECK COMPLETADAS")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(test_health_check())