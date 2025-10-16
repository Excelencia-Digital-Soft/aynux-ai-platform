-- Migration: Add pgvector support for semantic product search
-- Purpose: Enable native PostgreSQL vector similarity search for products
-- Author: Claude Code AI Assistant
-- Date: 2025-09-30

-- ============================================================================
-- Step 1: Install pgvector extension
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify extension installation
-- Run: SELECT * FROM pg_extension WHERE extname = 'vector';


-- ============================================================================
-- Step 2: Add embedding column to products table
-- ============================================================================
-- Using vector(1024) for nomic-embed-text model compatibility
-- Adjust dimension if using different embedding model
ALTER TABLE products
ADD COLUMN IF NOT EXISTS embedding vector(1024);

-- Add embedding metadata columns
ALTER TABLE products
ADD COLUMN IF NOT EXISTS last_embedding_update TIMESTAMP DEFAULT NULL,
ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(100) DEFAULT 'nomic-embed-text',
ADD COLUMN IF NOT EXISTS embedding_version INTEGER DEFAULT 1;

-- Add comment for documentation
COMMENT ON COLUMN products.embedding IS 'Vector embedding for semantic similarity search (1024 dimensions from nomic-embed-text)';
COMMENT ON COLUMN products.last_embedding_update IS 'Timestamp of last embedding generation/update';
COMMENT ON COLUMN products.embedding_model IS 'Name of the embedding model used (e.g., nomic-embed-text, mxbai-embed-large)';
COMMENT ON COLUMN products.embedding_version IS 'Version of embedding for cache invalidation';


-- ============================================================================
-- Step 3: Create HNSW index for fast similarity search
-- ============================================================================
-- HNSW (Hierarchical Navigable Small World) provides sub-100ms search
-- vector_cosine_ops uses cosine distance (most common for text embeddings)
CREATE INDEX IF NOT EXISTS idx_products_embedding_hnsw
ON products USING hnsw (embedding vector_cosine_ops);

-- Optional: Create IVFFlat index as alternative (faster build, slower search)
-- Uncomment if HNSW build time is too long for large datasets
-- CREATE INDEX IF NOT EXISTS idx_products_embedding_ivfflat
-- ON products USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);


-- ============================================================================
-- Step 4: Add helper functions for vector operations
-- ============================================================================

-- Function to calculate cosine similarity between product embeddings
CREATE OR REPLACE FUNCTION product_similarity(
    product_id_1 UUID,
    product_id_2 UUID
) RETURNS FLOAT AS $$
DECLARE
    similarity FLOAT;
BEGIN
    SELECT 1 - (p1.embedding <=> p2.embedding)
    INTO similarity
    FROM products p1, products p2
    WHERE p1.id = product_id_1
    AND p2.id = product_id_2
    AND p1.embedding IS NOT NULL
    AND p2.embedding IS NOT NULL;

    RETURN COALESCE(similarity, 0.0);
END;
$$ LANGUAGE plpgsql;

-- Function to find similar products with metadata filtering
CREATE OR REPLACE FUNCTION find_similar_products(
    query_embedding vector(1024),
    similarity_threshold FLOAT DEFAULT 0.7,
    max_results INTEGER DEFAULT 10,
    category_filter UUID DEFAULT NULL,
    brand_filter UUID DEFAULT NULL,
    min_price FLOAT DEFAULT NULL,
    max_price FLOAT DEFAULT NULL,
    require_stock BOOLEAN DEFAULT TRUE
) RETURNS TABLE (
    product_id UUID,
    product_name VARCHAR(255),
    similarity_score FLOAT,
    price FLOAT,
    stock INTEGER,
    category_name VARCHAR(200),
    brand_name VARCHAR(100)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.id,
        p.name,
        1 - (p.embedding <=> query_embedding) AS similarity,
        p.price,
        p.stock,
        c.display_name,
        b.name
    FROM products p
    LEFT JOIN categories c ON p.category_id = c.id
    LEFT JOIN brands b ON p.brand_id = b.id
    WHERE
        p.embedding IS NOT NULL
        AND p.active = TRUE
        AND (1 - (p.embedding <=> query_embedding)) >= similarity_threshold
        AND (category_filter IS NULL OR p.category_id = category_filter)
        AND (brand_filter IS NULL OR p.brand_id = brand_filter)
        AND (min_price IS NULL OR p.price >= min_price)
        AND (max_price IS NULL OR p.price <= max_price)
        AND (NOT require_stock OR p.stock > 0)
    ORDER BY similarity DESC
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- Step 5: Create trigger to auto-update embedding_version on product changes
-- ============================================================================
CREATE OR REPLACE FUNCTION update_embedding_version()
RETURNS TRIGGER AS $$
BEGIN
    -- Increment version when product content changes (requires re-embedding)
    IF (TG_OP = 'UPDATE' AND (
        OLD.name IS DISTINCT FROM NEW.name OR
        OLD.description IS DISTINCT FROM NEW.description OR
        OLD.specs IS DISTINCT FROM NEW.specs OR
        OLD.technical_specs IS DISTINCT FROM NEW.technical_specs
    )) THEN
        NEW.embedding_version := OLD.embedding_version + 1;
        NEW.last_embedding_update := NULL; -- Mark as needing update
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_embedding_version
BEFORE UPDATE ON products
FOR EACH ROW
EXECUTE FUNCTION update_embedding_version();


-- ============================================================================
-- Step 6: Create materialized view for embedding statistics
-- ============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS product_embedding_stats AS
SELECT
    COUNT(*) AS total_products,
    COUNT(embedding) AS products_with_embeddings,
    COUNT(*) FILTER (WHERE embedding IS NULL AND active = TRUE) AS missing_embeddings,
    COUNT(*) FILTER (WHERE last_embedding_update IS NULL AND embedding IS NOT NULL) AS stale_embeddings,
    AVG(EXTRACT(EPOCH FROM (NOW() - last_embedding_update)) / 3600) AS avg_hours_since_update,
    MIN(last_embedding_update) AS oldest_embedding_update,
    MAX(last_embedding_update) AS newest_embedding_update,
    COUNT(DISTINCT embedding_model) AS embedding_models_used
FROM products
WHERE active = TRUE;

-- Create index for faster refresh
CREATE UNIQUE INDEX IF NOT EXISTS idx_product_embedding_stats
ON product_embedding_stats (total_products);

-- Refresh function
CREATE OR REPLACE FUNCTION refresh_embedding_stats()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY product_embedding_stats;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- Step 7: Add indexes for common query patterns
-- ============================================================================
-- Index for filtering by embedding update status
CREATE INDEX IF NOT EXISTS idx_products_embedding_update
ON products (last_embedding_update)
WHERE embedding IS NOT NULL;

-- Index for finding products needing re-embedding
CREATE INDEX IF NOT EXISTS idx_products_stale_embeddings
ON products (embedding_version, last_embedding_update)
WHERE active = TRUE AND embedding IS NULL;

-- Composite index for common metadata filters with vector search
CREATE INDEX IF NOT EXISTS idx_products_category_brand_stock
ON products (category_id, brand_id, stock)
WHERE active = TRUE AND embedding IS NOT NULL;


-- ============================================================================
-- Step 8: Grant necessary permissions
-- ============================================================================
-- Grant usage on vector type to application user
-- Adjust username as needed (typically 'enzo' based on your setup)
-- GRANT USAGE ON TYPE vector TO enzo;
-- GRANT EXECUTE ON FUNCTION product_similarity(UUID, UUID) TO enzo;
-- GRANT EXECUTE ON FUNCTION find_similar_products(...) TO enzo;
-- GRANT SELECT ON product_embedding_stats TO enzo;


-- ============================================================================
-- Verification Queries
-- ============================================================================
-- Run these after migration to verify setup:

-- 1. Check extension installed
-- SELECT * FROM pg_extension WHERE extname = 'vector';

-- 2. Check columns added
-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'products' AND column_name IN ('embedding', 'last_embedding_update', 'embedding_model', 'embedding_version');

-- 3. Check indexes created
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename = 'products' AND indexname LIKE '%embedding%';

-- 4. Check functions created
-- SELECT proname, prosrc
-- FROM pg_proc
-- WHERE proname IN ('product_similarity', 'find_similar_products', 'update_embedding_version');

-- 5. Check embedding statistics
-- SELECT * FROM product_embedding_stats;

-- 6. Test vector operations
-- SELECT COUNT(*) AS products_with_embeddings FROM products WHERE embedding IS NOT NULL;
-- SELECT AVG(vector_dims(embedding)) AS avg_dimensions FROM products WHERE embedding IS NOT NULL;


-- ============================================================================
-- Rollback Instructions
-- ============================================================================
-- To rollback this migration, run in order:
-- DROP MATERIALIZED VIEW IF EXISTS product_embedding_stats CASCADE;
-- DROP TRIGGER IF EXISTS trigger_update_embedding_version ON products;
-- DROP FUNCTION IF EXISTS update_embedding_version();
-- DROP FUNCTION IF EXISTS find_similar_products(...);
-- DROP FUNCTION IF EXISTS product_similarity(UUID, UUID);
-- DROP INDEX IF EXISTS idx_products_embedding_hnsw;
-- DROP INDEX IF EXISTS idx_products_embedding_update;
-- DROP INDEX IF EXISTS idx_products_stale_embeddings;
-- DROP INDEX IF EXISTS idx_products_category_brand_stock;
-- ALTER TABLE products DROP COLUMN IF EXISTS embedding;
-- ALTER TABLE products DROP COLUMN IF EXISTS last_embedding_update;
-- ALTER TABLE products DROP COLUMN IF EXISTS embedding_model;
-- ALTER TABLE products DROP COLUMN IF EXISTS embedding_version;
-- DROP EXTENSION IF EXISTS vector CASCADE;