# Simulador de WhatsApp para Pruebas de Webhook

Este simulador permite enviar mensajes simulados de WhatsApp a un webhook, facilitando el desarrollo y prueba de chatbots sin necesidad de usar la API real de WhatsApp Business.

![WhatsApp Simulator](https://img.shields.io/badge/WhatsApp-Simulator-25D366?style=for-the-badge&logo=whatsapp&logoColor=white)

## Características

- ✉️ **Mensajes de texto** - Envío de mensajes de texto simples
- 🔘 **Botones interactivos** - Simula respuestas con botones
- 📋 **Listas de opciones** - Envío y selección de elementos de listas
- 📍 **Ubicaciones** - Envío de coordenadas geográficas con datos adicionales
- 🖼️ **Multimedia** - Soporte para imágenes, documentos, audios y videos
- 📝 **Plantillas** - Respuestas a plantillas de WhatsApp Business
- 🔄 **Flujos completos** - Simula conversaciones predefinidas de principio a fin
- 🔍 **Verificación** - Simula el proceso de verificación del webhook
- 📱 **Referrals** - Simula entradas desde anuncios o enlaces externos

## Requisitos

- Python 3.6 o superior
- Módulo `requests` (`pip install requests`)

## Instalación

1. Clone este repositorio o descargue el archivo `whatsapp_simulator.py`
2. Instale los requisitos: `pip install requests`

## Uso

### Modo Interactivo (por defecto)

```bash
python whatsapp_simulator.py
```

Este modo permite enviar mensajes manualmente uno a uno.

### Verificación del Webhook

```bash
python whatsapp_simulator.py --mode verify
```

Simula el proceso de verificación inicial que WhatsApp realiza al configurar un webhook.

### Script Automático

```bash
python whatsapp_simulator.py --mode script
```

Ejecuta una secuencia predefinida de mensajes que simulan una conversación completa.

### Flujos de Conversación

```bash
python whatsapp_simulator.py --mode flows
```

Muestra un menú para seleccionar entre diferentes flujos de conversación predefinidos.

### Personalización

```bash
python whatsapp_simulator.py --url https://miservidor.com/webhook --phone 5491199887766 --name "Juan Pérez"
```

## Comandos en Modo Interactivo

| Comando | Descripción | Ejemplo |
|---------|-------------|---------|
| `/help` | Muestra la lista de comandos | `/help` |
| `/quit` | Sale del simulador | `/quit` |
| `/verify` | Simula verificación del webhook | `/verify` |
| `/button:id:texto` | Envía respuesta de botón | `/button:btn_1:Aceptar` |
| `/list:id:título:descripción` | Envía respuesta de lista | `/list:lst_1:Opción 1:Descripción` |
| `/location:lat:lon:nombre:dirección` | Envía ubicación | `/location:-34.603:58.381:Oficina:Av. Corrientes 1000` |
| `/image:url:caption` | Envía imagen | `/image:https://ejemplo.com/img.jpg:Mi foto` |
| `/audio` | Envía nota de voz | `/audio` |
| `/document:url:nombre` | Envía documento | `/document:https://ejemplo.com/doc.pdf:Contrato` |
| `/video:url:caption` | Envía video | `/video:https://ejemplo.com/video.mp4:Video demo` |
| `/template:nombre:id` | Responde a plantilla | `/template:bienvenida:tmpl_1` |
| `/referral:url:tipo` | Simula entrada por referencia | `/referral:https://fb.com/ad:ad` |
| `/flow:nombre` | Ejecuta flujo predefinido | `/flow:consulta_deuda` |

## Flujos Predefinidos

El simulador incluye tres flujos de conversación predefinidos:

1. **consulta_deuda**: Simula una consulta de deuda municipal
2. **tramite_documento**: Simula un trámite para obtener un documento
3. **ayuda_general**: Simula una conversación general de ayuda

## Estructura del Mensaje

El simulador genera payloads en el formato exacto que WhatsApp Business API envía a los webhooks:

```json
{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "id": "123456789",
      "changes": [
        {
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {
              "display_phone_number": "1234567890",
              "phone_number_id": "987654321"
            },
            "contacts": [
              {
                "profile": {"name": "Usuario de Prueba"},
                "wa_id": "5491112345678"
              }
            ],
            "messages": [
              {
                "from": "5491112345678",
                "id": "wamid.abcd1234",
                "timestamp": "1621234567",
                "type": "text",
                "text": {"body": "Mensaje de prueba"}
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

## Personalización del Simulador

### Añadir Nuevos Flujos

Puedes añadir nuevos flujos de conversación modificando el diccionario `flows` en la función `execute_flow()`:

```python
flows = {
    "mi_nuevo_flujo": [
        ("text", "Mensaje inicial"),
        ("wait", 2),
        ("button", "boton_id", "Texto del botón"),
        # Más pasos...
    ],
    # Otros flujos...
}
```

### Modificar el Script Predefinido

Puedes personalizar el script automático modificando la lista `script` en la función `script_mode()`.

## Para Desarrolladores

### Extensión del Simulador

El simulador está diseñado para ser fácilmente extensible. Puedes añadir nuevos tipos de mensajes creando funciones similares a `send_text_message()`, `send_button_reply()`, etc.

### Depuración

Todas las funciones imprimen información detallada sobre los mensajes enviados y las respuestas recibidas, facilitando la depuración de problemas.

## Limitaciones

- Este simulador no implementa la firma criptográfica real que WhatsApp utiliza para verificar los mensajes. Usa una firma simulada (`sha256=dummy_signature`).
- No procesa las respuestas del webhook más allá de mostrarlas.
- Los mensajes multimedia (imágenes, videos, etc.) no envían datos binarios reales.
