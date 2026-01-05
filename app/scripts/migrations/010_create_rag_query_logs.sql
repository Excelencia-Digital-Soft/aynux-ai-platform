-- ============================================================================
-- Migration: Create RAG Query Logs Table
-- Description: Table for storing RAG query analytics and metrics
-- Schema: core
-- ============================================================================

-- Create RAG query logs table for analytics
CREATE TABLE IF NOT EXISTS core.rag_query_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Query and response data
    query TEXT NOT NULL,
    context_used JSONB NOT NULL DEFAULT '[]'::jsonb,
    response TEXT NOT NULL,

    -- Performance metrics
    token_count INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    relevance_score NUMERIC(4,3) CHECK (relevance_score IS NULL OR (relevance_score >= 0 AND relevance_score <= 1)),

    -- User feedback
    user_feedback VARCHAR(10) CHECK (user_feedback IN ('positive', 'negative')),

    -- Context
    agent_key VARCHAR(255),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add comments
COMMENT ON TABLE core.rag_query_logs IS 'Stores RAG query logs for analytics and monitoring';
COMMENT ON COLUMN core.rag_query_logs.query IS 'The user query text';
COMMENT ON COLUMN core.rag_query_logs.context_used IS 'JSON array of document IDs or titles used as context';
COMMENT ON COLUMN core.rag_query_logs.response IS 'The generated response text';
COMMENT ON COLUMN core.rag_query_logs.token_count IS 'Number of tokens used in the response';
COMMENT ON COLUMN core.rag_query_logs.latency_ms IS 'Response latency in milliseconds';
COMMENT ON COLUMN core.rag_query_logs.relevance_score IS 'Relevance score between 0 and 1';
COMMENT ON COLUMN core.rag_query_logs.user_feedback IS 'User feedback: positive or negative';
COMMENT ON COLUMN core.rag_query_logs.agent_key IS 'The agent that processed this query';

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_rag_logs_created_at ON core.rag_query_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rag_logs_latency ON core.rag_query_logs(latency_ms);
CREATE INDEX IF NOT EXISTS idx_rag_logs_agent_key ON core.rag_query_logs(agent_key) WHERE agent_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_rag_logs_feedback ON core.rag_query_logs(user_feedback) WHERE user_feedback IS NOT NULL;

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION core.update_rag_query_logs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_rag_query_logs_updated_at ON core.rag_query_logs;
CREATE TRIGGER trigger_update_rag_query_logs_updated_at
    BEFORE UPDATE ON core.rag_query_logs
    FOR EACH ROW
    EXECUTE FUNCTION core.update_rag_query_logs_updated_at();

-- ============================================================================
-- Verification
-- ============================================================================
-- SELECT * FROM core.rag_query_logs LIMIT 5;
-- SELECT COUNT(*) FROM core.rag_query_logs;
