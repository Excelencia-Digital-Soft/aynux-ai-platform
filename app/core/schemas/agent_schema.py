"""
Agent Schema - Centralized configuration for all agents, intents, and mappings.

This module provides a single source of truth for all agent-related configurations,
including intent definitions, agent mappings, routing logic, and descriptions.
"""

from enum import Enum
from typing import Dict, List, Optional, Set, Union

from pydantic import BaseModel, Field, field_validator


class IntentType(str, Enum):
    """Enumeration of all valid intent types."""

    SALUDO = "saludo"
    # E-commerce intents (consolidated - all route to ECOMMERCE_AGENT)
    ECOMMERCE = "ecommerce"  # Consolidated e-commerce intent
    PRODUCTO = "producto"  # Routes to ecommerce_agent
    PROMOCIONES = "promociones"  # E-commerce promotions → ecommerce_agent
    SEGUIMIENTO = "seguimiento"  # E-commerce tracking → ecommerce_agent
    FACTURACION = "facturacion"  # E-commerce invoices → ecommerce_agent
    # Excelencia-specific intents (NEW)
    EXCELENCIA = "excelencia"  # General Excelencia queries
    EXCELENCIA_FACTURACION = "excelencia_facturacion"  # Excelencia client invoices
    EXCELENCIA_PROMOCIONES = "excelencia_promociones"  # Excelencia software promotions
    EXCELENCIA_SOPORTE = "excelencia_soporte"  # Excelencia software support/incidents
    # Pharmacy domain intents
    PHARMACY = "pharmacy"  # Pharmacy debt queries, confirmations, invoices
    # Other intents
    DATOS = "datos"  # Data insights (Excelencia domain)
    SOPORTE = "soporte"  # Support (always available)
    FALLBACK = "fallback"
    DESPEDIDA = "despedida"
    # Conversational flow intents
    FOLLOW_UP = "follow_up"  # Response to a previous question from the assistant


class AgentType(str, Enum):
    """Enumeration of all valid agent types."""

    # System agents (always active)
    ORCHESTRATOR = "orchestrator"
    SUPERVISOR = "supervisor"

    # Always available agents (domain_key=None)
    GREETING_AGENT = "greeting_agent"
    FAREWELL_AGENT = "farewell_agent"
    FALLBACK_AGENT = "fallback_agent"
    SUPPORT_AGENT = "support_agent"  # Enhanced for Excelencia software knowledge

    # Excelencia domain agents (domain_key="excelencia")
    EXCELENCIA_AGENT = "excelencia_agent"  # Company info, modules, mission/vision
    EXCELENCIA_INVOICE_AGENT = "excelencia_invoice_agent"  # Client invoices
    EXCELENCIA_PROMOTIONS_AGENT = "excelencia_promotions_agent"  # Software promotions
    EXCELENCIA_SUPPORT_AGENT = "excelencia_support_agent"  # Software support/incidents
    DATA_INSIGHTS_AGENT = "data_insights_agent"  # Software analytics (moved to Excelencia)

    # E-commerce domain agents (domain_key="ecommerce")
    ECOMMERCE_AGENT = "ecommerce_agent"  # Subgraph with product, tracking, promotions, invoice nodes
    # Legacy e-commerce agents (deprecated - use ECOMMERCE_AGENT)
    PRODUCT_AGENT = "product_agent"
    PROMOTIONS_AGENT = "promotions_agent"
    TRACKING_AGENT = "tracking_agent"
    INVOICE_AGENT = "invoice_agent"

    # Credit domain (domain_key="credit")
    CREDIT = "credit_agent"

    # Pharmacy domain (domain_key="pharmacy")
    PHARMACY_OPERATIONS_AGENT = "pharmacy_operations_agent"


class IntentDefinition(BaseModel):
    """Definition of a single intent with its metadata."""

    intent: IntentType
    description: str = Field(..., description="Brief description of the intent")
    examples: List[str] = Field(..., description="Example phrases for this intent")
    target_agent: AgentType = Field(..., description="Agent that handles this intent")
    requires_handoff: bool = Field(default=False, description="Whether this intent requires human handoff")
    confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0, description="Minimum confidence threshold")


class AgentDefinition(BaseModel):
    """Definition of a single agent with its metadata."""

    agent: AgentType
    class_name: str = Field(..., description="Python class name for the agent")
    display_name: str = Field(..., description="Human-readable display name")
    description: str = Field(..., description="Description of agent functionality")
    primary_intents: List[IntentType] = Field(..., description="Primary intents handled by this agent")
    fallback_intents: List[IntentType] = Field(
        default_factory=list, description="Fallback intents this agent can handle"
    )
    requires_postgres: bool = Field(default=False, description="Whether agent requires PostgreSQL connection")
    requires_pgvector: bool = Field(default=False, description="Whether agent requires pgvector for semantic search")
    requires_external_apis: bool = Field(default=False, description="Whether agent requires external API access")
    config_key: str = Field(..., description="Configuration key for agent-specific settings")


class AgentSchema(BaseModel):
    """Complete schema for all agents, intents, and their relationships."""

    # Intent definitions
    intents: Dict[IntentType, IntentDefinition] = Field(..., description="All intent definitions")

    # Agent definitions
    agents: Dict[AgentType, AgentDefinition] = Field(..., description="All agent definitions")

    # Global configuration
    default_confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    default_fallback_agent: AgentType = Field(default=AgentType.FALLBACK_AGENT)
    human_handoff_intents: Set[str] = Field(default_factory=set, description="Intents requiring human handoff")

    # Routing configuration
    intent_cache_ttl: int = Field(default=300, description="Intent cache TTL in seconds")
    enable_fallback: bool = Field(default=True, description="Whether to enable fallback routing")

    @field_validator("intents")
    @classmethod
    def validate_intent_agent_mapping(cls, v: Dict[IntentType, IntentDefinition], info):
        """Validate that all intents have valid target agents."""
        if info.data.get("agents"):
            agent_types = set(info.data["agents"].keys())
            for intent_def in v.values():
                if intent_def.target_agent not in agent_types:
                    raise ValueError(f"Intent {intent_def.intent} targets unknown agent {intent_def.target_agent}")
        return v

    # Computed properties
    @property
    def intent_names(self) -> List[str]:
        """Get list of all intent names."""
        return [intent.value for intent in self.intents.keys()]

    @property
    def agent_names(self) -> List[str]:
        """Get list of all agent names."""
        return [agent.value for agent in self.agents.keys()]

    @property
    def graph_node_names(self) -> List[str]:
        """Get list of all graph node names (excludes orchestrator and supervisor)."""
        return [
            agent.value for agent in self.agents.keys() if agent not in (AgentType.ORCHESTRATOR, AgentType.SUPERVISOR)
        ]

    @property
    def intent_to_agent_mapping(self) -> Dict[str, str]:
        """Get mapping from intent names to agent names."""
        return {intent.value: definition.target_agent.value for intent, definition in self.intents.items()}

    @property
    def agent_class_mapping(self) -> Dict[str, str]:
        """Get mapping from agent names to class names."""
        return {agent.value: definition.class_name for agent, definition in self.agents.items()}

    @property
    def postgres_agents(self) -> List[str]:
        """Get list of agents that require PostgreSQL."""
        return [agent.value for agent, definition in self.agents.items() if definition.requires_postgres]

    @property
    def pgvector_agents(self) -> List[str]:
        """Get list of agents that require pgvector."""
        return [agent.value for agent, definition in self.agents.items() if definition.requires_pgvector]

    def get_intent_definition(self, intent: Union[str, IntentType]) -> Optional[IntentDefinition]:
        """Get intent definition by intent name or type."""
        if isinstance(intent, str):
            intent = IntentType(intent)
        return self.intents.get(intent)

    def get_agent_definition(self, agent: Union[str, AgentType]) -> Optional[AgentDefinition]:
        """Get agent definition by agent name or type."""
        if isinstance(agent, str):
            agent = AgentType(agent)
        return self.agents.get(agent)

    def get_agent_for_intent(self, intent: Union[str, IntentType]) -> Optional[str]:
        """Get agent name for a given intent."""
        intent_def = self.get_intent_definition(intent)
        return intent_def.target_agent.value if intent_def else None


# Default schema configuration
DEFAULT_AGENT_SCHEMA = AgentSchema(
    intents={
        IntentType.SALUDO: IntentDefinition(
            intent=IntentType.SALUDO,
            description="Greetings, welcome messages, and initial system capability inquiries",
            examples=[
                "hello",
                "hi",
                "hola",
                "buenos días",
                "good morning",
                "hey there",
                "greetings",
                "buenas tardes",
                "good afternoon",
                "hey",
                "hi there",
                "hello there",
            ],
            target_agent=AgentType.GREETING_AGENT,
            confidence_threshold=0.8,
        ),
        IntentType.PRODUCTO: IntentDefinition(
            intent=IntentType.PRODUCTO,
            description=(
                "Questions about available products, general product searches, " "categories, features, price, stock"
            ),
            examples=[
                "what products do you have?",
                "show me the products",
                "do you have the iphone 15 in stock?",
                "how much does it cost?",
                "what are the features of this product?",
                "list of available products",
                "what do you sell?",
                "show me laptops",
                "what categories do you have?",
                "products in electronics category",
                "list all product categories",
                "show me sneakers",
                "I'm looking for televisions",
                "technology products",
                "gaming laptops",
            ],
            target_agent=AgentType.ECOMMERCE_AGENT,  # Routes to ecommerce subgraph
            confidence_threshold=0.8,
        ),
        IntentType.DATOS: IntentDefinition(
            intent=IntentType.DATOS,
            description="Analytical or reporting queries",
            examples=[
                "how many sales were there yesterday?",
                "total registered users",
                "what is the best-selling product?",
                "sales statistics",
            ],
            target_agent=AgentType.DATA_INSIGHTS_AGENT,
            confidence_threshold=0.85,
        ),
        IntentType.SOPORTE: IntentDefinition(
            intent=IntentType.SOPORTE,
            description="Technical problems, errors, help with the service or product",
            examples=[
                "the product arrived defective",
                "the product is not responding",
                "I have a problem with my purchase",
                "I need technical help",
            ],
            target_agent=AgentType.SUPPORT_AGENT,
            requires_handoff=True,
            confidence_threshold=0.7,
        ),
        IntentType.SEGUIMIENTO: IntentDefinition(
            intent=IntentType.SEGUIMIENTO,
            description="Status of an order or shipment",
            examples=[
                "where is my order?",
                "I want the tracking for my purchase",
                "when will my order arrive?",
                "shipment tracking",
            ],
            target_agent=AgentType.ECOMMERCE_AGENT,  # Routes to ecommerce subgraph
            confidence_threshold=0.8,
        ),
        IntentType.FACTURACION: IntentDefinition(
            intent=IntentType.FACTURACION,
            description="Payments, invoices, returns",
            examples=[
                "I need the invoice for my order",
                "how do I request a refund?",
                "problem with the payment",
                "I want my receipt",
            ],
            target_agent=AgentType.ECOMMERCE_AGENT,  # Routes to ecommerce subgraph
            confidence_threshold=0.8,
        ),
        IntentType.PROMOCIONES: IntentDefinition(
            intent=IntentType.PROMOCIONES,
            description="Discounts, coupons, offers",
            examples=[
                "is there a discount coupon?",
                "what offers do you have today?",
                "available discounts",
                "current promotions",
            ],
            target_agent=AgentType.ECOMMERCE_AGENT,  # Routes to ecommerce subgraph
            confidence_threshold=0.75,
        ),
        IntentType.EXCELENCIA: IntentDefinition(
            intent=IntentType.EXCELENCIA,
            description="Queries about Excelencia Software system: demos, modules, training, vertical products",
            examples=[
                "qué es excelencia?",
                "demo de historia clínica",
                "módulos de excelencia",
                "capacitación ERP",
                "sistema de turnos médicos",
                "software para hoteles",
                "gestión de obras sociales",
                "productos de excelencia",
                "what is excelencia?",
                "hospital management system",
                "ERP for healthcare",
                "hotel software",
                "clinic software",
                "medical appointments system",
            ],
            target_agent=AgentType.EXCELENCIA_AGENT,
            confidence_threshold=0.75,
        ),
        IntentType.EXCELENCIA_FACTURACION: IntentDefinition(
            intent=IntentType.EXCELENCIA_FACTURACION,
            description="Excelencia client invoicing: client invoices, account statements, collections, payments",
            examples=[
                "factura del cliente",
                "estado de cuenta del cliente",
                "cobranza pendiente",
                "pago de cliente",
                "deuda del cliente",
                "facturar al cliente",
                "generar factura cliente",
                "consultar factura de empresa",
                "invoice for client",
                "client account statement",
                "pending collections",
            ],
            target_agent=AgentType.EXCELENCIA_INVOICE_AGENT,
            confidence_threshold=0.75,
        ),
        IntentType.EXCELENCIA_PROMOCIONES: IntentDefinition(
            intent=IntentType.EXCELENCIA_PROMOCIONES,
            description="Excelencia software promotions: software discounts, module offers, implementation deals",
            examples=[
                "promoción de software",
                "descuento en módulo",
                "oferta de implementación",
                "promoción excelencia",
                "descuento capacitación",
                "oferta software hospitalario",
                "promo módulo turnos",
                "software promotion",
                "module discount",
                "implementation offer",
            ],
            target_agent=AgentType.EXCELENCIA_PROMOTIONS_AGENT,
            confidence_threshold=0.75,
        ),
        IntentType.EXCELENCIA_SOPORTE: IntentDefinition(
            intent=IntentType.EXCELENCIA_SOPORTE,
            description="Excelencia software support: incidents, bugs, errors, tickets, technical issues",
            examples=[
                "tengo una incidencia",
                "reportar un problema",
                "error en el módulo",
                "bug en facturación",
                "el sistema no funciona",
                "falla en el sistema",
                "levantar ticket",
                "problema técnico",
                "incidencia módulo",
                "report an issue",
                "system error",
            ],
            target_agent=AgentType.EXCELENCIA_SUPPORT_AGENT,
            confidence_threshold=0.7,
        ),
        IntentType.PHARMACY: IntentDefinition(
            intent=IntentType.PHARMACY,
            description="Pharmacy debt queries, confirmations, and invoice generation",
            examples=[
                "consultar deuda",
                "mi saldo",
                "cuanto debo",
                "deuda farmacia",
                "generar factura farmacia",
                "confirmar deuda",
                "estado de cuenta",
                "check my debt",
                "pharmacy invoice",
            ],
            target_agent=AgentType.PHARMACY_OPERATIONS_AGENT,
            confidence_threshold=0.75,
        ),
        IntentType.DESPEDIDA: IntentDefinition(
            intent=IntentType.DESPEDIDA,
            description="Conversation closing, thanks",
            examples=["that's all, thank you", "goodbye", "see you later", "thank you very much for the help"],
            target_agent=AgentType.FAREWELL_AGENT,
            confidence_threshold=0.8,
        ),
        IntentType.FALLBACK: IntentDefinition(
            intent=IntentType.FALLBACK,
            description="Greetings, vague questions, or when no other intent fits",
            examples=["hello", "ok", "do you have that?", "how are you?", "good morning"],
            target_agent=AgentType.FALLBACK_AGENT,
            confidence_threshold=0.4,
        ),
    },
    agents={
        AgentType.ORCHESTRATOR: AgentDefinition(
            agent=AgentType.ORCHESTRATOR,
            class_name="OrchestratorAgent",
            display_name="Orchestrator",
            description="Analyzes user intent and routes to appropriate specialized agents",
            primary_intents=[],
            config_key="orchestrator",
        ),
        AgentType.SUPERVISOR: AgentDefinition(
            agent=AgentType.SUPERVISOR,
            class_name="SupervisorAgent",
            display_name="Supervisor",
            description="Evaluates agent responses and manages conversation quality and flow",
            primary_intents=[],
            config_key="supervisor",
        ),
        AgentType.GREETING_AGENT: AgentDefinition(
            agent=AgentType.GREETING_AGENT,
            class_name="GreetingAgent",
            display_name="Greeting Agent",
            description="Handles greetings and provides comprehensive system capabilities overview",
            primary_intents=[IntentType.SALUDO],
            requires_postgres=False,
            requires_pgvector=False,
            requires_external_apis=False,
            config_key="greeting",
        ),
        # E-commerce domain agent (subgraph wrapper)
        AgentType.ECOMMERCE_AGENT: AgentDefinition(
            agent=AgentType.ECOMMERCE_AGENT,
            class_name="EcommerceAgent",
            display_name="E-commerce Agent",
            description=(
                "Handles all e-commerce domain queries through an intelligent subgraph. "
                "Routes to specialized nodes for products, promotions, tracking, and billing."
            ),
            primary_intents=[
                IntentType.PRODUCTO,
                IntentType.PROMOCIONES,
                IntentType.SEGUIMIENTO,
                IntentType.FACTURACION,
            ],
            requires_postgres=True,
            requires_pgvector=True,
            requires_external_apis=True,
            config_key="ecommerce",
        ),
        # Legacy product agent (deprecated - use ECOMMERCE_AGENT)
        AgentType.PRODUCT_AGENT: AgentDefinition(
            agent=AgentType.PRODUCT_AGENT,
            class_name="ProductAgent",
            display_name="Product Agent (Legacy)",
            description="[DEPRECATED] Use ECOMMERCE_AGENT instead. Handles product inquiries.",
            primary_intents=[IntentType.PRODUCTO],
            requires_postgres=True,
            config_key="product",
        ),
        AgentType.DATA_INSIGHTS_AGENT: AgentDefinition(
            agent=AgentType.DATA_INSIGHTS_AGENT,
            class_name="DataInsightsAgent",
            display_name="Data Insights Agent",
            description="Provides analytics, reports, and data insights",
            primary_intents=[IntentType.DATOS],
            requires_postgres=True,
            config_key="data_insights",
        ),
        AgentType.PROMOTIONS_AGENT: AgentDefinition(
            agent=AgentType.PROMOTIONS_AGENT,
            class_name="PromotionsAgent",
            display_name="Promotions Agent",
            description="Handles discounts, coupons, and promotional offers",
            primary_intents=[IntentType.PROMOCIONES],
            requires_pgvector=True,
            config_key="promotions",
        ),
        AgentType.TRACKING_AGENT: AgentDefinition(
            agent=AgentType.TRACKING_AGENT,
            class_name="TrackingAgent",
            display_name="Tracking Agent",
            description="Manages order tracking and shipping information",
            primary_intents=[IntentType.SEGUIMIENTO],
            requires_pgvector=True,
            requires_external_apis=True,
            config_key="tracking",
        ),
        AgentType.SUPPORT_AGENT: AgentDefinition(
            agent=AgentType.SUPPORT_AGENT,
            class_name="SupportAgent",
            display_name="Support Agent",
            description="Provides technical support and troubleshooting assistance",
            primary_intents=[IntentType.SOPORTE],
            requires_pgvector=True,
            config_key="support",
        ),
        AgentType.INVOICE_AGENT: AgentDefinition(
            agent=AgentType.INVOICE_AGENT,
            class_name="InvoiceAgent",
            display_name="Invoice Agent",
            description="Handles billing, invoices, and payment-related queries",
            primary_intents=[IntentType.FACTURACION],
            requires_pgvector=True,
            requires_external_apis=True,
            config_key="invoice",
        ),
        AgentType.EXCELENCIA_AGENT: AgentDefinition(
            agent=AgentType.EXCELENCIA_AGENT,
            class_name="ExcelenciaAgent",
            display_name="Excelencia Software Agent",
            description=(
                "Handles queries about Excelencia Software system: demos, modules, training, "
                "and vertical products (healthcare, hotels, social security)"
            ),
            primary_intents=[IntentType.EXCELENCIA],
            requires_postgres=True,
            requires_pgvector=True,
            config_key="excelencia",
        ),
        AgentType.EXCELENCIA_INVOICE_AGENT: AgentDefinition(
            agent=AgentType.EXCELENCIA_INVOICE_AGENT,
            class_name="ExcelenciaInvoiceAgent",
            display_name="Excelencia Invoice Agent",
            description=(
                "Handles Excelencia client invoicing: generates invoices, queries account statements, "
                "manages collections and client payments for Excelencia software services"
            ),
            primary_intents=[IntentType.EXCELENCIA_FACTURACION],
            requires_postgres=True,
            requires_pgvector=True,
            config_key="excelencia_invoice",
        ),
        AgentType.EXCELENCIA_PROMOTIONS_AGENT: AgentDefinition(
            agent=AgentType.EXCELENCIA_PROMOTIONS_AGENT,
            class_name="ExcelenciaPromotionsAgent",
            display_name="Excelencia Promotions Agent",
            description=(
                "Handles Excelencia software promotions: discounts on modules, "
                "implementation offers, training deals, and special pricing for software services"
            ),
            primary_intents=[IntentType.EXCELENCIA_PROMOCIONES],
            requires_postgres=True,
            requires_pgvector=True,
            config_key="excelencia_promotions",
        ),
        AgentType.EXCELENCIA_SUPPORT_AGENT: AgentDefinition(
            agent=AgentType.EXCELENCIA_SUPPORT_AGENT,
            class_name="ExcelenciaSupportAgent",
            display_name="Excelencia Support Agent",
            description=(
                "Handles Excelencia software support: technical incidents, bug reports, "
                "module errors, ticket creation, and troubleshooting for ERP software"
            ),
            primary_intents=[IntentType.EXCELENCIA_SOPORTE],
            requires_postgres=True,
            requires_pgvector=True,
            config_key="excelencia_support",
        ),
        AgentType.FALLBACK_AGENT: AgentDefinition(
            agent=AgentType.FALLBACK_AGENT,
            class_name="FallbackAgent",
            display_name="Fallback Agent",
            description="Handles general inquiries and provides fallback responses",
            primary_intents=[IntentType.FALLBACK],
            fallback_intents=[IntentType.PRODUCTO],
            requires_postgres=True,
            config_key="fallback",
        ),
        AgentType.FAREWELL_AGENT: AgentDefinition(
            agent=AgentType.FAREWELL_AGENT,
            class_name="FarewellAgent",
            display_name="Farewell Agent",
            description="Manages conversation closure and farewells",
            primary_intents=[IntentType.DESPEDIDA],
            requires_postgres=True,
            config_key="farewell",
        ),
        AgentType.PHARMACY_OPERATIONS_AGENT: AgentDefinition(
            agent=AgentType.PHARMACY_OPERATIONS_AGENT,
            class_name="PharmacyOperationsAgent",
            display_name="Pharmacy Operations Agent",
            description="Handles pharmacy debt workflows: check debt, confirm, generate invoice",
            primary_intents=[IntentType.PHARMACY],
            requires_postgres=False,
            requires_pgvector=False,
            requires_external_apis=True,
            config_key="pharmacy",
        ),
    },
    human_handoff_intents={"complaint", "legal_issue", "payment_problem", "urgent_support"},
    intent_cache_ttl=300,
    enable_fallback=True,
)


# Convenience functions for accessing schema data
def get_valid_intents() -> List[str]:
    """Get list of valid intent names."""
    return DEFAULT_AGENT_SCHEMA.intent_names


def get_valid_agents() -> List[str]:
    """Get list of valid agent names."""
    return DEFAULT_AGENT_SCHEMA.agent_names


def get_intent_to_agent_mapping() -> Dict[str, str]:
    """Get mapping from intent names to agent names."""
    return DEFAULT_AGENT_SCHEMA.intent_to_agent_mapping


def get_agent_class_mapping() -> Dict[str, str]:
    """Get mapping from agent names to class names."""
    return DEFAULT_AGENT_SCHEMA.agent_class_mapping


def get_graph_node_names() -> List[str]:
    """Get list of graph node names (excludes supervisor)."""
    return DEFAULT_AGENT_SCHEMA.graph_node_names


def get_intent_examples() -> Dict[str, List[str]]:
    """Get mapping from intent names to example phrases."""
    return {intent.value: definition.examples for intent, definition in DEFAULT_AGENT_SCHEMA.intents.items()}


def get_intent_descriptions() -> Dict[str, str]:
    """Get mapping from intent names to descriptions."""
    return {intent.value: definition.description for intent, definition in DEFAULT_AGENT_SCHEMA.intents.items()}


def build_intent_prompt_text() -> str:
    """Build the intent prompt text for LLM processing."""
    lines = ["Valid Intents and Examples:"]

    for intent, definition in DEFAULT_AGENT_SCHEMA.intents.items():
        examples_text = ", ".join([f'"{ex}"' for ex in definition.examples[:2]])  # Limit to 2 examples
        lines.append(f"- {intent.value}: {definition.description} ({examples_text})")

    return "\n".join(lines)


def get_agent_routing_literal():
    """
    Genera el tipo Literal dinámicamente para routing desde AgentType.

    Returns:
        Tipo Literal con todos los agentes válidos para routing más "__end__"
    """
    # Obtener todos los agentes especializados (excluye ORCHESTRATOR y SUPERVISOR)
    agent_names = [agent.value for agent in AgentType if agent not in (AgentType.ORCHESTRATOR, AgentType.SUPERVISOR)]
    # Agregar __end__ para terminación
    routing_options = ["__end__"] + agent_names
    return routing_options


def get_agent_type_mapping() -> Dict[str, AgentType]:
    """
    Crea un mapeo de nombres de agentes a tipos de agente.

    Returns:
        Diccionario mapping agent_name -> AgentType
    """
    return {agent.value: agent for agent in AgentType}


def get_non_supervisor_agents() -> List[AgentType]:
    """
    Obtiene todos los tipos de agente especializados (excluye ORCHESTRATOR y SUPERVISOR).

    Returns:
        Lista de AgentType especializados sin orchestrator ni supervisor
    """
    return [agent for agent in AgentType if agent not in (AgentType.ORCHESTRATOR, AgentType.SUPERVISOR)]


# Export the default schema instance
__all__ = [
    "IntentType",
    "AgentType",
    "IntentDefinition",
    "AgentDefinition",
    "AgentSchema",
    "DEFAULT_AGENT_SCHEMA",
    "get_valid_intents",
    "get_valid_agents",
    "get_intent_to_agent_mapping",
    "get_agent_class_mapping",
    "get_graph_node_names",
    "get_intent_examples",
    "get_intent_descriptions",
    "build_intent_prompt_text",
    "get_agent_routing_literal",
    "get_agent_type_mapping",
    "get_non_supervisor_agents",
]
