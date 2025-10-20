-- Migration: Create company_knowledge table for corporate knowledge base
-- Purpose: Store company information with vector embeddings for RAG-enabled search
-- Author: Claude Code AI Assistant
-- Date: 2025-01-20
-- Dependencies: Requires pgvector extension (from migration 001)

-- ============================================================================
-- Step 1: Verify pgvector extension is installed
-- ============================================================================
-- This should already be installed from migration 001
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE EXCEPTION 'pgvector extension not installed. Run migration 001 first.';
    END IF;
END $$;


-- ============================================================================
-- Step 2: Create document_type enum
-- ============================================================================
DO $$ BEGIN
    CREATE TYPE document_type_enum AS ENUM (
        'mission_vision',    -- Misión, visión y valores
        'contact_info',      -- Información de contacto y redes sociales
        'software_catalog',  -- Catálogo de software y módulos
        'faq',               -- Preguntas frecuentes
        'clients',           -- Información de clientes actuales
        'success_stories',   -- Casos de éxito
        'general'            -- Información general
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;


-- ============================================================================
-- Step 3: Create company_knowledge table
-- ============================================================================
CREATE TABLE IF NOT EXISTS company_knowledge (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Document content
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,

    -- Categorization
    document_type document_type_enum NOT NULL,
    category VARCHAR(200),
    tags TEXT[],

    -- Metadata (renamed to meta_data to avoid conflicts)
    meta_data JSONB DEFAULT '{}'::jsonb,

    -- Status
    active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,

    -- Vector embeddings (1024 dimensions for nomic-embed-text)
    embedding vector(1024),

    -- Full-text search
    search_vector TSVECTOR,

    -- Timestamps
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

-- Add table comments
COMMENT ON TABLE company_knowledge IS 'Corporate knowledge base with vector embeddings for semantic search';
COMMENT ON COLUMN company_knowledge.title IS 'Document title';
COMMENT ON COLUMN company_knowledge.content IS 'Full document content in markdown/plain text';
COMMENT ON COLUMN company_knowledge.document_type IS 'Type of document for categorization';
COMMENT ON COLUMN company_knowledge.category IS 'Secondary category for finer classification';
COMMENT ON COLUMN company_knowledge.tags IS 'Tags for flexible categorization and filtering';
COMMENT ON COLUMN company_knowledge.meta_data IS 'Flexible metadata storage (author, source, version, etc.)';
COMMENT ON COLUMN company_knowledge.active IS 'Whether this document is active and searchable';
COMMENT ON COLUMN company_knowledge.embedding IS 'Vector embedding (1024-dim) for semantic similarity search';
COMMENT ON COLUMN company_knowledge.search_vector IS 'Full-text search vector (auto-generated from title + content)';
COMMENT ON COLUMN company_knowledge.sort_order IS 'Order for displaying documents (lower = first)';


-- ============================================================================
-- Step 4: Create indexes for fast queries
-- ============================================================================

-- Basic indexes for common queries
CREATE INDEX IF NOT EXISTS idx_knowledge_type_active
ON company_knowledge (document_type, active);

CREATE INDEX IF NOT EXISTS idx_knowledge_category
ON company_knowledge (category)
WHERE category IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_knowledge_active
ON company_knowledge (active);

CREATE INDEX IF NOT EXISTS idx_knowledge_sort
ON company_knowledge (sort_order);

-- HNSW index for fast vector similarity search
-- Parameters optimized for knowledge base (typically < 1000 documents)
CREATE INDEX IF NOT EXISTS idx_knowledge_embedding_hnsw
ON company_knowledge
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- GIN index for full-text search
CREATE INDEX IF NOT EXISTS idx_knowledge_search_vector
ON company_knowledge
USING gin (search_vector);

-- GIN index for tags array
CREATE INDEX IF NOT EXISTS idx_knowledge_tags
ON company_knowledge
USING gin (tags);

-- GIN index for JSONB metadata
CREATE INDEX IF NOT EXISTS idx_knowledge_meta_data
ON company_knowledge
USING gin (meta_data);


-- ============================================================================
-- Step 5: Create trigger to auto-update search_vector
-- ============================================================================
CREATE OR REPLACE FUNCTION update_knowledge_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    -- Auto-generate search_vector from title and content
    -- Spanish configuration for better text search
    NEW.search_vector :=
        setweight(to_tsvector('spanish', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('spanish', COALESCE(NEW.content, '')), 'B');

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_knowledge_search_vector
BEFORE INSERT OR UPDATE OF title, content ON company_knowledge
FOR EACH ROW
EXECUTE FUNCTION update_knowledge_search_vector();


-- ============================================================================
-- Step 6: Create trigger to auto-update updated_at timestamp
-- ============================================================================
CREATE OR REPLACE FUNCTION update_knowledge_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_knowledge_timestamp
BEFORE UPDATE ON company_knowledge
FOR EACH ROW
EXECUTE FUNCTION update_knowledge_updated_at();


-- ============================================================================
-- Step 7: Create helper functions for knowledge base operations
-- ============================================================================

-- Function to find similar knowledge documents
CREATE OR REPLACE FUNCTION find_similar_knowledge(
    query_embedding vector(1024),
    similarity_threshold FLOAT DEFAULT 0.7,
    max_results INTEGER DEFAULT 5,
    document_type_filter document_type_enum DEFAULT NULL,
    category_filter VARCHAR(200) DEFAULT NULL,
    tags_filter TEXT[] DEFAULT NULL,
    active_only BOOLEAN DEFAULT TRUE
) RETURNS TABLE (
    knowledge_id UUID,
    title VARCHAR(500),
    content TEXT,
    document_type document_type_enum,
    category VARCHAR(200),
    tags TEXT[],
    similarity_score FLOAT,
    meta_data JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        k.id,
        k.title,
        k.content,
        k.document_type,
        k.category,
        k.tags,
        1 - (k.embedding <=> query_embedding) AS similarity,
        k.meta_data
    FROM company_knowledge k
    WHERE
        k.embedding IS NOT NULL
        AND (NOT active_only OR k.active = TRUE)
        AND (1 - (k.embedding <=> query_embedding)) >= similarity_threshold
        AND (document_type_filter IS NULL OR k.document_type = document_type_filter)
        AND (category_filter IS NULL OR k.category = category_filter)
        AND (tags_filter IS NULL OR k.tags && tags_filter)  -- Array overlap operator
    ORDER BY similarity DESC, k.sort_order ASC
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION find_similar_knowledge IS 'Search knowledge base using vector similarity with optional filters';


-- Function for hybrid search (vector + full-text)
CREATE OR REPLACE FUNCTION search_knowledge_hybrid(
    query_text TEXT,
    query_embedding vector(1024),
    max_results INTEGER DEFAULT 10,
    vector_weight FLOAT DEFAULT 0.7,
    text_weight FLOAT DEFAULT 0.3,
    similarity_threshold FLOAT DEFAULT 0.5,
    document_type_filter document_type_enum DEFAULT NULL
) RETURNS TABLE (
    knowledge_id UUID,
    title VARCHAR(500),
    content TEXT,
    document_type document_type_enum,
    combined_score FLOAT,
    vector_similarity FLOAT,
    text_rank FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        k.id,
        k.title,
        k.content,
        k.document_type,
        (vector_weight * (1 - (k.embedding <=> query_embedding)) +
         text_weight * ts_rank(k.search_vector, plainto_tsquery('spanish', query_text))) AS score,
        1 - (k.embedding <=> query_embedding) AS vec_sim,
        ts_rank(k.search_vector, plainto_tsquery('spanish', query_text)) AS txt_rank
    FROM company_knowledge k
    WHERE
        k.active = TRUE
        AND k.embedding IS NOT NULL
        AND k.search_vector IS NOT NULL
        AND (1 - (k.embedding <=> query_embedding)) >= similarity_threshold
        AND (document_type_filter IS NULL OR k.document_type = document_type_filter)
    ORDER BY score DESC
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION search_knowledge_hybrid IS 'Hybrid search combining vector similarity and full-text search with weighted scoring';


-- ============================================================================
-- Step 8: Create materialized view for knowledge base statistics
-- ============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS knowledge_base_stats AS
SELECT
    COUNT(*) AS total_documents,
    COUNT(*) FILTER (WHERE active = TRUE) AS active_documents,
    COUNT(embedding) AS documents_with_embeddings,
    COUNT(*) FILTER (WHERE embedding IS NULL AND active = TRUE) AS missing_embeddings,
    COUNT(DISTINCT document_type) AS document_types,
    COUNT(DISTINCT category) AS categories,
    jsonb_object_agg(
        document_type::text,
        (SELECT COUNT(*) FROM company_knowledge WHERE document_type = k.document_type)
    ) AS documents_by_type,
    MAX(updated_at) AS last_update,
    MIN(created_at) AS oldest_document
FROM company_knowledge k
GROUP BY ();  -- Aggregate all rows

-- Create unique index for concurrent refresh
CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_stats_unique
ON knowledge_base_stats (total_documents);

-- Refresh function
CREATE OR REPLACE FUNCTION refresh_knowledge_stats()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY knowledge_base_stats;
END;
$$ LANGUAGE plpgsql;

COMMENT ON MATERIALIZED VIEW knowledge_base_stats IS 'Statistics about knowledge base documents and embeddings';


-- ============================================================================
-- Step 9: Grant permissions (adjust username as needed)
-- ============================================================================
-- Grant permissions to application user (typically 'enzo' in this setup)
-- Uncomment and adjust if needed:
-- GRANT SELECT, INSERT, UPDATE, DELETE ON company_knowledge TO enzo;
-- GRANT EXECUTE ON FUNCTION find_similar_knowledge(...) TO enzo;
-- GRANT EXECUTE ON FUNCTION search_knowledge_hybrid(...) TO enzo;
-- GRANT SELECT ON knowledge_base_stats TO enzo;


-- ============================================================================
-- Verification Queries
-- ============================================================================
-- Run these after migration to verify setup:

-- 1. Check table created
-- SELECT table_name, table_type
-- FROM information_schema.tables
-- WHERE table_name = 'company_knowledge';

-- 2. Check columns
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'company_knowledge'
-- ORDER BY ordinal_position;

-- 3. Check indexes
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename = 'company_knowledge';

-- 4. Check functions
-- SELECT proname, pg_get_functiondef(oid)
-- FROM pg_proc
-- WHERE proname LIKE '%knowledge%';

-- 5. Check triggers
-- SELECT trigger_name, event_manipulation, event_object_table
-- FROM information_schema.triggers
-- WHERE event_object_table = 'company_knowledge';

-- 6. Check statistics view
-- SELECT * FROM knowledge_base_stats;


-- ============================================================================
-- Rollback Instructions
-- ============================================================================
-- To rollback this migration, run in order:
-- DROP MATERIALIZED VIEW IF EXISTS knowledge_base_stats CASCADE;
-- DROP FUNCTION IF EXISTS refresh_knowledge_stats();
-- DROP FUNCTION IF EXISTS search_knowledge_hybrid(...);
-- DROP FUNCTION IF EXISTS find_similar_knowledge(...);
-- DROP TRIGGER IF EXISTS trigger_update_knowledge_timestamp ON company_knowledge;
-- DROP TRIGGER IF EXISTS trigger_update_knowledge_search_vector ON company_knowledge;
-- DROP FUNCTION IF EXISTS update_knowledge_updated_at();
-- DROP FUNCTION IF EXISTS update_knowledge_search_vector();
-- DROP INDEX IF EXISTS idx_knowledge_metadata;
-- DROP INDEX IF EXISTS idx_knowledge_tags;
-- DROP INDEX IF EXISTS idx_knowledge_search_vector;
-- DROP INDEX IF EXISTS idx_knowledge_embedding_hnsw;
-- DROP INDEX IF EXISTS idx_knowledge_sort;
-- DROP INDEX IF EXISTS idx_knowledge_active;
-- DROP INDEX IF EXISTS idx_knowledge_category;
-- DROP INDEX IF EXISTS idx_knowledge_type_active;
-- DROP TABLE IF EXISTS company_knowledge CASCADE;
-- DROP TYPE IF EXISTS document_type_enum CASCADE;
