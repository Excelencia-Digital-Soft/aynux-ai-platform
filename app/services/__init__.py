"""
Services Module

This module exports active services. Many legacy services have been deprecated
and migrated to Clean Architecture (Use Cases in app/domains/).

DEPRECATED SERVICES (removed):
- AIService → Use ILLM interface (app/core/interfaces/llm.py)
- CustomerService → Use GetOrCreateCustomerUseCase
- ProductService → Use SearchProductsUseCase, GetProductsByCategoryUseCase
- EnhancedProductService → Use SearchProductsUseCase
- CategoryVectorService → Use product Use Cases with vector search

MOVED SERVICES (now in integrations):
- DuxSyncService → app/domains/ecommerce/infrastructure/services/
- WhatsAppService → app/integrations/whatsapp/
- EmbeddingUpdateService → app/integrations/vector_stores/
- PromptService → app/core/shared/prompt_service.py

For dependency injection, use DependencyContainer (app/core/container.py)
"""

from .token_service import TokenService
from .user_service import UserService

__all__ = [
    "TokenService",
    "UserService",
]

