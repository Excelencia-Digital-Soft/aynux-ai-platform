-- Migration: Initialize system organization for fallback mode
-- Date: 2025-12-02
-- Author: Aynux System
-- Description: Crea la organizacion del sistema usada en modo generico (fallback)
-- Depends on: 007_create_tenancy_tables.sql

-- =====================================================
-- 1. Crear organización del sistema (modo genérico/fallback)
-- =====================================================
INSERT INTO core.organizations (
    id,
    slug,
    name,
    display_name,
    mode,
    llm_model,
    llm_temperature,
    llm_max_tokens,
    features,
    max_users,
    max_documents,
    max_agents,
    status,
    created_at,
    updated_at
)
VALUES (
    '00000000-0000-0000-0000-000000000000',
    'system',
    'System',
    'System (Generic Mode)',
    'generic',
    'llama3.2:1b',
    0.7,
    2048,
    '{"rag_enabled": true, "multi_domain": true, "custom_agents": true}'::jsonb,
    1000,
    10000,
    100,
    'active',
    NOW(),
    NOW()
)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    display_name = EXCLUDED.display_name,
    updated_at = NOW();

-- =====================================================
-- 2. Crear configuración por defecto para system org
-- =====================================================
INSERT INTO core.tenant_configs (
    id,
    organization_id,
    enabled_domains,
    default_domain,
    enabled_agent_types,
    agent_timeout_seconds,
    rag_enabled,
    rag_similarity_threshold,
    rag_max_results,
    prompt_scope,
    advanced_config,
    created_at,
    updated_at
)
VALUES (
    gen_random_uuid(),
    '00000000-0000-0000-0000-000000000000',
    ARRAY['ecommerce', 'healthcare', 'credit', 'excelencia'],
    'excelencia',
    ARRAY[]::text[],  -- Empty = all agents enabled
    30,
    TRUE,
    0.7,
    5,
    'org',
    '{"rate_limit": null, "priority": "normal"}'::jsonb,
    NOW(),
    NOW()
)
ON CONFLICT (organization_id) DO UPDATE SET
    enabled_domains = EXCLUDED.enabled_domains,
    rag_enabled = EXCLUDED.rag_enabled,
    updated_at = NOW();

-- =====================================================
-- 3. Crear agentes builtin para system org
-- =====================================================

-- Greeting Agent
INSERT INTO core.tenant_agents (id, organization_id, agent_key, agent_type, display_name, description, enabled, priority, keywords, intent_patterns, config, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    '00000000-0000-0000-0000-000000000000',
    'greeting_agent',
    'specialized',
    'Greeting Agent',
    'Maneja saludos y presentacion del sistema',
    TRUE, 10,
    ARRAY['hola', 'hello', 'buenos dias', 'buenas tardes', 'hi'],
    '[]'::jsonb,
    '{}'::jsonb,
    NOW(), NOW()
) ON CONFLICT (organization_id, agent_key) DO NOTHING;

-- Product Agent
INSERT INTO core.tenant_agents (id, organization_id, agent_key, agent_type, display_name, description, enabled, priority, domain_key, keywords, intent_patterns, config, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    '00000000-0000-0000-0000-000000000000',
    'product_agent',
    'domain',
    'Product Agent',
    'Busqueda y consultas de productos',
    TRUE, 20,
    'ecommerce',
    ARRAY['producto', 'precio', 'catalogo', 'buscar', 'comprar'],
    '[]'::jsonb,
    '{}'::jsonb,
    NOW(), NOW()
) ON CONFLICT (organization_id, agent_key) DO NOTHING;

-- Support Agent
INSERT INTO core.tenant_agents (id, organization_id, agent_key, agent_type, display_name, description, enabled, priority, keywords, intent_patterns, config, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    '00000000-0000-0000-0000-000000000000',
    'support_agent',
    'specialized',
    'Support Agent',
    'Soporte tecnico y ayuda al cliente',
    TRUE, 15,
    ARRAY['ayuda', 'problema', 'soporte', 'error', 'help'],
    '[]'::jsonb,
    '{}'::jsonb,
    NOW(), NOW()
) ON CONFLICT (organization_id, agent_key) DO NOTHING;

-- Excelencia Agent
INSERT INTO core.tenant_agents (id, organization_id, agent_key, agent_type, display_name, description, enabled, priority, domain_key, keywords, intent_patterns, config, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    '00000000-0000-0000-0000-000000000000',
    'excelencia_agent',
    'domain',
    'Excelencia Agent',
    'Informacion sobre sistema ERP Excelencia',
    TRUE, 25,
    'excelencia',
    ARRAY['excelencia', 'erp', 'sistema', 'modulo', 'funcionalidad'],
    '[]'::jsonb,
    '{}'::jsonb,
    NOW(), NOW()
) ON CONFLICT (organization_id, agent_key) DO NOTHING;

-- Fallback Agent
INSERT INTO core.tenant_agents (id, organization_id, agent_key, agent_type, display_name, description, enabled, priority, keywords, intent_patterns, config, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    '00000000-0000-0000-0000-000000000000',
    'fallback_agent',
    'specialized',
    'Fallback Agent',
    'Respuestas por defecto cuando no se detecta intent',
    TRUE, 1,
    ARRAY[]::text[],
    '[]'::jsonb,
    '{}'::jsonb,
    NOW(), NOW()
) ON CONFLICT (organization_id, agent_key) DO NOTHING;

-- Farewell Agent
INSERT INTO core.tenant_agents (id, organization_id, agent_key, agent_type, display_name, description, enabled, priority, keywords, intent_patterns, config, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    '00000000-0000-0000-0000-000000000000',
    'farewell_agent',
    'specialized',
    'Farewell Agent',
    'Despedidas y cierre de conversaciones',
    TRUE, 5,
    ARRAY['adios', 'chau', 'bye', 'gracias', 'hasta luego'],
    '[]'::jsonb,
    '{}'::jsonb,
    NOW(), NOW()
) ON CONFLICT (organization_id, agent_key) DO NOTHING;

-- Promotions Agent
INSERT INTO core.tenant_agents (id, organization_id, agent_key, agent_type, display_name, description, enabled, priority, domain_key, keywords, intent_patterns, config, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    '00000000-0000-0000-0000-000000000000',
    'promotions_agent',
    'domain',
    'Promotions Agent',
    'Ofertas, descuentos y promociones',
    TRUE, 18,
    'ecommerce',
    ARRAY['oferta', 'descuento', 'promocion', 'cupon', 'sale'],
    '[]'::jsonb,
    '{}'::jsonb,
    NOW(), NOW()
) ON CONFLICT (organization_id, agent_key) DO NOTHING;

-- Tracking Agent
INSERT INTO core.tenant_agents (id, organization_id, agent_key, agent_type, display_name, description, enabled, priority, domain_key, keywords, intent_patterns, config, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    '00000000-0000-0000-0000-000000000000',
    'tracking_agent',
    'domain',
    'Tracking Agent',
    'Seguimiento de pedidos y envios',
    TRUE, 16,
    'ecommerce',
    ARRAY['pedido', 'envio', 'seguimiento', 'tracking', 'donde esta'],
    '[]'::jsonb,
    '{}'::jsonb,
    NOW(), NOW()
) ON CONFLICT (organization_id, agent_key) DO NOTHING;

-- Invoice Agent
INSERT INTO core.tenant_agents (id, organization_id, agent_key, agent_type, display_name, description, enabled, priority, keywords, intent_patterns, config, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    '00000000-0000-0000-0000-000000000000',
    'invoice_agent',
    'specialized',
    'Invoice Agent',
    'Facturacion, pagos y comprobantes',
    TRUE, 14,
    ARRAY['factura', 'pago', 'comprobante', 'cuenta', 'deuda'],
    '[]'::jsonb,
    '{}'::jsonb,
    NOW(), NOW()
) ON CONFLICT (organization_id, agent_key) DO NOTHING;

-- =====================================================
-- 4. Verificación
-- =====================================================
DO $$
DECLARE
    org_count INTEGER;
    config_count INTEGER;
    agent_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO org_count FROM core.organizations WHERE id = '00000000-0000-0000-0000-000000000000';
    SELECT COUNT(*) INTO config_count FROM core.tenant_configs WHERE organization_id = '00000000-0000-0000-0000-000000000000';
    SELECT COUNT(*) INTO agent_count FROM core.tenant_agents WHERE organization_id = '00000000-0000-0000-0000-000000000000';

    RAISE NOTICE 'System organization initialized:';
    RAISE NOTICE '  - Organizations: %', org_count;
    RAISE NOTICE '  - Tenant configs: %', config_count;
    RAISE NOTICE '  - Builtin agents: %', agent_count;
END $$;
