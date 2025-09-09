-- Migration script to add external fields for DUX integration
-- Run this script to update the database schema with missing fields

-- Add external_id to categories table
ALTER TABLE categories 
ADD COLUMN IF NOT EXISTS external_id VARCHAR(100);

-- Create index for external_id lookups
CREATE INDEX IF NOT EXISTS idx_categories_external_id 
ON categories(external_id);

-- Add external_code to brands table
ALTER TABLE brands 
ADD COLUMN IF NOT EXISTS external_code VARCHAR(100);

-- Add missing fields to products table for DUX integration
ALTER TABLE products 
ADD COLUMN IF NOT EXISTS cost FLOAT DEFAULT 0.0;

ALTER TABLE products 
ADD COLUMN IF NOT EXISTS tax_percentage FLOAT DEFAULT 0.0;

ALTER TABLE products 
ADD COLUMN IF NOT EXISTS external_code VARCHAR(100);

ALTER TABLE products 
ADD COLUMN IF NOT EXISTS image_url VARCHAR(1000);

ALTER TABLE products 
ADD COLUMN IF NOT EXISTS barcode VARCHAR(100);

-- Create index for barcode lookups
CREATE INDEX IF NOT EXISTS idx_products_barcode 
ON products(barcode);

-- Add comments to document the purpose of these fields
COMMENT ON COLUMN categories.external_id IS 'External ID from DUX system (id_rubro)';
COMMENT ON COLUMN brands.external_code IS 'External code from DUX system (codigo_marca)';
COMMENT ON COLUMN products.cost IS 'Product cost from DUX system';
COMMENT ON COLUMN products.tax_percentage IS 'Tax percentage from DUX system (porc_iva)';
COMMENT ON COLUMN products.external_code IS 'External code from DUX system (codigo_externo)';
COMMENT ON COLUMN products.image_url IS 'Product image URL from DUX system';
COMMENT ON COLUMN products.barcode IS 'Product barcode from DUX system';