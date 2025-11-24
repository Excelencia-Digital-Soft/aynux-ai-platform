"""
Dependency Injection Container

Centralized container for creating and managing all application dependencies.
Implements Dependency Inversion Principle by wiring concrete implementations to interfaces.
"""

import logging
from typing import Dict, Optional

from app.config.settings import get_settings

# Core Interfaces
from app.core.interfaces.agent import IAgent
from app.core.interfaces.llm import ILLM
from app.core.interfaces.repository import IRepository
from app.core.interfaces.vector_store import IVectorStore

# Integrations (Implementations)
from app.integrations.llm import create_ollama_llm
from app.integrations.vector_stores import create_pgvector_store

# E-commerce Domain
from app.domains.ecommerce.infrastructure.repositories import ProductRepository
from app.domains.ecommerce.agents import ProductAgent
from app.domains.ecommerce.application.use_cases import (
    SearchProductsUseCase,
    GetProductsByCategoryUseCase,
    GetFeaturedProductsUseCase,
)

# Credit Domain
from app.domains.credit.infrastructure.persistence.sqlalchemy import CreditAccountRepository
from app.domains.credit.agents import CreditAgent
from app.domains.credit.application.use_cases import (
    GetCreditBalanceUseCase,
    ProcessPaymentUseCase,
    GetPaymentScheduleUseCase,
)

# Orchestration
from app.orchestration import SuperOrchestrator

# Shared Domain Use Cases
from app.domains.shared.application.use_cases import (
    GetOrCreateCustomerUseCase,
    SearchKnowledgeUseCase,
)

logger = logging.getLogger(__name__)


class DependencyContainer:
    """
    Dependency Injection Container.

    Single Responsibility: Create and wire all application dependencies
    Singleton Pattern: Ensures single instance of expensive resources (LLM, Vector Store)
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize container.

        Args:
            config: Optional configuration dict (overrides settings)
        """
        self.settings = get_settings()
        self.config = config or {}

        # Singletons (expensive to create)
        self._llm_instance: Optional[ILLM] = None
        self._vector_store_instance: Optional[IVectorStore] = None

        logger.info("DependencyContainer initialized")

    # ============================================================
    # SINGLETONS (Shared Resources)
    # ============================================================

    def get_llm(self) -> ILLM:
        """
        Get LLM instance (singleton).

        Returns:
            ILLM instance (Ollama)
        """
        if self._llm_instance is None:
            model_name = self.config.get("llm_model") or getattr(self.settings, "OLLAMA_API_MODEL", "deepseek-r1:7b")

            logger.info(f"Creating LLM instance with model: {model_name}")
            self._llm_instance = create_ollama_llm(model_name=model_name)

        return self._llm_instance

    def get_vector_store(self) -> IVectorStore:
        """
        Get Vector Store instance (singleton).

        Returns:
            Vector Store instance (PgVector)
        """
        if self._vector_store_instance is None:
            collection_name = self.config.get("vector_collection", "products")
            embedding_dim = self.config.get("embedding_dimension", 768)

            logger.info(f"Creating Vector Store: {collection_name} (dim: {embedding_dim})")
            self._vector_store_instance = create_pgvector_store(
                collection_name=collection_name,
                embedding_dimension=embedding_dim,
            )
            assert self._vector_store_instance is not None, "Failed to create vector store"

        return self._vector_store_instance

    # ============================================================
    # REPOSITORIES (Data Access)
    # ============================================================

    def create_product_repository(self) -> ProductRepository:
        """
        Create Product Repository.

        Returns:
            ProductRepository instance
        """
        return ProductRepository()  # type: ignore[abstract]

    def create_credit_account_repository(self) -> IRepository:
        """
        Create Credit Account Repository.

        Returns:
            CreditAccountRepository instance
        """
        return CreditAccountRepository()

    def create_payment_repository(self) -> IRepository:
        """
        Create Payment Repository.

        Note: Currently returns CreditAccountRepository as placeholder.
        TODO: Implement separate PaymentRepository when Payment model is ready.

        Returns:
            Repository for payments
        """
        # TODO: Replace with actual PaymentRepository
        return CreditAccountRepository()

    # ============================================================
    # USE CASES (Business Logic)
    # ============================================================

    # E-commerce Use Cases

    def create_search_products_use_case(self) -> SearchProductsUseCase:
        """Create SearchProductsUseCase with dependencies"""
        return SearchProductsUseCase(
            product_repository=self.create_product_repository(),
            vector_store=self.get_vector_store(),
            llm=self.get_llm(),
        )

    def create_get_products_by_category_use_case(self) -> GetProductsByCategoryUseCase:
        """Create GetProductsByCategoryUseCase with dependencies"""
        return GetProductsByCategoryUseCase(product_repository=self.create_product_repository())

    def create_get_featured_products_use_case(self) -> GetFeaturedProductsUseCase:
        """Create GetFeaturedProductsUseCase with dependencies"""
        return GetFeaturedProductsUseCase(product_repository=self.create_product_repository())

    # Credit Use Cases

    def create_get_credit_balance_use_case(self) -> GetCreditBalanceUseCase:
        """Create GetCreditBalanceUseCase with dependencies"""
        return GetCreditBalanceUseCase(credit_account_repository=self.create_credit_account_repository())

    def create_process_payment_use_case(self) -> ProcessPaymentUseCase:
        """Create ProcessPaymentUseCase with dependencies"""
        return ProcessPaymentUseCase(
            credit_account_repository=self.create_credit_account_repository(),
            payment_repository=self.create_payment_repository(),
        )

    def create_get_payment_schedule_use_case(self) -> GetPaymentScheduleUseCase:
        """Create GetPaymentScheduleUseCase with dependencies"""
        return GetPaymentScheduleUseCase(credit_account_repository=self.create_credit_account_repository())

    # Shared Use Cases

    def create_get_or_create_customer_use_case(self) -> GetOrCreateCustomerUseCase:
        """
        Create GetOrCreateCustomerUseCase.

        Returns:
            GetOrCreateCustomerUseCase instance
        """
        return GetOrCreateCustomerUseCase()

    def create_search_knowledge_use_case(self, db) -> SearchKnowledgeUseCase:
        """
        Create SearchKnowledgeUseCase with dependencies.

        Args:
            db: Async database session

        Returns:
            SearchKnowledgeUseCase instance
        """
        return SearchKnowledgeUseCase(db=db)

    def create_create_knowledge_use_case(self, db):
        """Create CreateKnowledgeUseCase with dependencies"""
        from app.domains.shared.application.use_cases import CreateKnowledgeUseCase

        return CreateKnowledgeUseCase(db=db)

    def create_get_knowledge_use_case(self, db):
        """Create GetKnowledgeUseCase with dependencies"""
        from app.domains.shared.application.use_cases import GetKnowledgeUseCase

        return GetKnowledgeUseCase(db=db)

    def create_update_knowledge_use_case(self, db):
        """Create UpdateKnowledgeUseCase with dependencies"""
        from app.domains.shared.application.use_cases import UpdateKnowledgeUseCase

        return UpdateKnowledgeUseCase(db=db)

    def create_delete_knowledge_use_case(self, db):
        """Create DeleteKnowledgeUseCase with dependencies"""
        from app.domains.shared.application.use_cases import DeleteKnowledgeUseCase

        return DeleteKnowledgeUseCase(db=db)

    def create_list_knowledge_use_case(self, db):
        """Create ListKnowledgeUseCase with dependencies"""
        from app.domains.shared.application.use_cases import ListKnowledgeUseCase

        return ListKnowledgeUseCase(db=db)

    def create_get_knowledge_statistics_use_case(self, db):
        """Create GetKnowledgeStatisticsUseCase with dependencies"""
        from app.domains.shared.application.use_cases import GetKnowledgeStatisticsUseCase

        return GetKnowledgeStatisticsUseCase(db=db)

    def create_regenerate_knowledge_embeddings_use_case(self, db):
        """Create RegenerateKnowledgeEmbeddingsUseCase with dependencies"""
        from app.domains.shared.application.use_cases import RegenerateKnowledgeEmbeddingsUseCase

        return RegenerateKnowledgeEmbeddingsUseCase(db=db)

    # Document Upload Use Cases

    def create_upload_pdf_use_case(self, db):
        """Create UploadPDFUseCase with dependencies"""
        from app.domains.shared.application.use_cases import UploadPDFUseCase

        return UploadPDFUseCase(db=db)

    def create_upload_text_use_case(self, db):
        """Create UploadTextUseCase with dependencies"""
        from app.domains.shared.application.use_cases import UploadTextUseCase

        return UploadTextUseCase(db=db)

    def create_batch_upload_documents_use_case(self, db):
        """Create BatchUploadDocumentsUseCase with dependencies"""
        from app.domains.shared.application.use_cases import BatchUploadDocumentsUseCase

        return BatchUploadDocumentsUseCase(db=db)

    # Agent Configuration Use Cases (don't require db session)

    def create_get_agent_config_use_case(self):
        """Create GetAgentConfigUseCase"""
        from app.domains.shared.application.use_cases import GetAgentConfigUseCase

        return GetAgentConfigUseCase()

    def create_update_agent_modules_use_case(self):
        """Create UpdateAgentModulesUseCase"""
        from app.domains.shared.application.use_cases import UpdateAgentModulesUseCase

        return UpdateAgentModulesUseCase()

    def create_update_agent_settings_use_case(self):
        """Create UpdateAgentSettingsUseCase"""
        from app.domains.shared.application.use_cases import UpdateAgentSettingsUseCase

        return UpdateAgentSettingsUseCase()

    # Admin Use Cases

    def create_list_domains_use_case(self, db):
        """
        Create ListDomainsUseCase with dependencies.

        Args:
            db: Async database session

        Returns:
            ListDomainsUseCase instance
        """
        from app.domains.shared.application.use_cases import ListDomainsUseCase

        return ListDomainsUseCase(db=db)

    def create_enable_domain_use_case(self, db):
        """Create EnableDomainUseCase with dependencies"""
        from app.domains.shared.application.use_cases import EnableDomainUseCase

        return EnableDomainUseCase(db=db)

    def create_disable_domain_use_case(self, db):
        """Create DisableDomainUseCase with dependencies"""
        from app.domains.shared.application.use_cases import DisableDomainUseCase

        return DisableDomainUseCase(db=db)

    def create_update_domain_config_use_case(self, db):
        """Create UpdateDomainConfigUseCase with dependencies"""
        from app.domains.shared.application.use_cases import UpdateDomainConfigUseCase

        return UpdateDomainConfigUseCase(db=db)

    def create_get_contact_domain_use_case(self, db):
        """Create GetContactDomainUseCase with dependencies"""
        from app.domains.shared.application.use_cases import GetContactDomainUseCase

        return GetContactDomainUseCase(db=db)

    def create_assign_contact_domain_use_case(self, db):
        """Create AssignContactDomainUseCase with dependencies"""
        from app.domains.shared.application.use_cases import AssignContactDomainUseCase

        return AssignContactDomainUseCase(db=db)

    def create_remove_contact_domain_use_case(self, db):
        """Create RemoveContactDomainUseCase with dependencies"""
        from app.domains.shared.application.use_cases import RemoveContactDomainUseCase

        return RemoveContactDomainUseCase(db=db)

    def create_clear_domain_assignments_use_case(self, db):
        """Create ClearDomainAssignmentsUseCase with dependencies"""
        from app.domains.shared.application.use_cases import ClearDomainAssignmentsUseCase

        return ClearDomainAssignmentsUseCase(db=db)

    def create_get_domain_stats_use_case(self, db):
        """Create GetDomainStatsUseCase with dependencies"""
        from app.domains.shared.application.use_cases import GetDomainStatsUseCase

        return GetDomainStatsUseCase(db=db)

    # ============================================================
    # AGENTS (Domain Coordinators)
    # ============================================================

    def create_product_agent(self) -> IAgent:
        """
        Create Product Agent with all dependencies.

        Returns:
            ProductAgent instance
        """
        agent_config = self.config.get("product_agent", {})

        logger.info("Creating ProductAgent")
        return ProductAgent(
            product_repository=self.create_product_repository(),
            vector_store=self.get_vector_store(),
            llm=self.get_llm(),
            config=agent_config,
        )

    def create_credit_agent(self) -> IAgent:
        """
        Create Credit Agent with all dependencies.

        Returns:
            CreditAgent instance
        """
        agent_config = self.config.get("credit_agent", {})

        logger.info("Creating CreditAgent")
        return CreditAgent(
            credit_account_repository=self.create_credit_account_repository(),
            payment_repository=self.create_payment_repository(),
            llm=self.get_llm(),
            config=agent_config,
        )

    # ============================================================
    # SUPER ORCHESTRATOR (Multi-Domain Router)
    # ============================================================

    def create_super_orchestrator(self) -> SuperOrchestrator:
        """
        Create Super Orchestrator with all domain agents.

        Returns:
            SuperOrchestrator instance
        """
        orchestrator_config = self.config.get("orchestrator", {})

        # Create all domain agents
        domain_agents = {
            "ecommerce": self.create_product_agent(),
            "credit": self.create_credit_agent(),
            # Add more domains as they're implemented:
            # "healthcare": self.create_healthcare_agent(),
            # "excelencia": self.create_excelencia_agent(),
        }

        logger.info(f"Creating SuperOrchestrator with {len(domain_agents)} domains: " f"{list(domain_agents.keys())}")

        return SuperOrchestrator(
            domain_agents=domain_agents,
            llm=self.get_llm(),
            config=orchestrator_config,
        )

    # ============================================================
    # CONFIGURATION
    # ============================================================

    def get_config(self) -> Dict:
        """Get current configuration"""
        return {
            "llm_model": self.config.get("llm_model", "deepseek-r1:7b"),
            "vector_collection": self.config.get("vector_collection", "products"),
            "embedding_dimension": self.config.get("embedding_dimension", 768),
            "domains": ["ecommerce", "credit"],
        }


# ============================================================
# GLOBAL CONTAINER INSTANCE
# ============================================================

_container: Optional[DependencyContainer] = None


def get_container(config: Optional[Dict] = None) -> DependencyContainer:
    """
    Get global container instance (singleton).

    Args:
        config: Optional configuration (only used on first call)

    Returns:
        DependencyContainer instance
    """
    global _container

    if _container is None:
        logger.info("Initializing global DependencyContainer")
        _container = DependencyContainer(config)
    elif config is not None:
        logger.warning(
            "Container already initialized, ignoring new config. " "Call reset_container() first to change config."
        )

    return _container


def reset_container() -> None:
    """
    Reset global container instance.

    Useful for testing or reconfiguration.
    """
    global _container
    logger.info("Resetting global DependencyContainer")
    _container = None


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================


def get_super_orchestrator() -> SuperOrchestrator:
    """
    Convenience function to get SuperOrchestrator.

    Returns:
        SuperOrchestrator instance
    """
    return get_container().create_super_orchestrator()


def get_product_agent() -> IAgent:
    """
    Convenience function to get ProductAgent.

    Returns:
        ProductAgent instance
    """
    return get_container().create_product_agent()


def get_credit_agent() -> IAgent:
    """
    Convenience function to get CreditAgent.

    Returns:
        CreditAgent instance
    """
    return get_container().create_credit_agent()
