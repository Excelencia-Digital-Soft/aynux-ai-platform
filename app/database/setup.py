"""
Database Setup - Scripts de inicialización y configuración de la base de datos.

Este módulo contiene todas las funciones necesarias para configurar, inicializar
y poblar la base de datos con datos de ejemplo.
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import get_settings
from app.models.db import (
    Brand,
    Category,
    Conversation,
    Customer,
    Product,
    ProductAttribute,
    ProductImage,
    ProductReview,
)
from app.models.db.base import Base
from app.models.db.conversation import ConversationMessage
from app.models.db.orders import Order, OrderItem

logger = logging.getLogger(__name__)


def create_search_trigger() -> str:
    """Crea el trigger para actualización automática del search_vector."""
    return """
    CREATE OR REPLACE FUNCTION update_search_vector() RETURNS TRIGGER AS $$
    BEGIN
        NEW.search_vector := setweight(to_tsvector('spanish', coalesce(NEW.name, '')), 'A') ||
                           setweight(to_tsvector('spanish', coalesce(NEW.description, '')), 'B') ||
                           setweight(to_tsvector('spanish', coalesce(NEW.short_description, '')), 'C');
        RETURN NEW;
    END
    $$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS tsvector_update_trigger ON products;
    CREATE TRIGGER tsvector_update_trigger
        BEFORE INSERT OR UPDATE ON products
        FOR EACH ROW EXECUTE FUNCTION update_search_vector();
    """


def create_indexes() -> str:
    """Crea índices adicionales para mejorar el rendimiento."""
    return """
    CREATE INDEX IF NOT EXISTS idx_products_search_gin ON products USING gin(search_vector);
    CREATE INDEX IF NOT EXISTS idx_products_name_trgm ON products USING gin(name gin_trgm_ops);
    CREATE INDEX IF NOT EXISTS idx_products_description_trgm ON products USING gin(description gin_trgm_ops);
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    """


class DatabaseSetup:
    """Clase para manejar la configuración de la base de datos."""

    def __init__(self):
        self.settings = get_settings()
        self.engine = create_async_engine(self.settings.database_config)
        self.async_session = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    async def create_tables(self) -> None:
        """Crea todas las tablas en la base de datos."""
        try:
            async with self.engine.begin() as conn:
                logger.info("Creando tablas...")
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Tablas creadas exitosamente")
        except Exception as e:
            logger.error(f"Error creando tablas: {e}")
            raise

    async def drop_tables(self) -> None:
        """Elimina todas las tablas de la base de datos."""
        try:
            async with self.engine.begin() as conn:
                logger.info("Eliminando tablas...")
                await conn.run_sync(Base.metadata.drop_all)
                logger.info("Tablas eliminadas exitosamente")
        except Exception as e:
            logger.error(f"Error eliminando tablas: {e}")
            raise

    async def setup_extensions(self) -> None:
        """Configura extensiones de PostgreSQL necesarias."""
        try:
            async with self.engine.begin() as conn:
                logger.info("Configurando extensiones de PostgreSQL...")

                extensions = [
                    "CREATE EXTENSION IF NOT EXISTS pg_trgm;",
                    "CREATE EXTENSION IF NOT EXISTS btree_gin;",
                    "CREATE EXTENSION IF NOT EXISTS uuid-ossp;",
                ]

                for extension in extensions:
                    await conn.execute(text(extension))

                logger.info("Extensiones configuradas exitosamente")
        except Exception as e:
            logger.error(f"Error configurando extensiones: {e}")
            raise

    async def setup_search_features(self) -> None:
        """Configura funciones de búsqueda full-text."""
        try:
            async with self.engine.begin() as conn:
                logger.info("Configurando funciones de búsqueda...")

                # Crear trigger de búsqueda
                await conn.execute(text(create_search_trigger()))

                # Crear índices adicionales
                await conn.execute(text(create_indexes()))

                logger.info("Funciones de búsqueda configuradas exitosamente")
        except Exception as e:
            logger.error(f"Error configurando búsqueda: {e}")
            raise

    async def populate_sample_data(self) -> None:
        """Puebla la base de datos con datos de ejemplo."""
        try:
            session = self.async_session()
            async with session:
                logger.info("Poblando datos de ejemplo...")

                # Crear categorías
                categories = await self._create_sample_categories(session)

                # Crear marcas
                brands = await self._create_sample_brands(session)

                # Crear productos
                products = await self._create_sample_products(session, categories, brands)

                # Crear clientes
                customers = await self._create_sample_customers(session)

                # Crear órdenes
                orders = await self._create_sample_orders(session, customers, products)

                # Crear conversaciones
                await self._create_sample_conversations(session, customers)

                # Crear reseñas
                await self._create_sample_reviews(session, customers, products)

                await session.commit()
                logger.info("Datos de ejemplo creados exitosamente")

        except Exception as e:
            logger.error(f"Error poblando datos: {e}")
            raise

    async def _create_sample_categories(self, session: AsyncSession) -> List[Category]:
        """Crea categorías de ejemplo."""
        categories_data = [
            {
                "name": "electronics",
                "display_name": "Electrónicos",
                "description": "Dispositivos electrónicos y tecnología",
            },
            {"name": "clothing", "display_name": "Ropa", "description": "Ropa y accesorios"},
            {"name": "home", "display_name": "Hogar", "description": "Artículos para el hogar"},
            {"name": "sports", "display_name": "Deportes", "description": "Artículos deportivos y fitness"},
            {"name": "books", "display_name": "Libros", "description": "Libros y material educativo"},
            {"name": "beauty", "display_name": "Belleza", "description": "Productos de belleza y cuidado personal"},
            {"name": "automotive", "display_name": "Automotriz", "description": "Accesorios y partes para vehículos"},
        ]

        categories = []
        for cat_data in categories_data:
            category = Category(**cat_data)
            session.add(category)
            categories.append(category)

        await session.flush()

        # Crear subcategorías
        subcategories_data = [
            {"name": "smartphones", "display_name": "Smartphones", "parent": "electronics"},
            {"name": "laptops", "display_name": "Laptops", "parent": "electronics"},
            {"name": "headphones", "display_name": "Auriculares", "parent": "electronics"},
            {"name": "shirts", "display_name": "Camisas", "parent": "clothing"},
            {"name": "shoes", "display_name": "Zapatos", "parent": "clothing"},
            {"name": "furniture", "display_name": "Muebles", "parent": "home"},
            {"name": "kitchen", "display_name": "Cocina", "parent": "home"},
        ]

        parent_map = {cat.name: cat for cat in categories}

        for subcat_data in subcategories_data:
            parent_name = subcat_data.pop("parent")
            parent = parent_map.get(parent_name)
            if parent:
                subcategory = Category(**subcat_data, parent_id=parent.id)
                session.add(subcategory)
                categories.append(subcategory)

        await session.flush()
        return categories

    async def _create_sample_brands(self, session: AsyncSession) -> List[Brand]:
        """Crea marcas de ejemplo."""
        brands_data = [
            {"name": "Apple", "description": "Tecnología innovadora"},
            {"name": "Samsung", "description": "Electrónicos de calidad"},
            {"name": "Nike", "description": "Ropa y calzado deportivo"},
            {"name": "Adidas", "description": "Artículos deportivos"},
            {"name": "Sony", "description": "Electrónicos y entretenimiento"},
            {"name": "Dell", "description": "Computadoras y tecnología"},
            {"name": "HP", "description": "Tecnología para todos"},
            {"name": "Zara", "description": "Moda contemporánea"},
            {"name": "IKEA", "description": "Muebles y decoración"},
            {"name": "Xiaomi", "description": "Tecnología accesible"},
        ]

        brands = []
        for brand_data in brands_data:
            brand = Brand(**brand_data)
            session.add(brand)
            brands.append(brand)

        await session.flush()
        return brands

    async def _create_sample_products(
        self, session: AsyncSession, categories: List[Category], brands: List[Brand]
    ) -> List[Product]:
        """Crea productos de ejemplo."""

        # Mapear categorías y marcas por nombre
        category_map = {cat.name: cat for cat in categories}
        brand_map = {brand.name: brand for brand in brands}

        products_data = [
            # Electrónicos
            {
                "name": "iPhone 15 Pro",
                "description": "El iPhone más avanzado con tecnología de punta",
                "short_description": "Smartphone premium con cámara profesional",
                "model": "A2848",
                "sku": "IP15PRO-128",
                "price": Decimal("999.99"),
                "stock": 50,
                "category": "smartphones",
                "brand": "Apple",
                "featured": True,
                "attributes": [
                    {"name": "color", "value": "Natural Titanium"},
                    {"name": "storage", "value": "128GB"},
                    {"name": "screen_size", "value": "6.1 inches"},
                ],
            },
            {
                "name": "Galaxy S24 Ultra",
                "description": "Smartphone Android con S Pen integrado",
                "short_description": "Smartphone con stylus y cámara de 200MP",
                "model": "SM-S928",
                "sku": "GS24U-256",
                "price": Decimal("899.99"),
                "stock": 35,
                "category": "smartphones",
                "brand": "Samsung",
                "attributes": [
                    {"name": "color", "value": "Phantom Black"},
                    {"name": "storage", "value": "256GB"},
                    {"name": "screen_size", "value": "6.8 inches"},
                ],
            },
            {
                "name": "MacBook Pro 14",
                "description": "Laptop profesional con chip M3",
                "short_description": "Laptop para profesionales creativos",
                "model": "MTMR3",
                "sku": "MBP14-M3-512",
                "price": Decimal("1999.99"),
                "stock": 25,
                "category": "laptops",
                "brand": "Apple",
                "attributes": [
                    {"name": "processor", "value": "Apple M3"},
                    {"name": "ram", "value": "16GB"},
                    {"name": "storage", "value": "512GB SSD"},
                ],
            },
            {
                "name": "Dell XPS 13",
                "description": "Ultrabook compacto con pantalla InfinityEdge",
                "short_description": "Ultrabook premium para productividad",
                "model": "XPS13-9340",
                "sku": "DELL-XPS13-512",
                "price": Decimal("1299.99"),
                "stock": 40,
                "category": "laptops",
                "brand": "Dell",
                "attributes": [
                    {"name": "processor", "value": "Intel Core i7"},
                    {"name": "ram", "value": "16GB"},
                    {"name": "storage", "value": "512GB SSD"},
                ],
            },
            {
                "name": "AirPods Pro 2",
                "description": "Auriculares inalámbricos con cancelación de ruido",
                "short_description": "Auriculares premium con ANC",
                "model": "MTJV3",
                "sku": "APP2-USB-C",
                "price": Decimal("249.99"),
                "stock": 100,
                "category": "headphones",
                "brand": "Apple",
                "on_sale": True,
                "original_price": Decimal("279.99"),
                "attributes": [
                    {"name": "connectivity", "value": "Bluetooth 5.3"},
                    {"name": "battery_life", "value": "6 hours + 24 hours case"},
                    {"name": "features", "value": "Active Noise Cancellation"},
                ],
            },
            # Ropa
            {
                "name": "Air Jordan 1 Retro High",
                "description": "Zapatillas icónicas de basketball",
                "short_description": "Sneakers clásicos de Michael Jordan",
                "model": "AJ1-RH",
                "sku": "AJ1-RH-42",
                "price": Decimal("170.00"),
                "stock": 60,
                "category": "shoes",
                "brand": "Nike",
                "attributes": [
                    {"name": "size", "value": "42"},
                    {"name": "color", "value": "Chicago Red/White"},
                    {"name": "material", "value": "Genuine Leather"},
                ],
            },
            {
                "name": "Ultraboost 22",
                "description": "Zapatillas de running con tecnología Boost",
                "short_description": "Zapatillas para correr con máximo confort",
                "model": "UB22",
                "sku": "UB22-41",
                "price": Decimal("180.00"),
                "stock": 45,
                "category": "shoes",
                "brand": "Adidas",
                "attributes": [
                    {"name": "size", "value": "41"},
                    {"name": "color", "value": "Core Black"},
                    {"name": "technology", "value": "Boost midsole"},
                ],
            },
            # Hogar
            {
                "name": "BILLY Estantería",
                "description": "Estantería de pino macizo, natural",
                "short_description": "Estantería versátil para cualquier habitación",
                "model": "BILLY-80",
                "sku": "IKEA-BILLY-80",
                "price": Decimal("59.99"),
                "stock": 30,
                "category": "furniture",
                "brand": "IKEA",
                "attributes": [
                    {"name": "material", "value": "Pine wood"},
                    {"name": "dimensions", "value": "80x28x202 cm"},
                    {"name": "shelves", "value": "5 adjustable shelves"},
                ],
            },
        ]

        products = []
        for product_data in products_data:
            # Extraer datos especiales
            attributes_data = product_data.pop("attributes", [])
            category_name = product_data.pop("category")
            brand_name = product_data.pop("brand")

            # Obtener referencias
            category = category_map.get(category_name)
            brand = brand_map.get(brand_name)

            # Crear producto
            product = Product(
                **product_data, category_id=category.id if category else None, brand_id=brand.id if brand else None
            )
            session.add(product)
            await session.flush()  # Para obtener el ID

            # Crear atributos
            for attr_data in attributes_data:
                attribute = ProductAttribute(product_id=product.id, **attr_data)
                session.add(attribute)

            # Crear imagen de ejemplo
            image = ProductImage(
                product_id=product.id,
                url=f"https://example.com/images/{product.sku}.jpg",
                alt_text=f"Imagen de {product.name}",
                is_primary=True,
            )
            session.add(image)

            products.append(product)

        await session.flush()
        return products

    async def _create_sample_customers(self, session: AsyncSession) -> List[Customer]:
        """Crea clientes de ejemplo."""
        customers_data = [
            {
                "phone_number": "+1234567890",
                "email": "juan.perez@email.com",
                "first_name": "Juan",
                "last_name": "Pérez",
                "preferences": {"language": "es", "notifications": True},
            },
            {
                "phone_number": "+1234567891",
                "email": "maria.garcia@email.com",
                "first_name": "María",
                "last_name": "García",
                "preferences": {"language": "es", "notifications": False},
            },
            {
                "phone_number": "+1234567892",
                "email": "carlos.rodriguez@email.com",
                "first_name": "Carlos",
                "last_name": "Rodríguez",
                "preferences": {"language": "es", "notifications": True},
            },
            {
                "phone_number": "+1234567893",
                "first_name": "Ana",
                "last_name": "López",
                "preferences": {"language": "es", "notifications": True},
            },
            {
                "phone_number": "+1234567894",
                "email": "diego.martinez@email.com",
                "first_name": "Diego",
                "last_name": "Martínez",
                "preferences": {"language": "es", "notifications": False},
            },
        ]

        customers = []
        for customer_data in customers_data:
            customer = Customer(**customer_data)
            session.add(customer)
            customers.append(customer)

        await session.flush()
        return customers

    async def _create_sample_orders(
        self, session: AsyncSession, customers: List[Customer], products: List[Product]
    ) -> List[Order]:
        """Crea órdenes de ejemplo."""
        orders = []

        for i, customer in enumerate(customers[:3]):  # Solo primeros 3 clientes
            # Crear 1-3 órdenes por cliente
            num_orders = random.randint(1, 3)

            for j in range(num_orders):
                order_number = f"ORD-{datetime.now().year}-{(i + 1):03d}-{(j + 1):02d}"

                order: Order = Order(
                    order_number=order_number,
                    customer_id=customer.id,
                    status=random.choice(["pending", "confirmed", "shipped", "delivered"]),
                    order_date=datetime.now() - timedelta(days=random.randint(1, 30)),
                    subtotal=0.0,
                    total_amount=0.0,
                    shipping_address={
                        "street": "Calle Principal 123",
                        "city": "Ciudad",
                        "country": "AR",
                        "postal_code": "1000",
                    },
                )
                session.add(order)
                await session.flush()

                # Agregar 1-4 items por orden
                num_items = random.randint(1, 4)
                selected_products = random.sample(products, min(num_items, len(products)))

                subtotal = Decimal("0")

                for product in selected_products:
                    quantity = random.randint(1, 3)
                    unit_price = product.price
                    total_price = unit_price * quantity

                    order_item = OrderItem(
                        order_id=order.id,
                        product_id=product.id,
                        quantity=quantity,
                        unit_price=unit_price,
                        total_price=total_price,
                        product_name=product.name,
                        product_sku=product.sku,
                    )
                    session.add(order_item)
                    subtotal += total_price

                # Actualizar totales
                order.subtotal = float(subtotal)  # type: ignore
                order.tax_amount = float(subtotal * Decimal("0.21"))  # 21% IVA # type: ignore
                order.shipping_amount = 10.0 if subtotal < 100 else 0.0  # type: ignore
                order.total_amount = order.subtotal + order.tax_amount + order.shipping_amount  # type: ignore

                orders.append(order)

        await session.flush()
        return orders

    async def _create_sample_conversations(self, session: AsyncSession, customers: List[Customer]) -> None:
        """Crea conversaciones de ejemplo."""
        sample_conversations = [
            {
                "customer": customers[0],
                "messages": [
                    {"content": "Hola, busco un smartphone nuevo", "sender_type": "customer"},
                    {
                        "content": "¡Hola! Te puedo ayudar a encontrar el smartphone perfecto. ¿Qué características buscas?",
                        "sender_type": "agent",
                        "agent_name": "smart_product_agent",
                    },
                    {"content": "Algo con buena cámara y que no sea muy caro", "sender_type": "customer"},
                    {
                        "content": "Te recomiendo el Galaxy S24 Ultra que tenemos en oferta por $899.99. Tiene una cámara de 200MP excelente.",
                        "sender_type": "agent",
                        "agent_name": "smart_product_agent",
                    },
                ],
            },
            {
                "customer": customers[1],
                "messages": [
                    {"content": "¿Tienen zapatillas Nike?", "sender_type": "customer"},
                    {
                        "content": "¡Sí! Tenemos varios modelos de Nike. Los Air Jordan 1 Retro High están muy populares.",
                        "sender_type": "agent",
                        "agent_name": "smart_product_agent",
                    },
                    {"content": "¿Cuánto cuestan?", "sender_type": "customer"},
                    {
                        "content": "Los Air Jordan 1 cuestan $170.00 y tenemos stock disponible en varias tallas.",
                        "sender_type": "agent",
                        "agent_name": "smart_product_agent",
                    },
                ],
            },
        ]

        for conv_data in sample_conversations:
            conversation = Conversation(customer_id=conv_data["customer"].id, channel="whatsapp", status="closed")
            session.add(conversation)
            await session.flush()

            for i, msg_data in enumerate(conv_data["messages"]):
                message = ConversationMessage(
                    conversation_id=conversation.id,
                    **msg_data,
                    created_at=datetime.now() - timedelta(minutes=len(conv_data["messages"]) - i),
                )
                session.add(message)

    async def _create_sample_reviews(
        self, session: AsyncSession, customers: List[Customer], products: List[Product]
    ) -> None:
        """Crea reseñas de ejemplo."""
        reviews_data = [
            {
                "customer": customers[0],
                "product": products[0],  # iPhone 15 Pro
                "rating": 5,
                "title": "Excelente teléfono",
                "comment": "La cámara es increíble y el rendimiento es súper fluido. Muy recomendado.",
                "is_verified": True,
            },
            {
                "customer": customers[1],
                "product": products[4],  # AirPods Pro 2
                "rating": 4,
                "title": "Buenos auriculares",
                "comment": "La cancelación de ruido funciona muy bien, aunque la batería podría durar más.",
                "is_verified": True,
            },
            {
                "customer": customers[2],
                "product": products[5],  # Air Jordan 1
                "rating": 5,
                "title": "Clásicos atemporales",
                "comment": "Calidad premium y diseño icónico. Vale cada peso.",
                "is_verified": False,
            },
        ]

        for review_data in reviews_data:
            customer = review_data.pop("customer")
            product = review_data.pop("product")

            review = ProductReview(customer_id=customer.id, product_id=product.id, **review_data)
            session.add(review)


# Funciones principales para uso externo


async def initialize_database():
    """Inicializa completamente la base de datos."""
    setup = DatabaseSetup()

    try:
        logger.info("Iniciando configuración de base de datos...")

        # Configurar extensiones
        await setup.setup_extensions()

        # Crear tablas
        await setup.create_tables()

        # Configurar búsqueda
        await setup.setup_search_features()

        # Poblar datos de ejemplo
        await setup.populate_sample_data()

        logger.info("Base de datos inicializada exitosamente")

    except Exception as e:
        logger.error(f"Error inicializando base de datos: {e}")
        raise


async def reset_database():
    """Resetea completamente la base de datos."""
    setup = DatabaseSetup()

    try:
        logger.info("Reseteando base de datos...")

        # Eliminar tablas existentes
        await setup.drop_tables()

        # Inicializar desde cero
        await initialize_database()

        logger.info("Base de datos reseteada exitosamente")

    except Exception as e:
        logger.error(f"Error reseteando base de datos: {e}")
        raise


if __name__ == "__main__":
    # Script principal para ejecutar desde línea de comandos
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "init":
            asyncio.run(initialize_database())
        elif command == "reset":
            asyncio.run(reset_database())
        else:
            print("Comandos disponibles: init, reset")
    else:
        print("Uso: python database_setup.py [init|reset]")
