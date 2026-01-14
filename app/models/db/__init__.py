"""
Database models package - Organized by responsibility
"""

from .agent import Agent, AgentType
from .agent_knowledge import AgentKnowledge
from .ai_model import AIModel, ModelProvider, ModelType
from .analytics import Analytics, PriceHistory, StockMovement
from .base import Base, TimestampMixin
from .catalog import Brand, Category, Product, ProductAttribute, ProductImage, Subcategory
from .contact_domains import ContactDomain, DomainConfig
from .conversation_history import ConversationContext, ConversationMessage
from .conversations import Conversation, Message
from .customers import Customer
from .domain import Domain
from .inquiries import ProductInquiry
from .knowledge_base import CompanyKnowledge
from .orders import Order, OrderItem
# Domain Intents (Multi-domain, JSONB patterns) - replaces legacy pharmacy_intents
from .domain_intents import DomainIntent
from .response_configs import ResponseConfig, PharmacyResponseConfig  # PharmacyResponseConfig is deprecated alias
# Intent Configs (replaces hardcoded intent_validator.py mappings)
from .intent_configs import FlowAgentConfig, IntentAgentMapping, KeywordAgentMapping
# Routing Configs (DB-driven routing for pharmacy flow)
from .routing_config import RoutingConfig, RoutingConfigType
from .promotions import Promotion
from .prompts import Prompt, PromptVersion
from .rag_query_log import RagQueryLog
from .reviews import ProductReview
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

# Tenancy models (multi-tenant support)
from .tenancy import (
    BypassRule,
    ChattigoCredentials,
    Organization,
    OrganizationUser,
    PharmacyMerchantConfig,
    TenantAgent,
    TenantConfig,
    TenantCredentials,
    TenantDocument,
    TenantInstitutionConfig,
    TenantPrompt,
)
from .user import UserDB

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
    # Domains
    "Domain",
    # Software Modules (Excelencia)
    "SoftwareModule",
    "ModuleStatus",
    "ModuleCategory",
    # Tenancy (Multi-tenant)
    "BypassRule",
    "ChattigoCredentials",
    "Organization",
    "OrganizationUser",
    "PharmacyMerchantConfig",
    "TenantAgent",
    "TenantConfig",
    "TenantCredentials",
    "TenantDocument",
    "TenantInstitutionConfig",
    "TenantPrompt",
    # Domain Intents (replaces legacy pharmacy_intents)
    "DomainIntent",
    # Response Configs (Multi-domain)
    "ResponseConfig",
    "PharmacyResponseConfig",  # Deprecated alias for backward compatibility
    # Intent Configs (replaces hardcoded intent_validator.py mappings)
    "IntentAgentMapping",
    "FlowAgentConfig",
    "KeywordAgentMapping",
    # Routing Configs (DB-driven routing for pharmacy flow)
    "RoutingConfig",
    "RoutingConfigType",
]
