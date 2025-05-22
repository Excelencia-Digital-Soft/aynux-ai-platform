# Guía de Testing - Bot Municipal WhatsApp

Este documento explica la estructura, funcionamiento y uso del framework de pruebas para el Bot Municipal de WhatsApp.

## 📋 Contenido

- [Visión General](#visión-general)
- [Estructura de las Pruebas](#estructura-de-las-pruebas)
- [Tipos de Pruebas](#tipos-de-pruebas)
  - [Pruebas Unitarias](#pruebas-unitarias)
  - [Pruebas de Integración](#pruebas-de-integración)
- [Herramientas de Soporte](#herramientas-de-soporte)
  - [Fixtures Comunes](#fixtures-comunes)
  - [Simulador de WhatsApp](#simulador-de-whatsapp)
- [Ejecución de Pruebas](#ejecución-de-pruebas)
- [Generación de Informes de Cobertura](#generación-de-informes-de-cobertura)
- [Pruebas Específicas](#pruebas-específicas)
- [Ampliación de las Pruebas](#ampliación-de-las-pruebas)
- [Mejores Prácticas](#mejores-prácticas)

## 🔍 Visión General

La suite de pruebas está diseñada para verificar el correcto funcionamiento del Bot Municipal de WhatsApp, enfocándose en:

- Validación de servicios individuales (pruebas unitarias)
- Verificación de flujos completos de usuario (pruebas de integración)
- Simulación de interacciones reales con la API de WhatsApp

Las pruebas utilizan `pytest` como framework principal, complementado con mocks para simular dependencias externas.

## 📁 Estructura de las Pruebas

```
tests/
├── __init__.py
├── conftest.py                    # Configuración y fixtures comunes
├── unit/                          # Pruebas unitarias
│   ├── __init__.py
│   ├── services/                  # Pruebas de servicios
│   │   ├── __init__.py
│   │   ├── test_ai_service.py     # Pruebas del servicio de IA
│   │   ├── test_ciudadano_service.py
│   │   ├── test_whatsapp_service.py
│   │   └── test_chatbot_service.py
│   ├── repositories/              # Pruebas de repositorios
│   │   ├── __init__.py
│   │   ├── test_ciudadano_repository.py
│   │   └── test_redis_repository.py
│   ├── models/                    # Pruebas de modelos
│   │   ├── __init__.py
│   │   ├── test_message.py
│   │   └── test_ciudadano.py
│   └── utils/                     # Pruebas de utilidades
│       ├── __init__.py
│       └── test_certificate_utils.py
├── integration/                   # Pruebas de integración
│   ├── __init__.py
│   ├── test_integration_flows.py  # Flujos completos
│   └── test_webhook_endpoint.py   # Pruebas del endpoint webhook
├── tools/                         # Herramientas para pruebas
│   ├── __init__.py
│   └── whatsapp_simulator.py      # Simulador de mensajes WhatsApp
└── scripts/                       # Scripts auxiliares
    ├── run_tests.sh               # Script para ejecutar todas las pruebas
    └── run_coverage.sh            # Script para ejecutar tests con cobertura
```

## 🧪 Tipos de Pruebas

### Pruebas Unitarias

Las pruebas unitarias verifican el funcionamiento correcto de componentes individuales de la aplicación, aislados de sus dependencias. Utilizamos mocks y fixtures para simular el comportamiento de las dependencias.

**Componentes testeados:**

- **Servicio de Ciudadano**: Verificación, registro y actualización de datos de ciudadanos.
- **Servicio de WhatsApp**: Envío de mensajes, documentos y componentes interactivos.
- **Servicio de IA (Gemini)**: Generación de respuestas y procesamiento de intenciones.
- **Servicio de Chatbot**: Coordinación entre servicios y procesamiento de mensajes.

**Ejemplo:**

```python
@pytest.mark.asyncio
async def test_get_info_ciudadano_success(self, ciudadano_service, mock_municipio_api):
    """Prueba para obtener información de un ciudadano con éxito"""
    # Configurar el mock para simular una respuesta exitosa
    mock_municipio_api.get.return_value = {
        "success": True,
        "data": {
            "id_ciudadano": "123",
            "nombre": "Juan",
            "apellido": "Pérez",
            "documento": "12345678",
            "telefono": "5491112345678"
        }
    }

    # Llamar al método y verificar el resultado
    result = await ciudadano_service.get_info_ciudadano("5491112345678")
    
    # Verificaciones
    mock_municipio_api.get.assert_called_once_with(
        "contribuyentes/celular", params={"telefono": "5491112345678"}
    )
    assert result["success"] is True
    assert result["data"]["nombre"] == "Juan"
```

### Pruebas de Integración

Las pruebas de integración verifican que varios componentes funcionen correctamente juntos, siguiendo flujos completos de usuario.

**Flujos probados:**

- **Verificación de identidad**: Inicio de conversación → verificación → confirmación.
- **Consulta de deuda**: Consulta del usuario → procesamiento IA → obtención de datos → respuesta.
- **Solicitud de certificado**: Solicitud → generación de certificado → envío al usuario.
- **Consulta de trámites**: Solicitud de información → listado de trámites disponibles.

**Ejemplo:**

```python
@pytest.mark.asyncio
async def test_flujo_verificacion_usuario(self, sample_message, sample_contact, mock_dependencies):
    """Prueba el flujo completo de verificación de un usuario"""
    # Configurar entorno de prueba
    chatbot_service = ChatbotService()
    # ... configuración de mocks ...
    
    # PASO 1: Mensaje inicial
    result_initial = await chatbot_service.procesar_mensaje(message_initial, sample_contact)
    
    # Verificar cambio de estado
    mock_ciudadano_repository.update_user_state.assert_called_once_with(
        "5491112345678", "verificar"
    )
    
    # PASO 2: Usuario confirma su identidad
    # ... configuración de mensaje de confirmación ...
    result_confirm = await chatbot_service.procesar_mensaje(message_confirm, sample_contact)
    
    # Verificar resultado final
    assert result_confirm["status"] == "success"
    assert result_confirm["state"] == "verificado"
```

## 🔧 Herramientas de Soporte

### Fixtures Comunes

El archivo `conftest.py` contiene fixtures compartidos entre todas las pruebas, incluyendo:

- Mocks de todos los servicios y repositorios
- Datos de ejemplo (mensajes, contactos, usuarios)
- Configuración para pruebas asíncronas
- Funciones auxiliares para crear escenarios de prueba

```python
@pytest.fixture
def sample_user() -> User:
    """Fixture para crear un usuario de ejemplo"""
    return User(
        phone_number="5491112345678",
        state=UserState(
            state="verificado",
            verificado=True,
            id_ciudadano="123",
        )
    )
```

### Simulador de WhatsApp

El simulador `whatsapp_simulator.py` permite enviar mensajes simulados al webhook para probar el sistema de manera interactiva:

- **Modo interactivo**: Para pruebas manuales de flujos de conversación.
- **Modo script**: Para ejecutar secuencias predefinidas de mensajes.
- **Modo verificación**: Para verificar la configuración del webhook.

## ▶️ Ejecución de Pruebas

### Ejecutar todas las pruebas:

```bash
./tests/scripts/run_tests.sh
```

### Ejecutar solo pruebas unitarias:

```bash
python -m pytest tests/unit -v
```

### Ejecutar solo pruebas de integración:

```bash
python -m pytest tests/integration -v
```

### Ejecutar un archivo específico:

```bash
python -m pytest tests/unit/services/test_ciudadano_service.py -v
```

### Ejecutar un test específico:

```bash
python -m pytest tests/unit/services/test_ciudadano_service.py::TestCiudadanoService::test_get_info_ciudadano_success -v
```

## 📊 Generación de Informes de Cobertura

Para generar informes de cobertura de código:

```bash
./tests/scripts/run_coverage.sh
```

Esto generará un informe detallado en HTML que podrás ver en `htmlcov/index.html`.

## 🎯 Pruebas Específicas

### Probar el servicio de ciudadano:

```bash
python -m pytest tests/unit/services/test_ciudadano_service.py -v
```

### Probar el servicio de WhatsApp:

```bash
python -m pytest tests/unit/services/test_whatsapp_service.py -v
```

### Probar los flujos de integración:

```bash
python -m pytest tests/integration/test_integration_flows.py -v
```

### Usar el simulador de WhatsApp:

```bash
# Modo interactivo
python tests/tools/whatsapp_simulator.py

# Verificar webhook
python tests/tools/whatsapp_simulator.py --mode verify

# Ejecutar script predefinido
python tests/tools/whatsapp_simulator.py --mode script

# Personalizar número y nombre
python tests/tools/whatsapp_simulator.py --phone 5491199887766 --name "Juan Pérez"
```

## 🔄 Ampliación de las Pruebas

Para añadir nuevas pruebas:

1. **Pruebas unitarias**: Crear un nuevo archivo `test_*.py` en el directorio correspondiente según el componente a probar.

2. **Pruebas de integración**: Añadir nuevos métodos de prueba en `test_integration_flows.py` o crear un nuevo archivo para flujos específicos.

3. **Fixtures reutilizables**: Añadir al archivo `conftest.py` para compartirlos entre pruebas.

Ejemplo de estructura para un nuevo test:

```python
@pytest.mark.asyncio
async def test_nuevo_flujo(self, fixtures_necesarios):
    """Descripción clara del propósito de la prueba"""
    # 1. Configuración (Arrange)
    # Preparar el entorno y los datos de prueba
    
    # 2. Acción (Act)
    # Ejecutar la funcionalidad a probar
    
    # 3. Verificación (Assert)
    # Comprobar que los resultados son los esperados
```

## ✅ Mejores Prácticas

1. **Nomenclatura clara**: Nombra los tests de forma descriptiva para entender su propósito.
2. **Aislamiento**: Cada test debe ser independiente y no afectar otros tests.
3. **Estructura AAA**: Sigue el patrón Arrange-Act-Assert (Preparar-Actuar-Verificar).
4. **Mocks específicos**: Configura los mocks solo con el comportamiento necesario.
5. **Pruebas de bordes**: Incluye casos límite y escenarios de error.
6. **Documentación**: Añade docstrings descriptivos a cada test.
7. **Mantenimiento**: Actualiza las pruebas cuando cambies la funcionalidad.

---

Si tienes preguntas o necesitas ayuda, por favor contacta al equipo de desarrollo.
