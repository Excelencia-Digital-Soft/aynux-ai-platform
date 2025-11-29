"""
Excelencia API Routes

FastAPI router for Excelencia ERP domain endpoints.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from app.domains.excelencia.api.dependencies import (
    get_schedule_demo_use_case,
    get_show_modules_use_case,
)
from app.domains.excelencia.api.schemas import (
    AvailableSlotResponse,
    DemoRequest,
    DemoResponse,
    ModuleResponse,
    ModulesListResponse,
)
from app.domains.excelencia.application.use_cases import (
    ScheduleDemoUseCase,
    ShowModulesRequest,
    ShowModulesUseCase,
)
from app.domains.excelencia.application.use_cases.schedule_demo import (
    ScheduleDemoRequest,
)

router = APIRouter(prefix="/excelencia", tags=["Excelencia ERP"])


@router.get("/modules", response_model=ModulesListResponse)
async def get_modules(
    use_case: Annotated[ShowModulesUseCase, Depends(get_show_modules_use_case)],
):
    """Get available ERP modules."""
    # Create request with default values
    request = ShowModulesRequest()
    result = await use_case.execute(request)

    modules = [
        ModuleResponse(
            name=module.display_name,
            description=module.description,
            features=module.features,
        )
        for module in result.modules
    ]

    return ModulesListResponse(
        modules=modules,
        total=len(modules),
    )


@router.post("/demo", response_model=DemoResponse)
async def schedule_demo(
    request: DemoRequest,
    use_case: Annotated[ScheduleDemoUseCase, Depends(get_schedule_demo_use_case)],
):
    """Schedule a demo session."""
    # Create use case request from API request
    use_case_request = ScheduleDemoRequest(
        contact_name=request.contact_name,
        company_name=request.company_name,
        contact_email=request.email,
        contact_phone=request.phone,
        preferred_date=request.preferred_date,
        preferred_time=request.preferred_time,
        notes=request.notes,
    )
    result = await use_case.execute(use_case_request)

    # Map response fields
    demo_id = result.scheduled_demo.demo_id if result.scheduled_demo else None
    scheduled_date = result.scheduled_demo.scheduled_date if result.scheduled_demo else None
    scheduled_time = result.scheduled_demo.scheduled_time if result.scheduled_demo else None

    return DemoResponse(
        success=result.success,
        message=result.message or result.error or "",
        demo_id=demo_id,
        scheduled_date=scheduled_date,
        scheduled_time=scheduled_time,
    )


@router.get("/demo/slots", response_model=list[AvailableSlotResponse])
async def get_available_slots(
    target_date: date,
    use_case: Annotated[ScheduleDemoUseCase, Depends(get_schedule_demo_use_case)],
):
    """Get available demo slots for a date."""
    slots = await use_case.get_available_slots(target_date)

    return [
        AvailableSlotResponse(
            date=slot.date,
            time=slot.start_time,
            is_available=slot.is_available,
        )
        for slot in slots
    ]


__all__ = ["router"]
