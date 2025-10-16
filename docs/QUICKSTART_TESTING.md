# 🚀 Quick Start: Testing Aynux Bot

Guía rápida para empezar a probar el bot en 5 minutos.

## ⚡ Setup Rápido (2 minutos)

### 1. Configura LangSmith

Agrega a tu `.env`:

```bash
LANGSMITH_API_KEY=tu_api_key_aqui  # Obtén en https://smith.langchain.com
LANGSMITH_PROJECT=aynux-production
LANGSMITH_TRACING_ENABLED=true
```

### 2. Instala Dependencias

```bash
uv add rich streamlit plotly pandas
```

### 3. Verifica Configuración

```bash
python tests/test_langsmith_verification.py
```

**Resultado Esperado**: ✅ Todas las verificaciones pasan

---

## 🎯 Opciones de Testing

Elige la herramienta según tu necesidad:

### Opción 1: Chat Interactivo en Terminal 💬

**Cuándo usar**: Pruebas rápidas, debugging, desarrollo

```bash
python tests/test_chat_interactive.py
```

**Características**:
- Chat en tiempo real
- Visualización de metadatos
- Escenarios predefinidos
- Links a LangSmith

**Comandos útiles**:
- Escribe tu mensaje normalmente
- `/scenarios` - Ver escenarios predefinidos
- `/run 1` - Ejecutar escenario #1
- `/traces` - Ver últimas trazas
- `/quit` - Salir

---

### Opción 2: Dashboard Visual de Monitoreo 📊

**Cuándo usar**: Monitoreo continuo, análisis de métricas, testing visual

```bash
streamlit run tests/monitoring_dashboard.py
```

Se abre en: http://localhost:8501

**Tabs disponibles**:
- 📊 **Dashboard**: Métricas en tiempo real
- 🔀 **Graph Viz**: Visualización del flujo de agentes
- 💬 **Test Chat**: Chat interactivo en el navegador
- 📖 **Docs**: Documentación completa

---

### Opción 3: Suite de Tests Automatizados 🤖

**Cuándo usar**: CI/CD, validación completa, regression testing

```bash
# Ver todos los escenarios
python tests/test_scenarios.py list

# Ejecutar todos
python tests/test_scenarios.py all

# Ejecutar uno específico
python tests/test_scenarios.py run product_query_simple

# Por categoría
python tests/test_scenarios.py tag products
```

**Resultados**:
- Resumen de éxito/fallo
- Métricas de performance
- Archivo JSON con detalles

---

## 🔗 Ver Trazas en LangSmith

1. Abre: https://smith.langchain.com
2. Selecciona tu proyecto (ej: `aynux-production`)
3. Ve las ejecuciones en tiempo real
4. Click en cualquier traza para ver detalles completos

**Qué verás**:
- Decisiones del Orchestrator
- Agente seleccionado y por qué
- Tiempo de cada componente
- Inputs/outputs de cada paso
- Errores completos (si los hay)

---

## 📋 Workflow Típico

### Para Desarrollo Diario:

1. **Morning Check** (1 min):
   ```bash
   python tests/test_langsmith_verification.py
   ```

2. **Testing Manual** (10-15 min):
   ```bash
   python tests/test_chat_interactive.py
   # Probar casos específicos
   ```

3. **Monitoreo Continuo** (background):
   ```bash
   streamlit run tests/monitoring_dashboard.py
   # Mantener abierto mientras desarrollas
   ```

4. **Before Commit** (5 min):
   ```bash
   python tests/test_scenarios.py tag <feature>
   # Validar que tu feature funciona
   ```

### Para Testing de WhatsApp:

El bot usa el **mismo backend** para WhatsApp y web chat:

1. **Test en Chat Web** primero:
   ```bash
   python tests/test_chat_interactive.py
   ```

2. **Verifica comportamiento** en LangSmith

3. **Prueba en WhatsApp** con confianza:
   - Envía mensaje real a tu número de WhatsApp
   - Observa la traza en LangSmith
   - Comportamiento debe ser idéntico

---

## 🐛 Problemas Comunes

### ❌ "LangSmith API key not found"

**Solución**:
```bash
# Verifica .env
cat .env | grep LANGSMITH_API_KEY

# Debe mostrar tu key real
# Si no, agrega:
LANGSMITH_API_KEY=lsv2_pt_xxxxxxxxx
```

### ❌ "Connection refused" al iniciar Dashboard

**Solución**:
```bash
# Verifica que PostgreSQL está corriendo
brew services list | grep postgresql

# Verifica que Ollama está activo
curl http://localhost:11434/api/tags
```

### ❌ Escenarios fallan con "agents_match = False"

**Solución**:
1. Prueba manualmente en chat interactivo
2. Ve la traza en LangSmith para entender qué agente se usó
3. Actualiza el escenario si el comportamiento es correcto

---

## 📚 Próximos Pasos

- 📖 Lee la [Guía Completa de Testing](docs/TESTING_GUIDE.md)
- 🔍 Explora trazas en LangSmith
- 🎯 Crea tus propios escenarios de prueba
- 📊 Configura alertas para métricas críticas

---

## 🆘 Ayuda

- Documentación completa: `docs/TESTING_GUIDE.md`
- LangSmith Docs: https://docs.smith.langchain.com
- Issues: Reporta bugs en GitHub

---

**¡Feliz Testing! 🎉**
