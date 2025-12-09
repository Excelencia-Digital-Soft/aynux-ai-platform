"""
Pharmacy Domain

Business domain for pharmacy operations including debt management,
confirmations, and invoice generation via external ERP integration.

Architecture:
- agents/: PharmacyOperationsAgent with LangGraph subgraph
- application/: Use cases and port interfaces
- domain/: Entities and value objects
- infrastructure/: External service adapters
"""

from app.domains.pharmacy.agents import PharmacyOperationsAgent

__all__ = ["PharmacyOperationsAgent"]
