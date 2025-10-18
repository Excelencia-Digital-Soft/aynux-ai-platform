-- Migration: Add embedding column to products table
-- Description: Adds vector embedding column for pgvector semantic search
-- Version: 003
-- Date: 2025-10-16

-- Add embedding column (1024 dimensions for nomic-embed-text)
ALTER TABLE products
ADD COLUMN IF NOT EXISTS embedding vector(1024);

-- Create HNSW index for fast similarity search
-- Parameters:
--   m=16: Number of connections per layer (balance between speed and recall)
--   ef_construction=64: Size of dynamic candidate list for construction
CREATE INDEX IF NOT EXISTS idx_products_embedding_hnsw
ON products
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Add comment for documentation
COMMENT ON COLUMN products.embedding IS 'Vector embedding (1024-dim) for semantic search using pgvector with nomic-embed-text model';

-- Verify the changes
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'products'
  AND column_name = 'embedding';

-- Verify the index
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'products'
  AND indexname = 'idx_products_embedding_hnsw';
