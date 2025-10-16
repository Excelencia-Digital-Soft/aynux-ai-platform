"""
Migration script: ChromaDB → pgvector

Migrates existing product embeddings from ChromaDB to PostgreSQL pgvector,
enabling native SQL vector search with better performance and integration.

Usage:
    python app/scripts/migrate_chroma_to_pgvector.py [options]

Options:
    --dry-run: Show migration plan without making changes
    --batch-size N: Process N products per batch (default: 50)
    --force: Force re-embedding even if embeddings exist
    --verify: Verify migration integrity after completion
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.integrations.chroma_integration import ChromaDBIntegration
from app.agents.integrations.pgvector_integration import PgVectorIntegration
from app.config.settings import get_settings
from app.database.async_db import get_async_db_context
from app.models.db import Product

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


class ChromaToPgVectorMigration:
    """Handles migration from ChromaDB to pgvector."""

    def __init__(
        self,
        dry_run: bool = False,
        batch_size: int = 50,
        force: bool = False,
        verify: bool = True,
    ):
        """
        Initialize migration.

        Args:
            dry_run: Show plan without making changes
            batch_size: Number of products per batch
            force: Force re-embedding even if exists
            verify: Verify migration integrity
        """
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.force = force
        self.verify = verify

        # Initialize integrations
        settings = get_settings()
        self.pgvector = PgVectorIntegration()

        chroma_path = os.path.join(settings.OLLAMA_API_CHROMADB, "products", "all_products")
        self.chroma = ChromaDBIntegration(chroma_path)
        self.chroma_collection = "products_all_products"

        # Migration statistics
        self.stats = {
            "total_products": 0,
            "products_with_chroma_embeddings": 0,
            "products_with_pgvector_embeddings": 0,
            "successfully_migrated": 0,
            "skipped": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
        }

    async def run(self) -> Dict[str, int]:
        """
        Execute migration.

        Returns:
            Migration statistics dictionary
        """
        logger.info("=" * 80)
        logger.info("ChromaDB → pgvector Migration")
        logger.info("=" * 80)

        if self.dry_run:
            logger.warning("DRY RUN MODE: No changes will be made")

        self.stats["start_time"] = datetime.now()

        try:
            # Step 1: Pre-flight checks
            logger.info("\n[Step 1/6] Running pre-flight checks...")
            if not await self._preflight_checks():
                logger.error("Pre-flight checks failed. Aborting migration.")
                return self.stats

            # Step 2: Analyze current state
            logger.info("\n[Step 2/6] Analyzing current state...")
            await self._analyze_current_state()

            # Step 3: Build migration plan
            logger.info("\n[Step 3/6] Building migration plan...")
            migration_plan = await self._build_migration_plan()

            if not migration_plan:
                logger.info("No products need migration. Exiting.")
                return self.stats

            # Step 4: Execute migration
            if not self.dry_run:
                logger.info(f"\n[Step 4/6] Migrating {len(migration_plan)} products...")
                await self._execute_migration(migration_plan)
            else:
                logger.info(f"\n[Step 4/6] Would migrate {len(migration_plan)} products (DRY RUN)")
                self.stats["skipped"] = len(migration_plan)

            # Step 5: Verify migration
            if self.verify and not self.dry_run:
                logger.info("\n[Step 5/6] Verifying migration integrity...")
                await self._verify_migration()
            else:
                logger.info("\n[Step 5/6] Skipping verification (DRY RUN or disabled)")

            # Step 6: Report results
            logger.info("\n[Step 6/6] Migration complete!")
            await self._generate_report()

            self.stats["end_time"] = datetime.now()
            return self.stats

        except Exception as e:
            logger.error(f"Migration failed with error: {e}", exc_info=True)
            self.stats["end_time"] = datetime.now()
            return self.stats

    async def _preflight_checks(self) -> bool:
        """Run pre-flight checks before migration."""
        checks_passed = True

        # Check 1: pgvector extension installed
        logger.info("  Checking pgvector extension...")
        pgvector_healthy = await self.pgvector.health_check()
        if not pgvector_healthy:
            logger.error("  ✗ pgvector extension not available")
            checks_passed = False
        else:
            logger.info("  ✓ pgvector extension available")

        # Check 2: ChromaDB accessible
        logger.info("  Checking ChromaDB accessibility...")
        try:
            chroma_collections = self.chroma.list_collections()
            if self.chroma_collection not in chroma_collections:
                logger.error(f"  ✗ ChromaDB collection '{self.chroma_collection}' not found")
                checks_passed = False
            else:
                logger.info(f"  ✓ ChromaDB collection '{self.chroma_collection}' found")
        except Exception as e:
            logger.error(f"  ✗ ChromaDB not accessible: {e}")
            checks_passed = False

        # Check 3: Database connectivity
        logger.info("  Checking database connectivity...")
        try:
            async with get_async_db_context() as db:
                result = await db.execute(select(Product.id).limit(1))
                result.scalar()
                logger.info("  ✓ Database connection successful")
        except Exception as e:
            logger.error(f"  ✗ Database connection failed: {e}")
            checks_passed = False

        return checks_passed

    async def _analyze_current_state(self) -> None:
        """Analyze current state of embeddings."""
        # Get pgvector stats
        pgvector_stats = await self.pgvector.get_embedding_statistics()
        self.stats["total_products"] = pgvector_stats.get("total_products", 0)
        self.stats["products_with_pgvector_embeddings"] = pgvector_stats.get("products_with_embeddings", 0)

        # Get ChromaDB stats
        chroma_stats = self.chroma.get_collection_stats(self.chroma_collection)
        self.stats["products_with_chroma_embeddings"] = chroma_stats.get("document_count", 0)

        logger.info(f"  Total products in database: {self.stats['total_products']}")
        logger.info(f"  Products with ChromaDB embeddings: {self.stats['products_with_chroma_embeddings']}")
        logger.info(f"  Products with pgvector embeddings: {self.stats['products_with_pgvector_embeddings']}")

        missing_embeddings = (
            self.stats["total_products"] - self.stats["products_with_pgvector_embeddings"]
        )
        logger.info(f"  Products missing pgvector embeddings: {missing_embeddings}")

    async def _build_migration_plan(self) -> List[str]:
        """
        Build list of product IDs to migrate.

        Returns:
            List of product IDs (as strings) needing migration
        """
        migration_plan = []

        async with get_async_db_context() as db:
            # Query products needing embeddings
            query = select(Product.id, Product.name).where(Product.active.is_(True))

            if not self.force:
                # Only products without pgvector embeddings
                query = query.where(Product.embedding.is_(None))

            result = await db.execute(query)
            products = result.all()

            for product_id, product_name in products:
                migration_plan.append(str(product_id))

                if len(migration_plan) <= 10:  # Show first 10 in log
                    logger.info(f"  - {product_name} ({product_id})")

            if len(migration_plan) > 10:
                logger.info(f"  ... and {len(migration_plan) - 10} more products")

        return migration_plan

    async def _execute_migration(self, product_ids: List[str]) -> None:
        """
        Execute migration for products.

        Args:
            product_ids: List of product IDs to migrate
        """
        total_products = len(product_ids)

        for i in range(0, total_products, self.batch_size):
            batch = product_ids[i : i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (total_products + self.batch_size - 1) // self.batch_size

            logger.info(f"  Processing batch {batch_num}/{total_batches} ({len(batch)} products)...")

            for product_id_str in batch:
                from uuid import UUID

                try:
                    product_id = UUID(product_id_str)

                    # Update embedding using pgvector integration
                    success = await self.pgvector.update_product_embedding(
                        product_id=product_id,
                        force_update=self.force,
                    )

                    if success:
                        self.stats["successfully_migrated"] += 1
                    else:
                        self.stats["skipped"] += 1

                except Exception as e:
                    logger.error(f"  Error migrating product {product_id_str}: {e}")
                    self.stats["errors"] += 1

            # Progress update
            processed = min(i + self.batch_size, total_products)
            progress_pct = (processed / total_products) * 100
            logger.info(
                f"  Progress: {processed}/{total_products} ({progress_pct:.1f}%) - "
                f"Migrated: {self.stats['successfully_migrated']}, "
                f"Errors: {self.stats['errors']}"
            )

    async def _verify_migration(self) -> None:
        """Verify migration integrity."""
        # Get updated stats
        pgvector_stats = await self.pgvector.get_embedding_statistics()
        final_embeddings = pgvector_stats.get("products_with_embeddings", 0)

        logger.info(f"  Products with pgvector embeddings after migration: {final_embeddings}")
        logger.info(f"  Expected embeddings: {self.stats['successfully_migrated'] + self.stats['products_with_pgvector_embeddings']}")

        # Spot check: Query a few products to verify embeddings
        logger.info("  Running spot checks on random products...")

        async with get_async_db_context() as db:
            result = await db.execute(
                select(Product.id, Product.name)
                .where(Product.embedding.isnot(None))
                .limit(5)
            )
            products = result.all()

            for product_id, product_name in products:
                logger.info(f"  ✓ {product_name} has valid embedding")

    async def _generate_report(self) -> None:
        """Generate migration summary report."""
        logger.info("\n" + "=" * 80)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 80)

        # Time taken
        if self.stats["start_time"] and self.stats["end_time"]:
            duration = self.stats["end_time"] - self.stats["start_time"]
            logger.info(f"Duration: {duration.total_seconds():.2f} seconds")

        # Results
        logger.info(f"\nTotal products: {self.stats['total_products']}")
        logger.info(f"Successfully migrated: {self.stats['successfully_migrated']}")
        logger.info(f"Skipped: {self.stats['skipped']}")
        logger.info(f"Errors: {self.stats['errors']}")

        # Coverage
        if self.stats["total_products"] > 0:
            coverage_pct = (
                (self.stats["products_with_pgvector_embeddings"] + self.stats["successfully_migrated"])
                / self.stats["total_products"]
                * 100
            )
            logger.info(f"\nFinal pgvector coverage: {coverage_pct:.1f}%")

        # Recommendations
        logger.info("\nNext Steps:")
        logger.info("1. Verify search quality with test queries")
        logger.info("2. Update environment variables:")
        logger.info("   USE_PGVECTOR=true")
        logger.info("   PRODUCT_SEARCH_STRATEGY=pgvector_primary")
        logger.info("3. Monitor LangSmith for search quality metrics")
        logger.info("4. Consider keeping ChromaDB as fallback initially")
        logger.info("=" * 80)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Migrate ChromaDB embeddings to pgvector")

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show migration plan without making changes",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of products to process per batch (default: 50)",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-embedding even if embeddings exist",
    )

    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip verification step after migration",
    )

    args = parser.parse_args()

    # Create and run migration
    migration = ChromaToPgVectorMigration(
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        force=args.force,
        verify=not args.no_verify,
    )

    stats = await migration.run()

    # Exit code based on results
    if stats["errors"] > 0:
        logger.error(f"Migration completed with {stats['errors']} errors")
        sys.exit(1)
    else:
        logger.info("Migration completed successfully")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())