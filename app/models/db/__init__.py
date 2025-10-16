"""
Database models package - Organized by responsibility
"""

from .analytics import Analytics, PriceHistory, StockMovement
from .base import Base, TimestampMixin
from .catalog import Brand, Category, Product, ProductAttribute, ProductImage, Subcategory
from .contact_domains import ContactDomain, DomainConfig
from .conversations import Conversation, Message
from .customers import Customer
from .inquiries import ProductInquiry
from .orders import Order, OrderItem
from .prompts import Prompt, PromptVersion
from .promotions import Promotion
from .reviews import ProductReview

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    # Catalog
    "Brand",
    "Category",
    "Product",
    "ProductAttribute",
    "ProductImage",
    "Subcategory",
    # Contact Domains
    "ContactDomain",
    "DomainConfig",
    # Customers
    "Customer",
    # Conversations
    "Conversation",
    "Message",
    # Orders
    "Order",
    "OrderItem",
    # Reviews
    "ProductReview",
    # Analytics
    "Analytics",
    "PriceHistory",
    "StockMovement",
    # Promotions
    "Promotion",
    # Inquiries
    "ProductInquiry",
    # Prompts
    "Prompt",
    "PromptVersion",
]

