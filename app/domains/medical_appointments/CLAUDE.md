# CLAUDE.md - Medical Appointments Domain

Guidance for Claude Code working with the Medical Appointments domain.

## Domain Overview

**Medical Appointments** - WhatsApp-based medical appointment booking system using LangGraph.

| Feature | Description |
|---------|-------------|
| **Purpose** | Book, confirm, cancel, and reschedule medical appointments via WhatsApp |
| **Architecture** | Clean Architecture + DDD + LangGraph StateGraph |
| **External System** | HCWeb SOAP API for medical institution data |
| **Notifications** | WhatsApp Business API via Chattigo adapter |

## Critical Development Rules

### 1. Exception Handling - Always preserve stack traces
```python
# ✅ Good
except ValueError as e:
    raise HTTPException(status_code=400, detail="Invalid") from e
```

### 2. Modern Typing (Python 3.10+)
```python
# ✅ Use native types
def func(ids: list[int], data: dict[str, str] | None) -> None: ...
# ❌ Avoid: List, Dict, Optional from typing
```

### 3. UTC Timezone
```python
from datetime import UTC, datetime
now = datetime.now(UTC)  # ✅ Always UTC
```

### 4. Dependency Inversion (DIP) - MANDATORY
```python
# ✅ Good - depend on abstractions
from ..application.ports import IMedicalSystemClient, INotificationService

class MyNode(BaseNode):
    def __init__(
        self,
        medical_client: IMedicalSystemClient,  # ✅ Interface
        notification_service: INotificationService | None = None,  # ✅ Interface
    ): ...

# ❌ Bad - depend on concrete implementations
from ..infrastructure.external import HCWebSOAPClient  # ❌ Concrete class
```

## SOLID Principles (Mandatory)

| Principle | Rule | This Domain |
|-----------|------|-------------|
| **SRP** | One responsibility per class | Nodes handle one conversation step |
| **OCP** | Extend via inheritance | BaseNode provides extensible base |
| **LSP** | Subclasses honor contracts | All nodes extend BaseNode correctly |
| **ISP** | Small, focused interfaces | 7 segregated interfaces in `ports/` |
| **DIP** | Depend on abstractions | Use `IMedicalSystemClient`, not `HCWebSOAPClient` |

### Size Limits
- Functions: <20 lines (max 50)
- Classes: <200 lines (max 500)
- Files: <500 lines

## Domain Architecture

```
medical_appointments/
├── domain/                    # Domain Layer
│   ├── entities/             # Appointment, Patient, Provider, Specialty
│   └── value_objects/        # AppointmentStatus, etc.
│
├── application/              # Application Layer
│   ├── ports/               # ⭐ Segregated Interfaces (ISP)
│   │   ├── patient_port.py          # IPatientManager
│   │   ├── appointment_port.py      # IAppointmentManager
│   │   ├── availability_port.py     # IAvailabilityChecker
│   │   ├── reminder_port.py         # IReminderManager
│   │   ├── notification_port.py     # INotificationService
│   │   ├── external_medical_system.py  # IMedicalSystemClient (composes all)
│   │   └── response.py              # ExternalResponse
│   ├── use_cases/           # Business logic
│   └── dto/                 # Data Transfer Objects
│
├── infrastructure/           # Infrastructure Layer
│   ├── external/
│   │   └── hcweb/           # ⭐ Refactored SOAP Client (SRP)
│   │       ├── client.py            # HCWebSOAPClient (implements interfaces)
│   │       ├── soap_builder.py      # SoapRequestBuilder
│   │       └── response_parser.py   # SoapResponseParser
│   ├── services/
│   │   ├── appointment_notification_service.py  # Implements INotificationService
│   │   └── notification/
│   │       └── interactive_selection.py  # InteractiveSelectionService
│   └── scheduler/           # Reminder scheduling
│
└── agents/                   # LangGraph Agents Layer
    ├── graph.py             # MedicalAppointmentsGraph (StateGraph)
    ├── state.py             # MedicalAppointmentsState (TypedDict)
    └── nodes/               # ⭐ LangGraph Nodes (12 nodes)
        ├── base.py                  # BaseNode (DIP compliant)
        ├── router.py                # Intent detection
        ├── greeting.py              # Welcome message
        ├── patient_identification.py
        ├── patient_registration.py
        ├── specialty_selection.py
        ├── provider_selection.py
        ├── date_selection.py
        ├── time_selection.py
        ├── booking_confirmation.py
        ├── appointment_management.py
        ├── reschedule.py
        └── fallback.py
```

## Segregated Interfaces (ISP)

Use the appropriate interface based on what functionality you need:

```python
# ✅ Use segregated interface when you only need patient operations
async def find_patient(client: IPatientManager, dni: str):
    return await client.buscar_paciente_dni(dni)

# ✅ Use combined interface when you need everything
async def full_booking(client: IMedicalSystemClient, ...):
    patient = await client.buscar_paciente_dni(dni)
    slots = await client.obtener_horarios_disponibles(provider_id, date)
    return await client.crear_turno(patient_id, provider_id, datetime)
```

### Interface Quick Reference

| Interface | Methods | Use When |
|-----------|---------|----------|
| `IPatientManager` | `buscar_paciente_dni`, `buscar_paciente_celular`, `registrar_paciente`, `actualizar_verificacion_whatsapp` | Patient CRUD only |
| `IAppointmentManager` | `crear_turno`, `confirmar_turno`, `cancelar_turno`, `reprogramar_turno`, `obtener_turnos_paciente`, `obtener_turno_sugerido` | Appointment operations |
| `IAvailabilityChecker` | `obtener_especialidades`, `obtener_prestadores`, `obtener_dias_disponibles`, `obtener_horarios_disponibles`, `get_proximo_turno_disponible*` | Availability queries |
| `IReminderManager` | `obtener_turnos_hoy`, `obtener_turnos_manana`, `obtener_turnos_para_recordatorio`, `marcar_recordatorio_enviado` | Reminder operations |
| `INotificationService` | `send_message`, `send_interactive_list`, `send_interactive_buttons`, `send_template`, `close` | WhatsApp notifications |
| `IMedicalSystemClient` | All of the above + `close`, `obtener_informacion_institucion`, `obtener_instituciones_activas` | Full access needed |

## LangGraph Node Pattern

### Creating a New Node

```python
# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: [Your node description]
# ============================================================================
"""[Node Name] Node.

[Brief description of what this node does]
"""

import logging
from typing import TYPE_CHECKING, Any

from .base import BaseNode

if TYPE_CHECKING:
    from ..state import MedicalAppointmentsState

logger = logging.getLogger(__name__)


class MyNewNode(BaseNode):
    """Node for [specific purpose].

    [Detailed description]
    """

    async def process(self, state: "MedicalAppointmentsState") -> dict[str, Any]:
        """Process the node.

        Args:
            state: Current conversation state.

        Returns:
            Dictionary with state updates.
        """
        message = self._get_message(state)

        # Use self._medical (IMedicalSystemClient) for API calls
        response = await self._medical.buscar_paciente_dni(dni)

        if not response.success:
            return self._error_response(response.error_message or "Error")

        # Use self._notification (INotificationService) for WhatsApp
        if self._notification:
            await self._notification.send_message(phone, "Mensaje")

        return self._text_response(
            "Respuesta al usuario",
            next_node="siguiente_nodo",
            # ... other state updates
        )
```

### BaseNode Helper Methods

```python
# Response helpers
self._text_response(text, **state_updates)  # Simple text response
self._error_response(error_message)          # Error response
self._list_response(title, items, ...)       # Numbered list

# State extraction
self._get_message(state)      # Get last user message
self._get_selection(state)    # Get numeric selection (0-based)
self._get_patient_id(state)   # Get patient ID from state
self._get_provider_id(state)  # Get provider ID from state
self._get_specialty_id(state) # Get specialty ID from state

# Validation
self._is_confirmation(message)   # Check if message confirms
self._is_cancellation(message)   # Check if message cancels
self._is_valid_document(message) # Check if valid DNI
self._extract_document(message)  # Extract DNI from message

# WhatsApp (via INotificationService)
await self._send_interactive_list(phone, title, items)
await self._send_interactive_buttons(phone, body, buttons)
```

## ExternalResponse Pattern

All API calls return `ExternalResponse`:

```python
from ..application.ports import ExternalResponse

# Making API calls
response = await self._medical.buscar_paciente_dni(dni)

# Check success
if response.success:
    data = response.data  # dict or list
    patient_id = response.get_value("idPaciente")
else:
    error_code = response.error_code
    error_msg = response.error_message

# Factory methods
ExternalResponse.ok({"key": "value"})
ExternalResponse.error("ERROR_CODE", "Error message")
```

## Configuration

The graph requires configuration with institution details:

```python
config = {
    "institution": "patologia_digestiva",      # Required: institution key
    "institution_name": "Patología Digestiva", # Required: display name
    "institution_id": "123",                   # Required: HCWeb institution ID
    "soap_url": "http://host/WsHcweb.asmx",   # Required: SOAP endpoint
    "did": "5492645668671",                    # Required: WhatsApp DID
}

graph = MedicalAppointmentsGraph(config=config, db_session=session)
```

## Conversation Flow

```
┌─────────┐
│ ROUTER  │ ← Entry point, detects intent
└────┬────┘
     │
     ├─► GREETING ──────────────────────────────────► END
     │
     ├─► PATIENT_IDENTIFICATION ─┬─► PATIENT_REGISTRATION ─► END
     │                           │
     │                           └─► SPECIALTY_SELECTION
     │                                      │
     │                                      ▼
     │                              PROVIDER_SELECTION
     │                                      │
     │                                      ▼
     │                               DATE_SELECTION
     │                                      │
     │                                      ▼
     │                               TIME_SELECTION
     │                                      │
     │                                      ▼
     │                           BOOKING_CONFIRMATION ─► END
     │
     ├─► APPOINTMENT_MANAGEMENT ────────────────────► END
     │
     ├─► RESCHEDULE ────────────────────────────────► END
     │
     └─► FALLBACK ──────────────────────────────────► END
```

## Adding New Functionality

### Adding a New Use Case

1. Create use case in `application/use_cases/`
2. Use segregated interface as dependency
3. Add DTO if needed in `application/dto/`

```python
# application/use_cases/my_new_use_case.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ports import IAppointmentManager  # ✅ Use interface

class MyNewUseCase:
    def __init__(self, appointment_manager: "IAppointmentManager"):
        self._appointments = appointment_manager

    async def execute(self, appointment_id: str) -> ...:
        return await self._appointments.confirmar_turno(appointment_id)
```

### Adding a New SOAP Method

1. Add to interface in `application/ports/` (appropriate segregated interface)
2. Implement in `infrastructure/external/hcweb/client.py`

```python
# 1. Add to interface (e.g., appointment_port.py)
class IAppointmentManager(Protocol):
    async def my_new_method(self, param: str) -> "ExternalResponse": ...

# 2. Implement in client.py
async def my_new_method(self, param: str) -> ExternalResponse:
    return await self._call_method("NuevoMetodoSOAP", {
        "parametro": param,
        "idInstitucion": self.institution_id,
    })
```

## Quality Checklist

Before committing changes to this domain:

- [ ] DIP: Using interfaces (`IMedicalSystemClient`, `INotificationService`), not concrete classes?
- [ ] SRP: Each class/function has single responsibility?
- [ ] Functions <20 lines?
- [ ] File <500 lines?
- [ ] Type hints complete?
- [ ] Error handling with `from e`?
- [ ] `ExternalResponse` pattern used for API calls?
- [ ] Node extends `BaseNode` and implements `process()`?
- [ ] State updates returned as dict?

## Common Patterns

### Safe API Call Pattern
```python
response = await self._medical.obtener_especialidades()
if not response.success:
    logger.warning(f"API error: {response.error_message}")
    return self._error_response(response.error_message or "Error al obtener datos")

specialties = response.get_list()
if not specialties:
    return self._text_response("No hay especialidades disponibles.")
```

### Interactive WhatsApp Pattern
```python
if self._notification:
    await self._send_interactive_list(
        phone=state.get("user_phone", ""),
        title="Seleccione una opción:",
        items=[{"id": s["codigo"], "title": s["nombre"]} for s in specialties],
    )
```

### State Flow Pattern
```python
return {
    "next_node": "provider_selection",
    "selected_specialty": specialty_id,
    "specialties_list": specialties,
    "detected_intent": "specialty_selected",
}
```
