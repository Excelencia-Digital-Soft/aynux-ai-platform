"""
E-commerce Intent Router

LLM-based intelligent routing for e-commerce domain intents.
Replaces keyword-based routing with AI-powered classification.
"""

import logging
from enum import Enum
from typing import Any

from app.integrations.llm import OllamaLLM
from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry
from app.utils import extract_json_from_text

logger = logging.getLogger(__name__)


class EcommerceIntentType(str, Enum):
    """E-commerce domain intent types."""

    PRODUCT_SEARCH = "product_search"
    PROMOTIONS = "promotions"
    ORDER_TRACKING = "order_tracking"
    BILLING = "billing"


# Intent descriptions for the router
ECOMMERCE_INTENT_DEFINITIONS = {
    EcommerceIntentType.PRODUCT_SEARCH: {
        "description": "Product catalog, search, pricing, stock, specifications, features, comparisons",
        "examples": [
            "busco una laptop",
            "tienen celulares?",
            "precio del iPhone",
            "que productos tienen en stock?",
            "mostrame televisores",
            "caracteristicas del producto",
            "cuanto cuesta?",
        ],
        "target_node": "product_node",
    },
    EcommerceIntentType.PROMOTIONS: {
        "description": "Discounts, coupons, promotional offers, deals, sales, special prices",
        "examples": [
            "tienen descuentos?",
            "cupones disponibles",
            "ofertas del dia",
            "promociones actuales",
            "hay alguna rebaja?",
            "codigo de descuento",
        ],
        "target_node": "promotions_node",
    },
    EcommerceIntentType.ORDER_TRACKING: {
        "description": "Order status, shipping tracking, delivery estimates, package location",
        "examples": [
            "donde esta mi pedido?",
            "tracking de mi orden",
            "cuando llega mi compra?",
            "seguimiento del envio",
            "estado de mi orden",
            "numero de seguimiento",
        ],
        "target_node": "tracking_node",
    },
    EcommerceIntentType.BILLING: {
        "description": "Invoices, payments, refunds, receipts, billing issues, tax information",
        "examples": [
            "necesito mi factura",
            "problema con el pago",
            "solicitar reembolso",
            "metodos de pago",
            "recibo de compra",
            "informacion fiscal",
        ],
        "target_node": "invoice_node",
    },
}


def _build_intent_descriptions() -> str:
    """Build formatted intent descriptions for prompts."""
    intent_descriptions = []
    for intent_type, definition in ECOMMERCE_INTENT_DEFINITIONS.items():
        examples = ", ".join([f'"{ex}"' for ex in definition["examples"][:3]])
        intent_descriptions.append(
            f"- {intent_type.value}: {definition['description']}. Examples: {examples}"
        )
    return "\n".join(intent_descriptions)


def _build_context_info(context: dict[str, Any] | None = None) -> str:
    """Build context info string for prompts."""
    context_info = ""
    if context:
        if context.get("cart"):
            context_info += f"\nUser has items in cart: {len(context['cart'].get('items', []))} items"
        if context.get("customer"):
            tier = context["customer"].get("tier", "basic")
            context_info += f"\nCustomer tier: {tier}"
    return context_info


class EcommerceIntentRouter:
    """
    LLM-based router for e-commerce domain intents.

    Uses Ollama to intelligently classify user messages into
    e-commerce sub-intents (product_search, promotions, order_tracking, billing).
    """

    def __init__(self, ollama: OllamaLLM, config: dict[str, Any] | None = None):
        """
        Initialize the e-commerce intent router.

        Args:
            ollama: OllamaLLM instance for LLM calls
            config: Optional configuration dict with:
                - confidence_threshold: Minimum confidence (default 0.6)
                - default_intent: Fallback intent (default product_search)
                - temperature: LLM temperature (default 0.3)
        """
        self.ollama = ollama
        self.config = config or {}
        self.prompt_manager = PromptManager()

        self.confidence_threshold = self.config.get("confidence_threshold", 0.6)
        self.default_intent = self.config.get("default_intent", EcommerceIntentType.PRODUCT_SEARCH)
        self.temperature = self.config.get("temperature", 0.3)

        logger.info(
            f"EcommerceIntentRouter initialized - "
            f"confidence_threshold={self.confidence_threshold}, "
            f"default_intent={self.default_intent.value}"
        )

    async def analyze_intent(
        self,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Analyze user message and determine e-commerce intent.

        Args:
            message: User message to classify
            context: Optional context dict with customer, cart info

        Returns:
            Dict with:
                - intent: EcommerceIntentType value
                - confidence: float 0.0-1.0
                - target_node: str node name to route to
                - reasoning: str explanation
                - method: str classification method used
        """
        try:
            result = await self._llm_analysis(message, context)

            # Validate confidence threshold
            if result["confidence"] < self.confidence_threshold:
                logger.info(
                    f"E-commerce intent confidence {result['confidence']:.2f} "
                    f"below threshold {self.confidence_threshold}, using default"
                )
                return self._create_default_result(
                    reason=f"Low confidence ({result['confidence']:.2f}), defaulting to product_search"
                )

            return result

        except Exception as e:
            logger.error(f"Error in e-commerce intent analysis: {e}")
            return self._create_default_result(reason=f"Analysis error: {str(e)}")

    async def _llm_analysis(
        self,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform LLM-based intent analysis."""
        # Build prompts from YAML templates
        intent_descriptions = _build_intent_descriptions()
        context_info = _build_context_info(context)

        system_prompt = await self.prompt_manager.get_prompt(
            PromptRegistry.ECOMMERCE_ROUTER_INTENT_CLASSIFIER,
            variables={"intent_descriptions": intent_descriptions},
        )

        user_prompt = await self.prompt_manager.get_prompt(
            PromptRegistry.ECOMMERCE_ROUTER_USER_CONTEXT,
            variables={"message": message, "context_info": context_info},
        )

        try:
            response_text = await self.ollama.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=self.temperature,
            )

            # Extract JSON from response
            result = extract_json_from_text(
                response_text,
                default={"intent": "product_search", "confidence": 0.5, "reasoning": "Parse failed"},
                required_keys=["intent"],
            )

            if not result or not isinstance(result, dict):
                logger.warning("Failed to parse LLM response for e-commerce routing")
                return self._create_default_result(reason="Failed to parse LLM response")

            # Validate intent
            intent_str = result.get("intent", "product_search")
            try:
                intent_type = EcommerceIntentType(intent_str)
            except ValueError:
                logger.warning(f"Invalid e-commerce intent '{intent_str}', using default")
                intent_type = self.default_intent

            # Get target node
            intent_def = ECOMMERCE_INTENT_DEFINITIONS.get(intent_type, {})
            target_node = intent_def.get("target_node", "product_node")

            return {
                "intent": intent_type.value,
                "confidence": float(result.get("confidence", 0.7)),
                "target_node": target_node,
                "reasoning": result.get("reasoning", "LLM classification"),
                "method": "llm_analysis",
            }

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            raise

    def _create_default_result(self, reason: str = "Default fallback") -> dict[str, Any]:
        """Create default result using product_search intent."""
        intent_def = ECOMMERCE_INTENT_DEFINITIONS[self.default_intent]

        return {
            "intent": self.default_intent.value,
            "confidence": 0.5,
            "target_node": intent_def["target_node"],
            "reasoning": reason,
            "method": "default_fallback",
        }

    def keyword_fallback(self, message: str) -> dict[str, Any]:
        """
        Keyword-based fallback for when LLM is unavailable.

        Args:
            message: User message

        Returns:
            Intent classification result
        """
        message_lower = message.lower()

        # Keyword patterns for each intent
        patterns = {
            EcommerceIntentType.ORDER_TRACKING: [
                "pedido", "orden", "tracking", "envio", "entrega",
                "seguimiento", "paquete", "donde esta", "cuando llega",
            ],
            EcommerceIntentType.PROMOTIONS: [
                "promocion", "descuento", "oferta", "cupon", "codigo",
                "rebaja", "promo", "sale", "deal",
            ],
            EcommerceIntentType.BILLING: [
                "factura", "pago", "cobro", "invoice", "recibo",
                "cuenta", "reembolso", "impuesto", "fiscal",
            ],
            # Product search is default, so checked last
            EcommerceIntentType.PRODUCT_SEARCH: [
                "producto", "precio", "stock", "busco", "tienen",
                "catalogo", "disponible", "caracteristicas",
            ],
        }

        # Find best matching intent
        best_intent = self.default_intent
        best_score = 0

        for intent_type, keywords in patterns.items():
            score = sum(1 for kw in keywords if kw in message_lower)
            if score > best_score:
                best_score = score
                best_intent = intent_type

        confidence = min(best_score * 0.25, 0.7) if best_score > 0 else 0.4
        intent_def = ECOMMERCE_INTENT_DEFINITIONS[best_intent]

        return {
            "intent": best_intent.value,
            "confidence": confidence,
            "target_node": intent_def["target_node"],
            "reasoning": f"Keyword match: {best_score} keywords for {best_intent.value}",
            "method": "keyword_fallback",
        }

    def get_node_for_intent(self, intent: str | EcommerceIntentType) -> str:
        """Get target node name for an intent."""
        if isinstance(intent, str):
            try:
                intent = EcommerceIntentType(intent)
            except ValueError:
                return "product_node"

        intent_def = ECOMMERCE_INTENT_DEFINITIONS.get(intent, {})
        target_node = intent_def.get("target_node", "product_node")
        return target_node if isinstance(target_node, str) else "product_node"
