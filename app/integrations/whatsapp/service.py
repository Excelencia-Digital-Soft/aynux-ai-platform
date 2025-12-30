"""
WhatsApp Service.

Single Responsibility: Facade for WhatsApp messaging operations.

Chattigo Mode (Default):
  - All messaging goes through Chattigo API
  - Chattigo handles Meta/WhatsApp verification
  - No direct WhatsApp Graph API calls needed

Multi-DID Support:
  - When db_session and chattigo_context with 'did' are provided,
    credentials are fetched from chattigo_credentials table
  - Falls back to settings-based credentials if not found in DB
"""

import logging
from typing import TYPE_CHECKING, Any

from app.config.settings import Settings, get_settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ============================================================================
# Chattigo Messaging Service
# ============================================================================


class ChattigoMessagingService:
    """
    Messaging service that uses Chattigo as the WhatsApp API intermediary.

    This is the primary implementation for sending messages via Chattigo API.

    Multi-DID Support:
    - If db_session and chattigo_context with 'did' are provided,
      credentials are fetched from chattigo_credentials table.
    - Falls back to settings-based credentials if:
      1. No db_session provided
      2. No 'did' in chattigo_context
      3. No credentials found in database for the DID
    """

    def __init__(
        self,
        settings: Settings,
        chattigo_context: dict | None = None,
        db_session: "AsyncSession | None" = None,
    ):
        """
        Initialize Chattigo messaging service.

        Args:
            settings: Application settings with Chattigo configuration (fallback)
            chattigo_context: Context from incoming webhook (did, idChat, channelId, idCampaign)
            db_session: Optional database session for multi-DID credential lookup
        """
        self._settings = settings
        self._chattigo_context = chattigo_context or {}
        self._db_session = db_session
        self._adapter = None
        self._multi_did_adapter = None
        self._use_multi_did = False

    async def _get_adapter(self):
        """
        Get or create ChattigoAdapter instance.

        Attempts to use multi-DID credentials from database if:
        1. db_session is available
        2. chattigo_context contains 'did'
        3. Credentials exist in database for that DID

        Falls back to settings-based adapter if any of the above fail.
        """
        # If we already have an adapter, return it
        if self._use_multi_did and self._multi_did_adapter is not None:
            return self._multi_did_adapter
        if self._adapter is not None:
            return self._adapter

        # Try multi-DID first if we have db and did
        did = self._chattigo_context.get("did")
        if self._db_session is not None and did:
            # Import at module level check to satisfy type checkers
            from app.core.tenancy.credential_service import CredentialNotFoundError
            from app.integrations.chattigo.adapter_factory import (
                get_chattigo_adapter_factory,
            )

            try:
                factory = get_chattigo_adapter_factory()
                self._multi_did_adapter = await factory.get_adapter(self._db_session, did)
                await self._multi_did_adapter.initialize()
                self._use_multi_did = True
                logger.info(f"Using multi-DID credentials for DID {did}")
                return self._multi_did_adapter

            except CredentialNotFoundError:
                logger.info(
                    f"No multi-DID credentials found for DID {did}, "
                    "falling back to settings-based adapter"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to get multi-DID adapter for DID {did}: {e}, "
                    "falling back to settings-based adapter"
                )

        # Fallback to settings-based adapter
        from app.integrations.chattigo import ChattigoAdapter

        self._adapter = ChattigoAdapter(self._settings)
        await self._adapter.initialize()
        logger.info("Using settings-based Chattigo adapter")
        return self._adapter

    async def send_message(self, numero: str, mensaje: str) -> dict[str, Any]:
        """Send text message via Chattigo API."""
        adapter = await self._get_adapter()

        try:
            result = await adapter.send_message(
                msisdn=numero,
                message=mensaje,
            )
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"Chattigo send_message failed: {e}")
            return {"success": False, "error": str(e)}

    async def send_document(
        self,
        numero: str,
        nombre: str,
        document_url: str,
        caption: str | None = None,
    ) -> dict[str, Any]:
        """Send document via Chattigo API."""
        adapter = await self._get_adapter()

        try:
            result = await adapter.send_document(
                msisdn=numero,
                document_url=document_url,
                filename=nombre,
                caption=caption,
            )
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"Chattigo send_document failed: {e}")
            return {"success": False, "error": str(e)}

    async def send_image(
        self,
        numero: str,
        image_url: str,
        caption: str | None = None,
    ) -> dict[str, Any]:
        """Send image via Chattigo API."""
        adapter = await self._get_adapter()

        try:
            result = await adapter.send_image(
                msisdn=numero,
                image_url=image_url,
                caption=caption,
            )
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"Chattigo send_image failed: {e}")
            return {"success": False, "error": str(e)}

    # Aliases for compatibility
    enviar_mensaje_texto = send_message
    enviar_documento = send_document

    async def enviar_template(
        self,
        numero: str,
        template_name: str,
        language_code: str = "es",
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Send template message via Chattigo.

        Note: Chattigo may handle templates differently than direct WhatsApp API.
        For now, this sends a regular message with template content.
        """
        # Extract body text from components if available
        body_text = ""
        if components:
            for comp in components:
                if comp.get("type") == "body" and comp.get("parameters"):
                    params = comp["parameters"]
                    body_text = " ".join(
                        str(p.get("text", "")) for p in params if p.get("type") == "text"
                    )

        if not body_text:
            body_text = f"[Template: {template_name}]"

        return await self.send_message(numero, body_text)

    async def enviar_template_con_documento(
        self,
        numero: str,
        template_name: str,
        document_url: str,
        document_filename: str,
        body_params: list[str] | None = None,
        language_code: str = "es",
    ) -> dict[str, Any]:
        """
        Send template message with document via Chattigo.

        Sends the document with a caption containing the template params.
        """
        caption = " ".join(body_params) if body_params else f"[Template: {template_name}]"
        return await self.send_document(
            numero=numero,
            nombre=document_filename,
            document_url=document_url,
            caption=caption,
        )

    # English aliases
    send_template = enviar_template
    send_template_with_document = enviar_template_con_documento

    async def close(self):
        """Close adapters."""
        if self._multi_did_adapter:
            await self._multi_did_adapter.close()
            self._multi_did_adapter = None
        if self._adapter:
            await self._adapter.close()
            self._adapter = None
        self._use_multi_did = False


# ============================================================================
# WhatsAppService (Compatibility Wrapper)
# ============================================================================


class WhatsAppService:
    """
    WhatsApp messaging service.

    When CHATTIGO_ENABLED=true (default), this class acts as a wrapper
    that delegates all messaging operations to ChattigoMessagingService.
    """

    def __init__(
        self,
        chattigo_context: dict | None = None,
        db_session: "AsyncSession | None" = None,
    ):
        """
        Initialize WhatsApp service.

        Args:
            chattigo_context: Context from Chattigo webhook (did, idChat, etc.)
            db_session: Optional database session for multi-DID credential lookup
        """
        self.settings = get_settings()
        self._chattigo_context = chattigo_context or {}
        self._db_session = db_session

        if not self.settings.CHATTIGO_ENABLED:
            raise RuntimeError(
                "Direct WhatsApp API is not available. "
                "Chattigo integration is required (CHATTIGO_ENABLED=true)."
            )

        # Use Chattigo internally
        self._chattigo_service = ChattigoMessagingService(
            self.settings, self._chattigo_context, self._db_session
        )

        logger.info("WhatsApp Service initialized (using Chattigo)")

    # Messaging methods - delegate to Chattigo
    async def enviar_mensaje_texto(self, numero: str, mensaje: str) -> dict[str, Any]:
        """Send text message."""
        return await self._chattigo_service.send_message(numero, mensaje)

    async def enviar_documento(
        self,
        numero: str,
        nombre: str,
        document_url: str,
        caption: str | None = None,
    ) -> dict[str, Any]:
        """Send document."""
        return await self._chattigo_service.send_document(
            numero, nombre, document_url, caption
        )

    async def enviar_template(
        self,
        numero: str,
        template_name: str,
        language_code: str = "es",
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send template message."""
        return await self._chattigo_service.enviar_template(
            numero, template_name, language_code, components
        )

    async def enviar_template_con_documento(
        self,
        numero: str,
        template_name: str,
        document_url: str,
        document_filename: str,
        body_params: list[str] | None = None,
        language_code: str = "es",
    ) -> dict[str, Any]:
        """Send template with document."""
        return await self._chattigo_service.enviar_template_con_documento(
            numero, template_name, document_url, document_filename, body_params, language_code
        )

    # English aliases
    send_message = enviar_mensaje_texto
    send_template = enviar_template
    send_template_with_document = enviar_template_con_documento

    async def verificar_configuracion(self) -> dict[str, Any]:
        """Verify Chattigo configuration."""
        return {
            "valid": self.settings.CHATTIGO_ENABLED,
            "issues": [] if self.settings.CHATTIGO_ENABLED else ["Chattigo not enabled"],
            "config": {
                "chattigo_enabled": self.settings.CHATTIGO_ENABLED,
                "chattigo_base_url": self.settings.CHATTIGO_BASE_URL,
                "chattigo_username": self.settings.CHATTIGO_USERNAME,
                "chattigo_channel_id": self.settings.CHATTIGO_CHANNEL_ID,
            },
        }


# ============================================================================
# Factory Functions
# ============================================================================


def get_messaging_service(
    chattigo_context: dict | None = None,
    db_session: "AsyncSession | None" = None,
) -> ChattigoMessagingService:
    """
    Get the messaging service.

    Returns ChattigoMessagingService since Chattigo is the only
    supported messaging integration.

    Multi-DID Support:
    - When db_session and chattigo_context with 'did' are provided,
      credentials are fetched from chattigo_credentials table.
    - Falls back to settings-based credentials if not found in DB.

    Args:
        chattigo_context: Context from Chattigo webhook (did, idChat, etc.)
                         Required for proper message routing.
        db_session: Optional database session for multi-DID credential lookup.
                   If provided with chattigo_context containing 'did',
                   enables multi-DID credential support.

    Returns:
        ChattigoMessagingService instance

    Example:
        # Basic usage (settings-based)
        service = get_messaging_service(chattigo_context=ctx)

        # Multi-DID usage (database credentials)
        service = get_messaging_service(chattigo_context=ctx, db_session=db)
        await service.send_message("5491234567890", "Hello!")
    """
    settings = get_settings()
    logger.info("Creating Chattigo messaging service")
    return ChattigoMessagingService(settings, chattigo_context, db_session)
