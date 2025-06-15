#!/usr/bin/env python3
"""
Script to fix intent routing issues and clear cache
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.agents.langgraph_system.integrations.ollama_integration import OllamaIntegration
from app.agents.langgraph_system.intelligence.intent_router import IntentRouter
from app.config.settings import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def test_intent_routing():
    """Test intent routing with various queries"""
    settings = get_settings()
    
    # Initialize components
    ollama = OllamaIntegration()
    router = IntentRouter(ollama=ollama, config={"cache_size": 100, "cache_ttl": 60})

    # Clear the cache first
    logger.info("Clearing intent cache...")
    router.clear_cache()

    # Test queries
    test_queries = [
        # Product-related queries
        "que productos tienes?",
        "¿qué productos tienen disponibles?",
        "muéstrame los productos",
        "quiero ver productos",
        "lista de productos",
        
        # Specific product queries
        "¿tienen stock del iphone 15?",
        "¿cuánto cuesta el laptop Dell?",
        "características del Samsung Galaxy",
        
        # Category queries
        "muéstrame zapatillas",
        "busco televisores",
        "productos de tecnología",
        
        # Accessory queries
        "que accesorios tienes?",
        "¿qué periféricos tienen?",
    ]

    logger.info("\nTesting intent routing for various queries:\n")
    
    for query in test_queries:
        result = await router.analyze_intent_with_llm(query, {})
        logger.info(
            f"Query: '{query}'\n"
            f"  Intent: {result['primary_intent']}\n"
            f"  Agent: {result['target_agent']}\n"
            f"  Confidence: {result['confidence']:.2f}\n"
        )

    # Show cache stats
    stats = router.get_cache_stats()
    logger.info(f"\nCache stats: {stats}")


async def clear_all_caches():
    """Clear all relevant caches"""
    import redis

    settings = get_settings()
    
    # Clear Redis cache
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        
        # Clear all WhatsApp session keys
        for key in redis_client.scan_iter("whatsapp:*"):
            redis_client.delete(key)
            
        # Clear all intent cache keys if any
        for key in redis_client.scan_iter("intent:*"):
            redis_client.delete(key)
            
        logger.info("Redis cache cleared successfully")
    except Exception as e:
        logger.error(f"Error clearing Redis cache: {e}")

    # Clear LangGraph intent router cache
    ollama = OllamaIntegration()
    router = IntentRouter(ollama=ollama)
    router.clear_cache()
    logger.info("Intent router cache cleared")


async def main():
    """Main function"""
    logger.info("Starting intent routing fix...\n")
    
    # Clear all caches
    await clear_all_caches()
    
    # Test intent routing
    await test_intent_routing()
    
    logger.info("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())