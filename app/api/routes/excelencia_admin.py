"""
Excelencia Admin API Routes

RESTful API for managing Excelencia ERP modules and demos.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import DependencyContainer
from app.database.async_db import get_async_db
from app.domains.excelencia.api.admin_schemas import (
    DemoAssign,
    DemoListResponse,
    DemoResponse,
    DemoSchedule,
    DemoStatusUpdate,
    DemoUpdate,
    ErrorResponse,
    MessageResponse,
    ModuleCreate,
    ModuleListResponse,
    ModuleResponse,
    ModuleUpdate,
)

logger = logging.getLogger(__name__)

# Create router (prefix is relative - api_router adds /api/v1)
router = APIRouter(
    prefix="/admin/excelencia",
    tags=["Excelencia Administration"],
    responses={
        404: {"model": ErrorResponse, "description": "Resource not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)


# ============================================================================
# Module Endpoints
# ============================================================================


@router.get(
    "/modules",
    response_model=ModuleListResponse,
    summary="List all modules",
    description="List all ERP modules with optional filtering",
)
async def list_modules(
    category: str | None = Query(None, description="Filter by category"),  # noqa: B008
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),  # noqa: B008
    page: int = Query(1, ge=1, description="Page number"),  # noqa: B008
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """List all ERP modules with optional filtering and pagination."""
    try:
        container = DependencyContainer()
        use_case = container.create_list_modules_admin_use_case(db)
        result = await use_case.execute(
            category=category,
            status=status_filter,
            page=page,
            page_size=page_size,
        )
        return ModuleListResponse(
            modules=[ModuleResponse(**m) for m in result.modules],
            total=result.total,
            page=result.page,
            page_size=result.page_size,
            total_pages=result.total_pages,
        )
    except Exception as e:
        logger.error(f"Error listing modules: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list modules",
        ) from e


@router.post(
    "/modules",
    response_model=ModuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a module",
    description="Create a new ERP module",
)
async def create_module(
    module: ModuleCreate,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Create a new ERP module."""
    try:
        container = DependencyContainer()
        use_case = container.create_create_module_use_case(db)
        result = await use_case.execute(
            code=module.code,
            name=module.name,
            category=module.category.value,
            description=module.description,
            status=module.status.value,
            features=module.features,
            pricing_tier=module.pricing_tier,
        )
        return ModuleResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error creating module: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create module",
        ) from e


@router.get(
    "/modules/{module_id}",
    response_model=ModuleResponse,
    summary="Get a module",
    description="Get a specific module by ID or code",
)
async def get_module(
    module_id: str,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Get a specific module by ID or code."""
    try:
        container = DependencyContainer()
        repository = container.excelencia.create_module_repository(db)
        module = await repository.get_by_id(module_id)
        if not module:
            module = await repository.get_by_code(module_id)

        if not module:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Module {module_id} not found",
            )

        return ModuleResponse(**module.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting module {module_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get module",
        ) from e


@router.put(
    "/modules/{module_id}",
    response_model=ModuleResponse,
    summary="Update a module",
    description="Update an existing module",
)
async def update_module(
    module_id: str,
    module: ModuleUpdate,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Update an existing module."""
    try:
        update_data = module.model_dump(exclude_unset=True)

        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided for update",
            )

        # Convert enums to values
        if "category" in update_data and update_data["category"]:
            update_data["category"] = update_data["category"].value
        if "status" in update_data and update_data["status"]:
            update_data["status"] = update_data["status"].value

        container = DependencyContainer()
        use_case = container.create_update_module_use_case(db)
        result = await use_case.execute(module_id=module_id, update_data=update_data)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Module {module_id} not found",
            )

        return ModuleResponse(**result)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error updating module {module_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update module",
        ) from e


@router.delete(
    "/modules/{module_id}",
    response_model=MessageResponse,
    summary="Delete a module",
    description="Delete a module (soft or hard delete)",
)
async def delete_module(
    module_id: str,
    hard_delete: bool = Query(False, description="Permanently delete (true) or deprecate (false)"),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Delete a module."""
    try:
        container = DependencyContainer()
        use_case = container.create_delete_module_use_case(db)
        success = await use_case.execute(
            module_id=module_id,
            soft_delete=not hard_delete,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Module {module_id} not found",
            )

        return MessageResponse(
            message=f"Module {'deleted' if hard_delete else 'deprecated'} successfully",
            success=True,
            details={"module_id": module_id, "hard_delete": hard_delete},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting module {module_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete module",
        ) from e


# ============================================================================
# Demo Endpoints
# ============================================================================


@router.get(
    "/demos",
    response_model=DemoListResponse,
    summary="List all demos",
    description="List all demos with optional filtering",
)
async def list_demos(
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),  # noqa: B008
    company: str | None = Query(None, description="Filter by company name"),  # noqa: B008
    page: int = Query(1, ge=1, description="Page number"),  # noqa: B008
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """List all demos with optional filtering and pagination."""
    try:
        container = DependencyContainer()
        use_case = container.create_list_demos_admin_use_case(db)
        result = await use_case.execute(
            status=status_filter,
            company=company,
            page=page,
            page_size=page_size,
        )
        return DemoListResponse(
            demos=[DemoResponse(**d) for d in result.demos],
            total=result.total,
            page=result.page,
            page_size=result.page_size,
            total_pages=result.total_pages,
        )
    except Exception as e:
        logger.error(f"Error listing demos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list demos",
        ) from e


@router.get(
    "/demos/{demo_id}",
    response_model=DemoResponse,
    summary="Get a demo",
    description="Get a specific demo by ID",
)
async def get_demo(
    demo_id: str,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Get a specific demo by ID."""
    try:
        container = DependencyContainer()
        repository = container.excelencia.create_demo_repository(db)
        demo = await repository.get_by_id(demo_id)

        if not demo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Demo {demo_id} not found",
            )

        # Flatten response
        result = demo.to_dict()
        request_data = result.pop("request", {})
        result.update(request_data)
        return DemoResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting demo {demo_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get demo",
        ) from e


@router.put(
    "/demos/{demo_id}",
    response_model=DemoResponse,
    summary="Update a demo",
    description="Update an existing demo",
)
async def update_demo(
    demo_id: str,
    demo: DemoUpdate,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Update an existing demo."""
    try:
        update_data = demo.model_dump(exclude_unset=True)

        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided for update",
            )

        # Convert enums to values
        if "demo_type" in update_data and update_data["demo_type"]:
            update_data["demo_type"] = update_data["demo_type"].value
        if "status" in update_data and update_data["status"]:
            update_data["status"] = update_data["status"].value

        container = DependencyContainer()
        use_case = container.create_update_demo_use_case(db)
        result = await use_case.execute(demo_id=demo_id, update_data=update_data)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Demo {demo_id} not found",
            )

        return DemoResponse(**result)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error updating demo {demo_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update demo",
        ) from e


@router.put(
    "/demos/{demo_id}/status",
    response_model=DemoResponse,
    summary="Update demo status",
    description="Update only the status of a demo",
)
async def update_demo_status(
    demo_id: str,
    status_update: DemoStatusUpdate,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Update only the status of a demo."""
    try:
        container = DependencyContainer()
        use_case = container.create_update_demo_status_use_case(db)
        result = await use_case.execute(
            demo_id=demo_id,
            new_status=status_update.status.value,
            notes=status_update.notes,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Demo {demo_id} not found",
            )

        return DemoResponse(**result)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error updating demo status {demo_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update demo status",
        ) from e


@router.put(
    "/demos/{demo_id}/schedule",
    response_model=DemoResponse,
    summary="Schedule a demo",
    description="Schedule a demo with date, time, and assignee",
)
async def schedule_demo(
    demo_id: str,
    schedule: DemoSchedule,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Schedule a demo."""
    try:
        container = DependencyContainer()
        use_case = container.create_schedule_demo_admin_use_case(db)
        result = await use_case.execute(
            demo_id=demo_id,
            scheduled_at=schedule.scheduled_at,
            assigned_to=schedule.assigned_to,
            duration_minutes=schedule.duration_minutes,
            meeting_link=schedule.meeting_link,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Demo {demo_id} not found",
            )

        return DemoResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scheduling demo {demo_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to schedule demo",
        ) from e


@router.put(
    "/demos/{demo_id}/assign",
    response_model=DemoResponse,
    summary="Assign a demo",
    description="Assign a demo to a sales rep",
)
async def assign_demo(
    demo_id: str,
    assignment: DemoAssign,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Assign a demo to a sales rep."""
    try:
        container = DependencyContainer()
        use_case = container.create_update_demo_use_case(db)
        result = await use_case.execute(
            demo_id=demo_id,
            update_data={"assigned_to": assignment.assigned_to},
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Demo {demo_id} not found",
            )

        return DemoResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning demo {demo_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign demo",
        ) from e


@router.delete(
    "/demos/{demo_id}",
    response_model=MessageResponse,
    summary="Delete a demo",
    description="Delete a demo permanently",
)
async def delete_demo(
    demo_id: str,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Delete a demo permanently."""
    try:
        container = DependencyContainer()
        repository = container.excelencia.create_demo_repository(db)
        success = await repository.delete(demo_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Demo {demo_id} not found",
            )

        return MessageResponse(
            message="Demo deleted successfully",
            success=True,
            details={"demo_id": demo_id},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting demo {demo_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete demo",
        ) from e
