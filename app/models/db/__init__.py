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
from .agent_knowledge import AgentKnowledge
from .knowledge_base import CompanyKnowledge
from .rag_query_log import RagQueryLog
from .orders import Order, OrderItem
from .promotions import Promotion
from .prompts import Prompt, PromptVersion
from .reviews import ProductReview
from .support_ticket import SupportTicket
from .user import UserDB
from .conversation_history import ConversationContext, ConversationMessage
from .agent import Agent, AgentType
from .ai_model import AIModel, ModelProvider, ModelType
from .software_module import ModuleCategory, ModuleStatus, SoftwareModule

# Soporte schema models
from .soporte import (
    Incident,
    IncidentCategory,
    IncidentComment,
    IncidentHistory,
    JiraConfig,
    PendingTicket,
)

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
    "AgentKnowledge",
    "CompanyKnowledge",
    "RagQueryLog",
    # Support Tickets
    "SupportTicket",
    # Authentication
    "UserDB",
    # Conversation History
    "ConversationContext",
    "ConversationMessage",
    # Soporte (Incidents)
    "Incident",
    "IncidentCategory",
    "IncidentComment",
    "IncidentHistory",
    "JiraConfig",
    "PendingTicket",
    # Agents
    "Agent",
    "AgentType",
    # AI Models
    "AIModel",
    "ModelProvider",
    "ModelType",
    # Software Modules (Excelencia)
    "SoftwareModule",
    "ModuleStatus",
    "ModuleCategory",
]
