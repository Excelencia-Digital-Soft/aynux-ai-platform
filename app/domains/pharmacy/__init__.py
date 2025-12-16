"""
Pharmacy Domain

Business domain for pharmacy operations including debt management,
confirmations, and invoice generation via external ERP integration.

Architecture:
- agents/: PharmacyOperationsAgent with LangGraph subgraph
- application/: Use cases and port interfaces
- domain/: Entities and value objects
- infrastructure/: External service adapters

Note: PharmacyOperationsAgent is NOT imported here to avoid circular imports.
Import directly from: app.domains.pharmacy.agents.pharmacy_operations_agent
"""

__all__: list[str] = []
