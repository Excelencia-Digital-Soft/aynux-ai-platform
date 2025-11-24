# Análisis de Servicios Legacy - Plan de Migración Completo

## 📊 Resumen Ejecutivo

**Total de servicios**: 27
**Deprecados**: 3 ✅
**Por migrar**: 24
**Fecha**: 2025-01-23

---

## 🎯 Clasificación de Servicios

### 1. Infrastructure Services (8 servicios)

Servicios que manejan infraestructura técnica (DB sync, vector stores, embeddings).

**Acción recomendada**: Mover a `app/domains/*/infrastructure/services/` o `app/integrations/`

| Servicio | Líneas | Destino Recomendado | Prioridad |
|----------|--------|---------------------|-----------|
| `dux_sync_service.py` | ~400 | `app/domains/ecommerce/infrastructure/services/` | Alta |
| `dux_rag_sync_service.py` | ~350 | `app/domains/ecommerce/infrastructure/services/` | Alta |
| `scheduled_sync_service.py` | ~200 | `app/domains/ecommerce/infrastructure/services/` | Media |
| `embedding_update_service.py` | ~300 | `app/integrations/vector_stores/` | Alta |
| `vector_service.py` | ~250 | `app/integrations/vector_stores/` | Alta |
| `vector_store_ingestion_service.py` | ~200 | `app/integrations/vector_stores/` | Alta |
| `pgvector_metrics_service.py` | ~150 | `app/integrations/vector_stores/` | Baja |
| `knowledge_embedding_service.py` | ~250 | `app/integrations/vector_stores/` | Media |

**Total**: ~2,100 líneas

**Beneficios de mover**:
- ✅ Mejor organización (infraestructura separada)
- ✅ Reutilizable entre dominios
- ✅ Más fácil de encontrar y mantener

---

### 2. Integration Services (3 servicios)

Servicios que integran con APIs externas (WhatsApp).

**Acción recomendada**: Mover a `app/integrations/whatsapp/`

| Servicio | Líneas | Destino Recomendado | Prioridad |
|----------|--------|---------------------|-----------|
| `whatsapp_service.py` | ~500 | `app/integrations/whatsapp/service.py` | Alta |
| `whatsapp_catalog_service.py` | ~200 | `app/integrations/whatsapp/catalog_service.py` | Media |
| `whatsapp_flows_service.py` | ~150 | `app/integrations/whatsapp/flows_service.py` | Media |

**Total**: ~850 líneas

**Beneficios de mover**:
- ✅ Todas las integraciones WhatsApp en un lugar
- ✅ Fácil de reemplazar si cambia proveedor
- ✅ Testeable con mocks de WhatsApp API

---

### 3. Domain Services (3 servicios)

Servicios con lógica de negocio que deberían convertirse en Use Cases.

**Acción recomendada**: Migrar a Use Cases siguiendo Clean Architecture

| Servicio | Líneas | Destino Recomendado | Prioridad |
|----------|--------|---------------------|-----------|
| `customer_service.py` | ~300 | `app/domains/shared/application/use_cases/` | Alta |
| `knowledge_service.py` | ~400 | `app/domains/shared/application/use_cases/` | Media |
| `category_vector_service.py` | ~250 | `app/domains/ecommerce/application/use_cases/` | Baja |

**Total**: ~950 líneas

**Migración recomendada**:

#### customer_service.py → Use Cases
```
- CreateCustomerUseCase
- UpdateCustomerUseCase
- GetCustomerHistoryUseCase
- CustomerRepository (nueva)
```

#### knowledge_service.py → Use Cases
```
- SearchKnowledgeUseCase
- AddKnowledgeUseCase
- KnowledgeRepository (nueva)
```

#### category_vector_service.py
```
- Integrar en SearchProductsUseCase (ya existe)
- O crear GetCategorySuggestionsUseCase
```

---

### 4. AI/LLM Services (5 servicios)

Servicios que manejan IA, LLMs y detección de dominios.

**Acción recomendada**: Mover a `app/integrations/llm/` o deprecar

| Servicio | Líneas | Destino/Acción | Prioridad |
|----------|--------|----------------|-----------|
| `ai_service.py` | ~600 | Deprecar (usar ILLM interface) | Alta |
| `prompt_service.py` | ~200 | Mover a `app/core/shared/` | Media |
| `domain_detector.py` | ~300 | Deprecar (SuperOrchestrator hace esto) | Alta |
| `domain_manager.py` | ~250 | Deprecar (SuperOrchestrator hace esto) | Alta |
| `ai_data_pipeline_service.py` | ~350 | Mover a `app/integrations/llm/` | Baja |

**Total**: ~1,700 líneas

**Análisis**:
- `ai_service.py`: Reemplazado por `ILLM` interface y `OllamaLLM` implementation
- `domain_detector.py` + `domain_manager.py`: Reemplazados por `SuperOrchestrator`
- `prompt_service.py`: Útil para gestionar prompts, mover a shared
- `ai_data_pipeline_service.py`: Especializado, mover a integrations

---

### 5. Utility Services (2 servicios)

Servicios de utilidades generales.

**Acción recomendada**: Mover a `app/core/shared/utils/`

| Servicio | Líneas | Destino Recomendado | Prioridad |
|----------|--------|---------------------|-----------|
| `data_extraction_service.py` | ~200 | `app/core/shared/utils/` | Baja |
| `phone_normalizer_pydantic.py` | ~100 | `app/core/shared/utils/` | Baja |

**Total**: ~300 líneas

---

### 6. Auth Services (2 servicios)

Servicios de autenticación y autorización.

**Acción recomendada**: **MANTENER** en `app/services/` (están bien ubicados)

| Servicio | Líneas | Acción | Prioridad |
|----------|--------|--------|-----------|
| `token_service.py` | ~150 | Mantener | N/A |
| `user_service.py` | ~200 | Mantener | N/A |

**Total**: ~350 líneas

**Razón**: Son servicios de infraestructura de auth que no pertenecen a ningún dominio específico.

---

### 7. Legacy/Wrapper Services (4 servicios)

Servicios legacy que usan arquitectura antigua.

**Acción recomendada**: Deprecar o mantener como wrappers temporales

| Servicio | Líneas | Acción | Prioridad |
|----------|--------|--------|-----------|
| `product_service.py` | ~460 | ✅ DEPRECADO | Completado |
| `enhanced_product_service.py` | ~160 | ✅ DEPRECADO | Completado |
| `super_orchestrator_service.py` | ~500 | ✅ DEPRECADO | Completado |
| `langgraph_chatbot_service.py` | ~800 | Mantener temporal (wrapper) | Media |

**Total**: ~1,920 líneas

**Análisis**:
- `langgraph_chatbot_service.py`: Mantener temporalmente como wrapper para compatibilidad con endpoints legacy

---

## 📋 Plan de Migración por Prioridad

### Prioridad Alta (9 servicios)

1. ✅ **Deprecar `product_service.py`** - COMPLETADO
2. ✅ **Deprecar `enhanced_product_service.py`** - COMPLETADO
3. ✅ **Deprecar `super_orchestrator_service.py`** - COMPLETADO
4. **Mover `dux_sync_service.py`** → `app/domains/ecommerce/infrastructure/services/`
5. **Mover `dux_rag_sync_service.py`** → `app/domains/ecommerce/infrastructure/services/`
6. **Mover `whatsapp_service.py`** → `app/integrations/whatsapp/`
7. **Migrar `customer_service.py`** → Use Cases
8. **Deprecar `ai_service.py`** (reemplazado por ILLM)
9. **Deprecar `domain_detector.py`** (reemplazado por SuperOrchestrator)
10. **Deprecar `domain_manager.py`** (reemplazado por SuperOrchestrator)

### Prioridad Media (7 servicios)

11. **Mover `embedding_update_service.py`** → `app/integrations/vector_stores/`
12. **Mover `vector_service.py`** → `app/integrations/vector_stores/`
13. **Mover `vector_store_ingestion_service.py`** → `app/integrations/vector_stores/`
14. **Mover `knowledge_embedding_service.py`** → `app/integrations/vector_stores/`
15. **Mover `whatsapp_catalog_service.py`** → `app/integrations/whatsapp/`
16. **Mover `whatsapp_flows_service.py`** → `app/integrations/whatsapp/`
17. **Migrar `knowledge_service.py`** → Use Cases
18. **Mover `prompt_service.py`** → `app/core/shared/`

### Prioridad Baja (5 servicios)

19. **Mover `scheduled_sync_service.py`** → `app/domains/ecommerce/infrastructure/services/`
20. **Mover `pgvector_metrics_service.py`** → `app/integrations/vector_stores/`
21. **Migrar `category_vector_service.py`** → integrar en SearchProductsUseCase
22. **Mover `ai_data_pipeline_service.py`** → `app/integrations/llm/`
23. **Mover `data_extraction_service.py`** → `app/core/shared/utils/`
24. **Mover `phone_normalizer_pydantic.py`** → `app/core/shared/utils/`

### Mantener (3 servicios)

- `token_service.py` - Auth infrastructure
- `user_service.py` - Auth infrastructure
- `langgraph_chatbot_service.py` - Wrapper temporal para compatibilidad

---

## 🎯 Resumen por Acción

| Acción | Cantidad | Líneas Aprox |
|--------|----------|--------------|
| **Deprecar** | 6 | ~2,670 |
| **Mover a infrastructure** | 8 | ~2,100 |
| **Mover a integrations** | 7 | ~1,450 |
| **Migrar a Use Cases** | 3 | ~950 |
| **Mover a shared/utils** | 2 | ~300 |
| **Mantener** | 3 | ~1,150 |
| **TOTAL** | **27** | **~8,620** |

---

## 📈 Progreso de Migración

```
Fase 8b Actual:
████░░░░░░░░░░░░░░░░  3/27 servicios (11%)

Fase 8b Prioridad Alta:
████████░░░░░░░░░░░░  3/10 servicios (30%)

Total estimado para completar:
- Prioridad Alta: 7 servicios restantes (~3-4 días)
- Prioridad Media: 8 servicios (~3-4 días)
- Prioridad Baja: 5 servicios (~2-3 días)
```

---

## 🚀 Siguiente Paso Inmediato

**Acción**: Mover `dux_sync_service.py` a infrastructure

**Razón**:
- Es un servicio de infraestructura puro (sincronización con API externa)
- No tiene lógica de negocio
- Pertenece al dominio e-commerce
- Prioridad alta en el plan

**Destino**: `app/domains/ecommerce/infrastructure/services/dux_sync_service.py`

**Impacto**:
- Imports a actualizar: ~10 archivos
- Tests a actualizar: ~2 archivos
- Mejora organización del código
- Sin breaking changes (solo reubicación)

---

## 📝 Notas

1. **Servicios de Auth** (`token_service`, `user_service`): Mantener en `app/services/` porque son infraestructura transversal, no pertenecen a ningún dominio específico.

2. **LangGraph Service**: Mantener temporalmente como wrapper para dar tiempo a migrar todos los consumidores a SuperOrchestrator.

3. **Vector Services**: Agrupar todos en `app/integrations/vector_stores/` para facilitar cambio de proveedor en futuro (ChromaDB → pgvector → otro).

4. **WhatsApp Services**: Agrupar en `app/integrations/whatsapp/` para aislar dependencia externa.

5. **DUX Services**: Específicos de e-commerce, mover al dominio correspondiente.

---

**Última actualización**: 2025-01-23
**Versión**: 1.0
**Autor**: Claude (Architectural Migration Phase 8b)
