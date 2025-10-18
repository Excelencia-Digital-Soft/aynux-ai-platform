"""
Migration script: ChromaDB → pgvector (SYNC VERSION)

Uses psycopg2 (synchronous) instead of asyncpg to avoid greenlet issues when running in background.

Usage:
    python app/scripts/migrate_chroma_to_pgvector_sync.py [options]

Options:
    --dry-run: Show migration plan without making changes
    --batch-size N: Process N products per batch (default: 50)
    --force: Force re-embedding even if embeddings exist
    --verify: Verify migration integrity after completion
"""

import argparse
import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, List
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.agents.integrations.chroma_integration import ChromaDBIntegration
from app.agents.integrations.ollama_integration import OllamaIntegration
from app.config.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


class SyncChromaToPgVectorMigration:
    """Synchronous migration handler from ChromaDB to pgvector using psycopg2."""

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

        # Initialize settings
        self.settings = get_settings()

        # Initialize integrations
        self.ollama = OllamaIntegration()
        self.embeddings = self.ollama.get_embeddings(model="mxbai-embed-large:latest")

        chroma_path = os.path.join(self.settings.OLLAMA_API_CHROMADB, "products", "all_products")
        self.chroma = ChromaDBIntegration(chroma_path)
        self.chroma_collection = "products_all_products"

        # Database connection string
        self.db_url = self._build_db_url()

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

    def _build_db_url(self) -> str:
        """Build PostgreSQL connection URL."""
        if self.settings.DB_PASSWORD:
            return (
                f"dbname={self.settings.DB_NAME} "
                f"user={self.settings.DB_USER} "
                f"password={self.settings.DB_PASSWORD} "
                f"host={self.settings.DB_HOST} "
                f"port={self.settings.DB_PORT}"
            )
        return (
            f"dbname={self.settings.DB_NAME} "
            f"user={self.settings.DB_USER} "
            f"host={self.settings.DB_HOST} "
            f"port={self.settings.DB_PORT}"
        )

    def _get_connection(self):
        """Get a new database connection."""
        return psycopg2.connect(self.db_url)

    def run(self) -> Dict[str, int]:
        """
        Execute migration.

        Returns:
            Migration statistics dictionary
        """
        logger.info("=" * 80)
        logger.info("ChromaDB → pgvector Migration (SYNC VERSION)")
        logger.info("=" * 80)

        if self.dry_run:
            logger.warning("DRY RUN MODE: No changes will be made")

        self.stats["start_time"] = datetime.now()

        try:
            # Step 1: Pre-flight checks
            logger.info("\n[Step 1/6] Running pre-flight checks...")
            if not self._preflight_checks():
                logger.error("Pre-flight checks failed. Aborting migration.")
                return self.stats

            # Step 2: Analyze current state
            logger.info("\n[Step 2/6] Analyzing current state...")
            self._analyze_current_state()

            # Step 3: Build migration plan
            logger.info("\n[Step 3/6] Building migration plan...")
            migration_plan = self._build_migration_plan()

            if not migration_plan:
                logger.info("No products need migration. Exiting.")
                return self.stats

            # Step 4: Execute migration
            if not self.dry_run:
                logger.info(f"\n[Step 4/6] Migrating {len(migration_plan)} products...")
                self._execute_migration(migration_plan)
            else:
                logger.info(f"\n[Step 4/6] Would migrate {len(migration_plan)} products (DRY RUN)")
                self.stats["skipped"] = len(migration_plan)

            # Step 5: Verify migration
            if self.verify and not self.dry_run:
                logger.info("\n[Step 5/6] Verifying migration integrity...")
                self._verify_migration()
            else:
                logger.info("\n[Step 5/6] Skipping verification (DRY RUN or disabled)")

            # Step 6: Report results
            logger.info("\n[Step 6/6] Migration complete!")
            self._generate_report()

            self.stats["end_time"] = datetime.now()
            return self.stats

        except Exception as e:
            logger.error(f"Migration failed with error: {e}", exc_info=True)
            self.stats["end_time"] = datetime.now()
            return self.stats

    def _preflight_checks(self) -> bool:
        """Run pre-flight checks before migration."""
        checks_passed = True

        # Check 1: pgvector extension installed
        logger.info("  Checking pgvector extension...")
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'")
                    result = cur.fetchone()
                    count = result[0] if result else 0
                    if count == 0:
                        logger.error("  ✗ pgvector extension not installed")
                        checks_passed = False
                    else:
                        logger.info("  ✓ pgvector extension available")
        except Exception as e:
            logger.error(f"  ✗ Database connection failed: {e}")
            checks_passed = False

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

        # Check 3: Ollama embeddings available
        logger.info("  Checking Ollama embeddings model...")
        try:
            test_embedding = self.embeddings.embed_query("test")
            if len(test_embedding) == 1024:
                logger.info("  ✓ Ollama embeddings working (1024 dimensions)")
            else:
                logger.error(f"  ✗ Unexpected embedding dimensions: {len(test_embedding)}")
                checks_passed = False
        except Exception as e:
            logger.error(f"  ✗ Ollama embeddings not available: {e}")
            checks_passed = False

        return checks_passed

    def _analyze_current_state(self) -> None:
        """Analyze current state of embeddings."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Count total products
                cur.execute("SELECT COUNT(*) FROM products WHERE active = true")
                result = cur.fetchone()
                self.stats["total_products"] = result[0] if result else 0

                # Count products with embeddings
                cur.execute("SELECT COUNT(*) FROM products WHERE active = true AND embedding IS NOT NULL")
                result = cur.fetchone()
                self.stats["products_with_pgvector_embeddings"] = result[0] if result else 0

        # Get ChromaDB stats
        chroma_stats = self.chroma.get_collection_stats(self.chroma_collection)
        self.stats["products_with_chroma_embeddings"] = chroma_stats.get("document_count", 0)

        logger.info(f"  Total products in database: {self.stats['total_products']}")
        logger.info(f"  Products with ChromaDB embeddings: {self.stats['products_with_chroma_embeddings']}")
        logger.info(f"  Products with pgvector embeddings: {self.stats['products_with_pgvector_embeddings']}")

        missing_embeddings = self.stats["total_products"] - self.stats["products_with_pgvector_embeddings"]
        logger.info(f"  Products missing pgvector embeddings: {missing_embeddings}")

    def _build_migration_plan(self) -> List[str]:
        """
        Build list of product IDs to migrate.

        Returns:
            List of product IDs (as strings) needing migration
        """
        migration_plan = []

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Query products needing embeddings
                if self.force:
                    cur.execute("SELECT id, name FROM products WHERE active = true")
                else:
                    cur.execute("SELECT id, name FROM products WHERE active = true AND embedding IS NULL")

                products = cur.fetchall()

                for product in products:
                    migration_plan.append(str(product["id"]))

                    if len(migration_plan) <= 10:  # Show first 10 in log
                        logger.info(f"  - {product['name']} ({product['id']})")

                if len(migration_plan) > 10:
                    logger.info(f"  ... and {len(migration_plan) - 10} more products")

        return migration_plan

    def _execute_migration(self, product_ids: List[str]) -> None:
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
                try:
                    product_id = UUID(product_id_str)

                    # Update embedding
                    success = self._update_product_embedding(product_id)

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

    def _update_product_embedding(self, product_id: UUID) -> bool:
        """
        Update embedding for a specific product.

        Args:
            product_id: Product UUID

        Returns:
            True if update successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Fetch product
                    cur.execute(
                        """
                        SELECT p.id, p.name, p.model, p.description, p.specs,
                               p.technical_specs, p.features,
                               c.display_name as category_name, b.name as brand_name
                        FROM products p
                        LEFT JOIN categories c ON p.category_id = c.id
                        LEFT JOIN brands b ON p.brand_id = b.id
                        WHERE p.id = %s
                        """,
                        (str(product_id),),
                    )
                    product = cur.fetchone()

                    if not product:
                        logger.warning(f"Product {product_id} not found")
                        return False

                    # Check if embedding exists and not forcing update
                    if not self.force:
                        cur.execute("SELECT embedding FROM products WHERE id = %s", (str(product_id),))
                        existing = cur.fetchone()
                        if existing and existing["embedding"] is not None:
                            logger.debug(f"Product {product_id} already has embedding, skipping")
                            return True

                    # Generate embedding text
                    embedding_text = self._create_embedding_text(product)

                    # Generate embedding using sync API
                    start_time = time.perf_counter()
                    embedding = self.embeddings.embed_query(embedding_text)
                    duration_ms = (time.perf_counter() - start_time) * 1000

                    if not embedding or all(v == 0.0 for v in embedding):
                        logger.error(f"Failed to generate valid embedding for product {product_id}")
                        return False

                    # Update product with new embedding
                    cur.execute(
                        """
                        UPDATE products
                        SET embedding = %s::vector,
                            last_embedding_update = %s,
                            embedding_model = %s
                        WHERE id = %s
                        """,
                        (embedding, datetime.now(UTC), "mxbai-embed-large:latest", str(product_id)),
                    )

                    conn.commit()

                    logger.debug(f"Updated embedding for product {product_id} in {duration_ms:.1f}ms")
                    return True

        except Exception as e:
            logger.error(f"Error updating product embedding {product_id}: {e}")
            return False

    def _create_embedding_text(self, product: dict) -> str:
        """
        Create comprehensive text representation for embedding generation.

        Args:
            product: Product record from database

        Returns:
            Combined text for embedding
        """
        parts = []

        # Product name (highest weight)
        if product.get("name"):
            parts.append(f"Product: {product['name']}")

        # Brand
        if product.get("brand_name"):
            parts.append(f"Brand: {product['brand_name']}")

        # Category
        if product.get("category_name"):
            parts.append(f"Category: {product['category_name']}")

        # Model
        if product.get("model"):
            parts.append(f"Model: {product['model']}")

        # Description
        if product.get("description"):
            desc = product["description"][:500] if len(product["description"]) > 500 else product["description"]
            parts.append(f"Description: {desc}")

        # Specs
        if product.get("specs"):
            specs = product["specs"][:300] if len(product["specs"]) > 300 else product["specs"]
            parts.append(f"Specifications: {specs}")

        # Technical specs (JSONB)
        if product.get("technical_specs") and isinstance(product["technical_specs"], dict):
            specs_text = ", ".join(f"{k}: {v}" for k, v in product["technical_specs"].items() if v)
            if specs_text:
                parts.append(f"Technical: {specs_text}")

        # Features (JSONB array)
        if product.get("features") and isinstance(product["features"], list):
            features_text = ", ".join(str(f) for f in product["features"] if f)
            if features_text:
                parts.append(f"Features: {features_text}")

        return ". ".join(parts)

    def _verify_migration(self) -> None:
        """Verify migration integrity."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Count final embeddings
                cur.execute("SELECT COUNT(*) FROM products WHERE active = true AND embedding IS NOT NULL")
                result = cur.fetchone()
                final_embeddings = result[0] if result else 0

                logger.info(f"  Products with pgvector embeddings after migration: {final_embeddings}")
                logger.info(
                    f"  Expected embeddings: {
                        self.stats['successfully_migrated'] + self.stats['products_with_pgvector_embeddings']
                    }"
                )

                # Spot check: Query a few products to verify embeddings
                logger.info("  Running spot checks on random products...")

                cur.execute("SELECT id, name FROM products WHERE embedding IS NOT NULL ORDER BY RANDOM() LIMIT 5")
                products = cur.fetchall()

                for _, product_name in products:
                    logger.info(f"  ✓ {product_name} has valid embedding")

    def _generate_report(self) -> None:
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
        logger.info("2. Monitor pgvector performance metrics")
        logger.info("3. Test semantic search with real user queries")
        logger.info("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Migrate ChromaDB embeddings to pgvector (SYNC)")

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
    migration = SyncChromaToPgVectorMigration(
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        force=args.force,
        verify=not args.no_verify,
    )

    stats = migration.run()

    # Exit code based on results
    if stats["errors"] > 0:
        logger.error(f"Migration completed with {stats['errors']} errors")
        sys.exit(1)
    else:
        logger.info("Migration completed successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
