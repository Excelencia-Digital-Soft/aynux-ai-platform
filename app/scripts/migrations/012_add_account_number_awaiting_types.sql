-- Migration: Add account_number and account_not_found awaiting types
-- Purpose: Support new authentication flow: Account Number (primary) + DNI/Name (fallback)
-- Date: 2025-01-14

-- Insert account_number awaiting type config (primary authentication)
INSERT INTO core.awaiting_type_configs (
    id,
    organization_id,
    domain_key,
    awaiting_type,
    target_node,
    valid_response_intents,
    validation_pattern,
    priority,
    is_enabled,
    display_name,
    description
) VALUES (
    gen_random_uuid(),
    NULL,  -- System default (applies to all orgs)
    'pharmacy',
    'account_number',
    'auth_plex',
    '[]'::jsonb,  -- No specific intents needed
    '^\d{1,10}$',  -- Pattern: 1-10 digits
    100,  -- High priority
    true,
    'Número de Cuenta',
    'Awaiting pharmacy account number for primary authentication'
) ON CONFLICT DO NOTHING;

-- Insert account_not_found awaiting type config (button selection after account not found)
INSERT INTO core.awaiting_type_configs (
    id,
    organization_id,
    domain_key,
    awaiting_type,
    target_node,
    valid_response_intents,
    validation_pattern,
    priority,
    is_enabled,
    display_name,
    description
) VALUES (
    gen_random_uuid(),
    NULL,  -- System default (applies to all orgs)
    'pharmacy',
    'account_not_found',
    'auth_plex',
    '["retry_account", "validate_dni"]'::jsonb,  -- Valid response intents for button selection
    NULL,  -- No regex pattern needed
    90,
    true,
    'Cuenta No Encontrada',
    'Awaiting user selection: retry account number or switch to DNI validation'
) ON CONFLICT DO NOTHING;

-- Verify insertion
SELECT awaiting_type, target_node, display_name, is_enabled
FROM core.awaiting_type_configs
WHERE awaiting_type IN ('account_number', 'account_not_found')
AND domain_key = 'pharmacy';
