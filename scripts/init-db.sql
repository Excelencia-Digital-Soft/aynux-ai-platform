-- =============================================================================
-- Aynux Database Initialization Script
-- This script runs automatically when PostgreSQL container starts
-- =============================================================================

-- Enable pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify extension is loaded
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE NOTICE 'pgvector extension enabled successfully';
    ELSE
        RAISE EXCEPTION 'Failed to enable pgvector extension';
    END IF;
END $$;

-- Create additional useful extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For trigram similarity (text search)
CREATE EXTENSION IF NOT EXISTS unaccent; -- For accent-insensitive search

-- =============================================================================
-- Create schemas for domain separation
-- =============================================================================

-- Core schema: System tables (auth, tenancy, configuration, shared knowledge)
CREATE SCHEMA IF NOT EXISTS core;

-- Ecommerce schema: E-commerce domain (products, customers, orders)
CREATE SCHEMA IF NOT EXISTS ecommerce;

-- Healthcare schema: Healthcare domain (patients, doctors, appointments)
CREATE SCHEMA IF NOT EXISTS healthcare;

-- Credit schema: Credit/finance domain (accounts, payments)
CREATE SCHEMA IF NOT EXISTS credit;

-- Grant permissions on schemas to current user
GRANT ALL ON SCHEMA core TO CURRENT_USER;
GRANT ALL ON SCHEMA ecommerce TO CURRENT_USER;
GRANT ALL ON SCHEMA healthcare TO CURRENT_USER;
GRANT ALL ON SCHEMA credit TO CURRENT_USER;

-- Create Alembic version table in public schema
CREATE TABLE IF NOT EXISTS public.alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Verify schemas are created
DO $$
DECLARE
    schema_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO schema_count
    FROM information_schema.schemata
    WHERE schema_name IN ('core', 'ecommerce', 'healthcare', 'credit');

    IF schema_count = 4 THEN
        RAISE NOTICE 'All schemas created successfully: core, ecommerce, healthcare, credit';
    ELSE
        RAISE EXCEPTION 'Failed to create all schemas. Expected 4, found %', schema_count;
    END IF;
END $$;

-- Log completion
DO $$ BEGIN RAISE NOTICE 'Database initialization completed with multi-schema architecture'; END $$;
