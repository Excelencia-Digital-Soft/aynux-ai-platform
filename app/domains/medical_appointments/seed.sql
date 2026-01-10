-- Medical Appointments Domain Seed
-- Run this SQL to register the domain and agent in the database

-- Insert domain
INSERT INTO core.domains (domain_key, display_name, description, icon, color, enabled, sort_order)
VALUES (
    'medical_appointments',
    'Turnos Médicos',
    'Gestión de turnos y citas médicas para instituciones de salud',
    'pi pi-calendar-plus',
    'info',
    true,
    50
)
ON CONFLICT (domain_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    icon = EXCLUDED.icon,
    color = EXCLUDED.color,
    enabled = EXCLUDED.enabled;

-- Insert agent
INSERT INTO core.agents (
    agent_key,
    name,
    description,
    agent_type,
    domain_key,
    enabled,
    priority,
    keywords,
    config
)
VALUES (
    'medical_appointments_agent',
    'Agente de Turnos Médicos',
    'Gestiona reserva, confirmación y cancelación de turnos médicos para Patología Digestiva',
    'builtin',
    'medical_appointments',
    true,
    50,
    ARRAY['turno', 'cita', 'médico', 'consulta', 'agendar', 'reservar', 'cancelar', 'confirmar'],
    '{
        "model": "qwen-3b",
        "temperature": 0.7,
        "knowledge_enabled": true,
        "institution": "patologia_digestiva"
    }'::jsonb
)
ON CONFLICT (agent_key) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    domain_key = EXCLUDED.domain_key,
    enabled = EXCLUDED.enabled,
    config = EXCLUDED.config;

-- Optional: Create bypass rule for the institution's WhatsApp number
-- Uncomment and update phone_number_id with the actual WhatsApp Business phone ID
/*
INSERT INTO core.bypass_rules (
    id,
    organization_id,
    rule_name,
    description,
    rule_type,
    phone_number_id,
    target_agent,
    target_domain,
    priority,
    enabled,
    isolated_history
)
VALUES (
    gen_random_uuid(),
    '00000000-0000-0000-0000-000000000000'::uuid,  -- System org or specific org UUID
    'medical_appointments_bypass_Patologia_Digestiva',
    'Bypass rule for Patología Digestiva medical appointments',
    'whatsapp_phone_number_id',
    'YOUR_WHATSAPP_PHONE_NUMBER_ID_HERE',  -- Replace with actual phone number ID
    'medical_appointments_agent',
    'medical_appointments',
    100,
    true,
    true
)
ON CONFLICT (organization_id, rule_name) DO UPDATE SET
    phone_number_id = EXCLUDED.phone_number_id,
    enabled = EXCLUDED.enabled;
*/
