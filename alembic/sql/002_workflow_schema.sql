-- ============================================================================
-- Workflow Schema - Configurable Workflow Builder
-- ============================================================================
-- Creates the workflow schema with tables for visual workflow builder.
-- Supports drag-and-drop workflow creation with Vue Flow editor.
-- ============================================================================

-- Create schema
CREATE SCHEMA IF NOT EXISTS workflow;

-- ============================================================================
-- Table: workflow.node_definitions
-- Registry of available node types (global catalog)
-- ============================================================================
CREATE TABLE workflow.node_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_key VARCHAR(100) NOT NULL UNIQUE,
    node_type VARCHAR(50) NOT NULL DEFAULT 'conversation',
    python_class VARCHAR(100) NOT NULL,
    python_module VARCHAR(255) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    icon VARCHAR(50) DEFAULT 'pi-circle',
    color VARCHAR(20) DEFAULT '#64748b',
    category VARCHAR(50) NOT NULL DEFAULT 'general',
    config_schema JSONB,
    default_config JSONB NOT NULL DEFAULT '{}',
    inputs JSONB NOT NULL DEFAULT '[]',
    outputs JSONB NOT NULL DEFAULT '[]',
    is_builtin BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_node_definitions_key ON workflow.node_definitions(node_key);
CREATE INDEX idx_node_definitions_type ON workflow.node_definitions(node_type);
CREATE INDEX idx_node_definitions_category ON workflow.node_definitions(category);
CREATE INDEX idx_node_definitions_active ON workflow.node_definitions(is_active);
CREATE INDEX idx_node_definitions_type_category ON workflow.node_definitions(node_type, category);

COMMENT ON TABLE workflow.node_definitions IS 'Registry of available node types for workflows';
COMMENT ON COLUMN workflow.node_definitions.node_key IS 'Unique key for the node type (e.g., greeting, specialty_selection)';
COMMENT ON COLUMN workflow.node_definitions.node_type IS 'Category: conversation, routing, integration, management';
COMMENT ON COLUMN workflow.node_definitions.python_class IS 'Python class name implementing this node';
COMMENT ON COLUMN workflow.node_definitions.config_schema IS 'JSON Schema for validating node configuration';

-- ============================================================================
-- Table: workflow.message_templates
-- Configurable message templates (created before workflow_definitions for FK)
-- ============================================================================
CREATE TABLE workflow.message_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_config_id UUID REFERENCES core.tenant_institution_configs(id) ON DELETE CASCADE,
    template_key VARCHAR(100) NOT NULL,
    template_type VARCHAR(50) NOT NULL DEFAULT 'general',
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    content TEXT NOT NULL,
    content_html TEXT,
    buttons JSONB NOT NULL DEFAULT '[]',
    placeholders JSONB NOT NULL DEFAULT '[]',
    language VARCHAR(10) NOT NULL DEFAULT 'es',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_message_templates_institution ON workflow.message_templates(institution_config_id);
CREATE INDEX idx_message_templates_key_type ON workflow.message_templates(template_key, template_type);
CREATE INDEX idx_message_templates_language ON workflow.message_templates(language);
CREATE INDEX idx_message_templates_active ON workflow.message_templates(is_active);
CREATE UNIQUE INDEX idx_message_templates_global_unique ON workflow.message_templates(template_key)
    WHERE institution_config_id IS NULL;

COMMENT ON TABLE workflow.message_templates IS 'Configurable message templates for workflows and reminders';
COMMENT ON COLUMN workflow.message_templates.institution_config_id IS 'Institution this template belongs to (NULL for global)';
COMMENT ON COLUMN workflow.message_templates.content IS 'Message content with {placeholders}';

-- ============================================================================
-- Table: workflow.workflow_definitions
-- Workflow configurations per institution
-- ============================================================================
CREATE TABLE workflow.workflow_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_config_id UUID NOT NULL REFERENCES core.tenant_institution_configs(id) ON DELETE CASCADE,
    workflow_key VARCHAR(100) NOT NULL,
    workflow_type VARCHAR(50) NOT NULL DEFAULT 'medical_appointments',
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    entry_node_id UUID,  -- FK added after node_instances table
    settings JSONB NOT NULL DEFAULT '{}',
    canvas_state JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_draft BOOLEAN NOT NULL DEFAULT TRUE,
    published_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_workflow_institution_key UNIQUE (institution_config_id, workflow_key)
);

CREATE INDEX idx_workflow_definitions_institution ON workflow.workflow_definitions(institution_config_id);
CREATE INDEX idx_workflow_definitions_type_active ON workflow.workflow_definitions(workflow_type, is_active);

COMMENT ON TABLE workflow.workflow_definitions IS 'Workflow configurations per institution';
COMMENT ON COLUMN workflow.workflow_definitions.settings IS 'Workflow-level settings (interaction mode, NLU config, etc.)';
COMMENT ON COLUMN workflow.workflow_definitions.canvas_state IS 'Vue Flow canvas state for visual editor';

-- ============================================================================
-- Table: workflow.node_instances
-- Configured node instances within workflows
-- ============================================================================
CREATE TABLE workflow.node_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES workflow.workflow_definitions(id) ON DELETE CASCADE,
    node_definition_id UUID NOT NULL REFERENCES workflow.node_definitions(id) ON DELETE RESTRICT,
    instance_key VARCHAR(100) NOT NULL,
    display_label VARCHAR(100),
    config JSONB NOT NULL DEFAULT '{}',
    position_x FLOAT NOT NULL DEFAULT 0.0,
    position_y FLOAT NOT NULL DEFAULT 0.0,
    is_entry_point BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_node_instance_workflow_key UNIQUE (workflow_id, instance_key)
);

CREATE INDEX idx_node_instances_workflow ON workflow.node_instances(workflow_id);
CREATE INDEX idx_node_instances_definition ON workflow.node_instances(node_definition_id);

COMMENT ON TABLE workflow.node_instances IS 'Configured node instances within workflows';
COMMENT ON COLUMN workflow.node_instances.instance_key IS 'Unique key within workflow (e.g., greeting_1)';
COMMENT ON COLUMN workflow.node_instances.position_x IS 'X position in Vue Flow canvas';

-- Add entry_node FK to workflow_definitions (after node_instances exists)
ALTER TABLE workflow.workflow_definitions
    ADD CONSTRAINT fk_workflow_entry_node
    FOREIGN KEY (entry_node_id) REFERENCES workflow.node_instances(id)
    ON DELETE SET NULL;

-- ============================================================================
-- Table: workflow.workflow_transitions
-- Transitions/edges between nodes
-- ============================================================================
CREATE TABLE workflow.workflow_transitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES workflow.workflow_definitions(id) ON DELETE CASCADE,
    source_node_id UUID NOT NULL REFERENCES workflow.node_instances(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES workflow.node_instances(id) ON DELETE CASCADE,
    transition_key VARCHAR(100),
    label VARCHAR(100),
    condition JSONB,
    priority INTEGER NOT NULL DEFAULT 0,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    style JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_workflow_transitions_workflow ON workflow.workflow_transitions(workflow_id);
CREATE INDEX idx_workflow_transitions_source ON workflow.workflow_transitions(source_node_id);
CREATE INDEX idx_workflow_transitions_target ON workflow.workflow_transitions(target_node_id);
CREATE INDEX idx_workflow_transitions_workflow_priority ON workflow.workflow_transitions(workflow_id, source_node_id, priority);

COMMENT ON TABLE workflow.workflow_transitions IS 'Transitions/edges between nodes in workflows';
COMMENT ON COLUMN workflow.workflow_transitions.condition IS 'JSON condition for conditional transitions';
COMMENT ON COLUMN workflow.workflow_transitions.priority IS 'Order for evaluating multiple transitions (lower = first)';

-- ============================================================================
-- Table: workflow.routing_rules
-- Configurable routing rules (human handoff, escalation, etc.)
-- ============================================================================
CREATE TABLE workflow.routing_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_config_id UUID NOT NULL REFERENCES core.tenant_institution_configs(id) ON DELETE CASCADE,
    rule_key VARCHAR(100) NOT NULL,
    rule_type VARCHAR(50) NOT NULL DEFAULT 'human_handoff',
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    condition JSONB NOT NULL DEFAULT '{}',
    action JSONB NOT NULL DEFAULT '{}',
    priority INTEGER NOT NULL DEFAULT 100,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_routing_rules_institution ON workflow.routing_rules(institution_config_id);
CREATE INDEX idx_routing_rules_type_active ON workflow.routing_rules(rule_type, is_active);
CREATE INDEX idx_routing_rules_institution_priority ON workflow.routing_rules(institution_config_id, priority);
CREATE INDEX idx_routing_rules_condition_gin ON workflow.routing_rules USING GIN (condition);

COMMENT ON TABLE workflow.routing_rules IS 'Configurable routing rules for workflow decisions';
COMMENT ON COLUMN workflow.routing_rules.condition IS 'JSON condition to evaluate (e.g., specialty == FONOAUDIOLOGIA)';
COMMENT ON COLUMN workflow.routing_rules.action IS 'JSON action to take (e.g., {type: human_handoff, message: ...})';

-- ============================================================================
-- Table: workflow.reminder_schedules
-- Reminder timing configuration per institution
-- ============================================================================
CREATE TABLE workflow.reminder_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_config_id UUID NOT NULL REFERENCES core.tenant_institution_configs(id) ON DELETE CASCADE,
    schedule_key VARCHAR(100) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    trigger_type VARCHAR(50) NOT NULL DEFAULT 'days_before',
    trigger_value INTEGER NOT NULL DEFAULT 1,
    execution_hour INTEGER NOT NULL DEFAULT 9,
    timezone VARCHAR(50) NOT NULL DEFAULT 'America/Argentina/San_Juan',
    message_template_id UUID REFERENCES workflow.message_templates(id) ON DELETE SET NULL,
    fallback_message TEXT,
    buttons JSONB NOT NULL DEFAULT '[]',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reminder_schedules_institution ON workflow.reminder_schedules(institution_config_id);
CREATE INDEX idx_reminder_schedules_trigger ON workflow.reminder_schedules(trigger_type, trigger_value);
CREATE INDEX idx_reminder_schedules_active ON workflow.reminder_schedules(is_active);

COMMENT ON TABLE workflow.reminder_schedules IS 'Reminder timing configuration per institution';
COMMENT ON COLUMN workflow.reminder_schedules.trigger_type IS 'Type: days_before, hours_before, minutes_before';
COMMENT ON COLUMN workflow.reminder_schedules.trigger_value IS 'Numeric value for trigger (e.g., 7 for 7 days before)';

-- ============================================================================
-- Triggers for updated_at timestamps
-- ============================================================================
CREATE OR REPLACE FUNCTION workflow.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_node_definitions_updated_at
    BEFORE UPDATE ON workflow.node_definitions
    FOR EACH ROW EXECUTE FUNCTION workflow.update_updated_at_column();

CREATE TRIGGER tr_workflow_definitions_updated_at
    BEFORE UPDATE ON workflow.workflow_definitions
    FOR EACH ROW EXECUTE FUNCTION workflow.update_updated_at_column();

CREATE TRIGGER tr_node_instances_updated_at
    BEFORE UPDATE ON workflow.node_instances
    FOR EACH ROW EXECUTE FUNCTION workflow.update_updated_at_column();

CREATE TRIGGER tr_workflow_transitions_updated_at
    BEFORE UPDATE ON workflow.workflow_transitions
    FOR EACH ROW EXECUTE FUNCTION workflow.update_updated_at_column();

CREATE TRIGGER tr_routing_rules_updated_at
    BEFORE UPDATE ON workflow.routing_rules
    FOR EACH ROW EXECUTE FUNCTION workflow.update_updated_at_column();

CREATE TRIGGER tr_reminder_schedules_updated_at
    BEFORE UPDATE ON workflow.reminder_schedules
    FOR EACH ROW EXECUTE FUNCTION workflow.update_updated_at_column();

CREATE TRIGGER tr_message_templates_updated_at
    BEFORE UPDATE ON workflow.message_templates
    FOR EACH ROW EXECUTE FUNCTION workflow.update_updated_at_column();
