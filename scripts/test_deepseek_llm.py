"""
Test script for DeepSeek API via OpenAICompatibleLLM.

Tests the integration with DeepSeek's API including:
- Basic generation (deepseek-chat)
- Reasoning generation (deepseek-reasoner)
- Think tag cleaning
- Health check

Usage:
    uv run python scripts/test_deepseek_llm.py
"""
from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_settings() -> bool:
    """Test that DeepSeek settings are loaded correctly."""
    from app.config.settings import get_settings

    print("\n" + "=" * 60)
    print("TEST 0: Configuration Check")
    print("=" * 60)

    settings = get_settings()

    print(f"EXTERNAL_LLM_ENABLED: {settings.EXTERNAL_LLM_ENABLED}")
    print(f"EXTERNAL_LLM_PROVIDER: {settings.EXTERNAL_LLM_PROVIDER}")
    print(f"EXTERNAL_LLM_API_KEY: {settings.EXTERNAL_LLM_API_KEY[:10]}...")
    print(f"EXTERNAL_LLM_MODEL_COMPLEX: {settings.EXTERNAL_LLM_MODEL_COMPLEX}")
    print(f"EXTERNAL_LLM_MODEL_REASONING: {settings.EXTERNAL_LLM_MODEL_REASONING}")
    print(f"Base URL resolved: {settings.external_llm_base_url_resolved}")

    if not settings.EXTERNAL_LLM_API_KEY:
        print("❌ No API key configured!")
        return False

    print("✅ Configuration OK")
    return True


async def test_llm_initialization() -> bool:
    """Test OpenAICompatibleLLM initialization."""
    from app.integrations.llm.openai_compatible import OpenAICompatibleLLM

    print("\n" + "=" * 60)
    print("TEST 1: LLM Initialization")
    print("=" * 60)

    try:
        llm = OpenAICompatibleLLM()
        print(f"Provider: {llm.provider}")
        print(f"Model (COMPLEX): {llm._model_complex}")
        print(f"Model (REASONING): {llm._model_reasoning}")
        print(f"Base URL: {llm._base_url}")
        print("✅ Initialization OK")
        return True
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        logger.exception("LLM init error")
        return False


async def test_simple_generation() -> bool:
    """Test basic text generation with deepseek-chat."""
    from app.integrations.llm.model_provider import ModelComplexity
    from app.integrations.llm.openai_compatible import OpenAICompatibleLLM

    print("\n" + "=" * 60)
    print("TEST 2: Simple Generation (deepseek-chat)")
    print("=" * 60)

    try:
        llm = OpenAICompatibleLLM()

        prompt = "Responde en una sola línea: ¿Cuál es la capital de Argentina?"
        print(f"Prompt: {prompt}")

        start = time.time()
        response = await llm.generate(
            prompt,
            complexity=ModelComplexity.COMPLEX,
            temperature=0.3,
            max_tokens=100,
        )
        elapsed = time.time() - start

        print(f"Response: {response}")
        print(f"Time: {elapsed:.2f}s")
        print("✅ Generation OK")
        return True

    except Exception as e:
        print(f"❌ Generation failed: {e}")
        logger.exception("Generation error")
        return False


async def test_chat_generation() -> bool:
    """Test chat-style generation with multiple messages."""
    from app.integrations.llm.model_provider import ModelComplexity
    from app.integrations.llm.openai_compatible import OpenAICompatibleLLM

    print("\n" + "=" * 60)
    print("TEST 3: Chat Generation")
    print("=" * 60)

    try:
        llm = OpenAICompatibleLLM()

        messages = [
            {"role": "system", "content": "Eres un asistente útil que responde en español de forma breve."},
            {"role": "user", "content": "¿Qué es Python?"},
        ]

        print(f"Messages: {messages}")

        start = time.time()
        response = await llm.generate_chat(
            messages,
            complexity=ModelComplexity.COMPLEX,
            temperature=0.5,
            max_tokens=150,
        )
        elapsed = time.time() - start

        print(f"Response: {response[:300]}...")
        print(f"Time: {elapsed:.2f}s")
        print("✅ Chat generation OK")
        return True

    except Exception as e:
        print(f"❌ Chat generation failed: {e}")
        logger.exception("Chat error")
        return False


async def test_reasoning_generation() -> bool:
    """Test reasoning model (deepseek-reasoner) with think tag cleaning."""
    from app.integrations.llm.model_provider import ModelComplexity
    from app.integrations.llm.openai_compatible import OpenAICompatibleLLM

    print("\n" + "=" * 60)
    print("TEST 4: Reasoning Generation (deepseek-reasoner)")
    print("=" * 60)

    try:
        llm = OpenAICompatibleLLM()

        prompt = "Si tengo 3 manzanas y le doy 1 a Juan, ¿cuántas me quedan? Explica brevemente."
        print(f"Prompt: {prompt}")

        start = time.time()
        response = await llm.generate(
            prompt,
            complexity=ModelComplexity.REASONING,
            temperature=0.2,
            max_tokens=200,
        )
        elapsed = time.time() - start

        print(f"Response: {response}")
        print(f"Time: {elapsed:.2f}s")

        # Verify think tags were cleaned
        if "<think>" in response:
            print("⚠️  Warning: <think> tags not cleaned!")
        else:
            print("✅ Think tags cleaned (if any)")

        print("✅ Reasoning OK")
        return True

    except Exception as e:
        print(f"❌ Reasoning failed: {e}")
        logger.exception("Reasoning error")
        return False


async def test_health_check() -> bool:
    """Test health check endpoint."""
    from app.integrations.llm.openai_compatible import OpenAICompatibleLLM

    print("\n" + "=" * 60)
    print("TEST 5: Health Check")
    print("=" * 60)

    try:
        llm = OpenAICompatibleLLM()

        start = time.time()
        healthy = await llm.health_check()
        elapsed = time.time() - start

        print(f"Healthy: {'✅ YES' if healthy else '❌ NO'}")
        print(f"Time: {elapsed:.2f}s")
        return healthy

    except Exception as e:
        print(f"❌ Health check failed: {e}")
        logger.exception("Health check error")
        return False


async def test_generate_response() -> bool:
    """Test generate_response method (OllamaLLM compatibility)."""
    from app.integrations.llm.model_provider import ModelComplexity
    from app.integrations.llm.openai_compatible import OpenAICompatibleLLM

    print("\n" + "=" * 60)
    print("TEST 6: Generate Response (OllamaLLM compat)")
    print("=" * 60)

    try:
        llm = OpenAICompatibleLLM()

        system = "Eres un experto en programación. Responde de forma concisa."
        user = "¿Qué es una función lambda en Python?"

        print(f"System: {system}")
        print(f"User: {user}")

        start = time.time()
        response = await llm.generate_response(
            system_prompt=system,
            user_prompt=user,
            complexity=ModelComplexity.COMPLEX,
            temperature=0.5,
            max_tokens=150,
        )
        elapsed = time.time() - start

        print(f"Response: {response[:300]}...")
        print(f"Time: {elapsed:.2f}s")
        print("✅ Generate response OK")
        return True

    except Exception as e:
        print(f"❌ Generate response failed: {e}")
        logger.exception("Generate response error")
        return False


async def main() -> bool:
    """Run all tests."""
    print("\n" + "=" * 60)
    print("  DEEPSEEK API TEST SUITE")
    print("=" * 60)

    results: dict[str, bool] = {}

    # Test 0: Configuration
    results["settings"] = await test_settings()

    if not results["settings"]:
        print("\n❌ Configuration issues. Fix settings first.")
        return False

    # Test 1: Initialization
    results["init"] = await test_llm_initialization()

    if not results["init"]:
        print("\n❌ Initialization failed. Check API key.")
        return False

    # Test 2: Simple generation
    results["simple_gen"] = await test_simple_generation()

    # Test 3: Chat generation
    results["chat_gen"] = await test_chat_generation()

    # Test 4: Reasoning (skip if simple fails to save API quota)
    if results["simple_gen"]:
        results["reasoning"] = await test_reasoning_generation()
    else:
        print("\n⚠️  Skipping reasoning test (simple generation failed)")
        results["reasoning"] = False

    # Test 5: Health check
    results["health"] = await test_health_check()

    # Test 6: Generate response
    if results["simple_gen"]:
        results["generate_response"] = await test_generate_response()
    else:
        results["generate_response"] = False

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
