#!/usr/bin/env python3
"""
Test product queries directly using the product tool
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.agents.langgraph_system.tools.product_tool import ProductTool

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def test_product_tool():
    """Test the product tool with various queries"""
    tool = ProductTool()
    
    test_cases = [
        # General searches
        ("search", {"search_term": "celular"}),
        ("search", {"search_term": "zapatillas"}),
        ("search", {"search_term": "laptop"}),
        
        # Brand searches
        ("by_brand", {"brand": "Apple"}),
        ("by_brand", {"brand": "Nike"}),
        ("by_brand", {"brand": "Samsung"}),
        
        # Category searches
        ("by_category", {"category": "celulares"}),
        ("by_category", {"category": "zapatillas"}),
        ("by_category", {"category": "informatica"}),
        
        # Featured products
        ("featured", {"limit": 5}),
        
        # Specific product searches
        ("search", {"search_term": "iPhone 15"}),
        ("search", {"search_term": "Dell XPS"}),
        ("search", {"search_term": "Air Jordan"}),
    ]
    
    for method, params in test_cases:
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing: {method} with {params}")
        logger.info(f"{'='*60}")
        
        try:
            result = await tool(method, **params)
            
            if result["success"]:
                products = result.get("products", [])
                logger.info(f"Found {len(products)} products:")
                
                for product in products[:3]:  # Show first 3
                    logger.info(f"  - {product['name']} (${product['price']}) - Stock: {product['stock']}")
                
                if len(products) > 3:
                    logger.info(f"  ... and {len(products) - 3} more products")
            else:
                logger.warning(f"Search failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error in {method}: {e}")
        
        await asyncio.sleep(0.5)


async def main():
    """Main function"""
    logger.info("Testing product tool with new database content...\n")
    await test_product_tool()
    logger.info("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())