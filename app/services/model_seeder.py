# ============================================================================
# SCOPE: GLOBAL
# Description: Seeder de modelos externos desde archivo de configuración JSON.
#              Permite inicializar la base de datos con modelos de OpenAI,
#              Anthropic, DeepSeek, etc.
# ============================================================================
"""
Model Seeder - Seeds external AI models from configuration.

Single Responsibility: Load and seed model definitions from JSON config.
Separates data (JSON file) from logic (seeding process).

Usage:
    repository = AIModelRepository(db)
    seeder = ModelSeeder(repository)

    result = await seeder.seed_external_models()
    # {"added": 5, "skipped": 3}
"""

import json
import logging
from pathlib import Path

from app.models.db.ai_model import AIModel
from app.repositories.ai_model_repository import AIModelRepository

logger = logging.getLogger(__name__)

# Default path to seed data file
SEED_FILE_PATH = Path(__file__).parent.parent / "config" / "seed_models.json"


class ModelSeeder:
    """
    Model seeder from JSON configuration.

    Single Responsibility: Seed models from config file.
    """

    def __init__(
        self,
        repository: AIModelRepository,
        seed_file_path: Path | None = None,
    ) -> None:
        """Initialize seeder with repository and config path.

        Args:
            repository: AIModelRepository for data access
            seed_file_path: Path to seed JSON file (defaults to config/seed_models.json)
        """
        self._repository = repository
        self._seed_file = seed_file_path or SEED_FILE_PATH

    def load_seed_data(self) -> list[dict]:
        """Load model definitions from JSON config file.

        Returns:
            List of model definition dicts

        Raises:
            FileNotFoundError: If seed file doesn't exist
            json.JSONDecodeError: If file is invalid JSON
        """
        if not self._seed_file.exists():
            logger.warning(f"Seed file not found: {self._seed_file}")
            return []

        with open(self._seed_file) as f:
            data = json.load(f)

        models = data.get("models", [])
        logger.debug(f"Loaded {len(models)} model definitions from {self._seed_file}")
        return models

    async def seed_external_models(self) -> dict[str, int]:
        """Seed database with models from JSON config.

        Adds models that don't already exist.
        All seeded models are disabled by default.

        Returns:
            Dict with added and skipped counts
        """
        seed_data = self.load_seed_data()

        if not seed_data:
            logger.info("No seed data found, skipping seeding")
            return {"added": 0, "skipped": 0}

        result = {"added": 0, "skipped": 0}

        for model_data in seed_data:
            model_id = model_data.get("model_id")
            if not model_id:
                logger.warning(f"Skipping model without model_id: {model_data}")
                continue

            # Check if already exists
            existing = await self._repository.get_by_model_id(model_id)
            if existing:
                result["skipped"] += 1
                continue

            # Create new model
            model = AIModel(
                model_id=model_data["model_id"],
                provider=model_data["provider"],
                model_type=model_data.get("model_type", "llm"),
                display_name=model_data["display_name"],
                description=model_data.get("description"),
                family=model_data.get("family"),
                context_window=model_data.get("context_window"),
                max_output_tokens=model_data.get("max_output_tokens", 4096),
                supports_streaming=model_data.get("supports_streaming", True),
                supports_functions=model_data.get("supports_functions", False),
                supports_vision=model_data.get("supports_vision", False),
                is_enabled=False,  # Always disabled by default
                sort_order=model_data.get("sort_order", 100),
                sync_source="seed",
            )

            await self._repository.create(model)
            result["added"] += 1
            logger.debug(f"Seeded model: {model_id}")

        logger.info(
            f"Model seeding complete: {result['added']} added, "
            f"{result['skipped']} skipped"
        )
        return result

    async def seed_if_empty(self) -> dict[str, int]:
        """Seed models only if no external models exist.

        Convenience method for initial setup.

        Returns:
            Dict with added and skipped counts
        """
        # Check if any seeded models exist
        existing_count = 0
        for provider in ["openai", "anthropic", "deepseek"]:
            models = await self._repository.find_all(provider=provider)
            existing_count += len(models)

        if existing_count > 0:
            logger.info(
                f"Found {existing_count} existing external models, skipping seed"
            )
            return {"added": 0, "skipped": 0}

        return await self.seed_external_models()
