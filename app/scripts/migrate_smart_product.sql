-- Migración para agregar los nuevos campos del smart product
-- Ejecutar este script después de los cambios en el modelo

-- Agregar nuevas columnas a products si no existen
DO $$ 
BEGIN
    -- Agregar short_description
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='products' AND column_name='short_description') THEN
        ALTER TABLE products ADD COLUMN short_description VARCHAR(500);
    END IF;
    
    -- Agregar cost_price
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='products' AND column_name='cost_price') THEN
        ALTER TABLE products ADD COLUMN cost_price NUMERIC(10,2);
    END IF;
    
    -- Agregar search_vector
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='products' AND column_name='search_vector') THEN
        ALTER TABLE products ADD COLUMN search_vector TSVECTOR;
    END IF;
    
    -- Agregar sort_order a categories
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='categories' AND column_name='sort_order') THEN
        ALTER TABLE categories ADD COLUMN sort_order INTEGER DEFAULT 0;
    END IF;
    
    -- Agregar preferences a customers
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='customers' AND column_name='preferences') THEN
        ALTER TABLE customers ADD COLUMN preferences JSONB DEFAULT '{}';
    END IF;
    
    -- Agregar customer_id a product_reviews
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='product_reviews' AND column_name='customer_id') THEN
        ALTER TABLE product_reviews ADD COLUMN customer_id UUID REFERENCES customers(id);
    END IF;
END $$;

-- Crear tabla product_attributes si no existe
CREATE TABLE IF NOT EXISTS product_attributes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    value VARCHAR(500) NOT NULL,
    attribute_type VARCHAR(50) DEFAULT 'text',
    is_searchable BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_product_attribute_name UNIQUE (product_id, name)
);

-- Crear tabla product_images si no existe
CREATE TABLE IF NOT EXISTS product_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    url VARCHAR(1000) NOT NULL,
    alt_text VARCHAR(200),
    is_primary BOOLEAN DEFAULT FALSE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Crear tabla price_history si no existe
CREATE TABLE IF NOT EXISTS price_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    price FLOAT NOT NULL,
    change_reason VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Crear tabla stock_movements si no existe
CREATE TABLE IF NOT EXISTS stock_movements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    movement_type VARCHAR(20) NOT NULL,
    quantity INTEGER NOT NULL,
    previous_stock INTEGER NOT NULL,
    new_stock INTEGER NOT NULL,
    reason VARCHAR(100),
    notes TEXT,
    reference_number VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100)
);

-- Agregar índices necesarios
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_attributes_product ON product_attributes(product_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_attributes_name ON product_attributes(name);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_attributes_searchable ON product_attributes(is_searchable);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_images_product ON product_images(product_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_images_primary ON product_images(is_primary);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_images_sort ON product_images(sort_order);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_categories_sort ON categories(sort_order);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_products_search ON products USING gin(search_vector);

-- Crear extensiones necesarias si no existen
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- Crear función y trigger para search_vector
CREATE OR REPLACE FUNCTION update_product_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := 
        setweight(to_tsvector('spanish', COALESCE(NEW.name, '')), 'A') ||
        setweight(to_tsvector('spanish', COALESCE(NEW.description, '')), 'B') ||
        setweight(to_tsvector('spanish', COALESCE(NEW.model, '')), 'C') ||
        setweight(to_tsvector('spanish', COALESCE(NEW.specs, '')), 'D');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Crear trigger si no existe
DROP TRIGGER IF EXISTS products_search_vector_trigger ON products;
CREATE TRIGGER products_search_vector_trigger
    BEFORE INSERT OR UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION update_product_search_vector();

-- Actualizar search_vector para productos existentes
UPDATE products SET search_vector = 
    setweight(to_tsvector('spanish', COALESCE(name, '')), 'A') ||
    setweight(to_tsvector('spanish', COALESCE(description, '')), 'B') ||
    setweight(to_tsvector('spanish', COALESCE(model, '')), 'C') ||
    setweight(to_tsvector('spanish', COALESCE(specs, '')), 'D')
WHERE search_vector IS NULL;

-- Agregar constraints de validación
DO $$
BEGIN
    -- Constraint para price positivo (si no existe)
    IF NOT EXISTS (SELECT 1 FROM information_schema.check_constraints 
                   WHERE constraint_name = 'check_price_positive') THEN
        ALTER TABLE products ADD CONSTRAINT check_price_positive CHECK (price >= 0);
    END IF;
    
    -- Constraint para stock no negativo (si no existe)
    IF NOT EXISTS (SELECT 1 FROM information_schema.check_constraints 
                   WHERE constraint_name = 'check_stock_non_negative') THEN
        ALTER TABLE products ADD CONSTRAINT check_stock_non_negative CHECK (stock >= 0);
    END IF;
END $$;

-- Mostrar resumen de cambios
SELECT 'Migration completed successfully' as status;

-- Verificar que las tablas y columnas existen
SELECT 
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name IN ('products', 'categories', 'customers', 'product_attributes', 'product_images')
    AND column_name IN ('short_description', 'cost_price', 'search_vector', 'sort_order', 'preferences')
ORDER BY table_name, column_name;