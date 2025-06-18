# 🤖 ConversaShop - Conversa más, vende mejor

Sistema inteligente de comercio conversacional que revoluciona la experiencia de compra a través de WhatsApp. Nuestra plataforma integra inteligencia artificial avanzada con un sistema multi-agente basado en LangGraph para actuar como un asesor personal que guía a los clientes en tiempo real, ayudándolos a descubrir productos, resolver dudas y completar compras de manera intuitiva y personalizada.

## 🌟 Características

- 🤖 **Sistema Multi-Agente LangGraph**: 10 agentes especializados con enrutamiento inteligente
- 🧠 **Ollama AI**: Modelos de IA locales para respuestas contextuales y análisis de intenciones
- 💬 **WhatsApp Business API**: Comunicación directa con clientes a través de WhatsApp
- 🏪 **Integración ERP DUX**: Sincronización automática de productos, categorías y facturas
- 🛍️ **E-commerce Completo**: Gestión de productos, pedidos, inventario y pagos
- 🔍 **Búsqueda Semántica**: ChromaDB para búsqueda vectorial avanzada
- 🔄 **Persistencia Multi-Base**: PostgreSQL, Redis y ChromaDB para datos optimizados
- 📊 **Analytics Inteligente**: Generación dinámica de reportes y métricas de ventas
- 🔒 **Seguridad Avanzada**: Autenticación JWT y manejo seguro de credenciales
- 🧩 **Arquitectura Modular**: Diseño escalable siguiendo principios SOLID

## 📋 Requisitos

- Python 3.11+
- PostgreSQL 13+
- Redis 6+
- Ollama (para modelos de IA locales)
- WhatsApp Business API
- DUX ERP (opcional)

## 🔧 Instalación

### Con Poetry (Recomendado)

1. **Instalar Poetry** (si no está instalado):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. **Clonar el repositorio**:
   ```bash
   git clone https://github.com/excelencia/bot-conversashop.git
   cd bot-conversashop
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

5. **Inicializar base de datos**:
   ```bash
   python app/scripts/init_database.py
   python app/scripts/init_checkpointer_tables.py
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

## 🏗️ Arquitectura del Sistema

### Sistema Multi-Agente LangGraph

```
ConversaShop utiliza un sistema sofisticado de 10 agentes especializados:

📋 SupervisorAgent     → Orquestador central y enrutamiento
🛍️  ProductAgent       → Consultas de productos, stock y precios
📂 CategoryAgent      → Exploración de categorías con búsqueda vectorial
📊 DataInsightsAgent  → Analytics y reportes dinámicos
🎯 SupportAgent       → Soporte técnico y FAQ
🚚 TrackingAgent      → Seguimiento de pedidos y envíos
💰 InvoiceAgent       → Facturación y procesamiento de pagos
🎁 PromotionsAgent    → Ofertas, descuentos y promociones
💬 FallbackAgent      → Conversaciones generales
👋 FarewellAgent      → Cierre de conversaciones
```

### Integración DUX ERP

```
ConversaShop/
│
├── app/
│   ├── agents/                     # Sistema LangGraph Multi-Agente
│   │   ├── langgraph_system/       # Core del sistema de agentes
│   │   │   ├── agents/             # Agentes especializados
│   │   │   ├── intelligence/       # Análisis de intenciones con IA
│   │   │   ├── integrations/       # PostgreSQL, ChromaDB, Ollama
│   │   │   └── tools/              # Herramientas para agentes
│   │   │
│   │   ├── api/                    # API REST con FastAPI
│   │   │   └── routes/             # Endpoints (webhook, admin)
│   │   │
│   │   ├── clients/                # Clientes HTTP especializados
│   │   │   ├── dux_api_client.py   # Cliente productos DUX
│   │   │   ├── dux_rubros_client.py # Cliente categorías DUX
│   │   │   └── dux_facturas_client.py # Cliente facturas DUX
│   │   │
│   │   ├── database/               # Configuración multi-base de datos
│   │   │   ├── async_db.py         # PostgreSQL asíncrono
│   │   │   └── setup.py            # Inicialización con datos
│   │   │
│   │   ├── models/                 # Modelos de datos
│   │   │   ├── db/                 # Modelos SQLAlchemy
│   │   │   └── dux/                # Modelos DUX ERP
│   │   │       ├── entities.py     # Entidades de negocio
│   │   │       ├── product.py      # Productos con utilidades
│   │   │       ├── invoice.py      # Facturas y pagos
│   │   │       └── response_*.py   # Respuestas especializadas
│   │   │
│   │   ├── schemas/                # Configuración centralizada
│   │   │   └── agent_schema.py     # Schema de agentes y enrutamiento
│   │   │
│   │   ├── services/               # Lógica de negocio
│   │   │   ├── langgraph_chatbot_service.py # Servicio principal
│   │   │   └── dux_sync_service.py # Sincronización DUX
│   │   │
│   │   ├── scripts/                # Scripts de utilidad
│   │   │   ├── init_database.py    # Inicialización BD
│   │   │   └── sync_dux_products.py # Sync productos DUX
│   │   │
│   │   └── utils/                  # Utilidades
│   │       └── rate_limiter.py     # Rate limiting DUX API
│   │
├── tests/                          # Pruebas automatizadas
├── .env.example                    # Plantilla variables de entorno
├── dev.sh                          # Script para desarrollo
└── pyproject.toml                  # Configuración Poetry
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

1. **Recepción de mensajes**: WhatsApp envía mensajes a través del webhook
2. **Análisis de intención**: Ollama AI clasifica la intención del usuario
3. **Enrutamiento inteligente**: SupervisorAgent dirige a agente especializado
4. **Procesamiento especializado**: Agente consulta datos (PostgreSQL/DUX/ChromaDB)
5. **Generación de respuesta**: IA contextual crea respuesta personalizada
6. **Persistencia**: Estado guardado en PostgreSQL con checkpointing
7. **Respuesta al cliente**: Mensaje enviado vía WhatsApp

## 🧪 Pruebas

```bash
# Ejecutar todas las pruebas
poetry run pytest

# Con cobertura
poetry run pytest --cov=app

# Pruebas específicas
poetry run pytest -m unit          # Pruebas unitarias
poetry run pytest -m integration   # Pruebas de integración
poetry run pytest -m api          # Pruebas de API
```

### Pruebas de Integración DUX

```bash
# Probar conexión y sincronización DUX
python app/scripts/sync_dux_products.py
```

## 📝 Convenciones de Código

El proyecto utiliza:
- **Black**: Formateador de código (120 caracteres)
- **isort**: Ordenamiento de imports
- **Ruff**: Linter para verificación estática
- **Pyright**: Verificación de tipos

```bash
# Verificar y formatear código
poetry run black app
poetry run isort app
poetry run ruff check app --fix
```

## 🔐 Variables de Entorno

Las principales variables que debes configurar en tu archivo `.env`:

```env
# API Configuration
API_V1_STR=/api/v1
PROJECT_NAME=ConversaShop API

# WhatsApp Business API
WHATSAPP_API_BASE=https://graph.facebook.com
WHATSAPP_API_VERSION=v22.0
WHATSAPP_PHONE_NUMBER_ID=tu_id_telefono
WHATSAPP_VERIFY_TOKEN=tu_token_verificacion
WHATSAPP_ACCESS_TOKEN=tu_token_acceso
META_APP_ID=tu_facebook_app_id
META_APP_SECRET=tu_facebook_app_secret

# PostgreSQL Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=conversashop
DB_USER=tu_usuario
DB_PASSWORD=tu_contraseña

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=tu_contraseña_redis

# Ollama AI
OLLAMA_API_MODEL=llama3.2:1b
OLLAMA_API_URL=http://localhost:11434
OLLAMA_API_CHROMADB=./data/vector_db/
OLLAMA_API_MODEL_EMBEDDING=mxbai-embed-large

# DUX ERP Integration
DUX_API_BASE_URL=https://erp.duxsoftware.com.ar/WSERP/rest/services
DUX_API_KEY=tu_api_key_dux
DUX_API_TIMEOUT=30
DUX_API_RATE_LIMIT_SECONDS=5
DUX_SYNC_BATCH_SIZE=50

# JWT Settings
JWT_SECRET_KEY=tu_clave_secreta_jwt
ACCESS_TOKEN_EXPIRE_MINUTES=10080
REFRESH_TOKEN_EXPIRE_DAYS=7
```

## 🔧 Configuración Adicional

### Ollama Setup

```bash
# Instalar Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Descargar modelos requeridos
ollama pull llama3.2:1b
ollama pull mxbai-embed-large
```

### PostgreSQL Extensions

```sql
-- Extensiones requeridas
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
```

## 🌐 Integraciones Disponibles

- **WhatsApp Business API**: Comunicación principal
- **DUX ERP**: Productos, categorías, facturas
- **PostgreSQL**: Base de datos principal
- **ChromaDB**: Búsqueda vectorial semántica
- **Redis**: Cache y sesiones
- **Ollama**: IA local para análisis y respuestas

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

## 📚 Documentación Adicional

Para más información sobre las tecnologías utilizadas:
- [FastAPI](https://fastapi.tiangolo.com/)
- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [Pydantic](https://docs.pydantic.dev/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
- [ChromaDB](https://docs.trychroma.com/)
- [Ollama](https://ollama.ai/)
- [WhatsApp Business API](https://developers.facebook.com/docs/whatsapp/)
- [Poetry](https://python-poetry.org/docs/)

## 🤝 Contribución

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📃 Licencia

Este proyecto está licenciado por Excelencia.

---

**ConversaShop** - Transformando conversaciones en ventas con inteligencia artificial avanzada 🚀
