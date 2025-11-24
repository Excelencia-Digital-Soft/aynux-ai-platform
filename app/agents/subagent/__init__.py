"""
Agentes especializados del sistema
"""

# Explicit imports for better type checking and reliability
from .data_insights_agent import DataInsightsAgent
from .excelencia_agent import ExcelenciaAgent
from .fallback_agent import FallbackAgent
from .farewell_agent import FarewellAgent
from .greeting_agent import GreetingAgent
from .invoice_agent import InvoiceAgent
from .orchestrator_agent import OrchestratorAgent
from .promotions_agent import PromotionsAgent

# Use refactored SOLID-compliant ProductAgent
from .refactored_product_agent import RefactoredProductAgent as ProductAgent
from .supervisor_agent import SupervisorAgent
from .support_agent import SupportAgent
from .tracking_agent import TrackingAgent

# Export all agent classes
__all__ = [
    "DataInsightsAgent",
    "ExcelenciaAgent",
    "FallbackAgent",
    "FarewellAgent",
    "GreetingAgent",
    "InvoiceAgent",
    "OrchestratorAgent",
    "ProductAgent",
    "PromotionsAgent",
    "SupervisorAgent",
    "SupportAgent",
    "TrackingAgent",
]
