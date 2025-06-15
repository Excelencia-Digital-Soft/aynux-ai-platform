#!/usr/bin/env python3
"""
Script to test the new products with the chatbot
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.langgraph_chatbot_service import LangGraphChatbotService
from app.models.message import WhatsAppMessage, Contact

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def test_queries():
    """Test various product queries"""
    service = LangGraphChatbotService()
    
    test_queries = [
        # General product queries
        "¿qué productos tienes?",
        "muéstrame todos los productos",
        
        # Category specific
        "¿qué celulares tienen?",
        "muéstrame zapatillas",
        "laptops disponibles",
        
        # Specific brands
        "productos de Apple",
        "¿tienen productos Samsung?",
        "zapatillas Nike",
        
        # Specific products
        "iPhone 15 Pro Max",
        "¿tienes Dell XPS?",
        "Air Jordan 1",
        
        # Stock and pricing
        "¿cuánto cuesta el iPhone 15?",
        "stock de zapatillas Adidas",
        "precio de laptops gaming",
    ]
    
    user_id = "test_5491234567890"
    
    for i, query in enumerate(test_queries, 1):
        logger.info(f"\n{'='*50}")
        logger.info(f"Test {i}: {query}")
        logger.info(f"{'='*50}")
        
        try:
            # Create WhatsApp message and contact objects
            whatsapp_message = WhatsAppMessage(
                id=f"msg_{i}",
                from_number=user_id,
                text=query,
                timestamp=1699000000 + i  # Mock timestamp
            )
            
            contact = Contact(
                profile={"name": "Test User"},
                wa_id=user_id
            )
            
            response = await service.process_webhook_message(whatsapp_message, contact)
            logger.info(f"Response: {response.text}")
        except Exception as e:
            logger.error(f"Error processing query '{query}': {e}")
        
        # Small delay between requests
        await asyncio.sleep(1)


async def main():
    """Main function"""
    logger.info("Testing new products with chatbot...\n")
    await test_queries()
    logger.info("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())