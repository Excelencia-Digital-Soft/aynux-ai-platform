# Plan de Implementación: Sistema de Agentes tipo Botpress

## Información del Proyecto

| Campo | Valor |
|-------|-------|
| **Proyecto** | Aynux Bot Studio - Sistema tipo Botpress |
| **Versión** | 1.0 |
| **Fecha** | Diciembre 2024 |
| **Duración Estimada** | 6-8 semanas (Backend) + 4 semanas (Frontend) |
| **Equipo Recomendado** | 4 Backend + 2 Frontend |

---

## Resumen Ejecutivo

Implementación de un sistema de configuración de agentes inspirado en **Botpress** para la plataforma multi-tenant **Aynux**.

### Objetivos Principales

1. **Workflows Completos**: Condiciones complejas, variables por scope, subworkflows anidados
2. **6 Agentes Especializados**: Policy, Summary, Personality, HITL, Translator, Analytics
3. **Integración Máxima con LangChain**: Adopción del framework de agentes completo
4. **API-First Design**: Backend REST completo para futura UI en Vue.js

### Características Clave (Inspiradas en Botpress)

| Feature Botpress | Implementación Aynux |
|------------------|---------------------|
| Autonomous Nodes | `AgentNodeConfig` con instructions, tools, transitions |
| Instruction Box | `AgentInstruction` con system_prompt, persona, guidelines, constraints |
| Tool Connections | `ToolBinding` con permisos configurables |
| Workflow Builder | `WorkflowConfig` con LangGraph StateGraph |
| Variable Scopes | `VariableManager` (workflow, conversation, user, bot) |
| Agent Router | `WorkflowExecutor` con `ConditionEvaluator` |

---

## Arquitectura de Alto Nivel

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Vue.js Bot Studio UI                            │
│              (Proyecto Separado - Semanas 7-10)                     │
└─────────────────────────────────────────────────────────────────────┘
                                    │ REST API
┌─────────────────────────────────────────────────────────────────────┐
│                      FastAPI Admin Layer                            │
│     /agent-nodes    /workflows    /tools    /templates              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                   LangChain Agent Framework                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ AgentExecutor    │  │ Tool Registry    │  │ Memory System    │  │
│  │ (per tenant)     │  │ (LangChain Tools)│  │ (ConversationBuf)│  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                    Workflow Engine (LangGraph)                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ WorkflowExecutor │  │ ConditionEval    │  │ VariableManager  │  │
│  │ (StateGraph)     │  │ (Expression)     │  │ (Scoped + Redis) │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                      Specialized Agents                             │
│  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌──────────┐     │
│  │ Policy  │ │ Summary │ │Personality│ │  HITL   │ │Translator│    │
│  └─────────┘ └─────────┘ └──────────┘ └─────────┘ └──────────┘     │
│                          ┌──────────┐                               │
│                          │Analytics │                               │
│                          └──────────┘                               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│              PostgreSQL + Redis (Multi-Tenant Storage)              │
│   agent_node_configs │ workflow_configs │ tool_definitions │ ...   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Distribución del Equipo

### Roles y Responsabilidades

| Rol | Responsabilidades | Skills Requeridos |
|-----|-------------------|-------------------|
| **Dev 1** (Backend Lead) | Schemas, Workflow Engine, API Agents | Python, FastAPI, LangGraph |
| **Dev 2** (Backend) | DB Models, Variables, API Workflows | SQLAlchemy, Redis, PostgreSQL |
| **Dev 3** (ML/AI Lead) | Tool Registry, LangChain Factory, Policy/HITL | LangChain, AI/ML, Python |
| **Dev 4** (ML/AI) | Custom Tools, Specialized Agents | LangChain, NLP, Python |
| **Frontend 1** | Setup, Workflow Canvas, Testing | Vue 3, TypeScript, vue-flow |
| **Frontend 2** | Agent Editor, Node Editor, Dashboard | Vue 3, PrimeVue, Forms |

---

## Cronograma Visual

```
Semana    1         2         3         4         5         6         7         8         9        10
         |---------|---------|---------|---------|---------|---------|---------|---------|---------|
EPIC 1   ████████████████
         Foundation & Data Layer

EPIC 2            ████████████████
                  Tool Registry & LangChain

EPIC 3                      ████████████████
                            Specialized Agents

EPIC 4                              ████████████████
                                    Workflow Engine

EPIC 5                                      ████████████████
                                            API Layer

EPIC 6                                              ████████
                                                    Integration

EPIC 7                                                      ████████████████████████████████████
                                                            Vue.js UI (Proyecto Separado)
```

---

## EPIC 1: Foundation & Data Layer

**Duración**: Semana 1-2
**Owner**: Backend Lead

### Tareas

| ID | Tarea | Asignado | Horas | Dependencias | Prioridad |
|----|-------|----------|-------|--------------|-----------|
| F-01 | Crear schemas Pydantic: `AgentInstruction`, `ToolBinding`, `WorkflowTransition` | Dev 1 | 4h | - | P0 |
| F-02 | Crear schema `AgentNodeConfig` completo | Dev 1 | 4h | F-01 | P0 |
| F-03 | Crear schemas `WorkflowConfig`, `WorkflowCondition`, `SubWorkflowReference` | Dev 1 | 4h | F-01 | P0 |
| F-04 | Crear schemas `ToolDefinition`, `TenantToolConfig` | Dev 1 | 2h | - | P0 |
| F-05 | Crear migración SQL `009_botpress_agent_system.sql` | Dev 2 | 4h | F-01→F-04 | P0 |
| F-06 | Crear modelo SQLAlchemy `AgentNodeConfig` | Dev 2 | 3h | F-05 | P0 |
| F-07 | Crear modelo SQLAlchemy `WorkflowConfig` | Dev 2 | 3h | F-05 | P0 |
| F-08 | Crear modelo SQLAlchemy `ToolDefinition` | Dev 2 | 2h | F-05 | P0 |
| F-09 | Crear modelo SQLAlchemy `TenantToolConfig` | Dev 2 | 2h | F-05 | P0 |
| F-10 | Actualizar `__init__.py` de models con nuevos exports | Dev 2 | 1h | F-06→F-09 | P0 |
| F-11 | Tests unitarios para schemas | Dev 1 | 4h | F-01→F-04 | P1 |
| F-12 | Tests de migración y modelos | Dev 2 | 4h | F-06→F-10 | P1 |

### Archivos a Crear

```
app/core/schemas/
├── agent_node_config.py      # AgentNodeConfig, AgentInstruction, ToolBinding
├── workflow_config.py        # WorkflowConfig, WorkflowCondition
└── tool_registry.py          # ToolDefinition, TenantToolConfig

app/models/db/tenancy/
├── agent_node_config.py      # SQLAlchemy model
├── workflow_config.py        # SQLAlchemy model
└── tenant_tool_config.py     # SQLAlchemy model

app/models/db/core/
└── tool_definition.py        # SQLAlchemy model (global)

app/scripts/migrations/
└── 009_botpress_agent_system.sql
```

### Definition of Done

- [ ] Todos los schemas validados con Pydantic
- [ ] Migración ejecuta sin errores
- [ ] Modelos SQLAlchemy con relaciones correctas
- [ ] Tests con >80% coverage

---

## EPIC 2: Tool Registry & LangChain Integration

**Duración**: Semana 2-3
**Owner**: ML/AI Lead

### Tareas

| ID | Tarea | Asignado | Horas | Dependencias | Prioridad |
|----|-------|----------|-------|--------------|-----------|
| T-01 | Crear `ToolRegistry` base class con singleton pattern | Dev 3 | 4h | F-04 | P0 |
| T-02 | Implementar `_load_langchain_tool()` para cargar tools dinámicamente | Dev 3 | 4h | T-01 | P0 |
| T-03 | Implementar `_load_custom_tool()` para tools personalizados | Dev 3 | 3h | T-01 | P0 |
| T-04 | Crear `builtin_tools.py` con 8 herramientas default | Dev 3 | 6h | T-01 | P0 |
| T-05 | Implementar `KnowledgeBaseTool` (RAG integration) | Dev 4 | 4h | T-03 | P0 |
| T-06 | Implementar `ProductSearchTool` | Dev 4 | 3h | T-03 | P1 |
| T-07 | Implementar `OrderLookupTool` | Dev 4 | 3h | T-03 | P1 |
| T-08 | Implementar `HumanHandoffTool` | Dev 4 | 4h | T-03 | P0 |
| T-09 | Implementar `WorkflowTransitionTool` | Dev 4 | 4h | T-03 | P0 |
| T-10 | Crear `LangChainAgentFactory` con métodos para crear AgentExecutor | Dev 3 | 6h | T-01→T-04 | P0 |
| T-11 | Implementar `_build_prompt()` desde `AgentInstruction` | Dev 3 | 4h | T-10 | P0 |
| T-12 | Tests unitarios para ToolRegistry | Dev 3 | 4h | T-01→T-04 | P1 |
| T-13 | Tests de integración LangChain | Dev 4 | 4h | T-10, T-11 | P1 |

### Archivos a Crear

```
app/core/tools/
├── __init__.py
├── registry.py               # ToolRegistry singleton
├── builtin_tools.py          # BUILTIN_TOOLS definitions
├── langchain_adapter.py      # LangChain tool conversion
└── custom/
    ├── __init__.py
    ├── knowledge_base_tool.py
    ├── product_search_tool.py
    ├── order_lookup_tool.py
    ├── human_handoff_tool.py
    └── workflow_transition_tool.py

app/core/agents/
└── langchain_factory.py      # LangChainAgentFactory
```

### Tools Builtin

| Tool Key | Tipo | Descripción |
|----------|------|-------------|
| `knowledge_base` | RAG | Búsqueda en knowledge base del tenant |
| `product_search` | Database | Búsqueda en catálogo de productos |
| `order_lookup` | Database | Consulta de estado de órdenes |
| `web_search` | LangChain | DuckDuckGo search |
| `human_handoff` | API | Escalación a agente humano |
| `workflow_transition` | Workflow | Transición entre workflows |
| `send_whatsapp` | API | Envío de mensaje WhatsApp |
| `conversation_summary` | LangChain | Resumen de conversación |

### Definition of Done

- [ ] ToolRegistry carga tools LangChain y custom
- [ ] Todas las tools builtin funcionando
- [ ] LangChainAgentFactory crea AgentExecutor correctamente
- [ ] Tests con mocks de LLM

---

## EPIC 3: Specialized Agents

**Duración**: Semana 3-4
**Owner**: ML/AI Lead

### Tareas

| ID | Tarea | Asignado | Horas | Dependencias | Prioridad |
|----|-------|----------|-------|--------------|-----------|
| A-01 | Crear `LangChainSpecializedAgent` base class | Dev 3 | 4h | T-10 | P0 |
| A-02 | Implementar `PolicyAgent` con rules engine | Dev 3 | 8h | A-01 | P0 |
| A-03 | Implementar `SummaryAgent` con LangChain summarization | Dev 4 | 6h | A-01 | P0 |
| A-04 | Implementar `PersonalityAgent` para consistencia de tono | Dev 4 | 4h | A-01 | P1 |
| A-05 | Implementar `HITLAgent` con handoff service | Dev 3 | 8h | A-01 | P0 |
| A-06 | Implementar `TranslatorAgent` con detección de idioma | Dev 4 | 6h | A-01 | P1 |
| A-07 | Implementar `AnalyticsAgent` con sentiment analysis | Dev 4 | 6h | A-01 | P2 |
| A-08 | Crear `HandoffService` para gestión de escalaciones | Dev 3 | 6h | - | P0 |
| A-09 | Crear `RulesEngine` para PolicyAgent | Dev 3 | 6h | - | P0 |
| A-10 | Tests unitarios para cada agente especializado | Dev 4 | 8h | A-02→A-07 | P1 |
| A-11 | Tests de integración agentes + tools | Dev 3 | 4h | A-02→A-07 | P1 |

### Archivos a Crear

```
app/core/agents/specialized/
├── __init__.py
├── base_langchain.py         # LangChainSpecializedAgent
├── policy_agent.py           # PolicyAgent + RulesEngine
├── summary_agent.py          # SummaryAgent
├── personality_agent.py      # PersonalityAgent
├── hitl_agent.py             # HITLAgent + HandoffService
├── translator_agent.py       # TranslatorAgent
└── analytics_agent.py        # AnalyticsAgent
```

### Descripción de Agentes

| Agente | Propósito | Features Clave |
|--------|-----------|----------------|
| **PolicyAgent** | Enforcement de reglas de negocio | RulesEngine, validaciones, compliance |
| **SummaryAgent** | Condensación de conversaciones | LangChain summarization, context compression |
| **PersonalityAgent** | Consistencia de tono/persona | Style transfer, brand voice |
| **HITLAgent** | Escalación a humanos | Queue management, notifications, context preservation |
| **TranslatorAgent** | Soporte multilenguaje | Auto-detection, translation, language routing |
| **AnalyticsAgent** | Análisis de interacciones | Sentiment, topics, satisfaction scoring |

### Definition of Done

- [ ] 6 agentes especializados implementados
- [ ] Cada agente usa LangChain AgentExecutor
- [ ] PolicyAgent valida reglas correctamente
- [ ] HITLAgent escala a humanos
- [ ] Tests con >80% coverage

---

## EPIC 4: Workflow Engine

**Duración**: Semana 4-5
**Owner**: Backend Lead

### Tareas

| ID | Tarea | Asignado | Horas | Dependencias | Prioridad |
|----|-------|----------|-------|--------------|-----------|
| W-01 | Crear `WorkflowExecutor` base con LangGraph StateGraph | Dev 1 | 8h | F-03, A-01 | P0 |
| W-02 | Implementar `build_graph()` para construir StateGraph dinámico | Dev 1 | 6h | W-01 | P0 |
| W-03 | Crear `ConditionEvaluator` con AST parsing seguro | Dev 2 | 6h | - | P0 |
| W-04 | Implementar evaluación de expresiones: comparaciones, booleanos | Dev 2 | 4h | W-03 | P0 |
| W-05 | Crear `VariableManager` con scopes (workflow, conversation, user, bot) | Dev 2 | 6h | - | P0 |
| W-06 | Integrar VariableManager con Redis para persistencia | Dev 2 | 4h | W-05 | P0 |
| W-07 | Implementar soporte para subworkflows anidados | Dev 1 | 6h | W-01, W-02 | P1 |
| W-08 | Crear `WorkflowState` TypedDict para LangGraph | Dev 1 | 3h | W-01 | P0 |
| W-09 | Integrar WorkflowExecutor con GraphRouter existente | Dev 1 | 4h | W-01, W-02 | P0 |
| W-10 | Tests unitarios ConditionEvaluator | Dev 2 | 4h | W-03, W-04 | P1 |
| W-11 | Tests unitarios VariableManager | Dev 2 | 3h | W-05, W-06 | P1 |
| W-12 | Tests de integración WorkflowExecutor | Dev 1 | 6h | W-01→W-09 | P1 |

### Archivos a Crear

```
app/core/workflow/
├── __init__.py
├── executor.py               # WorkflowExecutor (LangGraph)
├── condition_evaluator.py    # ConditionEvaluator (AST)
├── variable_manager.py       # VariableManager (Redis)
└── state.py                  # WorkflowState TypedDict
```

### Expresiones Soportadas

```python
# Ejemplos de condiciones
"intent == 'billing'"                    # Comparación de igualdad
"sentiment < 0.3"                        # Comparación numérica
"error_count >= 3"                       # Mayor o igual
"'urgent' in keywords"                   # Pertenencia
"intent == 'support' and priority > 5"  # Operadores booleanos
"not resolved"                          # Negación
```

### Scopes de Variables

| Scope | Persistencia | TTL | Uso |
|-------|--------------|-----|-----|
| `workflow` | Redis | Duración del workflow | Variables locales del workflow |
| `conversation` | Redis | 24h | Contexto de la conversación |
| `user` | Redis | 30d | Preferencias del usuario |
| `bot` | Redis | Permanente | Configuración global del bot |

### Definition of Done

- [ ] Workflows ejecutan correctamente con LangGraph
- [ ] Condiciones evalúan expresiones complejas
- [ ] Variables persisten entre sesiones
- [ ] Subworkflows funcionan correctamente
- [ ] Integración con sistema existente

---

## EPIC 5: API Layer

**Duración**: Semana 5-6
**Owner**: Backend Lead

### Tareas

| ID | Tarea | Asignado | Horas | Dependencias | Prioridad |
|----|-------|----------|-------|--------------|-----------|
| API-01 | Crear `AgentNodeService` CRUD operations | Dev 1 | 4h | F-06 | P0 |
| API-02 | Crear endpoints `/agent-nodes` (list, create, get, update, delete) | Dev 1 | 6h | API-01 | P0 |
| API-03 | Crear endpoints `/agent-nodes/{key}/tools` (list, add, remove) | Dev 1 | 4h | API-02 | P0 |
| API-04 | Crear endpoints `/agent-nodes/{key}/transitions` | Dev 1 | 3h | API-02 | P0 |
| API-05 | Crear endpoint `/agent-nodes/{key}/test` para testing interactivo | Dev 1 | 4h | API-02, A-01 | P1 |
| API-06 | Crear `WorkflowService` CRUD operations | Dev 2 | 4h | F-07 | P0 |
| API-07 | Crear endpoints `/workflows` (list, create, get, update, delete) | Dev 2 | 6h | API-06 | P0 |
| API-08 | Crear endpoint `/workflows/{key}/test` para testing | Dev 2 | 4h | API-07, W-01 | P1 |
| API-09 | Crear endpoint `/workflows/{key}/graph` para visualización | Dev 2 | 4h | API-07 | P1 |
| API-10 | Crear `ToolService` para gestión de tools | Dev 2 | 3h | F-08, F-09 | P0 |
| API-11 | Crear endpoints `/tools/definitions` (global) | Dev 2 | 3h | API-10 | P0 |
| API-12 | Crear endpoints `/organizations/{org}/tools` (per-tenant) | Dev 2 | 4h | API-10 | P0 |
| API-13 | Agregar cache Redis para configs | Dev 1 | 3h | API-01, API-06 | P1 |
| API-14 | Agregar validación de schemas en endpoints | Dev 2 | 3h | API-02, API-07 | P1 |
| API-15 | Tests de integración API | Dev 1 | 6h | API-02→API-12 | P1 |
| API-16 | Documentación OpenAPI/Swagger | Dev 2 | 4h | API-02→API-12 | P2 |

### Endpoints API

#### Agent Nodes

```
Base: /api/v1/admin/organizations/{org_id}/agent-nodes

GET    /                           # Listar agent nodes
POST   /                           # Crear agent node
GET    /{agent_key}                # Obtener agent node
PUT    /{agent_key}                # Actualizar agent node
DELETE /{agent_key}                # Eliminar agent node
POST   /{agent_key}/toggle         # Toggle enabled
POST   /{agent_key}/test           # Probar con mensaje

GET    /{agent_key}/tools          # Listar tool bindings
POST   /{agent_key}/tools          # Agregar tool binding
DELETE /{agent_key}/tools/{tool}   # Eliminar tool binding

GET    /{agent_key}/transitions    # Listar transiciones
POST   /{agent_key}/transitions    # Agregar transición
DELETE /{agent_key}/transitions/{id} # Eliminar transición
```

#### Workflows

```
Base: /api/v1/admin/organizations/{org_id}/workflows

GET    /                           # Listar workflows
POST   /                           # Crear workflow
GET    /{workflow_key}             # Obtener workflow
PUT    /{workflow_key}             # Actualizar workflow
DELETE /{workflow_key}             # Eliminar workflow
POST   /{workflow_key}/toggle      # Toggle enabled
POST   /{workflow_key}/test        # Probar workflow
GET    /{workflow_key}/graph       # Obtener grafo para visualización
```

#### Tools

```
Base: /api/v1/admin/tools

GET    /definitions                # Listar tool definitions (global)
GET    /definitions/{tool_key}     # Obtener tool definition

Base: /api/v1/admin/organizations/{org_id}/tools

GET    /                           # Listar tenant tools
PUT    /{tool_key}                 # Configurar tenant tool
POST   /{tool_key}/test            # Probar tool
```

### Definition of Done

- [ ] Todos los endpoints CRUD funcionando
- [ ] Endpoints de testing devuelven respuestas
- [ ] Cache Redis implementado
- [ ] Validación de schemas correcta
- [ ] Documentación OpenAPI completa

---

## EPIC 6: Integration & Container

**Duración**: Semana 6
**Owner**: Tech Lead

### Tareas

| ID | Tarea | Asignado | Horas | Dependencias | Prioridad |
|----|-------|----------|-------|--------------|-----------|
| I-01 | Actualizar `DependencyContainer` con nuevos services | Dev 1 | 3h | API-01, API-06, API-10 | P0 |
| I-02 | Crear `BotpressAgentContainer` para servicios específicos | Dev 1 | 4h | I-01 | P0 |
| I-03 | Integrar `AgentNodeConfig` con `TenantAgentService` existente | Dev 2 | 4h | F-06, API-01 | P0 |
| I-04 | Actualizar `GraphRouter` para usar AgentNodeConfig | Dev 2 | 4h | I-03 | P0 |
| I-05 | Actualizar `AynuxGraph` para soportar workflows | Dev 1 | 6h | W-01, I-04 | P0 |
| I-06 | Crear adapter `AgentConfig` ↔ `AgentNodeConfig` para compatibilidad | Dev 2 | 3h | F-02 | P1 |
| I-07 | Actualizar `router.py` con nuevas rutas | Dev 1 | 2h | API-02, API-07, API-11 | P0 |
| I-08 | Agregar nuevas dependencias a `pyproject.toml` | Dev 1 | 1h | - | P0 |
| I-09 | Tests de integración end-to-end | Dev 1/2 | 8h | I-01→I-07 | P0 |
| I-10 | Migration script para datos existentes | Dev 2 | 4h | I-06 | P1 |

### Archivos a Modificar

| Archivo | Modificación |
|---------|--------------|
| `app/core/container/__init__.py` | Agregar BotpressAgentContainer |
| `app/core/tenancy/agent_service.py` | Soporte para AgentNodeConfig |
| `app/core/graph/routing/graph_router.py` | Usar AgentNodeConfig |
| `app/core/graph/graph.py` | Integrar WorkflowExecutor |
| `app/api/router.py` | Agregar nuevas rutas |
| `pyproject.toml` | Agregar dependencias LangChain |

### Dependencias a Agregar

```toml
[project.dependencies]
langchain = ">=0.2.0"
langchain-core = ">=0.2.0"
langchain-community = ">=0.2.0"
langchain-openai = ">=0.1.0"
```

### Definition of Done

- [ ] Sistema integrado con arquitectura existente
- [ ] Compatibilidad backward con AgentConfig
- [ ] Tests E2E pasando
- [ ] Migración de datos existentes funcional

---

## EPIC 7: Vue.js UI (Proyecto Separado)

**Duración**: Semana 7-10
**Owner**: Frontend Lead

### Tareas

| ID | Tarea | Asignado | Horas | Dependencias | Prioridad |
|----|-------|----------|-------|--------------|-----------|
| UI-01 | Setup proyecto Vue 3 + Vite + TypeScript | Frontend 1 | 4h | - | P0 |
| UI-02 | Configurar PrimeVue/Vuetify + TailwindCSS | Frontend 1 | 3h | UI-01 | P0 |
| UI-03 | Crear API client con Axios + interceptors auth | Frontend 1 | 4h | UI-01 | P0 |
| UI-04 | Crear stores Pinia: agents, workflows, tools | Frontend 1 | 6h | UI-03 | P0 |
| UI-05 | Crear `AgentList.vue` con filtros y búsqueda | Frontend 2 | 6h | UI-04 | P0 |
| UI-06 | Crear `AgentEditor.vue` form completo | Frontend 2 | 8h | UI-04 | P0 |
| UI-07 | Crear `InstructionsEditor.vue` con Monaco Editor | Frontend 1 | 6h | UI-06 | P0 |
| UI-08 | Crear `ToolBindings.vue` panel de configuración | Frontend 2 | 4h | UI-06 | P1 |
| UI-09 | Crear `TransitionEditor.vue` editor de transiciones | Frontend 2 | 4h | UI-06 | P1 |
| UI-10 | Integrar vue-flow para `WorkflowCanvas.vue` | Frontend 1 | 8h | UI-04 | P0 |
| UI-11 | Crear `NodePalette.vue` con drag & drop | Frontend 1 | 4h | UI-10 | P0 |
| UI-12 | Crear `NodeEditor.vue` panel de propiedades | Frontend 2 | 6h | UI-10 | P0 |
| UI-13 | Crear `ConditionBuilder.vue` visual | Frontend 2 | 6h | UI-10 | P1 |
| UI-14 | Crear `TestConsole.vue` para testing interactivo | Frontend 1 | 6h | UI-06 | P1 |
| UI-15 | Crear `Dashboard.vue` con métricas | Frontend 2 | 6h | UI-04 | P2 |
| UI-16 | Tests E2E con Playwright | Frontend 1 | 8h | UI-05→UI-15 | P1 |

### Estructura del Proyecto Vue.js

```
vue-bot-studio/
├── src/
│   ├── components/
│   │   ├── workflow/
│   │   │   ├── WorkflowCanvas.vue      # Editor visual (vue-flow)
│   │   │   ├── NodePalette.vue         # Paleta de nodos
│   │   │   ├── NodeEditor.vue          # Editor de propiedades
│   │   │   └── ConditionBuilder.vue    # Constructor de condiciones
│   │   ├── agent/
│   │   │   ├── AgentList.vue           # Lista de agentes
│   │   │   ├── AgentEditor.vue         # Editor completo
│   │   │   ├── InstructionsEditor.vue  # Monaco editor
│   │   │   ├── ToolBindings.vue        # Configuración de tools
│   │   │   └── TransitionEditor.vue    # Editor de transiciones
│   │   ├── tools/
│   │   │   ├── ToolRegistry.vue        # Lista de tools
│   │   │   ├── ToolConfig.vue          # Configuración
│   │   │   └── ToolTester.vue          # Testing interactivo
│   │   └── common/
│   │       ├── JsonEditor.vue          # Editor JSON
│   │       ├── ExpressionBuilder.vue   # Constructor de expresiones
│   │       └── TestConsole.vue         # Consola de testing
│   ├── views/
│   │   ├── Dashboard.vue
│   │   ├── Agents.vue
│   │   ├── Workflows.vue
│   │   ├── Tools.vue
│   │   └── Analytics.vue
│   ├── stores/
│   │   ├── agents.ts
│   │   ├── workflows.ts
│   │   └── tools.ts
│   └── api/
│       ├── client.ts
│       ├── agents.ts
│       ├── workflows.ts
│       └── tools.ts
├── package.json
└── vite.config.ts
```

### Librerías Recomendadas

| Propósito | Librería | Razón |
|-----------|----------|-------|
| Workflow Canvas | vue-flow | Mejor para diagramas de flujo interactivos |
| Code Editor | Monaco Editor | Soporte completo para YAML/JSON |
| State Management | Pinia | Estándar Vue 3 |
| UI Components | PrimeVue | Componentes enterprise-ready |
| Forms | VeeValidate + Zod | Validación robusta |
| API Client | Axios + Vue Query | Caching y estado de requests |
| Drag & Drop | vuedraggable | Para paletas de nodos |

### Definition of Done

- [ ] UI conecta con API backend
- [ ] CRUD de agentes funcional
- [ ] Editor visual de workflows funcional
- [ ] Testing interactivo funciona
- [ ] Responsive design

---

## Sprint Planning

### Sprint 1 (Semanas 1-2): Foundation + Tool Registry Start

**Objetivo**: Base de datos y schemas listos, Tool Registry iniciado

| Team | Tareas | Story Points |
|------|--------|--------------|
| Backend | F-01→F-12 | 21 pts |
| ML/AI | T-01→T-04 | 13 pts |

**Demo**: Schemas validados, migración ejecutada, ToolRegistry cargando tools

---

### Sprint 2 (Semanas 3-4): Tools + Agents

**Objetivo**: Tools completos, Agentes especializados funcionando

| Team | Tareas | Story Points |
|------|--------|--------------|
| ML/AI | T-05→T-13, A-01→A-11 | 34 pts |
| Backend | W-03→W-06 (paralelo) | 10 pts |

**Demo**: Agentes PolicyAgent y HITLAgent funcionando con tools

---

### Sprint 3 (Semanas 5-6): Workflow + API

**Objetivo**: Workflow Engine completo, APIs listas

| Team | Tareas | Story Points |
|------|--------|--------------|
| Backend | W-01, W-02, W-07→W-12, API-01→API-16 | 42 pts |

**Demo**: Workflow ejecutando, APIs documentadas

---

### Sprint 4 (Semanas 6-7): Integration + UI Start

**Objetivo**: Sistema integrado, UI iniciada

| Team | Tareas | Story Points |
|------|--------|--------------|
| Backend | I-01→I-10 | 20 pts |
| Frontend | UI-01→UI-04 | 13 pts |

**Demo**: Sistema E2E funcionando, UI conecta con API

---

### Sprint 5-6 (Semanas 7-10): UI Complete

**Objetivo**: UI completamente funcional

| Team | Tareas | Story Points |
|------|--------|--------------|
| Frontend | UI-05→UI-16 | 35 pts |

**Demo**: Bot Studio visual funcionando

---

## Resumen de Horas por Desarrollador

| Desarrollador | Horas Totales | Sprints Activos |
|---------------|---------------|-----------------|
| **Dev 1** (Backend Lead) | ~85h | 1, 3, 4 |
| **Dev 2** (Backend) | ~82h | 1, 2, 3, 4 |
| **Dev 3** (ML/AI Lead) | ~62h | 1, 2 |
| **Dev 4** (ML/AI) | ~52h | 1, 2 |
| **Frontend 1** | ~54h | 4, 5, 6 |
| **Frontend 2** | ~50h | 4, 5, 6 |

**Total Backend**: ~281 horas (~7 semanas con 2 devs)
**Total Frontend**: ~104 horas (~4 semanas con 2 devs)

---

## Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Complejidad LangChain integration | Alta | Alto | Spike técnico en Sprint 1, documentar patrones |
| Performance workflow engine | Media | Alto | Benchmark temprano, cache agresivo |
| Compatibilidad backward | Media | Medio | Adapter pattern, tests de regresión |
| UI complexity vue-flow | Media | Medio | POC en Sprint 4, librería alternativa backup |

---

## Checklist de Entrega Final

### Backend

- [ ] Schemas Pydantic completos con validación
- [ ] Migración SQL ejecutada y verificada
- [ ] Modelos SQLAlchemy con relaciones
- [ ] ToolRegistry con 8+ tools funcionando
- [ ] 6 Agentes especializados implementados
- [ ] WorkflowExecutor con LangGraph
- [ ] ConditionEvaluator seguro
- [ ] VariableManager con Redis
- [ ] APIs CRUD completas
- [ ] Cache Redis configurado
- [ ] Tests >80% coverage
- [ ] Documentación OpenAPI

### Frontend (Vue.js)

- [ ] Proyecto configurado
- [ ] API client funcionando
- [ ] CRUD agentes visual
- [ ] Editor de workflows con vue-flow
- [ ] Testing interactivo
- [ ] Responsive design

---

## Ejemplo de Configuración de Agente

```json
{
  "agent_key": "product_specialist",
  "node_type": "autonomous",
  "agent_type": "react",
  "display_name": "Product Specialist",
  "instructions": {
    "system_prompt": "You are a friendly product specialist for {company_name}. Help customers find products, answer questions, and provide recommendations.",
    "persona": "Friendly, knowledgeable, patient, helpful",
    "guidelines": [
      "Always confirm customer needs before recommending products",
      "Mention current promotions when relevant",
      "Offer alternatives if requested product is unavailable"
    ],
    "constraints": [
      "Never discuss competitor products",
      "Do not provide medical advice for health products",
      "Do not promise delivery dates without verification"
    ],
    "examples": [
      {
        "user": "I'm looking for a gift for my mom",
        "assistant": "I'd be happy to help you find a perfect gift! Could you tell me more about your mom's interests?"
      }
    ],
    "temperature": 0.7,
    "max_tokens": 1024
  },
  "tools": [
    {
      "tool_key": "knowledge_base",
      "enabled": true,
      "config": {"collection": "products"},
      "permissions": ["read"]
    },
    {
      "tool_key": "product_search",
      "enabled": true,
      "permissions": ["read"]
    }
  ],
  "transitions": [
    {
      "target": "invoice_agent",
      "condition": "intent == 'billing' or 'factura' in message",
      "priority": 10
    },
    {
      "target": "hitl_agent",
      "condition": "sentiment < 0.3 or error_count >= 2",
      "priority": 20
    }
  ],
  "keywords": ["producto", "precio", "stock", "comprar"],
  "priority": 80,
  "enabled": true
}
```

---

## Contacto y Soporte

Para dudas sobre este plan, contactar al Tech Lead del proyecto.

**Última actualización**: Diciembre 2024
