"""
Agent Configuration API Endpoints

RESTful API for managing agent configuration (Excelencia agent).

Follows Clean Architecture:
- Uses Agent Config Use Cases
- Thin controllers
- Proper error handling
"""

import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.domains.shared.application.use_cases import (
    GetAgentConfigUseCase,
    UpdateAgentModulesUseCase,
    UpdateAgentSettingsUseCase,
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/v1/admin/agent-config",
    tags=["Agent Configuration"],
)


# ============================================================================
# Request/Response Models
# ============================================================================


class ModuleConfig(BaseModel):
    """Configuration for a single agent module."""

    name: str = Field(..., description="Module name")
    description: str = Field(..., description="Module description")
    features: list[str] = Field(..., description="List of features")
    target: str = Field(..., description="Target audience")


class UpdateModulesRequest(BaseModel):
    """Request model for updating agent modules."""

    modules: Dict[str, ModuleConfig] = Field(..., description="Modules configuration")
    create_backup: bool = Field(True, description="Create backup before update")


class AgentSettingsUpdate(BaseModel):
    """Request model for updating agent settings."""

    model: Optional[str] = Field(None, description="LLM model name")
    temperature: Optional[float] = Field(None, ge=0.0, le=1.0, description="Temperature")
    max_response_length: Optional[int] = Field(None, ge=100, le=2000, description="Max response length")
    use_rag: Optional[bool] = Field(None, description="Enable RAG")
    rag_max_results: Optional[int] = Field(None, ge=1, le=10, description="RAG results limit")


class ConfigResponse(BaseModel):
    """Response model for agent configuration."""

    modules: Dict[str, Any]
    query_types: Dict[str, list[str]]
    settings: Dict[str, Any]
    available_document_types: list[str]


class UpdateResponse(BaseModel):
    """Response model for configuration updates."""

    success: bool
    message: str
    backup_path: Optional[str] = None
    requires_restart: bool = False


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "/excelencia",
    response_model=ConfigResponse,
    summary="Get Excelencia agent configuration",
    description="Get current configuration for Excelencia agent",
)
async def get_excelencia_config():
    """
    Get current Excelencia agent configuration.

    Returns:
    - **modules**: Dictionary of agent modules
    - **query_types**: Query type keyword mappings
    - **settings**: Agent settings (model, temperature, etc.)
    - **available_document_types**: Supported document types for knowledge base
    """
    try:
        use_case = GetAgentConfigUseCase()
        config = await use_case.execute()
        return ConfigResponse(**config)

    except Exception as e:
        logger.error(f"Error getting agent config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent configuration: {str(e)}",
        )


@router.put(
    "/excelencia/modules",
    response_model=UpdateResponse,
    summary="Update Excelencia agent modules",
    description="Update module configuration for Excelencia agent",
)
async def update_excelencia_modules(request: UpdateModulesRequest):
    """
    Update Excelencia agent modules configuration.

    **WARNING**: This modifies the Python source file and requires application restart.

    **Parameters:**
    - **modules**: Dictionary of modules with their configuration
    - **create_backup**: Whether to create backup before update (recommended)

    **Example Request:**
    ```json
    {
      "modules": {
        "historia_clinica": {
          "name": "Historia Clínica Electrónica",
          "description": "Sistema completo de historias clínicas",
          "features": ["Registro de pacientes", "Consultas médicas"],
          "target": "Hospitales, Clínicas"
        }
      },
      "create_backup": true
    }
    ```

    **Returns:**
    - Success status
    - Number of modules updated
    - Backup file path
    - Restart requirement notice
    """
    try:
        # Convert Pydantic models to dicts
        modules_dict = {module_id: module_config.model_dump() for module_id, module_config in request.modules.items()}

        use_case = UpdateAgentModulesUseCase()
        result = await use_case.execute(
            modules=modules_dict,
            create_backup=request.create_backup,
        )

        return UpdateResponse(
            success=result["success"],
            message=result["message"],
            backup_path=result.get("backup_path"),
            requires_restart=result["requires_restart"],
        )

    except ValueError as e:
        logger.error(f"Validation error updating modules: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error updating agent modules: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update agent modules: {str(e)}",
        )


@router.patch(
    "/excelencia/settings",
    response_model=UpdateResponse,
    summary="Update Excelencia agent settings",
    description="Update runtime settings for Excelencia agent",
)
async def update_excelencia_settings(request: AgentSettingsUpdate):
    """
    Update Excelencia agent settings.

    **Note**: This is currently a validation-only endpoint.
    For production, implement database-backed configuration storage.

    **Parameters:**
    - **model**: LLM model name (optional)
    - **temperature**: Temperature 0.0-1.0 (optional)
    - **max_response_length**: Max response length 100-2000 (optional)
    - **use_rag**: Enable RAG (optional)
    - **rag_max_results**: Number of RAG results 1-10 (optional)

    **Example Request:**
    ```json
    {
      "model": "llama3.1",
      "temperature": 0.7,
      "max_response_length": 500,
      "use_rag": true,
      "rag_max_results": 3
    }
    ```
    """
    try:
        # Filter out None values
        settings_dict = {k: v for k, v in request.model_dump().items() if v is not None}

        use_case = UpdateAgentSettingsUseCase()
        result = await use_case.execute(settings=settings_dict)

        return UpdateResponse(
            success=result["success"],
            message=result["message"],
            requires_restart=False,
        )

    except ValueError as e:
        logger.error(f"Validation error updating settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error updating agent settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update agent settings: {str(e)}",
        )


@router.get(
    "/excelencia/modules",
    summary="Get Excelencia modules",
    description="Get list of Excelencia agent modules",
)
async def get_excelencia_modules():
    """
    Get list of Excelencia agent modules.

    Returns simplified list of modules with basic information.
    """
    try:
        use_case = GetAgentConfigUseCase()
        config = await use_case.execute()

        return {
            "modules": config["modules"],
            "total_modules": len(config["modules"]),
        }

    except Exception as e:
        logger.error(f"Error getting modules: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get modules: {str(e)}",
        )


@router.get(
    "/excelencia/settings",
    summary="Get Excelencia settings",
    description="Get current Excelencia agent settings",
)
async def get_excelencia_settings():
    """
    Get current Excelencia agent settings.

    Returns current agent settings (model, temperature, etc.).
    """
    try:
        use_case = GetAgentConfigUseCase()
        config = await use_case.execute()

        return {
            "settings": config["settings"],
        }

    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get settings: {str(e)}",
        )
