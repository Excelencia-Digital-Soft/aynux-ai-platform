# 🧪 Guía de Interfaces de Testing - Aynux

Esta guía documenta las tres interfaces de testing disponibles para probar el sistema multi-dominio de Aynux.

## 📋 Tabla de Contenidos

- [Resumen de Interfaces](#resumen-de-interfaces)
- [1. Interfaz Web de Chat](#1-interfaz-web-de-chat)
- [2. Simulador de WhatsApp](#2-simulador-de-whatsapp)
- [3. CLI Interactivo](#3-cli-interactivo)
- [Comparación de Interfaces](#comparación-de-interfaces)
- [Casos de Uso Recomendados](#casos-de-uso-recomendados)

---

## Resumen de Interfaces

Aynux proporciona **tres interfaces** para testing y desarrollo, cada una optimizada para diferentes casos de uso:

| Interfaz | Archivo | Uso Principal | Ventajas |
|----------|---------|--------------|----------|
| **Web Chat** | `http://localhost:8000/` | Testing visual e interactivo | UI moderna, streaming, debugging |
| **WhatsApp Sim** | `tests/test_whatsapp_simulator.py` | Testing de webhooks | Simula payloads reales, multi-dominio |
| **CLI Interactive** | `tests/test_chat_interactive.py` | Testing rápido de terminal | Rapidez, sin navegador, scripting |

---

## 1. Interfaz Web de Chat

### 🎯 Descripción

Interfaz web moderna con diseño responsive que simula una aplicación de chat. Ideal para testing visual y demostraciones.

### 🚀 Cómo Usarla

1. **Iniciar el servidor**:
   ```bash
   uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Abrir en el navegador**:
   ```
   http://localhost:8000/
   ```

3. **Características disponibles**:
   - Selector de dominio (auto, e-commerce, hospital, crédito)
   - Streaming en tiempo real (activable en panel debug)
   - Botones de acción rápida
   - Panel de debug con metadatos
   - Exportación de conversaciones a JSON
   - Historial persistente por sesión

### 🎨 Funcionalidades

#### Selección de Dominio
```javascript
// Cambiar dominio manualmente
Selector: Auto-Detectar | E-commerce | Hospital | Crédito
```

#### Modo Streaming
- Toggle en panel de debug
- Visualización de progreso en tiempo real
- Eventos: `thinking`, `processing`, `generating`, `complete`

#### Panel de Debug
Muestra información técnica en tiempo real:
- Session ID y User ID
- Dominio actual
- Agente utilizado
- Tiempo de procesamiento
- Metadatos completos en JSON

#### Exportar Chat
```json
{
  "session_id": "session_2025-01-16_abc123",
  "user_id": "web_xyz789",
  "domain": "ecommerce",
  "exported_at": "2025-01-16T10:30:00Z",
  "message_count": 15,
  "messages": [...]
}
```

### 📱 Responsive Design

La interfaz es completamente responsive:
- **Desktop**: Panel de debug lateral
- **Mobile**: Panel de debug fullscreen overlay
- **Tablet**: Diseño adaptativo

### 🔧 Configuración Avanzada

#### LocalStorage
```javascript
// User ID persistente
localStorage.getItem('aynux_user_id')

// Session management
window.aynuxChat.refreshSession()
```

#### API Endpoints Utilizados
- `POST /api/v1/chat/message` - Mensajes normales
- `POST /api/v1/chat/message/stream` - Mensajes con streaming
- `GET /api/v1/chat/history` - Historial de conversación
- `GET /api/v1/chat/health` - Estado del servicio

---

## 2. Simulador de WhatsApp

### 🎯 Descripción

Simula webhooks de WhatsApp generando payloads válidos y enviándolos al endpoint `/api/v1/webhook/`. Ideal para testing de integración WhatsApp y detección de dominios.

### 🚀 Cómo Usarlo

#### Modo Interactivo
```bash
python tests/test_whatsapp_simulator.py
```

#### Modo Comando Único
```bash
# Enviar un mensaje
python tests/test_whatsapp_simulator.py --message "¿Qué laptops tienen?"

# Ejecutar escenario predefinido
python tests/test_whatsapp_simulator.py --scenario 1

# Cambiar servidor
python tests/test_whatsapp_simulator.py --url http://production-server.com
```

### 📋 Escenarios Predefinidos

#### 1. Consulta de Productos (E-commerce)
```
WA ID: 5491112345678
Mensaje: "¿Qué laptops tienen disponibles?"
```

#### 2. Tracking de Pedido
```
WA ID: 5491112345678
Mensajes: ["Hola", "¿Dónde está mi pedido #12345?"]
```

#### 3. Soporte Técnico
```
WA ID: 5491112345678
Mensajes: ["Mi producto llegó dañado", "¿Qué puedo hacer?"]
```

#### 4. Consulta de Factura
```
WA ID: 5491112345678
Mensaje: "¿Puedo ver mi última factura?"
```

#### 5. Consulta Médica (Hospital)
```
WA ID: 5491187654321
Mensaje: "Necesito agendar una cita con el Dr. García"
```

#### 6. Estado de Cuenta (Crédito)
```
WA ID: 5491198765432
Mensajes: ["¿Cuál es mi saldo pendiente?", "¿Cuándo vence mi cuota?"]
```

#### 7. Conversación Multi-turno
```
WA ID: 5491112345678
Mensajes: ["Hola", "¿Qué productos tienen?", "Busco una laptop", "¿Cuál es la más barata?", "Gracias, adiós"]
```

#### 8. Test de Dominios Mixtos
```
WA ID: 5491112345678
Mensajes: ["¿Tienen laptops?", "¿Cuándo puedo ver al doctor?", "¿Cuál es mi deuda?"]
```

### 🔍 Comandos del Modo Interactivo

```bash
WhatsApp > ¿Qué productos tienen?       # Enviar mensaje
WhatsApp > /scenarios                    # Ver escenarios
WhatsApp > /run 1                        # Ejecutar escenario 1
WhatsApp > /user 5491187654321 Dr Garcia # Cambiar usuario
WhatsApp > /payload                      # Ver payload generado
WhatsApp > /quit                         # Salir
```

### 📦 Estructura del Payload Generado

```json
{
  "object": "whatsapp_business_account",
  "entry": [{
    "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
    "changes": [{
      "value": {
        "messaging_product": "whatsapp",
        "metadata": {
          "display_phone_number": "15551234567",
          "phone_number_id": "PHONE_NUMBER_ID"
        },
        "contacts": [{
          "profile": {"name": "Test User"},
          "wa_id": "5491112345678"
        }],
        "messages": [{
          "from": "5491112345678",
          "id": "wamid.abc123...",
          "timestamp": "1705401600",
          "type": "text",
          "text": {"body": "¿Qué laptops tienen?"}
        }]
      },
      "field": "messages"
    }]
  }]
}
```

### 🎭 Testing Multi-Dominio

El simulador permite probar la detección automática de dominio:

```python
# E-commerce: WA ID argentinos con prefijo 549
WA ID: 5491112345678 → Detecta: ecommerce

# Hospital: WA ID específicos registrados
WA ID: 5491187654321 → Detecta: hospital

# Crédito: WA ID específicos registrados
WA ID: 5491198765432 → Detecta: credit
```

---

## 3. CLI Interactivo

### 🎯 Descripción

Interfaz de línea de comandos con Rich UI para testing rápido sin navegador. Incluye integración con LangSmith para tracing.

### 🚀 Cómo Usarlo

```bash
python tests/test_chat_interactive.py
```

### 📋 Funcionalidades

#### Comandos Disponibles
```bash
> Hola, ¿qué productos tienen?          # Mensaje normal
> /stream ¿Dónde está mi pedido?        # Mensaje con streaming
> /scenarios                             # Ver escenarios predefinidos
> /run 3                                 # Ejecutar escenario 3
> /history                               # Ver historial de conversación
> /traces                                # Ver trazas en LangSmith
> /stats                                 # Estadísticas de sesión
> /clear                                 # Limpiar sesión
> /help                                  # Ayuda
> /quit                                  # Salir
```

### 🎨 Características

#### Rich UI
- Paneles con bordes coloreados
- Tablas formateadas
- Indicadores de progreso
- Markdown rendering

#### LangSmith Integration
```python
# Ver trazas recientes
> /traces

# Output:
┏━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┓
┃ Nombre       ┃ Estado ┃ Latencia┃ ID     ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━┩
│ product_agent│ ✅ OK  │ 1.25s   │ abc... │
└──────────────┴────────┴─────────┴────────┘
```

#### Metadatos Detallados
```
┏━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Campo                 ┃ Valor        ┃
┡━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ Agente Usado          │ product_agent│
│ Tiempo de Procesamiento│ 1234ms      │
│ Requiere Humano       │ False        │
│ Conversación Completa │ False        │
│ Session ID            │ test_sess... │
│ Mensaje #             │ 5            │
└───────────────────────┴──────────────┘
```

### 🔧 Escenarios Predefinidos

Similar a los del simulador de WhatsApp, pero optimizados para chat directo:

1. Consulta de productos
2. Tracking de pedido
3. Soporte técnico
4. Consulta de factura
5. Consulta de crédito
6. Saludo
7. Despedida
8. Conversación multi-turno

---

## Comparación de Interfaces

### ⚡ Velocidad de Ejecución

| Interfaz | Startup | Por Mensaje | Mejor Para |
|----------|---------|-------------|------------|
| CLI | 2-3s | <50ms overhead | Testing rápido, CI/CD |
| Web Chat | Navegador | ~100ms overhead | UI/UX testing |
| WhatsApp Sim | 2-3s | ~50ms overhead | Integration testing |

### 🎯 Casos de Uso

#### CLI Interactivo
✅ **Mejor para:**
- Development rápido
- Testing de lógica de agentes
- Debugging de prompts
- CI/CD pipelines
- Terminal workflows

❌ **No recomendado para:**
- Testing de UI/UX
- Demostraciones a clientes
- Testing de diseño responsive

#### Web Chat
✅ **Mejor para:**
- Demostraciones visuales
- Testing de UI/UX
- Presentaciones a stakeholders
- Testing de diseño responsive
- User acceptance testing

❌ **No recomendado para:**
- CI/CD pipelines
- Testing automatizado masivo
- Headless testing

#### WhatsApp Simulator
✅ **Mejor para:**
- Testing de integración WhatsApp
- Validación de webhooks
- Testing multi-dominio
- Escenarios de producción
- Load testing (con modificaciones)

❌ **No recomendado para:**
- Testing rápido de prompts
- UI development
- Demostraciones visuales

---

## Casos de Uso Recomendados

### 🏗️ Durante Desarrollo

```bash
# 1. Testear cambio en prompt del producto_agent
python tests/test_chat_interactive.py
> ¿Qué laptops tienen?

# 2. Verificar cambio en UI
Abrir: http://localhost:8000/

# 3. Validar webhook de WhatsApp
python tests/test_whatsapp_simulator.py --scenario 1
```

### 🧪 Testing de Regresión

```bash
# Ejecutar todos los escenarios de WhatsApp
for i in {1..8}; do
    python tests/test_whatsapp_simulator.py --scenario $i
done
```

### 🎨 Demo para Stakeholders

1. Abrir Web Chat: `http://localhost:8000/`
2. Activar panel de debug
3. Activar streaming
4. Demostrar cambio de dominios
5. Exportar conversación

### 🔍 Debugging de Problemas

```bash
# 1. Reproducir issue en CLI con tracing
python tests/test_chat_interactive.py
> /traces  # Ver trazas en LangSmith

# 2. Verificar payload de WhatsApp
python tests/test_whatsapp_simulator.py
> /payload

# 3. Inspeccionar en Web Chat con debug panel
http://localhost:8000/ → Toggle Debug
```

---

## 🚀 Quick Start Completo

### 1. Iniciar Servidor
```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Testing Rápido (CLI)
```bash
python tests/test_chat_interactive.py
```

### 3. Testing Visual (Web)
```
http://localhost:8000/
```

### 4. Testing WhatsApp (Simulator)
```bash
python tests/test_whatsapp_simulator.py --scenario 1
```

---

## 📊 Matriz de Decisión

**¿Qué interfaz usar?**

```
┌─────────────────────────┬──────────┬──────────┬──────────────┐
│ Necesito...             │ CLI      │ Web      │ WhatsApp Sim │
├─────────────────────────┼──────────┼──────────┼──────────────┤
│ Testear lógica de bot   │ ✅✅✅    │ ✅       │ ✅           │
│ Ver UI/diseño           │ ❌       │ ✅✅✅    │ ❌           │
│ Validar webhooks        │ ❌       │ ❌       │ ✅✅✅        │
│ Testing rápido          │ ✅✅✅    │ ✅       │ ✅           │
│ Demo a clientes         │ ❌       │ ✅✅✅    │ ✅           │
│ Testing multi-dominio   │ ✅       │ ✅       │ ✅✅✅        │
│ Debugging con traces    │ ✅✅✅    │ ✅       │ ✅           │
│ CI/CD automation        │ ✅✅✅    │ ❌       │ ✅           │
└─────────────────────────┴──────────┴──────────┴──────────────┘

Leyenda: ❌ No soportado | ✅ Soportado | ✅✅✅ Óptimo
```

---

## 🔧 Troubleshooting

### Web Chat no carga

```bash
# Verificar servidor
curl http://localhost:8000/health

# Verificar archivos estáticos
ls -la app/static/

# Ver logs
tail -f logs/app.log
```

### WhatsApp Simulator no conecta

```bash
# Verificar endpoint
curl -X POST http://localhost:8000/api/v1/webhook/health

# Verificar payload
python tests/test_whatsapp_simulator.py
> /payload
```

### CLI sin respuesta

```bash
# Verificar LangGraph service
curl http://localhost:8000/api/v1/chat/health

# Ver trazas
python tests/test_chat_interactive.py
> /traces
```

---

## 📝 Notas Finales

- Todas las interfaces usan los **mismos endpoints** del backend
- El **estado de conversación** es independiente por interfaz (diferentes session_id)
- **LangSmith** funciona en todas las interfaces cuando está configurado
- Los **archivos estáticos** se sirven desde `app/static/`
- Las **rutas frontend** están en `app/api/routes/frontend.py`

---

## 🔗 Enlaces Relacionados

- [Testing Guide](TESTING_GUIDE.md)
- [LangGraph Documentation](LangGraph.md)
- [API Documentation](http://localhost:8000/api/v1/docs)
- [LangSmith Dashboard](https://smith.langchain.com/)

---

**¡Feliz Testing! 🎉**
