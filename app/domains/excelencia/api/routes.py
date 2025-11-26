"""
Excelencia API Routes

FastAPI router for Excelencia ERP domain endpoints.
"""

from datetime import date

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

router = APIRouter(prefix="/excelencia", tags=["Excelencia ERP"])


@router.get("/modules", response_model=ModulesListResponse)
async def get_modules(
    use_case: ShowModulesUseCase = Depends(get_show_modules_use_case),
):
    """Get available ERP modules."""
    # Create request with default values
    request = ShowModulesRequest()
    result = await use_case.execute(request)

    modules = [
        ModuleResponse(
            name=m.display_name,
            description=m.description,
            features=m.features,
        )
        for m in result.modules
    ]

    return ModulesListResponse(
        modules=modules,
        total=len(modules),
    )


@router.post("/demo", response_model=DemoResponse)
async def schedule_demo(
    request: DemoRequest,
    use_case: ScheduleDemoUseCase = Depends(get_schedule_demo_use_case),
):
    """Schedule a demo session."""
    result = await use_case.execute(
        contact_name=request.contact_name,
        company_name=request.company_name,
        email=request.email,
        phone=request.phone,
        preferred_date=request.preferred_date,
        preferred_time=request.preferred_time,
        modules_of_interest=request.modules_of_interest,
        notes=request.notes,
    )

    return DemoResponse(
        success=result.success,
        message=result.message,
        demo_id=result.demo_id,
        scheduled_date=result.scheduled_date,
        scheduled_time=result.scheduled_time,
    )


@router.get("/demo/slots", response_model=list[AvailableSlotResponse])
async def get_available_slots(
    target_date: date,
    use_case: ScheduleDemoUseCase = Depends(get_schedule_demo_use_case),
):
    """Get available demo slots for a date."""
    slots = await use_case.get_available_slots(target_date)

    return [
        AvailableSlotResponse(
            date=slot.date,
            time=slot.time,
            is_available=slot.is_available,
        )
        for slot in slots
    ]


__all__ = ["router"]
