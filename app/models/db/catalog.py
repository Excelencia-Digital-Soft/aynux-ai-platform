"""
Product catalog models: Products, Categories, Brands, etc.
"""

import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
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
from pgvector.sqlalchemy import Vector
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .promotions import Promotion

# Tabla de asociación para productos y promociones (many-to-many)
product_promotion_association = Table(
    "product_promotions",
    Base.metadata,
    Column("product_id", UUID(as_uuid=True), ForeignKey("products.id")),
    Column("promotion_id", UUID(as_uuid=True), ForeignKey("promotions.id")),
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

    # External reference from DUX system
    external_id = Column(String(100), index=True)

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

    # External reference from DUX system
    external_code = Column(String(100))

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

    # Additional fields for DUX integration
    cost = Column(Float, default=0.0)  # Cost from DUX
    tax_percentage = Column(Float, default=0.0)  # Tax percentage from DUX
    external_code = Column(String(100))  # External code from DUX
    image_url = Column(String(1000))  # Image URL from DUX
    barcode = Column(String(100))  # Barcode from DUX

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

    # Vector embedding for semantic search (pgvector)
    # nomic-embed-text:v1.5 generates 768-dimensional vectors
    embedding = Column(Vector(768), nullable=True)

    # Metadatos adicionales
    meta_data = Column(JSONB, default=dict)

    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="products")
    subcategory: Mapped[Optional["Subcategory"]] = relationship("Subcategory", back_populates="products")
    brand: Mapped[Optional["Brand"]] = relationship("Brand", back_populates="products")
    attributes: Mapped[List["ProductAttribute"]] = relationship(
        "ProductAttribute", back_populates="product", cascade="all, delete-orphan"
    )
    product_images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    promotions: Mapped[List["Promotion"]] = relationship(
        "Promotion", secondary=product_promotion_association, back_populates="products"
    )

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
        # HNSW index for vector similarity search with pgvector
        Index(
            "idx_products_embedding_hnsw",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        CheckConstraint("price >= 0", name="check_price_positive"),
        CheckConstraint("stock >= 0", name="check_stock_non_negative"),
    )

    def __repr__(self):
        return f"<Product(name='{self.name}', price={self.price}, stock={self.stock})>"

    @hybrid_property
    def is_in_stock(self) -> bool:
        """Verifica si el producto está en stock."""
        return self.stock > 0  # type: ignore

    @hybrid_property
    def is_low_stock(self) -> bool:
        """Verifica si el producto está con stock bajo."""
        return self.stock <= self.min_stock  # type: ignore

    @hybrid_property
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
    product = relationship("Product", back_populates="product_images")

    # Índices
    __table_args__ = (
        Index("idx_product_images_product", product_id),
        Index("idx_product_images_primary", is_primary),
        Index("idx_product_images_sort", sort_order),
    )
