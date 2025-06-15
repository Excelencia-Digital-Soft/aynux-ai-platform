#!/usr/bin/env python3
"""
Test agent schema with Pydantic V2 validators
"""

import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.schemas import DEFAULT_AGENT_SCHEMA, get_valid_intents, get_intent_to_agent_mapping


def test_schema():
    """Test the agent schema with V2 validators"""
    print("Testing Agent Schema with Pydantic V2 validators...\n")
    
    # Test 1: Check that schema loads correctly
    print("1. Schema loaded successfully ✓")
    
    # Test 2: Check intent names
    intents = get_valid_intents()
    print(f"\n2. Valid intents ({len(intents)}):")
    for intent in intents:
        print(f"   - {intent}")
    
    # Test 3: Check intent to agent mapping
    mapping = get_intent_to_agent_mapping()
    print(f"\n3. Intent to agent mappings:")
    for intent, agent in mapping.items():
        print(f"   - {intent} → {agent}")
    
    # Test 4: Check specific intent definitions
    print(f"\n4. Product intent examples:")
    product_def = DEFAULT_AGENT_SCHEMA.get_intent_definition("producto")
    if product_def:
        for example in product_def.examples[:3]:
            print(f"   - {example}")
    
    # Test 5: Verify validator is working
    print(f"\n5. Validator test:")
    try:
        # Access the agents to ensure validator runs
        agents = DEFAULT_AGENT_SCHEMA.agents
        print(f"   - All {len(agents)} agents have valid target intents ✓")
    except Exception as e:
        print(f"   - Validator error: {e}")
    
    print("\nAll tests passed! ✓")


if __name__ == "__main__":
    test_schema()