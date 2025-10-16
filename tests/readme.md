# 🧪 Aynux Bot - Testing Suite

Suite completa de herramientas para testing, monitoreo y análisis del chatbot multi-agente.

## 📁 Archivos en este directorio

### 🔍 Verificación y Configuración

#### `test_langsmith_verification.py`
Verifica que LangSmith está correctamente configurado y funcionando.

**Uso**:
```bash
python tests/test_langsmith_verification.py
```

**Verifica**:
- ✅ Variables de entorno configuradas
- ✅ Conexión a LangSmith API
- ✅ Creación de trazas
- ✅ Procesamiento de conversaciones

**Cuándo ejecutar**:
- Primera vez que configuras el proyecto
- Después de cambios en `.env`
- Al diagnosticar problemas de tracing

---

### 💬 Testing Interactivo

#### `test_chat_interactive.py`
Interface de línea de comandos para probar conversaciones en tiempo real.

**Uso**:
```bash
python tests/test_chat_interactive.py
```

**Características**:
- Chat en tiempo real con el bot
- Visualización de metadatos
- Escenarios predefinidos
- Links a trazas de LangSmith
- Historial de conversación

**Comandos disponibles**:
- `<mensaje>` - Enviar mensaje
- `/stream <mensaje>` - Streaming response
- `/scenarios` - Ver escenarios
- `/run <#>` - Ejecutar escenario
- `/history` - Ver historial
- `/traces` - Ver trazas
- `/stats` - Estadísticas
- `/quit` - Salir

---

### 📊 Dashboard de Monitoreo

#### `monitoring_dashboard.py`
Dashboard web interactivo con visualizaciones y métricas.

**Uso**:
```bash
streamlit run tests/monitoring_dashboard.py
```

Se abre en: http://localhost:8501

**Características**:
- **Dashboard Tab**: Métricas en tiempo real
  - Total de ejecuciones
  - Tasa de éxito
  - Latencia promedio y P95
  - Distribución por agente
  - Timeline de uso
  - Análisis de errores

- **Graph Viz Tab**: Visualización del flujo
  - Arquitectura multi-agente
  - Conexiones entre componentes
  - Flujo de decisiones

- **Test Chat Tab**: Chat interactivo
  - Interface visual moderna
  - Metadatos expandibles
  - Mismo backend que WhatsApp

- **Docs Tab**: Documentación integrada

---

### 🤖 Tests Automatizados

#### `test_scenarios.py`
Suite de pruebas automatizadas con 16+ escenarios predefinidos.

**Uso**:
```bash
# Listar escenarios
python tests/test_scenarios.py list

# Ejecutar todos
python tests/test_scenarios.py all

# Ejecutar específico
python tests/test_scenarios.py run product_query_simple

# Por tag
python tests/test_scenarios.py tag products
```

**Escenarios incluidos**:
- Consultas de productos (simple, específica, comparación)
- Navegación de categorías
- Tracking de pedidos
- Soporte al cliente
- Facturación y crédito
- Promociones
- Saludos y despedidas
- Conversaciones multi-turno
- Consultas ambiguas
- Especificaciones técnicas
- Disponibilidad de stock
- Envío y entrega
- Métodos de pago
- Garantías y devoluciones

**Salida**:
- Resumen de éxito/fallo
- Métricas de performance
- `test_results.json` con detalles completos

---

## 🚀 Quick Start

### 1. Primera Vez

```bash
# Configura .env
LANGSMITH_API_KEY=tu_api_key
LANGSMITH_PROJECT=aynux-production
LANGSMITH_TRACING_ENABLED=true

# Instala dependencias
uv add rich streamlit plotly pandas

# Verifica configuración
python tests/test_langsmith_verification.py
```

### 2. Testing Diario

```bash
# Opción 1: Chat interactivo
python tests/test_chat_interactive.py

# Opción 2: Dashboard visual
streamlit run tests/monitoring_dashboard.py

# Opción 3: Tests automatizados
python tests/test_scenarios.py all
```

### 3. Ver Resultados

- **Terminal**: Resultados en consola con colores
- **LangSmith**: https://smith.langchain.com
- **Archivos**: `test_results*.json`

---

## 📋 Workflows Recomendados

### Development Workflow

```bash
# Morning: Verificar que todo funciona
python tests/test_langsmith_verification.py

# Durante desarrollo: Chat interactivo
python tests/test_chat_interactive.py

# Monitoreo continuo: Dashboard
streamlit run tests/monitoring_dashboard.py

# Before commit: Tests automatizados
python tests/test_scenarios.py tag <feature>
```

### Testing de WhatsApp

1. **Test en web primero**:
   ```bash
   python tests/test_chat_interactive.py
   ```

2. **Verifica en LangSmith**: Revisa trazas y comportamiento

3. **Test en WhatsApp**: Envía mensajes reales

4. **Compara**: Comportamiento debe ser idéntico (mismo backend)

---

## 🔗 Integración con LangSmith

Todas las herramientas están integradas con LangSmith para tracing automático:

- ✅ **Cada conversación** genera una traza
- ✅ **Decisiones de agentes** quedan registradas
- ✅ **Tiempos de ejecución** medidos automáticamente
- ✅ **Errores** capturados con stack traces
- ✅ **Metadata** de contexto incluida

**Ver trazas**:
- URL: https://smith.langchain.com
- Proyecto: Configurado en `LANGSMITH_PROJECT`
- Filtrar por: fecha, agente, estado, session_id

---

## 📊 Métricas Clave

| Métrica | Objetivo | Crítico |
|---------|----------|---------|
| Success Rate | >95% | >90% |
| Avg Latency | <2s | <5s |
| P95 Latency | <5s | <10s |
| Error Rate | <5% | <10% |
| Agent Accuracy | >90% | >80% |

---

## 🐛 Troubleshooting

### LangSmith no muestra trazas

```bash
# Verifica configuración
python tests/test_langsmith_verification.py

# Revisa .env
cat .env | grep LANGSMITH

# Debe tener:
# LANGSMITH_API_KEY=lsv2_pt_...
# LANGSMITH_TRACING_ENABLED=true
```

### Dashboard no carga

```bash
# Verifica servicios
brew services list | grep postgresql  # PostgreSQL debe estar running
curl http://localhost:11434/api/tags  # Ollama debe responder

# Reinstala dependencias
uv add streamlit plotly pandas rich
```

### Escenarios fallan

```bash
# Test manual
python tests/test_chat_interactive.py
# Envía los mismos mensajes del escenario

# Revisa traza en LangSmith
# Identifica qué agente se usó y por qué
```

---

## 📚 Documentación Adicional

- **Guía Completa**: `../docs/TESTING_GUIDE.md`
- **Quick Start**: `../QUICKSTART_TESTING.md`
- **LangSmith Docs**: https://docs.smith.langchain.com
- **Streamlit Docs**: https://docs.streamlit.io

---

## 🎯 Mejores Prácticas

### Testing Regular

- ✅ **Diario**: Verificación rápida con chat interactivo
- ✅ **Semanal**: Suite completa de tests automatizados
- ✅ **Mensual**: Revisión profunda de métricas en LangSmith
- ✅ **Continuo**: Dashboard abierto durante desarrollo

### Organización

- ✅ Crear escenarios para cada nuevo feature
- ✅ Mantener tests actualizados
- ✅ Documentar casos edge descubiertos
- ✅ Revisar métricas regularmente

### Monitoreo

- ✅ Configurar alertas para error rate >5%
- ✅ Revisar trazas de conversaciones problemáticas
- ✅ Analizar patrones de uso de agentes
- ✅ Optimizar componentes lentos

---

## 🆘 Soporte

Si tienes problemas:

1. **Revisar logs**: Consola tiene información detallada
2. **LangSmith**: Ver trazas completas con errores
3. **Documentación**: `docs/TESTING_GUIDE.md`
4. **GitHub Issues**: Reportar bugs

---

### Para ejecutar el test:

```bash
poetry run pytest tests/test_phone_normalizer_pydantic.py -v
```

---

**Happy Testing! 🎉**