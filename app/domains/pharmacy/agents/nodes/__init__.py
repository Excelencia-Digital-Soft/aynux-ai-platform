"""
Pharmacy Domain Graph Nodes - V2

LangGraph nodes for processing pharmacy workflow steps.

V2 Nodes Architecture:
- router_supervisor: DB-driven routing with context switching
- auth_plex: DNI validation, PLEX customer lookup, name verification
- debt_manager: Debt fetch from PLEX, formatting, payment options
- payment_processor: Payment confirmation and Mercado Pago integration
- account_switcher: Multiple registered accounts handling
- info_node: Pharmacy information queries
- response_formatter: WhatsApp buttons/lists formatting
"""

from app.domains.pharmacy.agents.nodes.account_switcher_node import (
    AccountSwitcherService,
    account_switcher_node,
)

# Business Logic Nodes
from app.domains.pharmacy.agents.nodes.auth_plex_node import (
    AuthPlexService,
    auth_plex_node,
)
from app.domains.pharmacy.agents.nodes.debt_manager_node import (
    DebtManagerService,
    debt_manager_node,
)
from app.domains.pharmacy.agents.nodes.info_node import (
    info_node,
)
from app.domains.pharmacy.agents.nodes.payment_processor_node import (
    PaymentProcessorService,
    payment_processor_node,
)
from app.domains.pharmacy.agents.nodes.response_formatter import (
    ResponseFormatter,
    response_formatter_node,
)

# Router and Response Formatter
from app.domains.pharmacy.agents.nodes.router_supervisor import (
    RouterSupervisor,
    router_supervisor_node,
)

__all__ = [
    # Router
    "RouterSupervisor",
    "router_supervisor_node",
    # Response Formatter
    "ResponseFormatter",
    "response_formatter_node",
    # Auth
    "auth_plex_node",
    "AuthPlexService",
    # Debt
    "debt_manager_node",
    "DebtManagerService",
    # Payment
    "payment_processor_node",
    "PaymentProcessorService",
    # Account
    "account_switcher_node",
    "AccountSwitcherService",
    # Info
    "info_node",
]
