"""
Endpoint de chat para procesamiento de mensajes con nueva arquitectura Clean Architecture.

Este módulo maneja el procesamiento de mensajes usando SuperOrchestrator que rutea
a los agentes especializados de cada dominio (e-commerce, credit, healthcare, etc.).

NOTE: Mantiene compatibilidad con LangGraphChatbotService para transición gradual.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_super_orchestrator
from app.models.chat import (
    ChatErrorResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatStreamEvent,
    ChatStreamRequest,
    ConversationHistoryResponse,
)
from app.orchestration import SuperOrchestrator
from app.services.langgraph_chatbot_service import LangGraphChatbotService

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)

# Legacy service (para transición gradual)
_langgraph_service: Optional[LangGraphChatbotService] = None


async def _get_langgraph_service() -> LangGraphChatbotService:
    """
    Obtiene o inicializa el servicio LangGraph legacy.

    DEPRECATED: Este servicio será eliminado en versión futura.
    Usar SuperOrchestrator (nueva arquitectura) en su lugar.
    """
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
    Procesa un mensaje de chat usando el sistema multi-agente LangGraph (LEGACY).

    DEPRECATED: Este endpoint usa la arquitectura legacy.
    Se recomienda usar /v2/message que usa Clean Architecture.

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
        # Combinar metadata del resultado con metadata del request
        combined_metadata = {
            "requires_human": result.get("requires_human", False),
            "is_complete": result.get("is_complete", False),
            "processing_time_ms": result.get("processing_time_ms", 0),
            "conversation_id": session_id,
            **(request.metadata or {}),
            # IMPORTANTE: Incluir metadata del resultado (productos, display_type, etc.)
            **(result.get("metadata", {})),
        }

        return ChatMessageResponse(
            response=result.get("response", "Lo siento, no pude procesar tu mensaje."),
            agent_used=result.get("agent_used", "unknown"),
            session_id=session_id,
            status="success",
            metadata=combined_metadata,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error processing message: {str(e)}"
        ) from e


@router.post("/v2/message", response_model=ChatMessageResponse, responses={503: {"model": ChatErrorResponse}})
async def process_chat_message_v2(
    request: ChatMessageRequest,
    orchestrator: SuperOrchestrator = Depends(get_super_orchestrator),
) -> ChatMessageResponse:
    """
    Procesa un mensaje de chat usando Clean Architecture + DDD.

    Este endpoint usa SuperOrchestrator que rutea mensajes a agentes especializados
    por dominio (e-commerce, credit, healthcare, etc.) siguiendo principios SOLID.

    Ventajas sobre /message:
    - Clean Architecture con separación de capas
    - SOLID principles aplicados
    - Dependency Injection
    - Testeable con mocks
    - Extensible para nuevos dominios

    Args:
        request: Datos del mensaje a procesar
        orchestrator: SuperOrchestrator (inyectado automáticamente)

    Returns:
        Respuesta del bot con metadatos del procesamiento
    """
    try:
        # Generar session_id si no se proporciona
        session_id = request.session_id or f"chat_{request.user_id}"

        logger.info(
            f"[V2] Processing chat message from user {request.user_id} in session {session_id}: {request.message[:50]}..."
        )

        # Crear state para SuperOrchestrator
        state = {
            "messages": [{"role": "user", "content": request.message}],
            "user_id": request.user_id,
            "session_id": session_id,
            "metadata": request.metadata or {},
        }

        # Rutear mensaje al dominio apropiado
        result = await orchestrator.route_message(state)

        # Extraer respuesta del asistente
        messages = result.get("messages", [])
        assistant_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                assistant_message = msg.get("content", "")
                break

        if not assistant_message:
            assistant_message = "Lo siento, no pude procesar tu mensaje."

        # Extraer metadata de routing
        routing = result.get("routing", {})
        detected_domain = routing.get("detected_domain", "unknown")
        agent_used = routing.get("agent_used", "unknown")

        # Combinar metadata
        combined_metadata = {
            "domain": detected_domain,
            "agent": agent_used,
            "orchestrator": "super_orchestrator_v2",
            "architecture": "clean_architecture",
            "session_id": session_id,
            **(request.metadata or {}),
            # Incluir datos recuperados (productos, crédito, etc.)
            **(result.get("retrieved_data", {})),
        }

        logger.info(f"[V2] Message routed to domain '{detected_domain}', agent '{agent_used}'")

        return ChatMessageResponse(
            response=assistant_message,
            agent_used=agent_used,
            session_id=session_id,
            status="success",
            metadata=combined_metadata,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[V2] Error processing chat message: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error processing message: {str(e)}"
        ) from e


@router.post("/message/stream")
async def process_chat_message_stream(request: ChatStreamRequest):
    """
    Procesa un mensaje de chat usando el sistema multi-agente LangGraph con streaming en tiempo real.

    Este endpoint utiliza Server-Sent Events (SSE) para enviar actualizaciones de progreso
    en tiempo real mientras los agentes especializados procesan la consulta.

    Args:
        request: Datos del mensaje para procesamiento con streaming

    Returns:
        StreamingResponse con eventos de progreso en formato SSE
    """
    try:
        # Obtener el servicio
        service = await _get_langgraph_service()

        # Generar session_id si no se proporciona
        session_id = request.session_id or f"chat_{request.user_id}"

        logger.info(f"Processing streaming chat message from user {request.user_id} in session {session_id}")

        # Crear generador de eventos SSE
        async def generate_sse_stream():
            """Generador de eventos Server-Sent Events"""
            try:
                # Procesar el mensaje con streaming
                async for stream_event in service.process_chat_message_stream(
                    message=request.message,
                    user_id=request.user_id,
                    session_id=session_id,
                    metadata=request.metadata or {},
                ):
                    # Convertir el evento a formato SSE
                    event_data = stream_event.model_dump()

                    # Formato Server-Sent Events
                    sse_event = f"data: {json.dumps(event_data)}\n\n"
                    yield sse_event.encode("utf-8")

                    # Si es el evento final, terminamos
                    if stream_event.event_type.value == "complete" or stream_event.event_type.value == "error":
                        break

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error in streaming: {str(e)}")
                # Enviar evento de error en formato SSE
                error_event = ChatStreamEvent(
                    event_type="error",
                    message=f"❌ Error procesando tu mensaje: {str(e)}",
                    agent_current="fallback",
                    progress=0.0,
                    metadata={"error": str(e)},
                    timestamp="",
                )
                error_data = error_event.model_dump()
                sse_event = f"data: {json.dumps(error_data)}\n\n"
                yield sse_event.encode("utf-8")

        # Devolver respuesta streaming con headers SSE apropiados
        return StreamingResponse(
            generate_sse_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Desactivar buffering en nginx
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting up chat message stream: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error setting up message stream: {str(e)}"
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
    Verifica el estado del servicio de chat LangGraph (LEGACY).

    DEPRECATED: Usar /v2/health para nueva arquitectura.

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


@router.get("/v2/health")
async def chat_health_check_v2(orchestrator: SuperOrchestrator = Depends(get_super_orchestrator)):
    """
    Verifica el estado del servicio de chat con Clean Architecture.

    Revisa la salud de SuperOrchestrator y todos los agentes de dominio registrados.

    Args:
        orchestrator: SuperOrchestrator (inyectado automáticamente)

    Returns:
        Estado del servicio con información de todos los dominios
    """
    try:
        # Obtener health check del orchestrator
        health = await orchestrator.health_check()

        # Obtener dominios disponibles
        available_domains = await orchestrator.get_available_domains()

        return {
            "service": "super_orchestrator_v2",
            "status": "healthy" if health.get("orchestrator") == "healthy" else "unhealthy",
            "architecture": "clean_architecture",
            "orchestrator": health.get("orchestrator"),
            "domains": health.get("domains", {}),
            "available_domains": available_domains,
            "total_domains": len(available_domains),
        }

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return {
            "service": "super_orchestrator_v2",
            "status": "unhealthy",
            "error": str(e),
        }


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
