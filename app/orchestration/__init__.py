"""
Orchestration Module

Multi-domain orchestration and routing.

This module provides:
- SuperOrchestrator: High-level domain routing (ecommerce, credit, excelencia, healthcare)
- DomainRouter: Routes messages to appropriate domain services
- ContextManager: Manages conversation context across domains
- OrchestrationState: Shared state schema for orchestration
- Routing Strategies: Keyword, AI, and Hybrid routing

Domain Graphs are available via direct import from their respective modules:
- app.domains.ecommerce.agents: EcommerceGraph, EcommerceState
- app.domains.credit.agents: CreditGraph, CreditState
- app.domains.excelencia.agents: ExcelenciaGraph, ExcelenciaState
- app.domains.healthcare.agents: HealthcareGraph, HealthcareState
"""

# High-level domain orchestrator
# Re-export graph-level agents from their new locations
# These are tightly coupled with the LangGraph execution model
from app.core.graph.agents import OrchestratorAgent, SupervisorAgent

# Context management
from .context_manager import (
    ContextManager,
    ConversationContext,
    get_context_manager,
)

# Domain routing
from .domain_router import DomainRouter, RoutingDecision

# Domain state registry
from .domain_state_registry import DomainStateRegistry

# Orchestration state
from .state import (
    DomainContext,
    OrchestrationState,
    create_initial_state,
    ensure_domain_initialized,
    extract_domain_context,
    extract_domain_fields_from_result,
    # Domain state helpers
    get_domain_state,
    update_domain_state,
    update_state_after_domain,
)

# Routing strategies
from .strategies import (
    AIBasedRoutingStrategy,
    DomainDescription,
    DomainKeywords,
    HybridRoutingStrategy,
    KeywordRoutingStrategy,
)
from .super_orchestrator import SuperOrchestrator

__all__ = [
    # Super Orchestrator (domain-level routing)
    "SuperOrchestrator",
    # Domain Router
    "DomainRouter",
    "RoutingDecision",
    # Context Manager
    "ContextManager",
    "ConversationContext",
    "get_context_manager",
    # Orchestration State
    "OrchestrationState",
    "DomainContext",
    "create_initial_state",
    "extract_domain_context",
    "update_state_after_domain",
    # Domain state helpers
    "get_domain_state",
    "update_domain_state",
    "ensure_domain_initialized",
    "extract_domain_fields_from_result",
    # Domain state registry
    "DomainStateRegistry",
    # Routing Strategies
    "KeywordRoutingStrategy",
    "AIBasedRoutingStrategy",
    "HybridRoutingStrategy",
    "DomainKeywords",
    "DomainDescription",
    # Graph-level agents
    "OrchestratorAgent",
    "SupervisorAgent",
]
