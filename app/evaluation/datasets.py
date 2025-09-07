"""
Dataset management for LangSmith evaluation in ConversaShop.

This module handles creation, management, and maintenance of evaluation datasets
for testing the multi-agent conversation system.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from langsmith.schemas import Dataset, Example
from pydantic import BaseModel, Field

from app.config.langsmith_config import get_tracer

logger = logging.getLogger(__name__)


class ConversationExample(BaseModel):
    """Structured representation of a conversation example for evaluation."""

    user_message: str = Field(..., description="User input message")
    expected_agent: str = Field(..., description="Expected agent to handle the request")
    expected_response_type: str = Field(
        ..., description="Type of expected response (product_info, category_list, etc.)"
    )
    expected_completion: bool = Field(default=True, description="Whether task should be completed in one turn")
    intent_category: str = Field(..., description="Category of user intent")
    language: str = Field(default="es", description="Language of the conversation")
    complexity: str = Field(default="simple", description="Complexity level: simple, moderate, complex")
    business_context: Optional[str] = Field(None, description="Business context or scenario")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def to_langsmith_example(self, dataset_name: str) -> Example:
        """Convert to LangSmith Example format."""
        return Example(
            inputs={"message": self.user_message},
            outputs={
                "expected_agent": self.expected_agent,
                "expected_response_type": self.expected_response_type,
                "expected_completion": self.expected_completion,
                "intent_category": self.intent_category,
                "language": self.language,
                "complexity": self.complexity,
                "business_context": self.business_context,
            },
            metadata={"dataset": dataset_name, "created_at": datetime.now().isoformat(), **self.metadata},
        )


class DatasetManager:
    """Manages evaluation datasets for the ConversaShop multi-agent system."""

    def __init__(self):
        self.tracer = get_tracer()
        self.client = self.tracer.client if self.tracer.client else None

        # Dataset configurations
        self.dataset_configs = {
            "conversashop_intent_routing": {
                "description": "Examples for testing intent detection and agent routing",
                "focus": "routing_accuracy",
            },
            "conversashop_response_quality": {
                "description": "Examples for evaluating response quality and relevance",
                "focus": "response_quality",
            },
            "conversashop_business_scenarios": {
                "description": "Real business scenarios for conversion and satisfaction testing",
                "focus": "business_metrics",
            },
            "conversashop_multilingual": {
                "description": "Examples in different languages for localization testing",
                "focus": "language_handling",
            },
            "conversashop_edge_cases": {
                "description": "Edge cases and error scenarios for robustness testing",
                "focus": "error_handling",
            },
        }

        logger.info("DatasetManager initialized")

    async def create_dataset(self, dataset_name: str, description: str = "") -> Optional[Dataset]:
        """
        Create a new evaluation dataset in LangSmith.

        Args:
            dataset_name: Name of the dataset
            description: Description of the dataset purpose

        Returns:
            Created Dataset object or None if creation failed
        """
        if not self.client:
            logger.error("LangSmith client not available")
            return None

        try:
            # Check if dataset already exists
            try:
                existing_dataset = self.client.read_dataset(dataset_name=dataset_name)
                logger.info(f"Dataset {dataset_name} already exists")
                return existing_dataset
            except Exception:
                pass  # Dataset doesn't exist, create it

            dataset = self.client.create_dataset(
                dataset_name=dataset_name, description=description or f"ConversaShop evaluation dataset: {dataset_name}"
            )

            logger.info(f"Created dataset: {dataset_name}")
            return dataset

        except Exception as e:
            logger.error(f"Failed to create dataset {dataset_name}: {e}")
            return None

    async def add_examples_to_dataset(self, dataset_name: str, examples: List[ConversationExample]) -> bool:
        """
        Add conversation examples to a dataset.

        Args:
            dataset_name: Name of the target dataset
            examples: List of conversation examples to add

        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            logger.error("LangSmith client not available")
            return False

        try:
            # Ensure dataset exists
            dataset = await self.create_dataset(dataset_name)
            if not dataset:
                return False

            # Convert examples to LangSmith format
            langsmith_examples = [example.to_langsmith_example(dataset_name) for example in examples]

            # Add examples to dataset
            for example in langsmith_examples:
                self.client.create_example(
                    dataset_name=dataset_name, inputs=example.inputs, outputs=example.outputs, metadata=example.metadata
                )

            logger.info(f"Added {len(examples)} examples to dataset {dataset_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to add examples to dataset {dataset_name}: {e}")
            return False

    def get_golden_examples(self) -> Dict[str, List[ConversationExample]]:
        """
        Get curated golden examples for all evaluation categories.

        Returns:
            Dictionary mapping dataset names to lists of examples
        """
        golden_examples = {}

        # =====================================================
        # INTENT ROUTING AND AGENT SELECTION EXAMPLES
        # =====================================================

        golden_examples["conversashop_intent_routing"] = [
            # Product queries - should route to product_agent
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
            # Category browsing - should route to category_agent
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
            # Support queries - should route to support_agent
            ConversationExample(
                user_message="Tengo un problema con mi pedido",
                expected_agent="support_agent",
                expected_response_type="support_assistance",
                intent_category="support_request",
                complexity="moderate",
                expected_completion=False,  # May need escalation
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
            # Tracking queries - should route to tracking_agent
            ConversationExample(
                user_message="¿Dónde está mi pedido #12345?",
                expected_agent="tracking_agent",
                expected_response_type="tracking_info",
                intent_category="order_tracking",
                complexity="simple",
                metadata={"scenario": "order_status", "order_id": "12345"},
            ),
            # Promotions queries - should route to promotions_agent
            ConversationExample(
                user_message="¿Hay algún descuento disponible?",
                expected_agent="promotions_agent",
                expected_response_type="promotion_info",
                intent_category="promotion_inquiry",
                complexity="simple",
                metadata={"scenario": "discount_inquiry"},
            ),
            # Billing queries - should route to invoice_agent
            ConversationExample(
                user_message="Necesito mi factura del mes pasado",
                expected_agent="invoice_agent",
                expected_response_type="invoice_info",
                intent_category="billing_inquiry",
                complexity="moderate",
                metadata={"scenario": "invoice_request"},
            ),
            # Goodbye/farewell - should route to farewell_agent
            ConversationExample(
                user_message="Muchas gracias, eso es todo",
                expected_agent="farewell_agent",
                expected_response_type="farewell",
                intent_category="conversation_end",
                complexity="simple",
                expected_completion=True,
                metadata={"scenario": "conversation_closure"},
            ),
            # Complex/ambiguous - might route to fallback_agent
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

        # =====================================================
        # RESPONSE QUALITY EXAMPLES
        # =====================================================

        golden_examples["conversashop_response_quality"] = [
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
                    "expected_elements": ["questions_for_clarification", "category_suggestions", "price_ranges"],
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

        # =====================================================
        # BUSINESS SCENARIO EXAMPLES
        # =====================================================

        golden_examples["conversashop_business_scenarios"] = [
            ConversationExample(
                user_message="¿Tienen laptops Dell en oferta?",
                expected_agent="product_agent",
                expected_response_type="product_offer",
                intent_category="promotional_product_inquiry",
                complexity="moderate",
                business_context="high_conversion_potential",
                metadata={
                    "conversion_signals": ["specific_brand", "price_sensitivity", "purchase_intent"],
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
                    "conversion_signals": ["quantity_specified", "immediate_need", "business_context"],
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

        # =====================================================
        # MULTILINGUAL AND EDGE CASES
        # =====================================================

        golden_examples["conversashop_multilingual"] = [
            ConversationExample(
                user_message="Hello, do you have any laptops?",
                expected_agent="product_agent",
                expected_response_type="language_switch_product_info",
                intent_category="product_inquiry",
                language="en",
                complexity="simple",
                metadata={"language_handling": "english_input_spanish_response", "scenario": "tourist_customer"},
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

        golden_examples["conversashop_edge_cases"] = [
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
                metadata={"scenario": "inappropriate_content_handling", "policy_enforcement": True},
            ),
        ]

        return golden_examples

    async def initialize_all_datasets(self) -> Dict[str, bool]:
        """
        Initialize all standard datasets with golden examples.

        Returns:
            Dictionary mapping dataset names to creation success status
        """
        results = {}
        golden_examples = self.get_golden_examples()

        for dataset_name, examples in golden_examples.items():
            config = self.dataset_configs.get(dataset_name, {})
            description = config.get("description", f"Evaluation dataset: {dataset_name}")

            # Create dataset
            dataset = await self.create_dataset(dataset_name, description)
            if not dataset:
                results[dataset_name] = False
                continue

            # Add examples
            success = await self.add_examples_to_dataset(dataset_name, examples)
            results[dataset_name] = success

            if success:
                logger.info(f"Successfully initialized dataset {dataset_name} with {len(examples)} examples")
            else:
                logger.error(f"Failed to initialize dataset {dataset_name}")

        return results

    async def update_dataset_from_production(
        self, dataset_name: str, conversation_runs: List[Dict[str, Any]], quality_threshold: float = 0.8
    ) -> int:
        """
        Update dataset with high-quality examples from production conversations.

        Args:
            dataset_name: Target dataset name
            conversation_runs: List of conversation run data
            quality_threshold: Minimum quality score to include

        Returns:
            Number of examples added
        """
        if not self.client:
            logger.error("LangSmith client not available")
            return 0

        added_count = 0

        try:
            for run_data in conversation_runs:
                # Extract conversation quality metrics
                quality_score = run_data.get("quality_score", 0.0)
                if quality_score < quality_threshold:
                    continue

                # Create example from production run
                example = ConversationExample(
                    user_message=run_data.get("user_message", ""),
                    expected_agent=run_data.get("agent_used", ""),
                    expected_response_type=run_data.get("response_type", ""),
                    expected_completion=run_data.get("is_complete", True),
                    intent_category=run_data.get("intent", ""),
                    complexity=run_data.get("complexity", "moderate"),
                    metadata={
                        "source": "production",
                        "quality_score": quality_score,
                        "conversation_id": run_data.get("conversation_id", ""),
                        "timestamp": run_data.get("timestamp", datetime.now().isoformat()),
                    },
                )

                # Add to dataset
                success = await self.add_examples_to_dataset(dataset_name, [example])
                if success:
                    added_count += 1

            logger.info(f"Added {added_count} production examples to {dataset_name}")
            return added_count

        except Exception as e:
            logger.error(f"Error updating dataset from production: {e}")
            return added_count

    def get_dataset_statistics(self, dataset_name: str) -> Dict[str, Any]:
        """
        Get statistics and analysis for a dataset.

        Args:
            dataset_name: Name of the dataset to analyze

        Returns:
            Dictionary containing dataset statistics
        """
        if not self.client:
            return {"error": "LangSmith client not available"}

        try:
            # Get dataset examples
            examples = list(self.client.list_examples(dataset_name=dataset_name))

            if not examples:
                return {"error": "Dataset not found or empty"}

            stats = {
                "total_examples": len(examples),
                "created_at": datetime.now().isoformat(),
                "dataset_name": dataset_name,
            }

            # Analyze by categories
            intent_categories = {}
            agents = {}
            complexity_levels = {}
            languages = {}

            for example in examples:
                # Intent categories
                intent = example.outputs.get("intent_category", "unknown")
                intent_categories[intent] = intent_categories.get(intent, 0) + 1

                # Expected agents
                agent = example.outputs.get("expected_agent", "unknown")
                agents[agent] = agents.get(agent, 0) + 1

                # Complexity levels
                complexity = example.outputs.get("complexity", "unknown")
                complexity_levels[complexity] = complexity_levels.get(complexity, 0) + 1

                # Languages
                language = example.outputs.get("language", "unknown")
                languages[language] = languages.get(language, 0) + 1

            stats.update(
                {
                    "intent_distribution": intent_categories,
                    "agent_distribution": agents,
                    "complexity_distribution": complexity_levels,
                    "language_distribution": languages,
                }
            )

            return stats

        except Exception as e:
            logger.error(f"Error getting dataset statistics: {e}")
            return {"error": str(e)}

    async def export_dataset(self, dataset_name: str, export_path: Path) -> bool:
        """
        Export dataset to JSON file for backup or sharing.

        Args:
            dataset_name: Name of dataset to export
            export_path: Path to save the exported file

        Returns:
            True if export successful, False otherwise
        """
        if not self.client:
            logger.error("LangSmith client not available")
            return False

        try:
            # Get all examples
            examples = list(self.client.list_examples(dataset_name=dataset_name))

            # Convert to exportable format
            export_data = {
                "dataset_name": dataset_name,
                "export_date": datetime.now().isoformat(),
                "total_examples": len(examples),
                "examples": [],
            }

            for example in examples:
                export_data["examples"].append(
                    {"inputs": example.inputs, "outputs": example.outputs, "metadata": example.metadata}
                )

            # Save to file
            export_path.parent.mkdir(parents=True, exist_ok=True)
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported dataset {dataset_name} to {export_path}")
            return True

        except Exception as e:
            logger.error(f"Error exporting dataset: {e}")
            return False


# Global singleton instance
_dataset_manager_instance: Optional[DatasetManager] = None


def get_dataset_manager() -> DatasetManager:
    """Get a singleton instance of DatasetManager."""
    global _dataset_manager_instance
    if _dataset_manager_instance is None:
        _dataset_manager_instance = DatasetManager()
    return _dataset_manager_instance

