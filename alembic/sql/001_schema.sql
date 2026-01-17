--
-- PostgreSQL database dump
--

\restrict gflMi0N2lGHJKsNAjdS9HdjmtZrH90ezD93aabqOQYTrW5KCKdOPnsRs9zXGcnw

-- Dumped from database version 18.1 (Debian 18.1-1.pgdg12+2)
-- Dumped by pg_dump version 18.1 (Debian 18.1-1.pgdg12+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: core; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA core;


--
-- Name: credit; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA credit;


--
-- Name: ecommerce; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA ecommerce;


--
-- Name: healthcare; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA healthcare;


--
-- Name: pharmacy; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA pharmacy;


--
-- Name: soporte; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA soporte;


--
-- Name: SCHEMA soporte; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA soporte IS 'Support/Incidents management schema with Jira integration';


--
-- Name: soporte_comment_author_type_enum; Type: TYPE; Schema: soporte; Owner: -
--

CREATE TYPE soporte.soporte_comment_author_type_enum AS ENUM (
    'user',
    'agent',
    'system'
);


--
-- Name: soporte_incident_impact_enum; Type: TYPE; Schema: soporte; Owner: -
--

CREATE TYPE soporte.soporte_incident_impact_enum AS ENUM (
    'individual',
    'group',
    'department',
    'organization'
);


--
-- Name: soporte_incident_priority_enum; Type: TYPE; Schema: soporte; Owner: -
--

CREATE TYPE soporte.soporte_incident_priority_enum AS ENUM (
    'low',
    'medium',
    'high',
    'critical'
);


--
-- Name: soporte_incident_source_enum; Type: TYPE; Schema: soporte; Owner: -
--

CREATE TYPE soporte.soporte_incident_source_enum AS ENUM (
    'whatsapp',
    'email',
    'phone',
    'web'
);


--
-- Name: soporte_incident_status_enum; Type: TYPE; Schema: soporte; Owner: -
--

CREATE TYPE soporte.soporte_incident_status_enum AS ENUM (
    'draft',
    'open',
    'in_progress',
    'pending_info',
    'resolved',
    'closed'
);


--
-- Name: soporte_incident_type_enum; Type: TYPE; Schema: soporte; Owner: -
--

CREATE TYPE soporte.soporte_incident_type_enum AS ENUM (
    'incident',
    'feedback',
    'question',
    'suggestion'
);


--
-- Name: soporte_incident_urgency_enum; Type: TYPE; Schema: soporte; Owner: -
--

CREATE TYPE soporte.soporte_incident_urgency_enum AS ENUM (
    'low',
    'medium',
    'high'
);


--
-- Name: soporte_jira_sync_status_enum; Type: TYPE; Schema: soporte; Owner: -
--

CREATE TYPE soporte.soporte_jira_sync_status_enum AS ENUM (
    'pending',
    'synced',
    'error',
    'manual'
);


--
-- Name: agent_knowledge_search_vector_trigger(); Type: FUNCTION; Schema: core; Owner: -
--

CREATE FUNCTION core.agent_knowledge_search_vector_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('spanish', COALESCE(NEW.title, '')), 'A') ||
                setweight(to_tsvector('spanish', COALESCE(NEW.content, '')), 'B');
            RETURN NEW;
        END;
        $$;


--
-- Name: agent_knowledge_updated_at_trigger(); Type: FUNCTION; Schema: core; Owner: -
--

CREATE FUNCTION core.agent_knowledge_updated_at_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$;


--
-- Name: update_rag_query_logs_updated_at(); Type: FUNCTION; Schema: core; Owner: -
--

CREATE FUNCTION core.update_rag_query_logs_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: calculate_sla_deadlines(); Type: FUNCTION; Schema: soporte; Owner: -
--

CREATE FUNCTION soporte.calculate_sla_deadlines() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    category_record RECORD;
BEGIN
    -- Get SLA hours from category
    IF NEW.category_id IS NOT NULL THEN
        SELECT sla_response_hours, sla_resolution_hours
        INTO category_record
        FROM soporte.incident_categories
        WHERE id = NEW.category_id;

        IF FOUND THEN
            NEW.sla_response_due := NEW.created_at + (category_record.sla_response_hours || ' hours')::INTERVAL;
            NEW.sla_resolution_due := NEW.created_at + (category_record.sla_resolution_hours || ' hours')::INTERVAL;
        END IF;
    END IF;

    -- Default SLA if no category
    IF NEW.sla_response_due IS NULL THEN
        NEW.sla_response_due := NEW.created_at + INTERVAL '24 hours';
    END IF;
    IF NEW.sla_resolution_due IS NULL THEN
        NEW.sla_resolution_due := NEW.created_at + INTERVAL '72 hours';
    END IF;

    RETURN NEW;
END;
$$;


--
-- Name: cleanup_expired_pending_tickets(); Type: FUNCTION; Schema: soporte; Owner: -
--

CREATE FUNCTION soporte.cleanup_expired_pending_tickets() RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM soporte.pending_tickets
    WHERE is_active = TRUE AND expires_at < NOW();

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;


--
-- Name: generate_incident_folio(); Type: FUNCTION; Schema: soporte; Owner: -
--

CREATE FUNCTION soporte.generate_incident_folio() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    year_part VARCHAR(4);
    sequence_num INTEGER;
    new_folio VARCHAR(20);
BEGIN
    -- Get current year
    year_part := EXTRACT(YEAR FROM NOW())::VARCHAR;

    -- Get next sequence number for this year
    SELECT COALESCE(MAX(
        CAST(SUBSTRING(folio FROM 'INC-' || year_part || '-(\d+)') AS INTEGER)
    ), 0) + 1
    INTO sequence_num
    FROM soporte.incidents
    WHERE folio LIKE 'INC-' || year_part || '-%';

    -- Generate folio: INC-2024-00001
    new_folio := 'INC-' || year_part || '-' || LPAD(sequence_num::VARCHAR, 5, '0');

    NEW.folio := new_folio;
    RETURN NEW;
END;
$$;


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: soporte; Owner: -
--

CREATE FUNCTION soporte.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: agent_knowledge; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.agent_knowledge (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    agent_key character varying(100) NOT NULL,
    title character varying(500) NOT NULL,
    content text NOT NULL,
    document_type character varying(50) DEFAULT 'general'::character varying NOT NULL,
    category character varying(200),
    tags character varying[] DEFAULT '{}'::character varying[],
    meta_data jsonb DEFAULT '{}'::jsonb,
    active boolean DEFAULT true NOT NULL,
    search_vector tsvector,
    sort_order integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    embedding public.vector(1024),
    embedding_updated_at timestamp with time zone
);


--
-- Name: COLUMN agent_knowledge.id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agent_knowledge.id IS 'Unique document identifier';


--
-- Name: COLUMN agent_knowledge.agent_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agent_knowledge.agent_key IS 'Agent this knowledge belongs to (e.g., ''support_agent'')';


--
-- Name: COLUMN agent_knowledge.title; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agent_knowledge.title IS 'Document title';


--
-- Name: COLUMN agent_knowledge.content; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agent_knowledge.content IS 'Full document content in markdown/plain text';


--
-- Name: COLUMN agent_knowledge.document_type; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agent_knowledge.document_type IS 'Type of document (faq, guide, manual, etc.)';


--
-- Name: COLUMN agent_knowledge.category; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agent_knowledge.category IS 'Secondary category for finer classification';


--
-- Name: COLUMN agent_knowledge.tags; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agent_knowledge.tags IS 'Tags for flexible categorization and filtering';


--
-- Name: COLUMN agent_knowledge.meta_data; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agent_knowledge.meta_data IS 'Flexible metadata (source_filename, page_count, author, etc.)';


--
-- Name: COLUMN agent_knowledge.active; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agent_knowledge.active IS 'Whether this document is active and searchable';


--
-- Name: COLUMN agent_knowledge.search_vector; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agent_knowledge.search_vector IS 'Full-text search vector (auto-generated from title + content)';


--
-- Name: COLUMN agent_knowledge.sort_order; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agent_knowledge.sort_order IS 'Order for displaying documents (lower = first)';


--
-- Name: COLUMN agent_knowledge.embedding; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agent_knowledge.embedding IS 'Vector embedding (1024-dim) for semantic search using BAAI/bge-m3 via Infinity';


--
-- Name: COLUMN agent_knowledge.embedding_updated_at; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agent_knowledge.embedding_updated_at IS 'Timestamp when embedding was last generated/updated';


--
-- Name: agents; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.agents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    agent_key character varying(100) NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    agent_type character varying(50) DEFAULT 'builtin'::character varying NOT NULL,
    domain_key character varying(50),
    enabled boolean DEFAULT true NOT NULL,
    priority integer DEFAULT 50 NOT NULL,
    keywords character varying[] DEFAULT '{}'::text[] NOT NULL,
    intent_patterns jsonb DEFAULT '[]'::jsonb NOT NULL,
    config jsonb DEFAULT '{}'::jsonb NOT NULL,
    sync_source character varying(50) DEFAULT 'seed'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: TABLE agents; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.agents IS 'Registry of available agents in the system. Admin controls visibility via enabled flag. Replaces ENABLED_AGENTS env var.';


--
-- Name: COLUMN agents.id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agents.id IS 'Unique agent identifier';


--
-- Name: COLUMN agents.agent_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agents.agent_key IS 'Unique agent key (e.g., ''greeting_agent'', ''support_agent'')';


--
-- Name: COLUMN agents.name; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agents.name IS 'Human-readable name for UI display';


--
-- Name: COLUMN agents.description; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agents.description IS 'Agent description and purpose';


--
-- Name: COLUMN agents.agent_type; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agents.agent_type IS 'Agent type: builtin, specialized, supervisor, orchestrator, custom';


--
-- Name: COLUMN agents.domain_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agents.domain_key IS 'Associated domain: None (global), excelencia, ecommerce, pharmacy, credit';


--
-- Name: COLUMN agents.enabled; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agents.enabled IS 'Whether agent is enabled globally';


--
-- Name: COLUMN agents.priority; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agents.priority IS 'Routing priority (100 = highest, 0 = lowest)';


--
-- Name: COLUMN agents.keywords; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agents.keywords IS 'Keywords for intent matching';


--
-- Name: COLUMN agents.intent_patterns; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agents.intent_patterns IS 'Intent patterns with weights: [{pattern: str, weight: float}]';


--
-- Name: COLUMN agents.config; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agents.config IS 'Agent-specific configuration';


--
-- Name: COLUMN agents.sync_source; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.agents.sync_source IS 'How agent was added: seed, manual';


--
-- Name: ai_models; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.ai_models (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    model_id character varying(255) NOT NULL,
    provider character varying(50) NOT NULL,
    model_type character varying(20) DEFAULT 'llm'::character varying NOT NULL,
    display_name character varying(255) NOT NULL,
    description text,
    family character varying(100),
    parameter_size character varying(50),
    quantization_level character varying(50),
    context_window integer,
    max_output_tokens integer DEFAULT 4096,
    supports_streaming boolean DEFAULT true NOT NULL,
    supports_functions boolean DEFAULT false NOT NULL,
    supports_vision boolean DEFAULT false NOT NULL,
    is_enabled boolean DEFAULT false NOT NULL,
    is_default boolean DEFAULT false NOT NULL,
    sort_order integer DEFAULT 100 NOT NULL,
    capabilities jsonb DEFAULT '{}'::jsonb NOT NULL,
    sync_source character varying(50) DEFAULT 'manual'::character varying NOT NULL,
    last_synced_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: TABLE ai_models; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.ai_models IS 'Registry of available AI models from various providers. Admin controls visibility via is_enabled.';


--
-- Name: COLUMN ai_models.id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.ai_models.id IS 'Unique model identifier';


--
-- Name: COLUMN ai_models.model_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.ai_models.model_id IS 'Provider-specific model ID (e.g., ''gpt-4'', ''llama3.2:3b'')';


--
-- Name: COLUMN ai_models.provider; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.ai_models.provider IS 'Model provider: ollama, openai, anthropic, deepseek';


--
-- Name: COLUMN ai_models.model_type; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.ai_models.model_type IS 'Model type: llm or embedding';


--
-- Name: COLUMN ai_models.display_name; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.ai_models.display_name IS 'Human-readable name for UI display';


--
-- Name: COLUMN ai_models.description; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.ai_models.description IS 'Model description';


--
-- Name: COLUMN ai_models.family; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.ai_models.family IS 'Model family (e.g., ''llama'', ''gpt'', ''claude'')';


--
-- Name: COLUMN ai_models.parameter_size; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.ai_models.parameter_size IS 'Model size (e.g., ''8B'', ''70B'')';


--
-- Name: COLUMN ai_models.quantization_level; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.ai_models.quantization_level IS 'Quantization level (e.g., ''Q4_K_M'', ''F16'')';


--
-- Name: COLUMN ai_models.context_window; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.ai_models.context_window IS 'Maximum context window in tokens';


--
-- Name: COLUMN ai_models.max_output_tokens; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.ai_models.max_output_tokens IS 'Maximum output tokens';


--
-- Name: COLUMN ai_models.supports_streaming; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.ai_models.supports_streaming IS 'Whether model supports streaming responses';


--
-- Name: COLUMN ai_models.supports_functions; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.ai_models.supports_functions IS 'Whether model supports function/tool calling';


--
-- Name: COLUMN ai_models.supports_vision; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.ai_models.supports_vision IS 'Whether model supports image input';


--
-- Name: COLUMN ai_models.is_enabled; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.ai_models.is_enabled IS 'Whether model is enabled for user selection';


--
-- Name: COLUMN ai_models.is_default; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.ai_models.is_default IS 'Whether this is a default model';


--
-- Name: COLUMN ai_models.sort_order; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.ai_models.sort_order IS 'Display order in UI (lower = first)';


--
-- Name: COLUMN ai_models.capabilities; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.ai_models.capabilities IS 'Additional capabilities and metadata';


--
-- Name: COLUMN ai_models.sync_source; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.ai_models.sync_source IS 'How model was added: manual, ollama_sync, seed';


--
-- Name: COLUMN ai_models.last_synced_at; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.ai_models.last_synced_at IS 'Last sync from provider';


--
-- Name: awaiting_type_configs; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.awaiting_type_configs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    organization_id uuid,
    domain_key character varying(50) DEFAULT 'pharmacy'::character varying NOT NULL,
    awaiting_type character varying(100) NOT NULL,
    target_node character varying(100) NOT NULL,
    valid_response_intents jsonb DEFAULT '[]'::jsonb,
    validation_pattern character varying(255),
    priority integer DEFAULT 0 NOT NULL,
    is_enabled boolean DEFAULT true NOT NULL,
    display_name character varying(200),
    description text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: TABLE awaiting_type_configs; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.awaiting_type_configs IS 'Database-driven awaiting type routing configuration. Replaces hardcoded awaiting_node_map and awaiting_intent_map in router_supervisor.py. Multi-tenant: each organization can customize. Multi-domain: supports pharmacy, healthcare, ecommerce via domain_key.';


--
-- Name: COLUMN awaiting_type_configs.id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.awaiting_type_configs.id IS 'Unique configuration identifier';


--
-- Name: COLUMN awaiting_type_configs.organization_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.awaiting_type_configs.organization_id IS 'Organization that owns this configuration (NULL for system defaults)';


--
-- Name: COLUMN awaiting_type_configs.domain_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.awaiting_type_configs.domain_key IS 'Domain: pharmacy, healthcare, ecommerce, etc.';


--
-- Name: COLUMN awaiting_type_configs.awaiting_type; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.awaiting_type_configs.awaiting_type IS 'Awaiting input type (dni, amount, payment_confirmation, etc.)';


--
-- Name: COLUMN awaiting_type_configs.target_node; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.awaiting_type_configs.target_node IS 'Node to route to when awaiting this type';


--
-- Name: COLUMN awaiting_type_configs.valid_response_intents; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.awaiting_type_configs.valid_response_intents IS 'Intent keys for validating responses (bypasses global keywords)';


--
-- Name: COLUMN awaiting_type_configs.validation_pattern; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.awaiting_type_configs.validation_pattern IS 'Optional regex pattern for validating responses (e.g., amount format)';


--
-- Name: COLUMN awaiting_type_configs.priority; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.awaiting_type_configs.priority IS 'Processing priority (higher = first)';


--
-- Name: COLUMN awaiting_type_configs.is_enabled; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.awaiting_type_configs.is_enabled IS 'Whether configuration is active';


--
-- Name: COLUMN awaiting_type_configs.display_name; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.awaiting_type_configs.display_name IS 'Human-readable name';


--
-- Name: COLUMN awaiting_type_configs.description; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.awaiting_type_configs.description IS 'Usage notes';


--
-- Name: bypass_rules; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.bypass_rules (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    organization_id uuid NOT NULL,
    rule_name character varying(100) NOT NULL,
    description text,
    rule_type character varying(50) NOT NULL,
    pattern character varying(100),
    phone_numbers character varying[],
    phone_number_id character varying(100),
    target_agent character varying(100) NOT NULL,
    target_domain character varying(50),
    priority integer DEFAULT 0 NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    pharmacy_id uuid,
    isolated_history boolean
);


--
-- Name: COLUMN bypass_rules.id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.bypass_rules.id IS 'Unique bypass rule identifier';


--
-- Name: COLUMN bypass_rules.organization_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.bypass_rules.organization_id IS 'Organization this rule belongs to';


--
-- Name: COLUMN bypass_rules.rule_name; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.bypass_rules.rule_name IS 'Human-readable name for the rule';


--
-- Name: COLUMN bypass_rules.description; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.bypass_rules.description IS 'Description of what this rule does';


--
-- Name: COLUMN bypass_rules.rule_type; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.bypass_rules.rule_type IS 'Type: phone_number, phone_number_list, whatsapp_phone_number_id';


--
-- Name: COLUMN bypass_rules.pattern; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.bypass_rules.pattern IS 'Pattern for phone_number type (e.g., ''549264*'')';


--
-- Name: COLUMN bypass_rules.phone_numbers; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.bypass_rules.phone_numbers IS 'List of phone numbers for phone_number_list type';


--
-- Name: COLUMN bypass_rules.phone_number_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.bypass_rules.phone_number_id IS 'WhatsApp Business phone number ID for whatsapp_phone_number_id type';


--
-- Name: COLUMN bypass_rules.target_agent; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.bypass_rules.target_agent IS 'Agent key to route to (e.g., ''pharmacy_operations_agent'')';


--
-- Name: COLUMN bypass_rules.target_domain; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.bypass_rules.target_domain IS 'Optional domain override';


--
-- Name: COLUMN bypass_rules.priority; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.bypass_rules.priority IS 'Priority for rule evaluation (higher = evaluated first)';


--
-- Name: COLUMN bypass_rules.enabled; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.bypass_rules.enabled IS 'Whether this rule is active';


--
-- Name: COLUMN bypass_rules.pharmacy_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.bypass_rules.pharmacy_id IS 'Pharmacy that auto-created this rule (NULL for manual rules)';


--
-- Name: COLUMN bypass_rules.isolated_history; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.bypass_rules.isolated_history IS 'When true, creates isolated conversation history for this rule''s flow';


--
-- Name: chattigo_credentials; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.chattigo_credentials (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    did character varying(20) NOT NULL,
    name character varying(100) NOT NULL,
    username_encrypted text NOT NULL,
    password_encrypted text NOT NULL,
    login_url character varying(255) DEFAULT 'https://channels.chattigo.com/bsp-cloud-chattigo-isv/login'::character varying NOT NULL,
    base_url character varying(255) DEFAULT 'https://channels.chattigo.com/bsp-cloud-chattigo-isv'::character varying CONSTRAINT chattigo_credentials_message_url_not_null NOT NULL,
    bot_name character varying(50) DEFAULT 'Aynux'::character varying NOT NULL,
    token_refresh_hours integer DEFAULT 7 NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    organization_id uuid NOT NULL,
    bypass_rule_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: COLUMN chattigo_credentials.did; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.chattigo_credentials.did IS 'WhatsApp Business phone number (DID), e.g., ''5492644710400''';


--
-- Name: COLUMN chattigo_credentials.name; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.chattigo_credentials.name IS 'Human-readable name for this DID (e.g., ''Turmedica'')';


--
-- Name: COLUMN chattigo_credentials.username_encrypted; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.chattigo_credentials.username_encrypted IS 'Encrypted Chattigo ISV username (pgcrypto)';


--
-- Name: COLUMN chattigo_credentials.password_encrypted; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.chattigo_credentials.password_encrypted IS 'Encrypted Chattigo ISV password (pgcrypto)';


--
-- Name: COLUMN chattigo_credentials.login_url; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.chattigo_credentials.login_url IS 'Chattigo ISV login endpoint';


--
-- Name: COLUMN chattigo_credentials.base_url; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.chattigo_credentials.base_url IS 'Chattigo ISV message/webhook endpoint';


--
-- Name: COLUMN chattigo_credentials.bot_name; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.chattigo_credentials.bot_name IS 'Bot display name for outbound messages';


--
-- Name: COLUMN chattigo_credentials.token_refresh_hours; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.chattigo_credentials.token_refresh_hours IS 'Hours between token refresh (tokens expire at 8h)';


--
-- Name: COLUMN chattigo_credentials.enabled; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.chattigo_credentials.enabled IS 'Whether this DID credential is active';


--
-- Name: COLUMN chattigo_credentials.organization_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.chattigo_credentials.organization_id IS 'Organization this credential belongs to';


--
-- Name: COLUMN chattigo_credentials.bypass_rule_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.chattigo_credentials.bypass_rule_id IS 'Optional bypass rule linked to this DID';


--
-- Name: company_knowledge; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.company_knowledge (
    id uuid NOT NULL,
    title character varying(500) NOT NULL,
    content text NOT NULL,
    document_type public.document_type_enum NOT NULL,
    category character varying(200),
    tags character varying[],
    meta_data jsonb,
    active boolean NOT NULL,
    embedding public.vector(1024),
    search_vector tsvector,
    sort_order integer,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: COLUMN company_knowledge.title; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.company_knowledge.title IS 'Document title';


--
-- Name: COLUMN company_knowledge.content; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.company_knowledge.content IS 'Full document content in markdown/plain text';


--
-- Name: COLUMN company_knowledge.document_type; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.company_knowledge.document_type IS 'Type of document for categorization';


--
-- Name: COLUMN company_knowledge.category; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.company_knowledge.category IS 'Secondary category for finer classification';


--
-- Name: COLUMN company_knowledge.tags; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.company_knowledge.tags IS 'Tags for flexible categorization and filtering';


--
-- Name: COLUMN company_knowledge.meta_data; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.company_knowledge.meta_data IS 'Flexible metadata storage (author, source, version, etc.)';


--
-- Name: COLUMN company_knowledge.active; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.company_knowledge.active IS 'Whether this document is active and searchable';


--
-- Name: COLUMN company_knowledge.embedding; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.company_knowledge.embedding IS 'Vector embedding (1024-dim) for semantic search using BAAI/bge-m3 via Infinity';


--
-- Name: COLUMN company_knowledge.search_vector; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.company_knowledge.search_vector IS 'Full-text search vector (auto-generated from title + content)';


--
-- Name: COLUMN company_knowledge.sort_order; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.company_knowledge.sort_order IS 'Order for displaying documents (lower = first)';


--
-- Name: contact_domains; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.contact_domains (
    id uuid NOT NULL,
    wa_id character varying(20) NOT NULL,
    domain character varying(50) NOT NULL,
    confidence double precision,
    assigned_method character varying(50) NOT NULL,
    domain_metadata jsonb,
    assigned_at timestamp with time zone NOT NULL,
    last_verified timestamp with time zone,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    organization_id uuid
);


--
-- Name: conversation_contexts; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.conversation_contexts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    conversation_id character varying(255) NOT NULL,
    organization_id uuid,
    user_phone character varying(50),
    rolling_summary text,
    topic_history jsonb DEFAULT '[]'::jsonb NOT NULL,
    key_entities jsonb DEFAULT '{}'::jsonb NOT NULL,
    total_turns integer DEFAULT 0 NOT NULL,
    last_user_message text,
    last_bot_response text,
    extra_data jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    last_activity_at timestamp with time zone DEFAULT now() NOT NULL,
    pharmacy_id uuid
);


--
-- Name: COLUMN conversation_contexts.conversation_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.conversation_contexts.conversation_id IS 'Unique identifier for the conversation (e.g., whatsapp_{phone})';


--
-- Name: COLUMN conversation_contexts.organization_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.conversation_contexts.organization_id IS 'Multi-tenancy: organization that owns this conversation';


--
-- Name: COLUMN conversation_contexts.user_phone; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.conversation_contexts.user_phone IS 'User phone number for WhatsApp conversations';


--
-- Name: COLUMN conversation_contexts.rolling_summary; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.conversation_contexts.rolling_summary IS 'LLM-generated rolling summary of the conversation';


--
-- Name: COLUMN conversation_contexts.topic_history; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.conversation_contexts.topic_history IS 'List of topics discussed in the conversation';


--
-- Name: COLUMN conversation_contexts.key_entities; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.conversation_contexts.key_entities IS 'Key entities mentioned (names, products, preferences)';


--
-- Name: COLUMN conversation_contexts.total_turns; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.conversation_contexts.total_turns IS 'Total number of conversation turns';


--
-- Name: COLUMN conversation_contexts.last_user_message; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.conversation_contexts.last_user_message IS 'Last message from user for quick access';


--
-- Name: COLUMN conversation_contexts.last_bot_response; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.conversation_contexts.last_bot_response IS 'Last response from assistant for quick access';


--
-- Name: COLUMN conversation_contexts.extra_data; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.conversation_contexts.extra_data IS 'Additional context data (channel, language, etc.)';


--
-- Name: COLUMN conversation_contexts.last_activity_at; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.conversation_contexts.last_activity_at IS 'Last activity timestamp for cleanup queries';


--
-- Name: COLUMN conversation_contexts.pharmacy_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.conversation_contexts.pharmacy_id IS 'Pharmacy that owns this conversation (for multi-pharmacy orgs)';


--
-- Name: conversation_messages; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.conversation_messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    conversation_id character varying(255) NOT NULL,
    sender_type public.sender_type_enum NOT NULL,
    content text NOT NULL,
    agent_name character varying(100),
    extra_data jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: COLUMN conversation_messages.conversation_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.conversation_messages.conversation_id IS 'Reference to conversation_contexts.conversation_id';


--
-- Name: COLUMN conversation_messages.sender_type; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.conversation_messages.sender_type IS 'Who sent the message: user, assistant, or system';


--
-- Name: COLUMN conversation_messages.content; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.conversation_messages.content IS 'Message content';


--
-- Name: COLUMN conversation_messages.agent_name; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.conversation_messages.agent_name IS 'Name of agent that generated response (for assistant messages)';


--
-- Name: COLUMN conversation_messages.extra_data; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.conversation_messages.extra_data IS 'Additional message data (intent, confidence, etc.)';


--
-- Name: domain_configs; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.domain_configs (
    domain character varying(50) NOT NULL,
    enabled character varying(10),
    display_name character varying(100) NOT NULL,
    description character varying(500),
    service_class character varying(100),
    model_config jsonb,
    phone_patterns jsonb,
    keyword_patterns jsonb,
    priority double precision,
    fallback_enabled character varying(10),
    config_metadata jsonb,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: domain_intents; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.domain_intents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    organization_id uuid NOT NULL,
    domain_key character varying(50) NOT NULL,
    intent_key character varying(100) NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    weight numeric(3,2) DEFAULT 1.0 NOT NULL,
    exact_match boolean DEFAULT false NOT NULL,
    is_enabled boolean DEFAULT true NOT NULL,
    priority integer DEFAULT 50 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    lemmas jsonb DEFAULT '[]'::jsonb NOT NULL,
    phrases jsonb DEFAULT '[]'::jsonb NOT NULL,
    confirmation_patterns jsonb DEFAULT '[]'::jsonb NOT NULL,
    keywords jsonb DEFAULT '[]'::jsonb NOT NULL
);


--
-- Name: COLUMN domain_intents.id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domain_intents.id IS 'Unique intent identifier';


--
-- Name: COLUMN domain_intents.organization_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domain_intents.organization_id IS 'Organization that owns this intent';


--
-- Name: COLUMN domain_intents.domain_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domain_intents.domain_key IS 'Domain: pharmacy, excelencia, ecommerce, healthcare, etc.';


--
-- Name: COLUMN domain_intents.intent_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domain_intents.intent_key IS 'Unique intent key within org+domain';


--
-- Name: COLUMN domain_intents.name; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domain_intents.name IS 'Human-readable intent name';


--
-- Name: COLUMN domain_intents.description; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domain_intents.description IS 'Intent description and usage notes';


--
-- Name: COLUMN domain_intents.weight; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domain_intents.weight IS 'Scoring weight multiplier';


--
-- Name: COLUMN domain_intents.exact_match; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domain_intents.exact_match IS 'If True, requires exact phrase match';


--
-- Name: COLUMN domain_intents.is_enabled; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domain_intents.is_enabled IS 'Whether intent is active for detection';


--
-- Name: COLUMN domain_intents.priority; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domain_intents.priority IS 'Evaluation order (100 = first, 0 = last)';


--
-- Name: COLUMN domain_intents.lemmas; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domain_intents.lemmas IS 'Array of lemma strings for spaCy matching';


--
-- Name: COLUMN domain_intents.phrases; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domain_intents.phrases IS 'Array of {phrase, match_type} objects';


--
-- Name: COLUMN domain_intents.confirmation_patterns; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domain_intents.confirmation_patterns IS 'Array of {pattern, pattern_type} objects';


--
-- Name: COLUMN domain_intents.keywords; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domain_intents.keywords IS 'Array of keyword strings';


--
-- Name: domains; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.domains (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    domain_key character varying(50) NOT NULL,
    display_name character varying(255) NOT NULL,
    description text,
    icon character varying(100),
    color character varying(50),
    enabled boolean DEFAULT true NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: COLUMN domains.id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domains.id IS 'Unique domain identifier';


--
-- Name: COLUMN domains.domain_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domains.domain_key IS 'Unique domain key (e.g., ''excelencia'', ''pharmacy'')';


--
-- Name: COLUMN domains.display_name; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domains.display_name IS 'Human-readable name for UI display';


--
-- Name: COLUMN domains.description; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domains.description IS 'Domain description and purpose';


--
-- Name: COLUMN domains.icon; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domains.icon IS 'PrimeVue icon class (e.g., ''pi-building'')';


--
-- Name: COLUMN domains.color; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domains.color IS 'Tag severity color (e.g., ''info'', ''success'')';


--
-- Name: COLUMN domains.enabled; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domains.enabled IS 'Whether domain is available for selection';


--
-- Name: COLUMN domains.sort_order; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.domains.sort_order IS 'Display order in dropdowns (lower = first)';


--
-- Name: flow_agent_configs; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.flow_agent_configs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    organization_id uuid NOT NULL,
    agent_key character varying(100) NOT NULL,
    is_flow_agent boolean DEFAULT true NOT NULL,
    flow_description text,
    max_turns integer DEFAULT 10 NOT NULL,
    timeout_seconds integer DEFAULT 300 NOT NULL,
    is_enabled boolean DEFAULT true NOT NULL,
    config jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: TABLE flow_agent_configs; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.flow_agent_configs IS 'Configures agents with multi-turn flows. Replaces hardcoded FLOW_AGENTS set. Multi-tenant via organization_id.';


--
-- Name: COLUMN flow_agent_configs.id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.flow_agent_configs.id IS 'Unique flow config identifier';


--
-- Name: COLUMN flow_agent_configs.organization_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.flow_agent_configs.organization_id IS 'Organization that owns this config';


--
-- Name: COLUMN flow_agent_configs.agent_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.flow_agent_configs.agent_key IS 'Agent key (e.g., ''pharmacy_operations_agent'')';


--
-- Name: COLUMN flow_agent_configs.is_flow_agent; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.flow_agent_configs.is_flow_agent IS 'Whether agent has multi-turn conversational flow';


--
-- Name: COLUMN flow_agent_configs.flow_description; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.flow_agent_configs.flow_description IS 'Description of the flow behavior';


--
-- Name: COLUMN flow_agent_configs.max_turns; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.flow_agent_configs.max_turns IS 'Maximum conversation turns in flow';


--
-- Name: COLUMN flow_agent_configs.timeout_seconds; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.flow_agent_configs.timeout_seconds IS 'Flow timeout in seconds';


--
-- Name: COLUMN flow_agent_configs.is_enabled; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.flow_agent_configs.is_enabled IS 'Whether flow config is active';


--
-- Name: COLUMN flow_agent_configs.config; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.flow_agent_configs.config IS 'Additional flow configuration';


--
-- Name: intent_agent_mappings; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.intent_agent_mappings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    organization_id uuid NOT NULL,
    domain_key character varying(50),
    intent_key character varying(100) NOT NULL,
    intent_name character varying(255) NOT NULL,
    intent_description text,
    agent_key character varying(100) NOT NULL,
    confidence_threshold numeric(3,2) DEFAULT 0.75 NOT NULL,
    requires_handoff boolean DEFAULT false NOT NULL,
    priority integer DEFAULT 50 NOT NULL,
    is_enabled boolean DEFAULT true NOT NULL,
    examples jsonb DEFAULT '[]'::jsonb NOT NULL,
    config jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: TABLE intent_agent_mappings; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.intent_agent_mappings IS 'Maps intents to target agents. Replaces hardcoded AGENT_TO_INTENT_MAPPING. Multi-tenant via organization_id.';


--
-- Name: COLUMN intent_agent_mappings.id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.intent_agent_mappings.id IS 'Unique mapping identifier';


--
-- Name: COLUMN intent_agent_mappings.organization_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.intent_agent_mappings.organization_id IS 'Organization that owns this mapping';


--
-- Name: COLUMN intent_agent_mappings.domain_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.intent_agent_mappings.domain_key IS 'Domain scope: NULL (global), excelencia, pharmacy, etc.';


--
-- Name: COLUMN intent_agent_mappings.intent_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.intent_agent_mappings.intent_key IS 'Intent identifier (e.g., ''saludo'', ''soporte'', ''excelencia'')';


--
-- Name: COLUMN intent_agent_mappings.intent_name; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.intent_agent_mappings.intent_name IS 'Human-readable intent name';


--
-- Name: COLUMN intent_agent_mappings.intent_description; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.intent_agent_mappings.intent_description IS 'Intent description for documentation';


--
-- Name: COLUMN intent_agent_mappings.agent_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.intent_agent_mappings.agent_key IS 'Target agent key (e.g., ''greeting_agent'', ''support_agent'')';


--
-- Name: COLUMN intent_agent_mappings.confidence_threshold; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.intent_agent_mappings.confidence_threshold IS 'Minimum confidence to route (0.00-1.00)';


--
-- Name: COLUMN intent_agent_mappings.requires_handoff; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.intent_agent_mappings.requires_handoff IS 'Whether intent requires human handoff';


--
-- Name: COLUMN intent_agent_mappings.priority; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.intent_agent_mappings.priority IS 'Evaluation priority (100 = highest, 0 = lowest)';


--
-- Name: COLUMN intent_agent_mappings.is_enabled; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.intent_agent_mappings.is_enabled IS 'Whether mapping is active';


--
-- Name: COLUMN intent_agent_mappings.examples; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.intent_agent_mappings.examples IS 'Example phrases for this intent';


--
-- Name: COLUMN intent_agent_mappings.config; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.intent_agent_mappings.config IS 'Additional configuration';


--
-- Name: keyword_agent_mappings; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.keyword_agent_mappings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    organization_id uuid NOT NULL,
    agent_key character varying(100) NOT NULL,
    keyword character varying(255) NOT NULL,
    match_type character varying(20) DEFAULT 'contains'::character varying NOT NULL,
    case_sensitive boolean DEFAULT false NOT NULL,
    priority integer DEFAULT 50 NOT NULL,
    is_enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: TABLE keyword_agent_mappings; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.keyword_agent_mappings IS 'Keyword-based fallback routing. Replaces hardcoded KEYWORD_TO_AGENT dict. Multi-tenant via organization_id.';


--
-- Name: COLUMN keyword_agent_mappings.id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.keyword_agent_mappings.id IS 'Unique keyword mapping identifier';


--
-- Name: COLUMN keyword_agent_mappings.organization_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.keyword_agent_mappings.organization_id IS 'Organization that owns this mapping';


--
-- Name: COLUMN keyword_agent_mappings.agent_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.keyword_agent_mappings.agent_key IS 'Target agent key';


--
-- Name: COLUMN keyword_agent_mappings.keyword; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.keyword_agent_mappings.keyword IS 'Keyword or phrase to match';


--
-- Name: COLUMN keyword_agent_mappings.match_type; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.keyword_agent_mappings.match_type IS 'Match type: exact, contains, prefix, regex';


--
-- Name: COLUMN keyword_agent_mappings.case_sensitive; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.keyword_agent_mappings.case_sensitive IS 'Whether match is case-sensitive';


--
-- Name: COLUMN keyword_agent_mappings.priority; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.keyword_agent_mappings.priority IS 'Evaluation priority (100 = highest)';


--
-- Name: COLUMN keyword_agent_mappings.is_enabled; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.keyword_agent_mappings.is_enabled IS 'Whether keyword is active';


--
-- Name: organization_users; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.organization_users (
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    user_id uuid NOT NULL,
    role character varying(50) NOT NULL,
    personal_settings jsonb NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: COLUMN organization_users.id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.organization_users.id IS 'Unique membership identifier';


--
-- Name: COLUMN organization_users.organization_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.organization_users.organization_id IS 'Organization this membership belongs to';


--
-- Name: COLUMN organization_users.user_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.organization_users.user_id IS 'User who is a member of the organization';


--
-- Name: COLUMN organization_users.role; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.organization_users.role IS 'User role: ''owner'', ''admin'', ''member''';


--
-- Name: COLUMN organization_users.personal_settings; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.organization_users.personal_settings IS 'User-specific settings overrides (e.g., default_domain, ui_preferences)';


--
-- Name: organizations; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.organizations (
    id uuid NOT NULL,
    slug character varying(50) NOT NULL,
    name character varying(255) NOT NULL,
    display_name character varying(255),
    mode character varying(20) NOT NULL,
    llm_model character varying(100) NOT NULL,
    llm_temperature double precision NOT NULL,
    llm_max_tokens integer NOT NULL,
    features jsonb NOT NULL,
    max_users integer NOT NULL,
    max_documents integer NOT NULL,
    max_agents integer NOT NULL,
    status character varying(20) NOT NULL,
    trial_ends_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: COLUMN organizations.id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.organizations.id IS 'Unique organization identifier';


--
-- Name: COLUMN organizations.slug; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.organizations.slug IS 'URL-friendly unique identifier (e.g., ''acme-corp'')';


--
-- Name: COLUMN organizations.name; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.organizations.name IS 'Official organization name';


--
-- Name: COLUMN organizations.display_name; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.organizations.display_name IS 'Display name for UI (falls back to name)';


--
-- Name: COLUMN organizations.mode; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.organizations.mode IS 'Operating mode: ''generic'' uses static config, ''multi_tenant'' uses DB config';


--
-- Name: COLUMN organizations.llm_model; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.organizations.llm_model IS 'Default LLM model for this tenant';


--
-- Name: COLUMN organizations.llm_temperature; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.organizations.llm_temperature IS 'Default temperature for LLM (0.0-1.0)';


--
-- Name: COLUMN organizations.llm_max_tokens; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.organizations.llm_max_tokens IS 'Max tokens for LLM responses';


--
-- Name: COLUMN organizations.features; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.organizations.features IS 'Feature flags (e.g., {''rag_enabled'': true, ''custom_agents'': false})';


--
-- Name: COLUMN organizations.max_users; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.organizations.max_users IS 'Maximum users allowed in organization';


--
-- Name: COLUMN organizations.max_documents; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.organizations.max_documents IS 'Maximum documents in knowledge base';


--
-- Name: COLUMN organizations.max_agents; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.organizations.max_agents IS 'Maximum custom agents';


--
-- Name: COLUMN organizations.status; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.organizations.status IS 'Organization status: ''active'', ''suspended'', ''trial''';


--
-- Name: COLUMN organizations.trial_ends_at; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.organizations.trial_ends_at IS 'Trial expiration date (null if not on trial)';


--
-- Name: rag_query_logs; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.rag_query_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    query text NOT NULL,
    context_used jsonb DEFAULT '[]'::jsonb NOT NULL,
    response text,
    token_count integer DEFAULT 0 NOT NULL,
    latency_ms integer DEFAULT 0 NOT NULL,
    relevance_score numeric(4,3),
    user_feedback character varying(10),
    agent_key character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT rag_query_logs_relevance_score_check CHECK (((relevance_score IS NULL) OR ((relevance_score >= (0)::numeric) AND (relevance_score <= (1)::numeric)))),
    CONSTRAINT rag_query_logs_user_feedback_check CHECK (((user_feedback)::text = ANY ((ARRAY['positive'::character varying, 'negative'::character varying])::text[])))
);


--
-- Name: TABLE rag_query_logs; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.rag_query_logs IS 'Stores RAG query logs for analytics and monitoring';


--
-- Name: COLUMN rag_query_logs.query; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.rag_query_logs.query IS 'The user query text';


--
-- Name: COLUMN rag_query_logs.context_used; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.rag_query_logs.context_used IS 'JSON array of document IDs or titles used as context';


--
-- Name: COLUMN rag_query_logs.response; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.rag_query_logs.response IS 'Generated response text (nullable - may be logged before response generation)';


--
-- Name: COLUMN rag_query_logs.token_count; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.rag_query_logs.token_count IS 'Number of tokens used in the response';


--
-- Name: COLUMN rag_query_logs.latency_ms; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.rag_query_logs.latency_ms IS 'Response latency in milliseconds';


--
-- Name: COLUMN rag_query_logs.relevance_score; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.rag_query_logs.relevance_score IS 'Relevance score between 0 and 1';


--
-- Name: COLUMN rag_query_logs.user_feedback; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.rag_query_logs.user_feedback IS 'User feedback: positive or negative';


--
-- Name: COLUMN rag_query_logs.agent_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.rag_query_logs.agent_key IS 'The agent that processed this query';


--
-- Name: response_configs; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.response_configs (
    id uuid DEFAULT gen_random_uuid() CONSTRAINT pharmacy_response_configs_id_not_null NOT NULL,
    organization_id uuid CONSTRAINT pharmacy_response_configs_organization_id_not_null NOT NULL,
    domain_key character varying(50) DEFAULT 'pharmacy'::character varying CONSTRAINT pharmacy_response_configs_domain_key_not_null NOT NULL,
    intent_key character varying(100) CONSTRAINT pharmacy_response_configs_intent_key_not_null NOT NULL,
    is_critical boolean DEFAULT false CONSTRAINT pharmacy_response_configs_is_critical_not_null NOT NULL,
    task_description text CONSTRAINT pharmacy_response_configs_task_description_not_null NOT NULL,
    fallback_template_key character varying(100) CONSTRAINT pharmacy_response_configs_fallback_template_key_not_null NOT NULL,
    display_name character varying(200),
    description text,
    priority integer DEFAULT 0 CONSTRAINT pharmacy_response_configs_priority_not_null NOT NULL,
    is_enabled boolean DEFAULT true CONSTRAINT pharmacy_response_configs_is_enabled_not_null NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP CONSTRAINT pharmacy_response_configs_created_at_not_null NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP CONSTRAINT pharmacy_response_configs_updated_at_not_null NOT NULL
);


--
-- Name: TABLE response_configs; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.response_configs IS 'Multi-domain response generation configuration. Supports pharmacy, healthcare, ecommerce, and future domains via domain_key. Multi-tenant: each organization can customize per domain.';


--
-- Name: COLUMN response_configs.id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.response_configs.id IS 'Unique configuration identifier';


--
-- Name: COLUMN response_configs.organization_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.response_configs.organization_id IS 'Organization that owns this configuration';


--
-- Name: COLUMN response_configs.domain_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.response_configs.domain_key IS 'Domain: pharmacy (expandable)';


--
-- Name: COLUMN response_configs.intent_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.response_configs.intent_key IS 'Intent identifier (e.g., ''greeting'', ''payment_confirmation'')';


--
-- Name: COLUMN response_configs.is_critical; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.response_configs.is_critical IS 'If true, always uses fixed template, never LLM';


--
-- Name: COLUMN response_configs.task_description; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.response_configs.task_description IS 'Task description for LLM system prompt (replaces _infer_task)';


--
-- Name: COLUMN response_configs.fallback_template_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.response_configs.fallback_template_key IS 'Key in fallback_templates.yaml (replaces _map_intent_to_fallback)';


--
-- Name: COLUMN response_configs.display_name; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.response_configs.display_name IS 'Human-readable configuration name';


--
-- Name: COLUMN response_configs.description; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.response_configs.description IS 'Configuration description and usage notes';


--
-- Name: COLUMN response_configs.priority; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.response_configs.priority IS 'Display/processing order (higher = first)';


--
-- Name: COLUMN response_configs.is_enabled; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.response_configs.is_enabled IS 'Whether configuration is active';


--
-- Name: routing_configs; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.routing_configs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    organization_id uuid,
    domain_key character varying(50) DEFAULT 'pharmacy'::character varying NOT NULL,
    config_type character varying(50) NOT NULL,
    trigger_value character varying(100) NOT NULL,
    target_intent character varying(100) NOT NULL,
    target_node character varying(100),
    priority integer DEFAULT 0 NOT NULL,
    is_enabled boolean DEFAULT true NOT NULL,
    requires_auth boolean DEFAULT false NOT NULL,
    clears_context boolean DEFAULT false NOT NULL,
    metadata jsonb,
    display_name character varying(200),
    description text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: TABLE routing_configs; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.routing_configs IS 'Database-driven routing configuration for multi-domain chatbot flows. Replaces hardcoded GLOBAL_KEYWORDS, MENU_OPTIONS, and button mappings. Multi-tenant: each organization can customize. Multi-domain: supports pharmacy, healthcare, ecommerce via domain_key.';


--
-- Name: COLUMN routing_configs.id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.routing_configs.id IS 'Unique configuration identifier';


--
-- Name: COLUMN routing_configs.organization_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.routing_configs.organization_id IS 'Organization that owns this configuration (NULL for system defaults)';


--
-- Name: COLUMN routing_configs.domain_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.routing_configs.domain_key IS 'Domain: pharmacy, healthcare, ecommerce, etc.';


--
-- Name: COLUMN routing_configs.config_type; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.routing_configs.config_type IS 'Type: global_keyword, button_mapping, menu_option, list_selection';


--
-- Name: COLUMN routing_configs.trigger_value; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.routing_configs.trigger_value IS 'Value that triggers routing (keyword, button_id, menu number)';


--
-- Name: COLUMN routing_configs.target_intent; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.routing_configs.target_intent IS 'Intent to set when triggered (e.g., show_menu, pay_full)';


--
-- Name: COLUMN routing_configs.target_node; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.routing_configs.target_node IS 'Node to route to (NULL to use default for intent)';


--
-- Name: COLUMN routing_configs.priority; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.routing_configs.priority IS 'Processing priority (higher = first)';


--
-- Name: COLUMN routing_configs.is_enabled; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.routing_configs.is_enabled IS 'Whether configuration is active';


--
-- Name: COLUMN routing_configs.requires_auth; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.routing_configs.requires_auth IS 'Whether this route requires authentication';


--
-- Name: COLUMN routing_configs.clears_context; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.routing_configs.clears_context IS 'Whether to clear pending flow context';


--
-- Name: COLUMN routing_configs.metadata; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.routing_configs.metadata IS 'Additional configuration (e.g., aliases, conditions)';


--
-- Name: COLUMN routing_configs.display_name; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.routing_configs.display_name IS 'Human-readable name';


--
-- Name: COLUMN routing_configs.description; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.routing_configs.description IS 'Usage notes';


--
-- Name: tenant_agents; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.tenant_agents (
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    agent_key character varying(100) NOT NULL,
    agent_type character varying(50) NOT NULL,
    display_name character varying(255) NOT NULL,
    description text,
    agent_class character varying(255),
    enabled boolean NOT NULL,
    priority integer NOT NULL,
    domain_key character varying(50),
    keywords character varying[] NOT NULL,
    intent_patterns jsonb NOT NULL,
    config jsonb NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: COLUMN tenant_agents.id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_agents.id IS 'Unique agent configuration identifier';


--
-- Name: COLUMN tenant_agents.organization_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_agents.organization_id IS 'Organization this agent belongs to';


--
-- Name: COLUMN tenant_agents.agent_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_agents.agent_key IS 'Unique key for this agent (e.g., ''product_agent'')';


--
-- Name: COLUMN tenant_agents.agent_type; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_agents.agent_type IS 'Agent type: ''domain'', ''specialized'', ''custom''';


--
-- Name: COLUMN tenant_agents.display_name; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_agents.display_name IS 'Human-readable agent name';


--
-- Name: COLUMN tenant_agents.description; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_agents.description IS 'Description of what this agent does';


--
-- Name: COLUMN tenant_agents.agent_class; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_agents.agent_class IS 'Full Python class path for custom agents (e.g., ''app.custom.MyAgent'')';


--
-- Name: COLUMN tenant_agents.enabled; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_agents.enabled IS 'Whether this agent is active';


--
-- Name: COLUMN tenant_agents.priority; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_agents.priority IS 'Priority for routing (higher = preferred)';


--
-- Name: COLUMN tenant_agents.domain_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_agents.domain_key IS 'Associated domain key (for domain agents)';


--
-- Name: COLUMN tenant_agents.keywords; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_agents.keywords IS 'Keywords that trigger this agent';


--
-- Name: COLUMN tenant_agents.intent_patterns; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_agents.intent_patterns IS 'Patterns for intent matching (e.g., [{pattern: ''...'', weight: 1.0}])';


--
-- Name: COLUMN tenant_agents.config; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_agents.config IS 'Agent-specific configuration (model, temperature, tools, etc.)';


--
-- Name: tenant_configs; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.tenant_configs (
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    enabled_domains character varying[] NOT NULL,
    default_domain character varying(50) NOT NULL,
    enabled_agent_types character varying[] NOT NULL,
    agent_timeout_seconds integer NOT NULL,
    rag_enabled boolean NOT NULL,
    rag_similarity_threshold double precision NOT NULL,
    rag_max_results integer NOT NULL,
    prompt_scope character varying(20) NOT NULL,
    whatsapp_phone_number_id character varying(50),
    whatsapp_verify_token character varying(255),
    advanced_config jsonb NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    fallback_agent character varying(100) DEFAULT 'fallback_agent'::character varying NOT NULL
);


--
-- Name: COLUMN tenant_configs.id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_configs.id IS 'Unique configuration identifier';


--
-- Name: COLUMN tenant_configs.organization_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_configs.organization_id IS 'Organization this config belongs to';


--
-- Name: COLUMN tenant_configs.enabled_domains; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_configs.enabled_domains IS 'List of enabled domain keys (e.g., [''ecommerce'', ''healthcare''])';


--
-- Name: COLUMN tenant_configs.default_domain; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_configs.default_domain IS 'Default domain for routing when intent is unclear';


--
-- Name: COLUMN tenant_configs.enabled_agent_types; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_configs.enabled_agent_types IS 'List of enabled agent keys (empty = all builtin)';


--
-- Name: COLUMN tenant_configs.agent_timeout_seconds; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_configs.agent_timeout_seconds IS 'Timeout for agent operations in seconds';


--
-- Name: COLUMN tenant_configs.rag_enabled; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_configs.rag_enabled IS 'Whether RAG is enabled for this tenant';


--
-- Name: COLUMN tenant_configs.rag_similarity_threshold; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_configs.rag_similarity_threshold IS 'Minimum similarity score for RAG results (0.0-1.0)';


--
-- Name: COLUMN tenant_configs.rag_max_results; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_configs.rag_max_results IS 'Maximum number of results from RAG search';


--
-- Name: COLUMN tenant_configs.prompt_scope; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_configs.prompt_scope IS 'Prompt resolution scope: ''system'', ''global'', ''org''';


--
-- Name: COLUMN tenant_configs.whatsapp_phone_number_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_configs.whatsapp_phone_number_id IS 'WhatsApp Business phone number ID (overrides global)';


--
-- Name: COLUMN tenant_configs.whatsapp_verify_token; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_configs.whatsapp_verify_token IS 'Webhook verification token (overrides global)';


--
-- Name: COLUMN tenant_configs.advanced_config; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_configs.advanced_config IS 'Additional configuration (rate limits, custom settings)';


--
-- Name: COLUMN tenant_configs.fallback_agent; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_configs.fallback_agent IS 'Agent to use when no specific routing matches';


--
-- Name: tenant_credentials; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.tenant_credentials (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    organization_id uuid NOT NULL,
    whatsapp_access_token_encrypted text,
    whatsapp_phone_number_id character varying(50),
    whatsapp_verify_token_encrypted text,
    dux_api_key_encrypted text,
    dux_api_base_url character varying(255),
    plex_api_url character varying(255),
    plex_api_user character varying(100),
    plex_api_pass_encrypted text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: COLUMN tenant_credentials.organization_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_credentials.organization_id IS 'Organization these credentials belong to (1:1 relationship)';


--
-- Name: COLUMN tenant_credentials.whatsapp_access_token_encrypted; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_credentials.whatsapp_access_token_encrypted IS 'Encrypted WhatsApp Graph API access token (pgcrypto)';


--
-- Name: COLUMN tenant_credentials.whatsapp_phone_number_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_credentials.whatsapp_phone_number_id IS 'WhatsApp Business phone number ID (not sensitive)';


--
-- Name: COLUMN tenant_credentials.whatsapp_verify_token_encrypted; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_credentials.whatsapp_verify_token_encrypted IS 'Encrypted webhook verification token (pgcrypto)';


--
-- Name: COLUMN tenant_credentials.dux_api_key_encrypted; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_credentials.dux_api_key_encrypted IS 'Encrypted DUX ERP API key (pgcrypto)';


--
-- Name: COLUMN tenant_credentials.dux_api_base_url; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_credentials.dux_api_base_url IS 'DUX API base URL (not sensitive)';


--
-- Name: COLUMN tenant_credentials.plex_api_url; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_credentials.plex_api_url IS 'Plex ERP API URL (not sensitive)';


--
-- Name: COLUMN tenant_credentials.plex_api_user; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_credentials.plex_api_user IS 'Plex ERP username (not sensitive)';


--
-- Name: COLUMN tenant_credentials.plex_api_pass_encrypted; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_credentials.plex_api_pass_encrypted IS 'Encrypted Plex ERP password (pgcrypto)';


--
-- Name: tenant_documents; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.tenant_documents (
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    title character varying(500) NOT NULL,
    content text NOT NULL,
    document_type character varying(100) NOT NULL,
    category character varying(200),
    tags character varying[] NOT NULL,
    meta_data jsonb NOT NULL,
    embedding public.vector(1024),
    search_vector tsvector,
    active boolean NOT NULL,
    sort_order integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: COLUMN tenant_documents.id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_documents.id IS 'Unique document identifier';


--
-- Name: COLUMN tenant_documents.organization_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_documents.organization_id IS 'Organization this document belongs to';


--
-- Name: COLUMN tenant_documents.title; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_documents.title IS 'Document title';


--
-- Name: COLUMN tenant_documents.content; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_documents.content IS 'Full document content in markdown/plain text';


--
-- Name: COLUMN tenant_documents.document_type; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_documents.document_type IS 'Type classification (faq, guide, policy, product_info, etc.)';


--
-- Name: COLUMN tenant_documents.category; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_documents.category IS 'Secondary category for finer classification';


--
-- Name: COLUMN tenant_documents.tags; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_documents.tags IS 'Flexible tags for filtering and categorization';


--
-- Name: COLUMN tenant_documents.meta_data; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_documents.meta_data IS 'Additional metadata (author, source, version, language, etc.)';


--
-- Name: COLUMN tenant_documents.embedding; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_documents.embedding IS 'Vector embedding (1024-dim) for semantic search using BAAI/bge-m3 via Infinity';


--
-- Name: COLUMN tenant_documents.search_vector; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_documents.search_vector IS 'Full-text search vector (auto-generated from title + content)';


--
-- Name: COLUMN tenant_documents.active; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_documents.active IS 'Whether this document is active and searchable';


--
-- Name: COLUMN tenant_documents.sort_order; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_documents.sort_order IS 'Order for displaying documents (lower = first)';


--
-- Name: tenant_institution_configs; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.tenant_institution_configs (
    id uuid DEFAULT gen_random_uuid() CONSTRAINT medical_institution_configs_id_not_null NOT NULL,
    organization_id uuid CONSTRAINT medical_institution_configs_organization_id_not_null NOT NULL,
    institution_key character varying(100) CONSTRAINT medical_institution_configs_institution_key_not_null NOT NULL,
    institution_name character varying(255) CONSTRAINT medical_institution_configs_institution_name_not_null NOT NULL,
    enabled boolean DEFAULT true CONSTRAINT medical_institution_configs_enabled_not_null NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() CONSTRAINT medical_institution_configs_created_at_not_null NOT NULL,
    updated_at timestamp with time zone DEFAULT now() CONSTRAINT medical_institution_configs_updated_at_not_null NOT NULL,
    institution_type character varying(50) DEFAULT 'generic'::character varying NOT NULL,
    settings jsonb DEFAULT '{}'::jsonb NOT NULL,
    encrypted_secrets bytea
);


--
-- Name: COLUMN tenant_institution_configs.organization_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_institution_configs.organization_id IS 'Organization this config belongs to';


--
-- Name: COLUMN tenant_institution_configs.institution_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_institution_configs.institution_key IS 'Unique key for the institution (e.g., ''patologia_digestiva'', ''mercedario'')';


--
-- Name: COLUMN tenant_institution_configs.institution_name; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_institution_configs.institution_name IS 'Human-readable institution name';


--
-- Name: COLUMN tenant_institution_configs.enabled; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_institution_configs.enabled IS 'Whether this institution configuration is active';


--
-- Name: COLUMN tenant_institution_configs.description; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_institution_configs.description IS 'Description or notes about this institution';


--
-- Name: tenant_prompts; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.tenant_prompts (
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    prompt_key character varying(255) NOT NULL,
    scope character varying(20) NOT NULL,
    user_id uuid,
    template text NOT NULL,
    description text,
    version character varying(50) NOT NULL,
    meta_data jsonb NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: COLUMN tenant_prompts.id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_prompts.id IS 'Unique prompt identifier';


--
-- Name: COLUMN tenant_prompts.organization_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_prompts.organization_id IS 'Organization this prompt belongs to';


--
-- Name: COLUMN tenant_prompts.prompt_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_prompts.prompt_key IS 'Key matching PromptRegistry (e.g., ''product.search.intent'')';


--
-- Name: COLUMN tenant_prompts.scope; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_prompts.scope IS 'Override scope: ''org'' (organization) or ''user'' (user-specific)';


--
-- Name: COLUMN tenant_prompts.user_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_prompts.user_id IS 'User ID for user-scope prompts (null for org-scope)';


--
-- Name: COLUMN tenant_prompts.template; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_prompts.template IS 'The prompt template text with {variable} placeholders';


--
-- Name: COLUMN tenant_prompts.description; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_prompts.description IS 'Description of this prompt''s purpose';


--
-- Name: COLUMN tenant_prompts.version; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_prompts.version IS 'Semantic version of this prompt';


--
-- Name: COLUMN tenant_prompts.meta_data; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_prompts.meta_data IS 'Additional metadata (required_variables, temperature, max_tokens, model)';


--
-- Name: COLUMN tenant_prompts.is_active; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tenant_prompts.is_active IS 'Whether this override is active';


--
-- Name: users; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.users (
    id uuid NOT NULL,
    username character varying(50) NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    full_name character varying(255),
    disabled boolean NOT NULL,
    scopes character varying[] NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: credit_accounts; Type: TABLE; Schema: credit; Owner: -
--

CREATE TABLE credit.credit_accounts (
    id integer NOT NULL,
    account_number character varying(50) NOT NULL,
    customer_id integer NOT NULL,
    customer_name character varying(200),
    credit_limit numeric(15,2) NOT NULL,
    interest_rate numeric(5,4) NOT NULL,
    risk_level public.risklevel NOT NULL,
    used_credit numeric(15,2) NOT NULL,
    pending_charges numeric(15,2) NOT NULL,
    accrued_interest numeric(15,2) NOT NULL,
    payment_day integer NOT NULL,
    minimum_payment_percentage numeric(5,4) NOT NULL,
    grace_period_days integer NOT NULL,
    status public.accountstatus NOT NULL,
    collection_status public.collectionstatus NOT NULL,
    opened_at timestamp without time zone,
    activated_at timestamp without time zone,
    last_payment_date date,
    next_payment_date date,
    last_statement_date date,
    blocked_at timestamp without time zone,
    closed_at timestamp without time zone,
    consecutive_on_time_payments integer NOT NULL,
    consecutive_late_payments integer NOT NULL,
    total_payments_made integer NOT NULL,
    days_overdue integer NOT NULL,
    last_collection_action timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone
);


--
-- Name: credit_accounts_id_seq; Type: SEQUENCE; Schema: credit; Owner: -
--

CREATE SEQUENCE credit.credit_accounts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: credit_accounts_id_seq; Type: SEQUENCE OWNED BY; Schema: credit; Owner: -
--

ALTER SEQUENCE credit.credit_accounts_id_seq OWNED BY credit.credit_accounts.id;


--
-- Name: payment_schedule_items; Type: TABLE; Schema: credit; Owner: -
--

CREATE TABLE credit.payment_schedule_items (
    id integer NOT NULL,
    account_id integer NOT NULL,
    due_date date NOT NULL,
    amount numeric(15,2) NOT NULL,
    principal_amount numeric(15,2),
    interest_amount numeric(15,2),
    status character varying(30) NOT NULL,
    paid_date date,
    paid_amount numeric(15,2),
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone
);


--
-- Name: payment_schedule_items_id_seq; Type: SEQUENCE; Schema: credit; Owner: -
--

CREATE SEQUENCE credit.payment_schedule_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payment_schedule_items_id_seq; Type: SEQUENCE OWNED BY; Schema: credit; Owner: -
--

ALTER SEQUENCE credit.payment_schedule_items_id_seq OWNED BY credit.payment_schedule_items.id;


--
-- Name: payments; Type: TABLE; Schema: credit; Owner: -
--

CREATE TABLE credit.payments (
    id integer NOT NULL,
    account_id integer NOT NULL,
    customer_id integer,
    account_number character varying(50),
    amount numeric(15,2) NOT NULL,
    payment_type public.paymenttype NOT NULL,
    payment_method public.paymentmethod NOT NULL,
    status public.paymentstatus NOT NULL,
    transaction_id character varying(100),
    reference_number character varying(50) NOT NULL,
    receipt_url character varying(500),
    interest_paid numeric(15,2) NOT NULL,
    charges_paid numeric(15,2) NOT NULL,
    principal_paid numeric(15,2) NOT NULL,
    initiated_at timestamp without time zone,
    processed_at timestamp without time zone,
    completed_at timestamp without time zone,
    failed_at timestamp without time zone,
    failure_reason text,
    retry_count integer NOT NULL,
    description text,
    notes text,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone
);


--
-- Name: payments_id_seq; Type: SEQUENCE; Schema: credit; Owner: -
--

CREATE SEQUENCE credit.payments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payments_id_seq; Type: SEQUENCE OWNED BY; Schema: credit; Owner: -
--

ALTER SEQUENCE credit.payments_id_seq OWNED BY credit.payments.id;


--
-- Name: analytics; Type: TABLE; Schema: ecommerce; Owner: -
--

CREATE TABLE ecommerce.analytics (
    id uuid NOT NULL,
    metric_name character varying(100) NOT NULL,
    metric_value double precision NOT NULL,
    metric_data jsonb,
    period_type character varying(20),
    period_start timestamp without time zone NOT NULL,
    period_end timestamp without time zone NOT NULL,
    created_at timestamp without time zone
);


--
-- Name: brands; Type: TABLE; Schema: ecommerce; Owner: -
--

CREATE TABLE ecommerce.brands (
    id uuid NOT NULL,
    name character varying(100) NOT NULL,
    display_name character varying(200) NOT NULL,
    reputation character varying(50),
    specialty character varying(100),
    warranty_years integer,
    description text,
    active boolean,
    external_code character varying(100),
    meta_data jsonb,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: categories; Type: TABLE; Schema: ecommerce; Owner: -
--

CREATE TABLE ecommerce.categories (
    id uuid NOT NULL,
    name character varying(100) NOT NULL,
    display_name character varying(200) NOT NULL,
    description text,
    active boolean,
    sort_order integer,
    external_id character varying(100),
    meta_data jsonb,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: conversations; Type: TABLE; Schema: ecommerce; Owner: -
--

CREATE TABLE ecommerce.conversations (
    id uuid NOT NULL,
    customer_id uuid NOT NULL,
    session_id character varying(100),
    total_messages integer,
    user_messages integer,
    bot_messages integer,
    intent_detected character varying(100),
    products_shown jsonb,
    conversion_stage character varying(50),
    started_at timestamp without time zone,
    ended_at timestamp without time zone,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: customers; Type: TABLE; Schema: ecommerce; Owner: -
--

CREATE TABLE ecommerce.customers (
    id uuid NOT NULL,
    phone_number character varying(20) NOT NULL,
    name character varying(200),
    first_name character varying(100),
    last_name character varying(100),
    profile_name character varying(200),
    date_of_birth timestamp without time zone,
    gender character varying(10),
    total_interactions integer,
    total_inquiries integer,
    interests jsonb,
    preferences jsonb,
    meta_data jsonb,
    budget_range character varying(50),
    preferred_brands jsonb,
    active boolean,
    blocked boolean,
    vip boolean,
    first_contact timestamp without time zone,
    last_contact timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: messages; Type: TABLE; Schema: ecommerce; Owner: -
--

CREATE TABLE ecommerce.messages (
    id uuid NOT NULL,
    user_phone character varying NOT NULL,
    conversation_id uuid NOT NULL,
    message_type character varying(20) NOT NULL,
    content text NOT NULL,
    intent character varying(100),
    confidence double precision,
    whatsapp_message_id character varying(100),
    message_format character varying(20),
    created_at timestamp without time zone
);


--
-- Name: order_items; Type: TABLE; Schema: ecommerce; Owner: -
--

CREATE TABLE ecommerce.order_items (
    id uuid NOT NULL,
    order_id uuid NOT NULL,
    product_id uuid NOT NULL,
    quantity integer NOT NULL,
    unit_price double precision NOT NULL,
    total_price double precision NOT NULL,
    product_name character varying(255) NOT NULL,
    product_sku character varying(50),
    product_specs text,
    meta_data jsonb,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: orders; Type: TABLE; Schema: ecommerce; Owner: -
--

CREATE TABLE ecommerce.orders (
    id uuid NOT NULL,
    order_number character varying(50) NOT NULL,
    customer_id uuid NOT NULL,
    status character varying(20) NOT NULL,
    subtotal double precision NOT NULL,
    total_amount double precision NOT NULL,
    tax_amount double precision,
    shipping_amount double precision,
    discount_amount double precision,
    payment_status character varying(20),
    payment_method character varying(50),
    payment_reference character varying(100),
    shipping_address jsonb,
    shipping_method character varying(50),
    tracking_number character varying(100),
    order_date timestamp without time zone NOT NULL,
    expected_delivery timestamp without time zone,
    delivered_at timestamp without time zone,
    notes text,
    internal_notes text,
    meta_data jsonb,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: price_history; Type: TABLE; Schema: ecommerce; Owner: -
--

CREATE TABLE ecommerce.price_history (
    id uuid NOT NULL,
    product_id uuid NOT NULL,
    price double precision NOT NULL,
    change_reason character varying(100),
    notes text,
    created_at timestamp without time zone
);


--
-- Name: product_attributes; Type: TABLE; Schema: ecommerce; Owner: -
--

CREATE TABLE ecommerce.product_attributes (
    id uuid NOT NULL,
    product_id uuid NOT NULL,
    name character varying(100) NOT NULL,
    value character varying(500) NOT NULL,
    attribute_type character varying(50),
    is_searchable boolean,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: product_images; Type: TABLE; Schema: ecommerce; Owner: -
--

CREATE TABLE ecommerce.product_images (
    id uuid NOT NULL,
    product_id uuid NOT NULL,
    url character varying(1000) NOT NULL,
    alt_text character varying(200),
    is_primary boolean,
    sort_order integer,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: product_inquiries; Type: TABLE; Schema: ecommerce; Owner: -
--

CREATE TABLE ecommerce.product_inquiries (
    id uuid NOT NULL,
    customer_id uuid NOT NULL,
    product_id uuid,
    category_id uuid,
    inquiry_type character varying(50) NOT NULL,
    inquiry_text text,
    budget_mentioned double precision,
    urgency character varying(20),
    status character varying(20),
    created_at timestamp without time zone,
    responded_at timestamp without time zone
);


--
-- Name: product_promotions; Type: TABLE; Schema: ecommerce; Owner: -
--

CREATE TABLE ecommerce.product_promotions (
    product_id uuid,
    promotion_id uuid
);


--
-- Name: product_reviews; Type: TABLE; Schema: ecommerce; Owner: -
--

CREATE TABLE ecommerce.product_reviews (
    id uuid NOT NULL,
    product_id uuid NOT NULL,
    customer_id uuid,
    customer_name character varying(200),
    customer_phone character varying(20),
    rating integer NOT NULL,
    review_text text,
    verified_purchase boolean,
    helpful_votes integer,
    active boolean,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: products; Type: TABLE; Schema: ecommerce; Owner: -
--

CREATE TABLE ecommerce.products (
    id uuid NOT NULL,
    name character varying(255) NOT NULL,
    model character varying(100),
    specs text NOT NULL,
    description text,
    short_description character varying(500),
    price double precision NOT NULL,
    original_price double precision,
    cost_price numeric(10,2),
    stock integer,
    min_stock integer,
    sku character varying(50),
    cost double precision,
    tax_percentage double precision,
    external_code character varying(100),
    image_url character varying(1000),
    barcode character varying(100),
    category_id uuid NOT NULL,
    subcategory_id uuid,
    brand_id uuid,
    technical_specs jsonb,
    features jsonb,
    images jsonb,
    active boolean,
    featured boolean,
    on_sale boolean,
    weight double precision,
    dimensions jsonb,
    search_vector tsvector,
    embedding public.vector(1024),
    meta_data jsonb,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    CONSTRAINT check_price_positive CHECK ((price >= (0)::double precision)),
    CONSTRAINT check_stock_non_negative CHECK ((stock >= 0))
);


--
-- Name: COLUMN products.embedding; Type: COMMENT; Schema: ecommerce; Owner: -
--

COMMENT ON COLUMN ecommerce.products.embedding IS 'Vector embedding (1024-dim) for semantic search using BAAI/bge-m3 via Infinity';


--
-- Name: promotions; Type: TABLE; Schema: ecommerce; Owner: -
--

CREATE TABLE ecommerce.promotions (
    id uuid NOT NULL,
    name character varying(200) NOT NULL,
    description text,
    discount_percentage double precision,
    discount_amount double precision,
    promo_code character varying(50),
    valid_from timestamp without time zone,
    valid_until timestamp without time zone NOT NULL,
    max_uses integer,
    current_uses integer,
    min_purchase_amount double precision,
    applicable_categories jsonb,
    active boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: stock_movements; Type: TABLE; Schema: ecommerce; Owner: -
--

CREATE TABLE ecommerce.stock_movements (
    id uuid NOT NULL,
    product_id uuid NOT NULL,
    movement_type character varying(20) NOT NULL,
    quantity integer NOT NULL,
    previous_stock integer NOT NULL,
    new_stock integer NOT NULL,
    reason character varying(100),
    notes text,
    reference_number character varying(100),
    created_at timestamp without time zone,
    created_by character varying(100)
);


--
-- Name: subcategories; Type: TABLE; Schema: ecommerce; Owner: -
--

CREATE TABLE ecommerce.subcategories (
    id uuid NOT NULL,
    name character varying(100) NOT NULL,
    display_name character varying(200) NOT NULL,
    description text,
    category_id uuid NOT NULL,
    active boolean,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: appointments; Type: TABLE; Schema: healthcare; Owner: -
--

CREATE TABLE healthcare.appointments (
    id integer NOT NULL,
    patient_id integer NOT NULL,
    doctor_id integer,
    patient_name character varying(200),
    doctor_name character varying(200),
    appointment_date date NOT NULL,
    start_time time without time zone NOT NULL,
    end_time time without time zone,
    duration_minutes integer,
    specialty public.doctorspecialty NOT NULL,
    appointment_type character varying(50),
    is_emergency boolean,
    triage_priority public.triagepriority,
    status public.appointmentstatus NOT NULL,
    location character varying(100),
    is_telemedicine boolean,
    video_call_url character varying(500),
    reason text,
    symptoms json,
    notes text,
    diagnosis text,
    prescriptions json,
    reminder_sent boolean,
    reminder_sent_at timestamp without time zone,
    confirmed_at timestamp without time zone,
    started_at timestamp without time zone,
    completed_at timestamp without time zone,
    cancelled_at timestamp without time zone,
    cancellation_reason text,
    cancelled_by character varying(50),
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone
);


--
-- Name: appointments_id_seq; Type: SEQUENCE; Schema: healthcare; Owner: -
--

CREATE SEQUENCE healthcare.appointments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: appointments_id_seq; Type: SEQUENCE OWNED BY; Schema: healthcare; Owner: -
--

ALTER SEQUENCE healthcare.appointments_id_seq OWNED BY healthcare.appointments.id;


--
-- Name: doctors; Type: TABLE; Schema: healthcare; Owner: -
--

CREATE TABLE healthcare.doctors (
    id integer NOT NULL,
    first_name character varying(100) NOT NULL,
    last_name character varying(100) NOT NULL,
    national_id character varying(20),
    license_number character varying(50) NOT NULL,
    specialty public.doctorspecialty NOT NULL,
    secondary_specialties json,
    email character varying(255),
    phone character varying(20),
    working_days json,
    working_hours_start time without time zone,
    working_hours_end time without time zone,
    appointment_duration_minutes integer,
    is_active boolean,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone
);


--
-- Name: doctors_id_seq; Type: SEQUENCE; Schema: healthcare; Owner: -
--

CREATE SEQUENCE healthcare.doctors_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: doctors_id_seq; Type: SEQUENCE OWNED BY; Schema: healthcare; Owner: -
--

ALTER SEQUENCE healthcare.doctors_id_seq OWNED BY healthcare.doctors.id;


--
-- Name: patients; Type: TABLE; Schema: healthcare; Owner: -
--

CREATE TABLE healthcare.patients (
    id integer NOT NULL,
    first_name character varying(100) NOT NULL,
    last_name character varying(100) NOT NULL,
    date_of_birth date,
    gender character varying(1),
    national_id character varying(20),
    email character varying(255),
    phone character varying(20),
    address_street character varying(255),
    address_city character varying(100),
    address_state character varying(100),
    address_postal_code character varying(20),
    address_country character varying(100),
    emergency_contact_name character varying(100),
    emergency_contact_relationship character varying(50),
    emergency_contact_phone character varying(20),
    emergency_contact_email character varying(255),
    blood_type character varying(5),
    allergies json,
    chronic_conditions json,
    current_medications json,
    insurance_provider character varying(100),
    insurance_policy_number character varying(50),
    insurance_group_number character varying(50),
    insurance_valid_until date,
    status public.patientstatus NOT NULL,
    last_vitals json,
    last_vitals_date timestamp without time zone,
    medical_record_number character varying(50),
    notes text,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone
);


--
-- Name: patients_id_seq; Type: SEQUENCE; Schema: healthcare; Owner: -
--

CREATE SEQUENCE healthcare.patients_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: patients_id_seq; Type: SEQUENCE OWNED BY; Schema: healthcare; Owner: -
--

ALTER SEQUENCE healthcare.patients_id_seq OWNED BY healthcare.patients.id;


--
-- Name: pharmacy_merchant_configs; Type: TABLE; Schema: pharmacy; Owner: -
--

CREATE TABLE pharmacy.pharmacy_merchant_configs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    organization_id uuid NOT NULL,
    pharmacy_name character varying(255) DEFAULT 'Farmacia'::character varying NOT NULL,
    pharmacy_address character varying(500),
    pharmacy_phone character varying(50),
    pharmacy_logo_path character varying(500),
    mp_enabled boolean DEFAULT false NOT NULL,
    mp_access_token character varying(500),
    mp_public_key character varying(255),
    mp_webhook_secret character varying(255),
    mp_sandbox boolean DEFAULT true NOT NULL,
    mp_timeout integer DEFAULT 30 NOT NULL,
    mp_notification_url character varying(500),
    receipt_public_url_base character varying(500),
    whatsapp_phone_number character varying(20),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    pharmacy_email character varying(255),
    pharmacy_website character varying(500),
    pharmacy_hours jsonb,
    pharmacy_is_24h boolean DEFAULT false NOT NULL,
    payment_option_half_percent integer DEFAULT 50 NOT NULL,
    payment_option_minimum_percent integer DEFAULT 30 CONSTRAINT pharmacy_merchant_configs_payment_option_minimum_perce_not_null NOT NULL,
    payment_minimum_amount integer DEFAULT 1000 NOT NULL,
    bot_service_hours jsonb,
    bot_service_enabled boolean DEFAULT false NOT NULL,
    emergency_phone character varying(50),
    name_match_threshold numeric(3,2) DEFAULT 0.70
);


--
-- Name: COLUMN pharmacy_merchant_configs.organization_id; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.organization_id IS 'Organization this config belongs to (1:1 relationship)';


--
-- Name: COLUMN pharmacy_merchant_configs.pharmacy_name; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.pharmacy_name IS 'Pharmacy name displayed on PDF receipts';


--
-- Name: COLUMN pharmacy_merchant_configs.pharmacy_address; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.pharmacy_address IS 'Pharmacy address displayed on PDF receipts';


--
-- Name: COLUMN pharmacy_merchant_configs.pharmacy_phone; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.pharmacy_phone IS 'Pharmacy phone displayed on PDF receipts';


--
-- Name: COLUMN pharmacy_merchant_configs.pharmacy_logo_path; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.pharmacy_logo_path IS 'Path to pharmacy logo image for PDF receipts';


--
-- Name: COLUMN pharmacy_merchant_configs.mp_enabled; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.mp_enabled IS 'Whether Mercado Pago integration is enabled';


--
-- Name: COLUMN pharmacy_merchant_configs.mp_access_token; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.mp_access_token IS 'Mercado Pago Access Token (APP_USR-xxx)';


--
-- Name: COLUMN pharmacy_merchant_configs.mp_public_key; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.mp_public_key IS 'Mercado Pago Public Key';


--
-- Name: COLUMN pharmacy_merchant_configs.mp_webhook_secret; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.mp_webhook_secret IS 'Secret for validating MP webhook signatures';


--
-- Name: COLUMN pharmacy_merchant_configs.mp_sandbox; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.mp_sandbox IS 'Use Mercado Pago sandbox mode for testing';


--
-- Name: COLUMN pharmacy_merchant_configs.mp_timeout; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.mp_timeout IS 'Timeout for Mercado Pago API requests in seconds';


--
-- Name: COLUMN pharmacy_merchant_configs.mp_notification_url; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.mp_notification_url IS 'Public URL for Mercado Pago webhook notifications';


--
-- Name: COLUMN pharmacy_merchant_configs.receipt_public_url_base; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.receipt_public_url_base IS 'Base URL for public PDF receipt access';


--
-- Name: COLUMN pharmacy_merchant_configs.whatsapp_phone_number; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.whatsapp_phone_number IS 'WhatsApp phone number for quick webhook org resolution';


--
-- Name: COLUMN pharmacy_merchant_configs.pharmacy_email; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.pharmacy_email IS 'Pharmacy contact email address';


--
-- Name: COLUMN pharmacy_merchant_configs.pharmacy_website; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.pharmacy_website IS 'Pharmacy website URL';


--
-- Name: COLUMN pharmacy_merchant_configs.pharmacy_hours; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.pharmacy_hours IS 'Pharmacy operating hours by day (JSONB format)';


--
-- Name: COLUMN pharmacy_merchant_configs.pharmacy_is_24h; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.pharmacy_is_24h IS 'Whether pharmacy operates 24 hours';


--
-- Name: COLUMN pharmacy_merchant_configs.payment_option_half_percent; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.payment_option_half_percent IS 'Percentage for ''half'' payment option (e.g., 50 for 50%)';


--
-- Name: COLUMN pharmacy_merchant_configs.payment_option_minimum_percent; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.payment_option_minimum_percent IS 'Percentage for ''minimum'' payment option (e.g., 30 for 30%)';


--
-- Name: COLUMN pharmacy_merchant_configs.payment_minimum_amount; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.payment_minimum_amount IS 'Minimum payment amount in currency units (e.g., 1000 for $1000)';


--
-- Name: COLUMN pharmacy_merchant_configs.bot_service_hours; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.bot_service_hours IS 'Bot service hours by day (JSONB format, e.g., {''lunes'': ''08:00-20:00''})';


--
-- Name: COLUMN pharmacy_merchant_configs.bot_service_enabled; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.bot_service_enabled IS 'Whether to enforce bot service hours (if False, bot is always available)';


--
-- Name: COLUMN pharmacy_merchant_configs.emergency_phone; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.emergency_phone IS 'Emergency contact phone for outside service hours';


--
-- Name: COLUMN pharmacy_merchant_configs.name_match_threshold; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.pharmacy_merchant_configs.name_match_threshold IS 'Minimum score for fuzzy name matching (0.0-1.0, default 0.7)';


--
-- Name: registered_persons; Type: TABLE; Schema: pharmacy; Owner: -
--

CREATE TABLE pharmacy.registered_persons (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    phone_number character varying(20) NOT NULL,
    dni character varying(20) NOT NULL,
    name character varying(255) NOT NULL,
    plex_customer_id integer NOT NULL,
    pharmacy_id uuid NOT NULL,
    is_self boolean DEFAULT false NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    last_used_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: COLUMN registered_persons.id; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.registered_persons.id IS 'Unique registration identifier';


--
-- Name: COLUMN registered_persons.phone_number; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.registered_persons.phone_number IS 'WhatsApp phone number that registered this person';


--
-- Name: COLUMN registered_persons.dni; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.registered_persons.dni IS 'Document number (validated against PLEX)';


--
-- Name: COLUMN registered_persons.name; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.registered_persons.name IS 'Full name (validated with LLM fuzzy matching)';


--
-- Name: COLUMN registered_persons.plex_customer_id; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.registered_persons.plex_customer_id IS 'PLEX customer ID for debt queries';


--
-- Name: COLUMN registered_persons.pharmacy_id; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.registered_persons.pharmacy_id IS 'Pharmacy this registration belongs to';


--
-- Name: COLUMN registered_persons.is_self; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.registered_persons.is_self IS 'True if person is the phone owner (auto-detected)';


--
-- Name: COLUMN registered_persons.expires_at; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.registered_persons.expires_at IS 'Registration expiration (refreshed to +180 days on each use)';


--
-- Name: COLUMN registered_persons.is_active; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.registered_persons.is_active IS 'Soft-delete flag';


--
-- Name: COLUMN registered_persons.last_used_at; Type: COMMENT; Schema: pharmacy; Owner: -
--

COMMENT ON COLUMN pharmacy.registered_persons.last_used_at IS 'Last time this registration was used';


--
-- Name: incident_categories; Type: TABLE; Schema: soporte; Owner: -
--

CREATE TABLE soporte.incident_categories (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    parent_id uuid,
    sla_response_hours integer DEFAULT 24,
    sla_resolution_hours integer DEFAULT 72,
    jira_issue_type character varying(50) DEFAULT 'Bug'::character varying,
    is_active boolean DEFAULT true NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE incident_categories; Type: COMMENT; Schema: soporte; Owner: -
--

COMMENT ON TABLE soporte.incident_categories IS 'Dynamic incident categories with SLA and Jira mapping';


--
-- Name: incident_comments; Type: TABLE; Schema: soporte; Owner: -
--

CREATE TABLE soporte.incident_comments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    incident_id uuid NOT NULL,
    author_type soporte.soporte_comment_author_type_enum DEFAULT 'user'::soporte.soporte_comment_author_type_enum NOT NULL,
    author_name character varying(200),
    content text NOT NULL,
    is_internal boolean DEFAULT false NOT NULL,
    jira_comment_id character varying(50),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE incident_comments; Type: COMMENT; Schema: soporte; Owner: -
--

COMMENT ON TABLE soporte.incident_comments IS 'Comments on incidents';


--
-- Name: incident_history; Type: TABLE; Schema: soporte; Owner: -
--

CREATE TABLE soporte.incident_history (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    incident_id uuid NOT NULL,
    field_changed character varying(100) NOT NULL,
    old_value text,
    new_value text,
    changed_by character varying(200),
    changed_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE incident_history; Type: COMMENT; Schema: soporte; Owner: -
--

COMMENT ON TABLE soporte.incident_history IS 'Audit trail of incident changes';


--
-- Name: incidents; Type: TABLE; Schema: soporte; Owner: -
--

CREATE TABLE soporte.incidents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    folio character varying(20) NOT NULL,
    organization_id uuid,
    user_phone character varying(50) NOT NULL,
    user_name character varying(200),
    conversation_id uuid,
    incident_type soporte.soporte_incident_type_enum DEFAULT 'incident'::soporte.soporte_incident_type_enum NOT NULL,
    category_id uuid,
    subject character varying(500),
    description text NOT NULL,
    priority soporte.soporte_incident_priority_enum DEFAULT 'medium'::soporte.soporte_incident_priority_enum NOT NULL,
    urgency soporte.soporte_incident_urgency_enum DEFAULT 'medium'::soporte.soporte_incident_urgency_enum,
    impact soporte.soporte_incident_impact_enum,
    status soporte.soporte_incident_status_enum DEFAULT 'open'::soporte.soporte_incident_status_enum NOT NULL,
    source soporte.soporte_incident_source_enum DEFAULT 'whatsapp'::soporte.soporte_incident_source_enum NOT NULL,
    environment character varying(100),
    steps_to_reproduce text,
    expected_behavior text,
    actual_behavior text,
    attachments jsonb DEFAULT '[]'::jsonb,
    jira_issue_key character varying(50),
    jira_issue_id character varying(50),
    jira_project_key character varying(20),
    jira_sync_status soporte.soporte_jira_sync_status_enum DEFAULT 'pending'::soporte.soporte_jira_sync_status_enum,
    jira_last_sync_at timestamp without time zone,
    jira_sync_error text,
    resolution text,
    resolution_type character varying(100),
    resolved_at timestamp without time zone,
    resolved_by character varying(200),
    sla_response_due timestamp without time zone,
    sla_resolution_due timestamp without time zone,
    sla_response_met boolean,
    sla_resolution_met boolean,
    meta_data jsonb DEFAULT '{}'::jsonb,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE incidents; Type: COMMENT; Schema: soporte; Owner: -
--

COMMENT ON TABLE soporte.incidents IS 'Main incidents/tickets table';


--
-- Name: jira_configs; Type: TABLE; Schema: soporte; Owner: -
--

CREATE TABLE soporte.jira_configs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    organization_id uuid,
    name character varying(100) NOT NULL,
    jira_base_url character varying(500) NOT NULL,
    jira_project_key character varying(20) NOT NULL,
    jira_api_token_encrypted text,
    jira_email character varying(200) NOT NULL,
    webhook_secret character varying(200),
    category_mapping jsonb DEFAULT '{}'::jsonb,
    module_mapping jsonb DEFAULT '{}'::jsonb,
    priority_mapping jsonb DEFAULT '{}'::jsonb,
    custom_fields jsonb DEFAULT '{}'::jsonb,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE jira_configs; Type: COMMENT; Schema: soporte; Owner: -
--

COMMENT ON TABLE soporte.jira_configs IS 'Multi-Jira configuration per organization';


--
-- Name: pending_tickets; Type: TABLE; Schema: soporte; Owner: -
--

CREATE TABLE soporte.pending_tickets (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    conversation_id character varying(255) NOT NULL,
    user_phone character varying(50) NOT NULL,
    current_step character varying(50) DEFAULT 'description'::character varying NOT NULL,
    collected_data jsonb DEFAULT '{}'::jsonb NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone DEFAULT (now() + '00:30:00'::interval) NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);


--
-- Name: TABLE pending_tickets; Type: COMMENT; Schema: soporte; Owner: -
--

COMMENT ON TABLE soporte.pending_tickets IS 'Conversational flow state for ticket creation';


--
-- Name: credit_accounts id; Type: DEFAULT; Schema: credit; Owner: -
--

ALTER TABLE ONLY credit.credit_accounts ALTER COLUMN id SET DEFAULT nextval('credit.credit_accounts_id_seq'::regclass);


--
-- Name: payment_schedule_items id; Type: DEFAULT; Schema: credit; Owner: -
--

ALTER TABLE ONLY credit.payment_schedule_items ALTER COLUMN id SET DEFAULT nextval('credit.payment_schedule_items_id_seq'::regclass);


--
-- Name: payments id; Type: DEFAULT; Schema: credit; Owner: -
--

ALTER TABLE ONLY credit.payments ALTER COLUMN id SET DEFAULT nextval('credit.payments_id_seq'::regclass);


--
-- Name: appointments id; Type: DEFAULT; Schema: healthcare; Owner: -
--

ALTER TABLE ONLY healthcare.appointments ALTER COLUMN id SET DEFAULT nextval('healthcare.appointments_id_seq'::regclass);


--
-- Name: doctors id; Type: DEFAULT; Schema: healthcare; Owner: -
--

ALTER TABLE ONLY healthcare.doctors ALTER COLUMN id SET DEFAULT nextval('healthcare.doctors_id_seq'::regclass);


--
-- Name: patients id; Type: DEFAULT; Schema: healthcare; Owner: -
--

ALTER TABLE ONLY healthcare.patients ALTER COLUMN id SET DEFAULT nextval('healthcare.patients_id_seq'::regclass);


--
-- Name: agent_knowledge agent_knowledge_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.agent_knowledge
    ADD CONSTRAINT agent_knowledge_pkey PRIMARY KEY (id);


--
-- Name: agents agents_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.agents
    ADD CONSTRAINT agents_pkey PRIMARY KEY (id);


--
-- Name: ai_models ai_models_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.ai_models
    ADD CONSTRAINT ai_models_pkey PRIMARY KEY (id);


--
-- Name: awaiting_type_configs awaiting_type_configs_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.awaiting_type_configs
    ADD CONSTRAINT awaiting_type_configs_pkey PRIMARY KEY (id);


--
-- Name: bypass_rules bypass_rules_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.bypass_rules
    ADD CONSTRAINT bypass_rules_pkey PRIMARY KEY (id);


--
-- Name: chattigo_credentials chattigo_credentials_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.chattigo_credentials
    ADD CONSTRAINT chattigo_credentials_pkey PRIMARY KEY (id);


--
-- Name: company_knowledge company_knowledge_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.company_knowledge
    ADD CONSTRAINT company_knowledge_pkey PRIMARY KEY (id);


--
-- Name: contact_domains contact_domains_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.contact_domains
    ADD CONSTRAINT contact_domains_pkey PRIMARY KEY (id);


--
-- Name: conversation_contexts conversation_contexts_conversation_id_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.conversation_contexts
    ADD CONSTRAINT conversation_contexts_conversation_id_key UNIQUE (conversation_id);


--
-- Name: conversation_contexts conversation_contexts_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.conversation_contexts
    ADD CONSTRAINT conversation_contexts_pkey PRIMARY KEY (id);


--
-- Name: conversation_messages conversation_messages_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.conversation_messages
    ADD CONSTRAINT conversation_messages_pkey PRIMARY KEY (id);


--
-- Name: domain_configs domain_configs_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.domain_configs
    ADD CONSTRAINT domain_configs_pkey PRIMARY KEY (domain);


--
-- Name: domain_intents domain_intents_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.domain_intents
    ADD CONSTRAINT domain_intents_pkey PRIMARY KEY (id);


--
-- Name: domains domains_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.domains
    ADD CONSTRAINT domains_pkey PRIMARY KEY (id);


--
-- Name: flow_agent_configs flow_agent_configs_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.flow_agent_configs
    ADD CONSTRAINT flow_agent_configs_pkey PRIMARY KEY (id);


--
-- Name: intent_agent_mappings intent_agent_mappings_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.intent_agent_mappings
    ADD CONSTRAINT intent_agent_mappings_pkey PRIMARY KEY (id);


--
-- Name: keyword_agent_mappings keyword_agent_mappings_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.keyword_agent_mappings
    ADD CONSTRAINT keyword_agent_mappings_pkey PRIMARY KEY (id);


--
-- Name: tenant_institution_configs medical_institution_configs_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tenant_institution_configs
    ADD CONSTRAINT medical_institution_configs_pkey PRIMARY KEY (id);


--
-- Name: organization_users organization_users_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.organization_users
    ADD CONSTRAINT organization_users_pkey PRIMARY KEY (id);


--
-- Name: organizations organizations_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.organizations
    ADD CONSTRAINT organizations_pkey PRIMARY KEY (id);


--
-- Name: rag_query_logs rag_query_logs_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.rag_query_logs
    ADD CONSTRAINT rag_query_logs_pkey PRIMARY KEY (id);


--
-- Name: response_configs response_configs_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.response_configs
    ADD CONSTRAINT response_configs_pkey PRIMARY KEY (id);


--
-- Name: routing_configs routing_configs_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.routing_configs
    ADD CONSTRAINT routing_configs_pkey PRIMARY KEY (id);


--
-- Name: tenant_agents tenant_agents_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tenant_agents
    ADD CONSTRAINT tenant_agents_pkey PRIMARY KEY (id);


--
-- Name: tenant_configs tenant_configs_organization_id_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tenant_configs
    ADD CONSTRAINT tenant_configs_organization_id_key UNIQUE (organization_id);


--
-- Name: tenant_configs tenant_configs_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tenant_configs
    ADD CONSTRAINT tenant_configs_pkey PRIMARY KEY (id);


--
-- Name: tenant_credentials tenant_credentials_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tenant_credentials
    ADD CONSTRAINT tenant_credentials_pkey PRIMARY KEY (id);


--
-- Name: tenant_documents tenant_documents_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tenant_documents
    ADD CONSTRAINT tenant_documents_pkey PRIMARY KEY (id);


--
-- Name: tenant_prompts tenant_prompts_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tenant_prompts
    ADD CONSTRAINT tenant_prompts_pkey PRIMARY KEY (id);


--
-- Name: agents uq_agents_agent_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.agents
    ADD CONSTRAINT uq_agents_agent_key UNIQUE (agent_key);


--
-- Name: ai_models uq_ai_models_model_id; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.ai_models
    ADD CONSTRAINT uq_ai_models_model_id UNIQUE (model_id);


--
-- Name: awaiting_type_configs uq_awaiting_type_configs_org_domain_type; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.awaiting_type_configs
    ADD CONSTRAINT uq_awaiting_type_configs_org_domain_type UNIQUE (organization_id, domain_key, awaiting_type);


--
-- Name: chattigo_credentials uq_chattigo_credentials_did; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.chattigo_credentials
    ADD CONSTRAINT uq_chattigo_credentials_did UNIQUE (did);


--
-- Name: domains uq_core_domains_domain_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.domains
    ADD CONSTRAINT uq_core_domains_domain_key UNIQUE (domain_key);


--
-- Name: domain_intents uq_domain_intents_org_domain_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.domain_intents
    ADD CONSTRAINT uq_domain_intents_org_domain_key UNIQUE (organization_id, domain_key, intent_key);


--
-- Name: flow_agent_configs uq_flow_agent_configs_org_agent; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.flow_agent_configs
    ADD CONSTRAINT uq_flow_agent_configs_org_agent UNIQUE (organization_id, agent_key);


--
-- Name: intent_agent_mappings uq_intent_agent_mappings_org_domain_intent; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.intent_agent_mappings
    ADD CONSTRAINT uq_intent_agent_mappings_org_domain_intent UNIQUE (organization_id, domain_key, intent_key);


--
-- Name: keyword_agent_mappings uq_keyword_agent_mappings_org_agent_keyword; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.keyword_agent_mappings
    ADD CONSTRAINT uq_keyword_agent_mappings_org_agent_keyword UNIQUE (organization_id, agent_key, keyword);


--
-- Name: tenant_agents uq_org_agent_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tenant_agents
    ADD CONSTRAINT uq_org_agent_key UNIQUE (organization_id, agent_key);


--
-- Name: bypass_rules uq_org_bypass_rule_name; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.bypass_rules
    ADD CONSTRAINT uq_org_bypass_rule_name UNIQUE (organization_id, rule_name);


--
-- Name: tenant_prompts uq_org_prompt_key_scope_user; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tenant_prompts
    ADD CONSTRAINT uq_org_prompt_key_scope_user UNIQUE (organization_id, prompt_key, scope, user_id);


--
-- Name: organization_users uq_org_user; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.organization_users
    ADD CONSTRAINT uq_org_user UNIQUE (organization_id, user_id);


--
-- Name: response_configs uq_response_configs_org_domain_intent; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.response_configs
    ADD CONSTRAINT uq_response_configs_org_domain_intent UNIQUE (organization_id, domain_key, intent_key);


--
-- Name: routing_configs uq_routing_configs_org_domain_type_trigger; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.routing_configs
    ADD CONSTRAINT uq_routing_configs_org_domain_type_trigger UNIQUE (organization_id, domain_key, config_type, trigger_value);


--
-- Name: tenant_credentials uq_tenant_credentials_org; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tenant_credentials
    ADD CONSTRAINT uq_tenant_credentials_org UNIQUE (organization_id);


--
-- Name: tenant_institution_configs uq_tenant_org_institution_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tenant_institution_configs
    ADD CONSTRAINT uq_tenant_org_institution_key UNIQUE (organization_id, institution_key);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: credit_accounts credit_accounts_pkey; Type: CONSTRAINT; Schema: credit; Owner: -
--

ALTER TABLE ONLY credit.credit_accounts
    ADD CONSTRAINT credit_accounts_pkey PRIMARY KEY (id);


--
-- Name: payment_schedule_items payment_schedule_items_pkey; Type: CONSTRAINT; Schema: credit; Owner: -
--

ALTER TABLE ONLY credit.payment_schedule_items
    ADD CONSTRAINT payment_schedule_items_pkey PRIMARY KEY (id);


--
-- Name: payments payments_pkey; Type: CONSTRAINT; Schema: credit; Owner: -
--

ALTER TABLE ONLY credit.payments
    ADD CONSTRAINT payments_pkey PRIMARY KEY (id);


--
-- Name: analytics analytics_pkey; Type: CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.analytics
    ADD CONSTRAINT analytics_pkey PRIMARY KEY (id);


--
-- Name: brands brands_name_key; Type: CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.brands
    ADD CONSTRAINT brands_name_key UNIQUE (name);


--
-- Name: brands brands_pkey; Type: CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.brands
    ADD CONSTRAINT brands_pkey PRIMARY KEY (id);


--
-- Name: categories categories_name_key; Type: CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.categories
    ADD CONSTRAINT categories_name_key UNIQUE (name);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: conversations conversations_pkey; Type: CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.conversations
    ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);


--
-- Name: customers customers_pkey; Type: CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.customers
    ADD CONSTRAINT customers_pkey PRIMARY KEY (id);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);


--
-- Name: order_items order_items_pkey; Type: CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.order_items
    ADD CONSTRAINT order_items_pkey PRIMARY KEY (id);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id);


--
-- Name: price_history price_history_pkey; Type: CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.price_history
    ADD CONSTRAINT price_history_pkey PRIMARY KEY (id);


--
-- Name: product_attributes product_attributes_pkey; Type: CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.product_attributes
    ADD CONSTRAINT product_attributes_pkey PRIMARY KEY (id);


--
-- Name: product_images product_images_pkey; Type: CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.product_images
    ADD CONSTRAINT product_images_pkey PRIMARY KEY (id);


--
-- Name: product_inquiries product_inquiries_pkey; Type: CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.product_inquiries
    ADD CONSTRAINT product_inquiries_pkey PRIMARY KEY (id);


--
-- Name: product_reviews product_reviews_pkey; Type: CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.product_reviews
    ADD CONSTRAINT product_reviews_pkey PRIMARY KEY (id);


--
-- Name: products products_pkey; Type: CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.products
    ADD CONSTRAINT products_pkey PRIMARY KEY (id);


--
-- Name: promotions promotions_pkey; Type: CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.promotions
    ADD CONSTRAINT promotions_pkey PRIMARY KEY (id);


--
-- Name: stock_movements stock_movements_pkey; Type: CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.stock_movements
    ADD CONSTRAINT stock_movements_pkey PRIMARY KEY (id);


--
-- Name: subcategories subcategories_pkey; Type: CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.subcategories
    ADD CONSTRAINT subcategories_pkey PRIMARY KEY (id);


--
-- Name: product_attributes uq_product_attribute_name; Type: CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.product_attributes
    ADD CONSTRAINT uq_product_attribute_name UNIQUE (product_id, name);


--
-- Name: appointments appointments_pkey; Type: CONSTRAINT; Schema: healthcare; Owner: -
--

ALTER TABLE ONLY healthcare.appointments
    ADD CONSTRAINT appointments_pkey PRIMARY KEY (id);


--
-- Name: doctors doctors_national_id_key; Type: CONSTRAINT; Schema: healthcare; Owner: -
--

ALTER TABLE ONLY healthcare.doctors
    ADD CONSTRAINT doctors_national_id_key UNIQUE (national_id);


--
-- Name: doctors doctors_pkey; Type: CONSTRAINT; Schema: healthcare; Owner: -
--

ALTER TABLE ONLY healthcare.doctors
    ADD CONSTRAINT doctors_pkey PRIMARY KEY (id);


--
-- Name: patients patients_pkey; Type: CONSTRAINT; Schema: healthcare; Owner: -
--

ALTER TABLE ONLY healthcare.patients
    ADD CONSTRAINT patients_pkey PRIMARY KEY (id);


--
-- Name: pharmacy_merchant_configs pharmacy_merchant_configs_pkey; Type: CONSTRAINT; Schema: pharmacy; Owner: -
--

ALTER TABLE ONLY pharmacy.pharmacy_merchant_configs
    ADD CONSTRAINT pharmacy_merchant_configs_pkey PRIMARY KEY (id);


--
-- Name: registered_persons registered_persons_pkey; Type: CONSTRAINT; Schema: pharmacy; Owner: -
--

ALTER TABLE ONLY pharmacy.registered_persons
    ADD CONSTRAINT registered_persons_pkey PRIMARY KEY (id);


--
-- Name: registered_persons uq_registered_persons_phone_dni_pharmacy; Type: CONSTRAINT; Schema: pharmacy; Owner: -
--

ALTER TABLE ONLY pharmacy.registered_persons
    ADD CONSTRAINT uq_registered_persons_phone_dni_pharmacy UNIQUE (phone_number, dni, pharmacy_id);


--
-- Name: incident_categories incident_categories_code_key; Type: CONSTRAINT; Schema: soporte; Owner: -
--

ALTER TABLE ONLY soporte.incident_categories
    ADD CONSTRAINT incident_categories_code_key UNIQUE (code);


--
-- Name: incident_categories incident_categories_pkey; Type: CONSTRAINT; Schema: soporte; Owner: -
--

ALTER TABLE ONLY soporte.incident_categories
    ADD CONSTRAINT incident_categories_pkey PRIMARY KEY (id);


--
-- Name: incident_comments incident_comments_pkey; Type: CONSTRAINT; Schema: soporte; Owner: -
--

ALTER TABLE ONLY soporte.incident_comments
    ADD CONSTRAINT incident_comments_pkey PRIMARY KEY (id);


--
-- Name: incident_history incident_history_pkey; Type: CONSTRAINT; Schema: soporte; Owner: -
--

ALTER TABLE ONLY soporte.incident_history
    ADD CONSTRAINT incident_history_pkey PRIMARY KEY (id);


--
-- Name: incidents incidents_folio_key; Type: CONSTRAINT; Schema: soporte; Owner: -
--

ALTER TABLE ONLY soporte.incidents
    ADD CONSTRAINT incidents_folio_key UNIQUE (folio);


--
-- Name: incidents incidents_pkey; Type: CONSTRAINT; Schema: soporte; Owner: -
--

ALTER TABLE ONLY soporte.incidents
    ADD CONSTRAINT incidents_pkey PRIMARY KEY (id);


--
-- Name: jira_configs jira_configs_pkey; Type: CONSTRAINT; Schema: soporte; Owner: -
--

ALTER TABLE ONLY soporte.jira_configs
    ADD CONSTRAINT jira_configs_pkey PRIMARY KEY (id);


--
-- Name: pending_tickets pending_tickets_pkey; Type: CONSTRAINT; Schema: soporte; Owner: -
--

ALTER TABLE ONLY soporte.pending_tickets
    ADD CONSTRAINT pending_tickets_pkey PRIMARY KEY (id);


--
-- Name: idx_agent_knowledge_active; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_agent_knowledge_active ON core.agent_knowledge USING btree (active);


--
-- Name: idx_agent_knowledge_agent_active; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_agent_knowledge_agent_active ON core.agent_knowledge USING btree (agent_key, active);


--
-- Name: idx_agent_knowledge_agent_key; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_agent_knowledge_agent_key ON core.agent_knowledge USING btree (agent_key);


--
-- Name: idx_agent_knowledge_agent_type; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_agent_knowledge_agent_type ON core.agent_knowledge USING btree (agent_key, document_type);


--
-- Name: idx_agent_knowledge_embedding_hnsw; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_agent_knowledge_embedding_hnsw ON core.agent_knowledge USING hnsw (embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64');


--
-- Name: idx_agent_knowledge_search_vector; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_agent_knowledge_search_vector ON core.agent_knowledge USING gin (search_vector);


--
-- Name: idx_agent_knowledge_tags; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_agent_knowledge_tags ON core.agent_knowledge USING gin (tags);


--
-- Name: idx_agent_knowledge_type_active; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_agent_knowledge_type_active ON core.agent_knowledge USING btree (document_type, active);


--
-- Name: idx_agents_agent_key; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_agents_agent_key ON core.agents USING btree (agent_key);


--
-- Name: idx_agents_agent_type; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_agents_agent_type ON core.agents USING btree (agent_type);


--
-- Name: idx_agents_domain_key; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_agents_domain_key ON core.agents USING btree (domain_key);


--
-- Name: idx_agents_enabled; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_agents_enabled ON core.agents USING btree (enabled);


--
-- Name: idx_agents_enabled_priority; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_agents_enabled_priority ON core.agents USING btree (enabled, priority DESC);


--
-- Name: idx_agents_priority; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_agents_priority ON core.agents USING btree (priority);


--
-- Name: idx_ai_models_enabled; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_ai_models_enabled ON core.ai_models USING btree (is_enabled);


--
-- Name: idx_ai_models_enabled_type; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_ai_models_enabled_type ON core.ai_models USING btree (is_enabled, model_type);


--
-- Name: idx_ai_models_model_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_ai_models_model_id ON core.ai_models USING btree (model_id);


--
-- Name: idx_ai_models_provider; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_ai_models_provider ON core.ai_models USING btree (provider);


--
-- Name: idx_ai_models_sort; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_ai_models_sort ON core.ai_models USING btree (sort_order);


--
-- Name: idx_ai_models_type; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_ai_models_type ON core.ai_models USING btree (model_type);


--
-- Name: idx_awaiting_type_configs_lookup; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_awaiting_type_configs_lookup ON core.awaiting_type_configs USING btree (organization_id, domain_key, is_enabled);


--
-- Name: idx_awaiting_type_configs_priority; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_awaiting_type_configs_priority ON core.awaiting_type_configs USING btree (priority);


--
-- Name: idx_awaiting_type_configs_type; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_awaiting_type_configs_type ON core.awaiting_type_configs USING btree (awaiting_type);


--
-- Name: idx_bypass_rules_enabled; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_bypass_rules_enabled ON core.bypass_rules USING btree (enabled);


--
-- Name: idx_bypass_rules_org_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_bypass_rules_org_id ON core.bypass_rules USING btree (organization_id);


--
-- Name: idx_bypass_rules_pharmacy_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_bypass_rules_pharmacy_id ON core.bypass_rules USING btree (pharmacy_id);


--
-- Name: idx_bypass_rules_priority; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_bypass_rules_priority ON core.bypass_rules USING btree (priority DESC);


--
-- Name: idx_bypass_rules_rule_type; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_bypass_rules_rule_type ON core.bypass_rules USING btree (rule_type);


--
-- Name: idx_chattigo_credentials_bypass_rule; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_chattigo_credentials_bypass_rule ON core.chattigo_credentials USING btree (bypass_rule_id);


--
-- Name: idx_chattigo_credentials_did; Type: INDEX; Schema: core; Owner: -
--

CREATE UNIQUE INDEX idx_chattigo_credentials_did ON core.chattigo_credentials USING btree (did);


--
-- Name: idx_chattigo_credentials_enabled; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_chattigo_credentials_enabled ON core.chattigo_credentials USING btree (enabled);


--
-- Name: idx_chattigo_credentials_org_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_chattigo_credentials_org_id ON core.chattigo_credentials USING btree (organization_id);


--
-- Name: idx_contact_domains_assigned_at; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_contact_domains_assigned_at ON core.contact_domains USING btree (assigned_at);


--
-- Name: idx_contact_domains_domain; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_contact_domains_domain ON core.contact_domains USING btree (domain);


--
-- Name: idx_contact_domains_method; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_contact_domains_method ON core.contact_domains USING btree (assigned_method);


--
-- Name: idx_contact_domains_org_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_contact_domains_org_id ON core.contact_domains USING btree (organization_id);


--
-- Name: idx_contact_domains_wa_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_contact_domains_wa_id ON core.contact_domains USING btree (wa_id);


--
-- Name: idx_conv_ctx_conversation_id; Type: INDEX; Schema: core; Owner: -
--

CREATE UNIQUE INDEX idx_conv_ctx_conversation_id ON core.conversation_contexts USING btree (conversation_id);


--
-- Name: idx_conv_ctx_last_activity; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_conv_ctx_last_activity ON core.conversation_contexts USING btree (last_activity_at);


--
-- Name: idx_conv_ctx_organization; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_conv_ctx_organization ON core.conversation_contexts USING btree (organization_id);


--
-- Name: idx_conv_ctx_user_phone_org; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_conv_ctx_user_phone_org ON core.conversation_contexts USING btree (user_phone, organization_id);


--
-- Name: idx_conv_msg_conversation_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_conv_msg_conversation_id ON core.conversation_messages USING btree (conversation_id);


--
-- Name: idx_conv_msg_created_at; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_conv_msg_created_at ON core.conversation_messages USING btree (created_at);


--
-- Name: idx_conv_msg_sender_type; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_conv_msg_sender_type ON core.conversation_messages USING btree (sender_type);


--
-- Name: idx_domain_configs_enabled; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_domain_configs_enabled ON core.domain_configs USING btree (enabled);


--
-- Name: idx_domain_configs_priority; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_domain_configs_priority ON core.domain_configs USING btree (priority);


--
-- Name: idx_domain_intents_domain; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_domain_intents_domain ON core.domain_intents USING btree (domain_key);


--
-- Name: idx_domain_intents_enabled; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_domain_intents_enabled ON core.domain_intents USING btree (organization_id, domain_key, is_enabled);


--
-- Name: idx_domain_intents_org; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_domain_intents_org ON core.domain_intents USING btree (organization_id);


--
-- Name: idx_domain_intents_org_domain; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_domain_intents_org_domain ON core.domain_intents USING btree (organization_id, domain_key);


--
-- Name: idx_flow_agent_configs_org; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_flow_agent_configs_org ON core.flow_agent_configs USING btree (organization_id);


--
-- Name: idx_flow_agent_configs_org_enabled; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_flow_agent_configs_org_enabled ON core.flow_agent_configs USING btree (organization_id, is_enabled);


--
-- Name: idx_intent_agent_mappings_enabled; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_intent_agent_mappings_enabled ON core.intent_agent_mappings USING btree (organization_id, is_enabled);


--
-- Name: idx_intent_agent_mappings_org; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_intent_agent_mappings_org ON core.intent_agent_mappings USING btree (organization_id);


--
-- Name: idx_intent_agent_mappings_org_domain; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_intent_agent_mappings_org_domain ON core.intent_agent_mappings USING btree (organization_id, domain_key);


--
-- Name: idx_keyword_agent_mappings_keyword; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_keyword_agent_mappings_keyword ON core.keyword_agent_mappings USING btree (organization_id, keyword);


--
-- Name: idx_keyword_agent_mappings_org; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_keyword_agent_mappings_org ON core.keyword_agent_mappings USING btree (organization_id);


--
-- Name: idx_keyword_agent_mappings_org_agent; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_keyword_agent_mappings_org_agent ON core.keyword_agent_mappings USING btree (organization_id, agent_key);


--
-- Name: idx_knowledge_category; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_knowledge_category ON core.company_knowledge USING btree (category);


--
-- Name: idx_knowledge_embedding_hnsw; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_knowledge_embedding_hnsw ON core.company_knowledge USING hnsw (embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64');


--
-- Name: idx_knowledge_search_vector; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_knowledge_search_vector ON core.company_knowledge USING gin (search_vector);


--
-- Name: idx_knowledge_tags; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_knowledge_tags ON core.company_knowledge USING gin (tags);


--
-- Name: idx_knowledge_type_active; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_knowledge_type_active ON core.company_knowledge USING btree (document_type, active);


--
-- Name: idx_org_users_org_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_org_users_org_id ON core.organization_users USING btree (organization_id);


--
-- Name: idx_org_users_role; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_org_users_role ON core.organization_users USING btree (role);


--
-- Name: idx_org_users_user_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_org_users_user_id ON core.organization_users USING btree (user_id);


--
-- Name: idx_organizations_created_at; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_organizations_created_at ON core.organizations USING btree (created_at);


--
-- Name: idx_organizations_mode; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_organizations_mode ON core.organizations USING btree (mode);


--
-- Name: idx_organizations_slug; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_organizations_slug ON core.organizations USING btree (slug);


--
-- Name: idx_organizations_status; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_organizations_status ON core.organizations USING btree (status);


--
-- Name: idx_rag_logs_agent_key; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_rag_logs_agent_key ON core.rag_query_logs USING btree (agent_key) WHERE (agent_key IS NOT NULL);


--
-- Name: idx_rag_logs_created_at; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_rag_logs_created_at ON core.rag_query_logs USING btree (created_at DESC);


--
-- Name: idx_rag_logs_feedback; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_rag_logs_feedback ON core.rag_query_logs USING btree (user_feedback) WHERE (user_feedback IS NOT NULL);


--
-- Name: idx_rag_logs_latency; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_rag_logs_latency ON core.rag_query_logs USING btree (latency_ms);


--
-- Name: idx_response_configs_domain; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_response_configs_domain ON core.response_configs USING btree (domain_key);


--
-- Name: idx_response_configs_enabled; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_response_configs_enabled ON core.response_configs USING btree (organization_id, is_enabled);


--
-- Name: idx_response_configs_org; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_response_configs_org ON core.response_configs USING btree (organization_id);


--
-- Name: idx_response_configs_org_domain; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_response_configs_org_domain ON core.response_configs USING btree (organization_id, domain_key);


--
-- Name: idx_routing_configs_lookup; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_routing_configs_lookup ON core.routing_configs USING btree (organization_id, domain_key, config_type, is_enabled);


--
-- Name: idx_routing_configs_priority; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_routing_configs_priority ON core.routing_configs USING btree (priority);


--
-- Name: idx_routing_configs_trigger; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_routing_configs_trigger ON core.routing_configs USING btree (trigger_value);


--
-- Name: idx_tenant_agents_agent_type; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_agents_agent_type ON core.tenant_agents USING btree (agent_type);


--
-- Name: idx_tenant_agents_domain_key; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_agents_domain_key ON core.tenant_agents USING btree (domain_key);


--
-- Name: idx_tenant_agents_enabled; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_agents_enabled ON core.tenant_agents USING btree (enabled);


--
-- Name: idx_tenant_agents_org_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_agents_org_id ON core.tenant_agents USING btree (organization_id);


--
-- Name: idx_tenant_configs_org_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_configs_org_id ON core.tenant_configs USING btree (organization_id);


--
-- Name: idx_tenant_credentials_org_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_credentials_org_id ON core.tenant_credentials USING btree (organization_id);


--
-- Name: idx_tenant_docs_category; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_docs_category ON core.tenant_documents USING btree (category);


--
-- Name: idx_tenant_docs_org_active; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_docs_org_active ON core.tenant_documents USING btree (organization_id, active);


--
-- Name: idx_tenant_docs_org_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_docs_org_id ON core.tenant_documents USING btree (organization_id);


--
-- Name: idx_tenant_docs_org_type; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_docs_org_type ON core.tenant_documents USING btree (organization_id, document_type);


--
-- Name: idx_tenant_docs_search_vector; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_docs_search_vector ON core.tenant_documents USING gin (search_vector);


--
-- Name: idx_tenant_docs_tags; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_docs_tags ON core.tenant_documents USING gin (tags);


--
-- Name: idx_tenant_institution_configs_key; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_institution_configs_key ON core.tenant_institution_configs USING btree (institution_key);


--
-- Name: idx_tenant_institution_configs_org; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_institution_configs_org ON core.tenant_institution_configs USING btree (organization_id);


--
-- Name: idx_tenant_institution_configs_settings_gin; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_institution_configs_settings_gin ON core.tenant_institution_configs USING gin (settings);


--
-- Name: idx_tenant_institution_configs_type; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_institution_configs_type ON core.tenant_institution_configs USING btree (institution_type);


--
-- Name: idx_tenant_institution_configs_wa_phone; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_institution_configs_wa_phone ON core.tenant_institution_configs USING btree ((((settings -> 'whatsapp'::text) ->> 'phone_number_id'::text)));


--
-- Name: idx_tenant_prompts_active; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_prompts_active ON core.tenant_prompts USING btree (is_active);


--
-- Name: idx_tenant_prompts_key; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_prompts_key ON core.tenant_prompts USING btree (prompt_key);


--
-- Name: idx_tenant_prompts_org_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_prompts_org_id ON core.tenant_prompts USING btree (organization_id);


--
-- Name: idx_tenant_prompts_org_key_scope; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_prompts_org_key_scope ON core.tenant_prompts USING btree (organization_id, prompt_key, scope);


--
-- Name: idx_tenant_prompts_scope; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_prompts_scope ON core.tenant_prompts USING btree (scope);


--
-- Name: idx_tenant_prompts_user_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tenant_prompts_user_id ON core.tenant_prompts USING btree (user_id);


--
-- Name: idx_users_created_at; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_users_created_at ON core.users USING btree (created_at);


--
-- Name: idx_users_disabled; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_users_disabled ON core.users USING btree (disabled);


--
-- Name: idx_users_email; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_users_email ON core.users USING btree (email);


--
-- Name: idx_users_username; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_users_username ON core.users USING btree (username);


--
-- Name: ix_conversation_contexts_pharmacy_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_conversation_contexts_pharmacy_id ON core.conversation_contexts USING btree (pharmacy_id);


--
-- Name: ix_core_company_knowledge_active; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_core_company_knowledge_active ON core.company_knowledge USING btree (active);


--
-- Name: ix_core_company_knowledge_category; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_core_company_knowledge_category ON core.company_knowledge USING btree (category);


--
-- Name: ix_core_company_knowledge_document_type; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_core_company_knowledge_document_type ON core.company_knowledge USING btree (document_type);


--
-- Name: ix_core_contact_domains_domain; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_core_contact_domains_domain ON core.contact_domains USING btree (domain);


--
-- Name: ix_core_contact_domains_wa_id; Type: INDEX; Schema: core; Owner: -
--

CREATE UNIQUE INDEX ix_core_contact_domains_wa_id ON core.contact_domains USING btree (wa_id);


--
-- Name: ix_core_domains_domain_key; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_core_domains_domain_key ON core.domains USING btree (domain_key);


--
-- Name: ix_core_domains_enabled; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_core_domains_enabled ON core.domains USING btree (enabled);


--
-- Name: ix_core_organization_users_organization_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_core_organization_users_organization_id ON core.organization_users USING btree (organization_id);


--
-- Name: ix_core_organization_users_user_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_core_organization_users_user_id ON core.organization_users USING btree (user_id);


--
-- Name: ix_core_organizations_slug; Type: INDEX; Schema: core; Owner: -
--

CREATE UNIQUE INDEX ix_core_organizations_slug ON core.organizations USING btree (slug);


--
-- Name: ix_core_organizations_status; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_core_organizations_status ON core.organizations USING btree (status);


--
-- Name: ix_core_tenant_agents_domain_key; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_core_tenant_agents_domain_key ON core.tenant_agents USING btree (domain_key);


--
-- Name: ix_core_tenant_agents_enabled; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_core_tenant_agents_enabled ON core.tenant_agents USING btree (enabled);


--
-- Name: ix_core_tenant_agents_organization_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_core_tenant_agents_organization_id ON core.tenant_agents USING btree (organization_id);


--
-- Name: ix_core_tenant_documents_active; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_core_tenant_documents_active ON core.tenant_documents USING btree (active);


--
-- Name: ix_core_tenant_documents_category; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_core_tenant_documents_category ON core.tenant_documents USING btree (category);


--
-- Name: ix_core_tenant_documents_document_type; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_core_tenant_documents_document_type ON core.tenant_documents USING btree (document_type);


--
-- Name: ix_core_tenant_documents_organization_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_core_tenant_documents_organization_id ON core.tenant_documents USING btree (organization_id);


--
-- Name: ix_core_tenant_prompts_is_active; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_core_tenant_prompts_is_active ON core.tenant_prompts USING btree (is_active);


--
-- Name: ix_core_tenant_prompts_organization_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_core_tenant_prompts_organization_id ON core.tenant_prompts USING btree (organization_id);


--
-- Name: ix_core_tenant_prompts_user_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_core_tenant_prompts_user_id ON core.tenant_prompts USING btree (user_id);


--
-- Name: ix_core_users_email; Type: INDEX; Schema: core; Owner: -
--

CREATE UNIQUE INDEX ix_core_users_email ON core.users USING btree (email);


--
-- Name: ix_core_users_username; Type: INDEX; Schema: core; Owner: -
--

CREATE UNIQUE INDEX ix_core_users_username ON core.users USING btree (username);


--
-- Name: ix_credit_credit_accounts_account_number; Type: INDEX; Schema: credit; Owner: -
--

CREATE UNIQUE INDEX ix_credit_credit_accounts_account_number ON credit.credit_accounts USING btree (account_number);


--
-- Name: ix_credit_credit_accounts_customer_id; Type: INDEX; Schema: credit; Owner: -
--

CREATE INDEX ix_credit_credit_accounts_customer_id ON credit.credit_accounts USING btree (customer_id);


--
-- Name: ix_credit_credit_accounts_id; Type: INDEX; Schema: credit; Owner: -
--

CREATE INDEX ix_credit_credit_accounts_id ON credit.credit_accounts USING btree (id);


--
-- Name: ix_credit_credit_accounts_status; Type: INDEX; Schema: credit; Owner: -
--

CREATE INDEX ix_credit_credit_accounts_status ON credit.credit_accounts USING btree (status);


--
-- Name: ix_credit_payment_schedule_items_account_id; Type: INDEX; Schema: credit; Owner: -
--

CREATE INDEX ix_credit_payment_schedule_items_account_id ON credit.payment_schedule_items USING btree (account_id);


--
-- Name: ix_credit_payment_schedule_items_due_date; Type: INDEX; Schema: credit; Owner: -
--

CREATE INDEX ix_credit_payment_schedule_items_due_date ON credit.payment_schedule_items USING btree (due_date);


--
-- Name: ix_credit_payment_schedule_items_id; Type: INDEX; Schema: credit; Owner: -
--

CREATE INDEX ix_credit_payment_schedule_items_id ON credit.payment_schedule_items USING btree (id);


--
-- Name: ix_credit_payments_account_id; Type: INDEX; Schema: credit; Owner: -
--

CREATE INDEX ix_credit_payments_account_id ON credit.payments USING btree (account_id);


--
-- Name: ix_credit_payments_id; Type: INDEX; Schema: credit; Owner: -
--

CREATE INDEX ix_credit_payments_id ON credit.payments USING btree (id);


--
-- Name: ix_credit_payments_reference_number; Type: INDEX; Schema: credit; Owner: -
--

CREATE UNIQUE INDEX ix_credit_payments_reference_number ON credit.payments USING btree (reference_number);


--
-- Name: ix_credit_payments_status; Type: INDEX; Schema: credit; Owner: -
--

CREATE INDEX ix_credit_payments_status ON credit.payments USING btree (status);


--
-- Name: idx_brands_active; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_brands_active ON ecommerce.brands USING btree (active);


--
-- Name: idx_brands_name_trgm; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_brands_name_trgm ON ecommerce.brands USING gin (name public.gin_trgm_ops);


--
-- Name: idx_categories_active; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_categories_active ON ecommerce.categories USING btree (active);


--
-- Name: idx_categories_sort; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_categories_sort ON ecommerce.categories USING btree (sort_order);


--
-- Name: idx_customers_active; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_customers_active ON ecommerce.customers USING btree (active);


--
-- Name: idx_customers_name; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_customers_name ON ecommerce.customers USING btree (first_name, last_name);


--
-- Name: idx_order_items_order; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_order_items_order ON ecommerce.order_items USING btree (order_id);


--
-- Name: idx_order_items_product; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_order_items_product ON ecommerce.order_items USING btree (product_id);


--
-- Name: idx_orders_customer; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_orders_customer ON ecommerce.orders USING btree (customer_id);


--
-- Name: idx_orders_customer_status_date; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_orders_customer_status_date ON ecommerce.orders USING btree (customer_id, status, order_date);


--
-- Name: idx_orders_date; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_orders_date ON ecommerce.orders USING btree (order_date);


--
-- Name: idx_orders_payment_status; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_orders_payment_status ON ecommerce.orders USING btree (payment_status);


--
-- Name: idx_orders_status; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_orders_status ON ecommerce.orders USING btree (status);


--
-- Name: idx_product_attributes_name; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_product_attributes_name ON ecommerce.product_attributes USING btree (name);


--
-- Name: idx_product_attributes_product; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_product_attributes_product ON ecommerce.product_attributes USING btree (product_id);


--
-- Name: idx_product_attributes_searchable; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_product_attributes_searchable ON ecommerce.product_attributes USING btree (is_searchable);


--
-- Name: idx_product_images_primary; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_product_images_primary ON ecommerce.product_images USING btree (is_primary);


--
-- Name: idx_product_images_product; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_product_images_product ON ecommerce.product_images USING btree (product_id);


--
-- Name: idx_product_images_sort; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_product_images_sort ON ecommerce.product_images USING btree (sort_order);


--
-- Name: idx_products_active; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_products_active ON ecommerce.products USING btree (active);


--
-- Name: idx_products_brand; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_products_brand ON ecommerce.products USING btree (brand_id);


--
-- Name: idx_products_category; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_products_category ON ecommerce.products USING btree (category_id);


--
-- Name: idx_products_description_trgm; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_products_description_trgm ON ecommerce.products USING gin (description public.gin_trgm_ops);


--
-- Name: idx_products_embedding_hnsw; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_products_embedding_hnsw ON ecommerce.products USING hnsw (embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64');


--
-- Name: idx_products_featured; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_products_featured ON ecommerce.products USING btree (featured);


--
-- Name: idx_products_name_trgm; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_products_name_trgm ON ecommerce.products USING gin (name public.gin_trgm_ops);


--
-- Name: idx_products_price; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_products_price ON ecommerce.products USING btree (price);


--
-- Name: idx_products_sale; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_products_sale ON ecommerce.products USING btree (on_sale);


--
-- Name: idx_products_search; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_products_search ON ecommerce.products USING gin (search_vector);


--
-- Name: idx_products_stock; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX idx_products_stock ON ecommerce.products USING btree (stock);


--
-- Name: ix_ecommerce_analytics_metric_name; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX ix_ecommerce_analytics_metric_name ON ecommerce.analytics USING btree (metric_name);


--
-- Name: ix_ecommerce_categories_external_id; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX ix_ecommerce_categories_external_id ON ecommerce.categories USING btree (external_id);


--
-- Name: ix_ecommerce_conversations_session_id; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX ix_ecommerce_conversations_session_id ON ecommerce.conversations USING btree (session_id);


--
-- Name: ix_ecommerce_customers_phone_number; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE UNIQUE INDEX ix_ecommerce_customers_phone_number ON ecommerce.customers USING btree (phone_number);


--
-- Name: ix_ecommerce_messages_user_phone; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX ix_ecommerce_messages_user_phone ON ecommerce.messages USING btree (user_phone);


--
-- Name: ix_ecommerce_messages_whatsapp_message_id; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE UNIQUE INDEX ix_ecommerce_messages_whatsapp_message_id ON ecommerce.messages USING btree (whatsapp_message_id);


--
-- Name: ix_ecommerce_orders_order_number; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE UNIQUE INDEX ix_ecommerce_orders_order_number ON ecommerce.orders USING btree (order_number);


--
-- Name: ix_ecommerce_products_active; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX ix_ecommerce_products_active ON ecommerce.products USING btree (active);


--
-- Name: ix_ecommerce_products_featured; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX ix_ecommerce_products_featured ON ecommerce.products USING btree (featured);


--
-- Name: ix_ecommerce_products_name; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX ix_ecommerce_products_name ON ecommerce.products USING btree (name);


--
-- Name: ix_ecommerce_products_on_sale; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX ix_ecommerce_products_on_sale ON ecommerce.products USING btree (on_sale);


--
-- Name: ix_ecommerce_products_price; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX ix_ecommerce_products_price ON ecommerce.products USING btree (price);


--
-- Name: ix_ecommerce_products_sku; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE UNIQUE INDEX ix_ecommerce_products_sku ON ecommerce.products USING btree (sku);


--
-- Name: ix_ecommerce_products_stock; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX ix_ecommerce_products_stock ON ecommerce.products USING btree (stock);


--
-- Name: ix_ecommerce_promotions_active; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE INDEX ix_ecommerce_promotions_active ON ecommerce.promotions USING btree (active);


--
-- Name: ix_ecommerce_promotions_promo_code; Type: INDEX; Schema: ecommerce; Owner: -
--

CREATE UNIQUE INDEX ix_ecommerce_promotions_promo_code ON ecommerce.promotions USING btree (promo_code);


--
-- Name: ix_healthcare_appointments_appointment_date; Type: INDEX; Schema: healthcare; Owner: -
--

CREATE INDEX ix_healthcare_appointments_appointment_date ON healthcare.appointments USING btree (appointment_date);


--
-- Name: ix_healthcare_appointments_doctor_id; Type: INDEX; Schema: healthcare; Owner: -
--

CREATE INDEX ix_healthcare_appointments_doctor_id ON healthcare.appointments USING btree (doctor_id);


--
-- Name: ix_healthcare_appointments_id; Type: INDEX; Schema: healthcare; Owner: -
--

CREATE INDEX ix_healthcare_appointments_id ON healthcare.appointments USING btree (id);


--
-- Name: ix_healthcare_appointments_patient_id; Type: INDEX; Schema: healthcare; Owner: -
--

CREATE INDEX ix_healthcare_appointments_patient_id ON healthcare.appointments USING btree (patient_id);


--
-- Name: ix_healthcare_appointments_status; Type: INDEX; Schema: healthcare; Owner: -
--

CREATE INDEX ix_healthcare_appointments_status ON healthcare.appointments USING btree (status);


--
-- Name: ix_healthcare_doctors_id; Type: INDEX; Schema: healthcare; Owner: -
--

CREATE INDEX ix_healthcare_doctors_id ON healthcare.doctors USING btree (id);


--
-- Name: ix_healthcare_doctors_license_number; Type: INDEX; Schema: healthcare; Owner: -
--

CREATE UNIQUE INDEX ix_healthcare_doctors_license_number ON healthcare.doctors USING btree (license_number);


--
-- Name: ix_healthcare_patients_id; Type: INDEX; Schema: healthcare; Owner: -
--

CREATE INDEX ix_healthcare_patients_id ON healthcare.patients USING btree (id);


--
-- Name: ix_healthcare_patients_medical_record_number; Type: INDEX; Schema: healthcare; Owner: -
--

CREATE UNIQUE INDEX ix_healthcare_patients_medical_record_number ON healthcare.patients USING btree (medical_record_number);


--
-- Name: ix_healthcare_patients_national_id; Type: INDEX; Schema: healthcare; Owner: -
--

CREATE UNIQUE INDEX ix_healthcare_patients_national_id ON healthcare.patients USING btree (national_id);


--
-- Name: ix_healthcare_patients_phone; Type: INDEX; Schema: healthcare; Owner: -
--

CREATE INDEX ix_healthcare_patients_phone ON healthcare.patients USING btree (phone);


--
-- Name: idx_pharmacy_merchant_configs_org; Type: INDEX; Schema: pharmacy; Owner: -
--

CREATE INDEX idx_pharmacy_merchant_configs_org ON pharmacy.pharmacy_merchant_configs USING btree (organization_id);


--
-- Name: idx_pharmacy_merchant_configs_whatsapp; Type: INDEX; Schema: pharmacy; Owner: -
--

CREATE INDEX idx_pharmacy_merchant_configs_whatsapp ON pharmacy.pharmacy_merchant_configs USING btree (whatsapp_phone_number) WHERE (whatsapp_phone_number IS NOT NULL);


--
-- Name: idx_registered_persons_active; Type: INDEX; Schema: pharmacy; Owner: -
--

CREATE INDEX idx_registered_persons_active ON pharmacy.registered_persons USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_registered_persons_dni_pharmacy; Type: INDEX; Schema: pharmacy; Owner: -
--

CREATE INDEX idx_registered_persons_dni_pharmacy ON pharmacy.registered_persons USING btree (dni, pharmacy_id);


--
-- Name: idx_registered_persons_expires; Type: INDEX; Schema: pharmacy; Owner: -
--

CREATE INDEX idx_registered_persons_expires ON pharmacy.registered_persons USING btree (expires_at) WHERE (is_active = true);


--
-- Name: idx_registered_persons_phone; Type: INDEX; Schema: pharmacy; Owner: -
--

CREATE INDEX idx_registered_persons_phone ON pharmacy.registered_persons USING btree (phone_number);


--
-- Name: idx_registered_persons_phone_pharmacy; Type: INDEX; Schema: pharmacy; Owner: -
--

CREATE INDEX idx_registered_persons_phone_pharmacy ON pharmacy.registered_persons USING btree (phone_number, pharmacy_id);


--
-- Name: idx_incident_category_active; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_incident_category_active ON soporte.incident_categories USING btree (is_active);


--
-- Name: idx_incident_category_code; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_incident_category_code ON soporte.incident_categories USING btree (code);


--
-- Name: idx_incident_category_parent; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_incident_category_parent ON soporte.incident_categories USING btree (parent_id);


--
-- Name: idx_incident_comments_author_type; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_incident_comments_author_type ON soporte.incident_comments USING btree (author_type);


--
-- Name: idx_incident_comments_created_at; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_incident_comments_created_at ON soporte.incident_comments USING btree (created_at);


--
-- Name: idx_incident_comments_incident_id; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_incident_comments_incident_id ON soporte.incident_comments USING btree (incident_id);


--
-- Name: idx_incident_history_changed_at; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_incident_history_changed_at ON soporte.incident_history USING btree (changed_at);


--
-- Name: idx_incident_history_field; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_incident_history_field ON soporte.incident_history USING btree (field_changed);


--
-- Name: idx_incident_history_incident_id; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_incident_history_incident_id ON soporte.incident_history USING btree (incident_id);


--
-- Name: idx_incidents_category_id; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_incidents_category_id ON soporte.incidents USING btree (category_id);


--
-- Name: idx_incidents_created_at; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_incidents_created_at ON soporte.incidents USING btree (created_at);


--
-- Name: idx_incidents_folio; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_incidents_folio ON soporte.incidents USING btree (folio);


--
-- Name: idx_incidents_jira_issue_key; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_incidents_jira_issue_key ON soporte.incidents USING btree (jira_issue_key);


--
-- Name: idx_incidents_organization_id; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_incidents_organization_id ON soporte.incidents USING btree (organization_id);


--
-- Name: idx_incidents_priority; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_incidents_priority ON soporte.incidents USING btree (priority);


--
-- Name: idx_incidents_status; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_incidents_status ON soporte.incidents USING btree (status);


--
-- Name: idx_incidents_user_phone; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_incidents_user_phone ON soporte.incidents USING btree (user_phone);


--
-- Name: idx_jira_configs_active; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_jira_configs_active ON soporte.jira_configs USING btree (is_active);


--
-- Name: idx_jira_configs_organization_id; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_jira_configs_organization_id ON soporte.jira_configs USING btree (organization_id);


--
-- Name: idx_jira_configs_project_key; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_jira_configs_project_key ON soporte.jira_configs USING btree (jira_project_key);


--
-- Name: idx_pending_tickets_active; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_pending_tickets_active ON soporte.pending_tickets USING btree (is_active);


--
-- Name: idx_pending_tickets_conversation_id; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_pending_tickets_conversation_id ON soporte.pending_tickets USING btree (conversation_id);


--
-- Name: idx_pending_tickets_expires; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_pending_tickets_expires ON soporte.pending_tickets USING btree (expires_at) WHERE (is_active = true);


--
-- Name: idx_pending_tickets_user_phone; Type: INDEX; Schema: soporte; Owner: -
--

CREATE INDEX idx_pending_tickets_user_phone ON soporte.pending_tickets USING btree (user_phone);


--
-- Name: agent_knowledge agent_knowledge_search_vector_update; Type: TRIGGER; Schema: core; Owner: -
--

CREATE TRIGGER agent_knowledge_search_vector_update BEFORE INSERT OR UPDATE ON core.agent_knowledge FOR EACH ROW EXECUTE FUNCTION core.agent_knowledge_search_vector_trigger();


--
-- Name: agent_knowledge agent_knowledge_updated_at_update; Type: TRIGGER; Schema: core; Owner: -
--

CREATE TRIGGER agent_knowledge_updated_at_update BEFORE UPDATE ON core.agent_knowledge FOR EACH ROW EXECUTE FUNCTION core.agent_knowledge_updated_at_trigger();


--
-- Name: rag_query_logs trigger_update_rag_query_logs_updated_at; Type: TRIGGER; Schema: core; Owner: -
--

CREATE TRIGGER trigger_update_rag_query_logs_updated_at BEFORE UPDATE ON core.rag_query_logs FOR EACH ROW EXECUTE FUNCTION core.update_rag_query_logs_updated_at();


--
-- Name: incidents trigger_calculate_sla_deadlines; Type: TRIGGER; Schema: soporte; Owner: -
--

CREATE TRIGGER trigger_calculate_sla_deadlines BEFORE INSERT ON soporte.incidents FOR EACH ROW EXECUTE FUNCTION soporte.calculate_sla_deadlines();


--
-- Name: incidents trigger_generate_incident_folio; Type: TRIGGER; Schema: soporte; Owner: -
--

CREATE TRIGGER trigger_generate_incident_folio BEFORE INSERT ON soporte.incidents FOR EACH ROW WHEN (((new.folio IS NULL) OR ((new.folio)::text = ''::text))) EXECUTE FUNCTION soporte.generate_incident_folio();


--
-- Name: incident_categories trigger_incident_categories_updated_at; Type: TRIGGER; Schema: soporte; Owner: -
--

CREATE TRIGGER trigger_incident_categories_updated_at BEFORE UPDATE ON soporte.incident_categories FOR EACH ROW EXECUTE FUNCTION soporte.update_updated_at_column();


--
-- Name: incident_comments trigger_incident_comments_updated_at; Type: TRIGGER; Schema: soporte; Owner: -
--

CREATE TRIGGER trigger_incident_comments_updated_at BEFORE UPDATE ON soporte.incident_comments FOR EACH ROW EXECUTE FUNCTION soporte.update_updated_at_column();


--
-- Name: incidents trigger_incidents_updated_at; Type: TRIGGER; Schema: soporte; Owner: -
--

CREATE TRIGGER trigger_incidents_updated_at BEFORE UPDATE ON soporte.incidents FOR EACH ROW EXECUTE FUNCTION soporte.update_updated_at_column();


--
-- Name: jira_configs trigger_jira_configs_updated_at; Type: TRIGGER; Schema: soporte; Owner: -
--

CREATE TRIGGER trigger_jira_configs_updated_at BEFORE UPDATE ON soporte.jira_configs FOR EACH ROW EXECUTE FUNCTION soporte.update_updated_at_column();


--
-- Name: awaiting_type_configs awaiting_type_configs_organization_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.awaiting_type_configs
    ADD CONSTRAINT awaiting_type_configs_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES core.organizations(id) ON DELETE CASCADE;


--
-- Name: bypass_rules bypass_rules_organization_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.bypass_rules
    ADD CONSTRAINT bypass_rules_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES core.organizations(id) ON DELETE CASCADE;


--
-- Name: bypass_rules bypass_rules_pharmacy_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.bypass_rules
    ADD CONSTRAINT bypass_rules_pharmacy_id_fkey FOREIGN KEY (pharmacy_id) REFERENCES pharmacy.pharmacy_merchant_configs(id) ON DELETE SET NULL;


--
-- Name: chattigo_credentials chattigo_credentials_bypass_rule_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.chattigo_credentials
    ADD CONSTRAINT chattigo_credentials_bypass_rule_id_fkey FOREIGN KEY (bypass_rule_id) REFERENCES core.bypass_rules(id) ON DELETE SET NULL;


--
-- Name: chattigo_credentials chattigo_credentials_organization_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.chattigo_credentials
    ADD CONSTRAINT chattigo_credentials_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES core.organizations(id) ON DELETE CASCADE;


--
-- Name: conversation_messages conversation_messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.conversation_messages
    ADD CONSTRAINT conversation_messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES core.conversation_contexts(conversation_id) ON DELETE CASCADE;


--
-- Name: domain_intents domain_intents_organization_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.domain_intents
    ADD CONSTRAINT domain_intents_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES core.organizations(id) ON DELETE CASCADE;


--
-- Name: bypass_rules fk_bypass_rules_pharmacy; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.bypass_rules
    ADD CONSTRAINT fk_bypass_rules_pharmacy FOREIGN KEY (pharmacy_id) REFERENCES pharmacy.pharmacy_merchant_configs(id) ON DELETE SET NULL;


--
-- Name: flow_agent_configs fk_flow_agent_configs_org; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.flow_agent_configs
    ADD CONSTRAINT fk_flow_agent_configs_org FOREIGN KEY (organization_id) REFERENCES core.organizations(id) ON DELETE CASCADE;


--
-- Name: intent_agent_mappings fk_intent_agent_mappings_org; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.intent_agent_mappings
    ADD CONSTRAINT fk_intent_agent_mappings_org FOREIGN KEY (organization_id) REFERENCES core.organizations(id) ON DELETE CASCADE;


--
-- Name: keyword_agent_mappings fk_keyword_agent_mappings_org; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.keyword_agent_mappings
    ADD CONSTRAINT fk_keyword_agent_mappings_org FOREIGN KEY (organization_id) REFERENCES core.organizations(id) ON DELETE CASCADE;


--
-- Name: organization_users organization_users_organization_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.organization_users
    ADD CONSTRAINT organization_users_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES core.organizations(id) ON DELETE CASCADE;


--
-- Name: organization_users organization_users_user_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.organization_users
    ADD CONSTRAINT organization_users_user_id_fkey FOREIGN KEY (user_id) REFERENCES core.users(id) ON DELETE CASCADE;


--
-- Name: response_configs pharmacy_response_configs_organization_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.response_configs
    ADD CONSTRAINT pharmacy_response_configs_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES core.organizations(id) ON DELETE CASCADE;


--
-- Name: routing_configs routing_configs_organization_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.routing_configs
    ADD CONSTRAINT routing_configs_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES core.organizations(id) ON DELETE CASCADE;


--
-- Name: tenant_agents tenant_agents_organization_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tenant_agents
    ADD CONSTRAINT tenant_agents_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES core.organizations(id) ON DELETE CASCADE;


--
-- Name: tenant_configs tenant_configs_organization_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tenant_configs
    ADD CONSTRAINT tenant_configs_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES core.organizations(id) ON DELETE CASCADE;


--
-- Name: tenant_credentials tenant_credentials_organization_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tenant_credentials
    ADD CONSTRAINT tenant_credentials_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES core.organizations(id) ON DELETE CASCADE;


--
-- Name: tenant_documents tenant_documents_organization_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tenant_documents
    ADD CONSTRAINT tenant_documents_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES core.organizations(id) ON DELETE CASCADE;


--
-- Name: tenant_institution_configs tenant_institution_configs_organization_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tenant_institution_configs
    ADD CONSTRAINT tenant_institution_configs_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES core.organizations(id) ON DELETE CASCADE;


--
-- Name: tenant_prompts tenant_prompts_organization_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tenant_prompts
    ADD CONSTRAINT tenant_prompts_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES core.organizations(id) ON DELETE CASCADE;


--
-- Name: tenant_prompts tenant_prompts_user_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tenant_prompts
    ADD CONSTRAINT tenant_prompts_user_id_fkey FOREIGN KEY (user_id) REFERENCES core.users(id) ON DELETE CASCADE;


--
-- Name: payment_schedule_items payment_schedule_items_account_id_fkey; Type: FK CONSTRAINT; Schema: credit; Owner: -
--

ALTER TABLE ONLY credit.payment_schedule_items
    ADD CONSTRAINT payment_schedule_items_account_id_fkey FOREIGN KEY (account_id) REFERENCES credit.credit_accounts(id);


--
-- Name: payments payments_account_id_fkey; Type: FK CONSTRAINT; Schema: credit; Owner: -
--

ALTER TABLE ONLY credit.payments
    ADD CONSTRAINT payments_account_id_fkey FOREIGN KEY (account_id) REFERENCES credit.credit_accounts(id);


--
-- Name: conversations conversations_customer_id_fkey; Type: FK CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.conversations
    ADD CONSTRAINT conversations_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES ecommerce.customers(id);


--
-- Name: messages messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.messages
    ADD CONSTRAINT messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES ecommerce.conversations(id);


--
-- Name: order_items order_items_order_id_fkey; Type: FK CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.order_items
    ADD CONSTRAINT order_items_order_id_fkey FOREIGN KEY (order_id) REFERENCES ecommerce.orders(id);


--
-- Name: order_items order_items_product_id_fkey; Type: FK CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.order_items
    ADD CONSTRAINT order_items_product_id_fkey FOREIGN KEY (product_id) REFERENCES ecommerce.products(id);


--
-- Name: orders orders_customer_id_fkey; Type: FK CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.orders
    ADD CONSTRAINT orders_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES ecommerce.customers(id);


--
-- Name: price_history price_history_product_id_fkey; Type: FK CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.price_history
    ADD CONSTRAINT price_history_product_id_fkey FOREIGN KEY (product_id) REFERENCES ecommerce.products(id);


--
-- Name: product_attributes product_attributes_product_id_fkey; Type: FK CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.product_attributes
    ADD CONSTRAINT product_attributes_product_id_fkey FOREIGN KEY (product_id) REFERENCES ecommerce.products(id);


--
-- Name: product_images product_images_product_id_fkey; Type: FK CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.product_images
    ADD CONSTRAINT product_images_product_id_fkey FOREIGN KEY (product_id) REFERENCES ecommerce.products(id);


--
-- Name: product_inquiries product_inquiries_category_id_fkey; Type: FK CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.product_inquiries
    ADD CONSTRAINT product_inquiries_category_id_fkey FOREIGN KEY (category_id) REFERENCES ecommerce.categories(id);


--
-- Name: product_inquiries product_inquiries_customer_id_fkey; Type: FK CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.product_inquiries
    ADD CONSTRAINT product_inquiries_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES ecommerce.customers(id);


--
-- Name: product_inquiries product_inquiries_product_id_fkey; Type: FK CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.product_inquiries
    ADD CONSTRAINT product_inquiries_product_id_fkey FOREIGN KEY (product_id) REFERENCES ecommerce.products(id);


--
-- Name: product_promotions product_promotions_product_id_fkey; Type: FK CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.product_promotions
    ADD CONSTRAINT product_promotions_product_id_fkey FOREIGN KEY (product_id) REFERENCES ecommerce.products(id);


--
-- Name: product_promotions product_promotions_promotion_id_fkey; Type: FK CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.product_promotions
    ADD CONSTRAINT product_promotions_promotion_id_fkey FOREIGN KEY (promotion_id) REFERENCES ecommerce.promotions(id);


--
-- Name: product_reviews product_reviews_customer_id_fkey; Type: FK CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.product_reviews
    ADD CONSTRAINT product_reviews_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES ecommerce.customers(id);


--
-- Name: product_reviews product_reviews_product_id_fkey; Type: FK CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.product_reviews
    ADD CONSTRAINT product_reviews_product_id_fkey FOREIGN KEY (product_id) REFERENCES ecommerce.products(id);


--
-- Name: products products_brand_id_fkey; Type: FK CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.products
    ADD CONSTRAINT products_brand_id_fkey FOREIGN KEY (brand_id) REFERENCES ecommerce.brands(id);


--
-- Name: products products_category_id_fkey; Type: FK CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.products
    ADD CONSTRAINT products_category_id_fkey FOREIGN KEY (category_id) REFERENCES ecommerce.categories(id);


--
-- Name: products products_subcategory_id_fkey; Type: FK CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.products
    ADD CONSTRAINT products_subcategory_id_fkey FOREIGN KEY (subcategory_id) REFERENCES ecommerce.subcategories(id);


--
-- Name: stock_movements stock_movements_product_id_fkey; Type: FK CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.stock_movements
    ADD CONSTRAINT stock_movements_product_id_fkey FOREIGN KEY (product_id) REFERENCES ecommerce.products(id);


--
-- Name: subcategories subcategories_category_id_fkey; Type: FK CONSTRAINT; Schema: ecommerce; Owner: -
--

ALTER TABLE ONLY ecommerce.subcategories
    ADD CONSTRAINT subcategories_category_id_fkey FOREIGN KEY (category_id) REFERENCES ecommerce.categories(id);


--
-- Name: appointments appointments_doctor_id_fkey; Type: FK CONSTRAINT; Schema: healthcare; Owner: -
--

ALTER TABLE ONLY healthcare.appointments
    ADD CONSTRAINT appointments_doctor_id_fkey FOREIGN KEY (doctor_id) REFERENCES healthcare.doctors(id);


--
-- Name: appointments appointments_patient_id_fkey; Type: FK CONSTRAINT; Schema: healthcare; Owner: -
--

ALTER TABLE ONLY healthcare.appointments
    ADD CONSTRAINT appointments_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES healthcare.patients(id);


--
-- Name: pharmacy_merchant_configs pharmacy_merchant_configs_organization_id_fkey; Type: FK CONSTRAINT; Schema: pharmacy; Owner: -
--

ALTER TABLE ONLY pharmacy.pharmacy_merchant_configs
    ADD CONSTRAINT pharmacy_merchant_configs_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES core.organizations(id) ON DELETE CASCADE;


--
-- Name: registered_persons registered_persons_pharmacy_id_fkey; Type: FK CONSTRAINT; Schema: pharmacy; Owner: -
--

ALTER TABLE ONLY pharmacy.registered_persons
    ADD CONSTRAINT registered_persons_pharmacy_id_fkey FOREIGN KEY (pharmacy_id) REFERENCES pharmacy.pharmacy_merchant_configs(id) ON DELETE CASCADE;


--
-- Name: incident_categories incident_categories_parent_id_fkey; Type: FK CONSTRAINT; Schema: soporte; Owner: -
--

ALTER TABLE ONLY soporte.incident_categories
    ADD CONSTRAINT incident_categories_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES soporte.incident_categories(id) ON DELETE SET NULL;


--
-- Name: incident_comments incident_comments_incident_id_fkey; Type: FK CONSTRAINT; Schema: soporte; Owner: -
--

ALTER TABLE ONLY soporte.incident_comments
    ADD CONSTRAINT incident_comments_incident_id_fkey FOREIGN KEY (incident_id) REFERENCES soporte.incidents(id) ON DELETE CASCADE;


--
-- Name: incident_history incident_history_incident_id_fkey; Type: FK CONSTRAINT; Schema: soporte; Owner: -
--

ALTER TABLE ONLY soporte.incident_history
    ADD CONSTRAINT incident_history_incident_id_fkey FOREIGN KEY (incident_id) REFERENCES soporte.incidents(id) ON DELETE CASCADE;


--
-- Name: incidents incidents_category_id_fkey; Type: FK CONSTRAINT; Schema: soporte; Owner: -
--

ALTER TABLE ONLY soporte.incidents
    ADD CONSTRAINT incidents_category_id_fkey FOREIGN KEY (category_id) REFERENCES soporte.incident_categories(id) ON DELETE SET NULL;


--
-- Name: incidents incidents_organization_id_fkey; Type: FK CONSTRAINT; Schema: soporte; Owner: -
--

ALTER TABLE ONLY soporte.incidents
    ADD CONSTRAINT incidents_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES core.organizations(id) ON DELETE CASCADE;


--
-- Name: jira_configs jira_configs_organization_id_fkey; Type: FK CONSTRAINT; Schema: soporte; Owner: -
--

ALTER TABLE ONLY soporte.jira_configs
    ADD CONSTRAINT jira_configs_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES core.organizations(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict gflMi0N2lGHJKsNAjdS9HdjmtZrH90ezD93aabqOQYTrW5KCKdOPnsRs9zXGcnw

