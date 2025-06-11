# 🤖 Integración LangGraph Multi-Agente para WhatsApp

Esta documentación explica cómo se integra el sistema multi-agente LangGraph con el flujo de conversación de WhatsApp existente.

## 📋 Arquitectura de Integración

### Flujo de Mensajes WhatsApp

```
WhatsApp → Webhook → Router de Servicios → LangGraph/Traditional → Respuesta
```

### Componentes Principales

1. **Webhook Handler** (`app/api/routes/webhook.py`)
   - Recibe mensajes de WhatsApp
   - Selecciona el servicio apropiado (LangGraph vs Traditional)
   - Maneja fallbacks automáticos

2. **LangGraph Service** (`app/services/langgraph_chatbot_service.py`)
   - Servicio principal que orquesta el sistema multi-agente
   - Compatibilidad con el sistema existente
   - Manejo de errores y fallbacks

3. **Configuration System** (`app/config/langgraph_config.py`)
   - Configuración centralizada
   - Validación de configuración
   - Gestión de entornos

## 🚀 Cómo Funciona la Integración

### 1. Recepción del Mensaje

Cuando llega un mensaje por WhatsApp:

```python
# En webhook.py
@router.post("/webhook/")
async def process_webhook(request: WhatsAppWebhookRequest):
    # 1. Verificar si es actualización de estado
    if is_status_update(request):
        return {"status": "ok"}
    
    # 2. Extraer mensaje y contacto
    message = request.get_message()
    contact = request.get_contact()
    
    # 3. Obtener servicio apropiado
    service = await _get_chatbot_service()
    
    # 4. Procesar mensaje
    result = await service.procesar_mensaje(message, contact)
    
    return {"status": "ok", "result": result}
```

### 2. Selección de Servicio

La variable de entorno `USE_LANGGRAPH` determina qué servicio usar:

```python
# Configuración
USE_LANGGRAPH = os.getenv("USE_LANGGRAPH", "true").lower() == "true"

async def _get_chatbot_service():
    if USE_LANGGRAPH:
        # Usar sistema multi-agente LangGraph
        if _langgraph_service is None:
            _langgraph_service = LangGraphChatbotService()
            await _langgraph_service.initialize()
        return _langgraph_service
    else:
        # Usar servicio tradicional
        return ChatbotService()
```

### 3. Procesamiento Multi-Agente

El servicio LangGraph procesa el mensaje:

```python
# En langgraph_chatbot_service.py
async def procesar_mensaje(self, message: WhatsAppMessage, contact: Contact):
    # 1. Extraer datos
    user_number = contact.wa_id
    message_text = self._extract_message_text(message)
    
    # 2. Verificar base de datos
    db_available = await self._check_database_health()
    
    # 3. Obtener/crear cliente
    customer = await self._safe_get_or_create_customer(user_number, contact.profile.get("name"))
    
    # 4. Procesar con LangGraph
    response_data = await self._process_with_langgraph(
        message_text=message_text,
        user_number=user_number,
        customer=customer,
        session_id=session_id
    )
    
    # 5. Enviar respuesta por WhatsApp
    await self._send_whatsapp_response(user_number, bot_response)
    
    return BotResponse(status="success", message=bot_response)
```

### 4. Integración con Agentes Especializados

El sistema LangGraph dirige el mensaje al agente apropiado:

```
Mensaje → Supervisor → Router → Agente Especializado → Respuesta
```

**Agentes Disponibles:**
- 🏷️ **Category Agent**: Navegación de categorías
- 📱 **Product Agent**: Consultas de productos y stock
- 🎯 **Promotions Agent**: Ofertas y descuentos
- 📦 **Tracking Agent**: Seguimiento de pedidos
- 🛠️ **Support Agent**: Soporte técnico y FAQ
- 🧾 **Invoice Agent**: Facturación y pagos

## ⚙️ Configuración

### Variables de Entorno

```bash
# Activar sistema LangGraph
USE_LANGGRAPH=true

# Base de datos
DATABASE_URL=postgresql://...

# WhatsApp
WHATSAPP_ACCESS_TOKEN=your_token
WHATSAPP_VERIFY_TOKEN=your_verify_token

# Ollama (opcional)
OLLAMA_API_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# Redis (opcional)
REDIS_URL=redis://localhost:6379

# ChromaDB (opcional)
CHROMADB_PATH=./data/chromadb

# Seguridad (recomendado)
JWT_SECRET=your-secret-key
ENCRYPTION_KEY=your-encryption-key
```

### Configuración Avanzada

El archivo `app/config/langgraph_config.py` permite configuración detallada:

```python
config = get_langgraph_config()

# Configurar agentes
config.update_config({
    "agents": {
        "product_agent": {
            "max_products_shown": 10,
            "show_stock": True
        }
    }
})
```

## 🔄 Fallbacks y Compatibilidad

### Fallback Automático

Si el sistema LangGraph falla, automáticamente usa el servicio tradicional:

```python
try:
    await _langgraph_service.initialize()
except Exception as e:
    logger.error(f"LangGraph failed: {e}")
    # Fallback automático
    return ChatbotService()
```

### Compatibilidad de Datos

El sistema mantiene compatibilidad con:
- ✅ Base de datos existente
- ✅ Conversaciones en Redis
- ✅ Modelos de datos actuales
- ✅ API de WhatsApp existente

## 📊 Monitoreo y Observabilidad

### Health Checks

```bash
# Verificar estado del sistema
GET /webhook/health

# Respuesta
{
  "service_type": "langgraph",
  "status": "healthy",
  "details": {
    "overall_status": "healthy",
    "components": {
      "langgraph": {...},
      "monitoring": {...},
      "security": {...}
    }
  }
}
```

### Historial de Conversaciones

```bash
# Obtener historial con LangGraph
GET /webhook/conversation/5491234567890

# Respuesta
{
  "success": true,
  "conversation_id": "conv_5491234567890",
  "messages": [...],
  "total_messages": 15
}
```

### Métricas Disponibles

- 📈 Tiempo de respuesta por agente
- 🎯 Tasa de éxito por intención
- 👥 Sesiones activas
- ⚡ Performance de componentes
- 🛡️ Eventos de seguridad

## 🚀 Inicialización del Sistema

### Script de Inicialización

```bash
# Ejecutar script de inicialización
python app/scripts/init_langgraph_system.py
```

El script verificará:
- ✅ Variables de entorno
- ✅ Conexión a base de datos
- ✅ Conexión a Ollama
- ✅ Configuración de ChromaDB
- ✅ Inicialización del sistema
- ✅ Conversación de prueba

### Inicio Manual

```python
from app.services.langgraph_chatbot_service import LangGraphChatbotService

# Crear e inicializar servicio
async with LangGraphChatbotService() as service:
    # El servicio está listo para usar
    result = await service.procesar_mensaje(message, contact)
```

## 🔧 Desarrollo y Testing

### Cambiar Entre Servicios

```bash
# Cambiar a LangGraph (desarrollo)
POST /webhook/switch-service
{
  "enable_langgraph": true
}

# Cambiar a tradicional
POST /webhook/switch-service
{
  "enable_langgraph": false
}
```

### Testing Local

```python
# Test básico
from app.services.langgraph_chatbot_service import LangGraphChatbotService

service = LangGraphChatbotService()
await service.initialize()

# Verificar health
health = await service.get_system_health()
print(health["overall_status"])  # "healthy"
```

## 📚 Estructura de Archivos

```
app/
├── agents/langgraph_system/          # Sistema multi-agente
│   ├── agents/                       # Agentes especializados
│   ├── integrations/                 # Integraciones (Ollama, ChromaDB, PostgreSQL)
│   ├── monitoring/                   # Monitoreo y seguridad
│   ├── models.py                     # Modelos de estado
│   ├── router.py                     # Sistema de routing
│   └── graph.py                      # Graph principal
├── api/routes/webhook.py             # Webhook integrado
├── services/
│   ├── langgraph_chatbot_service.py  # Servicio principal
│   └── chatbot_service.py            # Servicio tradicional
├── config/
│   └── langgraph_config.py           # Configuración
└── scripts/
    └── init_langgraph_system.py      # Script de inicialización
```

## 🔒 Seguridad

### Características Implementadas

- 🔐 JWT para autenticación
- 🛡️ RBAC (Role-Based Access Control)
- 🔒 Cifrado de datos sensibles
- 📝 Logs de auditoría
- ⚡ Rate limiting
- 🚫 Sanitización de entrada

### Configuración de Seguridad

```python
# Configuración de roles
"rbac": {
    "enabled": True,
    "default_role": "customer",
    "admin_users": ["admin@company.com"]
}

# Configuración de rate limiting
"rate_limiting": {
    "enabled": True,
    "requests_per_minute": 30,
    "requests_per_hour": 500
}
```

## 🚨 Troubleshooting

### Problemas Comunes

1. **LangGraph no se inicializa**
   ```bash
   # Verificar logs
   tail -f logs/langgraph.log
   
   # Verificar configuración
   python -c "from app.config.langgraph_config import get_langgraph_config; print(get_langgraph_config().validate_config())"
   ```

2. **Ollama no conecta**
   ```bash
   # Verificar servicio Ollama
   curl http://localhost:11434/api/tags
   
   # Verificar modelos
   ollama list
   ```

3. **Base de datos no disponible**
   ```bash
   # Verificar conexión
   python -c "from app.database import check_db_connection; import asyncio; print(asyncio.run(check_db_connection()))"
   ```

### Logs Importantes

```bash
# Logs del sistema LangGraph
tail -f logs/langgraph.log

# Logs de la aplicación
tail -f logs/app.log

# Logs de FastAPI
uvicorn app.main:app --log-level info
```

## 📈 Performance

### Objetivos de Performance

- ⚡ **Tiempo de respuesta**: < 3 segundos
- 🎯 **Disponibilidad**: > 99.5%
- 📊 **Throughput**: > 100 requests/segundo
- 💾 **Uso de memoria**: < 2GB por instancia

### Optimizaciones Implementadas

- 🔄 Lazy loading de agentes
- 💾 Cache de vectores
- 🏊 Pool de conexiones
- ⚡ Procesamiento asíncrono
- 📦 Checkpointing eficiente

## 🔄 Migración

### Desde Sistema Tradicional

1. **Fase 1**: Instalación paralela
   ```bash
   USE_LANGGRAPH=false  # Continuar con tradicional
   ```

2. **Fase 2**: Testing gradual
   ```bash
   USE_LANGGRAPH=true   # Activar LangGraph con fallback
   ```

3. **Fase 3**: Migración completa
   ```bash
   # Monitorear métricas
   GET /webhook/health
   ```

### Rollback

```bash
# Rollback inmediato
POST /webhook/switch-service
{
  "enable_langgraph": false
}

# O variable de entorno
USE_LANGGRAPH=false
```

## 🤝 Contribución

Para contribuir al sistema:

1. Crear nuevos agentes en `app/agents/langgraph_system/agents/`
2. Añadir integraciones en `app/agents/langgraph_system/integrations/`
3. Actualizar configuración en `app/config/langgraph_config.py`
4. Ejecutar tests con `python app/scripts/init_langgraph_system.py`

---

**🎯 Resultado**: Un sistema de chatbot híbrido que mantiene compatibilidad completa con el flujo existente mientras añade capacidades avanzadas de IA multi-agente.