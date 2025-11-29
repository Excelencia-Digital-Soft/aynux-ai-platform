"""
Dataset management for LangSmith evaluation in Aynux.

Single Responsibility: CRUD operations for LangSmith evaluation datasets.
Uses golden_examples module for test data.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from langsmith.schemas import Dataset, Example

from app.config.langsmith_config import get_tracer
from app.evaluation.golden_examples import (
    DATASET_CONFIGS,
    ConversationExample,
    get_golden_examples,
)

logger = logging.getLogger(__name__)


class DatasetManager:
    """Manages evaluation datasets for the Aynux multi-agent system."""

    def __init__(self):
        self.tracer = get_tracer()
        self.client = self.tracer.client if self.tracer.client else None
        self.dataset_configs = DATASET_CONFIGS
        logger.info("DatasetManager initialized")

    async def create_dataset(
        self,
        dataset_name: str,
        description: str = "",
    ) -> Dataset | None:
        """Create a new evaluation dataset in LangSmith."""
        if not self.client:
            logger.error("LangSmith client not available")
            return None

        try:
            existing = self.client.list_datasets(dataset_name=dataset_name)
            for ds in existing:
                if ds.name == dataset_name:
                    logger.info(f"Dataset '{dataset_name}' already exists")
                    return ds

            dataset = self.client.create_dataset(
                dataset_name=dataset_name,
                description=description or f"Aynux evaluation dataset: {dataset_name}",
            )
            logger.info(f"Created dataset: {dataset_name}")
            return dataset

        except Exception as e:
            logger.error(f"Error creating dataset: {e}")
            return None

    async def add_examples_to_dataset(
        self,
        dataset_name: str,
        examples: list[ConversationExample],
    ) -> bool:
        """Add examples to an existing dataset."""
        if not self.client:
            logger.error("LangSmith client not available")
            return False

        try:
            for example in examples:
                langsmith_example = self._convert_to_langsmith_example(
                    example, dataset_name
                )
                self.client.create_example(
                    inputs=langsmith_example.inputs,
                    outputs=langsmith_example.outputs,
                    metadata=langsmith_example.metadata,
                    dataset_name=dataset_name,
                )

            logger.info(f"Added {len(examples)} examples to '{dataset_name}'")
            return True

        except Exception as e:
            logger.error(f"Error adding examples: {e}")
            return False

    def _convert_to_langsmith_example(
        self,
        example: ConversationExample,
        dataset_name: str,
    ) -> Example:
        """Convert ConversationExample to LangSmith Example."""
        return Example(
            inputs={"message": example.user_message},
            outputs={
                "expected_agent": example.expected_agent,
                "expected_response_type": example.expected_response_type,
                "expected_completion": example.expected_completion,
                "intent_category": example.intent_category,
                "language": example.language,
                "complexity": example.complexity,
                "business_context": example.business_context,
            },
            metadata={
                "dataset": dataset_name,
                "created_at": datetime.now().isoformat(),
                **example.metadata,
            },
        )

    def get_golden_examples(self) -> dict[str, list[ConversationExample]]:
        """Get curated golden examples (delegated to module)."""
        return get_golden_examples()

    async def initialize_all_datasets(self) -> dict[str, bool]:
        """Initialize all standard datasets with golden examples."""
        results = {}
        golden_examples = self.get_golden_examples()

        for dataset_name, examples in golden_examples.items():
            config = self.dataset_configs.get(dataset_name, {})
            description = config.get("description", f"Evaluation dataset: {dataset_name}")

            dataset = await self.create_dataset(dataset_name, description)
            if dataset:
                success = await self.add_examples_to_dataset(dataset_name, examples)
                results[dataset_name] = success
            else:
                results[dataset_name] = False

        logger.info(f"Dataset initialization: {results}")
        return results

    async def update_dataset_from_production(
        self,
        dataset_name: str,
        production_examples: list[dict[str, Any]],
        max_examples: int = 100,
    ) -> int:
        """Update dataset with production conversation examples."""
        if not self.client:
            logger.error("LangSmith client not available")
            return 0

        added_count = 0
        try:
            for prod_example in production_examples[:max_examples]:
                try:
                    example = ConversationExample(
                        user_message=prod_example.get("message", ""),
                        expected_agent=prod_example.get("routed_agent", "unknown"),
                        expected_response_type=prod_example.get("response_type", "unknown"),
                        intent_category=prod_example.get("detected_intent", "unknown"),
                        complexity=prod_example.get("complexity", "moderate"),
                        metadata={
                            "source": "production",
                            "timestamp": prod_example.get("timestamp"),
                            "session_id": prod_example.get("session_id"),
                            "user_satisfaction": prod_example.get("satisfaction_score"),
                        },
                    )

                    langsmith_example = self._convert_to_langsmith_example(
                        example, dataset_name
                    )
                    self.client.create_example(
                        inputs=langsmith_example.inputs,
                        outputs=langsmith_example.outputs,
                        metadata=langsmith_example.metadata,
                        dataset_name=dataset_name,
                    )
                    added_count += 1

                except Exception as e:
                    logger.warning(f"Skipping invalid example: {e}")
                    continue

            logger.info(f"Added {added_count} production examples to '{dataset_name}'")
            return added_count

        except Exception as e:
            logger.error(f"Error updating dataset from production: {e}")
            return added_count

    def get_dataset_statistics(self, dataset_name: str) -> dict[str, Any]:
        """Get statistics for a specific dataset."""
        if not self.client:
            return {"error": "LangSmith client not available"}

        try:
            datasets = list(self.client.list_datasets(dataset_name=dataset_name))
            if not datasets:
                return {"error": f"Dataset '{dataset_name}' not found"}

            dataset = datasets[0]
            examples = list(self.client.list_examples(dataset_name=dataset_name))

            # Analyze examples with properly typed counters
            agents: dict[str, int] = {}
            intents: dict[str, int] = {}
            complexity_counts: dict[str, int] = {"simple": 0, "moderate": 0, "complex": 0}
            languages: dict[str, int] = {}

            for ex in examples:
                outputs = ex.outputs or {}

                # Count agents
                agent = outputs.get("expected_agent", "unknown")
                agents[agent] = agents.get(agent, 0) + 1

                # Count intents
                intent = outputs.get("intent_category", "unknown")
                intents[intent] = intents.get(intent, 0) + 1

                # Count complexity
                complexity = outputs.get("complexity", "moderate")
                if complexity in complexity_counts:
                    complexity_counts[complexity] += 1

                # Count languages
                lang = outputs.get("language", "es")
                languages[lang] = languages.get(lang, 0) + 1

            return {
                "dataset_name": dataset_name,
                "total_examples": len(examples),
                "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
                "agents": agents,
                "intents": intents,
                "complexity": complexity_counts,
                "languages": languages,
            }

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {"error": str(e)}

    async def export_dataset(
        self,
        dataset_name: str,
        export_path: Path,
    ) -> bool:
        """Export dataset to JSON file."""
        if not self.client:
            logger.error("LangSmith client not available")
            return False

        try:
            examples = list(self.client.list_examples(dataset_name=dataset_name))

            export_data = {
                "dataset_name": dataset_name,
                "exported_at": datetime.now().isoformat(),
                "example_count": len(examples),
                "examples": [
                    {
                        "inputs": ex.inputs,
                        "outputs": ex.outputs,
                        "metadata": ex.metadata,
                    }
                    for ex in examples
                ],
            }

            export_path.parent.mkdir(parents=True, exist_ok=True)
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported {len(examples)} examples to {export_path}")
            return True

        except Exception as e:
            logger.error(f"Error exporting dataset: {e}")
            return False


def get_dataset_manager() -> DatasetManager:
    """Get singleton DatasetManager instance."""
    return DatasetManager()
