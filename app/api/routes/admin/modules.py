"""
Software Modules API - Database-backed endpoint.

Provides RESTful API for software modules catalog (Excelencia).
Now uses PostgreSQL database instead of hardcoded values.
Automatically syncs with RAG (company_knowledge) for chatbot access.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.async_db import get_async_db
from app.domains.excelencia.application.use_cases import (
    CreateModuleDTO,
    CreateModuleUseCase,
    DeleteModuleUseCase,
    GetModuleUseCase,
    ListModulesUseCase,
    ModuleResponseDTO,
    SyncAllModulesToRagUseCase,
    UpdateModuleDTO,
    UpdateModuleUseCase,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/modules", tags=["Software Modules"])


# ============================================================================
# Request/Response Models
# ============================================================================


class CreateModuleRequest(BaseModel):
    """Request body for creating a module."""

    code: str = Field(..., min_length=2, max_length=20, description="Module code (e.g., HC-001)")
    name: str = Field(..., min_length=2, max_length=200, description="Module name")
    description: str = Field(..., min_length=10, description="Module description")
    category: str = Field(default="general", description="Category: healthcare, hospitality, finance, guilds, products, public_services, general")
    status: str = Field(default="active", description="Status: active, beta, deprecated, coming_soon")
    features: list[str] = Field(default_factory=list, description="List of features")
    pricing_tier: str = Field(default="standard", description="Pricing tier")


class UpdateModuleRequest(BaseModel):
    """Request body for updating a module."""

    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None)
    category: str | None = Field(default=None)
    status: str | None = Field(default=None)
    features: list[str] | None = Field(default=None)
    pricing_tier: str | None = Field(default=None)


class SyncResultResponse(BaseModel):
    """Response for sync operations."""

    total: int
    synced: int
    failed: int
    message: str


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "",
    response_model=list[ModuleResponseDTO],
    summary="Get all software modules",
    description="Get list of software modules from database with optional filters",
)
async def get_modules(
    category: str | None = Query(None, description="Filter by category"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    search: str | None = Query(None, description="Search in name/description"),
    active_only: bool = Query(True, description="Only return active modules"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Pagination limit"),
    db: AsyncSession = Depends(get_async_db),
) -> list[ModuleResponseDTO]:
    """
    Get list of software modules from database.

    Query Parameters:
    - **category**: Filter by category (healthcare, hospitality, etc.)
    - **status**: Filter by status (active, beta, etc.)
    - **search**: Search term for name/description
    - **active_only**: Only return active modules (default: true)
    - **skip**: Pagination offset
    - **limit**: Pagination limit (max 500)

    Returns:
        List of ModuleResponseDTO objects
    """
    try:
        use_case = ListModulesUseCase(db)
        modules = await use_case.execute(
            category=category,
            status=status_filter,
            search=search,
            active_only=active_only,
            skip=skip,
            limit=limit,
        )
        logger.info(f"Returning {len(modules)} modules")
        return modules

    except Exception as e:
        logger.exception(f"Error getting modules: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get modules: {e!s}",
        ) from e


@router.get(
    "/{module_id}",
    response_model=ModuleResponseDTO,
    summary="Get single module",
    description="Get a single software module by ID or code",
)
async def get_module(
    module_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> ModuleResponseDTO:
    """
    Get a single software module by ID or code.

    Args:
        module_id: Module identifier (UUID or code like "HC-001")

    Returns:
        ModuleResponseDTO object

    Raises:
        HTTPException 404: If module not found
    """
    try:
        use_case = GetModuleUseCase(db)

        # Try to parse as UUID first
        try:
            uuid_id = UUID(module_id)
            result = await use_case.execute(module_id=uuid_id)
        except ValueError:
            # Not a UUID, try as code
            result = await use_case.execute(code=module_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Module '{module_id}' not found",
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting module {module_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get module: {e!s}",
        ) from e


@router.post(
    "",
    response_model=ModuleResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create software module",
    description="Create a new software module and sync to RAG",
)
async def create_module(
    request: CreateModuleRequest,
    sync_to_rag: bool = Query(True, description="Sync to knowledge base for chatbot"),
    db: AsyncSession = Depends(get_async_db),
) -> ModuleResponseDTO:
    """
    Create a new software module.

    The module will be automatically synced to company_knowledge
    for RAG access by the chatbot.

    Args:
        request: CreateModuleRequest with module data
        sync_to_rag: Whether to sync to knowledge base (default: true)

    Returns:
        Created ModuleResponseDTO

    Raises:
        HTTPException 400: If module code already exists
    """
    try:
        dto = CreateModuleDTO(
            code=request.code,
            name=request.name,
            description=request.description,
            category=request.category,
            status=request.status,
            features=request.features,
            pricing_tier=request.pricing_tier,
        )

        use_case = CreateModuleUseCase(db)
        result = await use_case.execute(dto, sync_to_rag=sync_to_rag)

        logger.info(f"Created module: {result.code}")
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception(f"Error creating module: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create module: {e!s}",
        ) from e


@router.put(
    "/{module_id}",
    response_model=ModuleResponseDTO,
    summary="Update software module",
    description="Update an existing software module and sync to RAG",
)
async def update_module(
    module_id: str,
    request: UpdateModuleRequest,
    sync_to_rag: bool = Query(True, description="Sync changes to knowledge base"),
    db: AsyncSession = Depends(get_async_db),
) -> ModuleResponseDTO:
    """
    Update an existing software module.

    Changes will be automatically synced to company_knowledge
    for RAG access by the chatbot.

    Args:
        module_id: Module UUID
        request: UpdateModuleRequest with fields to update
        sync_to_rag: Whether to sync to knowledge base (default: true)

    Returns:
        Updated ModuleResponseDTO

    Raises:
        HTTPException 404: If module not found
    """
    try:
        uuid_id = UUID(module_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid module ID format (must be UUID)",
        ) from e

    try:
        dto = UpdateModuleDTO(
            name=request.name,
            description=request.description,
            category=request.category,
            status=request.status,
            features=request.features,
            pricing_tier=request.pricing_tier,
        )

        use_case = UpdateModuleUseCase(db)
        result = await use_case.execute(uuid_id, dto, sync_to_rag=sync_to_rag)

        logger.info(f"Updated module: {result.code}")
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception(f"Error updating module {module_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update module: {e!s}",
        ) from e


@router.delete(
    "/{module_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete software module",
    description="Delete a software module (soft delete by default)",
)
async def delete_module(
    module_id: str,
    hard_delete: bool = Query(False, description="Permanently delete instead of soft delete"),
    db: AsyncSession = Depends(get_async_db),
) -> None:
    """
    Delete a software module.

    By default, performs a soft delete (sets active=False).
    Use hard_delete=true to permanently remove.

    Args:
        module_id: Module UUID
        hard_delete: If true, permanently delete

    Raises:
        HTTPException 404: If module not found
    """
    try:
        uuid_id = UUID(module_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid module ID format (must be UUID)",
        ) from e

    try:
        use_case = DeleteModuleUseCase(db)
        deleted = await use_case.execute(uuid_id, hard_delete=hard_delete)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Module '{module_id}' not found",
            )

        logger.info(f"Deleted module: {module_id} (hard={hard_delete})")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting module {module_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete module: {e!s}",
        ) from e


@router.post(
    "/sync-rag",
    response_model=SyncResultResponse,
    summary="Sync all modules to RAG",
    description="Sync all modules to company_knowledge for chatbot access",
)
async def sync_modules_to_rag(
    db: AsyncSession = Depends(get_async_db),
) -> SyncResultResponse:
    """
    Sync all modules to company_knowledge for RAG.

    Useful for initial migration or re-sync after manual changes.

    Returns:
        SyncResultResponse with summary
    """
    try:
        use_case = SyncAllModulesToRagUseCase(db)
        result = await use_case.execute()

        return SyncResultResponse(
            total=result["total"],
            synced=result["synced"],
            failed=result["failed"],
            message=f"Synced {result['synced']}/{result['total']} modules to RAG",
        )

    except Exception as e:
        logger.exception(f"Error syncing modules to RAG: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync modules: {e!s}",
        ) from e
