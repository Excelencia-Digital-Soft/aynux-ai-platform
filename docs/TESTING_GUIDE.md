# 🧪 Guía de Testing y Monitoreo - Aynux Bot

Esta guía proporciona instrucciones completas para probar y monitorear el comportamiento del bot, incluyendo decisiones de agentes, trazas de LangSmith y visualización gráfica del sistema.

## 📋 Tabla de Contenidos

1. [Configuración Inicial](#configuración-inicial)
2. [Herramientas de Testing](#herramientas-de-testing)
3. [LangSmith Integration](#langsmith-integration)
4. [Workflow de Testing](#workflow-de-testing)
5. [Interpretación de Resultados](#interpretación-de-resultados)
6. [Troubleshooting](#troubleshooting)

---

## 🚀 Configuración Inicial

### Prerequisitos

1. **API Key de LangSmith**: Obtén tu clave en [smith.langchain.com](https://smith.langchain.com)

2. **Variables de Entorno**: Configura en tu archivo `.env`:

```bash
# LangSmith Configuration (REQUERIDO para tracing)
LANGSMITH_API_KEY=tu_api_key_aqui
LANGSMITH_PROJECT=aynux-production
LANGSMITH_TRACING_ENABLED=true
LANGSMITH_VERBOSE=false
LANGSMITH_SAMPLE_RATE=1.0
LANGSMITH_METRICS_ENABLED=true
```

3. **Dependencias Adicionales**:

```bash
# Instalar dependencias de testing
uv add rich streamlit plotly pandas

# O con pip
pip install rich streamlit plotly pandas
```

### Verificación de Configuración

Ejecuta el script de verificación para asegurar que todo está configurado correctamente:

```bash
python tests/test_langsmith_verification.py
```

**Salida Esperada:**
- ✅ LangSmith inicializado correctamente
- ✅ API connection exitosa
- ✅ Trazas creadas exitosamente
- ✅ Servicio de chat operacional

Si alguna verificación falla, sigue las instrucciones en pantalla para corregir la configuración.

---

## 🛠️ Herramientas de Testing

### 1. **Verificación de LangSmith** (`test_langsmith_verification.py`)

**Propósito**: Verifica que LangSmith está correctamente configurado y funcionando.

**Ejecución**:
```bash
python tests/test_langsmith_verification.py
```

**Qué Verifica**:
- ✅ Variables de entorno configuradas
- ✅ Conexión a LangSmith API
- ✅ Creación de trazas
- ✅ Procesamiento de conversaciones
- ✅ Almacenamiento de métricas

**Cuándo Usar**:
- Al configurar el proyecto por primera vez
- Después de cambios en configuración
- Para diagnosticar problemas de tracing

---

### 2. **Chat Interactivo** (`test_chat_interactive.py`)

**Propósito**: Interface de línea de comandos para probar conversaciones en tiempo real con el mismo backend que WhatsApp.

**Ejecución**:
```bash
python tests/test_chat_interactive.py
```

**Características**:
- 💬 Chat en tiempo real con el bot
- 🤖 Visualización del agente utilizado
- ⏱️ Métricas de tiempo de procesamiento
- 📊 Metadatos de cada respuesta
- 🔗 Links directos a trazas de LangSmith
- 📜 Historial de conversación
- 🎯 Escenarios predefinidos

**Comandos Disponibles**:

| Comando | Descripción |
|---------|-------------|
| `<mensaje>` | Enviar mensaje normal |
| `/stream <mensaje>` | Enviar con streaming |
| `/scenarios` | Ver escenarios predefinidos |
| `/run <número>` | Ejecutar escenario específico |
| `/history` | Ver historial de conversación |
| `/traces` | Ver últimas trazas en LangSmith |
| `/stats` | Mostrar estadísticas de sesión |
| `/clear` | Reiniciar sesión |
| `/help` | Mostrar ayuda |
| `/quit` | Salir |

**Ejemplo de Uso**:
```bash
> Hola
Bot (greeting_agent): ¡Hola! ¿En qué puedo ayudarte hoy?

> ¿Qué laptops tienen?
Bot (product_agent): Tenemos las siguientes laptops disponibles:
1. Dell XPS 15 - $1,299
2. HP Pavilion 14 - $899
...

> /run 1
# Ejecuta el escenario predefinido #1
```

---

### 3. **Dashboard de Monitoreo** (`monitoring_dashboard.py`)

**Propósito**: Dashboard web interactivo con visualizaciones en tiempo real, métricas de rendimiento y chat de prueba.

**Ejecución**:
```bash
streamlit run tests/monitoring_dashboard.py
```

**Características Principales**:

#### 📊 **Tab 1: Dashboard**
- **Métricas Generales**:
  - Total de ejecuciones
  - Tasa de éxito
  - Latencia promedio y P95
  - Tasa de error

- **Gráficos de Uso**:
  - Distribución de uso por agente (pie chart)
  - Ejecuciones por hora (timeline)
  - Análisis de errores por tipo

- **Tabla de Ejecuciones Recientes**:
  - Últimas 20 ejecuciones
  - Estado, latencia, timestamp
  - Link directo a LangSmith

#### 🔀 **Tab 2: Graph Visualization**
- **Visualización del Grafo de Agentes**:
  - Arquitectura del sistema multi-agente
  - Flujo de decisiones y routing
  - Conexiones entre Orchestrator, agentes y Supervisor

- **Explicación del Flujo**:
  - Punto de entrada: Orchestrator
  - Agentes especializados por tipo de consulta
  - Supervisor valida y decide si continuar

#### 💬 **Tab 3: Test Chat**
- **Chat Interactivo en el Dashboard**:
  - Mismo backend que WhatsApp
  - Interfaz visual moderna
  - Metadatos expandibles
  - Trazas automáticas en LangSmith

#### 📖 **Tab 4: Documentación**
- Guía completa del dashboard
- Explicación de métricas
- Instrucciones de uso

**Navegación del Dashboard**:

1. **Sidebar Izquierdo**:
   - Estado de LangSmith (activo/inactivo)
   - Selector de rango temporal
   - Botón de refresh

2. **Contenido Principal**:
   - Métricas en tarjetas
   - Gráficos interactivos (Plotly)
   - Tablas con datos detallados

**Interpretación de Gráficos**:

- **Agent Usage (Pie Chart)**: Muestra qué agentes se usan más frecuentemente
- **Performance Timeline**: Identifica picos de tráfico y patrones de uso
- **Error Analysis**: Ayuda a identificar problemas recurrentes

---

### 4. **Escenarios de Prueba** (`test_scenarios.py`)

**Propósito**: Suite de pruebas automatizadas con escenarios predefinidos para validar comportamiento de agentes.

**Ejecución**:

```bash
# Ver todos los escenarios disponibles
python tests/test_scenarios.py list

# Ejecutar todos los escenarios
python tests/test_scenarios.py all

# Ejecutar escenario específico
python tests/test_scenarios.py run product_query_simple

# Ejecutar por tag
python tests/test_scenarios.py tag products
```

**Escenarios Incluidos**:

| ID | Nombre | Mensajes | Tags |
|----|--------|----------|------|
| `product_query_simple` | Consulta Simple de Productos | 1 | products, simple |
| `product_query_specific` | Búsqueda Específica | 2 | products, search |
| `category_navigation` | Navegación por Categorías | 3 | categories, navigation |
| `order_tracking` | Seguimiento de Pedido | 3 | tracking, orders |
| `customer_support` | Soporte al Cliente | 3 | support, returns |
| `invoice_credit_query` | Facturación y Crédito | 3 | credit, invoicing |
| `promotions_query` | Consulta de Promociones | 3 | promotions, offers |
| `greeting_farewell` | Saludos y Despedidas | 5 | greeting, farewell |
| `multi_turn_product_purchase` | Compra Multi-Turno | 7 | multi-turn, end-to-end |
| `ambiguous_query` | Consulta Ambigua | 3 | ambiguous, fallback |
| `price_comparison` | Comparación de Precios | 3 | products, pricing |
| `specifications_query` | Especificaciones Técnicas | 4 | products, technical |
| `availability_stock` | Consulta de Disponibilidad | 3 | products, stock |
| `shipping_delivery` | Envío y Entrega | 4 | shipping, logistics |
| `payment_methods` | Métodos de Pago | 4 | payment, financing |
| `warranty_returns` | Garantía y Devoluciones | 3 | warranty, policy |

**Validaciones Automáticas**:
- ✅ Agentes utilizados coinciden con los esperados
- ✅ Todas las respuestas se generaron sin errores
- ✅ Tiempos de respuesta dentro de rangos aceptables

**Salida del Test**:
```
📊 TEST EXECUTION SUMMARY
═══════════════════════════════════════════════════════════

Total Scenarios: 16
Passed: 14
Failed: 2
Success Rate: 87.5%

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ ID                        ┃ Name               ┃ Status  ┃ Avg Time (ms)┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ product_query_simple      │ Consulta Simple... │ ✅ PASS │ 1234         │
│ product_query_specific    │ Búsqueda Específ...│ ✅ PASS │ 1456         │
...
└───────────────────────────┴────────────────────┴─────────┴──────────────┘

💾 Results saved to: test_results.json
```

---

## 🔗 LangSmith Integration

### Cómo Funciona el Tracing

**LangSmith** es la plataforma de observabilidad de LangChain que rastrea automáticamente todas las ejecuciones del bot.

**Qué se Rastrea**:
1. **Cada mensaje del usuario** y la respuesta del bot
2. **Decisiones del Orchestrator**: Qué intención detectó
3. **Agente seleccionado**: Routing decision
4. **Tiempo de procesamiento**: Latencia total y por componente
5. **Errores y excepciones**: Stack traces completos
6. **Contexto de conversación**: Session ID, user ID, metadata

**Estructura de Trazas**:

```
Conversación (Run)
├── Orchestrator (Chain)
│   ├── Intent Detection (LLM)
│   └── Router Decision (Tool)
├── ProductAgent (Chain)
│   ├── Query Processing (LLM)
│   ├── Database Search (Tool)
│   └── Response Generation (LLM)
└── Supervisor (Chain)
    └── Validation (LLM)
```

### Ver Trazas en LangSmith

1. **Acceder al Dashboard**:
   - URL: https://smith.langchain.com
   - Login con tu cuenta
   - Selecciona el proyecto configurado en `LANGSMITH_PROJECT`

2. **Filtrar Trazas**:
   - Por fecha/hora
   - Por nombre de agente
   - Por estado (success/error)
   - Por session_id o user_id

3. **Inspeccionar Traza Individual**:
   - Ver árbol de ejecución completo
   - Inputs y outputs de cada paso
   - Tiempos de ejecución
   - Metadata y tags

4. **Análisis de Performance**:
   - Latency timeline
   - Token usage (si aplica)
   - Error rates
   - Throughput

### Métricas Clave en LangSmith

| Métrica | Descripción | Objetivo |
|---------|-------------|----------|
| **Success Rate** | % de ejecuciones sin error | >95% |
| **Avg Latency** | Tiempo promedio de respuesta | <2s |
| **P95 Latency** | Percentil 95 de latencia | <5s |
| **Error Rate** | % de ejecuciones con error | <5% |
| **Agent Distribution** | Uso relativo de cada agente | Balanceado según casos de uso |

---

## 📝 Workflow de Testing

### Workflow Recomendado para Testing Completo

#### **Fase 1: Configuración y Verificación** (5-10 min)

```bash
# 1. Verificar configuración
python tests/test_langsmith_verification.py

# 2. Revisar estado en LangSmith
# Visitar: https://smith.langchain.com/o/default/projects/p/aynux-production
```

**Resultado Esperado**: ✅ Todas las verificaciones pasan

---

#### **Fase 2: Testing Manual Interactivo** (15-30 min)

```bash
# Iniciar chat interactivo
python tests/test_chat_interactive.py
```

**Qué Probar**:
1. **Saludos básicos**: "Hola", "Buenos días"
2. **Consultas de productos**: "¿Qué laptops tienen?"
3. **Navegación de categorías**: "Muéstrame las categorías"
4. **Tracking**: "¿Dónde está mi pedido #12345?"
5. **Soporte**: "Mi producto llegó dañado"
6. **Despedidas**: "Gracias, adiós"

**Observar**:
- ✅ Agente correcto seleccionado para cada consulta
- ✅ Respuestas coherentes y relevantes
- ✅ Tiempos de respuesta <3s
- ✅ Metadatos completos

---

#### **Fase 3: Testing Automatizado** (10-20 min)

```bash
# Ejecutar suite completa de escenarios
python tests/test_scenarios.py all
```

**Revisar Resultados**:
- Success rate general
- Escenarios que fallaron (si los hay)
- Tiempos promedio de respuesta
- Archivo `test_results.json` generado

**Análisis de Fallos**:
Si algún escenario falla:
1. Ver detalle del error en consola
2. Revisar qué agente se esperaba vs. cuál se usó
3. Ir a LangSmith para ver la traza completa
4. Identificar la causa raíz

---

#### **Fase 4: Monitoreo con Dashboard** (Tiempo variable)

```bash
# Iniciar dashboard
streamlit run tests/monitoring_dashboard.py
```

**Análisis en Dashboard**:

1. **Tab Dashboard**:
   - Revisar métricas generales
   - Identificar agentes más usados
   - Detectar errores recurrentes

2. **Tab Graph Viz**:
   - Entender arquitectura del sistema
   - Verificar flujo de agentes

3. **Tab Test Chat**:
   - Probar casos edge directamente
   - Ver respuestas en tiempo real

4. **Refrescar periódicamente** para ver tendencias

---

#### **Fase 5: Testing de WhatsApp** (Opcional)

Para probar el comportamiento real en WhatsApp:

1. Configurar webhook de WhatsApp apuntando a tu servidor
2. Enviar mensajes reales desde WhatsApp
3. Observar trazas en LangSmith
4. Comparar comportamiento con chat web

**Diferencia Clave**:
- WhatsApp usa `WebhookService` que procesa mensajes incoming
- Chat web usa API REST directa
- **Mismo backend LangGraph** → comportamiento idéntico de agentes

---

## 🔍 Interpretación de Resultados

### Métricas de Éxito

#### **1. Routing Accuracy** (Precisión de Enrutamiento)

**Definición**: ¿El Orchestrator selecciona el agente correcto?

**Cómo Medir**:
- En test scenarios: ver `agents_match` en resultados
- En LangSmith: revisar decisiones de routing

**Objetivo**: >90% de precisión

**Qué hacer si es bajo**:
- Revisar prompts del `IntentRouter`
- Añadir ejemplos de intenciones en configuración
- Mejorar detección de keywords

---

#### **2. Response Quality** (Calidad de Respuestas)

**Definición**: ¿Las respuestas son útiles, coherentes y correctas?

**Cómo Medir**:
- Revisión manual de respuestas
- Feedback de usuarios
- LangSmith evaluators (opcional)

**Criterios**:
- ✅ Responde la pregunta del usuario
- ✅ Tono apropiado (profesional, amigable)
- ✅ Sin alucinaciones o información incorrecta
- ✅ Contexto conversacional mantenido

---

#### **3. Performance** (Rendimiento)

**Métricas Clave**:

| Métrica | Objetivo | Crítico |
|---------|----------|---------|
| Avg Latency | <2s | <5s |
| P95 Latency | <5s | <10s |
| Error Rate | <5% | <10% |
| Success Rate | >95% | >90% |

**Optimizaciones si es lento**:
- Revisar queries a base de datos
- Optimizar embeddings y búsqueda vectorial
- Cachear respuestas frecuentes en Redis
- Reducir complejidad de prompts

---

#### **4. Error Handling** (Manejo de Errores)

**Tipos de Errores Comunes**:

1. **Database Errors**: Conexión a PostgreSQL falla
   - Solución: Verificar configuración de DB, pool size

2. **AI Model Errors**: Ollama no responde
   - Solución: Verificar servicio Ollama activo, modelo descargado

3. **Integration Errors**: DUX API, WhatsApp API fallan
   - Solución: Implementar fallbacks y reintentos

4. **Validation Errors**: Input del usuario inválido
   - Solución: Mejorar validación y mensajes de error

**En LangSmith**: Filtrar por `error=true` para ver trazas con errores

---

### Análisis de Conversaciones Multi-Turno

**Qué Verificar**:
- ✅ Contexto mantenido entre mensajes
- ✅ Referencias a mensajes anteriores funcionan
- ✅ Estado de conversación persiste correctamente
- ✅ Transiciones entre agentes son fluidas

**Ejemplo de Conversación Multi-Turno Exitosa**:
```
User: Hola                          → GreetingAgent
User: ¿Qué laptops tienen?          → ProductAgent (lista productos)
User: ¿Cuál es la más barata?       → ProductAgent (filtra por precio, mantiene contexto)
User: ¿Y la más potente?            → ProductAgent (filtra por specs, mantiene contexto)
User: Quiero comprar la Dell XPS 15 → ProductAgent (procesa selección)
User: ¿Cómo puedo pagar?            → SupportAgent (info de pago)
User: Gracias                       → FarewellAgent
```

**Red Flags**:
- ❌ Agente no recuerda selección anterior
- ❌ Contexto se pierde después de 3-4 mensajes
- ❌ Respuestas contradictorias

---

## 🐛 Troubleshooting

### Problema: LangSmith no muestra trazas

**Síntomas**:
- Dashboard vacío en LangSmith
- No hay trazas después de conversaciones

**Diagnóstico**:
```bash
python tests/test_langsmith_verification.py
```

**Soluciones**:

1. **API Key Incorrecta**:
   ```bash
   # Verificar .env
   cat .env | grep LANGSMITH_API_KEY

   # Debería mostrar tu key real, no 'your_api_key_here'
   ```

2. **Tracing Deshabilitado**:
   ```bash
   # En .env
   LANGSMITH_TRACING_ENABLED=true  # Debe ser 'true'
   ```

3. **Proyecto Incorrecto**:
   ```bash
   # Verificar que el proyecto existe en LangSmith
   # Ir a: https://smith.langchain.com
   # El nombre debe coincidir exactamente con LANGSMITH_PROJECT
   ```

4. **Variables de Entorno no Cargadas**:
   ```bash
   # Reiniciar servicio después de cambios en .env
   # O usar python-dotenv para cargar automáticamente
   ```

---

### Problema: Agentes seleccionados incorrectamente

**Síntomas**:
- ProductAgent usado cuando debería ser SupportAgent
- FallbackAgent usado con frecuencia alta

**Diagnóstico**:
- Revisar trazas en LangSmith → ver decisión de `IntentRouter`
- Ver prompt y reasoning del Orchestrator

**Soluciones**:

1. **Mejorar Detección de Intenciones**:
   - Editar `app/agents/intelligence/intent_router.py`
   - Añadir keywords específicas
   - Mejorar ejemplos de intenciones

2. **Ajustar Prompts del Orchestrator**:
   - Más ejemplos de routing correcto
   - Instrucciones más claras

3. **Revisar Configuración de Agentes**:
   - Verificar que cada agente tiene descripción clara
   - Asegurar que capabilities están bien definidas

---

### Problema: Respuestas lentas (>5s)

**Síntomas**:
- P95 latency >10s
- Usuarios reportan lentitud

**Diagnóstico**:
- En LangSmith: ver timeline de cada step
- Identificar componente más lento

**Soluciones por Componente**:

1. **Ollama (LLM)**:
   - Usar modelo más pequeño: `llama3.2:1b` vs `deepseek-r1:7b`
   - Verificar GPU disponible
   - Reducir longitud de context window

2. **Database Queries**:
   - Añadir índices en PostgreSQL
   - Optimizar queries complejas
   - Implementar caching en Redis

3. **Vector Search**:
   - Reducir número de resultados retornados
   - Verificar que pgvector esté optimizado correctamente
   - Pre-calcular embeddings

4. **Network**:
   - Verificar latencia a APIs externas (DUX, WhatsApp)
   - Implementar timeouts apropiados
   - Usar async/await correctamente

---

### Problema: Errores en Escenarios Automatizados

**Síntomas**:
- Test scenarios fallan consistentemente
- `agents_match = False`

**Diagnóstico**:
```bash
# Ver detalle de fallo
python tests/test_scenarios.py run <scenario_id>

# Revisar archivo de resultados
cat tests/test_results.json | jq '.[] | select(.success == false)'
```

**Soluciones**:

1. **Actualizar Expectativas**:
   - Si el comportamiento cambió intencionalmente
   - Editar `expected_agents` en `test_scenarios.py`

2. **Mejorar Escenario**:
   - Mensajes más claros
   - Contexto adicional en metadata

3. **Debuggear en Chat Interactivo**:
   ```bash
   # Probar manualmente el mismo escenario
   python tests/test_chat_interactive.py
   # Enviar los mismos mensajes y ver qué pasa
   ```

---

### Problema: Dashboard de Streamlit no carga

**Síntomas**:
- Error al ejecutar `streamlit run monitoring_dashboard.py`
- Dashboard se bloquea

**Soluciones**:

1. **Dependencias Faltantes**:
   ```bash
   uv add streamlit plotly pandas rich
   ```

2. **Puerto en Uso**:
   ```bash
   # Streamlit usa puerto 8501 por defecto
   # Si está en uso, especificar otro
   streamlit run tests/monitoring_dashboard.py --server.port 8502
   ```

3. **Error de Inicialización del Servicio**:
   - Verificar que PostgreSQL está corriendo
   - Verificar que Ollama está activo
   - Revisar logs en consola

---

## 📚 Recursos Adicionales

### Documentación de Referencia

- **LangSmith Docs**: https://docs.smith.langchain.com
- **LangGraph Docs**: https://langchain-ai.github.io/langgraph/
- **Streamlit Docs**: https://docs.streamlit.io

### Configuración Avanzada

#### Custom Evaluators en LangSmith

Para evaluación automática de calidad:

```python
# app/evaluation/langsmith_evaluators.py
from langsmith.evaluation import LangSmithRunEvaluator

def custom_evaluator(run, example):
    # Lógica de evaluación
    return {"score": 0.9, "reasoning": "Good response"}

evaluators = [LangSmithRunEvaluator(custom_evaluator)]
```

#### A/B Testing con LangSmith

Comparar versiones de prompts o modelos:

```python
# Experiment 1: Prompt V1
# Experiment 2: Prompt V2
# LangSmith mostrará comparación de métricas
```

---

## 🎯 Mejores Prácticas

### Testing Regular

1. **Daily**: Ejecutar `test_langsmith_verification.py`
2. **Weekly**: Suite completa de escenarios automatizados
3. **Monthly**: Revisión profunda de métricas en LangSmith
4. **Continuous**: Dashboard de Streamlit abierto durante desarrollo

### Organización de Tests

- Crear escenarios para cada nuevo feature
- Mantener tests actualizados con cambios en agentes
- Documentar casos edge descubiertos

### Monitoreo en Producción

- Configurar alertas en LangSmith para error rate >5%
- Revisar métricas semanalmente
- Mantener histórico de trazas para análisis

---

## 🆘 Soporte

Si encuentras problemas no cubiertos en esta guía:

1. **Revisar Logs**: `app/main.py` tiene logging detallado
2. **LangSmith Traces**: Ver errores completos con stack traces
3. **GitHub Issues**: Reportar bugs en el repositorio
4. **Documentación**: Revisar docs/ para detalles de arquitectura

---

**¡Happy Testing! 🎉**
