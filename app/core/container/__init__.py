# ============================================================================
# SCOPE: GLOBAL
# Description: Contenedor principal de inyección de dependencias (singleton).
#              Compone todos los sub-contenedores de dominio.
# Tenant-Aware: No - provee servicios de infraestructura compartidos.
#              Para servicios tenant-aware, usar TenantDependencyContainer.
# ============================================================================
"""
Dependency Injection Container.

Centralized container for creating and managing all application dependencies.
Implements Dependency Inversion Principle by wiring concrete implementations to interfaces.

This module is the facade that composes all domain-specific containers.
"""

from __future__ import annotations

import logging

from app.core.interfaces.agent import IAgent
from app.core.interfaces.llm import ILLM
from app.core.interfaces.repository import IRepository
from app.core.interfaces.vector_store import IVectorStore
from app.orchestration import SuperOrchestrator

from .agents import AgentsContainer
from .base import BaseContainer
from .credit import CreditContainer
from .ecommerce import EcommerceContainer
from .excelencia import ExcelenciaContainer
from .healthcare import HealthcareContainer
from .shared import SharedContainer
from .tenant_container import (
    TenantConfigCache,
    TenantDependencyContainer,
    get_tenant_config_cache,
    invalidate_tenant_config,
)

logger = logging.getLogger(__name__)


class DependencyContainer:
    """
    Dependency Injection Container (Facade).

    Single Responsibility: Compose and delegate to domain-specific containers.
    Singleton Pattern: Ensures single instance of expensive resources (LLM, Vector Store).
    """

    def __init__(self, config: dict | None = None):
        """
        Initialize container with all domain sub-containers.

        Args:
            config: Optional configuration dict (overrides settings)
        """
        # Base container with singletons
        self._base = BaseContainer(config)

        # Domain containers
        self._ecommerce = EcommerceContainer(self._base)
        self._credit = CreditContainer(self._base)
        self._healthcare = HealthcareContainer(self._base)
        self._excelencia = ExcelenciaContainer(self._base)
        self._shared = SharedContainer(self._base)

        # Agents container
        self._agents = AgentsContainer(
            self._base,
            self._ecommerce,
            self._credit,
            self._healthcare,
            self._excelencia,
        )

        logger.info("DependencyContainer initialized with all domain containers")

    # Expose config and settings for backwards compatibility
    @property
    def settings(self):
        return self._base.settings

    @property
    def config(self):
        return self._base.config

    # ============================================================
    # SINGLETONS (delegated to BaseContainer)
    # ============================================================

    def get_llm(self) -> ILLM:
        """Get LLM instance (singleton)."""
        return self._base.get_llm()

    def get_vector_store(self) -> IVectorStore:
        """Get Vector Store instance (singleton)."""
        return self._base.get_vector_store()

    def get_config(self) -> dict:
        """Get current configuration."""
        return self._base.get_config()

    # ============================================================
    # E-COMMERCE (delegated to EcommerceContainer)
    # ============================================================

    def create_product_repository(self):
        return self._ecommerce.create_product_repository()

    def create_order_repository(self, db):
        return self._ecommerce.create_order_repository(db)

    def create_category_repository(self, db):
        return self._ecommerce.create_category_repository(db)

    def create_promotion_repository(self, db):
        return self._ecommerce.create_promotion_repository(db)

    def create_search_products_use_case(self):
        return self._ecommerce.create_search_products_use_case()

    def create_get_products_by_category_use_case(self):
        return self._ecommerce.create_get_products_by_category_use_case()

    def create_get_featured_products_use_case(self):
        return self._ecommerce.create_get_featured_products_use_case()

    def create_get_product_by_id_use_case(self):
        return self._ecommerce.create_get_product_by_id_use_case()

    def create_create_order_use_case(self, db):
        return self._ecommerce.create_create_order_use_case(db)

    def create_track_order_use_case(self, db):
        return self._ecommerce.create_track_order_use_case(db)

    def create_get_customer_orders_use_case(self, db):
        return self._ecommerce.create_get_customer_orders_use_case(db)

    # ============================================================
    # CREDIT (delegated to CreditContainer)
    # ============================================================

    def create_credit_account_repository(self) -> IRepository:
        return self._credit.create_credit_account_repository()

    def create_payment_repository(self) -> IRepository:
        return self._credit.create_payment_repository()

    def create_credit_account_repository_sqlalchemy(self, db):
        return self._credit.create_credit_account_repository_sqlalchemy(db)

    def create_payment_repository_sqlalchemy(self, db):
        return self._credit.create_payment_repository_sqlalchemy(db)

    def create_payment_schedule_repository(self, db):
        return self._credit.create_payment_schedule_repository(db)

    def create_get_credit_balance_use_case(self):
        return self._credit.create_get_credit_balance_use_case()

    def create_process_payment_use_case(self):
        return self._credit.create_process_payment_use_case()

    def create_get_payment_schedule_use_case(self):
        return self._credit.create_get_payment_schedule_use_case()

    # ============================================================
    # HEALTHCARE (delegated to HealthcareContainer)
    # ============================================================

    def create_patient_repository(self, db):
        return self._healthcare.create_patient_repository(db)

    def create_appointment_repository(self, db):
        return self._healthcare.create_appointment_repository(db)

    def create_doctor_repository(self, db):
        return self._healthcare.create_doctor_repository(db)

    def create_book_appointment_use_case(self, db):
        return self._healthcare.create_book_appointment_use_case(db)

    def create_get_patient_records_use_case(self, db):
        return self._healthcare.create_get_patient_records_use_case(db)

    def create_triage_patient_use_case(self, db):
        return self._healthcare.create_triage_patient_use_case(db)

    # ============================================================
    # EXCELENCIA (delegated to ExcelenciaContainer)
    # ============================================================

    @property
    def excelencia(self) -> ExcelenciaContainer:
        """Direct access to Excelencia container for admin operations."""
        return self._excelencia

    def create_support_ticket_use_case(self, db):
        """Create use case for support ticket creation."""
        return self._excelencia.create_support_ticket_use_case(db)

    # ============================================================
    # SHARED (delegated to SharedContainer)
    # ============================================================

    def create_customer_repository(self, db):
        return self._shared.create_customer_repository(db)

    def create_get_or_create_customer_use_case(self, db):
        return self._shared.create_get_or_create_customer_use_case(db)

    # Knowledge
    def create_search_knowledge_use_case(self, db):
        return self._shared.create_search_knowledge_use_case(db)

    def create_create_knowledge_use_case(self, db):
        return self._shared.create_create_knowledge_use_case(db)

    def create_get_knowledge_use_case(self, db):
        return self._shared.create_get_knowledge_use_case(db)

    def create_update_knowledge_use_case(self, db):
        return self._shared.create_update_knowledge_use_case(db)

    def create_delete_knowledge_use_case(self, db):
        return self._shared.create_delete_knowledge_use_case(db)

    def create_list_knowledge_use_case(self, db):
        return self._shared.create_list_knowledge_use_case(db)

    def create_get_knowledge_statistics_use_case(self, db):
        return self._shared.create_get_knowledge_statistics_use_case(db)

    def create_regenerate_knowledge_embeddings_use_case(self, db):
        return self._shared.create_regenerate_knowledge_embeddings_use_case(db)

    # Documents
    def create_upload_pdf_use_case(self, db):
        return self._shared.create_upload_pdf_use_case(db)

    def create_upload_text_use_case(self, db):
        return self._shared.create_upload_text_use_case(db)

    def create_batch_upload_documents_use_case(self, db):
        return self._shared.create_batch_upload_documents_use_case(db)

    # Admin
    def create_list_domains_use_case(self, db):
        return self._shared.create_list_domains_use_case(db)

    def create_enable_domain_use_case(self, db):
        return self._shared.create_enable_domain_use_case(db)

    def create_disable_domain_use_case(self, db):
        return self._shared.create_disable_domain_use_case(db)

    def create_update_domain_config_use_case(self, db):
        return self._shared.create_update_domain_config_use_case(db)

    def create_get_domain_stats_use_case(self, db):
        return self._shared.create_get_domain_stats_use_case(db)

    def create_get_contact_domain_use_case(self, db):
        return self._shared.create_get_contact_domain_use_case(db)

    def create_assign_contact_domain_use_case(self, db):
        return self._shared.create_assign_contact_domain_use_case(db)

    def create_remove_contact_domain_use_case(self, db):
        return self._shared.create_remove_contact_domain_use_case(db)

    def create_clear_domain_assignments_use_case(self, db):
        return self._shared.create_clear_domain_assignments_use_case(db)

    def create_get_agent_config_use_case(self):
        return self._shared.create_get_agent_config_use_case()

    def create_update_agent_modules_use_case(self):
        return self._shared.create_update_agent_modules_use_case()

    def create_update_agent_settings_use_case(self):
        return self._shared.create_update_agent_settings_use_case()

    # ============================================================
    # AGENTS (delegated to AgentsContainer)
    # ============================================================

    def create_product_agent(self) -> IAgent:
        return self._agents.create_product_agent()

    def create_credit_agent(self) -> IAgent:
        return self._agents.create_credit_agent()

    def create_healthcare_agent(self) -> IAgent:
        return self._agents.create_healthcare_agent()

    def create_excelencia_agent(self) -> IAgent:
        return self._agents.create_excelencia_agent()

    def create_super_orchestrator(self) -> SuperOrchestrator:
        return self._agents.create_super_orchestrator()


# ============================================================
# GLOBAL CONTAINER INSTANCE
# ============================================================

_container: DependencyContainer | None = None


def get_container(config: dict | None = None) -> DependencyContainer:
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
            "Container already initialized, ignoring new config. "
            "Call reset_container() first to change config."
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
    """Convenience function to get SuperOrchestrator."""
    return get_container().create_super_orchestrator()


def get_product_agent() -> IAgent:
    """Convenience function to get ProductAgent."""
    return get_container().create_product_agent()


def get_credit_agent() -> IAgent:
    """Convenience function to get CreditAgent."""
    return get_container().create_credit_agent()


def get_healthcare_agent() -> IAgent:
    """Convenience function to get HealthcareAgent."""
    return get_container().create_healthcare_agent()


def get_excelencia_agent() -> IAgent:
    """Convenience function to get ExcelenciaAgent."""
    return get_container().create_excelencia_agent()


__all__ = [
    # Main container
    "DependencyContainer",
    # Global functions
    "get_container",
    "reset_container",
    # Convenience functions
    "get_super_orchestrator",
    "get_product_agent",
    "get_credit_agent",
    "get_healthcare_agent",
    "get_excelencia_agent",
    # Sub-containers (for advanced usage)
    "BaseContainer",
    "EcommerceContainer",
    "CreditContainer",
    "HealthcareContainer",
    "ExcelenciaContainer",
    "SharedContainer",
    "AgentsContainer",
    # Tenant-aware container
    "TenantDependencyContainer",
    "TenantConfigCache",
    "get_tenant_config_cache",
    "invalidate_tenant_config",
]
