"""
WhatsApp Flows Service - Specialized service for WhatsApp Flows operations
Following SOLID principles: Single Responsibility, Open/Closed, Dependency Inversion
"""

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.config.settings import get_settings
from app.integrations.whatsapp.service import WhatsAppService
from app.models.whatsapp_advanced import (
    FlowDataResponse,
    WhatsAppApiResponse,
)

logger = logging.getLogger(__name__)


class IFlowRepository(ABC):
    """Interface for flow data persistence (Interface Segregation Principle)"""

    @abstractmethod
    async def save_flow_session(
        self, user_phone: str, flow_id: str, flow_token: str, session_data: Dict[str, Any]
    ) -> bool:
        """Save flow session data"""
        pass

    @abstractmethod
    async def get_flow_session(self, user_phone: str, flow_token: str) -> Optional[Dict[str, Any]]:
        """Retrieve flow session data"""
        pass

    @abstractmethod
    async def update_flow_session(self, user_phone: str, flow_token: str, update_data: Dict[str, Any]) -> bool:
        """Update existing flow session"""
        pass

    @abstractmethod
    async def complete_flow_session(self, user_phone: str, flow_token: str, completion_data: Dict[str, Any]) -> bool:
        """Mark flow session as completed"""
        pass


class IFlowHandler(ABC):
    """Interface for flow-specific business logic (Interface Segregation Principle)"""

    @abstractmethod
    async def process_flow_data(self, flow_id: str, user_phone: str, flow_data: FlowDataResponse) -> Dict[str, Any]:
        """Process flow response data and return next actions"""
        pass

    @abstractmethod
    async def validate_flow_completion(self, flow_id: str, flow_data: FlowDataResponse) -> Tuple[bool, List[str]]:
        """Validate flow completion and return validation results"""
        pass


class FlowType:
    """Flow type constants"""

    ORDER_FORM = "order_form"
    CUSTOMER_SURVEY = "customer_survey"
    PRODUCT_INQUIRY = "product_inquiry"
    SUPPORT_TICKET = "support_ticket"
    FEEDBACK_FORM = "feedback_form"


class WhatsAppFlowsService:
    """
    Specialized service for WhatsApp Flows operations
    Following Single Responsibility Principle
    """

    def __init__(
        self,
        whatsapp_service: Optional[WhatsAppService] = None,
        flow_repository: Optional[IFlowRepository] = None,
        flow_handlers: Optional[Dict[str, IFlowHandler]] = None,
    ):
        """
        Initialize with dependency injection (Dependency Inversion Principle)

        Args:
            whatsapp_service: WhatsApp service for API calls
            flow_repository: Repository for flow data persistence
            flow_handlers: Handlers for different flow types
        """
        self.settings = get_settings()
        self.whatsapp_service = whatsapp_service or WhatsAppService()
        self.flow_repository = flow_repository
        self.flow_handlers = flow_handlers or {}

        # Default flow configurations
        self.default_flows = {
            FlowType.ORDER_FORM: {"name": "Formulario de Pedido", "cta": "Hacer Pedido", "timeout_minutes": 30},
            FlowType.CUSTOMER_SURVEY: {"name": "Encuesta de Satisfacción", "cta": "Responder", "timeout_minutes": 15},
            FlowType.PRODUCT_INQUIRY: {"name": "Consulta de Producto", "cta": "Consultar", "timeout_minutes": 20},
            FlowType.SUPPORT_TICKET: {"name": "Ticket de Soporte", "cta": "Reportar", "timeout_minutes": 45},
            FlowType.FEEDBACK_FORM: {"name": "Formulario de Feedback", "cta": "Opinar", "timeout_minutes": 10},
        }

        logger.info("WhatsApp Flows Service initialized")

    async def send_flow(
        self,
        user_phone: str,
        flow_type: str,
        flow_id: str,
        context_data: Optional[Dict[str, Any]] = None,
        custom_cta: Optional[str] = None,
        custom_body: Optional[str] = None,
    ) -> WhatsAppApiResponse:
        """
        Send a WhatsApp Flow to user

        Args:
            user_phone: User's phone number
            flow_type: Type of flow (from FlowType constants)
            flow_id: WhatsApp Flow ID
            context_data: Additional data to pass to flow
            custom_cta: Custom call-to-action text
            custom_body: Custom body text

        Returns:
            WhatsAppApiResponse with result
        """
        try:
            # Get flow configuration
            flow_config = self.default_flows.get(flow_type, {})
            if not flow_config:
                return WhatsAppApiResponse(success=False, error=f"Unknown flow type: {flow_type}")

            # Generate flow token for session tracking
            flow_token = self._generate_flow_token(user_phone, flow_type)

            # Prepare flow data
            flow_data = {
                "user_context": context_data or {},
                "flow_type": flow_type,
                "started_at": datetime.now(UTC).isoformat(),
                "timeout_at": (
                    datetime.now(UTC) + timedelta(minutes=flow_config.get("timeout_minutes", 30))
                ).isoformat(),
            }

            # Save flow session if repository available
            if self.flow_repository:
                await self.flow_repository.save_flow_session(user_phone, flow_id, flow_token, flow_data)

            # Prepare message content
            cta_text = custom_cta or flow_config.get("cta", "Continuar")
            body_text = custom_body or self._generate_default_body(flow_type, flow_config)

            # Send flow message
            response = await self.whatsapp_service.send_flow_message(
                numero=user_phone,
                flow_id=flow_id,
                flow_cta=cta_text,
                body_text=body_text,
                flow_token=flow_token,
                flow_data=flow_data,
            )

            if response.success:
                logger.info(f"Flow {flow_type} sent successfully to {user_phone}")

            return response

        except Exception as e:
            error_msg = f"Error sending flow: {str(e)}"
            logger.error(error_msg)
            return WhatsAppApiResponse(success=False, error=error_msg)

    async def process_flow_response(self, user_phone: str, flow_response: FlowDataResponse) -> Dict[str, Any]:
        """
        Process flow response from webhook

        Args:
            user_phone: User's phone number
            flow_response: Flow response data

        Returns:
            Processing results and next actions
        """
        try:
            # Get flow session data
            session_data = None
            if self.flow_repository:
                session_data = await self.flow_repository.get_flow_session(user_phone, flow_response.flow_token)

            if not session_data:
                logger.warning(f"No session found for flow token: {flow_response.flow_token}")
                return {"success": False, "error": "Session not found or expired", "action": "restart_flow"}

            flow_type = session_data.get("flow_type")

            # Use specific handler if available
            if flow_type in self.flow_handlers:
                handler = self.flow_handlers[flow_type]
                result = await handler.process_flow_data(
                    flow_response.flow_token.split("_")[0],  # Extract flow_id
                    user_phone,
                    flow_response,
                )

                # Update session with results
                if self.flow_repository:
                    await self.flow_repository.update_flow_session(user_phone, flow_response.flow_token, result)

                return result

            # Default processing
            return await self._default_flow_processing(user_phone, flow_response, session_data)

        except Exception as e:
            error_msg = f"Error processing flow response: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg, "action": "error_recovery"}

    async def _default_flow_processing(
        self, user_phone: str, flow_response: FlowDataResponse, session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Default flow processing logic"""

        flow_type = session_data.get("flow_type")
        response_data = flow_response.data

        # Basic validation
        if not response_data:
            return {"success": False, "error": "Empty flow response", "action": "request_retry"}

        # Process based on flow type
        if flow_type == FlowType.ORDER_FORM:
            return await self._process_order_form(user_phone, response_data, session_data)
        elif flow_type == FlowType.CUSTOMER_SURVEY:
            return await self._process_customer_survey(user_phone, response_data, session_data)
        elif flow_type == FlowType.PRODUCT_INQUIRY:
            return await self._process_product_inquiry(user_phone, response_data, session_data)
        elif flow_type == FlowType.SUPPORT_TICKET:
            return await self._process_support_ticket(user_phone, response_data, session_data)
        elif flow_type == FlowType.FEEDBACK_FORM:
            return await self._process_feedback_form(user_phone, response_data, session_data)
        else:
            return {"success": True, "message": "Flow completed", "action": "flow_complete", "data": response_data}

    async def _process_order_form(
        self, user_phone: str, response_data: Dict[str, Any], session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process order form submission"""

        required_fields = ["products", "customer_info", "delivery_address"]
        missing_fields = [field for field in required_fields if field not in response_data]

        if missing_fields:
            return {
                "success": False,
                "error": f"Missing required fields: {', '.join(missing_fields)}",
                "action": "request_completion",
                "missing_fields": missing_fields,
            }

        # Create order record (would integrate with order management system)
        order_data = {
            "user_phone": user_phone,
            "products": response_data.get("products", []),
            "customer_info": response_data.get("customer_info", {}),
            "delivery_address": response_data.get("delivery_address", {}),
            "created_at": datetime.now(UTC).isoformat(),
            "status": "pending_confirmation",
        }

        return {
            "success": True,
            "message": "Pedido recibido correctamente",
            "action": "order_created",
            "order_data": order_data,
            "next_steps": ["send_order_confirmation", "process_payment", "schedule_delivery"],
        }

    async def _process_customer_survey(
        self, user_phone: str, response_data: Dict[str, Any], session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process customer survey submission"""

        survey_data = {
            "user_phone": user_phone,
            "responses": response_data,
            "completed_at": datetime.now(UTC).isoformat(),
            "session_id": session_data.get("session_id"),
        }

        return {
            "success": True,
            "message": "¡Gracias por tu feedback!",
            "action": "survey_completed",
            "survey_data": survey_data,
        }

    async def _process_product_inquiry(
        self, user_phone: str, response_data: Dict[str, Any], session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process product inquiry submission"""

        inquiry_data = {
            "user_phone": user_phone,
            "product_id": response_data.get("product_id"),
            "questions": response_data.get("questions", []),
            "contact_preference": response_data.get("contact_preference", "whatsapp"),
            "created_at": datetime.now(UTC).isoformat(),
        }

        return {
            "success": True,
            "message": "Consulta recibida. Te contactaremos pronto.",
            "action": "inquiry_created",
            "inquiry_data": inquiry_data,
            "next_steps": ["assign_to_agent", "send_acknowledgment"],
        }

    async def _process_support_ticket(
        self, user_phone: str, response_data: Dict[str, Any], session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process support ticket submission"""

        ticket_data = {
            "user_phone": user_phone,
            "category": response_data.get("category"),
            "priority": response_data.get("priority", "medium"),
            "description": response_data.get("description"),
            "attachments": response_data.get("attachments", []),
            "created_at": datetime.now(UTC).isoformat(),
            "status": "open",
        }

        ticket_id = f"TK_{uuid.uuid4().hex[:8].upper()}"

        return {
            "success": True,
            "message": f"Ticket {ticket_id} creado exitosamente",
            "action": "ticket_created",
            "ticket_id": ticket_id,
            "ticket_data": ticket_data,
            "next_steps": ["assign_to_support", "send_ticket_details"],
        }

    async def _process_feedback_form(
        self, user_phone: str, response_data: Dict[str, Any], session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process feedback form submission"""

        feedback_data = {
            "user_phone": user_phone,
            "rating": response_data.get("rating"),
            "feedback_text": response_data.get("feedback_text"),
            "improvement_suggestions": response_data.get("improvement_suggestions", []),
            "created_at": datetime.now(UTC).isoformat(),
        }

        return {
            "success": True,
            "message": "Gracias por tu feedback",
            "action": "feedback_received",
            "feedback_data": feedback_data,
        }

    def _generate_flow_token(self, user_phone: str, flow_type: str) -> str:
        """Generate unique flow token for session tracking"""
        timestamp = int(datetime.now(UTC).timestamp())
        unique_id = uuid.uuid4().hex[:8]
        return f"{flow_type}_{user_phone[-4:]}_{timestamp}_{unique_id}"

    def _generate_default_body(self, flow_type: str, flow_config: Dict[str, Any]) -> str:
        """Generate default body text for flow messages"""

        flow_name = flow_config.get("name", "Formulario")
        timeout_minutes = flow_config.get("timeout_minutes", 30)

        return (
            f"Te invito a completar nuestro {flow_name}. "
            f"Tienes {timeout_minutes} minutos para completarlo. "
            f"Toca el botón para comenzar."
        )

    async def get_active_flow_sessions(self, user_phone: str) -> List[Dict[str, Any]]:
        """Get active flow sessions for a user"""
        if not self.flow_repository:
            return []

        try:
            # This would be implemented based on repository capabilities
            # For now, return empty list
            return []
        except Exception as e:
            logger.error(f"Error getting active sessions: {str(e)}")
            return []

    async def cancel_flow_session(self, user_phone: str, flow_token: str) -> bool:
        """Cancel an active flow session"""
        if not self.flow_repository:
            return False

        try:
            return await self.flow_repository.complete_flow_session(user_phone, flow_token, {"status": "cancelled"})
        except Exception as e:
            logger.error(f"Error cancelling flow session: {str(e)}")
            return False

    def get_available_flows(self) -> Dict[str, Dict[str, Any]]:
        """Get available flow types and their configurations"""
        return self.default_flows.copy()


# Default implementations for dependency injection


class InMemoryFlowRepository(IFlowRepository):
    """In-memory implementation for development/testing"""

    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def _get_session_key(self, user_phone: str, flow_token: str) -> str:
        return f"{user_phone}:{flow_token}"

    async def save_flow_session(
        self, user_phone: str, flow_id: str, flow_token: str, session_data: Dict[str, Any]
    ) -> bool:
        key = self._get_session_key(user_phone, flow_token)
        session_data.update({"flow_id": flow_id, "user_phone": user_phone, "flow_token": flow_token})
        self._sessions[key] = session_data
        return True

    async def get_flow_session(self, user_phone: str, flow_token: str) -> Optional[Dict[str, Any]]:
        key = self._get_session_key(user_phone, flow_token)
        return self._sessions.get(key)

    async def update_flow_session(self, user_phone: str, flow_token: str, update_data: Dict[str, Any]) -> bool:
        key = self._get_session_key(user_phone, flow_token)
        if key in self._sessions:
            self._sessions[key].update(update_data)
            return True
        return False

    async def complete_flow_session(self, user_phone: str, flow_token: str, completion_data: Dict[str, Any]) -> bool:
        key = self._get_session_key(user_phone, flow_token)
        if key in self._sessions:
            self._sessions[key].update(completion_data)
            self._sessions[key]["completed_at"] = datetime.now(UTC).isoformat()
            return True
        return False


class DefaultOrderFormHandler(IFlowHandler):
    """Default handler for order form flows"""

    async def process_flow_data(self, flow_id: str, user_phone: str, flow_data: FlowDataResponse) -> Dict[str, Any]:
        """Process order form data with enhanced validation"""

        data = flow_data.data

        # Enhanced validation
        is_valid, errors = await self.validate_flow_completion(flow_id, flow_data)

        if not is_valid:
            return {"success": False, "errors": errors, "action": "validation_failed"}

        # Process order
        return {
            "success": True,
            "action": "order_processed",
            "order_id": f"ORD_{uuid.uuid4().hex[:8].upper()}",
            "data": data,
        }

    async def validate_flow_completion(self, flow_id: str, flow_data: FlowDataResponse) -> Tuple[bool, List[str]]:
        """Validate order form completion"""

        errors = []
        data = flow_data.data

        # Required fields validation
        required_fields = ["products", "customer_name", "delivery_address"]
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Campo requerido: {field}")

        # Product validation
        products = data.get("products", [])
        if not isinstance(products, list) or len(products) == 0:
            errors.append("Debe seleccionar al menos un producto")

        return len(errors) == 0, errors
