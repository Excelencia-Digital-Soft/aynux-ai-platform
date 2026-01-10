#!/usr/bin/env python
"""
CLI script to seed domain intent patterns directly to database.

Usage:
    uv run python -m app.scripts.run_seed_intents --org-id <uuid> --domain pharmacy
    uv run python -m app.scripts.run_seed_intents --domain pharmacy  # Uses system org
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from uuid import UUID

from app.database.async_db import get_async_db_context
from app.repositories.domain_intent_repository import DomainIntentRepository
from app.scripts.seed_domain_intents import get_seed_data_for_domain

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# System organization UUID (used when no specific org is provided)
SYSTEM_ORG_ID = UUID("00000000-0000-0000-0000-000000000000")


async def seed_intents(
    organization_id: UUID,
    domain_key: str,
    overwrite: bool = False,
) -> dict:
    """Seed intents for a domain."""
    seed_data = get_seed_data_for_domain(domain_key)
    if not seed_data:
        return {"success": False, "error": f"No seed data for domain '{domain_key}'"}

    async with get_async_db_context() as db:
        repo = DomainIntentRepository(db)
        added = 0
        skipped = 0
        errors: list[str] = []

        for intent_key, pattern_data in seed_data.items():
            try:
                existing = await repo.get_intent_by_key(
                    organization_id, domain_key, intent_key
                )
                if existing:
                    if overwrite:
                        await repo.delete_intent(existing.id)
                        logger.info(f"  Deleted existing intent: {intent_key}")
                    else:
                        skipped += 1
                        logger.info(f"  Skipped (exists): {intent_key}")
                        continue

                intent_data = {
                    "intent_key": intent_key,
                    "name": pattern_data.get(
                        "name", intent_key.replace("_", " ").title()
                    ),
                    "description": pattern_data.get(
                        "description", f"Auto-seeded: {intent_key}"
                    ),
                    "weight": pattern_data.get("weight", 1.0),
                    "exact_match": pattern_data.get("exact_match", False),
                    "priority": pattern_data.get("priority", 50),
                    "lemmas": pattern_data.get("lemmas", []),
                    "phrases": pattern_data.get("phrases", []),
                    "confirmation_patterns": pattern_data.get(
                        "confirmation_patterns", []
                    ),
                    "keywords": pattern_data.get("keywords", []),
                }

                await repo.create_intent(organization_id, domain_key, intent_data)
                added += 1
                logger.info(f"  Added: {intent_key}")

            except Exception as e:
                errors.append(f"{intent_key}: {e!s}")
                logger.error(f"  Error seeding {intent_key}: {e}")

    return {
        "success": len(errors) == 0,
        "domain_key": domain_key,
        "added": added,
        "skipped": skipped,
        "errors": errors if errors else None,
    }


def main():
    parser = argparse.ArgumentParser(description="Seed domain intent patterns")
    parser.add_argument(
        "--org-id",
        type=str,
        default=str(SYSTEM_ORG_ID),
        help=f"Organization UUID (default: {SYSTEM_ORG_ID})",
    )
    parser.add_argument(
        "--domain",
        type=str,
        required=True,
        help="Domain key (e.g., pharmacy, excelencia)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing intents",
    )

    args = parser.parse_args()

    try:
        org_id = UUID(args.org_id)
    except ValueError as e:
        logger.error(f"Invalid organization ID: {e}")
        return

    logger.info(f"Seeding intents for domain '{args.domain}'")
    logger.info(f"Organization: {org_id}")
    logger.info(f"Overwrite: {args.overwrite}")
    logger.info("-" * 40)

    result = asyncio.run(seed_intents(org_id, args.domain, args.overwrite))

    logger.info("-" * 40)
    logger.info(f"Result: {result}")

    if result["success"]:
        logger.info(
            f"SUCCESS: Added {result['added']}, Skipped {result['skipped']}"
        )
    else:
        logger.error(f"FAILED: {result.get('errors', result.get('error'))}")


if __name__ == "__main__":
    main()
