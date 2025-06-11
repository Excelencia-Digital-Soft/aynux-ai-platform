#!/usr/bin/env python3
"""
Quick test to verify main fixes
"""
import asyncio
import sys
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.append(str(Path(__file__).parent))

from app.agents.langgraph_system.integrations.ollama_integration import OllamaIntegration
from app.models.message import WhatsAppMessage, TextMessage, Contact

async def test_ollama_embeddings():
    """Test that OllamaEmbeddings works without validation errors"""
    try:
        ollama = OllamaIntegration()
        embeddings = ollama.get_embeddings()
        
        # Test embedding generation
        test_vector = await embeddings.aembed_query("test message")
        
        print(f"✅ OllamaEmbeddings test passed - vector dimension: {len(test_vector)}")
        return True
    except Exception as e:
        print(f"❌ OllamaEmbeddings test failed: {e}")
        return False

def test_whatsapp_message():
    """Test that WhatsAppMessage validation works"""
    try:
        # Test with required 'from' field
        message = WhatsAppMessage(
            from_="5491234567890",
            id="test_msg_001",
            type="text",
            timestamp="1698765432",
            text=TextMessage(body="Hola, test message")
        )
        
        contact = Contact(
            wa_id="5491234567890",
            profile={"name": "Test User"}
        )
        
        print("✅ WhatsAppMessage validation test passed")
        return True
    except Exception as e:
        print(f"❌ WhatsAppMessage validation test failed: {e}")
        return False

async def main():
    """Run quick tests"""
    print("🧪 Running quick tests to verify fixes...\n")
    
    # Test 1: WhatsApp Message validation
    result1 = test_whatsapp_message()
    
    # Test 2: OllamaEmbeddings
    result2 = await test_ollama_embeddings()
    
    print(f"\n📊 Results:")
    print(f"   WhatsApp Message validation: {'PASS' if result1 else 'FAIL'}")
    print(f"   OllamaEmbeddings integration: {'PASS' if result2 else 'FAIL'}")
    
    overall_success = result1 and result2
    print(f"\n🎯 Overall result: {'✅ SUCCESS' if overall_success else '❌ SOME ISSUES REMAIN'}")
    
    return overall_success

if __name__ == "__main__":
    asyncio.run(main())