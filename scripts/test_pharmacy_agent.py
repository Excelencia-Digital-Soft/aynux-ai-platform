"""
Test script for Pharmacy Operations Agent.

Tests connectivity to PLEX ERP and the PharmacyGraph workflow.

Usage:
    uv run python scripts/test_pharmacy_agent.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_plex_connection() -> bool:
    """Test PLEX API connectivity."""
    from app.clients.plex_client import PlexClient

    print("\n" + "=" * 60)
    print("TEST 1: PLEX Connection")
    print("=" * 60)

    try:
        client = PlexClient()
        async with client:
            success = await client.test_connection()
            print(f"Connection: {'✅ OK' if success else '❌ FAILED'}")
            print(f"Base URL: {client.base_url}")
            return success
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        logger.exception("PLEX connection error")
        return False


async def test_customer_search(phone: str = "2645631000") -> bool:
    """Test customer search by phone."""
    from app.clients.plex_client import PlexClient

    print("\n" + "=" * 60)
    print("TEST 2: Customer Search")
    print("=" * 60)

    try:
        client = PlexClient()
        async with client:
            customers = await client.search_customer(phone=phone)
            print(f"Search phone: {phone}")
            print(f"Found: {len(customers)} customer(s)")

            for c in customers:
                print(f"  - ID: {c.id}, Name: {c.nombre}")

            if len(customers) == 0:
                print("  (No customers with this phone - search API works)")
                return True  # API works, just no data

            return True
    except Exception as e:
        print(f"❌ Customer search failed: {e}")
        logger.exception("Customer search error")
        return False


async def test_customer_balance(customer_id: int | None = None) -> bool:
    """Test getting customer balance."""
    from app.clients.plex_client import PlexClient

    print("\n" + "=" * 60)
    print("TEST 3: Customer Balance")
    print("=" * 60)

    if customer_id is None:
        print("⚠️  No customer ID provided, skipping balance test")
        return True

    try:
        client = PlexClient()
        async with client:
            balance = await client.get_customer_balance(customer_id=customer_id, detailed=True)
            print(f"Customer ID: {customer_id}")
            print(f"Balance data: {balance}")

            if balance:
                saldo = balance.get("saldo", 0)
                print(f"Total debt: ${saldo:,.2f}")
                return True
            return False
    except Exception as e:
        print(f"❌ Balance query failed: {e}")
        logger.exception("Balance query error")
        return False


async def test_pharmacy_graph_init() -> bool:
    """Test PharmacyGraph initialization."""
    from app.domains.pharmacy.agents.graph import PharmacyGraph

    print("\n" + "=" * 60)
    print("TEST 4: PharmacyGraph Initialization")
    print("=" * 60)

    try:
        graph = PharmacyGraph()
        graph.initialize()
        print("✅ PharmacyGraph initialized successfully")
        print(f"Graph compiled: {graph.app is not None}")
        return True
    except Exception as e:
        print(f"❌ PharmacyGraph initialization failed: {e}")
        logger.exception("Graph init error")
        return False


async def test_pharmacy_agent_health() -> bool:
    """Test PharmacyOperationsAgent health check."""
    from app.domains.pharmacy.agents.pharmacy_operations_agent import (
        PharmacyOperationsAgent,
    )

    print("\n" + "=" * 60)
    print("TEST 5: Agent Health Check")
    print("=" * 60)

    try:
        agent = PharmacyOperationsAgent()
        health = await agent.health_check()

        print(f"Agent name: {agent.agent_name}")
        print(f"Status: {health.get('status')}")
        print(f"Subgraph health: {health.get('subgraph', {})}")

        return health.get("status") == "healthy"
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        logger.exception("Health check error")
        return False


async def test_settings_loaded() -> bool:
    """Test that pharmacy settings are loaded correctly."""
    from app.config.settings import get_settings

    print("\n" + "=" * 60)
    print("TEST 0: Configuration Check")
    print("=" * 60)

    try:
        settings = get_settings()

        # Check PLEX settings
        plex_url = settings.PLEX_API_BASE_URL
        plex_user = settings.PLEX_API_USER
        plex_timeout = settings.PLEX_API_TIMEOUT

        print(f"PLEX_API_BASE_URL: {plex_url}")
        print(f"PLEX_API_USER: {plex_user}")
        print(f"PLEX_API_TIMEOUT: {plex_timeout}")

        # Check agent enabled
        enabled = "pharmacy_operations_agent" in settings.ENABLED_AGENTS
        print(f"pharmacy_operations_agent enabled: {'✅ YES' if enabled else '❌ NO'}")

        if not enabled:
            print(f"Current ENABLED_AGENTS: {settings.ENABLED_AGENTS}")

        return enabled and bool(plex_url) and bool(plex_user)
    except Exception as e:
        print(f"❌ Settings check failed: {e}")
        logger.exception("Settings error")
        return False


async def main() -> bool:
    """Run all tests."""
    print("\n" + "=" * 60)
    print("  PHARMACY AGENT TEST SUITE")
    print("=" * 60)

    results: dict[str, bool] = {}

    # Test 0: Configuration
    results["settings"] = await test_settings_loaded()

    if not results["settings"]:
        print("\n❌ Configuration issues detected. Fix settings first.")
        return False

    # Test 1: PLEX Connection
    results["plex_connection"] = await test_plex_connection()

    # Test 2: Customer Search (only if connected)
    customer_id = None
    if results["plex_connection"]:
        results["customer_search"] = await test_customer_search()

        # Try to get a customer ID for balance test
        if results["customer_search"]:
            from app.clients.plex_client import PlexAPIError, PlexClient

            try:
                async with PlexClient() as client:
                    # Use same phone from test_customer_search
                    customers = await client.search_customer(phone="2645631000")
                    if customers:
                        customer_id = customers[0].id
            except PlexAPIError as e:
                print(f"⚠️  Could not get customer for balance test: {e}")
                customer_id = None

    # Test 3: Customer Balance
    if results.get("plex_connection"):
        results["customer_balance"] = await test_customer_balance(customer_id)

    # Test 4: Graph Initialization
    results["graph_init"] = await test_pharmacy_graph_init()

    # Test 5: Agent Health
    results["agent_health"] = await test_pharmacy_agent_health()

    # Summary
    print("\n" + "=" * 60)
    print("  TEST SUMMARY")
    print("=" * 60)

    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test}: {status}")

    all_passed = all(results.values())
    print("\n" + "-" * 60)
    print(f"Overall: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
