#!/usr/bin/env python3
"""
Test simple para diagnosticar problemas
"""
import os
import sys
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.append(str(Path(__file__).parent))

# Configurar variables de entorno mínimas
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["USE_LANGGRAPH"] = "true"
os.environ["WHATSAPP_ACCESS_TOKEN"] = "test_token"
os.environ["WHATSAPP_VERIFY_TOKEN"] = "test_verify_token"
os.environ["WHATSAPP_PHONE_NUMBER_ID"] = "123456789"
os.environ["META_APP_ID"] = "test_app_id"
os.environ["META_APP_SECRET"] = "test_app_secret"

print("🔍 Diagnóstico del Sistema LangGraph")
print("=" * 50)

# Test 1: Imports básicos
print("1. Probando imports básicos...")
try:
    from app.config.settings import get_settings
    print("   ✅ Settings importados correctamente")
except Exception as e:
    print(f"   ❌ Error en settings: {e}")
    sys.exit(1)

try:
    from app.config.langgraph_config import get_langgraph_config
    print("   ✅ LangGraph config importado correctamente")
except Exception as e:
    print(f"   ❌ Error en langgraph config: {e}")
    sys.exit(1)

# Test 2: Configuración
print("\n2. Probando configuración...")
try:
    config = get_langgraph_config()
    validation = config.validate_config()
    print(f"   ✅ Configuración validada: {validation}")
except Exception as e:
    print(f"   ❌ Error en configuración: {e}")

# Test 3: Imports de integraciones
print("\n3. Probando imports de integraciones...")
try:
    from app.agents.langgraph_system.integrations.ollama_integration import OllamaIntegration
    print("   ✅ Ollama integration importado")
except Exception as e:
    print(f"   ❌ Error en Ollama integration: {e}")

try:
    from app.agents.langgraph_system.integrations.chroma_integration import ChromaDBIntegration
    print("   ✅ ChromaDB integration importado")
except Exception as e:
    print(f"   ❌ Error en ChromaDB integration: {e}")

try:
    from app.agents.langgraph_system.integrations.postgres_integration import PostgreSQLIntegration
    print("   ✅ PostgreSQL integration importado")
except Exception as e:
    print(f"   ❌ Error en PostgreSQL integration: {e}")

# Test 4: Sistema principal
print("\n4. Probando sistema principal...")
try:
    from app.services.langgraph_chatbot_service import LangGraphChatbotService
    print("   ✅ LangGraph chatbot service importado")
except Exception as e:
    print(f"   ❌ Error en chatbot service: {e}")

# Test 5: Crear instancia básica
print("\n5. Probando instanciación básica...")
try:
    service = LangGraphChatbotService()
    print("   ✅ Servicio instanciado correctamente")
except Exception as e:
    print(f"   ❌ Error instanciando servicio: {e}")

print("\n✅ Diagnóstico completado")