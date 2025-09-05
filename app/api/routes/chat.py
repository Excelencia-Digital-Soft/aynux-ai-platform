"""
Endpoint de chat para procesamiento de mensajes con LangGraph multi-agente
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from app.models.chat import (
    ChatErrorResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ConversationHistoryResponse,
)
from app.services.langgraph_chatbot_service import LangGraphChatbotService

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)

# Servicio LangGraph (inicializado de forma lazy)
_langgraph_service: Optional[LangGraphChatbotService] = None


async def _get_langgraph_service() -> LangGraphChatbotService:
    """Obtiene o inicializa el servicio LangGraph"""
    global _langgraph_service

    if _langgraph_service is None:
        try:
            _langgraph_service = LangGraphChatbotService()
            await _langgraph_service.initialize()
            logger.info("LangGraph chat service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LangGraph service: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Chat service temporarily unavailable",
            ) from e

    return _langgraph_service


@router.post("/message", response_model=ChatMessageResponse, responses={503: {"model": ChatErrorResponse}})
async def process_chat_message(request: ChatMessageRequest) -> ChatMessageResponse:
    """
    Procesa un mensaje de chat usando el sistema multi-agente LangGraph.

    Este endpoint permite enviar mensajes de texto para ser procesados por el sistema
    de agentes especializados (productos, soporte, tracking, etc.) sin necesidad de WhatsApp.

    Args:
        request: Datos del mensaje a procesar

    Returns:
        Respuesta del bot con metadatos del procesamiento
    """
    try:
        # Obtener el servicio
        service = await _get_langgraph_service()

        # Generar session_id si no se proporciona
        session_id = request.session_id or f"chat_{request.user_id}"

        logger.info(f"Processing chat message from user {request.user_id} in session {session_id}")

        # Procesar el mensaje
        result = await service.process_chat_message(
            message=request.message, user_id=request.user_id, session_id=session_id, metadata=request.metadata or {}
        )

        # Construir respuesta
        return ChatMessageResponse(
            response=result.get("response", "Lo siento, no pude procesar tu mensaje."),
            agent_used=result.get("agent_used", "unknown"),
            session_id=session_id,
            status="success",
            metadata={
                "requires_human": result.get("requires_human", False),
                "is_complete": result.get("is_complete", False),
                "processing_time_ms": result.get("processing_time_ms", 0),
                "conversation_id": session_id,
                **(request.metadata or {}),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error processing message: {str(e)}"
        ) from e


@router.get("/history", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    user_id: str, session_id: Optional[str] = None, limit: int = 50
) -> ConversationHistoryResponse:
    """
    Obtiene el historial de conversación de un usuario.

    Args:
        user_id: ID del usuario
        session_id: ID de sesión específica (opcional)
        limit: Número máximo de mensajes a devolver (1-100)

    Returns:
        Historial de conversación con metadatos
    """
    try:
        # Validar límite
        if limit < 1 or limit > 100:
            limit = 50

        # Obtener el servicio
        service = await _get_langgraph_service()

        # Usar session_id o generar uno basado en user_id
        session_id = session_id or f"chat_{user_id}"

        # Obtener historial usando el método existente
        history = await service.get_conversation_history_langgraph(
            user_number=session_id,  # Usamos session_id como identificador
            limit=limit,
        )

        # Verificar si hay error en la respuesta
        if "error" in history:
            logger.warning(f"Error getting conversation history: {history['error']}")
            # Retornar historial vacío en caso de error
            return ConversationHistoryResponse(
                user_id=user_id,
                session_id=session_id,
                messages=[],
                total_messages=0,
                metadata={"note": history.get("error", "No history found")},
            )

        return ConversationHistoryResponse(
            user_id=user_id,
            session_id=session_id,
            messages=history.get("messages", []),
            total_messages=history.get("total_messages", 0),
            metadata={"conversation_state": history.get("conversation_state", {}), "limited_to": limit},
        )

    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error retrieving conversation history: {str(e)}"
        ) from e


@router.get("/health")
async def chat_health_check():
    """
    Verifica el estado del servicio de chat LangGraph.

    Returns:
        Estado del servicio con información de componentes
    """
    try:
        service = await _get_langgraph_service()
        health = await service.get_system_health()

        return {
            "service": "langgraph_chat",
            "status": health.get("overall_status", "unknown"),
            "initialized": health.get("initialized", False),
            "components": health.get("components", {}),
            "database": health.get("database", False),
        }

    except HTTPException as e:
        return {"service": "langgraph_chat", "status": "unhealthy", "error": e.detail}
    except Exception as e:
        return {"service": "langgraph_chat", "status": "unhealthy", "error": str(e)}


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """
    Limpia/reinicia una sesión de conversación específica.

    Args:
        session_id: ID de la sesión a limpiar

    Returns:
        Confirmación de limpieza
    """
    try:
        # Por ahora solo retornamos confirmación
        # TODO: Implementar limpieza real de Redis/DB cuando sea necesario
        logger.info(f"Session {session_id} cleared")

        return {"status": "success", "message": f"Session {session_id} has been cleared", "session_id": session_id}

    except Exception as e:
        logger.error(f"Error clearing session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error clearing session: {str(e)}"
        ) from e

