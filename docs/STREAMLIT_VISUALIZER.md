# Streamlit Agent Visualizer

## Descripción General

El **Streamlit Agent Visualizer** es una herramienta de visualización interactiva que permite observar en tiempo real el funcionamiento interno del sistema multi-agente de Aynux. Esta aplicación proporciona una interfaz gráfica completa para:

- **Visualizar el grafo de ejecución** con nodos resaltados en tiempo real
- **Inspeccionar el razonamiento** de cada agente (análisis del orquestador, supervisor, etc.)
- **Ver el estado completo** del sistema en cada paso de ejecución
- **Revisar la historia de conversación** con mensajes de usuario y respuestas del asistente
- **Analizar métricas de rendimiento** (tiempos de ejecución, frecuencia de visitas por agente, etc.)

## Arquitectura

El visualizador está integrado en el **Streamlit Admin Dashboard** como una aplicación multi-página:

```
streamlit_admin/
├── app.py                               # Punto de entrada principal
├── lib/
│   ├── session_state.py                 # Gestión de estado de sesión
│   ├── auth.py                          # Autenticación
│   └── api_client.py                    # Cliente API
└── pages/
    ├── 0_🔐_Login.py
    ├── 1_🤖_Chat_Visualizer.py         # ← Chat Visualizer
    ├── 2_📚_Knowledge_Base.py
    ├── 3_📤_Upload_Documents.py
    ├── 4_🔧_Embeddings.py
    ├── 5_🏢_Excelencia.py
    ├── 6_⚙️_Agent_Config.py
    ├── 7_📊_Statistics.py
    ├── 8_🏢_Organizations.py
    ├── 9_👥_Users.py
    └── 10_⚙️_Tenant_Config.py
```

## Características Principales

### 1. 📊 Grafo de Ejecución Interactivo

Visualización gráfica del flujo de ejecución usando Graphviz:

- **Nodos coloreados** según su estado:
  - 🔴 Rojo: Nodo actualmente en ejecución
  - ⚪ Gris: Nodos visitados
  - ⚪ Gris claro: Nodos no visitados
  - 🔵 Azul: Orquestador
  - 🟢 Verde: Supervisor

- **Aristas resaltadas** mostrando el camino recorrido
- **Timeline de ejecución** con expandibles para cada paso

### 2. 🧠 Panel de Razonamiento

Visualiza el pensamiento interno de los agentes:

- **Análisis del Orquestador**:
  - Detección de intención
  - Confianza de la clasificación
  - Decisión de routing
  - Razonamiento detrás de la decisión
  - Entidades extraídas del mensaje

- **Análisis del Supervisor**:
  - Evaluación de calidad de la respuesta
  - Puntuación de completitud
  - Decisión de continuar o finalizar
  - Feedback para mejorar

- **Evaluación Final**:
  - Criterios de evaluación (relevancia, precisión, completitud)
  - Sugerencias de mejora
  - Estado de aprobación

### 3. 🔍 Inspector de Estado Detallado

Visualización organizada del estado completo del grafo en 5 tabs:

- **📋 Resumen**: Métricas clave, agente actual, historial de agentes
- **💬 Mensajes**: Todos los mensajes de la conversación con metadata
- **🎯 Intención & Routing**: Análisis de intención, decisiones de routing, historial
- **📊 Datos**: Datos recuperados, respuestas de agentes, contexto de cliente
- **⚙️ Control de Flujo**: Estado de re-routing, manejo de errores, métricas de rendimiento

### 4. 💬 Historia de Conversación

Vista estilo chat con:

- Mensajes del usuario con timestamp
- Respuestas del asistente con información del agente y timestamp
- Formato visualmente claro y fácil de seguir

### 5. 📈 Métricas de Rendimiento

Análisis detallado del rendimiento:

- **Tiempo total de ejecución**
- **Número total de pasos**
- **Tiempo promedio por paso**
- **Frecuencia de visitas por agente** (gráfico de barras)
- **Timeline detallado** de cada paso con duraciones
- **Agente más visitado**

### 6. 📥 Exportación de Datos

Exporta toda la sesión a JSON incluyendo:

- Historia de conversación completa
- Todos los pasos de ejecución
- Métricas de rendimiento
- Timestamp de la sesión

## Instalación

### Prerrequisitos

- Python 3.12+
- `uv` package manager
- Variables de entorno configuradas en `.env`

### Paso 1: Instalar Dependencias

```bash
# Sincronizar dependencias con uv
uv sync
```

Las dependencias necesarias ya están incluidas en `pyproject.toml`:
- `streamlit>=1.39.0`
- `graphviz>=0.20.3`

### Paso 2: Instalar Graphviz (Sistema)

**En Linux/Ubuntu:**
```bash
sudo apt-get install graphviz
```

**En macOS:**
```bash
brew install graphviz
```

**En Windows:**
Descarga e instala desde: https://graphviz.org/download/

## Uso

### Inicio Rápido

Ejecuta el script de inicio para el dashboard completo:

```bash
./run_admin.sh
```

O manualmente:

```bash
streamlit run streamlit_admin/app.py
```

Luego navega a la página **"🤖 Chat Visualizer"** desde el menú lateral.

### Paso a Paso

1. **Iniciar la aplicación**: Ejecuta el comando anterior
2. **Abrir en navegador**: Streamlit abrirá automáticamente `http://localhost:8501`
3. **Navegar a Chat Visualizer**: Click en "🤖 Chat Visualizer" en el menú lateral
4. **Inicializar el grafo**: Click en "🚀 Inicializar Grafo" en la barra lateral
5. **Enviar mensajes**: Escribe un mensaje en el input y presiona "📤 Enviar"
6. **Explorar visualizaciones**: Navega por las pestañas para ver diferentes aspectos

## Interfaz de Usuario

### Panel Principal

```
┌─────────────────────────────────────────────────────────┐
│  🤖 Chat Visualizer                                      │
│  Visualización en tiempo real del sistema multi-agente  │
│                                                          │
│  [Estado] [Agentes] [Mensajes] [Pasos]                 │
│                                                          │
│  💬 Interfaz de Conversación                            │
│  [________________Mensaje________________] [📤 Enviar]   │
│                                                          │
│  [📊 Grafo] [🧠 Razonamiento] [🔍 Estado] [💬 Chat]    │
└─────────────────────────────────────────────────────────┘
```

### Barra Lateral

```
┌──────────────────────┐
│ ⚙️ Configuración     │
│                      │
│ [🚀 Inicializar]    │
│                      │
│ 🤖 Agentes:         │
│ ✓ greeting_agent    │
│ ✓ product_agent     │
│ ✓ ...               │
│                      │
│ [🗑️ Limpiar]       │
│ [💾 Exportar]       │
└──────────────────────┘
```

## Ejemplos de Uso

### Caso 1: Depuración de Routing

**Problema**: El orquestador está enviando consultas de productos al agente incorrecto.

**Solución con el visualizador**:
1. Envía una consulta de producto: "¿Tienen laptops gaming?"
2. Ve al tab **🧠 Razonamiento**
3. Expande **Análisis del Orquestador**
4. Revisa:
   - Intención detectada
   - Confianza de la clasificación
   - Decisión de routing
   - Razonamiento detrás de la decisión

**Resultado**: Puedes ver exactamente por qué el orquestador tomó esa decisión y ajustar los prompts si es necesario.

### Caso 2: Análisis de Rendimiento

**Problema**: Las respuestas son lentas y quieres identificar cuellos de botella.

**Solución con el visualizador**:
1. Envía varios mensajes de diferentes tipos
2. Ve al tab **📈 Métricas**
3. Revisa:
   - Tiempo total de ejecución
   - Tiempo promedio por paso
   - Timeline detallado con duraciones
   - Agente más lento (paso más largo)

**Resultado**: Identificas qué agente o paso está causando las demoras.

### Caso 3: Verificación de Flujo Completo

**Problema**: Quieres verificar que el flujo multi-agente funciona correctamente de principio a fin.

**Solución con el visualizador**:
1. Envía un mensaje complejo que requiera múltiples agentes
2. Ve al tab **📊 Grafo de Ejecución**
3. Observa:
   - Los nodos visitados (resaltados)
   - El camino tomado por el grafo
   - Timeline de ejecución paso a paso

**Resultado**: Visualización clara del flujo completo desde entrada hasta salida.

### Caso 4: Inspección de Estado Detallado

**Problema**: Necesitas entender exactamente qué está pasando en cada paso del grafo.

**Solución con el visualizador**:
1. Envía un mensaje
2. Ve al tab **🔍 Estado Detallado**
3. Explora los 5 sub-tabs:
   - **Resumen**: Vista general rápida
   - **Mensajes**: Toda la conversación
   - **Intención & Routing**: Análisis de intenciones
   - **Datos**: Datos recuperados y contexto
   - **Control de Flujo**: Estado interno del sistema

**Resultado**: Conocimiento completo del estado interno en cada momento.

## Arquitectura Técnica

### Componentes Principales

```
streamlit_admin/pages/1_🤖_Chat_Visualizer.py
├── ChatVisualizerPage (clase principal)
│   ├── initialize_graph()
│   ├── process_message()
│   └── _stream_graph_execution()
│
app/visualization/
├── graph_visualizer.py
│   └── GraphVisualizer
│       └── create_graph_visualization()
│
├── reasoning_display.py
│   └── ReasoningDisplay
│       ├── display_orchestrator_analysis()
│       ├── display_supervisor_analysis()
│       └── display_supervisor_evaluation()
│
├── state_inspector.py
│   └── StateInspector
│       └── display_state()
│
└── metrics_tracker.py
    └── MetricsTracker
        ├── record_step()
        ├── get_metrics()
        └── get_summary()
```

### Flujo de Datos

```
Usuario → [Input] → process_message()
                           ↓
                    AynuxGraph.astream()
                           ↓
                    [Streaming Events]
                           ↓
         ┌─────────────────┴─────────────────┐
         ↓                 ↓                  ↓
    MetricsTracker  GraphVisualizer  StateInspector
         ↓                 ↓                  ↓
    [Métricas]       [Visualización]    [Estado]
         ↓                 ↓                  ↓
         └─────────────────┬─────────────────┘
                           ↓
                    [Streamlit UI]
                           ↓
                        Usuario
```

### Integración con LangGraph

El visualizador usa el método `astream()` de `AynuxGraph` para obtener eventos en tiempo real:

```python
async for event in self.graph.astream(message, conversation_id):
    if event.get("type") == "stream_event":
        # Actualizar visualización en tiempo real
        current_node = event["data"]["current_node"]
        state_preview = event["data"]["state_preview"]

        # Registrar en metrics tracker
        metrics_tracker.record_step(current_node, timestamp)

        # Actualizar UI
        st.info(f"Ejecutando {current_node}")
```

## Configuración Avanzada

### Variables de Entorno

El visualizador usa las mismas variables de entorno que la aplicación principal:

```bash
# .env

# Ollama Configuration
OLLAMA_API_URL=http://localhost:11434
OLLAMA_API_MODEL_COMPLEX=deepseek-r1:7b

# Database
DATABASE_URL=postgresql://user:pass@localhost/aynux

# Agent Configuration
ENABLED_AGENTS=greeting_agent,product_agent,promotions_agent,tracking_agent,support_agent,invoice_agent,excelencia_agent,fallback_agent,farewell_agent,data_insights_agent
```

### Personalización de Colores

Edita `app/visualization/graph_visualizer.py`:

```python
COLORS = {
    "orchestrator": "#4A90E2",  # Azul
    "supervisor": "#50C878",    # Verde
    "agent": "#F5A623",         # Naranja
    "current": "#E74C3C",       # Rojo (nodo actual)
    "visited": "#95A5A6",       # Gris (visitado)
    "inactive": "#ECF0F1",      # Gris claro (inactivo)
}
```

### Streamlit Configuration

Crea `.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#4A90E2"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"

[server]
port = 8501
headless = false
enableCORS = false
```

## Troubleshooting

### Error: "Graph not initialized"

**Problema**: El grafo no se ha inicializado correctamente.

**Solución**:
1. Verifica que todas las variables de entorno estén configuradas en `.env`
2. Asegúrate de que Ollama esté ejecutándose (`ollama serve`)
3. Verifica la conexión a la base de datos
4. Click en "🚀 Inicializar Grafo" en la barra lateral

### Error: "Graphviz executable not found"

**Problema**: Graphviz no está instalado en el sistema.

**Solución**:
- Linux/Ubuntu: `sudo apt-get install graphviz`
- macOS: `brew install graphviz`
- Windows: Descarga desde https://graphviz.org/download/

### Visualización lenta con muchos agentes

**Problema**: La renderización del grafo es lenta con muchos agentes habilitados.

**Solución**:
1. Reduce el número de agentes habilitados en `ENABLED_AGENTS`
2. Desactiva la actualización automática en Streamlit
3. Usa un navegador más rápido (Chrome/Edge recomendado)

### State no se actualiza en tiempo real

**Problema**: El estado no refleja cambios inmediatos.

**Solución**:
1. Verifica que `astream()` esté funcionando correctamente
2. Revisa los logs de la consola para errores
3. Usa `st.rerun()` manualmente si es necesario

## Roadmap y Mejoras Futuras

### Versión 1.1
- [ ] Gráficos de rendimiento histórico
- [ ] Comparación entre múltiples ejecuciones
- [ ] Filtros avanzados para el inspector de estado
- [ ] Exportación a diferentes formatos (PDF, CSV)

### Versión 1.2
- [ ] Modo de depuración interactivo con breakpoints
- [ ] Edición de estado en tiempo real
- [ ] Replay de conversaciones pasadas
- [ ] Integración con LangSmith para traces completos

### Versión 2.0
- [ ] Multi-usuario con sesiones separadas
- [ ] Dashboard de métricas agregadas
- [ ] Alertas y notificaciones de anomalías
- [ ] Integración con herramientas de CI/CD

## Contribuciones

Para contribuir al visualizador:

1. Crea una nueva rama: `git checkout -b feature/nueva-visualizacion`
2. Implementa los cambios en `app/visualization/`
3. Actualiza la documentación en `docs/STREAMLIT_VISUALIZER.md`
4. Crea tests en `tests/visualization/`
5. Abre un Pull Request

## Soporte

Para reportar bugs o solicitar features:

- Abre un issue en GitHub
- Incluye:
  - Versión de Python
  - Versión de Streamlit
  - Logs de error completos
  - Pasos para reproducir

## Licencia

Este visualizador está incluido como parte del proyecto Aynux y comparte la misma licencia.

---

**Creado con ❤️ para facilitar el desarrollo y depuración del sistema multi-agente Aynux**
