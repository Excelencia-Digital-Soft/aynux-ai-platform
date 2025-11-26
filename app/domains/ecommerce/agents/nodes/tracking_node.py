"""
Tracking Node - E-commerce domain node for order tracking.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any

from app.core.agents import BaseAgent
from app.core.utils.tracing import trace_async_method

logger = logging.getLogger(__name__)


class TrackingNode(BaseAgent):
    """E-commerce node specialized in order tracking and shipping status"""

    def __init__(self, ollama=None, config: dict[str, Any] | None = None):
        super().__init__("tracking_node", config or {}, ollama=ollama)

        # Initialize simulated tools
        self.order_tool = OrderLookupTool(None)
        self.shipping_tool = ShippingTrackingTool(None)
        self.delivery_tool = DeliveryEstimationTool()
        self.notification_tool = TrackingNotificationTool()

    @trace_async_method(
        name="tracking_node_process",
        run_type="chain",
        metadata={"agent_type": "tracking_node", "domain": "ecommerce"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Process order tracking queries"""
        user_message = message
        entities = (
            state_dict.get("current_intent", {}).get("entities", {})
            if state_dict.get("current_intent")
            else {}
        )
        customer_id = (
            state_dict.get("customer", {}).get("customer_id") if state_dict.get("customer") else None
        )

        # Extract order numbers from message
        order_numbers = self._extract_order_numbers(user_message, entities)

        if not order_numbers and not customer_id:
            return self._handle_no_order_info()

        # Find orders (simulated - in production would be async)
        if order_numbers:
            orders = self._get_orders_by_numbers_sync(order_numbers, customer_id)
        elif customer_id is not None:
            # Find recent orders for customer
            orders = self.order_tool.get_recent_orders_sync(customer_id)
        else:
            orders = []

        if not orders:
            return self._handle_no_orders_found(order_numbers)

        # Get tracking info for each order
        tracking_info = []
        for order in orders:
            tracking = self._get_tracking_details_sync(order)
            tracking_info.append(tracking)

        # Generate response based on number of orders
        if len(tracking_info) == 1:
            return self._format_single_order_response(tracking_info[0])
        else:
            return self._format_multiple_orders_response(tracking_info)

    def _extract_order_numbers(self, message: str, entities: dict) -> list[str]:
        """Extract order numbers from message"""
        order_numbers = []

        # First check entities
        if entities.get("order_numbers"):
            order_numbers.extend(entities["order_numbers"])

        # Search for additional patterns
        patterns = [
            r"#(\d{6,})",  # #123456
            r"orden\s*[:--]?\s*(\d{6,})",  # orden: 123456
            r"pedido\s*[:--]?\s*(\d{6,})",  # pedido: 123456
            r"tracking\s*[:--]?\s*([A-Z0-9]{8,})",  # tracking: ABC123XYZ
            r"\b([A-Z]{2,3}\d{8,})\b",  # FX12345678
        ]

        for pattern in patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            order_numbers.extend(matches)

        # Remove duplicates
        return list(set(order_numbers))

    def _get_orders_by_numbers_sync(
        self, order_numbers: list[str], customer_id: str | None
    ) -> list[dict]:
        """Find orders by numbers"""
        orders = []

        for number in order_numbers:
            order = self.order_tool.get_order_by_number_sync(number, customer_id)
            if order:
                orders.append(order)

        return orders

    def _get_tracking_details_sync(self, order: dict) -> dict[str, Any]:
        """Get complete tracking details for an order"""
        # Basic order info
        tracking_info = {
            "order": order,
            "tracking_number": order.get("tracking_number"),
            "carrier": order.get("carrier", "unknown"),
            "status": "unknown",
            "location": "unknown",
            "events": [],
            "estimated_delivery": None,
        }

        # Get carrier tracking
        if order.get("tracking_number") and order.get("carrier"):
            carrier_tracking = self.shipping_tool.get_tracking_info_sync(
                order["tracking_number"], order["carrier"]
            )

            if carrier_tracking:
                tracking_info.update(carrier_tracking)

        # Estimate delivery
        if tracking_info["status"] != "delivered":
            estimation = self.delivery_tool.estimate_delivery_sync(
                tracking_info, order.get("shipping_method")
            )
            tracking_info["estimated_delivery"] = estimation

        return tracking_info

    def _format_single_order_response(self, tracking: dict) -> dict[str, Any]:
        """Format response for a single order"""
        order = tracking["order"]

        # Header
        response = f"**Rastreo del Pedido #{order['order_number']}**\n\n"

        # Current status with emoji
        status_emoji = self._get_status_emoji(tracking["status"])
        response += f"{status_emoji} **Estado:** {self._translate_status(tracking['status'])}\n"

        # Current location
        if tracking.get("location") and tracking["location"] != "unknown":
            response += f"**Ubicacion:** {tracking['location']}\n"

        # Shipping info
        response += f"**Transportista:** {tracking['carrier'].upper()}\n"
        response += f"**Numero de rastreo:** `{tracking['tracking_number']}`\n\n"

        # Event timeline
        if tracking.get("events"):
            response += "**Historial del envio:**\n"
            for event in tracking["events"][:5]:  # Show last 5 events
                response += f"- {event['date']} - {event['description']}\n"
                if event.get("location"):
                    response += f"  {event['location']}\n"
            response += "\n"

        # Delivery estimation
        if tracking["status"] != "delivered":
            if tracking.get("estimated_delivery"):
                response += f"**Entrega estimada:** {tracking['estimated_delivery']}\n"
            else:
                response += "**Entrega estimada:** Calculando...\n"
        else:
            response += f"**Entregado el:** {tracking.get('delivery_date', 'Fecha no disponible')}\n"
            if tracking.get("delivered_to"):
                response += f"**Recibido por:** {tracking['delivered_to']}\n"

        # Order details
        response += "\n**Contenido del pedido:**\n"
        for item in order.get("items", [])[:3]:
            response += f"- {item['quantity']}x {item['name']}\n"

        # Useful links
        if tracking.get("tracking_url"):
            response += f"\n[Ver en sitio del transportista]({tracking['tracking_url']})\n"

        # Additional options
        response += "\nNecesitas ayuda con algo mas sobre tu pedido?"

        return {
            "messages": [{"role": "assistant", "content": response}],
            "current_agent": self.name,
            "agent_history": [self.name],
            "retrieved_data": {"tracking_info": tracking, "order_number": order["order_number"]},
            "is_complete": True,
        }

    def _format_multiple_orders_response(self, tracking_list: list[dict]) -> dict[str, Any]:
        """Format response for multiple orders"""
        response = f"**Rastreo de {len(tracking_list)} pedidos:**\n\n"

        for idx, tracking in enumerate(tracking_list, 1):
            order = tracking["order"]
            status_emoji = self._get_status_emoji(tracking["status"])

            response += f"**{idx}. Pedido #{order['order_number']}**\n"
            response += f"   {status_emoji} {self._translate_status(tracking['status'])}\n"

            # Location or delivery date
            if tracking["status"] == "delivered":
                response += f"   Entregado: {tracking.get('delivery_date', 'Fecha no disponible')}\n"
            else:
                response += f"   {tracking.get('location', 'En transito')}\n"
                if tracking.get("estimated_delivery"):
                    response += f"   Entrega estimada: {tracking['estimated_delivery']}\n"

            response += f"   {tracking['carrier'].upper()} - `{tracking['tracking_number']}`\n"
            response += "\n"

        response += "Selecciona el numero del pedido para ver mas detalles."

        return {
            "messages": [{"role": "assistant", "content": response}],
            "current_agent": self.name,
            "agent_history": [self.name],
            "retrieved_data": {"tracking_list": tracking_list, "total_orders": len(tracking_list)},
            "is_complete": True,
        }

    def _handle_no_order_info(self) -> dict[str, Any]:
        """Handle when no order info is provided"""
        response = "Para rastrear tu pedido, necesito:\n\n"
        response += "- **Numero de orden** (ej: #123456)\n"
        response += "- **Numero de rastreo** (ej: FX12345678)\n\n"
        response += "Tambien puedo mostrar tus pedidos recientes si lo prefieres."

        return {
            "messages": [{"role": "assistant", "content": response}],
            "current_agent": self.name,
            "agent_history": [self.name],
            "is_complete": False,
        }

    def _handle_no_orders_found(self, order_numbers: list[str]) -> dict[str, Any]:
        """Handle when no orders are found"""
        if order_numbers:
            response = f"No encontre pedidos con los numeros: {', '.join(order_numbers)}\n\n"
            response += "Por favor verifica:\n"
            response += "- Que el numero sea correcto\n"
            response += "- Que el pedido este asociado a tu cuenta\n"
        else:
            response = "No encontre pedidos recientes en tu cuenta.\n\n"
            response += "Si realizaste una compra recientemente, el pedido puede tardar unos minutos en aparecer."

        response += "\nNecesitas ayuda con algo mas?"

        return {
            "messages": [{"role": "assistant", "content": response}],
            "current_agent": self.name,
            "agent_history": [self.name],
            "retrieved_data": {"searched_numbers": order_numbers},
            "is_complete": True,
        }

    def _get_status_emoji(self, status: str) -> str:
        """Return appropriate emoji for status"""
        status_emojis = {
            "pending": "[PENDING]",
            "processing": "[PROCESSING]",
            "shipped": "[SHIPPED]",
            "in_transit": "[IN_TRANSIT]",
            "out_for_delivery": "[OUT_FOR_DELIVERY]",
            "delivered": "[DELIVERED]",
            "failed": "[FAILED]",
            "returned": "[RETURNED]",
            "cancelled": "[CANCELLED]",
        }
        return status_emojis.get(status.lower(), "[UNKNOWN]")

    def _translate_status(self, status: str) -> str:
        """Translate status to Spanish"""
        translations = {
            "pending": "Pendiente",
            "processing": "Procesando",
            "shipped": "Enviado",
            "in_transit": "En transito",
            "out_for_delivery": "En reparto",
            "delivered": "Entregado",
            "failed": "Fallo en entrega",
            "returned": "Devuelto",
            "cancelled": "Cancelado",
        }
        return translations.get(status.lower(), status)


# Tracking Tools
class OrderLookupTool:
    """Looks up orders in database"""

    def __init__(self, db_connection):
        self.db = db_connection

    def get_order_by_number_sync(self, order_number: str, customer_id: str | None = None) -> dict | None:
        """Find an order by number"""
        _ = customer_id  # unused in simulation
        # In production this would query DB
        # Simulation
        if order_number.startswith("1234"):
            return {
                "order_number": order_number,
                "customer_id": customer_id,
                "status": "shipped",
                "created_at": datetime.now() - timedelta(days=2),
                "tracking_number": f"FX{order_number}",
                "carrier": "fedex",
                "shipping_method": "express",
                "items": [{"name": "Laptop Gaming ASUS", "quantity": 1, "price": 45000}],
            }
        return None

    def get_recent_orders_sync(self, customer_id: str) -> list[dict]:
        """Get recent orders for a customer"""
        # In production this would query DB
        # Simulation
        if not customer_id:
            return []

        return [
            {
                "order_number": "123456",
                "customer_id": customer_id,
                "status": "delivered",
                "created_at": datetime.now() - timedelta(days=7),
                "tracking_number": "FX123456789",
                "carrier": "fedex",
                "items": [{"name": "Mouse Logitech G502", "quantity": 1, "price": 2500}],
            },
            {
                "order_number": "123457",
                "customer_id": customer_id,
                "status": "in_transit",
                "created_at": datetime.now() - timedelta(days=1),
                "tracking_number": "UPS987654321",
                "carrier": "ups",
                "items": [{"name": "Teclado Mecanico", "quantity": 1, "price": 5000}],
            },
        ]


class ShippingTrackingTool:
    """Gets tracking info from carriers"""

    def __init__(self, shipping_apis):
        self.shipping_apis = shipping_apis

    def get_tracking_info_sync(self, tracking_number: str, carrier: str) -> dict | None:
        """Get tracking info from carrier"""
        # In production this would call real APIs
        # Simulation

        if carrier.lower() == "fedex":
            return {
                "status": "in_transit",
                "location": "Centro de distribucion - Buenos Aires",
                "last_update": datetime.now() - timedelta(hours=3),
                "events": [
                    {
                        "date": (datetime.now() - timedelta(days=2)).strftime("%d/%m %H:%M"),
                        "description": "Paquete recibido",
                        "location": "Centro de envios",
                    },
                    {
                        "date": (datetime.now() - timedelta(days=1)).strftime("%d/%m %H:%M"),
                        "description": "En transito",
                        "location": "Hub Ezeiza",
                    },
                    {
                        "date": (datetime.now() - timedelta(hours=3)).strftime("%d/%m %H:%M"),
                        "description": "Llego a centro de distribucion",
                        "location": "Buenos Aires",
                    },
                ],
                "tracking_url": f"https://fedex.com/track/{tracking_number}",
            }

        elif carrier.lower() == "ups":
            return {
                "status": "out_for_delivery",
                "location": "En reparto - CABA",
                "last_update": datetime.now() - timedelta(hours=1),
                "events": [
                    {
                        "date": datetime.now().strftime("%d/%m %H:%M"),
                        "description": "Salio a reparto",
                        "location": "CABA",
                    }
                ],
                "tracking_url": f"https://ups.com/track/{tracking_number}",
            }

        return None


class DeliveryEstimationTool:
    """Estimates delivery dates"""

    def estimate_delivery_sync(self, tracking_info: dict, shipping_method: str | None = None) -> str:
        """Estimate delivery date based on current status"""
        status = tracking_info.get("status", "unknown")

        # Estimates by status
        if status == "shipped":
            days_to_add = 3 if shipping_method == "express" else 5
        elif status == "in_transit":
            days_to_add = 2 if shipping_method == "express" else 3
        elif status == "out_for_delivery":
            days_to_add = 0  # Today
        else:
            days_to_add = 7  # Default

        estimated_date = datetime.now() + timedelta(days=days_to_add)

        # Friendly format
        if days_to_add == 0:
            return "Hoy"
        elif days_to_add == 1:
            return "Manana"
        else:
            return estimated_date.strftime("%A %d de %B")


class TrackingNotificationTool:
    """Manages tracking notifications"""

    async def setup_notifications(
        self, order_number: str, customer_id: str, notification_preferences: dict
    ) -> bool:
        """Configure notifications for an order"""
        logger.debug(f"setup_notifications: {order_number}, {customer_id}, {notification_preferences}")
        # In production this would configure webhooks or subscriptions
        return True

    async def send_status_update(
        self, order_number: str, new_status: str, customer_contact: str
    ) -> bool:
        """Send status update"""
        logger.debug(f"Send status update: {order_number}, {new_status}, {customer_contact}")
        # In production this would send SMS/Email/WhatsApp
        return True


# Alias for backward compatibility
TrackingAgent = TrackingNode
