# 🧪 Guía de Pruebas del Sistema LangGraph

Esta guía explica cómo usar los scripts de prueba para verificar el funcionamiento completo del sistema multi-agente LangGraph sin necesidad de WhatsApp.

## 📋 Scripts de Prueba Disponibles

### 1. `test_chatbot_direct.py` - Pruebas Directas del Chatbot

**Propósito**: Probar el servicio de chatbot directamente sin WhatsApp
**Ubicación**: `app/scripts/test_chatbot_direct.py`

#### Características:
- 🗣️ **Conversación Interactiva**: Chatea directamente con el bot
- 🎭 **Conversaciones Predefinidas**: Tests automáticos con escenarios específicos
- ⚡ **Tests de Performance**: Medición de tiempos de respuesta
- 🔍 **Comparación de Servicios**: LangGraph vs Traditional
- 💾 **Logs Detallados**: Guarda resultados en JSON

#### Cómo usar:

```bash
# Ejecutar directamente
python app/scripts/test_chatbot_direct.py

# O como ejecutable
./app/scripts/test_chatbot_direct.py
```

#### Menú de opciones:
1. **Conversación interactiva** - Chatea en tiempo real
2. **Test con conversación predefinida** - Ejecuta escenarios automáticos
3. **Test de performance** - Ejecuta múltiples conversaciones y mide performance
4. **Comparar servicios** - Compara LangGraph vs Traditional

#### Conversaciones predefinidas disponibles:
- `saludo_basico` - Saludo simple y consulta básica
- `consulta_laptops` - Consulta específica sobre laptops gaming
- `consulta_componentes` - Consulta sobre componentes de PC
- `consulta_stock` - Verificación de stock
- `conversacion_compleja` - Flujo completo de consulta empresarial

### 2. `comprehensive_test_suite.py` - Suite Completa de Pruebas

**Propósito**: Verificar todo el flujo del sistema con logs detallados
**Ubicación**: `app/scripts/comprehensive_test_suite.py`

#### Características:
- 🔍 **14 Tests Integrales**: Desde configuración hasta integración completa
- 📊 **Verificación de Base de Datos**: Confirma que los datos se guardan correctamente
- 🧠 **Verificación Vectorial**: Testa ChromaDB y embeddings
- 🔄 **Verificación de Routing**: Confirma que los agentes correctos procesan cada mensaje
- 📝 **Logs Extremadamente Detallados**: Para identificar cualquier problema
- 📈 **Métricas de Performance**: Tiempos de respuesta y throughput
- 🛡️ **Tests de Manejo de Errores**: Verifica robustez del sistema

#### Cómo usar:

```bash
# Ejecutar suite completa
python app/scripts/comprehensive_test_suite.py

# O como ejecutable
./app/scripts/comprehensive_test_suite.py
```

#### Tests incluidos:

1. **Configuration Validation** - Verifica configuración del sistema
2. **Database Connectivity** - Prueba conexión y operaciones de BD
3. **Ollama Integration** - Verifica LLM y embeddings
4. **ChromaDB Integration** - Prueba almacenamiento vectorial
5. **PostgreSQL Integration** - Verifica checkpointing de LangGraph
6. **LangGraph Service Initialization** - Inicialización del sistema multi-agente
7. **Vector Storage and Retrieval** - Operaciones vectoriales completas
8. **Database Operations** - CRUD completo en base de datos
9. **Message Processing Flow** - Procesamiento de mensajes end-to-end
10. **Agent Routing** - Verificación de routing correcto
11. **Conversation Persistence** - Persistencia en BD y checkpoints
12. **Error Handling** - Manejo robusto de errores
13. **Performance Metrics** - Métricas de rendimiento
14. **Integration End-to-End** - Flujo completo de conversación

## 🚀 Cómo Ejecutar las Pruebas

### Preparación del Entorno

1. **Asegurar dependencias**:
```bash
# Verificar que el entorno virtual está activado
source venv/bin/activate  # o activate en Windows

# Instalar dependencias si es necesario
pip install -r requirements.txt
```

2. **Configurar variables de entorno**:
```bash
# Variables críticas
export USE_LANGGRAPH=true
export DATABASE_URL="postgresql://..."
export WHATSAPP_ACCESS_TOKEN="..."
export WHATSAPP_VERIFY_TOKEN="..."

# Variables opcionales para funcionalidad completa
export OLLAMA_API_URL="http://localhost:11434"
export REDIS_URL="redis://localhost:6379"
export CHROMADB_PATH="./data/chromadb"
```

3. **Inicializar sistema** (opcional pero recomendado):
```bash
python app/scripts/init_langgraph_system.py
```

### Ejecución Paso a Paso

#### Para Pruebas Rápidas (5-10 minutos):
```bash
# 1. Test interactivo rápido
python app/scripts/test_chatbot_direct.py
# Seleccionar opción 1: Conversación interactiva
# Escribir algunos mensajes de prueba

# 2. Test predefinido
python app/scripts/test_chatbot_direct.py
# Seleccionar opción 2: Test con conversación predefinida
# Elegir "saludo_basico" o "consulta_laptops"
```

#### Para Pruebas Completas (20-30 minutos):
```bash
# 1. Suite completa
python app/scripts/comprehensive_test_suite.py
# Responder "y" para confirmar

# 2. Comparación de servicios
python app/scripts/test_chatbot_direct.py
# Seleccionar opción 4: Comparar servicios
```

## 📊 Interpretación de Resultados

### Logs y Archivos Generados

#### `test_chatbot_direct.py` genera:
- `conversation_test_[service]_[timestamp].json` - Log de conversación individual
- `performance_test_[service]_[timestamp].json` - Resultados de performance
- `service_comparison_[timestamp].json` - Comparación entre servicios

#### `comprehensive_test_suite.py` genera:
- `comprehensive_test_[timestamp].log` - Log detallado de todas las pruebas
- `comprehensive_test_report_[timestamp].json` - Reporte completo con métricas

### Métricas Importantes a Verificar

#### ✅ **Indicadores de Éxito**:
- **Tasa de éxito**: > 95%
- **Tiempo de respuesta promedio**: < 3 segundos
- **Todos los componentes**: "healthy" o "degraded" (no "unhealthy")
- **Base de datos**: Mensajes se guardan correctamente
- **Vectores**: Búsquedas devuelven resultados relevantes
- **Routing**: Mensajes se dirigen a agentes correctos

#### ⚠️ **Señales de Alerta**:
- **Tasa de éxito**: < 90%
- **Tiempo de respuesta**: > 5 segundos
- **Componentes**: Estado "unhealthy"
- **Errores frecuentes**: En logs de aplicación
- **Respuestas vacías**: O muy cortas consistently

### Ejemplo de Interpretación

```json
{
  "test_summary": {
    "overall_success": true,
    "successful_tests": 13,
    "failed_tests": 1,
    "total_duration_seconds": 245.67
  }
}
```

**✅ Interpretación**: Sistema en buen estado, un test falló pero es aceptable.

```json
{
  "message_processing": {
    "success_rate": 100,
    "average_processing_time": 1.85,
    "average_response_length": 180
  }
}
```

**✅ Interpretación**: Procesamiento excelente, responde rápido y con contenido adecuado.

## 🔧 Debugging de Problemas

### Problemas Comunes y Soluciones

#### 1. **Error: "LangGraph system not initialized"**
```bash
# Verificar configuración
python -c "from app.config.langgraph_config import get_langgraph_config; print(get_langgraph_config().validate_config())"

# Ejecutar inicialización
python app/scripts/init_langgraph_system.py
```

#### 2. **Error: "Database connection failed"**
```bash
# Verificar base de datos
python -c "from app.database import check_db_connection; import asyncio; print(asyncio.run(check_db_connection()))"

# Verificar variable de entorno
echo $DATABASE_URL
```

#### 3. **Error: "Ollama connection error"**
```bash
# Verificar servicio Ollama
curl http://localhost:11434/api/tags

# Iniciar Ollama si no está corriendo
ollama serve

# Descargar modelo si es necesario
ollama pull llama3.1:8b
```

#### 4. **Error: "ChromaDB setup error"**
```bash
# Verificar directorio de ChromaDB
ls -la ./data/chromadb/

# Recrear directorio si es necesario
rm -rf ./data/chromadb/
mkdir -p ./data/chromadb/
```

#### 5. **Respuestas lentas (> 5 segundos)**
- Verificar carga de CPU/memoria
- Revisar logs de Ollama para cuellos de botella
- Considerar usar modelo más pequeño temporalmente

#### 6. **Routing incorrecto de agentes**
- Verificar configuración de agentes en `langgraph_config.py`
- Revisar logs de router para ver detección de intent
- Probar con mensajes más específicos

### Logs Detallados para Debugging

#### Ver logs en tiempo real:
```bash
# Durante las pruebas
tail -f comprehensive_test_[timestamp].log

# Logs de la aplicación
tail -f logs/app.log

# Si usas systemd para servicios
journalctl -f -u your-app-service
```

#### Analizar logs después de las pruebas:
```bash
# Buscar errores
grep -i "error\|exception\|failed" comprehensive_test_*.log

# Buscar warnings
grep -i "warning\|warn" comprehensive_test_*.log

# Ver métricas de performance
grep -i "processing_time\|response_time" comprehensive_test_*.log
```

## 📈 Métricas de Performance Esperadas

### Benchmarks de Referencia

#### **Hardware Mínimo** (4 CPU, 8GB RAM):
- Tiempo de respuesta promedio: 2-4 segundos
- Throughput: 10-20 requests/minuto
- Memoria utilizada: < 2GB

#### **Hardware Recomendado** (8 CPU, 16GB RAM):
- Tiempo de respuesta promedio: 1-2 segundos
- Throughput: 30-60 requests/minuto
- Memoria utilizada: < 4GB

#### **Hardware Alto** (16+ CPU, 32GB+ RAM):
- Tiempo de respuesta promedio: < 1 segundo
- Throughput: 100+ requests/minuto
- Memoria utilizada: < 8GB

### Factores que Afectan Performance

1. **Modelo de Ollama**: Modelos más grandes = más lentos pero mejor calidad
2. **Tamaño de ChromaDB**: Más documentos = búsquedas más lentas
3. **Complejidad de consultas**: Consultas multi-agente toman más tiempo
4. **Estado de la base de datos**: BD fragmentada puede ser más lenta
5. **Carga de red**: Latencia en conexiones a servicios externos

## 🎯 Casos de Uso de las Pruebas

### Durante Desarrollo
```bash
# Desarrollo rápido - verificar cambios
python app/scripts/test_chatbot_direct.py
# Opción 1: Conversación interactiva
```

### Antes de Deploy
```bash
# Test completo antes de subir a producción
python app/scripts/comprehensive_test_suite.py
```

### Monitoring en Producción
```bash
# Verificación rápida del sistema
python app/scripts/test_chatbot_direct.py
# Opción 2: Test predefinido con "saludo_basico"
```

### Debugging de Problemas
```bash
# Test específico del componente problemático
python app/scripts/comprehensive_test_suite.py
# Revisar logs detallados para el componente específico
```

### Comparación de Performance
```bash
# Antes y después de optimizaciones
python app/scripts/test_chatbot_direct.py
# Opción 3: Test de performance
```

## 📚 Recursos Adicionales

- **Configuración**: `app/config/langgraph_config.py`
- **Integración WhatsApp**: `LANGGRAPH_INTEGRATION.md`
- **Inicialización**: `app/scripts/init_langgraph_system.py`
- **Logs de aplicación**: `logs/` directory
- **Health checks**: `GET /webhook/health`

---

**🎯 Objetivo**: Estas pruebas te permiten verificar completamente el funcionamiento del sistema LangGraph multi-agente, identificar problemas antes de producción, y mantener la calidad del servicio sin depender de WhatsApp para testing.