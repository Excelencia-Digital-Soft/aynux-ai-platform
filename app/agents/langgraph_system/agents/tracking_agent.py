"""
Agente especializado en rastreo de pedidos
"""
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.agents.langgraph_system.agents.base_agent import BaseAgent
from app.agents.langgraph_system.models import SharedState


class TrackingAgent(BaseAgent):
    """Agente especializado en rastreo de pedidos y estado de envíos"""
    
    def __init__(self, db_connection, shipping_apis, llm):
        super().__init__("tracking_agent")
        self.db = db_connection
        self.shipping_apis = shipping_apis
        self.llm = llm
        
        # Inicializar herramientas
        self.tools = [
            OrderLookupTool(db_connection),
            ShippingTrackingTool(shipping_apis),
            DeliveryEstimationTool(),
            TrackingNotificationTool()
        ]
    
    async def _process_internal(self, state: SharedState) -> Dict[str, Any]:
        """Procesa consultas de rastreo de pedidos"""
        user_message = state.get_last_user_message()
        entities = state.current_intent.entities if state.current_intent else {}
        customer_id = state.customer.customer_id if state.customer else None
        
        # Extraer números de orden del mensaje
        order_numbers = self._extract_order_numbers(user_message, entities)
        
        if not order_numbers and not customer_id:
            return self._handle_no_order_info()
        
        # Buscar órdenes
        if order_numbers:
            orders = await self._get_orders_by_numbers(order_numbers, customer_id)
        else:
            # Buscar órdenes recientes del cliente
            orders = await self.tools[0].get_recent_orders(customer_id, limit=3)
        
        if not orders:
            return self._handle_no_orders_found(order_numbers)
        
        # Obtener información de tracking para cada orden
        tracking_info = []
        for order in orders:
            tracking = await self._get_tracking_details(order)
            tracking_info.append(tracking)
        
        # Generar respuesta según el número de órdenes
        if len(tracking_info) == 1:
            return self._format_single_order_response(tracking_info[0])
        else:
            return self._format_multiple_orders_response(tracking_info)
    
    def _extract_order_numbers(self, message: str, entities: Dict) -> List[str]:
        """Extrae números de orden del mensaje"""
        order_numbers = []
        
        # Primero verificar entidades
        if entities.get("order_numbers"):
            order_numbers.extend(entities["order_numbers"])
        
        # Buscar patrones adicionales
        patterns = [
            r'#(\d{6,})',  # #123456
            r'orden\s*[:‑–—-]?\s*(\d{6,})',  # orden: 123456
            r'pedido\s*[:‑–—-]?\s*(\d{6,})',  # pedido: 123456
            r'tracking\s*[:‑–—-]?\s*([A-Z0-9]{8,})',  # tracking: ABC123XYZ
            r'\b([A-Z]{2,3}\d{8,})\b',  # FX12345678
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            order_numbers.extend(matches)
        
        # Eliminar duplicados
        return list(set(order_numbers))
    
    async def _get_orders_by_numbers(
        self, 
        order_numbers: List[str], 
        customer_id: Optional[str]
    ) -> List[Dict]:
        """Busca órdenes por números"""
        orders = []
        
        for number in order_numbers:
            order = await self.tools[0].get_order_by_number(number, customer_id)
            if order:
                orders.append(order)
        
        return orders
    
    async def _get_tracking_details(self, order: Dict) -> Dict[str, Any]:
        """Obtiene detalles completos de tracking para una orden"""
        # Información básica de la orden
        tracking_info = {
            "order": order,
            "tracking_number": order.get("tracking_number"),
            "carrier": order.get("carrier", "unknown"),
            "status": "unknown",
            "location": "unknown",
            "events": [],
            "estimated_delivery": None
        }
        
        # Obtener tracking del carrier
        if order.get("tracking_number") and order.get("carrier"):
            carrier_tracking = await self.tools[1].get_tracking_info(
                order["tracking_number"],
                order["carrier"]
            )
            
            if carrier_tracking:
                tracking_info.update(carrier_tracking)
        
        # Estimar entrega
        if tracking_info["status"] != "delivered":
            estimation = await self.tools[2].estimate_delivery(
                tracking_info,
                order.get("shipping_method")
            )
            tracking_info["estimated_delivery"] = estimation
        
        return tracking_info
    
    def _format_single_order_response(self, tracking: Dict) -> Dict[str, Any]:
        """Formatea respuesta para una sola orden"""
        order = tracking["order"]
        
        # Encabezado
        response = f"📦 **Rastreo del Pedido #{order['order_number']}**\n\n"
        
        # Estado actual con emoji
        status_emoji = self._get_status_emoji(tracking["status"])
        response += f"{status_emoji} **Estado:** {self._translate_status(tracking['status'])}\n"
        
        # Ubicación actual
        if tracking.get("location") and tracking["location"] != "unknown":
            response += f"📍 **Ubicación:** {tracking['location']}\n"
        
        # Información del envío
        response += f"🚚 **Transportista:** {tracking['carrier'].upper()}\n"
        response += f"🔢 **Número de rastreo:** `{tracking['tracking_number']}`\n\n"
        
        # Timeline de eventos
        if tracking.get("events"):
            response += "📋 **Historial del envío:**\n"
            for event in tracking["events"][:5]:  # Mostrar últimos 5 eventos
                response += f"• {event['date']} - {event['description']}\n"
                if event.get("location"):
                    response += f"  📍 {event['location']}\n"
            response += "\n"
        
        # Estimación de entrega
        if tracking["status"] != "delivered":
            if tracking.get("estimated_delivery"):
                response += f"📅 **Entrega estimada:** {tracking['estimated_delivery']}\n"
            else:
                response += "📅 **Entrega estimada:** Calculando...\n"
        else:
            response += f"✅ **Entregado el:** {tracking.get('delivery_date', 'Fecha no disponible')}\n"
            if tracking.get("delivered_to"):
                response += f"👤 **Recibido por:** {tracking['delivered_to']}\n"
        
        # Detalles del pedido
        response += "\n📦 **Contenido del pedido:**\n"
        for item in order.get("items", [])[:3]:
            response += f"• {item['quantity']}x {item['name']}\n"
        
        # Enlaces útiles
        if tracking.get("tracking_url"):
            response += f"\n🔗 [Ver en sitio del transportista]({tracking['tracking_url']})\n"
        
        # Opciones adicionales
        response += "\n¿Necesitas ayuda con algo más sobre tu pedido?"
        
        return {
            "text": response,
            "data": {
                "tracking_info": tracking,
                "order_number": order["order_number"]
            },
            "tools_used": ["OrderLookupTool", "ShippingTrackingTool", "DeliveryEstimationTool"]
        }
    
    def _format_multiple_orders_response(self, tracking_list: List[Dict]) -> Dict[str, Any]:
        """Formatea respuesta para múltiples órdenes"""
        response = f"📦 **Rastreo de {len(tracking_list)} pedidos:**\n\n"
        
        for idx, tracking in enumerate(tracking_list, 1):
            order = tracking["order"]
            status_emoji = self._get_status_emoji(tracking["status"])
            
            response += f"**{idx}. Pedido #{order['order_number']}**\n"
            response += f"   {status_emoji} {self._translate_status(tracking['status'])}\n"
            
            # Ubicación o fecha de entrega
            if tracking["status"] == "delivered":
                response += f"   ✅ Entregado: {tracking.get('delivery_date', 'Fecha no disponible')}\n"
            else:
                response += f"   📍 {tracking.get('location', 'En tránsito')}\n"
                if tracking.get("estimated_delivery"):
                    response += f"   📅 Entrega estimada: {tracking['estimated_delivery']}\n"
            
            response += f"   🚚 {tracking['carrier'].upper()} - `{tracking['tracking_number']}`\n"
            response += "\n"
        
        response += "Selecciona el número del pedido para ver más detalles."
        
        return {
            "text": response,
            "data": {
                "tracking_list": tracking_list,
                "total_orders": len(tracking_list)
            },
            "tools_used": ["OrderLookupTool", "ShippingTrackingTool", "DeliveryEstimationTool"]
        }
    
    def _handle_no_order_info(self) -> Dict[str, Any]:
        """Maneja cuando no se proporciona información de orden"""
        response = "🔍 Para rastrear tu pedido, necesito:\n\n"
        response += "• **Número de orden** (ej: #123456)\n"
        response += "• **Número de rastreo** (ej: FX12345678)\n\n"
        response += "También puedo mostrar tus pedidos recientes si lo prefieres."
        
        return {
            "text": response,
            "data": {},
            "tools_used": []
        }
    
    def _handle_no_orders_found(self, order_numbers: List[str]) -> Dict[str, Any]:
        """Maneja cuando no se encuentran órdenes"""
        if order_numbers:
            response = f"❌ No encontré pedidos con los números: {', '.join(order_numbers)}\n\n"
            response += "Por favor verifica:\n"
            response += "• Que el número sea correcto\n"
            response += "• Que el pedido esté asociado a tu cuenta\n"
        else:
            response = "📭 No encontré pedidos recientes en tu cuenta.\n\n"
            response += "Si realizaste una compra recientemente, el pedido puede tardar unos minutos en aparecer."
        
        response += "\n¿Necesitas ayuda con algo más?"
        
        return {
            "text": response,
            "data": {
                "searched_numbers": order_numbers
            },
            "tools_used": ["OrderLookupTool"]
        }
    
    def _get_status_emoji(self, status: str) -> str:
        """Retorna emoji apropiado para el estado"""
        status_emojis = {
            "pending": "⏳",
            "processing": "📋",
            "shipped": "🚚",
            "in_transit": "✈️",
            "out_for_delivery": "🚛",
            "delivered": "✅",
            "failed": "❌",
            "returned": "↩️",
            "cancelled": "🚫"
        }
        return status_emojis.get(status.lower(), "📦")
    
    def _translate_status(self, status: str) -> str:
        """Traduce estado al español"""
        translations = {
            "pending": "Pendiente",
            "processing": "Procesando",
            "shipped": "Enviado",
            "in_transit": "En tránsito",
            "out_for_delivery": "En reparto",
            "delivered": "Entregado",
            "failed": "Fallo en entrega",
            "returned": "Devuelto",
            "cancelled": "Cancelado"
        }
        return translations.get(status.lower(), status)


# Herramientas del TrackingAgent
class OrderLookupTool:
    """Busca órdenes en la base de datos"""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    async def get_order_by_number(
        self, 
        order_number: str, 
        customer_id: Optional[str] = None
    ) -> Optional[Dict]:
        """Busca una orden por número"""
        # En producción esto consultaría la BD
        # Simulación
        if order_number.startswith("1234"):
            return {
                "order_number": order_number,
                "customer_id": customer_id,
                "status": "shipped",
                "created_at": datetime.now() - timedelta(days=2),
                "tracking_number": f"FX{order_number}",
                "carrier": "fedex",
                "shipping_method": "express",
                "items": [
                    {"name": "Laptop Gaming ASUS", "quantity": 1, "price": 45000}
                ]
            }
        return None
    
    async def get_recent_orders(
        self, 
        customer_id: str, 
        limit: int = 5
    ) -> List[Dict]:
        """Obtiene órdenes recientes de un cliente"""
        # En producción esto consultaría la BD
        # Simulación
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
                "items": [
                    {"name": "Mouse Logitech G502", "quantity": 1, "price": 2500}
                ]
            },
            {
                "order_number": "123457",
                "customer_id": customer_id,
                "status": "in_transit",
                "created_at": datetime.now() - timedelta(days=1),
                "tracking_number": "UPS987654321",
                "carrier": "ups",
                "items": [
                    {"name": "Teclado Mecánico", "quantity": 1, "price": 5000}
                ]
            }
        ]


class ShippingTrackingTool:
    """Obtiene información de tracking de transportistas"""
    
    def __init__(self, shipping_apis):
        self.shipping_apis = shipping_apis
    
    async def get_tracking_info(
        self, 
        tracking_number: str, 
        carrier: str
    ) -> Optional[Dict]:
        """Obtiene información de tracking del transportista"""
        # En producción esto llamaría a las APIs reales
        # Simulación
        
        if carrier.lower() == "fedex":
            return {
                "status": "in_transit",
                "location": "Centro de distribución - Buenos Aires",
                "last_update": datetime.now() - timedelta(hours=3),
                "events": [
                    {
                        "date": (datetime.now() - timedelta(days=2)).strftime("%d/%m %H:%M"),
                        "description": "Paquete recibido",
                        "location": "Centro de envíos"
                    },
                    {
                        "date": (datetime.now() - timedelta(days=1)).strftime("%d/%m %H:%M"),
                        "description": "En tránsito",
                        "location": "Hub Ezeiza"
                    },
                    {
                        "date": (datetime.now() - timedelta(hours=3)).strftime("%d/%m %H:%M"),
                        "description": "Llegó a centro de distribución",
                        "location": "Buenos Aires"
                    }
                ],
                "tracking_url": f"https://fedex.com/track/{tracking_number}"
            }
        
        elif carrier.lower() == "ups":
            return {
                "status": "out_for_delivery",
                "location": "En reparto - CABA",
                "last_update": datetime.now() - timedelta(hours=1),
                "events": [
                    {
                        "date": datetime.now().strftime("%d/%m %H:%M"),
                        "description": "Salió a reparto",
                        "location": "CABA"
                    }
                ],
                "tracking_url": f"https://ups.com/track/{tracking_number}"
            }
        
        return None


class DeliveryEstimationTool:
    """Estima fechas de entrega"""
    
    async def estimate_delivery(
        self, 
        tracking_info: Dict, 
        shipping_method: Optional[str] = None
    ) -> str:
        """Estima la fecha de entrega basándose en el estado actual"""
        status = tracking_info.get("status", "unknown")
        
        # Estimaciones según estado
        if status == "shipped":
            days_to_add = 3 if shipping_method == "express" else 5
        elif status == "in_transit":
            days_to_add = 2 if shipping_method == "express" else 3
        elif status == "out_for_delivery":
            days_to_add = 0  # Hoy
        else:
            days_to_add = 7  # Por defecto
        
        estimated_date = datetime.now() + timedelta(days=days_to_add)
        
        # Formato amigable
        if days_to_add == 0:
            return "Hoy"
        elif days_to_add == 1:
            return "Mañana"
        else:
            return estimated_date.strftime("%A %d de %B")


class TrackingNotificationTool:
    """Gestiona notificaciones de tracking"""
    
    async def setup_notifications(
        self, 
        order_number: str, 
        customer_id: str,
        notification_preferences: Dict
    ) -> bool:
        """Configura notificaciones para un pedido"""
        # En producción esto configuraría webhooks o suscripciones
        return True
    
    async def send_status_update(
        self,
        order_number: str,
        new_status: str,
        customer_contact: str
    ) -> bool:
        """Envía actualización de estado"""
        # En producción esto enviaría SMS/Email/WhatsApp
        return True