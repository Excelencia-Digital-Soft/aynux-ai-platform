#!/usr/bin/env python3
"""
Simple test script for the new products
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.agents.langgraph_system.graph import EcommerceAssistantGraph
from app.config.langgraph_config import get_langgraph_config

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def test_simple():
    """Simple test of the graph"""
    config = get_langgraph_config()
    graph = EcommerceAssistantGraph(config)
    await graph.initialize()
    
    test_queries = [
        "¿qué productos tienes?",
        "muéstrame celulares",
        "zapatillas Nike",
        "precio del iPhone 15",
    ]
    
    for query in test_queries:
        logger.info(f"\n{'='*50}")
        logger.info(f"Query: {query}")
        logger.info(f"{'='*50}")
        
        try:
            result = await graph.process_message_stream("test_user", query, {})
            async for update in result:
                if update.get("messages"):
                    for msg in update["messages"]:
                        if msg.get("content"):
                            logger.info(f"Response: {msg['content']}")
                            
        except Exception as e:
            logger.error(f"Error: {e}")
        
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(test_simple())