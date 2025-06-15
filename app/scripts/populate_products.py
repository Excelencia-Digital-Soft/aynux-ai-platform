#!/usr/bin/env python3
"""
Script to populate database with more categories and products
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.async_db import AsyncSessionLocal
from app.models.database import Category, Product, Brand, Base
from app.config.settings import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def create_brands(session: AsyncSession) -> Dict[str, Brand]:
    """Create or get brands"""
    brands_data = [
        {"name": "Apple", "description": "Tecnología premium"},
        {"name": "Samsung", "description": "Innovación en electrónicos"},
        {"name": "Dell", "description": "Computadoras y servidores"},
        {"name": "HP", "description": "Soluciones tecnológicas"},
        {"name": "Lenovo", "description": "Tecnología confiable"},
        {"name": "Asus", "description": "Gaming y productividad"},
        {"name": "Nike", "description": "Calzado deportivo líder"},
        {"name": "Adidas", "description": "Deportes y estilo"},
        {"name": "Puma", "description": "Rendimiento deportivo"},
        {"name": "New Balance", "description": "Comodidad y calidad"},
        {"name": "Xiaomi", "description": "Tecnología accesible"},
        {"name": "OnePlus", "description": "Flagship killers"},
        {"name": "Google", "description": "Tecnología inteligente"},
        {"name": "Motorola", "description": "Comunicación confiable"},
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
            "description": "Computadoras, componentes y accesorios informáticos",
            "icon": "💻"
        },
        {
            "name": "celulares",
            "display_name": "Celulares",
            "description": "Smartphones y accesorios móviles",
            "icon": "📱"
        },
        {
            "name": "zapatillas",
            "display_name": "Zapatillas",
            "description": "Calzado deportivo y casual",
            "icon": "👟"
        },
        {
            "name": "tablets",
            "display_name": "Tablets",
            "description": "Tablets y accesorios",
            "icon": "📱"
        },
        {
            "name": "gaming",
            "display_name": "Gaming",
            "description": "Consolas, juegos y accesorios gaming",
            "icon": "🎮"
        },
        {
            "name": "audio",
            "display_name": "Audio",
            "description": "Auriculares, parlantes y equipos de sonido",
            "icon": "🎧"
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
            "model": "XPS 15 9530",
            "specs": "Intel Core i7-13700H, 16GB DDR5, 512GB NVMe SSD, NVIDIA RTX 4050 6GB",
            "description": "Laptop premium con Intel Core i7, 16GB RAM, 512GB SSD, pantalla 4K OLED",
            "price": 1899.99,
            "stock": 15,
            "category": "informatica",
            "brand": "Dell",
            "featured": True,
            "technical_specs": {
                "cpu": "Intel Core i7-13700H",
                "ram": "16GB DDR5",
                "storage": "512GB NVMe SSD",
                "gpu": "NVIDIA RTX 4050 6GB",
                "display": "15.6\" 4K OLED Touch"
            },
            "features": ["Pantalla táctil OLED", "Thunderbolt 4", "Windows 11 Pro", "Teclado retroiluminado"],
        },
        {
            "sku": "HP-PAVILION-G7",
            "name": "HP Pavilion Gaming 15",
            "description": "Laptop gaming con AMD Ryzen 7, RTX 3060, 16GB RAM, 1TB SSD",
            "price": 1299.99,
            "stock": 8,
            "category": "informatica",
            "brand": "HP",
        },
        {
            "sku": "ASUS-ROG-STRIX",
            "name": "ASUS ROG Strix G16",
            "description": "Laptop gaming de alta gama, Intel i9, RTX 4070, 32GB RAM, 2TB SSD",
            "price": 2499.99,
            "stock": 5,
            "category": "informatica",
            "brand": "Asus",
            "featured": True,
        },
        {
            "sku": "LENOVO-THINKPAD-X1",
            "name": "Lenovo ThinkPad X1 Carbon",
            "description": "Ultrabook empresarial, Intel i7, 16GB RAM, 512GB SSD, 14\" FHD",
            "price": 1599.99,
            "stock": 12,
            "category": "informatica",
            "brand": "Lenovo",
        },
        {
            "sku": "APPLE-MACBOOK-PRO16",
            "name": "MacBook Pro 16\" M3 Max",
            "description": "MacBook Pro con chip M3 Max, 36GB RAM, 1TB SSD, pantalla Liquid Retina XDR",
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
            "description": "iPhone más avanzado con chip A17 Pro, 256GB, cámara de 48MP, titanio",
            "price": 1399.99,
            "stock": 20,
            "category": "celulares",
            "brand": "Apple",
            "featured": True,
        },
        {
            "sku": "SAMSUNG-S24-ULTRA",
            "name": "Samsung Galaxy S24 Ultra",
            "description": "Flagship Android con S-Pen, 12GB RAM, 512GB, cámara 200MP",
            "price": 1299.99,
            "stock": 18,
            "category": "celulares",
            "brand": "Samsung",
            "featured": True,
        },
        {
            "sku": "XIAOMI-14-PRO",
            "name": "Xiaomi 14 Pro",
            "description": "Smartphone premium con Snapdragon 8 Gen 3, 12GB RAM, 256GB, cámara Leica",
            "price": 899.99,
            "stock": 25,
            "category": "celulares",
            "brand": "Xiaomi",
        },
        {
            "sku": "ONEPLUS-12",
            "name": "OnePlus 12",
            "description": "Flagship killer con Snapdragon 8 Gen 3, 16GB RAM, 256GB, carga 100W",
            "price": 799.99,
            "stock": 15,
            "category": "celulares",
            "brand": "OnePlus",
        },
        {
            "sku": "GOOGLE-PIXEL-8-PRO",
            "name": "Google Pixel 8 Pro",
            "description": "Smartphone con IA avanzada, Tensor G3, 12GB RAM, 256GB, cámara excepcional",
            "price": 999.99,
            "stock": 10,
            "category": "celulares",
            "brand": "Google",
        },
        {
            "sku": "MOTOROLA-EDGE-40",
            "name": "Motorola Edge 40 Pro",
            "description": "Smartphone premium con pantalla curva 165Hz, 12GB RAM, 256GB",
            "price": 699.99,
            "stock": 12,
            "category": "celulares",
            "brand": "Motorola",
        },
        
        # Zapatillas Products
        {
            "sku": "NIKE-AIR-MAX-2024",
            "name": "Nike Air Max 2024",
            "description": "Zapatillas deportivas con tecnología Air Max, diseño moderno y cómodo",
            "price": 179.99,
            "stock": 30,
            "category": "zapatillas",
            "brand": "Nike",
            "featured": True,
        },
        {
            "sku": "ADIDAS-ULTRABOOST-22",
            "name": "Adidas Ultraboost 22",
            "description": "Zapatillas running con tecnología Boost, máxima amortiguación",
            "price": 189.99,
            "stock": 25,
            "category": "zapatillas",
            "brand": "Adidas",
            "featured": True,
        },
        {
            "sku": "NIKE-JORDAN-1-RETRO",
            "name": "Nike Air Jordan 1 Retro High",
            "description": "Icónicas zapatillas de baloncesto, edición retro clásica",
            "price": 249.99,
            "stock": 15,
            "category": "zapatillas",
            "brand": "Nike",
        },
        {
            "sku": "PUMA-RS-X",
            "name": "Puma RS-X³",
            "description": "Zapatillas con diseño futurista, tecnología RS cushioning",
            "price": 119.99,
            "stock": 20,
            "category": "zapatillas",
            "brand": "Puma",
        },
        {
            "sku": "NB-990V6",
            "name": "New Balance 990v6",
            "description": "Zapatillas premium Made in USA, máxima comodidad y durabilidad",
            "price": 199.99,
            "stock": 18,
            "category": "zapatillas",
            "brand": "New Balance",
        },
        {
            "sku": "ADIDAS-FORUM-LOW",
            "name": "Adidas Forum Low",
            "description": "Zapatillas clásicas de basketball, estilo retro urbano",
            "price": 109.99,
            "stock": 35,
            "category": "zapatillas",
            "brand": "Adidas",
        },
        {
            "sku": "NIKE-DUNK-LOW",
            "name": "Nike Dunk Low",
            "description": "Zapatillas icónicas de skateboarding, diseño versátil",
            "price": 139.99,
            "stock": 22,
            "category": "zapatillas",
            "brand": "Nike",
        },
        
        # Tablets
        {
            "sku": "IPAD-PRO-M2",
            "name": "iPad Pro 12.9\" M2",
            "description": "Tablet profesional con chip M2, 256GB, pantalla Liquid Retina XDR",
            "price": 1299.99,
            "stock": 10,
            "category": "tablets",
            "brand": "Apple",
            "featured": True,
        },
        {
            "sku": "SAMSUNG-TAB-S9-ULTRA",
            "name": "Samsung Galaxy Tab S9 Ultra",
            "description": "Tablet Android premium 14.6\", Snapdragon 8 Gen 2, 12GB RAM, S-Pen incluido",
            "price": 1199.99,
            "stock": 8,
            "category": "tablets",
            "brand": "Samsung",
        },
        
        # Gaming
        {
            "sku": "ASUS-ROG-ALLY",
            "name": "ASUS ROG Ally",
            "description": "Consola portátil gaming con AMD Z1 Extreme, 512GB SSD, Windows 11",
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
            "description": "Auriculares inalámbricos con cancelación de ruido activa, chip H2",
            "price": 249.99,
            "stock": 40,
            "category": "audio",
            "brand": "Apple",
            "featured": True,
        },
        {
            "sku": "SAMSUNG-BUDS2-PRO",
            "name": "Samsung Galaxy Buds2 Pro",
            "description": "Auriculares true wireless con ANC, sonido Hi-Fi 360",
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
            category = categories[product_data.pop("category")]
            brand = brands[product_data.pop("brand")]
            
            product = Product(
                **product_data,
                category_id=category.id,
                brand_id=brand.id,
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
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