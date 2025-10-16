-- Migration: Create prompts management tables
-- Description: Adds tables for centralized prompt management system
-- Version: 002
-- Date: 2025-01-16

-- Create prompts table
CREATE TABLE IF NOT EXISTS prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    template TEXT NOT NULL,
    version VARCHAR(50) NOT NULL DEFAULT '1.0.0',
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_dynamic BOOLEAN NOT NULL DEFAULT false,
    meta_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255)
);

-- Create prompt_versions table
CREATE TABLE IF NOT EXISTS prompt_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_id UUID NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
    version VARCHAR(50) NOT NULL,
    template TEXT NOT NULL,
    performance_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),
    notes TEXT,
    meta_data JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Create indexes for prompts table
CREATE INDEX IF NOT EXISTS ix_prompts_key ON prompts(key);
CREATE INDEX IF NOT EXISTS ix_prompts_key_active ON prompts(key, is_active);
CREATE INDEX IF NOT EXISTS ix_prompts_is_dynamic ON prompts(is_dynamic);

-- Create indexes for prompt_versions table
CREATE INDEX IF NOT EXISTS ix_prompt_versions_prompt_id ON prompt_versions(prompt_id);
CREATE INDEX IF NOT EXISTS ix_prompt_versions_version ON prompt_versions(version);
CREATE INDEX IF NOT EXISTS ix_prompt_versions_active ON prompt_versions(is_active);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_prompts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for updated_at
CREATE TRIGGER trigger_prompts_updated_at
    BEFORE UPDATE ON prompts
    FOR EACH ROW
    EXECUTE FUNCTION update_prompts_updated_at();

-- Insert some initial prompts (examples)
INSERT INTO prompts (key, name, description, template, is_dynamic, meta_data) VALUES
(
    'intent.analyzer.system',
    'Intent Analyzer System Prompt',
    'System prompt for analyzing user intents in conversations',
    'You are an expert intent classifier for an e-commerce assistant.
Your task is to analyze the context and user message to identify a single primary intent.

Consider conversation history. A message like "what about this one?" depends completely on previous messages.
Use customer data to better understand their query.

ALWAYS return a valid JSON object in a single line, without explanations, intros, or markdown.',
    false,
    '{"temperature": 0.5, "max_tokens": 500}'::jsonb
),
(
    'product.search.intent_analysis',
    'Product Search Intent Analysis',
    'Analyzes user intention for product searches',
    '# ANÁLISIS DE INTENCIÓN DE PRODUCTO

## MENSAJE DEL USUARIO:
"{message}"

## CONTEXTO DEL USUARIO:
{user_context}

## INSTRUCCIONES:
Analiza la intención del usuario y responde en JSON con la siguiente estructura:
{
  "intent_type": "search_general|search_specific|comparison|availability_check|price_inquiry|category_browse|recommendation_request|specification_inquiry",
  "search_params": {...},
  "filters": {...},
  "query_complexity": "simple|medium|complex",
  "semantic_search_recommended": bool,
  "sql_generation_needed": bool
}',
    false,
    '{"temperature": 0.3, "max_tokens": 800}'::jsonb
);

-- Comments
COMMENT ON TABLE prompts IS 'Stores AI prompts for the system, both static and dynamic';
COMMENT ON TABLE prompt_versions IS 'Stores historical versions of prompts for versioning and A/B testing';
COMMENT ON COLUMN prompts.key IS 'Unique identifier for the prompt (e.g., "product.search.intent")';
COMMENT ON COLUMN prompts.is_dynamic IS 'True if prompt can be edited at runtime, false if loaded from file';
COMMENT ON COLUMN prompts.meta_data IS 'Additional configuration like temperature, max_tokens, model';
COMMENT ON COLUMN prompt_versions.performance_metrics IS 'Performance metrics for this prompt version';
