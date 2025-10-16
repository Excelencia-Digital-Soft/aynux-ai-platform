import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, relationship
from pgvector.sqlalchemy import Vector

Base = declarative_base()

# Tabla de asociación para productos y promociones (many-to-many)
product_promotion_association = Table(
    "product_promotions",
    Base.metadata,
    Column("product_id", UUID(as_uuid=True), ForeignKey("products.id")),
    Column("promotion_id", UUID(as_uuid=True), ForeignKey("promotions.id")),
)


class TimestampMixin:
    """Mixin para agregar timestamps automáticos."""

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class Category(Base, TimestampMixin):
    """Categorías de productos (Laptops, Desktops, Components, etc.)"""

    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(200), nullable=False)
    description = Column(Text)
    active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)

    # Metadatos adicionales
    meta_data = Column(JSONB, default=dict)

    # Relationships
    subcategories: Mapped[List["Subcategory"]] = relationship("Subcategory", back_populates="category")
    products: Mapped[List["Product"]] = relationship("Product", back_populates="category")

    # Índices
    __table_args__ = (
        Index("idx_categories_active", active),
        Index("idx_categories_sort", sort_order),
    )


class Subcategory(Base, TimestampMixin):
    """Subcategorías (Gaming, Work, Budget, etc.)"""

    __tablename__ = "subcategories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)  # gaming, work, budget
    display_name = Column(String(200), nullable=False)  # Gaming, Trabajo, Económicas
    description = Column(Text)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    active = Column(Boolean, default=True)

    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="subcategories")
    products: Mapped[List["Product"]] = relationship("Product", back_populates="subcategory")


class Brand(Base, TimestampMixin):
    """Marcas de productos"""

    __tablename__ = "brands"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)  # ASUS, MSI, Lenovo
    display_name = Column(String(200), nullable=False)
    reputation = Column(String(50))  # premium, gaming, business, reliable
    specialty = Column(String(100))  # gaming, work, components
    warranty_years = Column(Integer, default=2)
    description = Column(Text)
    active = Column(Boolean, default=True)

    # Metadatos adicionales
    meta_data = Column(JSONB, default=dict)

    # Relationships
    products: Mapped[List["Product"]] = relationship("Product", back_populates="brand")

    # Índices
    __table_args__ = (
        Index("idx_brands_active", active),
        Index("idx_brands_name_trgm", name, postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}),
    )


class Product(Base, TimestampMixin):
    """Productos principales"""

    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    model = Column(String(100))  # ROG Strix G15, Katana 15, etc.
    specs = Column(Text, nullable=False)  # Especificaciones técnicas
    description = Column(Text)  # Descripción detallada
    short_description = Column(String(500), nullable=True)
    price = Column(Float, nullable=False, index=True)
    original_price = Column(Float)  # Para tracking de descuentos
    cost_price = Column(Numeric(10, 2))  # Para análisis de márgenes
    stock = Column(Integer, default=0, index=True)
    min_stock = Column(Integer, default=5)  # Alerta de stock bajo
    sku = Column(String(50), unique=True, index=True)  # Código de producto

    # Foreign Keys
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    subcategory_id = Column(UUID(as_uuid=True), ForeignKey("subcategories.id"))
    brand_id = Column(UUID(as_uuid=True), ForeignKey("brands.id"))

    # Product details as JSONB for flexibility
    technical_specs = Column(JSONB)  # {"cpu": "i7", "ram": "16GB", "storage": "512GB SSD"}
    features = Column(JSONB)  # ["RGB Keyboard", "144Hz Display", "WiFi 6"]
    images = Column(JSONB)  # ["url1", "url2", "url3"]

    # Status and metadata
    active = Column(Boolean, default=True, index=True)
    featured = Column(Boolean, default=False, index=True)  # Productos destacados
    on_sale = Column(Boolean, default=False, index=True)  # En oferta
    weight = Column(Float)  # Para shipping
    dimensions = Column(JSONB)  # {"width": 35, "height": 25, "depth": 2}

    # Campos para búsqueda full-text
    search_vector = Column(TSVECTOR)

    # Campos para búsqueda semántica con pgvector
    embedding = Column(Vector(1024))  # Vector embedding for semantic search (nomic-embed-text)
    last_embedding_update = Column(DateTime)  # Timestamp of last embedding generation
    embedding_model = Column(String(100), default="nomic-embed-text")  # Model used for embeddings
    embedding_version = Column(Integer, default=1)  # Version for cache invalidation

    # Metadatos adicionales
    meta_data = Column(JSONB, default=dict)

    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="products")
    subcategory: Mapped[Optional["Subcategory"]] = relationship("Subcategory", back_populates="products")
    brand: Mapped[Optional["Brand"]] = relationship("Brand", back_populates="products")
    attributes: Mapped[List["ProductAttribute"]] = relationship(
        "ProductAttribute", back_populates="product", cascade="all, delete-orphan"
    )
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    promotions: Mapped[List["Promotion"]] = relationship(
        "Promotion", secondary=product_promotion_association, back_populates="products"
    )
    reviews: Mapped[List["ProductReview"]] = relationship("ProductReview", back_populates="product")

    # Índices
    __table_args__ = (
        Index("idx_products_active", active),
        Index("idx_products_featured", featured),
        Index("idx_products_sale", on_sale),
        Index("idx_products_stock", stock),
        Index("idx_products_price", price),
        Index("idx_products_category", category_id),
        Index("idx_products_brand", brand_id),
        Index("idx_products_search", search_vector, postgresql_using="gin"),
        Index("idx_products_name_trgm", name, postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}),
        Index(
            "idx_products_description_trgm",
            description,
            postgresql_using="gin",
            postgresql_ops={"description": "gin_trgm_ops"},
        ),
        CheckConstraint("price >= 0", name="check_price_positive"),
        CheckConstraint("stock >= 0", name="check_stock_non_negative"),
    )

    def __repr__(self):
        return f"<Product(name='{self.name}', price={self.price}, stock={self.stock})>"

    @property
    def is_in_stock(self) -> bool:
        """Verifica si el producto está en stock."""
        return self.stock > 0  # type: ignore

    @property
    def is_low_stock(self) -> bool:
        """Verifica si el producto está con stock bajo."""
        return self.stock <= self.min_stock  # type: ignore

    @property
    def discount_percentage(self) -> Optional[float]:
        """Calcula el porcentaje de descuento si aplica."""
        if self.original_price and self.original_price > self.price:  # type: ignore
            return ((self.original_price - self.price) / self.original_price) * 100  # type: ignore
        return None


class ProductAttribute(Base, TimestampMixin):
    """Atributos adicionales de productos (color, talla, etc.)."""

    __tablename__ = "product_attributes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    name = Column(String(100), nullable=False)
    value = Column(String(500), nullable=False)
    attribute_type = Column(String(50), default="text")  # text, number, boolean, json
    is_searchable = Column(Boolean, default=True)

    # Relaciones
    product = relationship("Product", back_populates="attributes")

    # Índices
    __table_args__ = (
        Index("idx_product_attributes_product", product_id),
        Index("idx_product_attributes_name", name),
        Index("idx_product_attributes_searchable", is_searchable),
        UniqueConstraint("product_id", "name", name="uq_product_attribute_name"),
    )

    def __repr__(self):
        return f"<ProductAttribute(name='{self.name}', value='{self.value}')>"


class ProductImage(Base, TimestampMixin):
    """Imágenes de productos."""

    __tablename__ = "product_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    url = Column(String(1000), nullable=False)
    alt_text = Column(String(200))
    is_primary = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)

    # Relaciones
    product = relationship("Product", back_populates="images")

    # Índices
    __table_args__ = (
        Index("idx_product_images_product", product_id),
        Index("idx_product_images_primary", is_primary),
        Index("idx_product_images_sort", sort_order),
    )


class Promotion(Base):
    """Promociones y ofertas"""

    __tablename__ = "promotions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    discount_percentage = Column(Float)  # 15.0 para 15%
    discount_amount = Column(Float)  # Descuento fijo en $
    promo_code = Column(String(50), unique=True, index=True)  # Código promocional

    # Validity
    valid_from = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    valid_until = Column(DateTime, nullable=False)
    max_uses = Column(Integer)  # Límite de usos
    current_uses = Column(Integer, default=0)

    # Conditions
    min_purchase_amount = Column(Float)  # Monto mínimo de compra
    applicable_categories = Column(JSONB)  # ["laptops", "gaming"]

    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    products: Mapped[List["Product"]] = relationship(
        "Product", secondary=product_promotion_association, back_populates="promotions"
    )

    @property
    def is_valid(self) -> bool:
        """Verifica si la promoción está vigente"""
        now = datetime.now(timezone.utc)
        return bool(
            self.active
            and self.valid_from <= now <= self.valid_until
            and (self.max_uses is None or self.current_uses < self.max_uses)
        )


class ProductReview(Base, TimestampMixin):
    """Reviews y calificaciones de productos"""

    __tablename__ = "product_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    customer_name = Column(String(200))
    customer_phone = Column(String(20))  # Para identificar cliente de WhatsApp
    rating = Column(Integer, nullable=False)  # 1-5 estrellas
    review_text = Column(Text)
    verified_purchase = Column(Boolean, default=False)
    helpful_votes = Column(Integer, default=0)

    active = Column(Boolean, default=True)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="reviews")
    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="reviews")


class PriceHistory(Base):
    """Historial de precios para analytics"""

    __tablename__ = "price_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    price = Column(Float, nullable=False)
    change_reason = Column(String(100))  # promotion, market_change, cost_update
    notes = Column(Text)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    product: Mapped["Product"] = relationship("Product")


class StockMovement(Base):
    """Movimientos de inventario"""

    __tablename__ = "stock_movements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    movement_type = Column(String(20), nullable=False)  # in, out, adjustment
    quantity = Column(Integer, nullable=False)
    previous_stock = Column(Integer, nullable=False)
    new_stock = Column(Integer, nullable=False)
    reason = Column(String(100))  # sale, restock, damaged, adjustment
    notes = Column(Text)
    reference_number = Column(String(100))  # Número de orden, factura, etc.

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_by = Column(String(100))  # Usuario que hizo el movimiento

    # Relationships
    product: Mapped["Product"] = relationship("Product")


class Customer(Base, TimestampMixin):
    """Clientes del chatbot"""

    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_number = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(200))
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    profile_name = Column(String(200))  # Nombre del perfil de WhatsApp

    # Información adicional
    date_of_birth = Column(DateTime)
    gender = Column(String(10))

    # Customer analytics
    total_interactions = Column(Integer, default=0)
    total_inquiries = Column(Integer, default=0)
    interests = Column(JSONB)  # ["gaming", "work", "components"]
    preferences = Column(JSONB, default=dict)  # Preferencias generales del cliente
    meta_data = Column(JSONB, default=dict)
    budget_range = Column(String(50))  # "1000-1500", "1500-3000"
    preferred_brands = Column(JSONB)  # ["ASUS", "MSI"]

    # Status
    active = Column(Boolean, default=True)
    blocked = Column(Boolean, default=False)
    vip = Column(Boolean, default=False)

    first_contact = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_contact = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    conversations: Mapped[List["Conversation"]] = relationship("Conversation", back_populates="customer")
    inquiries: Mapped[List["ProductInquiry"]] = relationship("ProductInquiry", back_populates="customer")
    reviews = relationship("ProductReview", back_populates="customer")

    # Índices
    __table_args__ = (
        Index("idx_customers_active", active),
        Index("idx_customers_name", first_name, last_name),
    )

    def __repr__(self):
        return f"<Customer(phone='{self.phone_number}', name='{self.first_name} {self.last_name}')>"

    @property
    def full_name(self) -> str:
        """Nombre completo del cliente."""
        names = [full_name for full_name in [self.first_name, self.last_name] if full_name]  # type: ignore
        return " ".join(names) if names else self.phone_number  # type: ignore


class Conversation(Base):
    """Conversaciones del chatbot"""

    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    session_id = Column(String(100), index=True)  # Para agrupar mensajes de una sesión

    # Conversation metadata
    total_messages = Column(Integer, default=0)
    user_messages = Column(Integer, default=0)
    bot_messages = Column(Integer, default=0)
    intent_detected = Column(String(100))  # gaming, price_inquiry, support
    products_shown = Column(JSONB)  # IDs de productos mostrados
    conversion_stage = Column(String(50))  # inquiry, interested, qualified, closed

    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship("Message", back_populates="conversation")


class Message(Base):
    """Mensajes individuales"""

    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_phone = Column(String, nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    message_type = Column(String(20), nullable=False)  # user, bot, system
    content = Column(Text, nullable=False)
    intent = Column(String(100))  # Intención detectada
    confidence = Column(Float)  # Confianza en la detección de intención

    # WhatsApp specific
    whatsapp_message_id = Column(String(100), unique=True, index=True)
    message_format = Column(String(20))  # text, image, document, interactive

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")


class ProductInquiry(Base):
    """Consultas específicas sobre productos"""

    __tablename__ = "product_inquiries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"))
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"))

    inquiry_type = Column(String(50), nullable=False)  # price, specs, availability, comparison
    inquiry_text = Column(Text)
    budget_mentioned = Column(Float)
    urgency = Column(String(20))  # low, medium, high
    status = Column(String(20), default="open")  # open, responded, closed

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    responded_at = Column(DateTime)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="inquiries")
    product: Mapped[Optional["Product"]] = relationship("Product")
    category: Mapped[Optional["Category"]] = relationship("Category")


class Analytics(Base):
    """Analytics y métricas del chatbot"""

    __tablename__ = "analytics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    metric_data = Column(JSONB)  # Datos adicionales
    period_type = Column(String(20))  # daily, weekly, monthly
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# Índices adicionales para optimización

# Índices compuestos para búsquedas frecuentes
Index("idx_product_category_active", Product.category_id, Product.active)
Index("idx_product_price_stock", Product.price, Product.stock)
Index("idx_product_brand_category", Product.brand_id, Product.category_id)
Index("idx_customer_phone_active", Customer.phone_number, Customer.active)
Index("idx_conversation_customer_date", Conversation.customer_id, Conversation.started_at)
Index("idx_message_conversation_date", Message.conversation_id, Message.created_at)
Index("idx_promotion_validity", Promotion.valid_from, Promotion.valid_until, Promotion.active)


def create_search_trigger():
    """
    SQL para crear trigger de búsqueda full-text en productos.
    """
    return """
    CREATE OR REPLACE FUNCTION update_product_search_vector()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.search_vector := 
            setweight(to_tsvector('spanish', COALESCE(NEW.name, '')), 'A') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.description, '')), 'B') ||
            setweight(to_tsvector('spanish', COALESCE(NEW.model, '')), 'C');
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS products_search_vector_trigger ON products;
    CREATE TRIGGER products_search_vector_trigger
        BEFORE INSERT OR UPDATE ON products
        FOR EACH ROW EXECUTE FUNCTION update_product_search_vector();
    """


def create_indexes():
    """
    SQL adicional para crear índices especiales.
    """
    return """
    -- Extensiones necesarias
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    CREATE EXTENSION IF NOT EXISTS btree_gin;
    
    -- Índices GIN para búsquedas avanzadas
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_products_meta_data_gin 
        ON products USING gin (meta_data);
    
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_customers_preferences_gin 
        ON customers USING gin (preferences);
    
    -- Índices compuestos útiles
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_products_active_category_stock 
        ON products (active, category_id, stock) WHERE active = true;
    
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_products_active_brand_price 
        ON products (active, brand_id, price) WHERE active = true;
    """
