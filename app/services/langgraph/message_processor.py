"""
Message processing logic for LangGraph chatbot service
"""

import logging
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.graph import AynuxGraph
from app.core.schemas import ConversationContext, CustomerContext
from app.models.chat import ChatStreamEvent, StreamEventType
from app.models.message import WhatsAppMessage
from app.utils.language_detector import get_language_detector

logger = logging.getLogger(__name__)


class MessageProcessor:
    """Handles message processing and LangGraph integration"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.language_detector = get_language_detector(
            {
                "supported_languages": ["es", "en"],
                "default_language": "es",
                "confidence_threshold": 0.4,
                "cache_size": 500,
                "cache_ttl": 1800,  # 30 minutos
            }
        )

    def extract_message_text(self, message: WhatsAppMessage) -> str:
        """Extrae el texto del mensaje de WhatsApp (texto o respuesta interactiva)"""
        # Handle text messages
        if hasattr(message, "text") and message.text:
            return message.text.body.strip()

        # Handle interactive messages (button/list replies from WhatsApp)
        if hasattr(message, "interactive") and message.interactive:
            if message.interactive.button_reply:
                # Use button title (readable) or ID as fallback
                return message.interactive.button_reply.title or message.interactive.button_reply.id
            elif message.interactive.list_reply:
                # Use list item title (readable) or ID as fallback
                return message.interactive.list_reply.title or message.interactive.list_reply.id

        return ""

    def detect_language(self, text: str) -> str:
        """Detecta el idioma del mensaje usando spaCy con fallback robusto"""
        try:
            result = self.language_detector.detect_language(text)
            detected_language = result.get("language", "es")
            confidence = result.get("confidence", 0.0)
            method = result.get("method", "unknown")

            # Log para debugging (opcional)
            if confidence < 0.7:
                self.logger.debug(
                    f"Language detection with low confidence: {detected_language} "
                    f"({confidence:.2f}) using {method} for text: '{text[:50]}...'"
                )

            return detected_language

        except Exception as e:
            self.logger.warning(f"Error in language detection, falling back to default: {e}")
            return "es"  # Default a español en caso de error

    async def process_with_langgraph(
        self,
        graph_system: AynuxGraph,
        message_text: str,
        customer_context: CustomerContext,
        conversation_context: ConversationContext,
        session_id: str,
        business_domain: str = "ecommerce",
        db_session: AsyncSession | None = None,
        organization_id: UUID | None = None,
        pharmacy_id: UUID | None = None,
        user_phone: str | None = None,
        bypass_target_agent: str | None = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Procesa el mensaje usando el sistema LangGraph multi-agente.

        Args:
            graph_system: Sistema de graph LangGraph
            message_text: Texto del mensaje del usuario
            customer_context: Contexto del cliente
            conversation_context: Contexto de la conversación
            session_id: ID de la sesión
            business_domain: Dominio de negocio (ecommerce, hospital, credit, excelencia)
            db_session: Sesión de base de datos async (opcional)
            organization_id: UUID de organización (for multi-tenant context)
            pharmacy_id: UUID de farmacia (for pharmacy config lookup in PaymentLinkNode)
            user_phone: Número de teléfono del usuario (for conversation context)
            bypass_target_agent: Target agent from bypass routing (for direct routing)

        Returns:
            Diccionario con respuesta del graph y metadatos
        """
        try:
            # Procesar con el graph multi-agente (incluir business_domain, tenant IDs, and bypass routing)
            result = await graph_system.invoke(
                message=message_text,
                conversation_id=session_id,
                customer_data=customer_context.model_dump(),
                conversation_data=conversation_context.model_dump(),
                business_domain=business_domain,
                db_session=db_session,
                organization_id=str(organization_id) if organization_id else None,
                pharmacy_id=str(pharmacy_id) if pharmacy_id else None,
                user_phone=user_phone,
                bypass_target_agent=bypass_target_agent,
                **kwargs,  # Pass additional context (e.g., pharmacy_name, pharmacy_phone)
            )

            # Extraer la respuesta del último mensaje AI
            response_text = "Lo siento, no pude procesar tu mensaje."
            agent_used = result.get("current_agent", "unknown")

            # Buscar el último mensaje AI en los mensajes
            messages = result.get("messages", [])
            for msg in reversed(messages):
                if hasattr(msg, "content") and msg.__class__.__name__ == "AIMessage":
                    response_text = msg.content
                    break

            # Log interactive response fields for debugging
            self.logger.info(
                f"[MESSAGE_PROCESSOR] Graph result has response_type={result.get('response_type')}, "
                f"buttons_count={len(result.get('response_buttons') or [])}"
            )

            return {
                "response": response_text,
                "agent_used": agent_used,
                "requires_human": result.get("human_handoff_requested", False),
                "is_complete": result.get("is_complete", False),
                "processing_time_ms": 0,  # TODO: Implement timing
                "graph_result": result,
                # WhatsApp interactive response fields (pharmacy domain)
                "response_type": result.get("response_type"),
                "response_buttons": result.get("response_buttons"),
                "response_list_items": result.get("response_list_items"),
            }

        except Exception as e:
            self.logger.error(f"Error in LangGraph processing: {e}")
            # Respuesta de fallback
            return {
                "response": "Disculpa, tuve un problema procesando tu mensaje. ¿Podrías intentar de nuevo?",
                "agent_used": "fallback",
                "requires_human": False,
                "is_complete": False,
                "processing_time_ms": 0,
                "error": str(e),
            }

    async def process_with_langgraph_stream(
        self,
        graph_system: AynuxGraph,
        message_text: str,
        customer_context: CustomerContext,
        conversation_context: ConversationContext,
        session_id: str,
    ) -> AsyncGenerator[ChatStreamEvent, None]:
        """
        Procesa el mensaje usando el sistema LangGraph multi-agente con streaming.

        Args:
            graph_system: Sistema de graph LangGraph
            message_text: Texto del mensaje del usuario
            customer_context: Contexto del cliente
            conversation_context: Contexto de la conversación
            session_id: ID de la sesión

        Yields:
            ChatStreamEvent: Eventos de streaming durante el procesamiento
        """
        try:
            # Verify that the graph system has the astream method
            if not hasattr(graph_system, "astream"):
                raise AttributeError("Graph system does not support streaming")

            start_time = datetime.now()

            # Emit initial thinking event
            yield ChatStreamEvent(
                event_type=StreamEventType.THINKING,
                message="🤔 Analizando tu consulta...",
                agent_current="orchestrator",
                progress=0.1,
                metadata={"step": "initial_analysis"},
                timestamp=start_time.isoformat(),
            )

            step_count = 0
            current_agent = "orchestrator"

            # Stream through the graph execution
            async for raw_chunk in graph_system.astream(
                message=message_text,
                conversation_id=session_id,
                customer_data=customer_context.model_dump(),
                conversation_data=conversation_context.model_dump(),
            ):
                step_count += 1
                # Cast to dict - LangGraph stream yields dicts
                chunk = cast(Dict[str, Any], raw_chunk)

                if chunk.get("type") == "stream_event":
                    data = cast(Dict[str, Any], chunk.get("data", {}))
                    current_node = str(data.get("current_node", "unknown"))

                    # Map node names to user-friendly agent names and messages
                    agent_info = self._map_node_to_agent_info(current_node)
                    current_agent = agent_info["agent_name"]

                    # Calculate progress based on step count
                    progress = min(0.9, 0.1 + (step_count * 0.15))

                    yield ChatStreamEvent(
                        event_type=agent_info["event_type"],
                        message=agent_info["message"],
                        agent_current=current_agent,
                        progress=progress,
                        metadata={
                            "step": step_count,
                            "node": current_node,
                            "state_preview": data.get("state_preview", {}),
                        },
                        timestamp=datetime.now().isoformat(),
                    )

                elif chunk.get("type") == "final_result":
                    # Process final result
                    result = cast(Dict[str, Any], chunk.get("data", {}))

                    # Extract response text from final result
                    response_text = "Lo siento, no pude procesar tu mensaje."
                    agent_used = str(result.get("current_agent", current_agent))

                    # Get response from last AI message
                    messages = cast(list[Any], result.get("messages", []))
                    for msg in reversed(messages):
                        if hasattr(msg, "content") and msg.__class__.__name__ == "AIMessage":
                            response_text = msg.content
                            break

                    # Calculate processing time
                    processing_time = (datetime.now() - start_time).total_seconds() * 1000

                    # Emit final generation event
                    yield ChatStreamEvent(
                        event_type=StreamEventType.GENERATING,
                        message="✨ Generando respuesta final...",
                        agent_current=agent_used,
                        progress=0.95,
                        metadata={"step": "final_generation"},
                        timestamp=datetime.now().isoformat(),
                    )

                    # Emit completion event with response
                    yield ChatStreamEvent(
                        event_type=StreamEventType.COMPLETE,
                        message=response_text,
                        agent_current=agent_used,
                        progress=1.0,
                        metadata={
                            "requires_human": bool(result.get("human_handoff_requested", False)),
                            "is_complete": bool(result.get("is_complete", True)),
                            "processing_time_ms": int(processing_time),
                            "total_steps": step_count,
                            "session_id": session_id,
                        },
                        timestamp=datetime.now().isoformat(),
                    )

                elif chunk.get("type") == "error":
                    # Emit error event
                    error_data = cast(Dict[str, Any], chunk.get("data", {}))
                    error_msg = str(error_data.get("error", "Error desconocido"))
                    yield ChatStreamEvent(
                        event_type=StreamEventType.ERROR,
                        message=f"❌ Error procesando tu mensaje: {error_msg}",
                        agent_current=current_agent,
                        progress=0.0,
                        metadata={"error": error_msg},
                        timestamp=datetime.now().isoformat(),
                    )
                    break

        except Exception as e:
            self.logger.error(f"Error in LangGraph streaming: {e}")
            # Emit error event
            yield ChatStreamEvent(
                event_type=StreamEventType.ERROR,
                message="❌ Disculpa, tuve un problema procesando tu mensaje. ¿Podrías intentar de nuevo?",
                agent_current="fallback",
                progress=0.0,
                metadata={"error": str(e)},
                timestamp=datetime.now().isoformat(),
            )

    def _map_node_to_agent_info(self, node_name: str) -> Dict[str, Any]:
        """Map LangGraph node names to user-friendly agent information"""

        # Mapping of node names to user-friendly information
        node_mapping = {
            "orchestrator": {
                "agent_name": "orchestrator",
                "event_type": StreamEventType.THINKING,
                "message": "🎯 Analizando el tipo de consulta...",
            },
            "supervisor": {
                "agent_name": "supervisor",
                "event_type": StreamEventType.PROCESSING,
                "message": "🔍 Coordinando la respuesta...",
            },
            "product_agent": {
                "agent_name": "product_agent",
                "event_type": StreamEventType.PROCESSING,
                "message": "🛍️ Buscando productos en el catálogo...",
            },
            "category_agent": {
                "agent_name": "category_agent",
                "event_type": StreamEventType.PROCESSING,
                "message": "📂 Explorando categorías de productos...",
            },
            "promotions_agent": {
                "agent_name": "promotions_agent",
                "event_type": StreamEventType.PROCESSING,
                "message": "🏷️ Revisando ofertas y promociones...",
            },
            "support_agent": {
                "agent_name": "support_agent",
                "event_type": StreamEventType.PROCESSING,
                "message": "🛟 Preparando asistencia técnica...",
            },
            "tracking_agent": {
                "agent_name": "tracking_agent",
                "event_type": StreamEventType.PROCESSING,
                "message": "📦 Consultando estado de pedidos...",
            },
            "invoice_agent": {
                "agent_name": "invoice_agent",
                "event_type": StreamEventType.PROCESSING,
                "message": "🧾 Revisando información de facturación...",
            },
            "data_insights_agent": {
                "agent_name": "data_insights_agent",
                "event_type": StreamEventType.PROCESSING,
                "message": "📊 Analizando datos y métricas...",
            },
            "fallback_agent": {
                "agent_name": "fallback_agent",
                "event_type": StreamEventType.PROCESSING,
                "message": "🤝 Preparando asistencia general...",
            },
            "farewell_agent": {
                "agent_name": "farewell_agent",
                "event_type": StreamEventType.GENERATING,
                "message": "👋 Preparando despedida...",
            },
        }

        # Get agent info or use default
        agent_info = node_mapping.get(
            node_name,
            {
                "agent_name": node_name,
                "event_type": StreamEventType.PROCESSING,
                "message": f"⚙️ Procesando con {node_name}...",
            },
        )

        return agent_info

    def create_customer_context(self, user_id: str, metadata: Dict[str, Any] | None = None) -> CustomerContext:
        """Crea contexto del cliente para chat genérico"""
        metadata = metadata or {}

        return CustomerContext(
            customer_id=user_id,
            name=metadata.get("user_name", "Usuario"),
            email=metadata.get("email"),
            phone=metadata.get("phone", ""),
            tier=metadata.get("tier", "basic"),
            purchase_history=[],
            preferences=metadata.get("preferences", {}),
        )

    def create_conversation_context(
        self, session_id: str, message_text: str, metadata: Dict[str, Any] | None = None
    ) -> ConversationContext:
        """Crea contexto de conversación"""
        metadata = metadata or {}

        return ConversationContext(
            conversation_id=session_id,
            session_id=session_id,
            channel=metadata.get("channel", "whatsapp"),
            language=metadata.get("language", self.detect_language(message_text)),
        )
