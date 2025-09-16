-- Migración: Crear tablas para sistema multi-dominio
-- Archivo: create_contact_domains_tables.sql
-- Descripción: Infraestructura para detección y gestión de dominios por contacto

-- =====================================================
-- Tabla: contact_domains
-- Propósito: Mapeo de contactos WhatsApp a dominios
-- =====================================================

CREATE TABLE IF NOT EXISTS contact_domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wa_id VARCHAR(20) UNIQUE NOT NULL,
    domain VARCHAR(50) NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 1.0,
    assigned_method VARCHAR(50) NOT NULL,
    domain_metadata JSONB DEFAULT '{}',
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_verified TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices optimizados para performance
CREATE INDEX IF NOT EXISTS idx_contact_domains_wa_id ON contact_domains(wa_id);
CREATE INDEX IF NOT EXISTS idx_contact_domains_domain ON contact_domains(domain);
CREATE INDEX IF NOT EXISTS idx_contact_domains_method ON contact_domains(assigned_method);
CREATE INDEX IF NOT EXISTS idx_contact_domains_assigned_at ON contact_domains(assigned_at);

-- Comentarios para documentación
COMMENT ON TABLE contact_domains IS 'Mapeo de contactos WhatsApp a dominios específicos del negocio';
COMMENT ON COLUMN contact_domains.wa_id IS 'WhatsApp ID del contacto (ej: 5491123456789)';
COMMENT ON COLUMN contact_domains.domain IS 'Dominio asignado: ecommerce, hospital, credit, excelencia';
COMMENT ON COLUMN contact_domains.confidence IS 'Nivel de confianza en la asignación (0.0-1.0)';
COMMENT ON COLUMN contact_domains.assigned_method IS 'Método de asignación: manual, auto, pattern, ai, admin';
COMMENT ON COLUMN contact_domains.domain_metadata IS 'Metadatos específicos del dominio (JSON)';

-- =====================================================
-- Tabla: domain_configs
-- Propósito: Configuración dinámica de dominios
-- =====================================================

CREATE TABLE IF NOT EXISTS domain_configs (
    domain VARCHAR(50) PRIMARY KEY,
    enabled VARCHAR(10) NOT NULL DEFAULT 'true',
    display_name VARCHAR(100) NOT NULL,
    description VARCHAR(500),
    service_class VARCHAR(100),
    model_config JSONB DEFAULT '{}',
    phone_patterns JSONB DEFAULT '[]',
    keyword_patterns JSONB DEFAULT '[]',
    priority FLOAT DEFAULT 0.5,
    fallback_enabled VARCHAR(10) DEFAULT 'true',
    config_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para configuración
CREATE INDEX IF NOT EXISTS idx_domain_configs_enabled ON domain_configs(enabled);
CREATE INDEX IF NOT EXISTS idx_domain_configs_priority ON domain_configs(priority);

-- Comentarios
COMMENT ON TABLE domain_configs IS 'Configuración dinámica de dominios disponibles';
COMMENT ON COLUMN domain_configs.enabled IS 'Estado: true, false, maintenance';
COMMENT ON COLUMN domain_configs.service_class IS 'Clase Python del servicio de dominio';
COMMENT ON COLUMN domain_configs.phone_patterns IS 'Patrones de números para detección automática';
COMMENT ON COLUMN domain_configs.keyword_patterns IS 'Palabras clave para clasificación';
COMMENT ON COLUMN domain_configs.priority IS 'Prioridad en clasificación automática (0.0-1.0)';

-- =====================================================
-- Datos iniciales: Configuración de dominios
-- =====================================================

-- Dominio E-commerce (existente)
INSERT INTO domain_configs (
    domain, 
    enabled, 
    display_name, 
    description, 
    service_class,
    priority,
    keyword_patterns,
    metadata
) VALUES (
    'ecommerce',
    'true',
    'E-commerce ConversaShop',
    'Tienda online de productos tecnológicos y componentes',
    'EcommerceDomainService',
    0.8,
    '["comprar", "producto", "precio", "tienda", "envío", "stock", "descuento", "carrito", "pago", "factura"]',
    '{"default_model": "deepseek-r1:7b", "vector_collection": "products"}'
) ON CONFLICT (domain) DO NOTHING;

-- Dominio Hospital
INSERT INTO domain_configs (
    domain, 
    enabled, 
    display_name, 
    description, 
    service_class,
    priority,
    keyword_patterns,
    metadata
) VALUES (
    'hospital',
    'true',
    'Sistema Hospitalario',
    'Gestión de citas, consultas y servicios médicos',
    'HospitalDomainService',
    0.7,
    '["cita", "doctor", "médico", "consulta", "urgencia", "emergencia", "síntoma", "turno", "especialista", "hospital"]',
    '{"default_model": "deepseek-r1:7b", "vector_collection": "medical_knowledge"}'
) ON CONFLICT (domain) DO NOTHING;

-- Dominio Créditos
INSERT INTO domain_configs (
    domain, 
    enabled, 
    display_name, 
    description, 
    service_class,
    priority,
    keyword_patterns,
    metadata
) VALUES (
    'credit',
    'false',
    'Servicios Crediticios',
    'Préstamos, financiamiento y servicios financieros',
    'CreditDomainService',
    0.6,
    '["préstamo", "crédito", "financiamiento", "cuota", "tasa", "interés", "DNI", "ingresos", "garantía", "aval"]',
    '{"default_model": "deepseek-r1:7b", "vector_collection": "credit_products"}'
) ON CONFLICT (domain) DO NOTHING;

-- Dominio Excelencia (Software)
INSERT INTO domain_configs (
    domain, 
    enabled, 
    display_name, 
    description, 
    service_class,
    priority,
    keyword_patterns,
    metadata
) VALUES (
    'excelencia',
    'true',
    'Software Excelencia',
    'Demostración y soporte del software ERP Excelencia',
    'ExcelenciaDomainService',
    0.5,
    '["software", "sistema", "ERP", "excelencia", "demo", "funcionalidad", "módulo", "reporte", "gestión", "automatización"]',
    '{"default_model": "deepseek-r1:7b", "vector_collection": "software_knowledge"}'
) ON CONFLICT (domain) DO NOTHING;

-- =====================================================
-- Función: Trigger para updated_at automático
-- =====================================================

-- Función para actualizar timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers para updated_at automático
DROP TRIGGER IF EXISTS update_contact_domains_updated_at ON contact_domains;
CREATE TRIGGER update_contact_domains_updated_at
    BEFORE UPDATE ON contact_domains
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_domain_configs_updated_at ON domain_configs;
CREATE TRIGGER update_domain_configs_updated_at
    BEFORE UPDATE ON domain_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- Validaciones y constraints
-- =====================================================

-- Constraint: confidence debe estar entre 0.0 y 1.0
ALTER TABLE contact_domains 
ADD CONSTRAINT chk_confidence_range 
CHECK (confidence >= 0.0 AND confidence <= 1.0);

-- Constraint: priority debe estar entre 0.0 y 1.0
ALTER TABLE domain_configs 
ADD CONSTRAINT chk_priority_range 
CHECK (priority >= 0.0 AND priority <= 1.0);

-- Constraint: valores válidos para enabled
ALTER TABLE domain_configs 
ADD CONSTRAINT chk_enabled_values 
CHECK (enabled IN ('true', 'false', 'maintenance'));

-- Constraint: valores válidos para fallback_enabled
ALTER TABLE domain_configs 
ADD CONSTRAINT chk_fallback_enabled_values 
CHECK (fallback_enabled IN ('true', 'false'));

-- =====================================================
-- Fin de migración
-- =====================================================

-- Verificar que las tablas se crearon correctamente
SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables 
WHERE tablename IN ('contact_domains', 'domain_configs')
ORDER BY tablename;