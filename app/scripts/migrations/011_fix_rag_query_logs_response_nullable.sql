-- ============================================================================
-- Migration: Fix RAG Query Logs Response Nullable
-- Description: Make response column nullable to allow logging before response generation
-- Schema: core
-- ============================================================================

-- Fix: Make response column nullable as safety measure
-- The ORM model already has nullable=True, this aligns the DB schema
ALTER TABLE core.rag_query_logs ALTER COLUMN response DROP NOT NULL;

-- Add comment explaining the change
COMMENT ON COLUMN core.rag_query_logs.response IS 'Generated response text (nullable - may be logged before response generation)';

-- ============================================================================
-- Verification
-- ============================================================================
-- SELECT column_name, is_nullable FROM information_schema.columns
-- WHERE table_schema = 'core' AND table_name = 'rag_query_logs' AND column_name = 'response';
