-- Migración 004: Ajustar dimensión de embeddings de 1024 a 768
-- Fecha: 2025-10-17
-- Razón: nomic-embed-text:v1.5 genera embeddings de 768 dimensiones
-- Autor: Sistema de migración automática

BEGIN;

-- 1. Eliminar índice HNSW existente
DROP INDEX IF EXISTS idx_products_embedding_hnsw;

-- 2. Eliminar columna de embeddings antigua
ALTER TABLE products DROP COLUMN IF EXISTS embedding CASCADE;

-- 3. Agregar columna con dimensión correcta (768)
ALTER TABLE products ADD COLUMN embedding vector(768);

-- 4. Agregar columnas de tracking si no existen
ALTER TABLE products
  ADD COLUMN IF NOT EXISTS last_embedding_update TIMESTAMP,
  ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(100) DEFAULT 'nomic-embed-text:v1.5';

-- 5. Recrear índice HNSW optimizado para 768 dimensiones
-- Parámetros HNSW: m=16 (número de conexiones), ef_construction=64 (calidad del índice)
CREATE INDEX idx_products_embedding_hnsw
  ON products
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- 6. Agregar comentarios descriptivos
COMMENT ON COLUMN products.embedding IS
  'Vector embedding (768-dim) for semantic search using nomic-embed-text:v1.5';
COMMENT ON COLUMN products.embedding_model IS
  'Embedding model name (e.g., nomic-embed-text:v1.5, mxbai-embed-large)';
COMMENT ON COLUMN products.last_embedding_update IS
  'Timestamp of last embedding generation/update';

-- 7. Verificar que la extensión pgvector está activa
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'vector'
    ) THEN
        RAISE EXCEPTION 'pgvector extension is not installed. Please install it first.';
    END IF;
END $$;

COMMIT;

-- Nota: Los embeddings existentes se invalidan con este cambio.
-- Usar el servicio de actualización de embeddings para regenerarlos:
-- POST /api/v1/admin/embeddings/batch-update
