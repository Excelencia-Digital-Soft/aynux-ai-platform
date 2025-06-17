#!/usr/bin/env python3
"""
Script to populate database with more categories and products - Simplified version
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.async_db import AsyncSessionLocal
from app.models.db import Category, Product, Brand
from app.config.settings import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def create_brands(session: AsyncSession) -> Dict[str, Brand]:
    """Create or get brands"""
    brands_data = [
        {"name": "Apple", "display_name": "Apple"},
        {"name": "Samsung", "display_name": "Samsung"},
        {"name": "Dell", "display_name": "Dell"},
        {"name": "HP", "display_name": "HP"},
        {"name": "Lenovo", "display_name": "Lenovo"},
        {"name": "Asus", "display_name": "ASUS"},
        {"name": "Nike", "display_name": "Nike"},
        {"name": "Adidas", "display_name": "Adidas"},
        {"name": "Puma", "display_name": "Puma"},
        {"name": "NewBalance", "display_name": "New Balance"},
        {"name": "Xiaomi", "display_name": "Xiaomi"},
        {"name": "OnePlus", "display_name": "OnePlus"},
        {"name": "Google", "display_name": "Google"},
        {"name": "Motorola", "display_name": "Motorola"},
    ]
    
    brands = {}
    for brand_data in brands_data:
        # Check if brand exists
        result = await session.execute(select(Brand).where(Brand.name == brand_data["name"]))
        brand = result.scalar_one_or_none()
        
        if not brand:
            brand = Brand(**brand_data)
            session.add(brand)
            await session.flush()
            logger.info(f"Created brand: {brand.name}")
        
        brands[brand.name] = brand
    
    return brands


async def create_categories(session: AsyncSession) -> Dict[str, Category]:
    """Create or get categories"""
    categories_data = [
        {
            "name": "informatica",
            "display_name": "Informática",
            "description": "Computadoras, componentes y accesorios informáticos"
        },
        {
            "name": "celulares",
            "display_name": "Celulares",
            "description": "Smartphones y accesorios móviles"
        },
        {
            "name": "zapatillas",
            "display_name": "Zapatillas",
            "description": "Calzado deportivo y casual"
        },
        {
            "name": "tablets",
            "display_name": "Tablets",
            "description": "Tablets y accesorios"
        },
        {
            "name": "gaming",
            "display_name": "Gaming",
            "description": "Consolas, juegos y accesorios gaming"
        },
        {
            "name": "audio",
            "display_name": "Audio",
            "description": "Auriculares, parlantes y equipos de sonido"
        },
    ]
    
    categories = {}
    for cat_data in categories_data:
        # Check if category exists
        result = await session.execute(select(Category).where(Category.name == cat_data["name"]))
        category = result.scalar_one_or_none()
        
        if not category:
            category = Category(**cat_data)
            session.add(category)
            await session.flush()
            logger.info(f"Created category: {category.display_name}")
        
        categories[category.name] = category
    
    return categories


async def create_products(session: AsyncSession, categories: Dict[str, Category], brands: Dict[str, Brand]):
    """Create products for all categories"""
    
    products_data = [
        # Informática Products
        {
            "sku": "DELL-XPS15-2024",
            "name": "Dell XPS 15 2024",
            "specs": "Intel Core i7-13700H, 16GB DDR5, 512GB NVMe SSD, RTX 4050",
            "description": "Laptop premium con pantalla 4K OLED táctil",
            "price": 1899.99,
            "stock": 15,
            "category": "informatica",
            "brand": "Dell",
            "featured": True,
        },
        {
            "sku": "HP-PAVILION-G15",
            "name": "HP Pavilion Gaming 15",
            "specs": "AMD Ryzen 7 5800H, 16GB RAM, 1TB SSD, RTX 3060",
            "description": "Laptop gaming con excelente relación precio-rendimiento",
            "price": 1299.99,
            "stock": 8,
            "category": "informatica",
            "brand": "HP",
        },
        {
            "sku": "ASUS-ROG-STRIX",
            "name": "ASUS ROG Strix G16",
            "specs": "Intel i9-13980HX, 32GB DDR5, 2TB SSD, RTX 4070",
            "description": "Laptop gaming de alta gama para entusiastas",
            "price": 2499.99,
            "stock": 5,
            "category": "informatica",
            "brand": "Asus",
            "featured": True,
        },
        {
            "sku": "LENOVO-THINKPAD-X1",
            "name": "Lenovo ThinkPad X1 Carbon",
            "specs": "Intel i7-1365U, 16GB RAM, 512GB SSD, 14\" FHD",
            "description": "Ultrabook empresarial con diseño robusto",
            "price": 1599.99,
            "stock": 12,
            "category": "informatica",
            "brand": "Lenovo",
        },
        {
            "sku": "APPLE-MACBOOK-PRO16",
            "name": "MacBook Pro 16\" M3 Max",
            "specs": "Apple M3 Max, 36GB RAM, 1TB SSD, Liquid Retina XDR",
            "description": "MacBook Pro más potente para profesionales creativos",
            "price": 3999.99,
            "stock": 7,
            "category": "informatica",
            "brand": "Apple",
            "featured": True,
        },
        
        # Celulares Products
        {
            "sku": "IPHONE-15-PRO-MAX",
            "name": "iPhone 15 Pro Max",
            "specs": "A17 Pro, 256GB, Cámara 48MP, Titanio",
            "description": "El iPhone más avanzado con diseño en titanio",
            "price": 1399.99,
            "stock": 20,
            "category": "celulares",
            "brand": "Apple",
            "featured": True,
        },
        {
            "sku": "SAMSUNG-S24-ULTRA",
            "name": "Samsung Galaxy S24 Ultra",
            "specs": "Snapdragon 8 Gen 3, 12GB RAM, 512GB, Cámara 200MP",
            "description": "Flagship Android con S-Pen integrado",
            "price": 1299.99,
            "stock": 18,
            "category": "celulares",
            "brand": "Samsung",
            "featured": True,
        },
        {
            "sku": "XIAOMI-14-PRO",
            "name": "Xiaomi 14 Pro",
            "specs": "Snapdragon 8 Gen 3, 12GB RAM, 256GB, Cámara Leica",
            "description": "Smartphone premium con sistema de cámara Leica",
            "price": 899.99,
            "stock": 25,
            "category": "celulares",
            "brand": "Xiaomi",
        },
        {
            "sku": "ONEPLUS-12",
            "name": "OnePlus 12",
            "specs": "Snapdragon 8 Gen 3, 16GB RAM, 256GB, Carga 100W",
            "description": "Flagship killer con carga súper rápida",
            "price": 799.99,
            "stock": 15,
            "category": "celulares",
            "brand": "OnePlus",
        },
        {
            "sku": "GOOGLE-PIXEL-8-PRO",
            "name": "Google Pixel 8 Pro",
            "specs": "Tensor G3, 12GB RAM, 256GB, IA avanzada",
            "description": "Smartphone con las mejores capacidades de IA",
            "price": 999.99,
            "stock": 10,
            "category": "celulares",
            "brand": "Google",
        },
        {
            "sku": "MOTOROLA-EDGE-40",
            "name": "Motorola Edge 40 Pro",
            "specs": "Snapdragon 8 Gen 2, 12GB RAM, 256GB, 165Hz",
            "description": "Smartphone con pantalla curva de alta frecuencia",
            "price": 699.99,
            "stock": 12,
            "category": "celulares",
            "brand": "Motorola",
        },
        
        # Zapatillas Products
        {
            "sku": "NIKE-AIR-MAX-2024",
            "name": "Nike Air Max 2024",
            "specs": "Tecnología Air Max, Flyknit upper, Suela de goma",
            "description": "Zapatillas deportivas con máxima amortiguación",
            "price": 179.99,
            "stock": 30,
            "category": "zapatillas",
            "brand": "Nike",
            "featured": True,
        },
        {
            "sku": "ADIDAS-ULTRABOOST-22",
            "name": "Adidas Ultraboost 22",
            "specs": "Boost midsole, Primeknit+ upper, Continental rubber",
            "description": "Zapatillas running con tecnología Boost",
            "price": 189.99,
            "stock": 25,
            "category": "zapatillas",
            "brand": "Adidas",
            "featured": True,
        },
        {
            "sku": "NIKE-JORDAN-1-RETRO",
            "name": "Nike Air Jordan 1 Retro High",
            "specs": "Cuero premium, Air-Sole, Diseño clásico",
            "description": "Icónicas zapatillas de baloncesto",
            "price": 249.99,
            "stock": 15,
            "category": "zapatillas",
            "brand": "Nike",
        },
        {
            "sku": "PUMA-RS-X",
            "name": "Puma RS-X³",
            "specs": "RS cushioning, Mesh y cuero, Diseño retro",
            "description": "Zapatillas con estilo retro futurista",
            "price": 119.99,
            "stock": 20,
            "category": "zapatillas",
            "brand": "Puma",
        },
        {
            "sku": "NB-990V6",
            "name": "New Balance 990v6",
            "specs": "ENCAP midsole, Pigskin/mesh upper, Made in USA",
            "description": "Zapatillas premium hechas en Estados Unidos",
            "price": 199.99,
            "stock": 18,
            "category": "zapatillas",
            "brand": "NewBalance",
        },
        {
            "sku": "ADIDAS-FORUM-LOW",
            "name": "Adidas Forum Low",
            "specs": "Cuero sintético, EVA midsole, Diseño basketball",
            "description": "Clásicas zapatillas de basketball estilo urbano",
            "price": 109.99,
            "stock": 35,
            "category": "zapatillas",
            "brand": "Adidas",
        },
        {
            "sku": "NIKE-DUNK-LOW",
            "name": "Nike Dunk Low",
            "specs": "Cuero y sintético, Zoom Air, Suela de goma",
            "description": "Zapatillas versátiles para skateboarding y lifestyle",
            "price": 139.99,
            "stock": 22,
            "category": "zapatillas",
            "brand": "Nike",
        },
        
        # Tablets
        {
            "sku": "IPAD-PRO-M2",
            "name": "iPad Pro 12.9\" M2",
            "specs": "Apple M2, 256GB, Liquid Retina XDR, WiFi 6E",
            "description": "Tablet profesional con pantalla mini-LED",
            "price": 1299.99,
            "stock": 10,
            "category": "tablets",
            "brand": "Apple",
            "featured": True,
        },
        {
            "sku": "SAMSUNG-TAB-S9-ULTRA",
            "name": "Samsung Galaxy Tab S9 Ultra",
            "specs": "Snapdragon 8 Gen 2, 12GB RAM, 512GB, 14.6\" AMOLED",
            "description": "Tablet Android más grande con S-Pen incluido",
            "price": 1199.99,
            "stock": 8,
            "category": "tablets",
            "brand": "Samsung",
        },
        
        # Gaming
        {
            "sku": "ASUS-ROG-ALLY",
            "name": "ASUS ROG Ally",
            "specs": "AMD Z1 Extreme, 512GB SSD, 7\" FHD 120Hz, Windows 11",
            "description": "Consola portátil para juegos de PC",
            "price": 699.99,
            "stock": 12,
            "category": "gaming",
            "brand": "Asus",
            "featured": True,
        },
        
        # Audio
        {
            "sku": "APPLE-AIRPODS-PRO2",
            "name": "Apple AirPods Pro 2",
            "specs": "Chip H2, ANC adaptativo, Audio espacial, USB-C",
            "description": "Auriculares inalámbricos con la mejor cancelación de ruido",
            "price": 249.99,
            "stock": 40,
            "category": "audio",
            "brand": "Apple",
            "featured": True,
        },
        {
            "sku": "SAMSUNG-BUDS2-PRO",
            "name": "Samsung Galaxy Buds2 Pro",
            "specs": "ANC inteligente, Hi-Fi 24bit, IPX7, 360 Audio",
            "description": "Auriculares true wireless con sonido de alta fidelidad",
            "price": 229.99,
            "stock": 25,
            "category": "audio",
            "brand": "Samsung",
        },
    ]
    
    created_count = 0
    for product_data in products_data:
        # Check if product exists
        result = await session.execute(select(Product).where(Product.sku == product_data["sku"]))
        existing_product = result.scalar_one_or_none()
        
        if not existing_product:
            # Get category and brand
            category = categories.get(product_data.pop("category"))
            brand = brands.get(product_data.pop("brand"))
            
            if not category or not brand:
                logger.warning(f"Skipping product {product_data['name']} - missing category or brand")
                continue
            
            product = Product(
                **product_data,
                category_id=category.id,
                brand_id=brand.id,
                active=True
            )
            session.add(product)
            created_count += 1
            logger.info(f"Created product: {product.name}")
    
    return created_count


async def main():
    """Main function to populate database"""
    logger.info("Starting database population...")
    
    async with AsyncSessionLocal() as session:
        try:
            # Create brands
            brands = await create_brands(session)
            logger.info(f"Total brands: {len(brands)}")
            
            # Create categories
            categories = await create_categories(session)
            logger.info(f"Total categories: {len(categories)}")
            
            # Create products
            product_count = await create_products(session, categories, brands)
            logger.info(f"Created {product_count} new products")
            
            # Commit all changes
            await session.commit()
            
            # Show summary
            result = await session.execute(select(Product))
            total_products = len(result.scalars().all())
            
            logger.info("\n" + "="*50)
            logger.info("DATABASE POPULATION COMPLETE")
            logger.info(f"Total products in database: {total_products}")
            logger.info("="*50)
            
            # Show products by category
            for cat_name, category in categories.items():
                result = await session.execute(
                    select(Product).where(Product.category_id == category.id)
                )
                products = result.scalars().all()
                logger.info(f"\n{category.display_name}: {len(products)} products")
                for product in products[:3]:  # Show first 3
                    logger.info(f"  - {product.name} (${product.price})")
                if len(products) > 3:
                    logger.info(f"  ... and {len(products) - 3} more")
            
        except Exception as e:
            logger.error(f"Error populating database: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())