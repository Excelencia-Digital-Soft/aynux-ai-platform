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
from .knowledge_base import CompanyKnowledge
from .orders import Order, OrderItem
from .promotions import Promotion
from .prompts import Prompt, PromptVersion
from .reviews import ProductReview
from .support_ticket import SupportTicket
from .user import UserDB
from .conversation_history import ConversationContext, ConversationMessage

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
    # Knowledge Base
    "CompanyKnowledge",
    # Support Tickets
    "SupportTicket",
    # Authentication
    "UserDB",
    # Conversation History
    "ConversationContext",
    "ConversationMessage",
]
