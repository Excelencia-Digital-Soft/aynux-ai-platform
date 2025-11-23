"""
Implementation Guide for Remaining Domains

This guide shows how to implement Healthcare and Excelencia domains
following the same Clean Architecture pattern used for E-commerce and Credit.

## Pattern to Follow

Each domain should have:
1. **Use Cases** (Business Logic)
2. **Repositories** (Data Access)
3. **Agents** (Orchestration)

## Healthcare Domain Implementation

### 1. Identify Use Cases

Based on hospital/medical needs:
- **GetPatientInfoUseCase**: Get patient medical records
- **ScheduleAppointmentUseCase**: Book medical appointments
- **GetAppointmentScheduleUseCase**: View appointment calendar
- **GetMedicalRecordsUseCase**: Access medical history
- **PrescriptionManagementUseCase**: Manage prescriptions

### 2. Create Use Case (Example)

```python
# app/domains/healthcare/application/use_cases/get_patient_info.py

from dataclasses import dataclass
from typing import Optional
from app.core.interfaces.repository import IRepository

@dataclass
class GetPatientInfoRequest:
    patient_id: str
    user_id: Optional[str] = None  # For authorization

@dataclass
class GetPatientInfoResponse:
    patient_id: str
    name: str
    age: int
    medical_history: str
    allergies: List[str]
    current_medications: List[str]
    success: bool
    error: Optional[str] = None

class GetPatientInfoUseCase:
    def __init__(self, patient_repository: IRepository):
        self.patient_repo = patient_repository

    async def execute(self, request: GetPatientInfoRequest) -> GetPatientInfoResponse:
        try:
            patient = await self.patient_repo.find_by_id(request.patient_id)

            if not patient:
                return GetPatientInfoResponse(
                    patient_id=request.patient_id,
                    name="",
                    age=0,
                    medical_history="",
                    allergies=[],
                    current_medications=[],
                    success=False,
                    error="Patient not found"
                )

            return GetPatientInfoResponse(
                patient_id=patient.patient_id,
                name=patient.name,
                age=patient.age,
                medical_history=patient.medical_history,
                allergies=patient.allergies,
                current_medications=patient.current_medications,
                success=True
            )
        except Exception as e:
            logger.error(f"Error getting patient info: {e}")
            return GetPatientInfoResponse(
                patient_id=request.patient_id,
                name="",
                age=0,
                medical_history="",
                allergies=[],
                current_medications=[],
                success=False,
                error=str(e)
            )
```

### 3. Create Repository

```python
# app/domains/healthcare/infrastructure/persistence/sqlalchemy/patient_repository.py

from app.core.interfaces.repository import IRepository

class PatientRepository(IRepository[Patient, str]):
    async def find_by_id(self, id: str) -> Optional[Patient]:
        # TODO: Implement with SQLAlchemy
        pass

    async def find_all(self, skip: int = 0, limit: int = 100) -> List[Patient]:
        # TODO: Implement with SQLAlchemy
        pass

    # ... other IRepository methods

    # Domain-specific methods
    async def find_by_medical_record_number(self, mrn: str) -> Optional[Patient]:
        pass

    async def find_appointments_for_patient(self, patient_id: str) -> List[Appointment]:
        pass
```

### 4. Create Agent

```python
# app/domains/healthcare/agents/healthcare_agent.py

from app.core.interfaces.agent import IAgent, AgentType

class HealthcareAgent(IAgent):
    def __init__(
        self,
        patient_repository: IRepository,
        appointment_repository: IRepository,
        llm: ILLM,
        config: Optional[Dict[str, Any]] = None
    ):
        self._patient_repo = patient_repository
        self._appointment_repo = appointment_repository
        self._llm = llm

        # Initialize use cases
        self._patient_info_use_case = GetPatientInfoUseCase(patient_repository)
        self._schedule_appointment_use_case = ScheduleAppointmentUseCase(appointment_repository)

    @property
    def agent_type(self) -> AgentType:
        return AgentType.HEALTHCARE

    @property
    def agent_name(self) -> str:
        return "healthcare_agent"

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # Analyze intent and route to appropriate use case
        intent = await self._analyze_intent(messages[-1]["content"])

        if intent == "patient_info":
            return await self._handle_patient_info(state)
        elif intent == "schedule_appointment":
            return await self._handle_schedule_appointment(state)
        # ... etc
```

## Excelencia Domain Implementation

### 1. Identify Use Cases

Based on Excelencia Digital Soft business needs:
- **GetCompanyServicesUseCase**: List available services
- **RequestQuoteUseCase**: Request project quote
- **GetPortfolioUseCase**: View company portfolio
- **ContactSalesUseCase**: Contact sales team
- **GetServiceDetailsUseCase**: Details about specific service

### 2. Implementation Pattern

Follow the same pattern as Healthcare:

```python
# app/domains/excelencia/application/use_cases/get_company_services.py

@dataclass
class GetCompanyServicesRequest:
    category: Optional[str] = None  # 'web', 'mobile', 'ai', etc.

@dataclass
class GetCompanyServicesResponse:
    services: List[Dict[str, Any]]
    total_count: int
    success: bool
    error: Optional[str] = None

class GetCompanyServicesUseCase:
    def __init__(self, service_repository: IRepository):
        self.service_repo = service_repository

    async def execute(self, request: GetCompanyServicesRequest) -> GetCompanyServicesResponse:
        # Implementation similar to E-commerce pattern
        pass
```

## Key Principles to Maintain

### 1. Single Responsibility Principle
- Each use case does ONE thing
- Each repository handles ONE entity type
- Each agent coordinates ONE domain

### 2. Dependency Inversion
- Always depend on interfaces (IRepository, ILLM, IVectorStore)
- Never depend on concrete implementations
- Use dependency injection

### 3. Clean Architecture Layers
```
Agents (Interface) → Use Cases (Business Logic) → Repositories (Data Access)
       ↓                      ↓                           ↓
   IAgent Interface    Domain Logic Only           IRepository Interface
```

### 4. Testability
- All components can be tested with mocks
- No database required for unit tests
- Follow pattern from: tests/unit/domains/ecommerce/test_product_use_cases.py

## Implementation Checklist

For each new domain:

- [ ] Identify 3-5 core use cases
- [ ] Create use case request/response dataclasses
- [ ] Implement use cases with business logic only
- [ ] Create repository implementing IRepository
- [ ] Create agent implementing IAgent
- [ ] Wire dependencies with dependency injection
- [ ] Create unit tests with mocks
- [ ] Update __init__.py files with exports

## Example Directory Structure

```
app/domains/healthcare/
├── application/
│   └── use_cases/
│       ├── __init__.py
│       ├── get_patient_info.py
│       ├── schedule_appointment.py
│       └── get_medical_records.py
├── infrastructure/
│   └── persistence/
│       └── sqlalchemy/
│           ├── __init__.py
│           ├── patient_repository.py
│           └── appointment_repository.py
└── agents/
    ├── __init__.py
    └── healthcare_agent.py
```

## Integration with Super Orchestrator

Once domains are implemented, register them in Super Orchestrator:

```python
# app/services/super_orchestrator_service.py

from app.domains.healthcare.agents import HealthcareAgent
from app.domains.excelencia.agents import ExcelenciaAgent

class SuperOrchestratorService:
    def __init__(self):
        # Initialize domain agents
        self.healthcare_agent = self._create_healthcare_agent()
        self.excelencia_agent = self._create_excelencia_agent()

        # Register in routing table
        self.domain_agents = {
            "healthcare": self.healthcare_agent,
            "excelencia": self.excelencia_agent,
            # ... other domains
        }

    async def route_to_domain(self, message: str, state: Dict) -> Dict:
        domain = await self._detect_domain(message)
        agent = self.domain_agents.get(domain)
        return await agent.execute(state)
```

## Benefits of This Architecture

1. **Consistency**: All domains follow same pattern
2. **Maintainability**: Easy to understand and modify
3. **Testability**: 100% unit test coverage possible
4. **Scalability**: Easy to add new domains
5. **Flexibility**: Easy to change implementations

## Next Steps

1. Choose one domain to implement first (Healthcare or Excelencia)
2. Start with 2-3 core use cases
3. Create repository with mock data first
4. Implement agent with basic routing
5. Add more use cases incrementally
6. Replace mock data with real DB when ready

## Reference Implementation

See completed domains for reference:
- **E-commerce**: app/domains/ecommerce/
- **Credit**: app/domains/credit/

Both follow this exact pattern and can serve as templates.
"""
