"""
AI-Based Routing Strategy

Uses LLM for intelligent domain classification with context awareness.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.interfaces.llm import ILLM

logger = logging.getLogger(__name__)


@dataclass
class DomainDescription:
    """Description of a domain for AI routing."""

    domain: str
    description: str
    example_queries: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)


@dataclass
class AIRoutingResult:
    """Result of AI-based routing."""

    domain: str
    confidence: float
    reasoning: str
    strategy: str = "ai"


class AIBasedRoutingStrategy:
    """
    AI-powered routing strategy using LLM classification.

    Uses language model to understand message intent and route to
    appropriate domain. More accurate for ambiguous or complex messages.

    Example:
        ```python
        strategy = AIBasedRoutingStrategy(llm=ollama_llm)

        strategy.add_domain(DomainDescription(
            domain="ecommerce",
            description="Handles product inquiries, orders, and shopping",
            example_queries=["What's the price of X?", "Where's my order?"],
            capabilities=["product search", "order tracking", "pricing"]
        ))

        result = await strategy.route("I'm looking for a laptop under $1000")
        print(result.domain)  # "ecommerce"
        ```
    """

    DEFAULT_DOMAINS: list[DomainDescription] = [
        DomainDescription(
            domain="ecommerce",
            description="Handles product catalog, pricing, orders, invoices, promotions, and shipping tracking",
            example_queries=[
                "Cuanto cuesta este producto?",
                "Donde esta mi pedido?",
                "Tienen ofertas?",
                "Quiero comprar...",
                "Necesito mi factura",
            ],
            capabilities=[
                "product search",
                "pricing information",
                "order tracking",
                "promotions and discounts",
                "invoice generation",
            ],
        ),
        DomainDescription(
            domain="healthcare",
            description="Handles medical appointments, patient information, doctors, and health services",
            example_queries=[
                "Quiero sacar un turno",
                "Que medicos hay disponibles?",
                "Necesito una consulta",
                "Me duele...",
                "Cuando es mi proxima cita?",
            ],
            capabilities=[
                "appointment scheduling",
                "doctor availability",
                "patient records",
                "medical consultations",
                "health services",
            ],
        ),
        DomainDescription(
            domain="credit",
            description="Handles credit accounts, payments, balances, and financial services",
            example_queries=[
                "Cuanto debo?",
                "Quiero pagar mi cuota",
                "Cual es mi saldo?",
                "Cuando vence mi pago?",
                "Necesito financiacion",
            ],
            capabilities=[
                "balance inquiries",
                "payment processing",
                "credit limits",
                "payment schedules",
                "account status",
            ],
        ),
        DomainDescription(
            domain="excelencia",
            description="Handles software system questions, ERP functionality, and technical support",
            example_queries=[
                "Como funciona el sistema?",
                "Como configuro...?",
                "Necesito ayuda con el modulo",
                "Que puede hacer Excelencia?",
            ],
            capabilities=[
                "system documentation",
                "feature explanations",
                "configuration help",
                "technical support",
            ],
        ),
    ]

    SYSTEM_PROMPT = """You are a domain classifier for a multi-service chatbot.
Your task is to determine which domain should handle a user's message.

Available domains:
{domains_info}

Instructions:
1. Analyze the user's message intent
2. Match it to the most appropriate domain
3. Return ONLY the domain name in lowercase
4. If unsure, return "{default_domain}"

User message: {message}

Domain:"""

    def __init__(
        self,
        llm: ILLM,
        default_domain: str = "ecommerce",
        temperature: float = 0.1,
        max_tokens: int = 20,
    ):
        """
        Initialize AI-based routing strategy.

        Args:
            llm: Language model interface
            default_domain: Default domain when classification fails
            temperature: LLM temperature (lower = more deterministic)
            max_tokens: Maximum tokens for response
        """
        self.llm = llm
        self.default_domain = default_domain
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.domains: dict[str, DomainDescription] = {}

        # Load default domains
        for domain in self.DEFAULT_DOMAINS:
            self.add_domain(domain)

    def add_domain(self, description: DomainDescription) -> None:
        """
        Add or update domain description.

        Args:
            description: Domain description
        """
        self.domains[description.domain] = description
        logger.debug(f"Added AI routing config for domain: {description.domain}")

    def remove_domain(self, domain: str) -> bool:
        """
        Remove a domain description.

        Args:
            domain: Domain name to remove

        Returns:
            True if removed, False if not found
        """
        if domain in self.domains:
            del self.domains[domain]
            return True
        return False

    async def route(self, message: str, context: dict[str, Any] | None = None) -> AIRoutingResult:
        """
        Route message to domain using AI classification.

        Args:
            message: User message
            context: Optional additional context

        Returns:
            Routing result with domain and confidence
        """
        try:
            # Build domains info for prompt
            domains_info = self._build_domains_info()

            # Generate classification prompt
            prompt = self.SYSTEM_PROMPT.format(
                domains_info=domains_info,
                default_domain=self.default_domain,
                message=message,
            )

            # Get LLM classification
            response = await self.llm.generate(
                prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            # Parse response
            domain = response.strip().lower()

            # Validate domain
            if domain not in self.domains:
                logger.warning(f"AI returned unknown domain '{domain}', using default")
                return AIRoutingResult(
                    domain=self.default_domain,
                    confidence=0.5,
                    reasoning=f"AI returned unknown domain: {domain}",
                )

            return AIRoutingResult(
                domain=domain,
                confidence=0.85,  # AI routing typically has good confidence
                reasoning=f"AI classified as {domain}",
            )

        except Exception as e:
            logger.error(f"AI routing error: {e}", exc_info=True)
            return AIRoutingResult(
                domain=self.default_domain,
                confidence=0.0,
                reasoning=f"Error during classification: {e}",
            )

    async def route_with_reasoning(
        self, message: str, context: dict[str, Any] | None = None
    ) -> AIRoutingResult:
        """
        Route with detailed reasoning (more tokens, better explanation).

        Args:
            message: User message
            context: Optional additional context

        Returns:
            Routing result with detailed reasoning
        """
        try:
            domains_info = self._build_domains_info()

            prompt = f"""Analyze this message and determine the appropriate domain.

Available domains:
{domains_info}

Message: "{message}"

Respond in this format:
DOMAIN: <domain_name>
CONFIDENCE: <high/medium/low>
REASONING: <brief explanation>
"""

            response = await self.llm.generate(
                prompt,
                temperature=self.temperature,
                max_tokens=100,
            )

            # Parse structured response
            domain = self.default_domain
            confidence = 0.5
            reasoning = "Could not parse response"

            for line in response.strip().split("\n"):
                if line.startswith("DOMAIN:"):
                    domain = line.split(":", 1)[1].strip().lower()
                elif line.startswith("CONFIDENCE:"):
                    conf_str = line.split(":", 1)[1].strip().lower()
                    confidence = {"high": 0.9, "medium": 0.7, "low": 0.4}.get(conf_str, 0.5)
                elif line.startswith("REASONING:"):
                    reasoning = line.split(":", 1)[1].strip()

            # Validate domain
            if domain not in self.domains:
                domain = self.default_domain
                confidence = 0.3

            return AIRoutingResult(
                domain=domain,
                confidence=confidence,
                reasoning=reasoning,
            )

        except Exception as e:
            logger.error(f"AI routing with reasoning error: {e}", exc_info=True)
            return AIRoutingResult(
                domain=self.default_domain,
                confidence=0.0,
                reasoning=f"Error: {e}",
            )

    def _build_domains_info(self) -> str:
        """Build formatted domain information for prompts."""
        lines = []
        for domain, desc in self.domains.items():
            lines.append(f"- {domain}: {desc.description}")
            if desc.capabilities:
                caps = ", ".join(desc.capabilities[:3])
                lines.append(f"  Capabilities: {caps}")
        return "\n".join(lines)

    def get_available_domains(self) -> list[str]:
        """Get list of configured domains."""
        return list(self.domains.keys())
