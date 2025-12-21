"""
WhatsApp Service.

Single Responsibility: Facade for WhatsApp Business API operations.
Uses composition with HttpClient, Messenger for messaging operations.
"""

import logging
from typing import Any

from app.config.settings import get_settings
from app.integrations.whatsapp.http_client import WhatsAppHttpClient
from app.integrations.whatsapp.messenger import WhatsAppMessenger
from app.models.whatsapp_advanced import (
    CatalogConfiguration,
    FlowConfiguration,
    WhatsAppApiResponse,
)

logger = logging.getLogger(__name__)


class WhatsAppService:
    """
    WhatsApp Business API service.

    Uses composition:
    - WhatsAppHttpClient for HTTP communication
    - WhatsAppMessenger for message sending
    """

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.WHATSAPP_API_BASE
        self.version = self.settings.WHATSAPP_API_VERSION
        self.phone_number_id = self.settings.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = self.settings.WHATSAPP_ACCESS_TOKEN
        self.catalog_id = self.settings.WHATSAPP_CATALOG_ID

        # Compose dependencies
        self._http_client = WhatsAppHttpClient(
            base_url=self.base_url,
            version=self.version,
            phone_number_id=self.phone_number_id,
            access_token=self.access_token,
        )

        self._messenger = WhatsAppMessenger(
            http_client=self._http_client,
            catalog_id=self.catalog_id,
            is_development=self.settings.is_development,
        )

        logger.info("WhatsApp Service initialized:")
        logger.info(f"  Base URL: {self.base_url}")
        logger.info(f"  Version: {self.version}")
        logger.info(f"  Phone ID: {self.phone_number_id}")
        logger.info(f"  Catalog ID: {self.catalog_id}")

    # HTTP methods (for backwards compatibility and direct access)
    def _get_headers(self) -> dict[str, str]:
        """Get standard headers."""
        return self._http_client.headers

    def _get_message_url(self) -> str:
        """Get message URL."""
        return self._http_client.message_url

    async def _make_request(
        self,
        payload: dict[str, Any],
        endpoint: str = "messages",
    ) -> dict[str, Any]:
        """Make HTTP request (delegated to client)."""
        return await self._http_client.post(payload, endpoint)

    # Messaging methods (delegated to messenger)
    async def enviar_mensaje_texto(
        self,
        numero: str,
        mensaje: str,
    ) -> dict[str, Any]:
        """Send text message."""
        return await self._messenger.send_text(numero, mensaje)

    async def enviar_documento(
        self,
        numero: str,
        nombre: str,
        document_url: str,
        caption: str | None = None,
    ) -> dict[str, Any]:
        """Send document."""
        return await self._messenger.send_document(numero, nombre, document_url, caption)

    async def enviar_ubicacion(
        self,
        numero: str,
        latitud: float,
        longitud: float,
        nombre: str | None = None,
    ) -> dict[str, Any]:
        """Send location."""
        return await self._messenger.send_location(numero, latitud, longitud, nombre)

    async def enviar_lista_opciones(
        self,
        numero: str,
        titulo: str,
        cuerpo: str,
        opciones: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Send interactive list."""
        return await self._messenger.send_list(numero, titulo, cuerpo, opciones)

    async def enviar_botones(
        self,
        numero: str,
        titulo: str,
        cuerpo: str,
        botones: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Send interactive buttons."""
        return await self._messenger.send_buttons(numero, titulo, cuerpo, botones)

    async def send_product_list(
        self,
        numero: str,
        body_text: str,
        header_text: str | None = None,
        product_retailer_id: str | None = None,
        catalog_id: str | None = None,
    ) -> WhatsAppApiResponse:
        """Send product catalog list."""
        return await self._messenger.send_product_list(
            numero, body_text, header_text, product_retailer_id, catalog_id
        )

    async def send_flow_message(
        self,
        numero: str,
        flow_id: str,
        flow_cta: str,
        body_text: str | None = None,
        header_text: str | None = None,
        flow_token: str | None = None,
        flow_data: dict[str, Any] | None = None,
    ) -> WhatsAppApiResponse:
        """Send WhatsApp Flow message."""
        return await self._messenger.send_flow(
            numero, flow_id, flow_cta, body_text, header_text, flow_token, flow_data
        )

    async def enviar_template(
        self,
        numero: str,
        template_name: str,
        language_code: str = "es",
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Send a WhatsApp template message (HSM).

        Args:
            numero: Recipient phone number
            template_name: Name of the pre-approved template
            language_code: Template language code (default: "es")
            components: Template components (header, body, button parameters)

        Returns:
            API response dict
        """
        return await self._messenger.send_template(
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
        """
        Send a template message with a document header.

        Convenience method for payment receipts and invoices.

        Args:
            numero: Recipient phone number
            template_name: Name of the pre-approved template
            document_url: Public URL of the document (PDF)
            document_filename: Filename to show to recipient
            body_params: List of body parameter values ({{1}}, {{2}}, etc.)
            language_code: Template language code (default: "es")

        Returns:
            API response dict
        """
        return await self._messenger.send_template_with_document(
            numero, template_name, document_url, document_filename, body_params, language_code
        )

    # Aliases in English
    send_message = enviar_mensaje_texto
    send_template = enviar_template
    send_template_with_document = enviar_template_con_documento

    # Catalog methods
    async def get_catalog_products(
        self,
        limit: int = 10,
        after: str | None = None,
        catalog_id: str | None = None,
    ) -> WhatsAppApiResponse:
        """Get catalog products."""
        used_catalog_id = catalog_id or self.catalog_id

        try:
            response = await self._http_client.get(
                f"{used_catalog_id}/products",
                params={"limit": limit, **({"after": after} if after else {})},
            )

            if response.get("success"):
                data = response.get("data", {})
                logger.info(f"Catalog products: {len(data.get('data', []))}")
                return WhatsAppApiResponse(success=True, data=data)
            else:
                return WhatsAppApiResponse(
                    success=False,
                    error=response.get("error"),
                    status_code=response.get("status_code"),
                )

        except Exception as e:
            logger.error(f"Error getting catalog products: {e}")
            return WhatsAppApiResponse(success=False, error=str(e))

    async def get_business_catalogs(
        self,
        business_account_id: str,
    ) -> WhatsAppApiResponse:
        """Get business catalogs."""
        try:
            response = await self._http_client.get(
                f"{business_account_id}/owned_product_catalogs"
            )

            if response.get("success"):
                data = response.get("data", {})
                logger.info(f"Catalogs: {len(data.get('data', []))}")
                return WhatsAppApiResponse(success=True, data=data)
            else:
                return WhatsAppApiResponse(
                    success=False,
                    error=response.get("error"),
                    status_code=response.get("status_code"),
                )

        except Exception as e:
            logger.error(f"Error getting catalogs: {e}")
            return WhatsAppApiResponse(success=False, error=str(e))

    # Configuration methods
    def get_catalog_configuration(self) -> CatalogConfiguration:
        """Get catalog configuration."""
        return CatalogConfiguration(
            catalog_id=self.catalog_id,
            phone_number_id=self.phone_number_id,
            access_token=self.access_token,
        )

    def create_flow_configuration(
        self,
        flow_id: str,
        flow_name: str,
    ) -> FlowConfiguration:
        """Create flow configuration."""
        return FlowConfiguration(
            flow_id=flow_id,
            flow_name=flow_name,
            phone_number_id=self.phone_number_id,
            access_token=self.access_token,
        )

    async def verificar_configuracion(self) -> dict[str, Any]:
        """Verify WhatsApp API configuration."""
        issues = []

        if not self.access_token:
            issues.append("Access token not configured")
        elif len(self.access_token) < 50:
            issues.append("Access token seems invalid (too short)")

        if not self.phone_number_id:
            issues.append("Phone Number ID not configured")
        elif not self.phone_number_id.isdigit():
            issues.append("Phone Number ID must be numeric")

        if not self.base_url.startswith("https://"):
            issues.append("Base URL must use HTTPS")

        if not self.catalog_id:
            issues.append("Catalog ID not configured")
        elif not self.catalog_id.isdigit():
            issues.append("Catalog ID must be numeric")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "config": {
                "base_url": self.base_url,
                "version": self.version,
                "phone_id": self.phone_number_id,
                "catalog_id": self.catalog_id,
                "token_length": len(self.access_token) if self.access_token else 0,
            },
            "catalog_configuration": {
                "catalog_id": self.catalog_id,
                "catalog_url": f"{self.base_url}/{self.version}/{self.catalog_id}",
                "products_url": f"{self.base_url}/{self.version}/{self.catalog_id}/products",
            },
        }
