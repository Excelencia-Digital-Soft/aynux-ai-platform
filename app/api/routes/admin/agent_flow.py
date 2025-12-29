# ============================================================================
# SCOPE: DUAL-MODE (Global + Multi-Tenant)
# Description: Admin API para visualización del flujo de agentes.
#              Soporta modo global (sin org_id) y multi-tenant (con org_id).
# Tenant-Aware: Conditional - depends on MULTI_TENANT_MODE setting.
# ============================================================================
"""
Agent Flow Visualization API - Visualization data for agent system architecture.

Provides endpoints for fetching agent flow visualization data including:
- Agent definitions and their domains
- Bypass rules and their routing
- Orchestrator routes and intent mappings
- Domain groupings

Supports dual-mode operation:
- Global Mode: Returns agents from ENABLED_AGENTS env var, no bypass rules
- Multi-tenant Mode: Returns per-organization agent config and bypass rules
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_organization_by_id, require_admin
from app.config.settings import get_settings
from app.core.agents.builtin_agents import BUILTIN_AGENT_DEFAULTS
from app.core.schemas.agent_schema import DEFAULT_AGENT_SCHEMA, AgentType
from app.database.async_db import get_async_db
from app.models.db.tenancy import BypassRule, Organization, OrganizationUser, TenantAgent, TenantConfig

router = APIRouter(tags=["Agent Flow Visualization"])

settings = get_settings()


# ============================================================
# SCHEMAS
# ============================================================


class AgentVisualization(BaseModel):
    """Agent visualization data."""

    id: str
    agent_key: str
    display_name: str
    description: str | None = None
    domain_key: str | None = None
    enabled: bool = True
    priority: int = 0
    keywords: list[str] = Field(default_factory=list)
    primary_intents: list[str] = Field(default_factory=list)
    requires_postgres: bool = False
    requires_pgvector: bool = False
    requires_external_apis: bool = False
    icon: str = "pi-android"
    node_color: str = "#3b82f6"


class BypassRuleVisualization(BaseModel):
    """Bypass rule visualization data."""

    id: str
    rule_name: str
    description: str | None = None
    rule_type: str
    pattern: str | None = None
    phone_numbers: list[str] | None = None
    phone_number_id: str | None = None
    target_agent: str
    target_domain: str | None = None
    priority: int = 0
    enabled: bool = True


class DomainGroup(BaseModel):
    """Domain group for visualization."""

    domain_key: str
    display_name: str
    description: str = ""
    color: str = "#3b82f6"


class OrchestratorRoute(BaseModel):
    """Orchestrator routing configuration."""

    intent: str
    target_agent: str
    confidence_threshold: float = 0.75
    description: str | None = None


class IntentMapping(BaseModel):
    """Intent mapping for visualization."""

    intent: str
    description: str
    examples: list[str] = Field(default_factory=list)
    target_agent: str


class AgentFlowVisualization(BaseModel):
    """Complete visualization data response."""

    agents: list[AgentVisualization]
    bypass_rules: list[BypassRuleVisualization]
    domains: list[DomainGroup]
    orchestrator_routes: list[OrchestratorRoute]
    intent_mappings: list[IntentMapping]
    organization_id: str | None = None
    tenant_enabled_agents: list[str]
    default_domain: str = "excelencia"
    is_multi_tenant: bool = False


# ============================================================
# HELPER FUNCTIONS
# ============================================================

# Domain configuration
DOMAIN_CONFIG: dict[str, dict[str, str]] = {
    "system": {"display_name": "Sistema", "color": "#64748b"},
    "global": {"display_name": "Global", "color": "#3b82f6"},
    "excelencia": {"display_name": "Excelencia Software", "color": "#8b5cf6"},
    "ecommerce": {"display_name": "E-commerce", "color": "#10b981"},
    "pharmacy": {"display_name": "Farmacia", "color": "#14b8a6"},
    "credit": {"display_name": "Credito", "color": "#f59e0b"},
}

# Agent type to icon mapping
AGENT_ICONS: dict[str, str] = {
    "greeting_agent": "pi-comments",
    "farewell_agent": "pi-sign-out",
    "fallback_agent": "pi-question-circle",
    "support_agent": "pi-headphones",
    "excelencia_agent": "pi-building",
    "excelencia_invoice_agent": "pi-file-edit",
    "excelencia_promotions_agent": "pi-tag",
    "excelencia_support_agent": "pi-wrench",
    "data_insights_agent": "pi-chart-bar",
    "ecommerce_agent": "pi-shopping-cart",
    "pharmacy_operations_agent": "pi-heart",
    "credit_agent": "pi-wallet",
    "orchestrator": "pi-sitemap",
    "supervisor": "pi-eye",
}


def get_domain_for_agent(agent_key: str) -> str | None:
    """Get domain key for an agent."""
    # Check builtin defaults first
    if agent_key in BUILTIN_AGENT_DEFAULTS:
        return BUILTIN_AGENT_DEFAULTS[agent_key].get("domain_key")

    # Check agent schema
    try:
        agent_type = AgentType(agent_key)
        agent_def = DEFAULT_AGENT_SCHEMA.get_agent_definition(agent_type)
        if agent_def:
            # Infer domain from agent name
            if "excelencia" in agent_key:
                return "excelencia"
            if "ecommerce" in agent_key or "product" in agent_key:
                return "ecommerce"
            if "pharmacy" in agent_key:
                return "pharmacy"
            if "credit" in agent_key:
                return "credit"
    except ValueError:
        pass

    return None


def build_agent_visualization_from_schema(agent_key: str, enabled: bool = True) -> AgentVisualization:
    """Build AgentVisualization from DEFAULT_AGENT_SCHEMA."""
    # Get agent definition from schema
    try:
        agent_type = AgentType(agent_key)
        agent_def = DEFAULT_AGENT_SCHEMA.get_agent_definition(agent_type)
    except ValueError:
        agent_def = None

    # Get builtin config
    builtin_config = BUILTIN_AGENT_DEFAULTS.get(agent_key, {})

    # Build visualization data
    display_name = agent_def.display_name if agent_def else agent_key.replace("_", " ").title()
    description = agent_def.description if agent_def else None
    domain_key = get_domain_for_agent(agent_key)

    # Get primary intents
    primary_intents: list[str] = []
    if agent_def:
        primary_intents = [i.value for i in agent_def.primary_intents]

    # Get keywords from builtin config
    keywords = builtin_config.get("keywords", [])

    # Get requirements
    requires_postgres = agent_def.requires_postgres if agent_def else False
    requires_pgvector = agent_def.requires_pgvector if agent_def else False
    requires_external_apis = agent_def.requires_external_apis if agent_def else False

    # Get icon and color
    icon = AGENT_ICONS.get(agent_key, "pi-android")
    node_color = DOMAIN_CONFIG.get(domain_key or "global", {}).get("color", "#3b82f6")

    return AgentVisualization(
        id=agent_key,
        agent_key=agent_key,
        display_name=display_name,
        description=description,
        domain_key=domain_key,
        enabled=enabled,
        priority=builtin_config.get("priority", 0),
        keywords=keywords[:10],  # Limit keywords for visualization
        primary_intents=primary_intents,
        requires_postgres=requires_postgres,
        requires_pgvector=requires_pgvector,
        requires_external_apis=requires_external_apis,
        icon=icon,
        node_color=node_color,
    )


def build_orchestrator_routes() -> list[OrchestratorRoute]:
    """Build orchestrator routes from DEFAULT_AGENT_SCHEMA."""
    routes = []
    for intent_type, intent_def in DEFAULT_AGENT_SCHEMA.intents.items():
        routes.append(
            OrchestratorRoute(
                intent=intent_type.value,
                target_agent=intent_def.target_agent.value,
                confidence_threshold=intent_def.confidence_threshold,
                description=intent_def.description,
            )
        )
    return routes


def build_intent_mappings() -> list[IntentMapping]:
    """Build intent mappings from DEFAULT_AGENT_SCHEMA."""
    mappings = []
    for intent_type, intent_def in DEFAULT_AGENT_SCHEMA.intents.items():
        mappings.append(
            IntentMapping(
                intent=intent_type.value,
                description=intent_def.description,
                examples=intent_def.examples[:5],  # Limit examples
                target_agent=intent_def.target_agent.value,
            )
        )
    return mappings


def build_domain_groups() -> list[DomainGroup]:
    """Build domain groups for visualization."""
    return [
        DomainGroup(
            domain_key=key,
            display_name=config["display_name"],
            color=config["color"],
        )
        for key, config in DOMAIN_CONFIG.items()
        if key not in ("system",)  # Exclude system domain from visualization
    ]


# ============================================================
# GLOBAL MODE ENDPOINTS (No org_id required)
# ============================================================


@router.get("/agent-flow/visualization", response_model=AgentFlowVisualization)
async def get_global_visualization():
    """
    Get agent flow visualization data for Global Mode.

    Returns:
    - Agents from ENABLED_AGENTS environment variable
    - Empty bypass_rules (not applicable in global mode)
    - Orchestrator routes from DEFAULT_AGENT_SCHEMA
    - Intent mappings from DEFAULT_AGENT_SCHEMA

    This endpoint is used when MULTI_TENANT_MODE=false.
    """
    # Get enabled agents from settings
    enabled_agents = settings.effective_enabled_agents

    # Build agent visualizations
    agents = []
    for agent_key in enabled_agents:
        agents.append(build_agent_visualization_from_schema(agent_key, enabled=True))

    # Add orchestrator and supervisor (always present but not in enabled_agents)
    for system_agent in ["orchestrator", "supervisor"]:
        agents.append(
            AgentVisualization(
                id=system_agent,
                agent_key=system_agent,
                display_name=system_agent.title(),
                description="System agent for routing and supervision",
                domain_key="system",
                enabled=True,
                priority=100,
                keywords=[],
                primary_intents=[],
                requires_postgres=False,
                requires_pgvector=False,
                requires_external_apis=False,
                icon=AGENT_ICONS.get(system_agent, "pi-cog"),
                node_color=DOMAIN_CONFIG["system"]["color"],
            )
        )

    return AgentFlowVisualization(
        agents=agents,
        bypass_rules=[],  # No bypass rules in global mode
        domains=build_domain_groups(),
        orchestrator_routes=build_orchestrator_routes(),
        intent_mappings=build_intent_mappings(),
        organization_id=None,
        tenant_enabled_agents=enabled_agents,
        default_domain="excelencia",
        is_multi_tenant=False,
    )


# ============================================================
# MULTI-TENANT MODE ENDPOINTS (org_id required)
# ============================================================

# Type aliases
OrgIdPath = Annotated[uuid.UUID, Path(description="Organization ID")]
AdminMembership = Annotated[OrganizationUser, Depends(require_admin)]
OrgDep = Annotated[Organization, Depends(get_organization_by_id)]
DbSession = Annotated[AsyncSession, Depends(get_async_db)]


@router.get("/{org_id}/agent-flow/visualization", response_model=AgentFlowVisualization)
async def get_tenant_visualization(
    org_id: OrgIdPath,
    membership: AdminMembership,
    org: OrgDep,
    db: DbSession,
):
    """
    Get agent flow visualization data for a specific organization.

    Returns:
    - Agents: BOTH global (from ENABLED_AGENTS) AND organization-specific (from tenant_agents)
    - Bypass rules for this organization
    - Orchestrator routes from DEFAULT_AGENT_SCHEMA
    - Intent mappings from DEFAULT_AGENT_SCHEMA

    Requires admin or owner role.
    """
    # Get tenant agents
    stmt = select(TenantAgent).where(TenantAgent.organization_id == org_id)
    result = await db.execute(stmt)
    tenant_agents = result.scalars().all()

    # Get bypass rules
    stmt = select(BypassRule).where(BypassRule.organization_id == org_id).order_by(desc(BypassRule.priority))
    result = await db.execute(stmt)
    bypass_rules_db = result.scalars().all()

    # Get tenant config for default domain
    stmt = select(TenantConfig).where(TenantConfig.organization_id == org_id)
    result = await db.execute(stmt)
    tenant_config = result.scalar_one_or_none()

    default_domain = "excelencia"
    if tenant_config and tenant_config.default_domain:
        default_domain = tenant_config.default_domain

    # Build agent visualizations - combining GLOBAL + ORGANIZATIONAL
    agents = []
    enabled_agent_keys = []
    tenant_agent_keys = {ta.agent_key for ta in tenant_agents}

    # 1. Add GLOBAL agents from ENABLED_AGENTS (that are NOT overridden by tenant)
    global_enabled_agents = settings.effective_enabled_agents
    for agent_key in global_enabled_agents:
        if agent_key not in tenant_agent_keys:
            # Add global agent (not customized by tenant)
            agent_viz = build_agent_visualization_from_schema(agent_key, enabled=True)
            agent_viz.id = f"global-{agent_key}"  # Mark as global
            agents.append(agent_viz)
            enabled_agent_keys.append(agent_key)

    # 2. Add ORGANIZATIONAL agents from tenant_agents table
    for ta in tenant_agents:
        agent_key = ta.agent_key
        enabled_agent_keys.append(agent_key)

        # Get base visualization from schema
        agent_viz = build_agent_visualization_from_schema(agent_key, enabled=ta.enabled)

        # Override with tenant-specific config
        agent_viz.id = str(ta.id)
        agent_viz.priority = ta.priority or 0

        # Override display name if customized
        if ta.display_name:
            agent_viz.display_name = ta.display_name

        # Override domain if specified
        if ta.domain_key:
            agent_viz.domain_key = ta.domain_key
            agent_viz.node_color = DOMAIN_CONFIG.get(ta.domain_key, {}).get("color", "#3b82f6")

        agents.append(agent_viz)

    # Add system agents
    for system_agent in ["orchestrator", "supervisor"]:
        agents.append(
            AgentVisualization(
                id=system_agent,
                agent_key=system_agent,
                display_name=system_agent.title(),
                description="System agent for routing and supervision",
                domain_key="system",
                enabled=True,
                priority=100,
                keywords=[],
                primary_intents=[],
                requires_postgres=False,
                requires_pgvector=False,
                requires_external_apis=False,
                icon=AGENT_ICONS.get(system_agent, "pi-cog"),
                node_color=DOMAIN_CONFIG["system"]["color"],
            )
        )

    # Build bypass rule visualizations
    bypass_rules = []
    for rule in bypass_rules_db:
        bypass_rules.append(
            BypassRuleVisualization(
                id=str(rule.id),
                rule_name=rule.rule_name,
                description=rule.description,
                rule_type=rule.rule_type,
                pattern=rule.pattern,
                phone_numbers=rule.phone_numbers,
                phone_number_id=rule.phone_number_id,
                target_agent=rule.target_agent,
                target_domain=rule.target_domain,
                priority=rule.priority,
                enabled=rule.enabled,
            )
        )

    return AgentFlowVisualization(
        agents=agents,
        bypass_rules=bypass_rules,
        domains=build_domain_groups(),
        orchestrator_routes=build_orchestrator_routes(),
        intent_mappings=build_intent_mappings(),
        organization_id=str(org_id),
        tenant_enabled_agents=[a for a in enabled_agent_keys if any(ag.agent_key == a and ag.enabled for ag in agents)],
        default_domain=default_domain,
        is_multi_tenant=True,
    )
