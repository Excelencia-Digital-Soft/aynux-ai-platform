"""
Excelencia Domain Value Objects

Value objects for the Excelencia ERP domain.
"""

from app.domains.excelencia.domain.value_objects.erp_types import (
    LicenseType,
    ModuleType,
    SupportPriority,
    SupportTicketStatus,
)

__all__ = [
    "ModuleType",
    "SupportTicketStatus",
    "SupportPriority",
    "LicenseType",
]
