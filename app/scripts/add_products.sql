-- Script SQL para agregar más categorías y productos

-- Primero, agregar más categorías si no existen
INSERT INTO categories (id, name, display_name, description, active) 
VALUES 
    (gen_random_uuid(), 'informatica', 'Informática', 'Computadoras, componentes y accesorios informáticos', true),
    (gen_random_uuid(), 'celulares', 'Celulares', 'Smartphones y accesorios móviles', true),
    (gen_random_uuid(), 'zapatillas', 'Zapatillas', 'Calzado deportivo y casual', true),
    (gen_random_uuid(), 'tablets', 'Tablets', 'Tablets y accesorios', true),
    (gen_random_uuid(), 'gaming', 'Gaming', 'Consolas, juegos y accesorios gaming', true),
    (gen_random_uuid(), 'audio', 'Audio', 'Auriculares, parlantes y equipos de sonido', true)
ON CONFLICT (name) DO NOTHING;

-- Agregar más marcas si no existen
INSERT INTO brands (id, name, display_name, warranty_years, active) 
VALUES 
    (gen_random_uuid(), 'Apple', 'Apple', 2, true),
    (gen_random_uuid(), 'Samsung', 'Samsung', 2, true),
    (gen_random_uuid(), 'Dell', 'Dell', 2, true),
    (gen_random_uuid(), 'HP', 'HP', 2, true),
    (gen_random_uuid(), 'Lenovo', 'Lenovo', 2, true),
    (gen_random_uuid(), 'Asus', 'ASUS', 2, true),
    (gen_random_uuid(), 'Nike', 'Nike', 1, true),
    (gen_random_uuid(), 'Adidas', 'Adidas', 1, true),
    (gen_random_uuid(), 'Puma', 'Puma', 1, true),
    (gen_random_uuid(), 'NewBalance', 'New Balance', 1, true),
    (gen_random_uuid(), 'Xiaomi', 'Xiaomi', 2, true),
    (gen_random_uuid(), 'OnePlus', 'OnePlus', 2, true),
    (gen_random_uuid(), 'Google', 'Google', 2, true),
    (gen_random_uuid(), 'Motorola', 'Motorola', 2, true)
ON CONFLICT (name) DO NOTHING;

-- Agregar productos de informática
INSERT INTO products (id, name, model, specs, description, price, stock, sku, category_id, brand_id, active, featured) 
SELECT 
    gen_random_uuid(),
    'Dell XPS 15 2024',
    'XPS 15 9530',
    'Intel Core i7-13700H, 16GB DDR5, 512GB NVMe SSD, RTX 4050',
    'Laptop premium con pantalla 4K OLED táctil',
    1899.99,
    15,
    'DELL-XPS15-2024',
    (SELECT id FROM categories WHERE name = 'informatica' LIMIT 1),
    (SELECT id FROM brands WHERE name = 'Dell' LIMIT 1),
    true,
    true
WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'DELL-XPS15-2024');

INSERT INTO products (id, name, model, specs, description, price, stock, sku, category_id, brand_id, active, featured) 
SELECT 
    gen_random_uuid(),
    'HP Pavilion Gaming 15',
    'Pavilion Gaming 15-ec2024',
    'AMD Ryzen 7 5800H, 16GB RAM, 1TB SSD, RTX 3060',
    'Laptop gaming con excelente relación precio-rendimiento',
    1299.99,
    8,
    'HP-PAVILION-G15',
    (SELECT id FROM categories WHERE name = 'informatica' LIMIT 1),
    (SELECT id FROM brands WHERE name = 'HP' LIMIT 1),
    true,
    false
WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'HP-PAVILION-G15');

INSERT INTO products (id, name, model, specs, description, price, stock, sku, category_id, brand_id, active, featured) 
SELECT 
    gen_random_uuid(),
    'ASUS ROG Strix G16',
    'G614JZ',
    'Intel i9-13980HX, 32GB DDR5, 2TB SSD, RTX 4070',
    'Laptop gaming de alta gama para entusiastas',
    2499.99,
    5,
    'ASUS-ROG-STRIX',
    (SELECT id FROM categories WHERE name = 'informatica' LIMIT 1),
    (SELECT id FROM brands WHERE name = 'Asus' LIMIT 1),
    true,
    true
WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'ASUS-ROG-STRIX');

-- Agregar productos de celulares
INSERT INTO products (id, name, model, specs, description, price, stock, sku, category_id, brand_id, active, featured) 
SELECT 
    gen_random_uuid(),
    'iPhone 15 Pro Max',
    'A3106',
    'A17 Pro, 256GB, Cámara 48MP, Titanio',
    'El iPhone más avanzado con diseño en titanio',
    1399.99,
    20,
    'IPHONE-15-PRO-MAX',
    (SELECT id FROM categories WHERE name = 'celulares' LIMIT 1),
    (SELECT id FROM brands WHERE name = 'Apple' LIMIT 1),
    true,
    true
WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'IPHONE-15-PRO-MAX');

INSERT INTO products (id, name, model, specs, description, price, stock, sku, category_id, brand_id, active, featured) 
SELECT 
    gen_random_uuid(),
    'Samsung Galaxy S24 Ultra',
    'SM-S928B',
    'Snapdragon 8 Gen 3, 12GB RAM, 512GB, Cámara 200MP',
    'Flagship Android con S-Pen integrado',
    1299.99,
    18,
    'SAMSUNG-S24-ULTRA',
    (SELECT id FROM categories WHERE name = 'celulares' LIMIT 1),
    (SELECT id FROM brands WHERE name = 'Samsung' LIMIT 1),
    true,
    true
WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'SAMSUNG-S24-ULTRA');

INSERT INTO products (id, name, model, specs, description, price, stock, sku, category_id, brand_id, active, featured) 
SELECT 
    gen_random_uuid(),
    'Xiaomi 14 Pro',
    '23129RA',
    'Snapdragon 8 Gen 3, 12GB RAM, 256GB, Cámara Leica',
    'Smartphone premium con sistema de cámara Leica',
    899.99,
    25,
    'XIAOMI-14-PRO',
    (SELECT id FROM categories WHERE name = 'celulares' LIMIT 1),
    (SELECT id FROM brands WHERE name = 'Xiaomi' LIMIT 1),
    true,
    false
WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'XIAOMI-14-PRO');

-- Agregar productos de zapatillas
INSERT INTO products (id, name, model, specs, description, price, stock, sku, category_id, brand_id, active, featured) 
SELECT 
    gen_random_uuid(),
    'Nike Air Max 2024',
    'DH8010-100',
    'Tecnología Air Max, Flyknit upper, Suela de goma',
    'Zapatillas deportivas con máxima amortiguación',
    179.99,
    30,
    'NIKE-AIR-MAX-2024',
    (SELECT id FROM categories WHERE name = 'zapatillas' LIMIT 1),
    (SELECT id FROM brands WHERE name = 'Nike' LIMIT 1),
    true,
    true
WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'NIKE-AIR-MAX-2024');

INSERT INTO products (id, name, model, specs, description, price, stock, sku, category_id, brand_id, active, featured) 
SELECT 
    gen_random_uuid(),
    'Adidas Ultraboost 22',
    'GX5915',
    'Boost midsole, Primeknit+ upper, Continental rubber',
    'Zapatillas running con tecnología Boost',
    189.99,
    25,
    'ADIDAS-ULTRABOOST-22',
    (SELECT id FROM categories WHERE name = 'zapatillas' LIMIT 1),
    (SELECT id FROM brands WHERE name = 'Adidas' LIMIT 1),
    true,
    true
WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'ADIDAS-ULTRABOOST-22');

INSERT INTO products (id, name, model, specs, description, price, stock, sku, category_id, brand_id, active, featured) 
SELECT 
    gen_random_uuid(),
    'Nike Air Jordan 1 Retro High',
    'DZ5485-612',
    'Cuero premium, Air-Sole, Diseño clásico',
    'Icónicas zapatillas de baloncesto',
    249.99,
    15,
    'NIKE-JORDAN-1-RETRO',
    (SELECT id FROM categories WHERE name = 'zapatillas' LIMIT 1),
    (SELECT id FROM brands WHERE name = 'Nike' LIMIT 1),
    true,
    false
WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'NIKE-JORDAN-1-RETRO');

INSERT INTO products (id, name, model, specs, description, price, stock, sku, category_id, brand_id, active, featured) 
SELECT 
    gen_random_uuid(),
    'Puma RS-X³',
    '372429-01',
    'RS cushioning, Mesh y cuero, Diseño retro',
    'Zapatillas con estilo retro futurista',
    119.99,
    20,
    'PUMA-RS-X',
    (SELECT id FROM categories WHERE name = 'zapatillas' LIMIT 1),
    (SELECT id FROM brands WHERE name = 'Puma' LIMIT 1),
    true,
    false
WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'PUMA-RS-X');

INSERT INTO products (id, name, model, specs, description, price, stock, sku, category_id, brand_id, active, featured) 
SELECT 
    gen_random_uuid(),
    'New Balance 990v6',
    'M990GL6',
    'ENCAP midsole, Pigskin/mesh upper, Made in USA',
    'Zapatillas premium hechas en Estados Unidos',
    199.99,
    18,
    'NB-990V6',
    (SELECT id FROM categories WHERE name = 'zapatillas' LIMIT 1),
    (SELECT id FROM brands WHERE name = 'NewBalance' LIMIT 1),
    true,
    false
WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'NB-990V6');

-- Agregar algunos productos más en otras categorías
INSERT INTO products (id, name, model, specs, description, price, stock, sku, category_id, brand_id, active, featured) 
SELECT 
    gen_random_uuid(),
    'iPad Pro 12.9" M2',
    'MNXP3LL/A',
    'Apple M2, 256GB, Liquid Retina XDR, WiFi 6E',
    'Tablet profesional con pantalla mini-LED',
    1299.99,
    10,
    'IPAD-PRO-M2',
    (SELECT id FROM categories WHERE name = 'tablets' LIMIT 1),
    (SELECT id FROM brands WHERE name = 'Apple' LIMIT 1),
    true,
    true
WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'IPAD-PRO-M2');

INSERT INTO products (id, name, model, specs, description, price, stock, sku, category_id, brand_id, active, featured) 
SELECT 
    gen_random_uuid(),
    'ASUS ROG Ally',
    'RC71L',
    'AMD Z1 Extreme, 512GB SSD, 7" FHD 120Hz, Windows 11',
    'Consola portátil para juegos de PC',
    699.99,
    12,
    'ASUS-ROG-ALLY',
    (SELECT id FROM categories WHERE name = 'gaming' LIMIT 1),
    (SELECT id FROM brands WHERE name = 'Asus' LIMIT 1),
    true,
    true
WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'ASUS-ROG-ALLY');

INSERT INTO products (id, name, model, specs, description, price, stock, sku, category_id, brand_id, active, featured) 
SELECT 
    gen_random_uuid(),
    'Apple AirPods Pro 2',
    'MQD83AM/A',
    'Chip H2, ANC adaptativo, Audio espacial, USB-C',
    'Auriculares inalámbricos con la mejor cancelación de ruido',
    249.99,
    40,
    'APPLE-AIRPODS-PRO2',
    (SELECT id FROM categories WHERE name = 'audio' LIMIT 1),
    (SELECT id FROM brands WHERE name = 'Apple' LIMIT 1),
    true,
    true
WHERE NOT EXISTS (SELECT 1 FROM products WHERE sku = 'APPLE-AIRPODS-PRO2');

-- Mostrar resumen
SELECT c.display_name as categoria, COUNT(p.id) as total_productos
FROM categories c
LEFT JOIN products p ON c.id = p.category_id
GROUP BY c.display_name
ORDER BY total_productos DESC;