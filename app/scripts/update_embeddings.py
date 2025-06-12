#!/usr/bin/env python3
"""
Script to update product embeddings from the database
Can be run manually or scheduled with cron
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.database import init_db
from app.services.embedding_update_service import EmbeddingUpdateService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Main function to update embeddings"""
    try:
        logger.info("Starting embedding update process...")
        
        # Initialize database
        await init_db()
        
        # Create service instance
        service = EmbeddingUpdateService()
        
        # Check if specific product ID was provided
        if len(sys.argv) > 1:
            try:
                product_id = int(sys.argv[1])
                logger.info(f"Updating embeddings for product ID: {product_id}")
                await service.update_product_embeddings(product_id=product_id)
            except ValueError:
                logger.error("Invalid product ID provided")
                sys.exit(1)
        else:
            # Update all products
            logger.info("Updating embeddings for all products...")
            await service.update_all_embeddings()
        
        # Print statistics
        stats = service.get_collection_stats()
        logger.info("Embedding update completed. Collection statistics:")
        for category, count in stats.items():
            logger.info(f"  {category}: {count} documents")
        
        logger.info("Process completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during embedding update: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())