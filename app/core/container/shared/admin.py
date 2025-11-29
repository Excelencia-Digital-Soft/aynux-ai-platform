"""
Shared Domain Container - Admin Use Cases.

Single Responsibility: Wire admin and configuration use cases.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.container.base import BaseContainer

logger = logging.getLogger(__name__)


class AdminContainer:
    """
    Admin use cases container.

    Single Responsibility: Create admin and domain configuration use cases.
    """

    def __init__(self, base: "BaseContainer"):
        """
        Initialize admin container.

        Args:
            base: BaseContainer with shared singletons
        """
        self._base = base

    # ==================== DOMAIN MANAGEMENT ====================

    def create_list_domains_use_case(self, db):
        """Create ListDomainsUseCase with dependencies."""
        from app.domains.shared.application.use_cases import ListDomainsUseCase

        return ListDomainsUseCase(db=db)

    def create_enable_domain_use_case(self, db):
        """Create EnableDomainUseCase with dependencies."""
        from app.domains.shared.application.use_cases import EnableDomainUseCase

        return EnableDomainUseCase(db=db)

    def create_disable_domain_use_case(self, db):
        """Create DisableDomainUseCase with dependencies."""
        from app.domains.shared.application.use_cases import DisableDomainUseCase

        return DisableDomainUseCase(db=db)

    def create_update_domain_config_use_case(self, db):
        """Create UpdateDomainConfigUseCase with dependencies."""
        from app.domains.shared.application.use_cases import UpdateDomainConfigUseCase

        return UpdateDomainConfigUseCase(db=db)

    def create_get_domain_stats_use_case(self, db):
        """Create GetDomainStatsUseCase with dependencies."""
        from app.domains.shared.application.use_cases import GetDomainStatsUseCase

        return GetDomainStatsUseCase(db=db)

    # ==================== CONTACT-DOMAIN ASSIGNMENT ====================

    def create_get_contact_domain_use_case(self, db):
        """Create GetContactDomainUseCase with dependencies."""
        from app.domains.shared.application.use_cases import GetContactDomainUseCase

        return GetContactDomainUseCase(db=db)

    def create_assign_contact_domain_use_case(self, db):
        """Create AssignContactDomainUseCase with dependencies."""
        from app.domains.shared.application.use_cases import AssignContactDomainUseCase

        return AssignContactDomainUseCase(db=db)

    def create_remove_contact_domain_use_case(self, db):
        """Create RemoveContactDomainUseCase with dependencies."""
        from app.domains.shared.application.use_cases import RemoveContactDomainUseCase

        return RemoveContactDomainUseCase(db=db)

    def create_clear_domain_assignments_use_case(self, db):
        """Create ClearDomainAssignmentsUseCase with dependencies."""
        from app.domains.shared.application.use_cases import ClearDomainAssignmentsUseCase

        return ClearDomainAssignmentsUseCase(db=db)

    # ==================== AGENT CONFIGURATION ====================

    def create_get_agent_config_use_case(self):
        """Create GetAgentConfigUseCase."""
        from app.domains.shared.application.use_cases import GetAgentConfigUseCase

        return GetAgentConfigUseCase()

    def create_update_agent_modules_use_case(self):
        """Create UpdateAgentModulesUseCase."""
        from app.domains.shared.application.use_cases import UpdateAgentModulesUseCase

        return UpdateAgentModulesUseCase()

    def create_update_agent_settings_use_case(self):
        """Create UpdateAgentSettingsUseCase."""
        from app.domains.shared.application.use_cases import UpdateAgentSettingsUseCase

        return UpdateAgentSettingsUseCase()
