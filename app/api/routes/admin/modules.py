"""
Software Modules API - Frontend-compatible endpoint.

Provides RESTful API for software modules catalog (Excelencia).
Transforms backend Dict format to frontend Array format.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.domains.shared.application.use_cases.agent_config_use_case import (
    GetAgentConfigUseCase,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/modules", tags=["Software Modules"])


# ============================================================================
# Response Models (compatible with frontend SoftwareModule interface)
# ============================================================================


class SoftwareModuleResponse(BaseModel):
    """Response model matching frontend SoftwareModule interface."""

    id: str = Field(..., description="Module unique identifier")
    code: str = Field(..., description="Module code prefix")
    name: str = Field(..., description="Module name")
    description: str = Field(..., description="Module description")
    category: str = Field(..., description="Module category")
    status: str = Field(default="active", description="Module status")
    features: list[str] = Field(default_factory=list, description="Module features")
    pricing_tier: str = Field(default="standard", description="Pricing tier")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


# ============================================================================
# Transformation Logic
# ============================================================================

# Mapping: backend target -> frontend category
TARGET_TO_CATEGORY: dict[str, str] = {
    "healthcare": "salud",
    "hospitality": "hotelería",
    "finance": "financiero",
    "guilds": "gremios",
    "products": "productos",
    "public_services": "servicios públicos",
}


def _extract_code_prefix(module_id: str) -> str:
    """Extract code prefix from module ID (e.g., 'HC-001' -> 'HC')."""
    if "-" in module_id:
        return module_id.split("-")[0]
    return module_id[:2].upper() if len(module_id) >= 2 else module_id.upper()


def _map_target_to_category(target: str) -> str:
    """Map backend target to frontend category."""
    return TARGET_TO_CATEGORY.get(target.lower(), "general")


def _transform_module(module_id: str, module_data: dict[str, Any]) -> SoftwareModuleResponse:
    """Transform backend module dict to frontend SoftwareModule format."""
    now = datetime.now(UTC).isoformat()

    return SoftwareModuleResponse(
        id=module_id,
        code=_extract_code_prefix(module_id),
        name=module_data.get("name", ""),
        description=module_data.get("description", ""),
        category=_map_target_to_category(module_data.get("target", "general")),
        status="active",
        features=module_data.get("features", []),
        pricing_tier="standard",
        created_at=now,
        updated_at=now,
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "",
    response_model=list[SoftwareModuleResponse],
    summary="Get all software modules",
    description="Get list of software modules in frontend-compatible format",
)
async def get_modules(
    category: str | None = Query(None, description="Filter by category"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    search: str | None = Query(None, description="Search in name/description"),
) -> list[SoftwareModuleResponse]:
    """
    Get list of software modules.

    Transforms backend module dict format to frontend SoftwareModule array.

    Query Parameters:
    - **category**: Filter by category (salud, hotelería, etc.)
    - **status**: Filter by status (active, beta, etc.)
    - **search**: Search term for name/description

    Returns:
        List of SoftwareModuleResponse objects
    """
    try:
        use_case = GetAgentConfigUseCase()
        config = await use_case.execute()

        modules_dict: dict[str, Any] = config.get("modules", {})

        # Transform dict to array
        modules: list[SoftwareModuleResponse] = [
            _transform_module(module_id, module_data) for module_id, module_data in modules_dict.items()
        ]

        # Apply filters
        if category:
            modules = [m for m in modules if m.category == category]

        if status_filter:
            modules = [m for m in modules if m.status == status_filter]

        if search:
            search_lower = search.lower()
            modules = [m for m in modules if search_lower in m.name.lower() or search_lower in m.description.lower()]

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
    response_model=SoftwareModuleResponse,
    summary="Get single module",
    description="Get a single software module by ID",
)
async def get_module(module_id: str) -> SoftwareModuleResponse:
    """
    Get a single software module by ID.

    Args:
        module_id: Module identifier (e.g., "HC-001")

    Returns:
        SoftwareModuleResponse object

    Raises:
        HTTPException 404: If module not found
    """
    try:
        use_case = GetAgentConfigUseCase()
        config = await use_case.execute()

        modules_dict: dict[str, Any] = config.get("modules", {})

        if module_id not in modules_dict:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Module '{module_id}' not found",
            )

        return _transform_module(module_id, modules_dict[module_id])

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting module {module_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get module: {e!s}",
        ) from e
