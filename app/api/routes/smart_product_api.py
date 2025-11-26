"""
Smart Product API - Integración de FastAPI para búsquedas inteligentes de productos.

Este módulo proporciona endpoints para interactuar con el ProductAgent (RefactoredProductAgent)
desde WhatsApp y otras interfaces conversacionales.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from app.integrations.llm import OllamaLLM
from app.domains.ecommerce.agents.nodes.product_node import ProductNode as ProductAgent
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


# Modelos Pydantic para las APIs
class ProductSearchRequest(BaseModel):
    """Request para búsqueda de productos."""

    message: str = Field(..., description="Mensaje del usuario en lenguaje natural")
    user_id: Optional[str] = Field(None, description="ID del usuario")
    phone_number: Optional[str] = Field(None, description="Número de teléfono del usuario")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Contexto adicional")
    max_results: Optional[int] = Field(10, description="Máximo número de resultados")
    enable_ai_response: Optional[bool] = Field(True, description="Generar respuesta con AI")


class ProductSearchResponse(BaseModel):
    """Response de búsqueda de productos."""

    success: bool
    message: str
    products: List[Dict[str, Any]] = Field(default_factory=list)
    total_found: int = 0
    search_metadata: Dict[str, Any] = Field(default_factory=dict)
    processing_time_ms: float = 0.0
    user_id: Optional[str] = None


class WhatsAppMessageRequest(BaseModel):
    """Request simulando un mensaje de WhatsApp."""

    from_number: str = Field(..., description="Número del remitente")
    message_body: str = Field(..., description="Contenido del mensaje")
    message_id: str = Field(..., description="ID único del mensaje")
    timestamp: Optional[datetime] = Field(default_factory=datetime.now)


class WhatsAppMessageResponse(BaseModel):
    """Response para WhatsApp."""

    success: bool
    response_message: str
    should_end_conversation: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Router principal
router = APIRouter(prefix="/api/v1/smart-products", tags=["Smart Products"])


# Cache Redis para conversaciones
async def get_redis_client() -> redis.Redis:
    """Obtiene cliente Redis para cache."""
    settings = get_settings()
    redis_url = settings.redis_url() if callable(settings.redis_url) else str(settings.redis_url)
    return redis.from_url(redis_url, decode_responses=True)


async def get_product_agent() -> ProductAgent:
    """Dependency para obtener instancia del agente (RefactoredProductAgent)."""
    ollama = OllamaLLM()
    return ProductAgent(ollama=ollama)


@router.post("/search", response_model=ProductSearchResponse)
async def search_products(
    request: ProductSearchRequest,
    agent: ProductAgent = Depends(get_product_agent),  # noqa: B008
    background_tasks: BackgroundTasks = BackgroundTasks(),  # noqa: B008
) -> ProductSearchResponse:
    """
    Endpoint principal para búsqueda inteligente de productos.

    Permite buscar productos usando lenguaje natural y obtener respuestas inteligentes.
    """
    start_time = datetime.now()

    try:
        # Preparar estado inicial
        state_dict = {
            "user_id": request.user_id or request.phone_number,
            "phone_number": request.phone_number,
            "context": request.context,
            "max_results": request.max_results,
            "timestamp": start_time.isoformat(),
        }

        # Procesar con el agente inteligente
        result = await agent._process_internal(request.message, state_dict)

        # Extraer datos del resultado
        success = not result.get("error_count", 0) > 0
        ai_message = ""
        products = []
        metadata = {}

        if result.get("messages"):
            ai_message = result["messages"][0].get("content", "")

        retrieved_data = result.get("retrieved_data", {})
        products = retrieved_data.get("products", [])
        metadata = {
            "intent": retrieved_data.get("intent", {}),
            "search_method": retrieved_data.get("search_method", "unknown"),
            "agent": result.get("current_agent", "smart_product_agent"),
        }

        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        # Logging para análisis
        background_tasks.add_task(
            log_search_analytics, request.message, request.user_id, len(products), processing_time, metadata
        )

        return ProductSearchResponse(
            success=success,
            message=ai_message if request.enable_ai_response else "Búsqueda completada",
            products=products,
            total_found=len(products),
            search_metadata=metadata,
            processing_time_ms=processing_time,
            user_id=request.user_id,
        )

    except Exception as e:
        logger.error(f"Error in product search: {e}")
        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        return ProductSearchResponse(
            success=False,
            message="Disculpa, hubo un problema con tu búsqueda. ¿Podrías intentar de nuevo?",
            products=[],
            total_found=0,
            search_metadata={"error": str(e)},
            processing_time_ms=processing_time,
            user_id=request.user_id,
        )


@router.post("/whatsapp/message", response_model=WhatsAppMessageResponse)
async def handle_whatsapp_message(
    request: WhatsAppMessageRequest,
    agent: ProductAgent = Depends(get_product_agent),  # noqa: B008
    redis_client: redis.Redis = Depends(get_redis_client),  # noqa: B008
) -> WhatsAppMessageResponse:
    """
    Endpoint para manejar mensajes de WhatsApp.

    Simula la integración completa con WhatsApp Business API.
    """
    try:
        # Obtener contexto de conversación desde Redis
        conversation_key = f"whatsapp:conversation:{request.from_number}"
        conversation_context = await get_conversation_context(redis_client, conversation_key)

        # Preparar estado para el agente
        state_dict = {
            "user_id": request.from_number,
            "phone_number": request.from_number,
            "message_id": request.message_id,
            "conversation_history": conversation_context.get("history", []),
            "timestamp": request.timestamp.isoformat() if request.timestamp else "",
        }

        # Procesar mensaje con el agente
        result = await agent._process_internal(request.message_body, state_dict)

        # Extraer respuesta
        success = not result.get("error_count", 0) > 0
        response_message = ""

        if result.get("messages"):
            response_message = result["messages"][0].get("content", "")

        if not response_message:
            response_message = "Disculpa, no pude procesar tu mensaje. ¿Podrías reformularlo?"

        # Actualizar contexto de conversación
        await update_conversation_context(
            redis_client, conversation_key, request.message_body, response_message, result.get("retrieved_data", {})
        )

        # Determinar si debe terminar la conversación
        should_end = await should_end_conversation(request.message_body, response_message)

        return WhatsAppMessageResponse(
            success=success,
            response_message=response_message,
            should_end_conversation=should_end,
            metadata={
                "agent_used": result.get("current_agent", "smart_product_agent"),
                "products_found": len(result.get("retrieved_data", {}).get("products", [])),
                "intent": result.get("retrieved_data", {}).get("intent", {}),
            },
        )

    except Exception as e:
        logger.error(f"Error handling WhatsApp message: {e}")

        return WhatsAppMessageResponse(
            success=False,
            response_message="Disculpa, tuve un problema técnico. ¿Podrías intentar de nuevo en unos momentos?",
            should_end_conversation=False,
            metadata={"error": str(e)},
        )


@router.get("/conversation/{phone_number}")
async def get_conversation_history(
    phone_number: str,
    redis_client: redis.Redis = Depends(get_redis_client),  # noqa: B008
) -> Dict[str, Any]:
    """
    Obtiene el historial de conversación de un número.
    """
    try:
        conversation_key = f"whatsapp:conversation:{phone_number}"
        context = await get_conversation_context(redis_client, conversation_key)

        return {
            "success": True,
            "phone_number": phone_number,
            "conversation_history": context.get("history", []),
            "last_activity": context.get("last_activity"),
            "total_messages": len(context.get("history", [])),
        }

    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving conversation history") from e


@router.delete("/conversation/{phone_number}")
async def clear_conversation(
    phone_number: str,
    redis_client: redis.Redis = Depends(get_redis_client),  # noqa: B008
) -> Dict[str, Any]:
    """
    Limpia el historial de conversación de un número.
    """
    try:
        conversation_key = f"whatsapp:conversation:{phone_number}"
        await redis_client.delete(conversation_key)

        return {"success": True, "message": f"Conversación de {phone_number} eliminada"}

    except Exception as e:
        logger.error(f"Error clearing conversation: {e}")
        raise HTTPException(status_code=500, detail="Error clearing conversation") from e


@router.get("/health")
async def health_check(agent: ProductAgent = Depends(get_product_agent)) -> Dict[str, Any]:  # noqa: B008
    """
    Health check del sistema de productos inteligentes.
    """
    try:
        # Test básico del agente usando health_check method
        test_result = await agent.health_check()

        return {
            "status": "healthy" if test_result.get("healthy", False) else "degraded",
            "timestamp": datetime.now().isoformat(),
            "agent": "refactored_product_agent",
            "health_details": test_result,
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy") from e


# Funciones auxiliares


async def get_conversation_context(redis_client: redis.Redis, conversation_key: str) -> Dict[str, Any]:
    """
    Obtiene contexto de conversación desde Redis.
    """
    try:
        context_data = await redis_client.get(conversation_key)
        if context_data:
            import json

            return json.loads(context_data)
        else:
            return {"history": [], "last_activity": None}
    except Exception as e:
        logger.warning(f"Could not get conversation context: {e}")
        return {"history": [], "last_activity": None}


async def update_conversation_context(
    redis_client: redis.Redis, conversation_key: str, user_message: str, bot_response: str, metadata: Dict[str, Any]
) -> None:
    """
    Actualiza contexto de conversación en Redis.
    """
    try:
        context = await get_conversation_context(redis_client, conversation_key)

        # Agregar nuevo intercambio
        context["history"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "user_message": user_message,
                "bot_response": bot_response,
                "metadata": metadata,
            }
        )

        # Mantener solo los últimos 20 intercambios
        context["history"] = context["history"][-20:]
        context["last_activity"] = datetime.now().isoformat()

        # Guardar en Redis con expiración de 24 horas
        import json

        await redis_client.setex(
            conversation_key,
            86400,  # 24 horas
            json.dumps(context),
        )

    except Exception as e:
        logger.error(f"Error updating conversation context: {e}")


async def should_end_conversation(user_message: str, bot_response: str) -> bool:
    """
    Determina si la conversación debería terminar.
    """
    ending_phrases = [
        "gracias",
        "bye",
        "adiós",
        "hasta luego",
        "chau",
        "nos vemos",
        "está bien",
        "perfecto",
        "ok",
        "listo",
        "eso es todo",
    ]

    user_lower = user_message.lower()

    # Si el usuario usa frases de despedida
    if any(phrase in user_lower for phrase in ending_phrases):
        return True

    # Si la respuesta del bot indica completitud
    if any(phrase in bot_response.lower() for phrase in ["¿algo más?", "¿necesitas algo más?"]):
        return False  # Dar oportunidad de continuar

    return False


async def log_search_analytics(
    query: str, user_id: Optional[str], results_count: int, processing_time: float, metadata: Dict[str, Any]
) -> None:
    """
    Registra analíticas de búsqueda para análisis posterior.
    """
    try:
        analytics_data = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "user_id": user_id,
            "results_count": results_count,
            "processing_time_ms": processing_time,
            "intent_type": metadata.get("intent", {}).get("intent_type"),
            "search_method": metadata.get("search_method"),
            "query_complexity": metadata.get("intent", {}).get("query_complexity"),
        }

        # En producción, enviar a sistema de analytics
        logger.info(f"Search analytics: {analytics_data}")

    except Exception as e:
        logger.error(f"Error logging analytics: {e}")
