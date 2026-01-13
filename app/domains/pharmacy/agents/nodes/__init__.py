"""
Pharmacy Domain Graph Nodes

LangGraph nodes for processing pharmacy workflow steps.

V1 Nodes (Legacy):
- ConfirmationNode, CustomerIdentificationNode, etc.
- 9+ specialized nodes with complex state dependencies

V2 Nodes (Simplified - USE_PHARMACY_V2=true):
- router_supervisor_node: DB-driven routing with context switching
- response_formatter_node: WhatsApp buttons/lists formatting
- 6 main nodes total (router, auth, debt, payment, account, response)
"""

# === V1 Nodes (Legacy) ===
from app.domains.pharmacy.agents.nodes.confirmation_node import ConfirmationNode
from app.domains.pharmacy.agents.nodes.customer_identification_node import (
    CustomerIdentificationNode,
)
from app.domains.pharmacy.agents.nodes.customer_registration_node import (
    CustomerRegistrationNode,
)
from app.domains.pharmacy.agents.nodes.debt_check_node import DebtCheckNode
from app.domains.pharmacy.agents.nodes.invoice_generation_node import (
    InvoiceGenerationNode,
)
from app.domains.pharmacy.agents.nodes.payment_link_node import PaymentLinkNode
from app.domains.pharmacy.agents.nodes.person_resolution_node import (
    PersonResolutionNode,
)
from app.domains.pharmacy.agents.nodes.person_selection_node import PersonSelectionNode
from app.domains.pharmacy.agents.nodes.person_validation_node import (
    PersonValidationNode,
)

# === V2 Nodes (Simplified) ===
from app.domains.pharmacy.agents.nodes.router_supervisor import (
    RouterSupervisor,
    router_supervisor_node,
)
from app.domains.pharmacy.agents.nodes.response_formatter import (
    ResponseFormatter,
    response_formatter_node,
)

__all__ = [
    # V1 Nodes (Legacy)
    "ConfirmationNode",
    "CustomerIdentificationNode",
    "CustomerRegistrationNode",
    "DebtCheckNode",
    "InvoiceGenerationNode",
    "PaymentLinkNode",
    "PersonResolutionNode",
    "PersonSelectionNode",
    "PersonValidationNode",
    # V2 Nodes (Simplified)
    "RouterSupervisor",
    "router_supervisor_node",
    "ResponseFormatter",
    "response_formatter_node",
]
