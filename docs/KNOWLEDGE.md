🔍 Análisis Exhaustivo: Tablas de Conocimiento

  Resumen Ejecutivo

  | Tabla                       | Schema     | Propósito                          | Scope                |
  |-----------------------------|------------|------------------------------------|----------------------|
  | core.company_knowledge      | core       | Conocimiento corporativo global    | Toda la organización |
  | core.agent_knowledge        | core       | Conocimiento específico por agente | Per-agent            |
  | excelencia.software_modules | excelencia | Catálogo maestro de módulos        | Dominio Excelencia   |

  ---
  1. core.company_knowledge

  📋 Cuándo se usa

  Usuario hace pregunta → KnowledgeBaseSearch.search()
                                  ↓
                      Busca en agent_knowledge (primero)
                                  ↓
                      Busca en company_knowledge (segundo)
                                  ↓
                      Combina resultados para LLM context

  Se usa cuando:
  1. Un agente necesita contexto RAG para responder
  2. La búsqueda en agent_knowledge no encuentra suficientes resultados
  3. Se necesita información corporativa general (misión, contactos, FAQs)
  4. Se necesita información del catálogo de software (sincronizada desde software_modules)

  📊 Requisitos para obtener datos

  # Ubicación: knowledge_search.py:105-137
  async def _search_company_knowledge(self, query: str, max_results: int):
      embedding_service = KnowledgeEmbeddingService()
      results = await embedding_service.search_knowledge(
          query=query,
          k=max_results,
          min_similarity=0.3,      # ← Threshold bajo para permitir keyword fallback
          keyword_search=True,      # ← Búsqueda híbrida habilitada
      )

  Requisitos:
  | Requisito              | Valor    | Descripción                      |
  |------------------------|----------|----------------------------------|
  | active                 | TRUE     | Solo documentos activos          |
  | min_similarity         | 0.3      | Threshold de similitud vectorial |
  | embedding              | NOT NULL | Debe tener embedding generado    |
  | KNOWLEDGE_BASE_ENABLED | true     | Setting habilitado               |

  Tipos de documento (document_type):
  - mission_vision - Misión y visión
  - contact_info - Información de contacto
  - software_catalog - Sincronizado desde software_modules
  - faq - Preguntas frecuentes generales
  - clients - Información de clientes
  - success_stories - Casos de éxito
  - general - Contenido general
  - support_* - Guías de soporte

  🔗 Dependencias

  software_modules ─────────────────→ company_knowledge
                   CREATE/UPDATE sync   (document_type='software_catalog')
                                        (knowledge_doc_id reference)

  Flujo de sincronización (software_module_use_cases.py:245-290):
  # Al crear módulo:
  knowledge_doc = CompanyKnowledge(
      title=f"Módulo: {module.name}",
      content=module.to_rag_content(),
      document_type="software_catalog",  # ← Tipo especial
      meta_data={
          "module_code": module.code,
          "module_id": str(module.id),
          "status": module.status,
      },
  )

  ---
  2. core.agent_knowledge

  📋 Cuándo se usa

  Usuario hace pregunta → KnowledgeBaseSearch.search()
                                  ↓
           ┌──────────────────────┴──────────────────────┐
           ↓                                              ↓
    SearchAgentKnowledgeUseCase              (después) company_knowledge
    agent_key="support_agent"
           ↓
    Búsqueda vectorial con HNSW
           ↓
    Resultados específicos del agente

  Se usa cuando:
  1. SIEMPRE primero en la búsqueda de conocimiento
  2. Se necesita información específica del agente (no compartida)
  3. Se suben documentos personalizados (PDF, DOCX, TXT, MD)
  4. Se crean FAQs, guías o manuales específicos del agente

  📊 Requisitos para obtener datos

  # Ubicación: agent_knowledge_use_cases.py:51-106
  async def execute(
      self,
      agent_key: str,           # REQUERIDO: ej. "support_agent", "excelencia_agent"
      query: str,               # REQUERIDO: texto de búsqueda
      max_results: int = 3,     # Máximo resultados
      min_similarity: float = 0.5,  # Threshold más alto que company_knowledge
  ):
      # 1. Verifica que existan documentos para el agente
      count = await self.repository.count_by_agent(agent_key)
      if count == 0:
          return []  # ← Sin documentos, retorna vacío

      # 2. Genera embedding de la query
      query_embedding = await self.embedding_service.generate_embedding(query)

      # 3. Si falla embedding → fallback a full-text search
      if not query_embedding:
          return await self.repository.search_fulltext(agent_key, query)

      # 4. Búsqueda semántica
      return await self.repository.search_semantic(
          agent_key=agent_key,
          query_embedding=query_embedding,
          max_results=max_results,
          min_similarity=min_similarity,
      )

  Requisitos:
  | Requisito      | Valor    | Descripción                                       |
  |----------------|----------|---------------------------------------------------|
  | agent_key      | String   | Identificador del agente (ej: "support_agent")    |
  | active         | TRUE     | Solo documentos activos                           |
  | min_similarity | 0.5      | Threshold más estricto que company_knowledge      |
  | embedding      | NOT NULL | Debe tener embedding (fallback a full-text si no) |

  Agentes conocidos:
  - support_agent - Agente de soporte general
  - excelencia_agent - Agente de Excelencia Software

  🔗 Dependencias

  No tiene dependencias externas - Es una tabla independiente por diseño.

  Depende de servicios:
  - KnowledgeEmbeddingService - Para generar embeddings con Ollama
  - DocumentExtractor - Para extraer texto de archivos subidos

  ---
  3. excelencia.software_modules

  📋 Cuándo se usa

  ┌─────────────────────────────────────────────────────────────┐
  │                    FLUJO ADMINISTRATIVO                      │
  │                                                              │
  │  POST /admin/modules ──→ CreateModuleUseCase                │
  │                              ↓                               │
  │         ┌────────────────────┼────────────────────┐         │
  │         ↓                    ↓                    ↓         │
  │  software_modules    company_knowledge     Embedding        │
  │  (source of truth)   (RAG-searchable)     (pgvector)        │
  └─────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │                    FLUJO DE CHATBOT                          │
  │                                                              │
  │  Usuario: "¿Qué módulos tienen?"                            │
  │         ↓                                                    │
  │  ExcelenciaNode._module_manager.get_modules()               │
  │         ↓                                                    │
  │  GetModulesForChatbotUseCase                                │
  │         ↓                                                    │
  │  software_modules (formato legacy dict)                      │
  └─────────────────────────────────────────────────────────────┘

  Se usa cuando:
  1. Administración: CRUD de módulos via API /admin/modules
  2. Chatbot: Para mostrar catálogo de software en respuestas
  3. RAG indirecto: Se sincroniza a company_knowledge para búsqueda vectorial

  📊 Requisitos para obtener datos

  Para chatbot (software_module_use_cases.py:445-466):
  class GetModulesForChatbotUseCase:
      async def execute(self) -> dict[str, dict[str, Any]]:
          return await self.repository.get_all_as_dict(active_only=True)

  Para búsqueda RAG: Los módulos se acceden indirectamente a través de company_knowledge:
  # Los módulos están en company_knowledge como document_type="software_catalog"
  # La búsqueda RAG encuentra estos documentos automáticamente

  Requisitos:
  | Requisito        | Valor       | Descripción                            |
  |------------------|-------------|----------------------------------------|
  | active           | TRUE        | Solo módulos activos                   |
  | organization_id  | NULL o UUID | Para multi-tenancy (SaaS mode)         |
  | knowledge_doc_id | UUID        | Referencia al doc en company_knowledge |

  🔗 Dependencias

  excelencia.software_modules
           │
           │ knowledge_doc_id (FK lógica)
           ↓
  core.company_knowledge
           │
           │ document_type = 'software_catalog'
           │ meta_data.module_id, meta_data.module_code
           ↓
      RAG Search (KnowledgeEmbeddingService)

  Sincronización bidireccional:

  | Operación | software_modules | company_knowledge         |
  |-----------|------------------|---------------------------|
  | CREATE    | Nuevo módulo     | Crea doc software_catalog |
  | UPDATE    | Actualiza módulo | Actualiza doc existente   |
  | DELETE    | active=FALSE     | active=FALSE en doc       |

  ---
  Diagrama de Flujo Completo

  ┌─────────────────────────────────────────────────────────────────────────┐
  │                           FLUJO RAG COMPLETO                            │
  ├─────────────────────────────────────────────────────────────────────────┤
  │                                                                         │
  │  Usuario: "¿Cómo funciona el módulo de turnos?"                        │
  │                           ↓                                             │
  │  ExcelenciaNode._process_internal()                                     │
  │                           ↓                                             │
  │  _get_rag_context(message, query_type)                                  │
  │                           ↓                                             │
  │  KnowledgeBaseSearch.search()                                           │
  │                           ↓                                             │
  │  ┌────────────────────────┼────────────────────────┐                   │
  │  │                        ↓                        │                   │
  │  │     SearchAgentKnowledgeUseCase                 │                   │
  │  │     agent_key="excelencia_agent"                │                   │
  │  │     min_similarity=0.5                          │                   │
  │  │              ↓                                  │                   │
  │  │     ┌───────────────────┐                       │                   │
  │  │     │ agent_knowledge   │                       │                   │
  │  │     │ (per-agent docs)  │                       │                   │
  │  │     └───────────────────┘                       │                   │
  │  │              ↓                                  │                   │
  │  │     Resultados específicos del agente           │                   │
  │  └─────────────────────────────────────────────────┘                   │
  │                           ↓                                             │
  │  ┌────────────────────────┼────────────────────────┐                   │
  │  │                        ↓                        │                   │
  │  │     KnowledgeEmbeddingService.search_knowledge  │                   │
  │  │     min_similarity=0.3                          │                   │
  │  │     keyword_search=True (híbrido)               │                   │
  │  │              ↓                                  │                   │
  │  │     ┌───────────────────┐                       │                   │
  │  │     │ company_knowledge │ ←── software_modules  │                   │
  │  │     │ (incluye módulos) │     (sincronizados)   │                   │
  │  │     └───────────────────┘                       │                   │
  │  │              ↓                                  │                   │
  │  │     Incluye doc "Módulo: Sistema de Turnos"     │                   │
  │  └─────────────────────────────────────────────────┘                   │
  │                           ↓                                             │
  │  _format_results() → Contexto combinado para LLM                       │
  │                           ↓                                             │
  │  ResponseGenerationHandler.generate(rag_context=...)                   │
  │                           ↓                                             │
  │  Respuesta al usuario con información del módulo                       │
  │                                                                         │
  └─────────────────────────────────────────────────────────────────────────┘

  ---
  Matriz de Acceso por API

  | Endpoint                            | Tabla                                | Operación | Auth  |
  |-------------------------------------|--------------------------------------|-----------|-------|
  | GET /admin/knowledge                | company_knowledge                    | READ      | Admin |
  | POST /admin/knowledge               | company_knowledge                    | CREATE    | Admin |
  | PUT /admin/knowledge/{id}           | company_knowledge                    | UPDATE    | Admin |
  | DELETE /admin/knowledge/{id}        | company_knowledge                    | DELETE    | Admin |
  | POST /admin/knowledge/search        | company_knowledge                    | SEARCH    | Admin |
  | GET /agents/{key}/knowledge         | agent_knowledge                      | READ      | Admin |
  | POST /agents/{key}/knowledge        | agent_knowledge                      | CREATE    | Admin |
  | POST /agents/{key}/knowledge/upload | agent_knowledge                      | UPLOAD    | Admin |
  | POST /agents/{key}/knowledge/search | agent_knowledge                      | SEARCH    | Admin |
  | GET /admin/modules                  | software_modules                     | READ      | Admin |
  | POST /admin/modules                 | software_modules + company_knowledge | CREATE    | Admin |
  | PUT /admin/modules/{id}             | software_modules + company_knowledge | UPDATE    | Admin |
  | POST /admin/modules/sync-rag        | software_modules → company_knowledge | SYNC      | Admin |

  ---
  Resumen de Requisitos

  Para que RAG funcione correctamente:

  1. Embeddings generados: Todos los documentos deben tener embedding (vector 768D)
  2. Ollama disponible: Modelo nomic-embed-text para generar embeddings
  3. pgvector habilitado: Extensión PostgreSQL con índice HNSW
  4. KNOWLEDGE_BASE_ENABLED=true: Setting de configuración

  Prioridad de búsqueda:

  1º agent_knowledge (min_similarity=0.5) → Específico del agente
  2º company_knowledge (min_similarity=0.3) → Corporativo + módulos

  Sincronización de módulos:

  software_modules es SOURCE OF TRUTH
           ↓ (auto-sync on CRUD)
  company_knowledge almacena versión RAG-searchable
