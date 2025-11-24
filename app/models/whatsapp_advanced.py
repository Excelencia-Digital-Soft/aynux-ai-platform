"""
Advanced WhatsApp Business API models for catalog and flows functionality
Following SOLID principles and Pydantic best practices
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class InteractiveType(str, Enum):
    """Supported interactive message types"""

    PRODUCT_LIST = "product_list"
    FLOW = "flow"
    BUTTON = "button"
    LIST = "list"


class FlowAction(str, Enum):
    """Available flow actions"""

    NAVIGATE = "navigate"
    COMPLETE = "complete"
    UPDATE_SCREEN = "update_screen"


# Base WhatsApp Message Models
class WhatsAppRecipient(BaseModel):
    """Base recipient model for WhatsApp messages"""

    to: str = Field(..., description="Recipient phone number")
    messaging_product: str = Field(default="whatsapp", description="Messaging product")
    recipient_type: str = Field(default="individual", description="Type of recipient")


class WhatsAppHeaderText(BaseModel):
    """Text header for interactive messages"""

    type: str = Field(default="text", description="Header type")
    text: str = Field(..., max_length=60, description="Header text (max 60 chars)")


class WhatsAppBody(BaseModel):
    """Body text for messages"""

    text: str = Field(..., max_length=1024, description="Body text (max 1024 chars)")


# Catalog Models
class CatalogProductAction(BaseModel):
    """Catalog action configuration"""

    catalog_id: str = Field(..., description="WhatsApp Business catalog ID")
    product_retailer_id: Optional[str] = Field(None, description="Specific product ID to highlight")


class ProductListInteractive(BaseModel):
    """Interactive configuration for product list"""

    type: InteractiveType = Field(InteractiveType.PRODUCT_LIST, description="Interactive type")
    header: Optional[WhatsAppHeaderText] = Field(None, description="Optional header")
    body: WhatsAppBody = Field(..., description="Message body")
    footer: Optional[Dict[str, str]] = Field(None, description="Optional footer")
    action: CatalogProductAction = Field(..., description="Catalog action configuration")


class ProductListMessage(WhatsAppRecipient):
    """Complete product list message structure"""

    type: str = Field(default="interactive", description="Message type")
    interactive: ProductListInteractive = Field(..., description="Interactive configuration")

    @field_validator("interactive", mode="after")
    @classmethod
    def validate_interactive_type(cls, value):
        """Ensure interactive type is product_list"""
        if value.type != InteractiveType.PRODUCT_LIST:
            raise ValueError("Interactive type must be product_list")
        return value


# Flow Models
class FlowData(BaseModel):
    """Flow data configuration"""

    flow_message_version: str = Field(default="1", description="Flow message version")
    flow_token: Optional[str] = Field(None, description="Flow token for data passing")
    flow_id: str = Field(..., description="WhatsApp Flow ID")
    flow_cta: str = Field(..., max_length=20, description="Call to action text (max 20 chars)")
    flow_action: FlowAction = Field(FlowAction.NAVIGATE, description="Flow action type")
    flow_action_payload: Optional[Dict[str, Any]] = Field(None, description="Additional flow data")

    @field_validator("flow_cta", mode="after")
    @classmethod
    def validate_flow_cta_length(cls, value):
        """Validate flow CTA length"""
        if len(value) > 20:
            raise ValueError("Flow CTA must be 20 characters or less")
        return value


class FlowInteractive(BaseModel):
    """Interactive configuration for flows"""

    type: InteractiveType = Field(InteractiveType.FLOW, description="Interactive type")
    header: Optional[WhatsAppHeaderText] = Field(None, description="Optional header")
    body: Optional[WhatsAppBody] = Field(None, description="Optional body")
    footer: Optional[Dict[str, str]] = Field(None, description="Optional footer")
    action: FlowData = Field(..., description="Flow action configuration")


class FlowMessage(WhatsAppRecipient):
    """Complete flow message structure"""

    type: str = Field(default="interactive", description="Message type")
    interactive: FlowInteractive = Field(..., description="Interactive configuration")

    @field_validator("interactive", mode="after")
    @classmethod
    def validate_interactive_type(cls, value):
        """Ensure interactive type is flow"""
        if value.type != InteractiveType.FLOW:
            raise ValueError("Interactive type must be flow")
        return value


# Response Models
class WhatsAppMessageResponse(BaseModel):
    """Standard WhatsApp API response"""

    messaging_product: str
    contacts: List[Dict[str, Any]]
    messages: List[Dict[str, str]]


class WhatsAppErrorResponse(BaseModel):
    """WhatsApp API error response"""

    error: Dict[str, Any]


class WhatsAppApiResponse(BaseModel):
    """Generic WhatsApp API response wrapper"""

    success: bool = Field(..., description="Request success status")
    data: Optional[Union[WhatsAppMessageResponse, Dict[str, Any]]] = Field(None, description="Response data")
    error: Optional[Union[WhatsAppErrorResponse, str]] = Field(None, description="Error details")
    status_code: Optional[int] = Field(None, description="HTTP status code")


# Catalog Product Models (for local processing)
class CatalogProduct(BaseModel):
    """Local representation of catalog product"""

    id: str = Field(..., description="Product ID")
    retailer_id: str = Field(..., description="Retailer product ID")
    name: str = Field(..., description="Product name")
    description: Optional[str] = Field(None, description="Product description")
    price: Optional[str] = Field(None, description="Product price")
    currency: str = Field(default="ARS", description="Price currency")
    image_url: Optional[str] = Field(None, description="Product image URL")
    url: Optional[str] = Field(None, description="Product URL")
    brand: Optional[str] = Field(None, description="Product brand")
    category: Optional[str] = Field(None, description="Product category")
    availability: str = Field(default="in stock", description="Product availability")


class CatalogProductList(BaseModel):
    """List of catalog products with metadata"""

    products: List[CatalogProduct] = Field(..., description="List of products")
    total_count: int = Field(..., description="Total number of products")
    has_more: bool = Field(default=False, description="Whether more products are available")
    next_cursor: Optional[str] = Field(None, description="Cursor for pagination")


# Flow Response Models (for handling webhook responses)
class FlowDataResponse(BaseModel):
    """Flow data received from webhook"""

    flow_token: str = Field(..., description="Flow token")
    version: str = Field(..., description="Flow version")
    data: Dict[str, Any] = Field(..., description="Flow response data")
    screen: Optional[str] = Field(None, description="Current screen")
    action: Optional[str] = Field(None, description="User action")


class FlowWebhookData(BaseModel):
    """Webhook data for flow responses"""

    messaging_product: str = Field(..., description="Messaging product")
    metadata: Dict[str, Any] = Field(..., description="Message metadata")
    contacts: List[Dict[str, Any]] = Field(..., description="Contact information")
    messages: List[Dict[str, Any]] = Field(..., description="Messages with flow data")


# Validation and Configuration Models
class CatalogConfiguration(BaseModel):
    """Catalog configuration validation"""

    catalog_id: str = Field(..., description="WhatsApp Business catalog ID")
    phone_number_id: str = Field(..., description="WhatsApp phone number ID")
    access_token: str = Field(..., description="WhatsApp access token")

    def get_catalog_url(self) -> str:
        """Get the catalog API URL"""
        return f"https://graph.facebook.com/v23.0/{self.catalog_id}"

    def get_catalog_products_url(self) -> str:
        """Get the catalog products API URL"""
        return f"https://graph.facebook.com/v23.0/{self.catalog_id}/products"


class FlowConfiguration(BaseModel):
    """Flow configuration validation"""

    flow_id: str = Field(..., description="WhatsApp Flow ID")
    flow_name: str = Field(..., description="Flow name")
    flow_version: str = Field(default="1.0", description="Flow version")
    phone_number_id: str = Field(..., description="WhatsApp phone number ID")
    access_token: str = Field(..., description="WhatsApp access token")

    def get_flow_url(self) -> str:
        """Get the flow API URL"""
        return f"https://graph.facebook.com/v23.0/{self.flow_id}"


# Factory Classes for Message Creation
class MessageFactory:
    """Factory for creating WhatsApp messages following Factory pattern"""

    @staticmethod
    def create_product_list_message(
        to: str,
        catalog_id: str,
        body_text: str,
        header_text: Optional[str] = None,
        product_retailer_id: Optional[str] = None,
    ) -> ProductListMessage:
        """Create a product list message"""
        interactive_config = ProductListInteractive(
            body=WhatsAppBody(text=body_text),
            action=CatalogProductAction(catalog_id=catalog_id, product_retailer_id=product_retailer_id),
        )

        if header_text:
            interactive_config.header = WhatsAppHeaderText(text=header_text)

        return ProductListMessage(to=to, interactive=interactive_config)

    @staticmethod
    def create_flow_message(
        to: str,
        flow_id: str,
        flow_cta: str,
        body_text: Optional[str] = None,
        header_text: Optional[str] = None,
        flow_token: Optional[str] = None,
        flow_action_payload: Optional[Dict[str, Any]] = None,
    ) -> FlowMessage:
        """Create a flow message"""
        flow_data = FlowData(
            flow_id=flow_id, flow_cta=flow_cta, flow_token=flow_token, flow_action_payload=flow_action_payload
        )

        interactive_config = FlowInteractive(action=flow_data)

        if body_text:
            interactive_config.body = WhatsAppBody(text=body_text)

        if header_text:
            interactive_config.header = WhatsAppHeaderText(text=header_text)

        return FlowMessage(to=to, interactive=interactive_config)
