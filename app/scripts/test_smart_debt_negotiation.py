#!/usr/bin/env python
"""
Test script for Smart Debt Negotiation flow.

Tests:
1. Payment options calculation based on pharmacy config
2. Payment options formatting
3. Auth level determination
4. Items ofuscation based on auth level
5. Payment option selection handling

Usage:
    uv run python -m app.scripts.test_smart_debt_negotiation
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID

from app.core.tenancy.pharmacy_config_service import PharmacyConfig, PharmacyConfigService
from app.database.async_db import get_async_db_context
from app.domains.pharmacy.agents.nodes.debt_check_node import (
    AUTH_LEVEL_MEDIUM,
    AUTH_LEVEL_STRONG,
    AUTH_LEVEL_WEAK,
    DebtCheckNode,
)
from app.domains.pharmacy.domain.entities.pharmacy_debt import DebtItem

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# System organization UUID
SYSTEM_ORG_ID = UUID("00000000-0000-0000-0000-000000000000")


@dataclass
class TestResult:
    name: str
    passed: bool
    details: str


def create_test_config(
    half_percent: int = 50,
    min_percent: int = 30,
    min_amount: int = 1000,
) -> PharmacyConfig:
    """Create a test PharmacyConfig with required fields."""
    return PharmacyConfig(
        pharmacy_id=SYSTEM_ORG_ID,
        pharmacy_name="Test Pharmacy",
        pharmacy_address="123 Test St",
        pharmacy_phone="555-1234",
        pharmacy_hours="8:00-20:00",
        pharmacy_logo_path=None,
        mp_enabled=True,
        mp_access_token="test_token",
        mp_public_key="test_public",
        mp_webhook_secret="test_secret",
        mp_sandbox=True,
        mp_timeout=30,
        mp_notification_url="http://test/webhook",
        receipt_public_url_base="http://test/receipts",
        organization_id=SYSTEM_ORG_ID,
        payment_option_half_percent=half_percent,
        payment_option_minimum_percent=min_percent,
        payment_minimum_amount=min_amount,
    )


async def test_payment_options_calculation() -> list[TestResult]:
    """Test payment options calculation with various configs."""
    results: list[TestResult] = []
    node = DebtCheckNode()

    # Test 1: With default config (50% half, 30% minimum, $1000 min)
    config = create_test_config()

    # Test with $10,000 debt
    options = node._calculate_payment_options(10000.0, config)
    expected = {"full": 10000.0, "half": 5000.0, "minimum": 3000.0}

    if options == expected:
        results.append(TestResult(
            "Payment options ($10,000 debt)",
            True,
            f"Correct: {options}",
        ))
    else:
        results.append(TestResult(
            "Payment options ($10,000 debt)",
            False,
            f"Expected {expected}, got {options}",
        ))

    # Test 2: Small debt (below minimum threshold)
    options = node._calculate_payment_options(2000.0, config)
    # half = $1000, minimum = $1000 (same, so minimum not included)
    if options.get("full") == 2000.0 and options.get("half") == 1000.0:
        results.append(TestResult(
            "Payment options ($2,000 debt - small)",
            True,
            f"Correct: {options}",
        ))
    else:
        results.append(TestResult(
            "Payment options ($2,000 debt - small)",
            False,
            f"Got {options}",
        ))

    # Test 3: Very small debt (half below minimum)
    options = node._calculate_payment_options(1500.0, config)
    # half = $750 (< $1000), should not be included
    if "half" not in options:
        results.append(TestResult(
            "Payment options ($1,500 debt - very small)",
            True,
            f"Correctly excluded 'half' option: {options}",
        ))
    else:
        results.append(TestResult(
            "Payment options ($1,500 debt - very small)",
            False,
            f"Should not include 'half': {options}",
        ))

    # Test 4: Custom percentages (70% half, 40% minimum)
    custom_config = create_test_config(
        half_percent=70,
        min_percent=40,
        min_amount=500,
    )

    options = node._calculate_payment_options(5000.0, custom_config)
    expected_full = 5000.0
    expected_half = 3500.0  # 70%
    expected_min = 2000.0  # 40%

    if (
        options.get("full") == expected_full
        and options.get("half") == expected_half
        and options.get("minimum") == expected_min
    ):
        results.append(TestResult(
            "Payment options (custom 70%/40% config)",
            True,
            f"Correct: {options}",
        ))
    else:
        results.append(TestResult(
            "Payment options (custom 70%/40% config)",
            False,
            f"Expected full={expected_full}, half={expected_half}, min={expected_min}, got {options}",
        ))

    # Test 5: No config (use defaults)
    options = node._calculate_payment_options(10000.0, None)
    if options.get("full") == 10000.0:
        results.append(TestResult(
            "Payment options (no config - defaults)",
            True,
            f"Uses defaults correctly: {options}",
        ))
    else:
        results.append(TestResult(
            "Payment options (no config - defaults)",
            False,
            f"Got {options}",
        ))

    return results


async def test_payment_options_formatting() -> list[TestResult]:
    """Test payment options formatting."""
    results: list[TestResult] = []
    node = DebtCheckNode()

    config = create_test_config()

    options = {"full": 10000.0, "half": 5000.0, "minimum": 3000.0}
    formatted = node._format_payment_options(options, config)

    # Check all options are present
    checks = [
        ("*1.* Pago Total:" in formatted, "Full payment option"),
        ("*2.* Pago Parcial (50%):" in formatted, "Half payment option"),
        ("*3.* Pago Mínimo (30%):" in formatted, "Minimum payment option"),
        ("*4.* Otro monto" in formatted, "Custom option"),
        ("$10,000.00" in formatted, "Full amount formatted"),
        ("$5,000.00" in formatted, "Half amount formatted"),
        ("$3,000.00" in formatted, "Minimum amount formatted"),
    ]

    for check, name in checks:
        results.append(TestResult(
            f"Format: {name}",
            check,
            formatted if not check else "OK",
        ))

    return results


async def test_auth_level_determination() -> list[TestResult]:
    """Test authentication level determination."""
    results: list[TestResult] = []
    node = DebtCheckNode()

    # Test STRONG: is_self=True
    state = {"is_self": True}
    level = node._determine_auth_level(state)
    results.append(TestResult(
        "Auth level STRONG (is_self=True)",
        level == AUTH_LEVEL_STRONG,
        f"Got: {level}",
    ))

    # Test MEDIUM: has active_registered_person_id
    state = {"is_self": False, "active_registered_person_id": "some-uuid"}
    level = node._determine_auth_level(state)
    results.append(TestResult(
        "Auth level MEDIUM (registered person)",
        level == AUTH_LEVEL_MEDIUM,
        f"Got: {level}",
    ))

    # Test WEAK: neither is_self nor registered person
    state = {"is_self": False}
    level = node._determine_auth_level(state)
    results.append(TestResult(
        "Auth level WEAK (DNI+Name only)",
        level == AUTH_LEVEL_WEAK,
        f"Got: {level}",
    ))

    # Test WEAK: empty state
    state = {}
    level = node._determine_auth_level(state)
    results.append(TestResult(
        "Auth level WEAK (empty state)",
        level == AUTH_LEVEL_WEAK,
        f"Got: {level}",
    ))

    return results


async def test_items_ofuscation() -> list[TestResult]:
    """Test debt items formatting with ofuscation."""
    results: list[TestResult] = []
    node = DebtCheckNode()

    # Create sample debt items
    from decimal import Decimal

    items = [
        DebtItem(
            description="Medicamento A",
            amount=Decimal("1000.0"),
            quantity=2,
            unit_price=Decimal("500.0"),
            product_code="MED001",
            invoice_date="2024-01-15",
        ),
        DebtItem(
            description="Medicamento B",
            amount=Decimal("1500.0"),
            quantity=1,
            unit_price=Decimal("1500.0"),
            product_code="MED002",
            invoice_date="2024-01-16",
        ),
    ]

    # Test STRONG auth - should show full details
    formatted = node._format_items_by_auth_level(items, AUTH_LEVEL_STRONG)
    # Should contain individual item descriptions
    if "Medicamento A" in formatted or "$1,000.00" in formatted:
        results.append(TestResult(
            "STRONG auth: Full details shown",
            True,
            "Items shown with descriptions",
        ))
    else:
        results.append(TestResult(
            "STRONG auth: Full details shown",
            False,
            f"Expected full details, got: {formatted}",
        ))

    # Test MEDIUM auth - should be ofuscated
    formatted = node._format_items_by_auth_level(items, AUTH_LEVEL_MEDIUM)
    if "2 items" in formatted and "Medicamento" not in formatted:
        results.append(TestResult(
            "MEDIUM auth: Ofuscated (no product names)",
            True,
            formatted,
        ))
    else:
        results.append(TestResult(
            "MEDIUM auth: Ofuscated (no product names)",
            False,
            f"Should not show product names: {formatted}",
        ))

    # Test WEAK auth - should also be ofuscated
    formatted = node._format_items_by_auth_level(items, AUTH_LEVEL_WEAK)
    if "2 items" in formatted and "Medicamento" not in formatted:
        results.append(TestResult(
            "WEAK auth: Ofuscated (no product names)",
            True,
            formatted,
        ))
    else:
        results.append(TestResult(
            "WEAK auth: Ofuscated (no product names)",
            False,
            f"Should not show product names: {formatted}",
        ))

    # Test empty items
    formatted = node._format_items_by_auth_level([], AUTH_LEVEL_STRONG)
    if "Sin detalle" in formatted:
        results.append(TestResult(
            "Empty items: Shows 'Sin detalle'",
            True,
            formatted,
        ))
    else:
        results.append(TestResult(
            "Empty items: Shows 'Sin detalle'",
            False,
            f"Expected 'Sin detalle', got: {formatted}",
        ))

    return results


async def test_database_config_loading() -> list[TestResult]:
    """Test loading pharmacy config from database."""
    results: list[TestResult] = []

    async with get_async_db_context() as db:
        config_service = PharmacyConfigService(db)

        # Try to load config for system org
        try:
            config = await config_service.get_config(SYSTEM_ORG_ID)

            results.append(TestResult(
                "Load pharmacy config from DB",
                True,
                f"Loaded: {config.pharmacy_name}",
            ))

            # Check payment option fields
            results.append(TestResult(
                "Config has payment_option_half_percent",
                hasattr(config, "payment_option_half_percent"),
                f"Value: {config.payment_option_half_percent}%",
            ))

            results.append(TestResult(
                "Config has payment_option_minimum_percent",
                hasattr(config, "payment_option_minimum_percent"),
                f"Value: {config.payment_option_minimum_percent}%",
            ))

            results.append(TestResult(
                "Config has payment_minimum_amount",
                hasattr(config, "payment_minimum_amount"),
                f"Value: ${config.payment_minimum_amount}",
            ))

        except Exception as e:
            # No config found is OK - just means admin needs to configure it
            error_msg = str(e)
            if "No pharmacy config found" in error_msg:
                results.append(TestResult(
                    "Database schema ready (no config for system org)",
                    True,
                    "Schema OK - admin needs to create pharmacy_merchant_configs entry",
                ))
            else:
                results.append(TestResult(
                    "Load pharmacy config from DB",
                    False,
                    f"Error: {e}",
                ))

    return results


async def main():
    logger.info("=" * 70)
    logger.info("SMART DEBT NEGOTIATION FLOW TEST")
    logger.info("=" * 70)

    all_results: list[TestResult] = []

    # Run all test suites
    test_suites = [
        ("Payment Options Calculation", test_payment_options_calculation),
        ("Payment Options Formatting", test_payment_options_formatting),
        ("Auth Level Determination", test_auth_level_determination),
        ("Items Ofuscation", test_items_ofuscation),
        ("Database Config Loading", test_database_config_loading),
    ]

    for suite_name, suite_func in test_suites:
        logger.info("-" * 70)
        logger.info(f"Test Suite: {suite_name}")
        logger.info("-" * 70)

        try:
            results = await suite_func()
            all_results.extend(results)

            for r in results:
                status = "✅ PASS" if r.passed else "❌ FAIL"
                logger.info(f"{status} | {r.name} | {r.details}")
        except Exception as e:
            logger.error(f"Suite failed with error: {e}")
            all_results.append(TestResult(suite_name, False, str(e)))

    # Summary
    passed = sum(1 for r in all_results if r.passed)
    failed = sum(1 for r in all_results if not r.passed)

    logger.info("=" * 70)
    logger.info(f"RESULTS: {passed} passed, {failed} failed")
    logger.info("=" * 70)

    if failed == 0:
        logger.info("\n✅ ALL TESTS PASSED!")
    else:
        logger.error("\n❌ SOME TESTS FAILED!")

    return failed == 0


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
