"""
API de administración para gestión de agentes del sistema multi-agente

Proporciona endpoints para:
- Consultar estado de agentes habilitados/deshabilitados
- Ver configuración actual de agentes
- Obtener estadísticas de agentes

NOTA: La habilitación/deshabilitación de agentes requiere modificar la configuración
ENABLED_AGENTS en .env y reiniciar el servicio. No se soporta hot-reload de agentes.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.langgraph_chatbot_service import LangGraphChatbotService

router = APIRouter(prefix="/api/v1/admin/agents", tags=["agents-admin"])
logger = logging.getLogger(__name__)


# ============================================================
# PYDANTIC MODELS
# ============================================================


class AgentStatusResponse(BaseModel):
    """Response model for agent status"""

    enabled_agents: List[str] = Field(..., description="List of enabled agent names")
    disabled_agents: List[str] = Field(..., description="List of disabled agent names")
    enabled_count: int = Field(..., description="Number of enabled agents")
    disabled_count: int = Field(..., description="Number of disabled agents")
    total_possible_agents: int = Field(..., description="Total number of possible agents")


class AgentListResponse(BaseModel):
    """Response model for agent list"""

    agents: List[str] = Field(..., description="List of agent names")
    count: int = Field(..., description="Number of agents")


class AgentDetailResponse(BaseModel):
    """Response model for individual agent details"""

    agent_name: str = Field(..., description="Agent name")
    enabled: bool = Field(..., description="Whether agent is enabled")
    description: str = Field(..., description="Agent description")


class SystemConfigResponse(BaseModel):
    """Response model for system configuration"""

    enabled_agents: List[str] = Field(..., description="Configured enabled agents")
    system_initialized: bool = Field(..., description="Whether graph system is initialized")


# ============================================================
# DEPENDENCY
# ============================================================


async def get_chatbot_service() -> LangGraphChatbotService:
    """Get initialized LangGraph chatbot service"""
    service = LangGraphChatbotService()
    if not service._initialized:
        await service.initialize()
    return service


# ============================================================
# ENDPOINTS
# ============================================================


@router.get("/status", response_model=AgentStatusResponse)
async def get_agent_status(service: LangGraphChatbotService = Depends(get_chatbot_service)):  # noqa: B008
    """
    Get complete agent status information.

    Returns:
        AgentStatusResponse with enabled/disabled agents and statistics
    """
    try:
        if not service.graph_system:
            raise HTTPException(status_code=503, detail="Graph system not initialized")

        status = service.graph_system.get_agent_status()

        return AgentStatusResponse(
            enabled_agents=status["enabled_agents"],
            disabled_agents=status["disabled_agents"],
            enabled_count=status["enabled_count"],
            disabled_count=status["disabled_count"],
            total_possible_agents=status["total_possible_agents"],
        )

    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting agent status: {str(e)}") from e


@router.get("/enabled", response_model=AgentListResponse)
async def get_enabled_agents(service: LangGraphChatbotService = Depends(get_chatbot_service)):  # noqa: B008
    """
    Get list of all enabled agents.

    Returns:
        AgentListResponse with list of enabled agent names
    """
    try:
        if not service.graph_system:
            raise HTTPException(status_code=503, detail="Graph system not initialized")

        enabled = service.graph_system.get_enabled_agents()

        return AgentListResponse(agents=enabled, count=len(enabled))

    except Exception as e:
        logger.error(f"Error getting enabled agents: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting enabled agents: {str(e)}") from e


@router.get("/disabled", response_model=AgentListResponse)
async def get_disabled_agents(service: LangGraphChatbotService = Depends(get_chatbot_service)):  # noqa: B008
    """
    Get list of all disabled agents.

    Returns:
        AgentListResponse with list of disabled agent names
    """
    try:
        if not service.graph_system:
            raise HTTPException(status_code=503, detail="Graph system not initialized")

        disabled = service.graph_system.get_disabled_agents()

        return AgentListResponse(agents=disabled, count=len(disabled))

    except Exception as e:
        logger.error(f"Error getting disabled agents: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting disabled agents: {str(e)}") from e


@router.get("/config", response_model=SystemConfigResponse)
async def get_agent_config(service: LangGraphChatbotService = Depends(get_chatbot_service)):  # noqa: B008
    """
    Get current agent configuration.

    Returns:
        SystemConfigResponse with configured enabled agents
    """
    try:
        if not service.graph_system:
            raise HTTPException(status_code=503, detail="Graph system not initialized")

        return SystemConfigResponse(
            enabled_agents=service.graph_system.enabled_agents, system_initialized=service._initialized
        )

    except Exception as e:
        logger.error(f"Error getting agent config: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting agent config: {str(e)}") from e


@router.get("/check/{agent_name}")
async def check_agent_enabled(
    agent_name: str, service: LangGraphChatbotService = Depends(get_chatbot_service)
):  # noqa: B008
    """
    Check if a specific agent is enabled.

    Args:
        agent_name: Name of the agent to check

    Returns:
        Dict with agent name and enabled status
    """
    try:
        if not service.graph_system:
            raise HTTPException(status_code=503, detail="Graph system not initialized")

        enabled = service.graph_system.is_agent_enabled(agent_name)

        return {"agent_name": agent_name, "enabled": enabled, "timestamp": service.graph_system.config.get("timestamp")}

    except Exception as e:
        logger.error(f"Error checking agent {agent_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Error checking agent: {str(e)}") from e
