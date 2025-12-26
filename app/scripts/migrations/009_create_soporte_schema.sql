-- ============================================================================
-- Migration: 009_create_soporte_schema.sql
-- Description: Creates the soporte schema for incident management with
--              Jira integration support and conversational flow state.
-- Date: 2024-12-24
-- ============================================================================

-- Create the soporte schema
CREATE SCHEMA IF NOT EXISTS soporte;

-- ============================================================================
-- ENUM TYPES (in soporte schema)
-- ============================================================================

-- Incident type
CREATE TYPE soporte.soporte_incident_type_enum AS ENUM (
    'incident', 'feedback', 'question', 'suggestion'
);

-- Incident status
CREATE TYPE soporte.soporte_incident_status_enum AS ENUM (
    'draft', 'open', 'in_progress', 'pending_info', 'resolved', 'closed'
);

-- Incident priority
CREATE TYPE soporte.soporte_incident_priority_enum AS ENUM (
    'low', 'medium', 'high', 'critical'
);

-- Incident urgency
CREATE TYPE soporte.soporte_incident_urgency_enum AS ENUM (
    'low', 'medium', 'high'
);

-- Incident impact
CREATE TYPE soporte.soporte_incident_impact_enum AS ENUM (
    'individual', 'group', 'department', 'organization'
);

-- Incident source
CREATE TYPE soporte.soporte_incident_source_enum AS ENUM (
    'whatsapp', 'email', 'phone', 'web'
);

-- Jira sync status
CREATE TYPE soporte.soporte_jira_sync_status_enum AS ENUM (
    'pending', 'synced', 'error', 'manual'
);

-- Comment author type
CREATE TYPE soporte.soporte_comment_author_type_enum AS ENUM (
    'user', 'agent', 'system'
);

-- ============================================================================
-- TABLE: incident_categories
-- ============================================================================

CREATE TABLE soporte.incident_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    parent_id UUID REFERENCES soporte.incident_categories(id) ON DELETE SET NULL,
    sla_response_hours INTEGER DEFAULT 24,
    sla_resolution_hours INTEGER DEFAULT 72,
    jira_issue_type VARCHAR(50) DEFAULT 'Bug',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for incident_categories
CREATE INDEX idx_incident_category_code ON soporte.incident_categories(code);
CREATE INDEX idx_incident_category_active ON soporte.incident_categories(is_active);
CREATE INDEX idx_incident_category_parent ON soporte.incident_categories(parent_id);

-- Seed initial categories
INSERT INTO soporte.incident_categories (code, name, description, sla_response_hours, sla_resolution_hours, jira_issue_type, sort_order) VALUES
    ('TECNICO', 'Tecnico', 'Problemas tecnicos, errores y bugs del sistema', 4, 24, 'Bug', 1),
    ('FACTURACION', 'Facturacion', 'Problemas con facturacion electronica, CFDI y SAT', 4, 24, 'Bug', 2),
    ('CAPACITACION', 'Capacitacion', 'Solicitudes de capacitacion y entrenamiento', 24, 72, 'Story', 3),
    ('INVENTARIO', 'Inventario', 'Problemas con el modulo de inventario', 8, 48, 'Bug', 4),
    ('NOMINA', 'Nomina', 'Problemas con el modulo de nomina', 8, 48, 'Bug', 5),
    ('CONTABILIDAD', 'Contabilidad', 'Problemas con el modulo de contabilidad', 8, 48, 'Bug', 6),
    ('GENERAL', 'General', 'Consultas y problemas generales', 24, 72, 'Task', 7);

-- ============================================================================
-- TABLE: incidents
-- ============================================================================

CREATE TABLE soporte.incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    folio VARCHAR(20) UNIQUE NOT NULL,
    organization_id UUID REFERENCES core.organizations(id) ON DELETE CASCADE,
    user_phone VARCHAR(50) NOT NULL,
    user_name VARCHAR(200),
    conversation_id UUID,
    incident_type soporte.soporte_incident_type_enum NOT NULL DEFAULT 'incident',
    category_id UUID REFERENCES soporte.incident_categories(id) ON DELETE SET NULL,
    subject VARCHAR(500),
    description TEXT NOT NULL,
    priority soporte.soporte_incident_priority_enum NOT NULL DEFAULT 'medium',
    urgency soporte.soporte_incident_urgency_enum DEFAULT 'medium',
    impact soporte.soporte_incident_impact_enum,
    status soporte.soporte_incident_status_enum NOT NULL DEFAULT 'open',
    source soporte.soporte_incident_source_enum NOT NULL DEFAULT 'whatsapp',
    environment VARCHAR(100),
    steps_to_reproduce TEXT,
    expected_behavior TEXT,
    actual_behavior TEXT,
    attachments JSONB DEFAULT '[]'::jsonb,
    -- Jira integration
    jira_issue_key VARCHAR(50),
    jira_issue_id VARCHAR(50),
    jira_project_key VARCHAR(20),
    jira_sync_status soporte.soporte_jira_sync_status_enum DEFAULT 'pending',
    jira_last_sync_at TIMESTAMP,
    jira_sync_error TEXT,
    -- Resolution
    resolution TEXT,
    resolution_type VARCHAR(100),
    resolved_at TIMESTAMP,
    resolved_by VARCHAR(200),
    -- SLA
    sla_response_due TIMESTAMP,
    sla_resolution_due TIMESTAMP,
    sla_response_met BOOLEAN,
    sla_resolution_met BOOLEAN,
    -- Metadata
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for incidents
CREATE INDEX idx_incidents_folio ON soporte.incidents(folio);
CREATE INDEX idx_incidents_status ON soporte.incidents(status);
CREATE INDEX idx_incidents_user_phone ON soporte.incidents(user_phone);
CREATE INDEX idx_incidents_organization_id ON soporte.incidents(organization_id);
CREATE INDEX idx_incidents_jira_issue_key ON soporte.incidents(jira_issue_key);
CREATE INDEX idx_incidents_created_at ON soporte.incidents(created_at);
CREATE INDEX idx_incidents_priority ON soporte.incidents(priority);
CREATE INDEX idx_incidents_category_id ON soporte.incidents(category_id);

-- ============================================================================
-- TABLE: incident_comments
-- ============================================================================

CREATE TABLE soporte.incident_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES soporte.incidents(id) ON DELETE CASCADE,
    author_type soporte.soporte_comment_author_type_enum NOT NULL DEFAULT 'user',
    author_name VARCHAR(200),
    content TEXT NOT NULL,
    is_internal BOOLEAN NOT NULL DEFAULT FALSE,
    jira_comment_id VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for incident_comments
CREATE INDEX idx_incident_comments_incident_id ON soporte.incident_comments(incident_id);
CREATE INDEX idx_incident_comments_author_type ON soporte.incident_comments(author_type);
CREATE INDEX idx_incident_comments_created_at ON soporte.incident_comments(created_at);

-- ============================================================================
-- TABLE: incident_history
-- ============================================================================

CREATE TABLE soporte.incident_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES soporte.incidents(id) ON DELETE CASCADE,
    field_changed VARCHAR(100) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_by VARCHAR(200),
    changed_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for incident_history
CREATE INDEX idx_incident_history_incident_id ON soporte.incident_history(incident_id);
CREATE INDEX idx_incident_history_changed_at ON soporte.incident_history(changed_at);
CREATE INDEX idx_incident_history_field ON soporte.incident_history(field_changed);

-- ============================================================================
-- TABLE: jira_configs
-- ============================================================================

CREATE TABLE soporte.jira_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES core.organizations(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    jira_base_url VARCHAR(500) NOT NULL,
    jira_project_key VARCHAR(20) NOT NULL,
    jira_api_token_encrypted TEXT,
    jira_email VARCHAR(200) NOT NULL,
    webhook_secret VARCHAR(200),
    category_mapping JSONB DEFAULT '{}'::jsonb,
    module_mapping JSONB DEFAULT '{}'::jsonb,
    priority_mapping JSONB DEFAULT '{}'::jsonb,
    custom_fields JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for jira_configs
CREATE INDEX idx_jira_configs_organization_id ON soporte.jira_configs(organization_id);
CREATE INDEX idx_jira_configs_active ON soporte.jira_configs(is_active);
CREATE INDEX idx_jira_configs_project_key ON soporte.jira_configs(jira_project_key);

-- ============================================================================
-- TABLE: pending_tickets
-- ============================================================================

CREATE TABLE soporte.pending_tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id VARCHAR(255) NOT NULL,
    user_phone VARCHAR(50) NOT NULL,
    current_step VARCHAR(50) NOT NULL DEFAULT 'description',
    collected_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL DEFAULT (NOW() + INTERVAL '30 minutes'),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- Indexes for pending_tickets
CREATE INDEX idx_pending_tickets_conversation_id ON soporte.pending_tickets(conversation_id);
CREATE INDEX idx_pending_tickets_user_phone ON soporte.pending_tickets(user_phone);
CREATE INDEX idx_pending_tickets_active ON soporte.pending_tickets(is_active);
CREATE INDEX idx_pending_tickets_expires ON soporte.pending_tickets(expires_at) WHERE is_active = TRUE;

-- ============================================================================
-- FUNCTION: Generate folio for incidents
-- ============================================================================

CREATE OR REPLACE FUNCTION soporte.generate_incident_folio()
RETURNS TRIGGER AS $$
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
$$ LANGUAGE plpgsql;

-- Trigger to auto-generate folio
CREATE TRIGGER trigger_generate_incident_folio
    BEFORE INSERT ON soporte.incidents
    FOR EACH ROW
    WHEN (NEW.folio IS NULL OR NEW.folio = '')
    EXECUTE FUNCTION soporte.generate_incident_folio();

-- ============================================================================
-- FUNCTION: Calculate SLA deadlines
-- ============================================================================

CREATE OR REPLACE FUNCTION soporte.calculate_sla_deadlines()
RETURNS TRIGGER AS $$
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
$$ LANGUAGE plpgsql;

-- Trigger to auto-calculate SLA deadlines
CREATE TRIGGER trigger_calculate_sla_deadlines
    BEFORE INSERT ON soporte.incidents
    FOR EACH ROW
    EXECUTE FUNCTION soporte.calculate_sla_deadlines();

-- ============================================================================
-- FUNCTION: Update updated_at timestamp
-- ============================================================================

CREATE OR REPLACE FUNCTION soporte.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER trigger_incidents_updated_at
    BEFORE UPDATE ON soporte.incidents
    FOR EACH ROW
    EXECUTE FUNCTION soporte.update_updated_at_column();

CREATE TRIGGER trigger_incident_categories_updated_at
    BEFORE UPDATE ON soporte.incident_categories
    FOR EACH ROW
    EXECUTE FUNCTION soporte.update_updated_at_column();

CREATE TRIGGER trigger_incident_comments_updated_at
    BEFORE UPDATE ON soporte.incident_comments
    FOR EACH ROW
    EXECUTE FUNCTION soporte.update_updated_at_column();

CREATE TRIGGER trigger_jira_configs_updated_at
    BEFORE UPDATE ON soporte.jira_configs
    FOR EACH ROW
    EXECUTE FUNCTION soporte.update_updated_at_column();

-- ============================================================================
-- CLEANUP FUNCTION: Remove expired pending tickets
-- ============================================================================

CREATE OR REPLACE FUNCTION soporte.cleanup_expired_pending_tickets()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM soporte.pending_tickets
    WHERE is_active = TRUE AND expires_at < NOW();

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON SCHEMA soporte IS 'Support/Incidents management schema with Jira integration';
COMMENT ON TABLE soporte.incidents IS 'Main incidents/tickets table';
COMMENT ON TABLE soporte.incident_categories IS 'Dynamic incident categories with SLA and Jira mapping';
COMMENT ON TABLE soporte.incident_comments IS 'Comments on incidents';
COMMENT ON TABLE soporte.incident_history IS 'Audit trail of incident changes';
COMMENT ON TABLE soporte.jira_configs IS 'Multi-Jira configuration per organization';
COMMENT ON TABLE soporte.pending_tickets IS 'Conversational flow state for ticket creation';
