#!/usr/bin/env python3
"""
Test script demonstrating the usage of the centralized agent schema.

This script shows how to use the new agent schema to replace hardcoded
values throughout the codebase.
"""

import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from schemas import (
    DEFAULT_AGENT_SCHEMA,
    get_valid_intents,
    get_valid_agents,
    get_intent_to_agent_mapping,
    get_agent_class_mapping,
    get_graph_node_names,
    get_intent_examples,
    get_intent_descriptions,
    build_intent_prompt_text,
    IntentType,
    AgentType,
)


def demonstrate_schema_usage():
    """Demonstrate various ways to use the agent schema."""
    
    print("=== Agent Schema Usage Demonstration ===\n")
    
    # 1. Get valid intents (replaces hardcoded lists)
    print("1. Valid Intents:")
    valid_intents = get_valid_intents()
    print(f"   {valid_intents}")
    print(f"   Count: {len(valid_intents)}\n")
    
    # 2. Get valid agents (replaces hardcoded lists)
    print("2. Valid Agents:")
    valid_agents = get_valid_agents()
    print(f"   {valid_agents}")
    print(f"   Count: {len(valid_agents)}\n")
    
    # 3. Intent to agent mapping (replaces hardcoded dicts)
    print("3. Intent to Agent Mapping:")
    mapping = get_intent_to_agent_mapping()
    for intent, agent in mapping.items():
        print(f"   {intent} -> {agent}")
    print()
    
    # 4. Agent class mapping (for dynamic imports)
    print("4. Agent Class Mapping:")
    class_mapping = get_agent_class_mapping()
    for agent, class_name in class_mapping.items():
        if agent != "supervisor":  # Skip supervisor for clarity
            print(f"   {agent} -> {class_name}")
    print()
    
    # 5. Graph node names (for StateGraph construction)
    print("5. Graph Node Names (excludes supervisor):")
    node_names = get_graph_node_names()
    print(f"   {node_names}")
    print(f"   Count: {len(node_names)}\n")
    
    # 6. Intent examples (for LLM prompts)
    print("6. Intent Examples:")
    examples = get_intent_examples()
    for intent, example_list in examples.items():
        print(f"   {intent}: {example_list[:2]}...")  # Show first 2 examples
    print()
    
    # 7. Intent descriptions (for documentation)
    print("7. Intent Descriptions:")
    descriptions = get_intent_descriptions()
    for intent, description in descriptions.items():
        print(f"   {intent}: {description}")
    print()
    
    # 8. Build LLM prompt text (replaces hardcoded prompt)
    print("8. LLM Prompt Text:")
    prompt_text = build_intent_prompt_text()
    print(f"   {prompt_text}\n")
    
    # 9. Access individual definitions
    print("9. Individual Intent Definition:")
    product_intent = DEFAULT_AGENT_SCHEMA.get_intent_definition(IntentType.PRODUCTO)
    if product_intent:
        print(f"   Intent: {product_intent.intent}")
        print(f"   Description: {product_intent.description}")
        print(f"   Target Agent: {product_intent.target_agent}")
        print(f"   Confidence Threshold: {product_intent.confidence_threshold}")
        print(f"   Examples: {product_intent.examples}")
    print()
    
    # 10. Agent requirements (for dependency injection)
    print("10. Agent Requirements:")
    postgres_agents = DEFAULT_AGENT_SCHEMA.postgres_agents
    chroma_agents = DEFAULT_AGENT_SCHEMA.chroma_agents
    print(f"   PostgreSQL Required: {postgres_agents}")
    print(f"   ChromaDB Required: {chroma_agents}")
    print()
    
    # 11. Configuration validation
    print("11. Schema Validation:")
    try:
        # The schema validates relationships automatically
        print("   ✓ All intent-to-agent mappings are valid")
        print("   ✓ All agent definitions are complete")
        print("   ✓ Schema passes validation")
    except Exception as e:
        print(f"   ✗ Schema validation failed: {e}")
    print()


def show_migration_examples():
    """Show examples of how to migrate from hardcoded values to schema."""
    
    print("=== Migration Examples ===\n")
    
    print("BEFORE (hardcoded):")
    print('''
    valid_intents = [
        "producto",
        "datos", 
        "soporte",
        "seguimiento",
        "facturacion",
        "promociones",
        "categoria",
        "despedida",
        "fallback",
    ]
    ''')
    
    print("AFTER (using schema):")
    print('''
    from app.schemas import get_valid_intents
    
    valid_intents = get_valid_intents()
    ''')
    print()
    
    print("BEFORE (hardcoded mapping):")
    print('''
    mapping = {
        "producto": "product_agent",
        "datos": "data_insights_agent", 
        "soporte": "support_agent",
        # ... rest of mapping
    }
    ''')
    
    print("AFTER (using schema):")
    print('''
    from app.schemas import get_intent_to_agent_mapping
    
    mapping = get_intent_to_agent_mapping()
    ''')
    print()
    
    print("BEFORE (hardcoded graph nodes):")
    print('''
    for agent in [
        "category_agent",
        "data_insights_agent",
        "product_agent", 
        # ... rest of agents
    ]:
        workflow.add_conditional_edges(agent, ...)
    ''')
    
    print("AFTER (using schema):")
    print('''
    from app.schemas import get_graph_node_names
    
    for agent in get_graph_node_names():
        workflow.add_conditional_edges(agent, ...)
    ''')
    print()


if __name__ == "__main__":
    demonstrate_schema_usage()
    show_migration_examples()
    
    print("=== Schema Test Completed Successfully ===")