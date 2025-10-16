"""
API endpoints for WhatsApp Catalog and Flows functionality
Following FastAPI patterns and security best practices
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.api.dependencies import get_current_user
from app.services.phone_normalizer_pydantic import get_normalized_number_only
from app.services.whatsapp_catalog_service import WhatsAppCatalogService
from app.services.whatsapp_flows_service import FlowType, WhatsAppFlowsService
from app.services.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Catalog & Flows"])


# Request/Response Models
class SendCatalogRequest(BaseModel):
    """Request model for sending catalog"""

    phone_number: str = Field(..., description="Recipient phone number")
    body_text: str = Field(..., max_length=1024, description="Main message text")
    header_text: Optional[str] = Field(None, max_length=60, description="Optional header text")
    product_retailer_id: Optional[str] = Field(None, description="Specific product to highlight")
    catalog_id: Optional[str] = Field(None, description="Override default catalog ID")

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        if not v or len(v) < 10:
            raise ValueError("Phone number must be at least 10 digits")
        return v

    @field_validator("body_text")
    @classmethod
    def validate_body_text(cls, v: str) -> str:
        if not v or len(v.strip()) < 5:
            raise ValueError("Body text must be at least 5 characters")
        return v.strip()


class SendFlowRequest(BaseModel):
    """Request model for sending flows"""

    phone_number: str = Field(..., description="Recipient phone number")
    flow_id: str = Field(..., description="WhatsApp Flow ID")
    flow_type: str = Field(..., description="Type of flow")
    flow_cta: Optional[str] = Field(None, max_length=20, description="Call to action text")
    body_text: Optional[str] = Field(None, max_length=1024, description="Optional message body")
    header_text: Optional[str] = Field(None, max_length=60, description="Optional header text")
    context_data: Optional[Dict[str, Any]] = Field(None, description="Additional data for flow")

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        if not v or len(v) < 10:
            raise ValueError("Phone number must be at least 10 digits")
        return v

    @field_validator("flow_type")
    @classmethod
    def validate_flow_type(cls, v: str) -> str:
        valid_types = [
            FlowType.ORDER_FORM,
            FlowType.CUSTOMER_SURVEY,
            FlowType.PRODUCT_INQUIRY,
            FlowType.SUPPORT_TICKET,
            FlowType.FEEDBACK_FORM,
        ]
        if v not in valid_types:
            raise ValueError(f"Flow type must be one of: {', '.join(valid_types)}")
        return v

    @field_validator("flow_cta")
    @classmethod
    def validate_flow_cta(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 20:
            raise ValueError("Flow CTA must be 20 characters or less")
        return v


class CatalogStatusResponse(BaseModel):
    """Response model for catalog status"""

    catalog_configured: bool
    catalog_id: Optional[str] = None
    catalog_accessible: bool
    api_error: Optional[str] = None
    service_config: Dict[str, Any]


class FlowStatusResponse(BaseModel):
    """Response model for flow status"""

    flows_available: Dict[str, Dict[str, Any]]
    service_initialized: bool


class WhatsAppResponse(BaseModel):
    """Generic WhatsApp API response"""

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# Catalog Endpoints
@router.get("/catalog/status", response_model=CatalogStatusResponse)
async def get_catalog_status(_: Dict = Depends(get_current_user)) -> CatalogStatusResponse:  # noqa: B008
    """Get WhatsApp catalog configuration status"""
    try:
        catalog_service = WhatsAppCatalogService()
        catalog_info = await catalog_service.get_catalog_info()

        return CatalogStatusResponse(**catalog_info)

    except Exception as e:
        logger.error(f"Error getting catalog status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error getting catalog status: {str(e)}"
        ) from e


@router.post("/catalog/send", response_model=WhatsAppResponse)
async def send_catalog_message(request: SendCatalogRequest, _: Dict = Depends(get_current_user)) -> WhatsAppResponse:  # noqa: B008
    """Send WhatsApp catalog message to user"""
    try:
        # Normalize phone number
        normalized_phone = get_normalized_number_only(request.phone_number)
        if not normalized_phone:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone number format")

        # Initialize WhatsApp service
        whatsapp_service = WhatsAppService()

        # Send catalog
        response = await whatsapp_service.send_product_list(
            numero=normalized_phone,
            body_text=request.body_text,
            header_text=request.header_text,
            product_retailer_id=request.product_retailer_id,
            catalog_id=request.catalog_id,
        )

        if response.success:
            return WhatsAppResponse(
                success=True, message=f"Catalog sent successfully to {normalized_phone}", data=response.data
            )
        else:
            return WhatsAppResponse(success=False, message="Failed to send catalog", error=response.error)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending catalog: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error sending catalog: {str(e)}"
        ) from e


@router.get("/catalog/products")
async def get_catalog_products(
    limit: int = 10, after: Optional[str] = None, catalog_id: Optional[str] = None, _: Dict = Depends(get_current_user)  # noqa: B008
):
    """Get products from WhatsApp Business Catalog"""
    try:
        whatsapp_service = WhatsAppService()
        response = await whatsapp_service.get_catalog_products(limit=limit, after=after, catalog_id=catalog_id)

        if response.success:
            return {"success": True, "data": response.data, "pagination": {"limit": limit, "after": after}}
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=response.error)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting catalog products: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error getting catalog products: {str(e)}"
        ) from e


# Flow Endpoints
@router.get("/flows/status", response_model=FlowStatusResponse)
async def get_flows_status(_: Dict = Depends(get_current_user)) -> FlowStatusResponse:  # noqa: B008
    """Get WhatsApp flows configuration status"""
    try:
        flows_service = WhatsAppFlowsService()
        available_flows = flows_service.get_available_flows()

        return FlowStatusResponse(flows_available=available_flows, service_initialized=True)

    except Exception as e:
        logger.error(f"Error getting flows status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error getting flows status: {str(e)}"
        ) from e


@router.post("/flows/send", response_model=WhatsAppResponse)
async def send_flow_message(request: SendFlowRequest, _: Dict = Depends(get_current_user)) -> WhatsAppResponse:  # noqa: B008
    """Send WhatsApp Flow message to user"""
    try:
        # Normalize phone number
        normalized_phone = get_normalized_number_only(request.phone_number)
        if not normalized_phone:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone number format")

        # Initialize flows service
        flows_service = WhatsAppFlowsService()

        # Send flow
        response = await flows_service.send_flow(
            user_phone=normalized_phone,
            flow_type=request.flow_type,
            flow_id=request.flow_id,
            context_data=request.context_data,
            custom_cta=request.flow_cta,
            custom_body=request.body_text,
        )

        if response.success:
            return WhatsAppResponse(
                success=True, message=f"Flow sent successfully to {normalized_phone}", data=response.data
            )
        else:
            return WhatsAppResponse(success=False, message="Failed to send flow", error=response.error)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending flow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error sending flow: {str(e)}"
        ) from e


@router.get("/flows/types")
async def get_available_flow_types(_: Dict = Depends(get_current_user)):  # noqa: B008
    """Get available flow types and their configurations"""
    try:
        flows_service = WhatsAppFlowsService()
        available_flows = flows_service.get_available_flows()

        return {"success": True, "flow_types": available_flows, "total_types": len(available_flows)}

    except Exception as e:
        logger.error(f"Error getting flow types: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error getting flow types: {str(e)}"
        ) from e


# Webhook handlers for flow responses
@router.post("/flows/webhook")
async def handle_flow_webhook(webhook_data: Dict[str, Any], _: Dict = Depends(get_current_user)):  # noqa: B008
    """Handle flow response webhook from WhatsApp"""
    try:
        # This would be implemented based on WhatsApp webhook structure
        # For now, just return acknowledgment

        logger.info(f"Flow webhook received: {webhook_data}")

        return {
            "success": True,
            "message": "Webhook received and processed",
            "timestamp": webhook_data.get("timestamp"),
        }

    except Exception as e:
        logger.error(f"Error handling flow webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error handling flow webhook: {str(e)}"
        ) from e


# Utility endpoints
@router.get("/config/validate")
async def validate_whatsapp_config(_: Dict = Depends(get_current_user)):  # noqa: B008
    """Validate WhatsApp service configuration"""
    try:
        whatsapp_service = WhatsAppService()
        config_status = await whatsapp_service.verificar_configuracion()

        return {
            "success": True,
            "configuration": config_status,
            "recommendations": [
                "Ensure catalog_id is valid and accessible",
                "Test catalog API access regularly",
                "Monitor flow response rates",
            ],
        }

    except Exception as e:
        logger.error(f"Error validating config: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error validating config: {str(e)}"
        ) from e


@router.post("/test/catalog")
async def test_catalog_functionality(test_phone: str, _: Dict = Depends(get_current_user)):  # noqa: B008
    """Test catalog functionality with a test message"""
    try:
        # Normalize phone number
        normalized_phone = get_normalized_number_only(test_phone)
        if not normalized_phone:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone number format")

        # Test catalog service
        catalog_service = WhatsAppCatalogService()

        # Simulate a product search to test the decision engine
        test_products = [
            {"id": "test_1", "name": "Test Product 1", "price": 100.0},
            {"id": "test_2", "name": "Test Product 2", "price": 200.0},
        ]

        test_intent = {"intent": "search_specific_products", "search_terms": ["test", "product"], "category": None}

        response = await catalog_service.send_smart_product_response(
            user_phone=normalized_phone,
            user_message="Show me test products",
            intent_analysis=test_intent,
            local_products=test_products,
        )

        return {
            "success": True,
            "test_result": {"catalog_sent": response.success, "response_data": response.data, "error": response.error},
            "test_phone": normalized_phone,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing catalog: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error testing catalog: {str(e)}"
        ) from e

