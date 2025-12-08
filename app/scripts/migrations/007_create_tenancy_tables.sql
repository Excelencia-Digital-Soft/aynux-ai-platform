-- Migration: Create multi-tenancy tables
-- Date: 2025-12-02
-- Author: Aynux System
-- Description: Tablas para soporte multi-tenant del sistema de bot
-- Schema: core (multi-tenant isolation)

-- =====================================================
-- 0. Crear esquema core si no existe
-- =====================================================
CREATE SCHEMA IF NOT EXISTS core;

-- =====================================================
-- 1. Tabla organizations (entidad principal de tenant)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    display_name VARCHAR(255),
    mode VARCHAR(20) NOT NULL DEFAULT 'multi_tenant',
    llm_model VARCHAR(100) NOT NULL DEFAULT 'llama3.2:1b',
    llm_temperature FLOAT NOT NULL DEFAULT 0.7,
    llm_max_tokens INTEGER NOT NULL DEFAULT 2048,
    features JSONB NOT NULL DEFAULT '{}',
    max_users INTEGER NOT NULL DEFAULT 10,
    max_documents INTEGER NOT NULL DEFAULT 1000,
    max_agents INTEGER NOT NULL DEFAULT 20,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    trial_ends_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indices para organizations
CREATE INDEX IF NOT EXISTS idx_organizations_slug ON core.organizations(slug);
CREATE INDEX IF NOT EXISTS idx_organizations_status ON core.organizations(status);
CREATE INDEX IF NOT EXISTS idx_organizations_mode ON core.organizations(mode);
CREATE INDEX IF NOT EXISTS idx_organizations_created_at ON core.organizations(created_at);

-- Comentarios
COMMENT ON TABLE core.organizations IS 'Organizaciones/tenants del sistema multi-tenant';
COMMENT ON COLUMN core.organizations.id IS 'UUID unico de la organizacion';
COMMENT ON COLUMN core.organizations.slug IS 'Identificador URL-friendly unico (ej: acme-corp)';
COMMENT ON COLUMN core.organizations.mode IS 'Modo de operacion: generic o multi_tenant';
COMMENT ON COLUMN core.organizations.llm_model IS 'Modelo LLM por defecto para este tenant';
COMMENT ON COLUMN core.organizations.llm_temperature IS 'Temperature para LLM (0.0-1.0)';
COMMENT ON COLUMN core.organizations.llm_max_tokens IS 'Max tokens para respuestas LLM';
COMMENT ON COLUMN core.organizations.features IS 'Feature flags en formato JSON';
COMMENT ON COLUMN core.organizations.status IS 'Estado: active, suspended, trial';

-- =====================================================
-- 2. Tabla organization_users (membresía de usuarios)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.organization_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL DEFAULT 'member',
    personal_settings JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_org_user UNIQUE (organization_id, user_id)
);

-- Indices para organization_users
CREATE INDEX IF NOT EXISTS idx_org_users_org_id ON core.organization_users(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_users_user_id ON core.organization_users(user_id);
CREATE INDEX IF NOT EXISTS idx_org_users_role ON core.organization_users(role);

-- Comentarios
COMMENT ON TABLE core.organization_users IS 'Membresia de usuarios en organizaciones';
COMMENT ON COLUMN core.organization_users.role IS 'Rol del usuario: owner, admin, member';
COMMENT ON COLUMN core.organization_users.personal_settings IS 'Configuraciones personales del usuario';

-- =====================================================
-- 3. Tabla tenant_configs (configuración por tenant)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.tenant_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID UNIQUE NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    enabled_domains TEXT[] NOT NULL DEFAULT ARRAY['excelencia'],
    default_domain VARCHAR(50) NOT NULL DEFAULT 'excelencia',
    enabled_agent_types TEXT[] NOT NULL DEFAULT '{}',
    agent_timeout_seconds INTEGER NOT NULL DEFAULT 30,
    rag_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    rag_similarity_threshold FLOAT NOT NULL DEFAULT 0.7,
    rag_max_results INTEGER NOT NULL DEFAULT 5,
    prompt_scope VARCHAR(20) NOT NULL DEFAULT 'org',
    whatsapp_phone_number_id VARCHAR(50),
    whatsapp_verify_token VARCHAR(255),
    advanced_config JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indices para tenant_configs
CREATE INDEX IF NOT EXISTS idx_tenant_configs_org_id ON core.tenant_configs(organization_id);

-- Comentarios
COMMENT ON TABLE core.tenant_configs IS 'Configuracion detallada por tenant';
COMMENT ON COLUMN core.tenant_configs.enabled_domains IS 'Lista de dominios habilitados (ecommerce, healthcare, etc)';
COMMENT ON COLUMN core.tenant_configs.enabled_agent_types IS 'Lista de agentes habilitados (vacio = todos)';
COMMENT ON COLUMN core.tenant_configs.rag_enabled IS 'Si RAG esta habilitado para este tenant';
COMMENT ON COLUMN core.tenant_configs.rag_similarity_threshold IS 'Umbral de similitud para RAG (0.0-1.0)';
COMMENT ON COLUMN core.tenant_configs.prompt_scope IS 'Alcance de prompts: system, global, org';

-- =====================================================
-- 4. Tabla tenant_documents (documentos con embeddings)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.tenant_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    document_type VARCHAR(100) NOT NULL,
    category VARCHAR(200),
    tags TEXT[] NOT NULL DEFAULT '{}',
    meta_data JSONB NOT NULL DEFAULT '{}',
    embedding vector(768),
    search_vector TSVECTOR,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indices para tenant_documents
CREATE INDEX IF NOT EXISTS idx_tenant_docs_org_id ON core.tenant_documents(organization_id);
CREATE INDEX IF NOT EXISTS idx_tenant_docs_org_active ON core.tenant_documents(organization_id, active);
CREATE INDEX IF NOT EXISTS idx_tenant_docs_org_type ON core.tenant_documents(organization_id, document_type);
CREATE INDEX IF NOT EXISTS idx_tenant_docs_category ON core.tenant_documents(category);
CREATE INDEX IF NOT EXISTS idx_tenant_docs_search_vector ON core.tenant_documents USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_tenant_docs_tags ON core.tenant_documents USING GIN(tags);

-- Indice HNSW para búsqueda vectorial (requiere pgvector)
CREATE INDEX IF NOT EXISTS idx_tenant_docs_embedding ON core.tenant_documents
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Comentarios
COMMENT ON TABLE core.tenant_documents IS 'Documentos del knowledge base por tenant con embeddings';
COMMENT ON COLUMN core.tenant_documents.embedding IS 'Vector embedding de 768 dimensiones (nomic-embed-text)';
COMMENT ON COLUMN core.tenant_documents.search_vector IS 'Vector de busqueda full-text (auto-generado)';
COMMENT ON COLUMN core.tenant_documents.document_type IS 'Tipo: faq, guide, policy, product_info, uploaded_pdf, etc';

-- Trigger para actualizar search_vector automáticamente
CREATE OR REPLACE FUNCTION core.update_tenant_document_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('spanish', COALESCE(NEW.title, '') || ' ' || COALESCE(NEW.content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_tenant_docs_search_vector
    BEFORE INSERT OR UPDATE OF title, content ON core.tenant_documents
    FOR EACH ROW
    EXECUTE FUNCTION core.update_tenant_document_search_vector();

-- =====================================================
-- 5. Tabla tenant_prompts (overrides de prompts)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.tenant_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    prompt_key VARCHAR(255) NOT NULL,
    scope VARCHAR(20) NOT NULL DEFAULT 'org',
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    template TEXT NOT NULL,
    description TEXT,
    version VARCHAR(50) NOT NULL DEFAULT '1.0.0',
    meta_data JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_org_prompt_key_scope_user UNIQUE (organization_id, prompt_key, scope, user_id)
);

-- Indices para tenant_prompts
CREATE INDEX IF NOT EXISTS idx_tenant_prompts_org_id ON core.tenant_prompts(organization_id);
CREATE INDEX IF NOT EXISTS idx_tenant_prompts_key ON core.tenant_prompts(prompt_key);
CREATE INDEX IF NOT EXISTS idx_tenant_prompts_scope ON core.tenant_prompts(scope);
CREATE INDEX IF NOT EXISTS idx_tenant_prompts_user_id ON core.tenant_prompts(user_id);
CREATE INDEX IF NOT EXISTS idx_tenant_prompts_active ON core.tenant_prompts(is_active);
CREATE INDEX IF NOT EXISTS idx_tenant_prompts_org_key_scope ON core.tenant_prompts(organization_id, prompt_key, scope);

-- Comentarios
COMMENT ON TABLE core.tenant_prompts IS 'Overrides de prompts por tenant/usuario';
COMMENT ON COLUMN core.tenant_prompts.prompt_key IS 'Key del prompt (ej: product.search.intent)';
COMMENT ON COLUMN core.tenant_prompts.scope IS 'Alcance: org (organizacion) o user (usuario)';
COMMENT ON COLUMN core.tenant_prompts.template IS 'Template del prompt con {variables}';

-- =====================================================
-- 6. Tabla tenant_agents (configuración de agentes)
-- =====================================================
CREATE TABLE IF NOT EXISTS core.tenant_agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    agent_key VARCHAR(100) NOT NULL,
    agent_type VARCHAR(50) NOT NULL DEFAULT 'specialized',
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    agent_class VARCHAR(255),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    priority INTEGER NOT NULL DEFAULT 0,
    domain_key VARCHAR(50),
    keywords TEXT[] NOT NULL DEFAULT '{}',
    intent_patterns JSONB NOT NULL DEFAULT '[]',
    config JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_org_agent_key UNIQUE (organization_id, agent_key)
);

-- Indices para tenant_agents
CREATE INDEX IF NOT EXISTS idx_tenant_agents_org_id ON core.tenant_agents(organization_id);
CREATE INDEX IF NOT EXISTS idx_tenant_agents_enabled ON core.tenant_agents(enabled);
CREATE INDEX IF NOT EXISTS idx_tenant_agents_domain_key ON core.tenant_agents(domain_key);
CREATE INDEX IF NOT EXISTS idx_tenant_agents_agent_type ON core.tenant_agents(agent_type);

-- Comentarios
COMMENT ON TABLE core.tenant_agents IS 'Configuracion de agentes por tenant';
COMMENT ON COLUMN core.tenant_agents.agent_key IS 'Key unico del agente (ej: product_agent)';
COMMENT ON COLUMN core.tenant_agents.agent_type IS 'Tipo: domain, specialized, custom';
COMMENT ON COLUMN core.tenant_agents.agent_class IS 'Clase Python para agentes custom (ej: app.custom.MyAgent)';
COMMENT ON COLUMN core.tenant_agents.priority IS 'Prioridad para routing (mayor = preferido)';
COMMENT ON COLUMN core.tenant_agents.keywords IS 'Keywords que activan este agente';
COMMENT ON COLUMN core.tenant_agents.intent_patterns IS 'Patrones para matching de intent';

-- =====================================================
-- 7. Triggers para updated_at en todas las tablas
-- =====================================================
CREATE OR REPLACE FUNCTION core.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para organizations
CREATE TRIGGER update_organizations_updated_at
    BEFORE UPDATE ON core.organizations
    FOR EACH ROW
    EXECUTE FUNCTION core.update_updated_at_column();

-- Trigger para organization_users
CREATE TRIGGER update_org_users_updated_at
    BEFORE UPDATE ON core.organization_users
    FOR EACH ROW
    EXECUTE FUNCTION core.update_updated_at_column();

-- Trigger para tenant_configs
CREATE TRIGGER update_tenant_configs_updated_at
    BEFORE UPDATE ON core.tenant_configs
    FOR EACH ROW
    EXECUTE FUNCTION core.update_updated_at_column();

-- Trigger para tenant_documents
CREATE TRIGGER update_tenant_docs_updated_at
    BEFORE UPDATE ON core.tenant_documents
    FOR EACH ROW
    EXECUTE FUNCTION core.update_updated_at_column();

-- Trigger para tenant_prompts
CREATE TRIGGER update_tenant_prompts_updated_at
    BEFORE UPDATE ON core.tenant_prompts
    FOR EACH ROW
    EXECUTE FUNCTION core.update_updated_at_column();

-- Trigger para tenant_agents
CREATE TRIGGER update_tenant_agents_updated_at
    BEFORE UPDATE ON core.tenant_agents
    FOR EACH ROW
    EXECUTE FUNCTION core.update_updated_at_column();

-- =====================================================
-- 8. Verificación de creación
-- =====================================================
DO $$
BEGIN
    RAISE NOTICE 'Multi-tenancy tables created successfully in core schema:';
    RAISE NOTICE '  - core.organizations';
    RAISE NOTICE '  - core.organization_users';
    RAISE NOTICE '  - core.tenant_configs';
    RAISE NOTICE '  - core.tenant_documents (with vector embedding)';
    RAISE NOTICE '  - core.tenant_prompts';
    RAISE NOTICE '  - core.tenant_agents';
END $$;
