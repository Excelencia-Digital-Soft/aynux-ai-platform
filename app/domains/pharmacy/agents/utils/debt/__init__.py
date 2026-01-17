# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Debt management utilities for pharmacy domain.
#              Extracted from debt_manager_node.py for SRP compliance.
# Tenant-Aware: Yes - organization_id handling and config loading.
# ============================================================================
"""
Debt management utilities for pharmacy domain.

This module provides:
- organization_resolver: Organization ID normalization
- debt_data_preparer: Fetch and prepare debt data
- invoice_handler: Invoice selection and aggregation
- payment_amount_extractor: Payment amount extraction from messages
"""

from app.domains.pharmacy.agents.utils.debt.debt_data_preparer import (
    DebtDataPreparer,
    PreparedDebtData,
)
from app.domains.pharmacy.agents.utils.debt.invoice_handler import (
    InvoiceData,
    InvoiceHandler,
)
from app.domains.pharmacy.agents.utils.debt.organization_resolver import (
    SYSTEM_ORG_ID,
    OrganizationResolver,
)
from app.domains.pharmacy.agents.utils.debt.payment_amount_extractor import (
    PaymentAmountExtractor,
    PaymentPatternProvider,
)

__all__ = [
    # Organization
    "OrganizationResolver",
    "SYSTEM_ORG_ID",
    # Debt Data
    "DebtDataPreparer",
    "PreparedDebtData",
    # Invoice
    "InvoiceHandler",
    "InvoiceData",
    # Payment
    "PaymentAmountExtractor",
    "PaymentPatternProvider",
]
