# Chattigo Integration Guide

Guía completa para integrar Chattigo como intermediario de WhatsApp Business API.

## Resumen

Chattigo actúa como intermediario entre Meta (WhatsApp Business API) y nuestra aplicación:

```
Usuario WhatsApp → Meta → Chattigo → Nuestro Webhook → Bot Response → Chattigo → Meta → Usuario
```

**Ventajas de usar Chattigo:**
- Chattigo maneja la verificación de webhooks con Meta
- No necesitamos implementar el challenge de verificación de Meta
- Gestión simplificada de números de WhatsApp Business

---

## 1. Autenticación

### Obtener Token de Acceso

```bash
curl -X POST "https://channels.chattigo.com/bsp-cloud-chattigo-isv/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "tu_usuario@dominio",
    "password": "tu_password"
  }'
```

**Respuesta exitosa:**
```json
{
  "access_token": "eyJhbGciOiJIUzUxMiJ9...",
  "user": "tu_usuario@dominio",
  "access": true
}
```

**Credenciales en Base de Datos:**

Las credenciales de Chattigo ahora se almacenan en la base de datos con encriptación.
Configure via Admin API:

```bash
# Crear credenciales para un DID
curl -X POST "http://localhost:8080/api/v1/admin/chattigo-credentials" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TU_JWT_TOKEN" \
  -d '{
    "did": "5492644710400",
    "name": "WhatsApp Principal",
    "username": "usuario@dominio",
    "password": "tu_password",
    "organization_id": "uuid-de-organizacion"
  }'
```

**Variables de entorno (solo configuración, NO credenciales):**
```bash
CHATTIGO_ENABLED=true
CHATTIGO_BASE_URL=https://channels.chattigo.com/bsp-cloud-chattigo-isv
```

---

## 2. Registrar Webhook

Una vez autenticado, registrar la URL del webhook donde Chattigo enviará los mensajes:

```python
import requests
import json

url = "https://channels.chattigo.com/bsp-cloud-chattigo-isv/webhooks/inbound"

payload = json.dumps({
    "waId": "5492644710400",  # Número de WhatsApp Business (con código país)
    "externalWebhook": "https://api.aynux.com.ar/api/v1/webhook"  # Tu webhook URL
})

headers = {
    'Authorization': 'Bearer TU_ACCESS_TOKEN',
    'Content-Type': 'application/json'
}

response = requests.request("PATCH", url, headers=headers, data=payload)
print(response.text)
```

**Importante:**
- `waId`: El número de WhatsApp Business SIN el `+` (ej: `5492644710400`)
- `externalWebhook`: URL pública HTTPS donde recibirás los mensajes

---

## 3. Estructura del Webhook

### Formato de Mensajes Entrantes

Chattigo reenvía los webhooks de Meta en formato estándar de WhatsApp Business API:

```json
{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "id": "1318067943193449",
      "changes": [
        {
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {
              "display_phone_number": "5492644710400",
              "phone_number_id": "734053143122597"
            },
            "contacts": [
              {
                "profile": { "name": "Nombre Usuario" },
                "wa_id": "5492644472542"
              }
            ],
            "messages": [
              {
                "from": "5492644472542",
                "id": "wamid.HBgNNTQ5MjY0NDQ3MjU0MhUCABI...",
                "timestamp": "1767030562",
                "text": { "body": "Hola" },
                "type": "text"
              }
            ]
          },
          "field": "messages"
        }
      ]
    }
  ]
}
```

### Campos Importantes

| Campo | Ubicación | Descripción |
|-------|-----------|-------------|
| `from` | `entry[0].changes[0].value.messages[0].from` | Número del remitente |
| `text.body` | `entry[0].changes[0].value.messages[0].text.body` | Contenido del mensaje |
| `type` | `entry[0].changes[0].value.messages[0].type` | Tipo: text, image, audio, etc |
| `wa_id` | `entry[0].changes[0].value.contacts[0].wa_id` | ID de WhatsApp del usuario |
| `name` | `entry[0].changes[0].value.contacts[0].profile.name` | Nombre del usuario |
| `phone_number_id` | `entry[0].changes[0].value.metadata.phone_number_id` | ID del número de negocio |

### Status Updates

Chattigo también envía actualizaciones de estado (entregado, leído). Estos NO tienen `messages`:

```json
{
  "object": "whatsapp_business_account",
  "entry": [{
    "changes": [{
      "value": {
        "statuses": [{
          "id": "wamid...",
          "status": "delivered",
          "timestamp": "1767030600"
        }]
      }
    }]
  }]
}
```

**Detección:** Si `value.statuses` existe, es un status update (ignorar).

---

## 4. Enviar Mensajes

Chattigo utiliza un formato propietario para enviar mensajes (no el formato Meta).

### Endpoint

```
POST https://channels.chattigo.com/bsp-cloud-chattigo-isv/webhooks/inbound
```

### Enviar Mensaje de Texto

```python
import requests

url = "https://channels.chattigo.com/bsp-cloud-chattigo-isv/webhooks/inbound"

# Formato propietario Chattigo
payload = {
    "id": "1234567890",              # ID único del mensaje (timestamp)
    "did": "5492644710400",          # Tu número de WhatsApp Business
    "msisdn": "5492644472542",       # Número destino
    "type": "text",
    "channel": "WHATSAPP",
    "content": "Hola! Soy el bot de Aynux",
    "name": "Aynux",                 # Nombre del bot
    "isAttachment": False
}

headers = {
    'Authorization': 'Bearer TU_ACCESS_TOKEN',
    'Content-Type': 'application/json'
}

response = requests.post(url, headers=headers, json=payload)
```

### Enviar Documento/Media

```python
payload = {
    "id": "1234567890",
    "did": "5492644710400",
    "msisdn": "5492644472542",
    "type": "media",                 # Tipo "media" para archivos
    "channel": "WHATSAPP",
    "content": "Aquí tienes el documento",  # Caption
    "name": "Aynux",
    "isAttachment": True,
    "attachment": {
        "mediaUrl": "https://example.com/document.pdf",
        "mimeType": "application/pdf",
        "fileName": "documento.pdf"
    }
}
```

### Enviar Imagen

```python
payload = {
    "id": "1234567890",
    "did": "5492644710400",
    "msisdn": "5492644472542",
    "type": "media",
    "channel": "WHATSAPP",
    "content": "Aquí tienes la imagen",
    "name": "Aynux",
    "isAttachment": True,
    "attachment": {
        "mediaUrl": "https://example.com/image.jpg",
        "mimeType": "image/jpeg"
    }
}
```

### Respuesta Exitosa

HTTP 200 con cuerpo vacío indica éxito.

---

## 5. Implementación en el Código

### Archivos Relevantes

| Archivo | Descripción |
|---------|-------------|
| `app/api/routes/webhook.py` | Endpoint que recibe webhooks |
| `app/integrations/chattigo/models.py` | Modelos Pydantic para payloads |
| `app/models/message.py` | `WhatsAppWebhookRequest` para parsear |
| `app/integrations/whatsapp/service.py` | Servicio para enviar mensajes |

### Flujo de Procesamiento

```python
# 1. Detectar formato del payload
if raw_json.get("object") == "whatsapp_business_account":
    # Formato WhatsApp estándar (desde Chattigo)
    wa_request = WhatsAppWebhookRequest.model_validate(raw_json)
    message = wa_request.get_message()
    contact = wa_request.get_contact()
else:
    # Formato Chattigo ISV legacy (raro)
    payload = ChattigoWebhookPayload(**raw_json)

# 2. Ignorar status updates
if is_status_update(wa_request):
    return {"status": "ok", "type": "status_update"}

# 3. Procesar mensaje
# ... lógica del bot
```

---

## 6. Configuración de Producción

### Credenciales (Base de Datos)

Las credenciales de Chattigo se almacenan en la tabla `chattigo_credentials` con encriptación.
Gestione las credenciales via Admin API:

```bash
# Listar credenciales
GET /api/v1/admin/chattigo-credentials

# Crear credenciales
POST /api/v1/admin/chattigo-credentials
{
  "did": "5492644710400",
  "name": "WhatsApp Produccion",
  "username": "usuario@dominio",
  "password": "password_seguro",
  "bot_name": "Aynux",
  "organization_id": "uuid-de-organizacion"
}

# Probar autenticación
POST /api/v1/admin/chattigo-credentials/{did}/test
```

### Variables de Entorno (Solo Configuración)

```bash
# Chattigo (solo configuración, credenciales en DB)
CHATTIGO_ENABLED=true
CHATTIGO_BASE_URL=https://channels.chattigo.com/bsp-cloud-chattigo-isv
```

### Verificar Conectividad

```bash
# Test autenticación
curl -X POST "https://channels.chattigo.com/bsp-cloud-chattigo-isv/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "TU_USUARIO", "password": "TU_PASSWORD"}'
```

---

## 7. Troubleshooting

### Mensaje no llega al bot

1. **Verificar webhook registrado:**
   - Confirmar que `externalWebhook` apunta a tu URL
   - URL debe ser HTTPS válida y accesible públicamente

2. **Revisar logs:**
   ```bash
   docker logs aynux-prod-app-1 -f | grep webhook
   ```

3. **Verificar formato:** El payload debe tener `"object": "whatsapp_business_account"`

### Bot no responde

1. **Verificar token Chattigo:** El token expira, regenerar si es necesario
2. **Verificar servicio WhatsApp:** Logs deben mostrar "Sending WhatsApp message"
3. **NO debe decir `[TEST MODE]`** - Si lo dice, el envío está deshabilitado

### Error "status update, ignoring"

Esto es normal para notificaciones de entrega/lectura. Solo los mensajes con `messages[]` se procesan.

---

## 8. Script de Prueba

Archivo: `scripts/test_chattigo.py`

```bash
# Solo autenticación
uv run python scripts/test_chattigo.py --auth-only

# Enviar mensaje de prueba
uv run python scripts/test_chattigo.py --send-test --phone 5491112345678
```

---

## Endpoints Chattigo

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/login` | Autenticación |
| PATCH | `/webhooks/inbound` | Registrar webhook para mensajes entrantes |
| POST | `/webhooks/inbound` | Enviar mensaje saliente (formato Chattigo propietario) |

**Base URL:** `https://channels.chattigo.com/bsp-cloud-chattigo-isv`

**Formato de Mensajes Salientes:** Formato propietario Chattigo (NO WhatsApp Cloud API)
- Campos requeridos: `id`, `did`, `msisdn`, `type`, `channel`, `content`, `name`, `isAttachment`
