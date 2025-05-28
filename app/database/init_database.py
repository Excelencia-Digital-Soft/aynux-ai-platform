"""
Script para inicializar la base de datos con datos de ejemplo
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

from sqlalchemy.exc import IntegrityError

from app.database import get_db_context, init_db
from app.models.database import Brand, Category, Product, Promotion, Subcategory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_categories():
    """Crea las categorías principales"""
    try:
        with get_db_context() as db:
            categories_data = [
                {
                    "name": "laptops",
                    "display_name": "Laptops",
                    "description": "Computadoras portátiles para todo tipo de uso",
                },
                {
                    "name": "desktops",
                    "display_name": "PCs de Escritorio",
                    "description": "Computadoras de escritorio y workstations",
                },
                {
                    "name": "components",
                    "display_name": "Componentes",
                    "description": "Hardware y componentes individuales",
                },
                {"name": "peripherals", "display_name": "Periféricos", "description": "Accesorios y periféricos"},
                {"name": "software", "display_name": "Software", "description": "Licencias de software y programas"},
            ]

            categories = []
            for cat_data in categories_data:
                category = Category(**cat_data)
                db.add(category)
                categories.append(category)

            db.commit()
            logger.info(f"Created {len(categories)} categories")
            return categories

    except IntegrityError as e:
        logger.warning(f"Categories may already exist: {e}")
        return []
    except Exception as e:
        logger.error(f"Error creating categories: {e}")
        return []


async def create_subcategories():
    """Crea las subcategorías"""
    try:
        with get_db_context() as db:
            # Obtener categorías existentes
            laptops_cat = db.query(Category).filter(Category.name == "laptops").first()
            desktops_cat = db.query(Category).filter(Category.name == "desktops").first()
            components_cat = db.query(Category).filter(Category.name == "components").first()

            if not laptops_cat or not desktops_cat or not components_cat:
                logger.error("Categories not found, cannot create subcategories")
                return []

            subcategories_data = [
                # Laptops
                {"name": "gaming", "display_name": "Gaming", "category_id": laptops_cat.id},
                {"name": "work", "display_name": "Trabajo", "category_id": laptops_cat.id},
                {"name": "budget", "display_name": "Económicas", "category_id": laptops_cat.id},
                {"name": "ultrabook", "display_name": "Ultrabooks", "category_id": laptops_cat.id},
                # Desktops
                {"name": "gaming", "display_name": "Gaming", "category_id": desktops_cat.id},
                {"name": "work", "display_name": "Oficina", "category_id": desktops_cat.id},
                {"name": "workstation", "display_name": "Workstation", "category_id": desktops_cat.id},
                # Components
                {"name": "cpu", "display_name": "Procesadores", "category_id": components_cat.id},
                {"name": "gpu", "display_name": "Tarjetas Gráficas", "category_id": components_cat.id},
                {"name": "ram", "display_name": "Memoria RAM", "category_id": components_cat.id},
                {"name": "storage", "display_name": "Almacenamiento", "category_id": components_cat.id},
                {"name": "motherboard", "display_name": "Motherboards", "category_id": components_cat.id},
                {"name": "psu", "display_name": "Fuentes de Poder", "category_id": components_cat.id},
            ]

            subcategories = []
            for subcat_data in subcategories_data:
                subcategory = Subcategory(**subcat_data)
                db.add(subcategory)
                subcategories.append(subcategory)

            db.commit()
            logger.info(f"Created {len(subcategories)} subcategories")
            return subcategories

    except IntegrityError as e:
        logger.warning(f"Subcategories may already exist: {e}")
        return []
    except Exception as e:
        logger.error(f"Error creating subcategories: {e}")
        return []


async def create_brands():
    """Crea las marcas"""
    try:
        with get_db_context() as db:
            brands_data = [
                {
                    "name": "ASUS",
                    "display_name": "ASUS",
                    "reputation": "premium",
                    "specialty": "gaming",
                    "warranty_years": 3,
                    "description": "Líder en hardware gaming y profesional",
                },
                {
                    "name": "MSI",
                    "display_name": "MSI",
                    "reputation": "gaming",
                    "specialty": "gaming",
                    "warranty_years": 2,
                    "description": "Especialista en equipos gaming de alto rendimiento",
                },
                {
                    "name": "Lenovo",
                    "display_name": "Lenovo",
                    "reputation": "business",
                    "specialty": "work",
                    "warranty_years": 3,
                    "description": "Soluciones empresariales y ThinkPad",
                },
                {
                    "name": "HP",
                    "display_name": "HP",
                    "reputation": "versatile",
                    "specialty": "general",
                    "warranty_years": 2,
                    "description": "Equipos versátiles para todo uso",
                },
                {
                    "name": "Dell",
                    "display_name": "Dell",
                    "reputation": "business",
                    "specialty": "work",
                    "warranty_years": 3,
                    "description": "Equipos empresariales y workstations",
                },
                {
                    "name": "Corsair",
                    "display_name": "Corsair",
                    "reputation": "premium",
                    "specialty": "components",
                    "warranty_years": 5,
                    "description": "Componentes gaming de alta calidad",
                },
                {
                    "name": "Logitech",
                    "display_name": "Logitech",
                    "reputation": "reliable",
                    "specialty": "peripherals",
                    "warranty_years": 2,
                    "description": "Periféricos de calidad profesional",
                },
                {
                    "name": "AMD",
                    "display_name": "AMD",
                    "reputation": "performance",
                    "specialty": "components",
                    "warranty_years": 3,
                    "description": "Procesadores y tarjetas gráficas",
                },
                {
                    "name": "Intel",
                    "display_name": "Intel",
                    "reputation": "reliable",
                    "specialty": "components",
                    "warranty_years": 3,
                    "description": "Líder en procesadores",
                },
                {
                    "name": "NVIDIA",
                    "display_name": "NVIDIA",
                    "reputation": "premium",
                    "specialty": "components",
                    "warranty_years": 3,
                    "description": "Tarjetas gráficas de alto rendimiento",
                },
            ]

            brands = []
            for brand_data in brands_data:
                brand = Brand(**brand_data)
                db.add(brand)
                brands.append(brand)

            db.commit()
            logger.info(f"Created {len(brands)} brands")
            return brands

    except IntegrityError as e:
        logger.warning(f"Brands may already exist: {e}")
        return []
    except Exception as e:
        logger.error(f"Error creating brands: {e}")
        return []


async def create_sample_products():
    """Crea productos de ejemplo"""
    try:
        with get_db_context() as db:
            # Obtener referencias necesarias
            laptops_cat = db.query(Category).filter(Category.name == "laptops").first()
            desktops_cat = db.query(Category).filter(Category.name == "desktops").first()
            components_cat = db.query(Category).filter(Category.name == "components").first()
            peripherals_cat = db.query(Category).filter(Category.name == "peripherals").first()

            gaming_laptop_subcat = (
                db.query(Subcategory)
                .filter(Subcategory.name == "gaming", Subcategory.category_id == laptops_cat.id)
                .first()
            )
            work_laptop_subcat = (
                db.query(Subcategory)
                .filter(Subcategory.name == "work", Subcategory.category_id == laptops_cat.id)
                .first()
            )
            budget_laptop_subcat = (
                db.query(Subcategory)
                .filter(Subcategory.name == "budget", Subcategory.category_id == laptops_cat.id)
                .first()
            )

            gaming_desktop_subcat = (
                db.query(Subcategory)
                .filter(Subcategory.name == "gaming", Subcategory.category_id == desktops_cat.id)
                .first()
            )
            work_desktop_subcat = (
                db.query(Subcategory)
                .filter(Subcategory.name == "work", Subcategory.category_id == desktops_cat.id)
                .first()
            )

            cpu_subcat = (
                db.query(Subcategory)
                .filter(Subcategory.name == "cpu", Subcategory.category_id == components_cat.id)
                .first()
            )
            gpu_subcat = (
                db.query(Subcategory)
                .filter(Subcategory.name == "gpu", Subcategory.category_id == components_cat.id)
                .first()
            )
            ram_subcat = (
                db.query(Subcategory)
                .filter(Subcategory.name == "ram", Subcategory.category_id == components_cat.id)
                .first()
            )

            # Obtener marcas
            asus_brand = db.query(Brand).filter(Brand.name == "ASUS").first()
            msi_brand = db.query(Brand).filter(Brand.name == "MSI").first()
            lenovo_brand = db.query(Brand).filter(Brand.name == "Lenovo").first()
            hp_brand = db.query(Brand).filter(Brand.name == "HP").first()
            dell_brand = db.query(Brand).filter(Brand.name == "Dell").first()
            corsair_brand = db.query(Brand).filter(Brand.name == "Corsair").first()
            logitech_brand = db.query(Brand).filter(Brand.name == "Logitech").first()
            amd_brand = db.query(Brand).filter(Brand.name == "AMD").first()
            nvidia_brand = db.query(Brand).filter(Brand.name == "NVIDIA").first()

            products_data = [
                # Gaming Laptops
                {
                    "name": "ASUS ROG Strix G15",
                    "model": "G513QM",
                    "specs": "AMD Ryzen 7 5800H, RTX 3060, 16GB RAM, 512GB SSD, 144Hz",
                    "description": "Laptop gaming de alto rendimiento con excelente relación precio-calidad",
                    "price": 1299.99,
                    "stock": 15,
                    "sku": "ASUS-ROG-G15-001",
                    "category_id": laptops_cat.id,
                    "subcategory_id": gaming_laptop_subcat.id,
                    "brand_id": asus_brand.id,
                    "featured": True,
                    "technical_specs": {
                        "cpu": "AMD Ryzen 7 5800H",
                        "gpu": "RTX 3060 6GB",
                        "ram": "16GB DDR4",
                        "storage": "512GB NVMe SSD",
                        "display": '15.6" 144Hz IPS',
                        "os": "Windows 11",
                    },
                    "features": ["RGB Keyboard", "144Hz Display", "WiFi 6", "USB-C", "HDMI 2.0"],
                },
                {
                    "name": "MSI Katana 15",
                    "model": "B13VFK",
                    "specs": "Intel i7-13620H, RTX 4050, 16GB RAM, 1TB SSD, 144Hz",
                    "description": "Laptop gaming con la última generación de procesadores Intel",
                    "price": 1099.99,
                    "stock": 8,
                    "sku": "MSI-KATANA-15-001",
                    "category_id": laptops_cat.id,
                    "subcategory_id": gaming_laptop_subcat.id,
                    "brand_id": msi_brand.id,
                    "technical_specs": {
                        "cpu": "Intel i7-13620H",
                        "gpu": "RTX 4050 6GB",
                        "ram": "16GB DDR4",
                        "storage": "1TB NVMe SSD",
                        "display": '15.6" 144Hz',
                        "os": "Windows 11",
                    },
                },
                # Work Laptops
                {
                    "name": "Lenovo ThinkPad E15",
                    "model": "Gen 4",
                    "specs": "Intel i5-1235U, Intel Iris Xe, 8GB RAM, 256GB SSD",
                    "description": "Laptop empresarial confiable y duradera",
                    "price": 699.99,
                    "stock": 25,
                    "sku": "LEN-TP-E15-001",
                    "category_id": laptops_cat.id,
                    "subcategory_id": work_laptop_subcat.id,
                    "brand_id": lenovo_brand.id,
                    "technical_specs": {
                        "cpu": "Intel i5-1235U",
                        "gpu": "Intel Iris Xe",
                        "ram": "8GB DDR4",
                        "storage": "256GB SSD",
                        "display": '15.6" Full HD',
                        "os": "Windows 11 Pro",
                    },
                },
                {
                    "name": "HP ProBook 450 G9",
                    "model": "G9",
                    "specs": "Intel i7-1255U, Intel Iris Xe, 16GB RAM, 512GB SSD",
                    "description": "Laptop profesional con excelente autonomía",
                    "price": 899.99,
                    "stock": 18,
                    "sku": "HP-PB450-G9-001",
                    "category_id": laptops_cat.id,
                    "subcategory_id": work_laptop_subcat.id,
                    "brand_id": hp_brand.id,
                },
                {
                    "name": "Dell Latitude 3420",
                    "model": "G6",
                    "specs": "Intel i5-1135G7, Intel Iris Xe, 8GB RAM, 256GB SSD",
                    "description": "Laptop de escritorio con una solución de procesamiento avanzada",
                    "price": 1199.99,
                    "stock": 2,
                    "sku": "DELL-LAT3420-G6-001",
                    "category_id": laptops_cat.id,
                    "subcategory_id": work_laptop_subcat.id,
                    "brand_id": dell_brand.id,
                },
                # Budget Laptops
                {
                    "name": "ASUS VivoBook 15",
                    "model": "X515EA",
                    "specs": "AMD Ryzen 5 5500U, Radeon Graphics, 8GB RAM, 256GB SSD",
                    "description": "Laptop económica perfecta para uso diario",
                    "price": 449.99,
                    "stock": 30,
                    "sku": "ASUS-VB15-001",
                    "category_id": laptops_cat.id,
                    "subcategory_id": budget_laptop_subcat.id,
                    "brand_id": asus_brand.id,
                },
                # Gaming Desktops
                {
                    "name": "Gaming PC RTX 4070",
                    "model": "Custom Build",
                    "specs": "AMD Ryzen 5 7600X, RTX 4070, 16GB DDR5, 1TB NVMe SSD",
                    "description": "PC gaming de alta gama para juegos 4K",
                    "price": 1599.99,
                    "stock": 10,
                    "sku": "GAMING-PC-4070-001",
                    "category_id": desktops_cat.id,
                    "subcategory_id": gaming_desktop_subcat.id,
                    "featured": True,
                    "technical_specs": {
                        "cpu": "AMD Ryzen 5 7600X",
                        "gpu": "RTX 4070 12GB",
                        "ram": "16GB DDR5-5600",
                        "storage": "1TB NVMe SSD",
                        "psu": "750W 80+ Gold",
                        "case": "Mid Tower RGB",
                    },
                },
                # Work Desktops
                {
                    "name": "Office PC Standard",
                    "model": "Business Series",
                    "specs": "Intel i5-13400, Intel UHD 730, 16GB DDR4, 512GB SSD",
                    "description": "PC de oficina confiable y eficiente",
                    "price": 649.99,
                    "stock": 20,
                    "sku": "OFFICE-PC-STD-001",
                    "category_id": desktops_cat.id,
                    "subcategory_id": work_desktop_subcat.id,
                },
                # Components
                {
                    "name": "AMD Ryzen 5 7600X",
                    "model": "7600X",
                    "specs": "6 cores, 12 threads, 4.7GHz boost, AM5 socket",
                    "description": "Procesador gaming de última generación",
                    "price": 249.99,
                    "stock": 15,
                    "sku": "AMD-R5-7600X-001",
                    "category_id": components_cat.id,
                    "subcategory_id": cpu_subcat.id,
                    "brand_id": amd_brand.id,
                },
                {
                    "name": "RTX 4060 Ti",
                    "model": "4060 Ti 16GB",
                    "specs": "16GB VRAM, DLSS 3, Ray Tracing, PCIe 4.0",
                    "description": "Tarjeta gráfica ideal para gaming 1440p",
                    "price": 499.99,
                    "stock": 8,
                    "sku": "RTX-4060TI-16GB-001",
                    "category_id": components_cat.id,
                    "subcategory_id": gpu_subcat.id,
                    "brand_id": nvidia_brand.id,
                    "on_sale": True,
                },
                {
                    "name": "Corsair Vengeance LPX 16GB",
                    "model": "CMK16GX4M2B3200C16",
                    "specs": "DDR4-3200, 2x8GB kit, CL16, Black",
                    "description": "Memoria RAM de alto rendimiento",
                    "price": 79.99,
                    "stock": 25,
                    "sku": "CORS-VEN-16GB-001",
                    "category_id": components_cat.id,
                    "subcategory_id": ram_subcat.id,
                    "brand_id": corsair_brand.id,
                },
                # Peripherals
                {
                    "name": "Logitech G Pro X Superlight",
                    "model": "G Pro X",
                    "specs": "Gaming mouse, 25,600 DPI, wireless, 63g",
                    "description": "Mouse gaming profesional ultra ligero",
                    "price": 149.99,
                    "stock": 20,
                    "sku": "LOG-GPRO-SL-001",
                    "category_id": peripherals_cat.id,
                    "brand_id": logitech_brand.id,
                },
                {
                    "name": "Corsair K70 RGB MK.2",
                    "model": "K70 MK.2",
                    "specs": "Mechanical keyboard, Cherry MX switches, RGB backlight",
                    "description": "Teclado mecánico gaming premium",
                    "price": 169.99,
                    "stock": 18,
                    "sku": "CORS-K70-RGB-001",
                    "category_id": peripherals_cat.id,
                    "brand_id": corsair_brand.id,
                },
            ]

            products = []
            for product_data in products_data:
                product = Product(**product_data)
                db.add(product)
                products.append(product)

            db.commit()
            logger.info(f"Created {len(products)} sample products")
            return products

    except Exception as e:
        logger.error(f"Error creating sample products: {e}")
        return []


async def create_sample_promotions():
    """Crea promociones de ejemplo"""
    try:
        with get_db_context() as db:
            # Obtener algunos productos para las promociones
            gaming_products = db.query(Product).join(Subcategory).filter(Subcategory.name == "gaming").limit(3).all()

            promotions_data = [
                {
                    "name": "Combo Gaming Completo",
                    "description": "Descuento especial en equipos gaming",
                    "discount_percentage": 15.0,
                    "promo_code": "GAMING2025",
                    "valid_until": datetime.now(timezone.utc) + timedelta(days=30),
                    "min_purchase_amount": 1000.0,
                    "applicable_categories": ["laptops", "desktops"],
                    "max_uses": 50,
                },
                {
                    "name": "Paquete Oficina Pro",
                    "description": "Descuento en equipos empresariales",
                    "discount_percentage": 10.0,
                    "promo_code": "OFFICE2025",
                    "valid_until": datetime.now(timezone.utc) + timedelta(days=45),
                    "min_purchase_amount": 500.0,
                    "applicable_categories": ["laptops", "desktops"],
                    "max_uses": 100,
                },
                {
                    "name": "Black Friday Tech",
                    "description": "Mega descuentos en componentes",
                    "discount_percentage": 25.0,
                    "promo_code": "BLACKFRI25",
                    "valid_until": datetime.now(timezone.utc) + timedelta(days=7),
                    "applicable_categories": ["components", "peripherals"],
                    "max_uses": 200,
                },
            ]

            promotions = []
            for promo_data in promotions_data:
                promotion = Promotion(**promo_data)
                db.add(promotion)

                # Asociar productos gaming con la primera promoción
                if promotion.name.name == "Combo Gaming Completo" and len(gaming_products) > 0:
                    promotion.products.extend(gaming_products[:2])

                promotions.append(promotion)

            db.commit()
            logger.info(f"Created {len(promotions)} sample promotions")
            return promotions

    except Exception as e:
        logger.error(f"Error creating sample promotions: {e}")
        return []


async def main():
    """Función principal para inicializar la base de datos"""
    try:
        logger.info("Starting database initialization...")

        # Crear tablas
        await init_db()
        logger.info("Database tables created successfully")

        # Crear datos de ejemplo
        categories = await create_categories()
        subcategories = await create_subcategories()
        brands = await create_brands()
        products = await create_sample_products()
        promotions = await create_sample_promotions()

        logger.info("Database initialization completed successfully!")
        logger.info("Summary:")
        logger.info(f"- Categories: {len(categories) if categories else 'Already exist'}")
        logger.info(f"- Subcategories: {len(subcategories) if subcategories else 'Already exist'}")
        logger.info(f"- Brands: {len(brands) if brands else 'Already exist'}")
        logger.info(f"- Products: {len(products) if products else 'Already exist'}")
        logger.info(f"- Promotions: {len(promotions) if promotions else 'Already exist'}")

    except Exception as e:
        logger.error(f"Error during database initialization: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
