# Agent Schema Migration Guide

This guide shows how to replace hardcoded agent and intent values throughout the codebase with the centralized `agent_schema.py`.

## Overview

The new `app/schemas/agent_schema.py` provides a single source of truth for:
- Intent definitions and descriptions
- Agent definitions and mappings  
- Intent-to-agent routing logic
- LLM prompt text generation
- Configuration validation

## Migration Checklist

### 1. Intent Router (`app/agents/langgraph_system/intelligence/intent_router.py`)

**BEFORE (Lines 225-235):**
```python
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
```

**AFTER:**
```python
from app.schemas import get_valid_intents

valid_intents = get_valid_intents()
```

**BEFORE (Lines 317-328):**
```python
mapping = {
    "producto": "product_agent",
    "datos": "data_insights_agent",
    "soporte": "support_agent",
    "seguimiento": "tracking_agent", 
    "facturacion": "invoice_agent",
    "promociones": "promotions_agent",
    "categoria": "category_agent",
    "despedida": "farewell_agent",
    "fallback": "fallback_agent",
    "general": "fallback_agent",
}
```

**AFTER:**
```python
from app.schemas import get_intent_to_agent_mapping

mapping = get_intent_to_agent_mapping()
# Add any special cases not in schema
mapping["general"] = "fallback_agent"
```

### 2. Intent Analyzer Prompts (`app/agents/langgraph_system/prompts/intent_analyzer.py`)

**BEFORE (Lines 24-34):**
```python  
# Hardcoded intent descriptions in prompt
```

**AFTER:**
```python
from app.schemas import build_intent_prompt_text

def get_system_prompt(self) -> str:
    intent_text = build_intent_prompt_text()
    return f"""
    Eres un analizador de intenciones para un asistente de comercio conversacional...
    
    {intent_text}
    
    ..."""
```

### 3. LangGraph Construction (`app/agents/langgraph_system/graph.py`)

**BEFORE (Lines 75-84):**
```python
workflow.add_node("supervisor", self._supervisor_node)
workflow.add_node("category_agent", self._category_agent_node)
workflow.add_node("data_insights_agent", self._data_insights_agent_node)
workflow.add_node("product_agent", self._product_agent_node)
workflow.add_node("promotions_agent", self._promotions_agent_node)
workflow.add_node("tracking_agent", self._tracking_agent_node)
workflow.add_node("support_agent", self._support_agent_node)
workflow.add_node("invoice_agent", self._invoice_agent_node)
workflow.add_node("fallback_agent", self._fallback_agent_node)
workflow.add_node("farewell_agent", self._farewell_agent_node)
```

**AFTER:**
```python
from app.schemas import get_graph_node_names, AgentType

# Add supervisor
workflow.add_node(AgentType.SUPERVISOR.value, self._supervisor_node)

# Add all other agents dynamically
for agent_name in get_graph_node_names():
    node_method = getattr(self, f"_{agent_name}_node")
    workflow.add_node(agent_name, node_method)
```

**BEFORE (Lines 93-104):**
```python
{
    "category_agent": "category_agent",
    "data_insights_agent": "data_insights_agent",
    "product_agent": "product_agent",
    "promotions_agent": "promotions_agent", 
    "tracking_agent": "tracking_agent",
    "support_agent": "support_agent",
    "invoice_agent": "invoice_agent",
    "fallback_agent": "fallback_agent",
    "farewell_agent": "farewell_agent",
    "__end__": END,
}
```

**AFTER:**
```python
from app.schemas import get_graph_node_names

# Build conditional edges mapping dynamically  
edges_mapping = {agent: agent for agent in get_graph_node_names()}
edges_mapping["__end__"] = END

workflow.add_conditional_edges(
    "supervisor",
    self._route_to_agent,
    edges_mapping
)
```

**BEFORE (Lines 108-118):**
```python
for agent in [
    "category_agent",
    "data_insights_agent", 
    "product_agent",
    "promotions_agent",
    "tracking_agent",
    "support_agent",
    "invoice_agent",
    "fallback_agent",
    "farewell_agent",
]:
```

**AFTER:**
```python
from app.schemas import get_graph_node_names

for agent in get_graph_node_names():
```

**BEFORE (Lines 292-301):**
```python
valid_agents = [
    "category_agent",
    "product_agent",
    "promotions_agent",
    "tracking_agent", 
    "support_agent",
    "invoice_agent",
    "fallback_agent",
    "farewell_agent",
]
```

**AFTER:**
```python
from app.schemas import get_graph_node_names

valid_agents = get_graph_node_names()
```

**BEFORE (Lines 769-771):**
```python
agent_names = ["category_agent", "product_agent", "promotions_agent",
              "tracking_agent", "support_agent", "invoice_agent", 
              "fallback_agent", "farewell_agent"]
```

**AFTER:**
```python
from app.schemas import get_graph_node_names

agent_names = get_graph_node_names()
```

### 4. Agent Registry (`app/agents/langgraph_system/agents/__init__.py`)

**BEFORE:**
```python
from .category_agent import CategoryAgent
from .data_insights_agent import DataInsightsAgent
# ... individual imports

__all__ = [
    "CategoryAgent",
    "DataInsightsAgent", 
    # ... individual class names
]
```

**AFTER:**
```python
from app.schemas import get_agent_class_mapping

# Dynamic imports based on schema
_agent_classes = {}
for agent_name, class_name in get_agent_class_mapping().items():
    if agent_name != "supervisor":  # Skip supervisor
        module_name = agent_name
        module = __import__(f".{module_name}", package=__name__, fromlist=[class_name])
        _agent_classes[class_name] = getattr(module, class_name)

# Export all agent classes
globals().update(_agent_classes)
__all__ = list(_agent_classes.keys())
```

### 5. Router Configuration (`app/agents/langgraph_system/router.py`)

**BEFORE (Lines 22-30):**
```python
self.agent_mapping = {
    "category_browsing": "category_agent",
    "product_inquiry": "product_agent",
    "promotions": "promotions_agent",
    "order_tracking": "tracking_agent",
    "technical_support": "support_agent", 
    "invoice_request": "invoice_agent",
    "general_inquiry": "category_agent",
}
```

**AFTER:**
```python
from app.schemas import get_intent_to_agent_mapping

# Use schema mapping as base, add custom mappings
base_mapping = get_intent_to_agent_mapping()
self.agent_mapping = {
    "category_browsing": base_mapping.get("categoria", "category_agent"),
    "product_inquiry": base_mapping.get("producto", "product_agent"),
    "promotions": base_mapping.get("promociones", "promotions_agent"),
    "order_tracking": base_mapping.get("seguimiento", "tracking_agent"),
    "technical_support": base_mapping.get("soporte", "support_agent"),
    "invoice_request": base_mapping.get("facturacion", "invoice_agent"),
    "general_inquiry": base_mapping.get("categoria", "category_agent"),
}
```

### 6. Agent Initialization in Graph

**BEFORE (Lines 662-690):**
```python
self.product_agent = ProductAgent(
    ollama=self.ollama, postgres=self.postgres, config=agent_config.get("product", {})
)
self.category_agent = CategoryAgent(
    ollama=self.ollama, chroma=self.chroma, config=agent_config.get("category", {})
)
# ... manual initialization for each agent
```

**AFTER:**
```python
from app.schemas import DEFAULT_AGENT_SCHEMA, get_agent_class_mapping

# Dynamic agent initialization based on schema
agent_classes = get_agent_class_mapping()

for agent_name, class_name in agent_classes.items():
    if agent_name == "supervisor":
        continue
        
    agent_def = DEFAULT_AGENT_SCHEMA.get_agent_definition(agent_name)
    if not agent_def:
        continue
        
    # Build initialization parameters based on requirements
    init_params = {"ollama": self.ollama, "config": agent_config.get(agent_def.config_key, {})}
    
    if agent_def.requires_postgres:
        init_params["postgres"] = self.postgres
    if agent_def.requires_chroma:
        init_params["chroma"] = self.chroma
        
    # Get agent class and instantiate
    agent_class = globals()[class_name]  # Assumes class is imported
    agent_instance = agent_class(**init_params)
    
    # Set as instance attribute
    setattr(self, agent_name, agent_instance)
```

## Usage Examples

### Getting Intent Information
```python
from app.schemas import DEFAULT_AGENT_SCHEMA, IntentType

# Get specific intent definition
product_intent = DEFAULT_AGENT_SCHEMA.get_intent_definition(IntentType.PRODUCTO)
print(f"Confidence threshold: {product_intent.confidence_threshold}")
print(f"Examples: {product_intent.examples}")

# Get agent for intent
agent_name = DEFAULT_AGENT_SCHEMA.get_agent_for_intent("producto")
print(f"Agent: {agent_name}")
```

### Building Dynamic Configurations
```python
from app.schemas import DEFAULT_AGENT_SCHEMA

# Get agents requiring specific databases
postgres_agents = DEFAULT_AGENT_SCHEMA.postgres_agents
chroma_agents = DEFAULT_AGENT_SCHEMA.chroma_agents

# Configure database connections accordingly
if postgres_agents:
    setup_postgres_connection()
if chroma_agents:
    setup_chroma_connection()
```

### Validation
```python
from app.schemas import DEFAULT_AGENT_SCHEMA

# The schema automatically validates:
# - All intents have valid target agents
# - All required fields are present
# - Confidence thresholds are in valid range

try:
    # This will raise an error if schema is invalid
    schema = DEFAULT_AGENT_SCHEMA
    print("Schema is valid!")
except ValueError as e:
    print(f"Schema validation failed: {e}")
```

## Benefits of Migration

1. **Single Source of Truth**: All agent/intent definitions in one place
2. **Type Safety**: Pydantic validation ensures consistency
3. **Easy Maintenance**: Add new agents/intents by updating schema only
4. **Automatic Validation**: Schema validates relationships between intents and agents
5. **Dynamic Configuration**: Graph construction becomes data-driven
6. **Documentation**: Schema serves as living documentation
7. **Testing**: Schema can be used to generate test cases
8. **IDE Support**: Enums provide autocomplete and type checking

## Testing the Migration

Use the test script to verify the schema works correctly:

```bash
python app/scripts/test_agent_schema.py
```

This will demonstrate all schema features and validate the configuration.

## Next Steps

1. Start with the Intent Router migration (lowest risk)
2. Update the LangGraph construction (medium risk)
3. Migrate agent initialization (highest complexity)
4. Update tests to use schema
5. Add schema validation to CI/CD pipeline