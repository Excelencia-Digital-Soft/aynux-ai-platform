#!/usr/bin/env python3
"""
Script to update intent definitions if you want to change routing behavior
"""

import json
from typing import Dict, List


def show_current_definitions():
    """Show current intent definitions"""
    from app.schemas import DEFAULT_AGENT_SCHEMA, IntentType

    print("CURRENT INTENT DEFINITIONS:")
    print("=" * 80)
    
    for intent_type in [IntentType.PRODUCTO, IntentType.CATEGORIA]:
        intent_def = DEFAULT_AGENT_SCHEMA.intents[intent_type]
        print(f"\n{intent_type.value.upper()}:")
        print(f"  Description: {intent_def.description}")
        print(f"  Target Agent: {intent_def.target_agent.value}")
        print(f"  Examples:")
        for example in intent_def.examples:
            print(f"    - {example}")


def suggest_changes():
    """Suggest possible changes to fix the routing"""
    print("\n\nSUGGESTED CHANGES:")
    print("=" * 80)
    
    print("\nOption 1: Keep current behavior (RECOMMENDED)")
    print("-" * 40)
    print("The current routing is semantically correct:")
    print("- 'que productos tienes?' → category_agent (for browsing)")
    print("- 'precio del iPhone' → product_agent (for specific queries)")
    print("\nThis makes sense because general browsing should go to category exploration.")
    
    print("\n\nOption 2: Update PRODUCTO intent to include general queries")
    print("-" * 40)
    print("If you want ALL product queries to go to product_agent, update:")
    print("\nIn app/schemas/agent_schema.py, line 157-167:")
    print("""
    IntentType.PRODUCTO: IntentDefinition(
        intent=IntentType.PRODUCTO,
        description="Preguntas sobre productos en general o específicos, características, precio, stock",
        examples=[
            "¿qué productos tienes?",
            "muéstrame los productos",
            "lista de productos disponibles",
            "¿tienen stock del iphone 15?",
            "¿cuánto cuesta?",
            "¿qué características tiene este producto?",
        ],
        target_agent=AgentType.PRODUCT_AGENT,
        confidence_threshold=0.8,
    ),
    """)
    
    print("\n\nOption 3: Update intent router prompts")
    print("-" * 40)
    print("You can also update the LLM prompts to better distinguish intents.")
    print("This would be in app/agents/langgraph_system/prompts/intent_analyzer.py")


def create_test_queries() -> List[str]:
    """Create test queries to validate routing"""
    return [
        # General product queries
        "que productos tienes?",
        "¿qué productos tienen disponibles?",
        "muéstrame todos los productos",
        "lista de productos",
        "¿qué venden?",
        
        # Specific product queries  
        "precio del iPhone 15",
        "características del Samsung Galaxy",
        "stock de laptops Dell",
        
        # Category browsing
        "muéstrame televisores",
        "busco zapatillas",
        "productos de tecnología",
        
        # Mixed queries
        "¿tienen laptops?",
        "¿qué celulares tienen?",
        "muéstrame productos en oferta",
    ]


def main():
    """Main function"""
    print("INTENT ROUTING ANALYSIS")
    print("=" * 80)
    
    show_current_definitions()
    suggest_changes()
    
    print("\n\nTEST QUERIES TO VALIDATE:")
    print("=" * 80)
    for query in create_test_queries():
        print(f"- {query}")
    
    print("\n\nRECOMMENDATION:")
    print("=" * 80)
    print("Run the following commands to test and fix:")
    print("1. python app/scripts/fix_intent_routing.py  # Clear cache and test")
    print("2. python app/scripts/test_chatbot_direct.py  # Test with actual chatbot")
    print("\nIf you want to change the behavior, edit app/schemas/agent_schema.py")


if __name__ == "__main__":
    main()