#!/usr/bin/env python3
"""
Test script to verify the supervisor agent's response enhancement functionality
"""

import asyncio
import logging

# Add the project root to Python path
import sys
from pathlib import Path

from app.agents.integrations.ollama_integration import OllamaIntegration
from app.agents.subagent.supervisor_agent import SupervisorAgent

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))


async def test_supervisor_enhancement():
    """Test the supervisor agent's response enhancement capability"""

    print("\n" + "=" * 50)
    print("Testing Supervisor Agent Response Enhancement")
    print("=" * 50 + "\n")

    # Initialize Ollama integration
    ollama_config = {"api_url": "http://localhost:11434", "model": "deepseek-r1:7b", "timeout": 30}
    ollama = OllamaIntegration(ollama_config)

    # Initialize supervisor agent with enhancement enabled
    supervisor_config = {"enable_response_enhancement": True, "quality_threshold": 0.7, "max_retries": 2}
    supervisor = SupervisorAgent(ollama=ollama, config=supervisor_config)

    # Test cases with different scenarios - more complete responses for better scores
    test_cases = [
        {
            "name": "Product Query Response",
            "user_message": "¿Cuánto cuesta la laptop HP?",
            "agent_response": "La laptop HP modelo Pavilion 15 tiene un precio de $1200. Este producto está disponible en stock y cuenta con las siguientes características: procesador Intel Core i5, 8GB RAM, 512GB SSD. El precio incluye garantía de 1 año.",
            "expected_language": "es",
        },
        {
            "name": "English Product Query",
            "user_message": "What is the price of the Dell laptop?",
            "agent_response": "The Dell Inspiron laptop costs $1500. It's currently available in stock with free shipping. This model features an Intel Core i7 processor, 16GB RAM, and 1TB SSD storage. The price includes a 2-year warranty and technical support.",
            "expected_language": "en",
        },
        {
            "name": "Support Request",
            "user_message": "Tengo un problema con mi pedido, ¿qué puedo hacer?",
            "agent_response": "Puedo ayudarte con tu pedido. He verificado que tu pedido número #12345 está actualmente en proceso de envío y llegará en 3-5 días hábiles. Si necesitas hacer algún cambio o tienes alguna pregunta específica sobre el pedido, puedes contactar a nuestro equipo de soporte o verificar el estado en tu cuenta.",
            "expected_language": "es",
        },
    ]

    for test_case in test_cases:
        print(f"\n{'=' * 40}")
        print(f"Test Case: {test_case['name']}")
        print(f"{'=' * 40}")

        # Create state dict simulating a conversation
        state_dict = {
            "messages": [
                {"role": "user", "content": test_case["user_message"]},
                {"role": "assistant", "content": test_case["agent_response"]},
            ],
            "current_agent": "product_agent",
            "supervisor_retry_count": 0,
            "error_count": 0,
            "customer_data": {"name": "Juan Pérez"},
        }

        try:
            # Process with supervisor
            result = await supervisor._process_internal(message=test_case["user_message"], state_dict=state_dict)

            # Display results
            print(f"\nUser Message: {test_case['user_message']}")
            print(f"Original Response: {test_case['agent_response']}")

            if result.get("enhanced_response"):
                print(f"\n✅ Enhanced Response Generated:")
                print("-" * 40)
                print(result["enhanced_response"])
                print("-" * 40)
            else:
                print("\n⚠️ No enhanced response generated")

            # Show evaluation details
            evaluation = result.get("supervisor_evaluation", {})
            print(f"\nQuality Evaluation:")
            print(f"  - Overall Score: {evaluation.get('overall_score', 0):.2f}")
            print(f"  - Completeness: {evaluation.get('completeness_score', 0):.2f}")
            print(f"  - Relevance: {evaluation.get('relevance_score', 0):.2f}")
            print(f"  - Clarity: {evaluation.get('clarity_score', 0):.2f}")
            print(f"  - Helpfulness: {evaluation.get('helpfulness_score', 0):.2f}")

            # Show flow decision
            flow = result.get("conversation_flow", {})
            print(f"\nFlow Decision:")
            print(f"  - Type: {flow.get('decision_type', 'unknown')}")
            print(f"  - Should End: {flow.get('should_end', False)}")
            print(f"  - Reason: {flow.get('reason', 'N/A')}")

        except Exception as e:
            print(f"\n❌ Error testing case '{test_case['name']}': {str(e)}")
            logger.error(f"Error details: {e}", exc_info=True)

    print("\n" + "=" * 50)
    print("Test Complete")
    print("=" * 50 + "\n")


async def test_language_detection():
    """Test language detection for different inputs"""

    print("\n" + "=" * 50)
    print("Testing Language Detection")
    print("=" * 50 + "\n")

    from app.utils.language_detector import LanguageDetector

    detector = LanguageDetector({"default_language": "es", "supported_languages": ["es", "en", "pt"]})

    test_messages = [
        "¿Cuánto cuesta este producto?",  # Spanish
        "What is the price of this item?",  # English
        "Qual é o preço deste produto?",  # Portuguese
        "Hola, necesito ayuda",  # Spanish
        "Hello, I need help",  # English
    ]

    for message in test_messages:
        result = detector.detect_language(message)
        print(f"Message: '{message}'")
        print(f"  → Detected: {result['language']} (confidence: {result['confidence']:.2f})")
        print()


if __name__ == "__main__":
    # Run the tests
    print("Starting Supervisor Enhancement Tests...")

    # Test language detection first
    asyncio.run(test_language_detection())

    # Then test the full enhancement flow
    asyncio.run(test_supervisor_enhancement())

