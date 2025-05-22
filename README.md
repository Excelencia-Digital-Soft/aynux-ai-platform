# 🤖 Chatbot Municipal para WhatsApp

Un sistema avanzado para municipalidades que permite a los ciudadanos realizar consultas, trámites y gestiones a través de WhatsApp utilizando inteligencia artificial.

## 🌟 Características

- 🚀 **FastAPI**: Framework moderno y de alto rendimiento para crear APIs asíncronas
- 🧠 **Gemini AI**: Integración con modelos avanzados de IA para respuestas contextuales inteligentes
- 💬 **WhatsApp Business API**: Comunicación directa con los ciudadanos a través de WhatsApp
- 📱 **Verificación de identidad**: Sistema seguro de verificación de ciudadanos
- 🏢 **Gestión municipal**: Consulta de deudas, trámites, reclamos y certificados
- 📄 **Generación de certificados**: Emisión automática de certificados con códigos QR verificables
- 🔄 **Persistencia con Redis**: Gestión eficiente de sesiones y estados de conversación
- 🔒 **Autenticación JWT**: Sistema de autenticación seguro para APIs
- 🧩 **Arquitectura modular**: Diseño escalable y mantenible

## 📋 Requisitos

- Python 3.11+
- Redis
- Cuenta en WhatsApp Business API
- Cuenta en Gemini AI
- API municipal de backend (o servicios simulados para desarrollo)

## 🔧 Instalación

### Con Poetry (Recomendado)

1. **Instalar Poetry** (si no está instalado):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. **Clonar el repositorio**:
   ```bash
   git clone https://github.com/tu-usuario/chatbot-municipal.git
   cd chatbot-municipal
   ```

3. **Instalar dependencias**:
   ```bash
   poetry install
   ```

4. **Configurar variables de entorno**:
   ```bash
   cp .env.example .env
   # Editar .env con tus credenciales
   ```

### Script de desarrollo

El proyecto incluye un script `dev.sh` que facilita el desarrollo:

```bash
# Dar permisos de ejecución
chmod +x dev.sh

# Ejecutar el script
./dev.sh
```

El script ofrece opciones para:
- Instalar dependencias
- Iniciar el servidor de desarrollo
- Ejecutar verificaciones de código (black, isort, ruff)
- Ejecutar pruebas
- Actualizar dependencias
- Generar shell de Poetry

## 🏗️ Estructura del Proyecto

```
chatbot-municipal/
│
├── app/                        # Código principal de la aplicación
│   ├── __init__.py
│   ├── main.py                 # Punto de entrada de FastAPI
│   │
│   ├── api/                    # Rutas y endpoints de la API
│   │   ├── __init__.py
│   │   ├── dependencies.py     # Dependencias para inyección
│   │   ├── middleware/         # Middlewares personalizados
│   │   └── routes/             # Definición de rutas por recurso
│   │
│   ├── config/                 # Configuración con Pydantic
│   │   ├── __init__.py
│   │   └── settings.py
│   │
│   ├── models/                 # Modelos de datos Pydantic
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── ciudadano.py
│   │   ├── message.py
│   │   └── webhook.py
│   │
│   ├── repositories/           # Capa de acceso a datos (Redis)
│   │   ├── __init__.py
│   │   ├── ciudadano_repository.py
│   │   └── redis_repository.py
│   │
│   ├── services/               # Lógica de negocio
│   │   ├── __init__.py
│   │   ├── ai_service.py       # Integración con Gemini AI
│   │   ├── chatbot_service.py  # Coordinación de servicios
│   │   ├── ciudadano_service.py
│   │   ├── municipio_api_service.py
│   │   ├── reclamos_service.py
│   │   ├── token_service.py
│   │   ├── tramites_service.py
│   │   └── whatsapp_service.py # Comunicación con WhatsApp
│   │
│   └── utils/                  # Utilidades y herramientas
│       ├── __init__.py
│       ├── certificate_utils.py # Generación de certificados
│       └── whatsapp_utils.py
│
├── tests/                      # Pruebas automatizadas
│   ├── __init__.py
│   ├── conftest.py             # Configuración de pytest
│   ├── test_services.py
│   └── test_webhook.py
│
├── .env.example                # Plantilla de variables de entorno
├── .gitignore                  # Archivos ignorados por git
├── dev.sh                      # Script para desarrollo
├── pyproject.toml              # Configuración de Poetry y herramientas
└── README.md                   # Este archivo
```

## 🚀 Ejecución

### Servidor de desarrollo

```bash
# Con Poetry
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# O usando el script de desarrollo
./dev.sh
# Seleccionar opción 2: "Iniciar servidor de desarrollo"
```

### Documentación de la API

La documentación automática estará disponible en:
- **Swagger UI**: `http://localhost:8000/api/v1/docs`
- **ReDoc**: `http://localhost:8000/api/v1/redoc`

## 🔄 Flujo de Funcionamiento

1. **Recepción de mensajes**: WhatsApp envía mensajes a través del webhook.
2. **Verificación de identidad**: Se identifica al ciudadano y se verifica su identidad.
3. **Procesamiento con IA**: Gemini AI interpreta la intención del usuario.
4. **Integración con servicios municipales**: Se conecta con la API municipal para consultar datos.
5. **Respuesta contextual**: Se envía respuesta personalizada al ciudadano.

## 🧪 Pruebas

```bash
# Ejecutar todas las pruebas
poetry run pytest

# Con cobertura
poetry run pytest --cov=app
```

## 📝 Convenciones de Código

El proyecto utiliza:
- **Black**: Formateador de código
- **isort**: Ordenamiento de imports
- **Ruff**: Linter para verificación estática

Para verificar y formatear el código:
```bash
poetry run black app
poetry run isort app
poetry run ruff check app --fix
```

## 📊 Gestión de Dependencias con Poetry

Poetry simplifica la gestión de dependencias y entornos virtuales:

```bash
# Añadir una dependencia
poetry add nombre-paquete

# Añadir dependencia de desarrollo
poetry add --group dev nombre-paquete

# Actualizar dependencias
poetry update

# Generar requirements.txt (si es necesario)
poetry export -f requirements.txt --output requirements.txt
```

## 🔐 Variables de Entorno

Las principales variables que debes configurar en tu archivo `.env`:

```
# API de WhatsApp
ACCESS_TOKEN=tu_token_whatsapp
PHONE_NUMBER_ID=tu_id_telefono
VERIFY_TOKEN=tu_token_verificacion

# API municipal
MUNICIPIO_API_BASE=https://api.municipalidad.gob.ar
MUNICIPIO_API_KEY=tu_api_key

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=tu_contraseña_redis

# Gemini AI
GEMINI_API_KEY=tu_api_key_gemini
GEMINI_MODEL=gemini-1.5-flash
```

## 📚 Documentación Adicional

Para más información sobre las tecnologías utilizadas:
- [FastAPI](https://fastapi.tiangolo.com/)
- [Pydantic](https://docs.pydantic.dev/)
- [Redis](https://redis.io/docs/)
- [Poetry](https://python-poetry.org/docs/)
- [WhatsApp Business API](https://developers.facebook.com/docs/whatsapp/)
- [Gemini AI](https://ai.google.dev/docs/gemini)

## 📃 Licencia

Este proyecto está licenciado por Excelencia.
