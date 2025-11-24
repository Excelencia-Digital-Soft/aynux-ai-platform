"""
Services Module

This module exports active services. Many legacy services have been deprecated
and migrated to Clean Architecture (Use Cases in app/domains/).

DEPRECATED SERVICES (removed in Phase 1):
- AIService → Use ILLM interface (app/core/interfaces/llm.py)
- CustomerService → Use GetOrCreateCustomerUseCase
- ProductService → Use SearchProductsUseCase, GetProductsByCategoryUseCase
- EnhancedProductService → Use SearchProductsUseCase
- CategoryVectorService → Use product Use Cases with vector search

DEPRECATED SERVICES (removed in Phase 2 - Part 4):
- domain_detector → Use GetContactDomainUseCase (Admin Use Cases)
- domain_manager → Use LangGraphChatbotService + domain Use Cases directly
- super_orchestrator_service → Use app/orchestration/super_orchestrator.py
- super_orchestrator_service_refactored → Use app/orchestration/super_orchestrator.py

DEPRECATED SERVICES (removed in Phase 3):
- knowledge_service → Use Knowledge Use Cases (CreateKnowledgeUseCase,
  GetKnowledgeUseCase, UpdateKnowledgeUseCase, DeleteKnowledgeUseCase,
  ListKnowledgeUseCase, SearchKnowledgeUseCase, GetKnowledgeStatisticsUseCase,
  RegenerateKnowledgeEmbeddingsUseCase)

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
