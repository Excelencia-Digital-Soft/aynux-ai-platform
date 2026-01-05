"""
Servicio integrado de chatbot usando LangGraph multi-agente

Supports DUAL-MODE operation:
- Global mode (no tenant): Processes messages with Python default configs
- Multi-tenant mode (with token): Applies tenant-specific agent configurations

The set_tenant_registry_for_request() method configures agents per-request.
"""

import logging
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.langgraph_config import get_langgraph_config
from app.config.settings import get_settings
from app.core.container import DependencyContainer
from app.core.graph import AynuxGraph
from app.core.schemas import CustomerContext
from app.models.chat import ChatStreamEvent
from app.models.message import BotResponse, Contact, WhatsAppMessage
from app.services.langgraph import (
    ConversationManager,
    MessageProcessor,
    SecurityValidator,
    SystemMonitor,
)

if TYPE_CHECKING:
    from app.core.schemas.tenant_agent_config import TenantAgentRegistry

BUSINESS_NAME = "Conversa Shop"

logger = logging.getLogger(__name__)


class LangGraphChatbotService:
    """
    Servicio de chatbot integrado con sistema multi-agente LangGraph

    Versión refactorizada que usa:
    - Modelos Pydantic para validación de datos
    - TypedDict para estado de LangGraph (máximo rendimiento)
    - Módulos especializados para separación de responsabilidades
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.settings = get_settings()

        # Cargar configuración LangGraph
        self.langgraph_config = get_langgraph_config()

        # Dependency Container
        self.container = DependencyContainer()

        # Módulos especializados
        self.message_processor = MessageProcessor()
        self.security_validator = SecurityValidator()
        # ConversationManager se crea por request para soportar multi-DID Chattigo
        self._default_conversation_manager = ConversationManager()
        self.system_monitor = SystemMonitor()

        # Graph principal (se inicializa en initialize())
        self.graph_system = None
        self._initialized = False

    async def initialize(self):
        """
        Inicializa el sistema de forma asíncrona.
        Debe llamarse antes de procesar mensajes.
        """
        try:
            if self._initialized:
                return

            self.logger.info("Initializing LangGraph chatbot service...")

            # Crear y configurar el sistema de graph
            self.graph_system = AynuxGraph(self.langgraph_config.model_dump())

            # Inicializar el graph de forma asíncrona (con checkpointer)
            await self.graph_system.initialize()

            self._initialized = True
            self.logger.info("LangGraph chatbot service initialized successfully")

        except Exception as e:
            self.logger.error(f"Error initializing LangGraph service: {str(e)}")
            raise

    async def process_webhook_message(
        self,
        message: WhatsAppMessage,
        contact: Contact,
        business_domain: str = "ecommerce",
        db_session: AsyncSession | None = None,
        organization_id: "UUID | None" = None,
        pharmacy_id: "UUID | None" = None,
        chattigo_context: dict | None = None,
        bypass_target_agent: str | None = None,
    ) -> BotResponse:
        """
        Procesa un mensaje de WhatsApp usando el sistema multi-agente refactorizado.

        Args:
            message: Mensaje de WhatsApp recibido
            contact: Información de contacto del usuario
            business_domain: Dominio de negocio (ecommerce, hospital, credit, excelencia)
            db_session: Sesión de base de datos async (opcional)
            organization_id: UUID de organización (from bypass routing, for multi-tenant context)
            pharmacy_id: UUID de farmacia (from bypass routing, for pharmacy config lookup)
            chattigo_context: Contexto de Chattigo (did, idChat, etc.) para seleccionar
                            credenciales correctas de la base de datos.
            bypass_target_agent: Target agent from bypass routing (for direct routing)

        Returns:
            Respuesta estructurada del bot
        """

        if not self._initialized:
            await self.initialize()

        # Extraer información básica
        user_number = contact.wa_id
        message_text = self.message_processor.extract_message_text(message)
        session_id = f"whatsapp_{user_number}"

        self.logger.info(f"Processing message from {user_number} (domain: {business_domain}): {message_text[:100]}...")

        try:
            # 1. Verificar seguridad del mensaje
            security_check = await self.security_validator.check_message_security(user_number, message_text)
            if not security_check["allowed"]:
                return BotResponse(status="blocked", message=security_check["message"])

            # 2. Verificar estado de la base de datos
            db_available = await self.security_validator.check_database_health()

            # Obtener contextos necesarios
            profile_name: str = (
                contact.profile.get("name") if contact.profile and isinstance(contact.profile, dict) else None
            ) or "Usuario"
            customer_context = await self._get_or_create_customer_context(user_number, profile_name, db_session)
            conversation_context = self.message_processor.create_conversation_context(
                session_id, message_text, {"channel": "whatsapp"}
            )

            # 5. Procesar con el sistema LangGraph (incluir business_domain, tenant IDs, and bypass routing)
            assert self.graph_system is not None  # Guaranteed after initialize()
            response_data = await self.message_processor.process_with_langgraph(
                graph_system=self.graph_system,
                message_text=message_text,
                customer_context=customer_context,
                conversation_context=conversation_context,
                session_id=session_id,
                business_domain=business_domain,
                db_session=db_session,
                organization_id=organization_id,
                pharmacy_id=pharmacy_id,
                user_phone=user_number,
                bypass_target_agent=bypass_target_agent,
            )

            # Crear ConversationManager con contexto de Chattigo para selección de credenciales
            conversation_manager = ConversationManager(
                chattigo_context=chattigo_context,
                db_session=db_session,
            )

            # Operaciones post-procesamiento
            await conversation_manager.handle_whatsapp_post_processing(
                db_available=db_available,
                user_number=user_number,
                user_message=message_text,
                session_id=session_id,
                response_data=response_data,
            )

            return BotResponse(
                status="success",
                message=response_data["response"],
                metadata={
                    "agent_used": response_data.get("agent_used"),
                    "requires_human": response_data.get("requires_human", False),
                    "conversation_id": session_id,
                    "graph_result": response_data.get("graph_result"),  # Include full execution history
                },
            )

        except Exception as e:
            # Usar ConversationManager con contexto para error handling
            error_manager = ConversationManager(
                chattigo_context=chattigo_context,
                db_session=db_session,
            )
            return await error_manager.handle_processing_error(e, user_number)

    async def process_chat_message(
        self,
        message: str,
        user_id: str,
        session_id: str,
        metadata: Dict[str, Any] | None = None,
        db_session: AsyncSession | None = None,
    ) -> Dict[str, Any]:
        """
        Procesa un mensaje de chat genérico (no WhatsApp) usando el sistema multi-agente.

        Args:
            message: Texto del mensaje del usuario
            user_id: ID único del usuario
            session_id: ID de la sesión
            metadata: Metadatos adicionales opcionales

        Returns:
            Diccionario con respuesta del graph y metadatos
        """
        if not self._initialized:
            await self.initialize()

        metadata = metadata or {}

        self.logger.info(f"Processing chat message from user {user_id} in session {session_id}: {message[:100]}...")

        try:
            # Crear contexto del cliente simplificado
            customer_context = self.message_processor.create_customer_context(user_id, metadata)

            # Crear contexto de conversación
            conversation_context = self.message_processor.create_conversation_context(session_id, message, metadata)

            # Procesar con el sistema LangGraph
            assert self.graph_system is not None  # Guaranteed after initialize()
            response_data = await self.message_processor.process_with_langgraph(
                graph_system=self.graph_system,
                message_text=message,
                customer_context=customer_context,
                conversation_context=conversation_context,
                session_id=session_id,
                db_session=db_session,
            )

            # Post-procesamiento simplificado (sin WhatsApp, usa default manager)
            await self._default_conversation_manager.handle_chat_post_processing(
                user_id=user_id, user_message=message, session_id=session_id, response_data=response_data
            )

            return response_data

        except Exception as e:
            self.logger.error(f"Error processing chat message: {str(e)}")
            return {
                "response": "Disculpa, tuve un problema procesando tu mensaje. ¿Podrías intentar de nuevo?",
                "agent_used": "fallback",
                "requires_human": False,
                "is_complete": False,
                "processing_time_ms": 0,
                "error": str(e),
            }

    async def process_chat_message_stream(
        self, message: str, user_id: str, session_id: str, metadata: Dict[str, Any] | None = None
    ) -> AsyncGenerator[ChatStreamEvent, None]:
        """
        Procesa un mensaje de chat con streaming en tiempo real usando el sistema multi-agente.

        Args:
            message: Texto del mensaje del usuario
            user_id: ID único del usuario
            session_id: ID de la sesión
            metadata: Metadatos adicionales opcionales

        Yields:
            ChatStreamEvent: Eventos de streaming durante el procesamiento
        """
        if not self._initialized:
            await self.initialize()

        metadata = metadata or {}
        self.logger.info(
            f"Processing streaming chat message from user {user_id} in session {session_id}:\
            {message[:100]}..."
        )

        try:
            # Preparar contextos
            customer_context = self.message_processor.create_customer_context(user_id, metadata)
            conversation_context = self.message_processor.create_conversation_context(session_id, message, metadata)

            # Procesar con streaming usando el sistema LangGraph
            assert self.graph_system is not None  # Guaranteed after initialize()
            last_event = None
            async for stream_event in self.message_processor.process_with_langgraph_stream(
                graph_system=self.graph_system,
                message_text=message,
                customer_context=customer_context,
                conversation_context=conversation_context,
                session_id=session_id,
            ):
                last_event = stream_event
                yield stream_event

            # Post-procesamiento simplificado (sin WhatsApp, usa default manager)
            # Solo si el último evento fue de completion
            if last_event and last_event.event_type.value == "complete":
                await self._default_conversation_manager.handle_chat_post_processing(
                    user_id=user_id,
                    user_message=message,
                    session_id=session_id,
                    response_data={
                        "response": last_event.message,
                        "agent_used": last_event.agent_current,
                        "requires_human": last_event.metadata.get("requires_human", False),
                        "is_complete": last_event.metadata.get("is_complete", True),
                        "processing_time_ms": last_event.metadata.get("processing_time_ms", 0),
                    },
                )

        except Exception as e:
            self.logger.error(f"Error processing streaming chat message: {str(e)}")

            # Yield error event
            from datetime import datetime

            from app.models.chat import StreamEventType

            yield ChatStreamEvent(
                event_type=StreamEventType.ERROR,
                message="❌ Disculpa, tuve un problema procesando tu mensaje. ¿Podrías intentar de nuevo?",
                agent_current="fallback",
                progress=0.0,
                metadata={"error": str(e)},
                timestamp=datetime.now().isoformat(),
            )

    async def get_conversation_history_langgraph(self, user_number: str, limit: int = 50) -> Dict[str, Any]:
        """Obtiene el historial de conversación para un usuario usando LangGraph"""
        if not self._initialized or self.graph_system is None:
            return {"messages": [], "error": "Service not initialized"}
        return await self.system_monitor.get_conversation_history_langgraph(self.graph_system, user_number, limit)

    async def get_conversation_stats(self, user_number: str) -> Dict[str, Any]:
        """Obtiene estadísticas de conversación para un usuario"""
        if not self._initialized or self.graph_system is None:
            return {"error": "Service not initialized"}
        return await self.system_monitor.get_conversation_stats(self.graph_system, user_number)

    async def get_system_health(self) -> Dict[str, Any]:
        """Obtiene el estado de salud del sistema LangGraph"""
        if not self._initialized or self.graph_system is None:
            return {"status": "not_initialized", "graph_system": None}
        return await self.system_monitor.get_system_health(self._initialized, self.graph_system)

    async def cleanup(self):
        """Limpieza de recursos del servicio"""
        try:
            self.logger.info("Cleaning up LangGraph chatbot service...")
            self._initialized = False
            # TODO: Cleanup graph resources if needed
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    async def _get_or_create_customer_context(
        self, user_number: str, user_name: str, db_session: AsyncSession | None = None
    ) -> CustomerContext:
        """
        Get or create customer context using new Clean Architecture Use Case.

        Args:
            user_number: WhatsApp number
            user_name: User's profile name
            db_session: Optional database session for customer lookup

        Returns:
            CustomerContext instance
        """
        try:
            # If no db_session, return default context
            if db_session is None:
                return CustomerContext(
                    customer_id=f"whatsapp_{user_number}",
                    name=user_name or "Usuario",
                    email=None,
                    phone=user_number,
                    tier="basic",
                    purchase_history=[],
                    preferences={},
                )

            # Use GetOrCreateCustomerUseCase from DependencyContainer
            use_case = self.container.create_get_or_create_customer_use_case(db_session)
            customer = await use_case.execute(phone_number=user_number, profile_name=user_name)

            if not customer:
                # Fallback to default context
                return CustomerContext(
                    customer_id=f"whatsapp_{user_number}",
                    name=user_name or "Usuario",
                    email=None,
                    phone=user_number,
                    tier="basic",
                    purchase_history=[],
                    preferences={},
                )

            # Transform customer dict to CustomerContext
            customer_name = customer.get("name") or customer.get("profile_name") or user_name or "Usuario"

            return CustomerContext(
                customer_id=str(customer.get("id", f"whatsapp_{user_number}")),
                name=customer_name,
                email=customer.get("email"),
                phone=customer.get("phone_number", user_number),
                tier=customer.get("tier", "basic"),
                purchase_history=[],  # Can be loaded from DB if needed
                preferences=customer.get("preferences", {}),
            )

        except Exception as e:
            self.logger.warning(f"Error getting customer context: {e}")
            # Return fallback context on error
            return CustomerContext(
                customer_id=f"whatsapp_{user_number}",
                name=user_name or "Usuario",
                email=None,
                phone=user_number,
                tier="basic",
                purchase_history=[],
                preferences={},
            )

    # =========================================================================
    # Dual-Mode Methods (Global vs Multi-Tenant)
    # =========================================================================

    def set_tenant_registry_for_request(self, registry: "TenantAgentRegistry") -> None:
        """
        Configure agents for tenant-specific processing.

        Called before processing a request in multi-tenant mode to apply
        tenant-specific agent configurations from database.

        Args:
            registry: TenantAgentRegistry loaded from database for current tenant

        Example:
            >>> # In webhook handler
            >>> registry = await tenant_service.get_agent_registry(org_id)
            >>> service.set_tenant_registry_for_request(registry)
            >>> result = await service.process_webhook_message(message, contact, domain)
        """
        if not self._initialized or not self.graph_system:
            self.logger.warning(
                "Service not initialized, cannot set tenant registry"
            )
            return

        self.graph_system.set_tenant_registry(registry)
        self.logger.info(
            f"Configured service for tenant: {registry.organization_id}"
        )

    def reset_tenant_config(self) -> None:
        """
        Reset agents to global default configuration.

        Called after processing a request in multi-tenant mode to ensure
        agents don't retain tenant-specific config for next request.
        """
        if not self._initialized or not self.graph_system:
            return

        self.graph_system.reset_tenant_config()
        self.logger.debug("Reset service to global defaults")

    def get_mode_info(self) -> Dict[str, Any]:
        """
        Get information about current service operation mode.

        Returns:
            Dict with mode info and configuration state
        """
        if not self._initialized or not self.graph_system:
            return {
                "mode": "not_initialized",
                "initialized": False,
            }

        graph_info = self.graph_system.get_mode_info()
        return {
            **graph_info,
            "service_initialized": self._initialized,
            "multi_tenant_mode": self.settings.MULTI_TENANT_MODE,
        }
