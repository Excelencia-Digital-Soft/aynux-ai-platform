# 🤖 Streamlit Agent Visualizer - Inicio Rápido

## ¿Qué es esto?

Una aplicación web interactiva para visualizar en tiempo real cómo funcionan los agentes de IA de Aynux. Puedes ver:

- 📊 **Grafo de ejecución** - Ve por dónde pasa tu mensaje en el sistema
- 🧠 **Razonamiento del agente** - Qué está pensando cada agente
- 🔍 **Estado completo** - Todos los datos internos en cada momento
- 💬 **Chat interactivo** - Prueba conversaciones y ve el flujo
- 📈 **Métricas** - Tiempos, frecuencias, rendimiento

## Instalación Rápida

### 1. Instalar dependencias

```bash
# Opción A: Con uv (recomendado)
uv sync

# Opción B: Con pip (si uv falla)
pip install streamlit graphviz
```

### 2. Instalar Graphviz en el sistema

**Linux/Ubuntu:**
```bash
sudo apt-get install graphviz
```

**macOS:**
```bash
brew install graphviz
```

**Windows:**
Descarga desde: https://graphviz.org/download/

### 3. Configurar .env

Copia y configura las variables de entorno:

```bash
cp .env.example .env
# Edita .env con tus credenciales
```

## Ejecutar

### Método 1: Script automático (recomendado)

```bash
./run_visualizer.sh
```

### Método 2: Comando directo

```bash
streamlit run streamlit_agent_visualizer.py
```

Se abrirá automáticamente en tu navegador: **http://localhost:8501**

## Uso Básico

1. **Inicializar**: Click en "🚀 Inicializar Grafo" en la barra lateral
2. **Chatear**: Escribe un mensaje y presiona "📤 Enviar"
3. **Explorar**: Navega por las pestañas:
   - 📊 **Grafo** - Ver flujo visual
   - 🧠 **Razonamiento** - Ver qué piensa cada agente
   - 🔍 **Estado** - Inspeccionar datos internos
   - 💬 **Conversación** - Historia del chat
   - 📈 **Métricas** - Rendimiento y estadísticas

## Ejemplos de Mensajes para Probar

```
"Hola, ¿qué puedes hacer?"
→ Ve cómo el greeting_agent responde

"¿Tienen laptops gaming?"
→ Observa el flujo: orchestrator → product_agent → supervisor

"¿Hay promociones?"
→ Ve cómo se detecta la intención y routing a promotions_agent

"Quiero rastrear mi pedido #12345"
→ Flujo hacia tracking_agent
```

## Características Principales

### Visualización del Grafo con Indicadores Enriquecidos

```
    ┌─────────────┐
    │ Orchestrator│  ← Punto de entrada
    └──────┬──────┘
           │
    ┌──────┴──────────────┐
    │                     │
┌───▼────┐         ┌─────▼─────┐
│Product │  ...    │ Fallback  │
│ Agent  │         │  Agent    │
└───┬────┘         └─────┬─────┘
    │                    │
    └────────┬───────────┘
             │
      ┌──────▼───────┐
      │  Supervisor  │  ← Control de calidad
      └──────┬───────┘
             │
        ┌────▼────┐
        │   END   │
        └─────────┘
```

Los nodos se resaltan según el estado:
- 🔴 Rojo = Ejecutando ahora
- ⚪ Gris = Ya visitado
- ⚪ Gris claro = No visitado

**Nuevo: Indicadores de Progreso en Tiempo Real**

Cada paso muestra un indicador visual enriquecido con:
- 🎯 **Emoji distintivo** del agente
- 📝 **Descripción clara** de la actividad
- 🔄 **Spinner animado** durante ejecución
- ⏱️ **Timestamp** de inicio

Ejemplo durante ejecución:
```
┌─────────────────────────────────────────┐
│ 🛍️  Paso 2: Buscando productos         │
│ Consultando catálogo y generando       │
│ recomendaciones de productos            │
│ 🔧 Agente: product_agent          🔄   │
└─────────────────────────────────────────┘
```

**Timeline Visual Mejorado**

Después de la ejecución, el timeline muestra:
- 📌 **Paso resaltado** (último paso con gradiente)
- 🏷️ **Etiquetas de color** por tipo de agente
- ⏰ **Timestamps precisos**
- 🔍 **Detalles expandibles** por paso

### Panel de Razonamiento

Muestra el "pensamiento" interno:

```
🎯 Análisis del Orquestador:
  - Intención: "product_query"
  - Confianza: 95%
  - Agente: product_agent
  - Razonamiento: "Usuario pregunta por productos específicos..."

👁️ Análisis del Supervisor:
  - Calidad: 8.5/10
  - Completitud: ✅ Sí
  - Decisión: Finalizar conversación
```

### Resumen de Ejecución

Al finalizar, muestra un resumen visual con:
- ✅ **Indicador de éxito/error** con gradiente
- 📊 **Métricas de ejecución** (pasos, tiempo)
- 🛤️ **Ruta completa** del flujo ejecutado

### Inspector de Estado

5 tabs organizados con toda la información:

1. **📋 Resumen** - Vista rápida
2. **💬 Mensajes** - Todos los mensajes
3. **🎯 Intención & Routing** - Decisiones
4. **📊 Datos** - Datos recuperados
5. **⚙️ Control** - Estado interno

## Exportar Sesión

1. Click en "💾 Exportar Sesión (JSON)" en la barra lateral
2. Click en "⬇️ Descargar"
3. Guarda el archivo JSON con toda la sesión

## Troubleshooting

### "Graph not initialized"

**Solución**: Click en "🚀 Inicializar Grafo" en la barra lateral

### "Graphviz executable not found"

**Solución**: Instala graphviz en tu sistema (ver paso 2 arriba)

### "Module not found: streamlit"

**Solución**:
```bash
pip install streamlit graphviz
```

### El grafo no se visualiza

**Solución**:
1. Verifica que graphviz esté instalado: `dot -V`
2. Reinicia Streamlit
3. Revisa los logs en la consola

## Documentación Completa

Para más detalles, ver: **[docs/STREAMLIT_VISUALIZER.md](docs/STREAMLIT_VISUALIZER.md)**

Incluye:
- Arquitectura técnica completa
- Casos de uso detallados
- Configuración avanzada
- Troubleshooting exhaustivo
- Roadmap de mejoras futuras

## Atajos de Teclado

- `Ctrl+R` o `R` - Recargar la aplicación
- `Ctrl+C` (en terminal) - Detener servidor

## Soporte

Para reportar bugs o pedir features:
- Abre un issue en GitHub
- Incluye logs y pasos para reproducir

---

**Creado para facilitar el desarrollo y debugging del sistema multi-agente Aynux** 🚀
