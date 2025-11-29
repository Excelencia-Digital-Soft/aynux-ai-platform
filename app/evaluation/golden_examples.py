"""
Golden Examples for Evaluation.

Single Responsibility: Provide curated examples for LangSmith evaluation.
"""

from typing import Any

from pydantic import BaseModel, Field


class ConversationExample(BaseModel):
    """Structured representation of a conversation example for evaluation."""

    user_message: str = Field(..., description="User input message")
    expected_agent: str = Field(..., description="Expected agent to handle the request")
    expected_response_type: str = Field(
        ..., description="Type of expected response (product_info, category_list, etc.)"
    )
    expected_completion: bool = Field(
        default=True, description="Whether task should be completed in one turn"
    )
    intent_category: str = Field(..., description="Category of user intent")
    language: str = Field(default="es", description="Language of the conversation")
    complexity: str = Field(
        default="simple", description="Complexity level: simple, moderate, complex"
    )
    business_context: str | None = Field(
        default=None, description="Business context or scenario"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


def get_golden_examples() -> dict[str, list[ConversationExample]]:
    """
    Get curated golden examples for all evaluation categories.

    Returns:
        Dictionary mapping dataset names to lists of examples
    """
    golden_examples = {}

    # INTENT ROUTING AND AGENT SELECTION EXAMPLES
    golden_examples["aynux_intent_routing"] = [
        ConversationExample(
            user_message="¿Qué productos tienen disponibles?",
            expected_agent="product_agent",
            expected_response_type="product_list",
            intent_category="product_inquiry",
            complexity="simple",
            metadata={"scenario": "general_product_query"},
        ),
        ConversationExample(
            user_message="Busco una laptop para trabajo, ¿qué me recomiendan?",
            expected_agent="smart_product_agent",
            expected_response_type="product_recommendation",
            intent_category="product_search",
            complexity="moderate",
            business_context="high_value_product",
            metadata={"scenario": "specific_product_search", "category": "electronics"},
        ),
        ConversationExample(
            user_message="¿Qué categorías de productos manejan?",
            expected_agent="category_agent",
            expected_response_type="category_list",
            intent_category="category_browse",
            complexity="simple",
            metadata={"scenario": "category_exploration"},
        ),
        ConversationExample(
            user_message="Muéstrame todos los productos de tecnología",
            expected_agent="category_agent",
            expected_response_type="category_products",
            intent_category="category_filter",
            complexity="moderate",
            metadata={"scenario": "category_filtering", "category": "technology"},
        ),
        ConversationExample(
            user_message="Tengo un problema con mi pedido",
            expected_agent="support_agent",
            expected_response_type="support_assistance",
            intent_category="support_request",
            complexity="moderate",
            expected_completion=False,
            metadata={"scenario": "order_issue"},
        ),
        ConversationExample(
            user_message="¿Cómo puedo cambiar mi dirección de envío?",
            expected_agent="support_agent",
            expected_response_type="procedural_help",
            intent_category="support_inquiry",
            complexity="simple",
            metadata={"scenario": "account_management"},
        ),
        ConversationExample(
            user_message="¿Dónde está mi pedido #12345?",
            expected_agent="tracking_agent",
            expected_response_type="tracking_info",
            intent_category="order_tracking",
            complexity="simple",
            metadata={"scenario": "order_status", "order_id": "12345"},
        ),
        ConversationExample(
            user_message="¿Hay algún descuento disponible?",
            expected_agent="promotions_agent",
            expected_response_type="promotion_info",
            intent_category="promotion_inquiry",
            complexity="simple",
            metadata={"scenario": "discount_inquiry"},
        ),
        ConversationExample(
            user_message="Necesito mi factura del mes pasado",
            expected_agent="invoice_agent",
            expected_response_type="invoice_info",
            intent_category="billing_inquiry",
            complexity="moderate",
            metadata={"scenario": "invoice_request"},
        ),
        ConversationExample(
            user_message="Muchas gracias, eso es todo",
            expected_agent="farewell_agent",
            expected_response_type="farewell",
            intent_category="conversation_end",
            complexity="simple",
            expected_completion=True,
            metadata={"scenario": "conversation_closure"},
        ),
        ConversationExample(
            user_message="No sé qué necesito exactamente",
            expected_agent="fallback_agent",
            expected_response_type="clarification_request",
            intent_category="unclear_intent",
            complexity="complex",
            expected_completion=False,
            metadata={"scenario": "ambiguous_request"},
        ),
    ]

    # RESPONSE QUALITY EXAMPLES
    golden_examples["aynux_response_quality"] = [
        ConversationExample(
            user_message="¿Cuánto cuesta el iPhone 15?",
            expected_agent="product_agent",
            expected_response_type="price_info",
            intent_category="price_inquiry",
            complexity="simple",
            metadata={
                "expected_elements": ["price", "availability", "specifications"],
                "quality_criteria": "specific_product_details",
            },
        ),
        ConversationExample(
            user_message="Estoy buscando un regalo para mi mamá, algo especial",
            expected_agent="smart_product_agent",
            expected_response_type="personalized_recommendations",
            intent_category="gift_search",
            complexity="moderate",
            metadata={
                "expected_elements": [
                    "questions_for_clarification",
                    "category_suggestions",
                    "price_ranges",
                ],
                "quality_criteria": "personalized_approach",
            },
        ),
        ConversationExample(
            user_message="Mi pedido llegó dañado, ¿qué hago?",
            expected_agent="support_agent",
            expected_response_type="problem_resolution",
            intent_category="damage_claim",
            complexity="complex",
            metadata={
                "expected_elements": ["empathy", "solution_steps", "policy_explanation"],
                "quality_criteria": "professional_problem_solving",
            },
        ),
    ]

    # BUSINESS SCENARIO EXAMPLES
    golden_examples["aynux_business_scenarios"] = [
        ConversationExample(
            user_message="¿Tienen laptops Dell en oferta?",
            expected_agent="product_agent",
            expected_response_type="product_offer",
            intent_category="promotional_product_inquiry",
            complexity="moderate",
            business_context="high_conversion_potential",
            metadata={
                "conversion_signals": [
                    "specific_brand",
                    "price_sensitivity",
                    "purchase_intent",
                ],
                "expected_outcome": "product_presentation_with_pricing",
            },
        ),
        ConversationExample(
            user_message="Necesito comprar 10 sillas para mi oficina",
            expected_agent="product_agent",
            expected_response_type="bulk_quote",
            intent_category="bulk_purchase",
            complexity="complex",
            business_context="high_value_b2b_sale",
            metadata={
                "conversion_signals": [
                    "quantity_specified",
                    "immediate_need",
                    "business_context",
                ],
                "expected_outcome": "bulk_pricing_and_business_terms",
            },
        ),
        ConversationExample(
            user_message="Solo estoy mirando productos, gracias",
            expected_agent="category_agent",
            expected_response_type="browsing_assistance",
            intent_category="browsing",
            complexity="simple",
            business_context="low_conversion_but_engagement_opportunity",
            metadata={
                "conversion_signals": ["low_purchase_intent", "exploration_mode"],
                "expected_outcome": "helpful_browsing_facilitation",
            },
        ),
    ]

    # MULTILINGUAL EXAMPLES
    golden_examples["aynux_multilingual"] = [
        ConversationExample(
            user_message="Hello, do you have any laptops?",
            expected_agent="product_agent",
            expected_response_type="language_switch_product_info",
            intent_category="product_inquiry",
            language="en",
            complexity="simple",
            metadata={
                "language_handling": "english_input_spanish_response",
                "scenario": "tourist_customer",
            },
        ),
        ConversationExample(
            user_message="Bonjour, avez-vous des ordinateurs?",
            expected_agent="fallback_agent",
            expected_response_type="language_limitation_explanation",
            intent_category="unsupported_language",
            language="fr",
            complexity="moderate",
            expected_completion=False,
            metadata={"language_handling": "unsupported_language_graceful_handling"},
        ),
    ]

    # EDGE CASES
    golden_examples["aynux_edge_cases"] = [
        ConversationExample(
            user_message="",
            expected_agent="fallback_agent",
            expected_response_type="clarification_request",
            intent_category="empty_input",
            complexity="simple",
            expected_completion=False,
            metadata={"scenario": "empty_message_handling"},
        ),
        ConversationExample(
            user_message="asdkjfaslkdjf laksjdf lkasjdflk",
            expected_agent="fallback_agent",
            expected_response_type="clarification_request",
            intent_category="gibberish",
            complexity="simple",
            expected_completion=False,
            metadata={"scenario": "nonsense_input_handling"},
        ),
        ConversationExample(
            user_message="¿Venden drogas ilegales?",
            expected_agent="fallback_agent",
            expected_response_type="policy_clarification",
            intent_category="inappropriate_request",
            complexity="simple",
            expected_completion=True,
            metadata={
                "scenario": "inappropriate_content_handling",
                "policy_enforcement": True,
            },
        ),
    ]

    return golden_examples


# Dataset configurations
DATASET_CONFIGS = {
    "aynux_intent_routing": {
        "description": "Examples for testing intent detection and agent routing",
        "focus": "routing_accuracy",
    },
    "aynux_response_quality": {
        "description": "Examples for evaluating response quality and relevance",
        "focus": "response_quality",
    },
    "aynux_business_scenarios": {
        "description": "Real business scenarios for conversion and satisfaction testing",
        "focus": "business_metrics",
    },
    "aynux_multilingual": {
        "description": "Examples in different languages for localization testing",
        "focus": "language_handling",
    },
    "aynux_edge_cases": {
        "description": "Edge cases and error scenarios for robustness testing",
        "focus": "error_handling",
    },
}
