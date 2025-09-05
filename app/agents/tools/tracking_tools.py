"""
Tools especializadas para el Tracking Agent
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class OrderTrackingInput(BaseModel):
    """Input para rastreo de orden"""
    order_id: str = Field(description="ID de la orden a rastrear")


class DeliveryInfoInput(BaseModel):
    """Input para información de entrega"""
    order_id: str = Field(description="ID de la orden")
    detailed: bool = Field(default=False, description="Incluir información detallada")


class AddressUpdateInput(BaseModel):
    """Input para actualizar dirección de envío"""
    order_id: str = Field(description="ID de la orden")
    new_address: str = Field(description="Nueva dirección de envío")
    city: str = Field(description="Ciudad")
    postal_code: str = Field(description="Código postal")
    phone: Optional[str] = Field(default=None, description="Teléfono de contacto")


# Base de datos simulada de órdenes
ORDERS_DB = {
    "ORD-2024-001": {
        "order_id": "ORD-2024-001",
        "user_id": "user123",
        "status": "delivered",
        "tracking_number": "TRK-001-2024",
        "carrier": "Express Delivery",
        "items": [
            {"product_id": "laptop_001", "name": "Laptop Gaming ASUS ROG", "quantity": 1}
        ],
        "order_date": "2024-11-15",
        "shipped_date": "2024-11-16",
        "estimated_delivery": "2024-11-20",
        "actual_delivery": "2024-11-19",
        "shipping_address": {
            "street": "Calle Principal 123",
            "city": "Buenos Aires",
            "postal_code": "1000",
            "country": "Argentina"
        },
        "tracking_events": [
            {
                "date": "2024-11-15 14:30",
                "status": "order_placed",
                "location": "Centro de Procesamiento",
                "description": "Orden recibida y en preparación"
            },
            {
                "date": "2024-11-16 09:15",
                "status": "shipped",
                "location": "Centro de Distribución Buenos Aires",
                "description": "Paquete enviado desde almacén"
            },
            {
                "date": "2024-11-17 12:00",
                "status": "in_transit",
                "location": "Hub de Transporte Córdoba",
                "description": "En tránsito hacia destino"
            },
            {
                "date": "2024-11-18 16:45",
                "status": "out_for_delivery",
                "location": "Centro de Distribución Local",
                "description": "Salió para entrega"
            },
            {
                "date": "2024-11-19 11:30",
                "status": "delivered",
                "location": "Calle Principal 123",
                "description": "Entregado exitosamente - Recibido por: María García"
            }
        ]
    },
    "ORD-2024-002": {
        "order_id": "ORD-2024-002",
        "user_id": "user456",
        "status": "in_transit",
        "tracking_number": "TRK-002-2024",
        "carrier": "Standard Shipping",
        "items": [
            {"product_id": "phone_001", "name": "iPhone 15 Pro", "quantity": 1},
            {"product_id": "phone_acc_001", "name": "Funda Protectora", "quantity": 1}
        ],
        "order_date": "2024-12-01",
        "shipped_date": "2024-12-02",
        "estimated_delivery": "2024-12-07",
        "actual_delivery": None,
        "shipping_address": {
            "street": "Av. Libertador 456",
            "city": "Rosario",
            "postal_code": "2000",
            "country": "Argentina"
        },
        "tracking_events": [
            {
                "date": "2024-12-01 10:20",
                "status": "order_placed",
                "location": "Centro de Procesamiento",
                "description": "Orden confirmada y en preparación"
            },
            {
                "date": "2024-12-02 14:30",
                "status": "shipped",
                "location": "Centro de Distribución Buenos Aires",
                "description": "Paquete despachado"
            },
            {
                "date": "2024-12-04 08:15",
                "status": "in_transit",
                "location": "Hub Regional Santa Fe",
                "description": "En tránsito hacia Rosario"
            }
        ]
    },
    "ORD-2024-003": {
        "order_id": "ORD-2024-003", 
        "user_id": "user789",
        "status": "processing",
        "tracking_number": None,
        "carrier": "Express Delivery",
        "items": [
            {"product_id": "laptop_003", "name": "Laptop HP Pavilion", "quantity": 1}
        ],
        "order_date": "2024-12-05",
        "shipped_date": None,
        "estimated_delivery": "2024-12-10",
        "actual_delivery": None,
        "shipping_address": {
            "street": "San Martín 789",
            "city": "Mendoza",
            "postal_code": "5500",
            "country": "Argentina"
        },
        "tracking_events": [
            {
                "date": "2024-12-05 16:45",
                "status": "order_placed",
                "location": "Centro de Procesamiento",
                "description": "Orden recibida, verificando stock"
            },
            {
                "date": "2024-12-06 09:00",
                "status": "processing",
                "location": "Almacén Principal", 
                "description": "Preparando productos para envío"
            }
        ]
    }
}

# Estados y descripciones
STATUS_DESCRIPTIONS = {
    "order_placed": "Orden Recibida",
    "processing": "Procesando",
    "shipped": "Enviado",
    "in_transit": "En Tránsito",
    "out_for_delivery": "Salió para Entrega",
    "delivered": "Entregado",
    "returned": "Devuelto",
    "cancelled": "Cancelado"
}

# Transportistas y sus URLs de seguimiento
CARRIERS = {
    "Express Delivery": {
        "name": "Express Delivery",
        "tracking_url": "https://express-delivery.com/tracking/",
        "phone": "0800-EXPRESS",
        "email": "soporte@express-delivery.com"
    },
    "Standard Shipping": {
        "name": "Standard Shipping", 
        "tracking_url": "https://standard-shipping.com/track/",
        "phone": "0800-STANDARD",
        "email": "ayuda@standard-shipping.com"
    }
}


@tool(args_schema=OrderTrackingInput)
async def track_order_tool(order_id: str) -> Dict[str, Any]:
    """
    Rastrea el estado actual de una orden proporcionando información completa de seguimiento.
    
    Útil para mantener informado al cliente sobre el progreso de su pedido.
    """
    logger.info(f"Tracking order: {order_id}")
    
    # Simular latencia de consulta
    await asyncio.sleep(0.12)
    
    # Buscar orden
    order = ORDERS_DB.get(order_id)
    
    if not order:
        return {
            "success": False,
            "error": f"Orden {order_id} no encontrada",
            "order_id": order_id,
            "suggestions": [
                "Verifica que el número de orden sea correcto",
                "Los números de orden tienen formato ORD-YYYY-XXX",
                "Contacta soporte si el problema persiste"
            ]
        }
    
    # Obtener último evento de seguimiento
    latest_event = order["tracking_events"][-1] if order["tracking_events"] else None
    
    # Calcular progreso
    status_order = ["order_placed", "processing", "shipped", "in_transit", "out_for_delivery", "delivered"]
    current_status_index = status_order.index(order["status"]) if order["status"] in status_order else 0
    progress_percentage = ((current_status_index + 1) / len(status_order)) * 100
    
    # Información del transportista
    carrier_info = CARRIERS.get(order["carrier"], {})
    
    # Calcular tiempo estimado restante
    estimated_info = None
    if order["status"] not in ["delivered", "cancelled", "returned"]:
        if order["estimated_delivery"]:
            est_delivery = datetime.strptime(order["estimated_delivery"], "%Y-%m-%d")
            today = datetime.now()
            days_remaining = (est_delivery - today).days
            
            if days_remaining >= 0:
                estimated_info = f"{days_remaining} días restantes para entrega"
            else:
                estimated_info = f"Entrega retrasada por {abs(days_remaining)} días"
    
    # Preparar siguiente paso esperado
    next_step = None
    if order["status"] == "processing":
        next_step = "Su orden será enviada pronto"
    elif order["status"] == "shipped":
        next_step = "Su paquete está en camino al centro de distribución"
    elif order["status"] == "in_transit":
        next_step = "Su paquete llegará al centro de distribución local"
    elif order["status"] == "out_for_delivery":
        next_step = "Su paquete será entregado hoy"
    
    return {
        "success": True,
        "order": {
            "order_id": order["order_id"],
            "status": order["status"],
            "status_description": STATUS_DESCRIPTIONS.get(order["status"], order["status"]),
            "tracking_number": order["tracking_number"],
            "carrier": order["carrier"],
            "progress_percentage": round(progress_percentage, 1),
            "estimated_delivery": order["estimated_delivery"],
            "actual_delivery": order["actual_delivery"]
        },
        "latest_update": {
            "date": latest_event["date"] if latest_event else None,
            "location": latest_event["location"] if latest_event else None,
            "description": latest_event["description"] if latest_event else None
        },
        "estimated_info": estimated_info,
        "next_step": next_step,
        "carrier_info": carrier_info,
        "items": order["items"],
        "shipping_address": order["shipping_address"]
    }


@tool(args_schema=DeliveryInfoInput)
async def get_delivery_info_tool(order_id: str, detailed: bool = False) -> Dict[str, Any]:
    """
    Obtiene información detallada sobre la entrega de una orden, incluyendo horarios y opciones.
    
    Útil para coordinar la entrega con el cliente y proporcionar opciones flexibles.
    """
    logger.info(f"Getting delivery info for order {order_id}, detailed: {detailed}")
    
    # Simular latencia
    await asyncio.sleep(0.08)
    
    order = ORDERS_DB.get(order_id)
    
    if not order:
        return {
            "success": False,
            "error": f"Orden {order_id} no encontrada"
        }
    
    # Información básica de entrega
    delivery_info = {
        "order_id": order_id,
        "status": order["status"],
        "estimated_delivery": order["estimated_delivery"],
        "actual_delivery": order["actual_delivery"],
        "shipping_address": order["shipping_address"]
    }
    
    # Agregar información detallada si se solicita
    if detailed:
        # Ventanas de entrega disponibles
        delivery_windows = [
            {"time": "09:00-12:00", "description": "Mañana", "available": True},
            {"time": "12:00-15:00", "description": "Medio día", "available": True},
            {"time": "15:00-18:00", "description": "Tarde", "available": False},
            {"time": "18:00-21:00", "description": "Noche", "available": True}
        ]
        
        # Opciones de entrega especiales
        delivery_options = [
            {
                "option": "Entrega en punto de recogida",
                "description": "Recoge en tienda cercana",
                "cost": 0,
                "available": order["status"] in ["shipped", "in_transit"]
            },
            {
                "option": "Entrega programada",
                "description": "Elige fecha y hora específica",
                "cost": 5.99,
                "available": order["status"] in ["shipped", "in_transit"]
            },
            {
                "option": "Entrega sin contacto",
                "description": "Dejar en la puerta",
                "cost": 0,
                "available": True
            }
        ]
        
        # Instrucciones especiales actuales
        delivery_instructions = [
            "Tocar timbre antes de dejar el paquete",
            "No dejar sin supervisión",
            "Contactar por teléfono si no hay respuesta",
            "Horario preferido: 10:00-16:00"
        ]
        
        delivery_info.update({
            "delivery_windows": delivery_windows,
            "delivery_options": delivery_options,
            "current_instructions": delivery_instructions,
            "carrier_contact": CARRIERS.get(order["carrier"], {}),
            "tracking_events": order["tracking_events"]
        })
    
    # Información contextual basada en estado
    status_specific_info = {}
    
    if order["status"] == "delivered":
        status_specific_info = {
            "delivery_confirmation": "Paquete entregado exitosamente",
            "received_by": "María García",  # Simulado
            "delivery_photo": "https://example.com/delivery-photo.jpg",
            "rating_request": "¿Cómo fue tu experiencia de entrega?"
        }
    elif order["status"] == "out_for_delivery":
        status_specific_info = {
            "estimated_window": "Entre 10:00 y 14:00",
            "driver_contact": "+54 11 1234-5678",
            "live_tracking": "https://track.example.com/live/" + order.get("tracking_number", ""),
            "preparation_tips": [
                "Asegúrate de estar disponible",
                "Ten tu documento de identidad listo",
                "Prepara espacio para recibir el paquete"
            ]
        }
    elif order["status"] in ["shipped", "in_transit"]:
        status_specific_info = {
            "can_modify": True,
            "modification_deadline": "24 horas antes de la entrega",
            "available_changes": [
                "Cambiar dirección de entrega",
                "Programar fecha de entrega",
                "Agregar instrucciones especiales"
            ]
        }
    
    delivery_info["status_info"] = status_specific_info
    
    return {
        "success": True,
        "delivery_info": delivery_info,
        "notifications": [
            "Recibirás SMS cuando el paquete salga para entrega",
            "Recibirás confirmación cuando sea entregado",
            "Puedes modificar preferencias hasta 24h antes"
        ]
    }


@tool(args_schema=AddressUpdateInput)
async def update_shipping_address_tool(
    order_id: str,
    new_address: str,
    city: str,
    postal_code: str,
    phone: Optional[str] = None
) -> Dict[str, Any]:
    """
    Actualiza la dirección de envío de una orden si aún es posible modificarla.
    
    Útil cuando el cliente necesita cambiar el destino de entrega antes del envío.
    """
    logger.info(f"Updating shipping address for order {order_id}")
    
    # Simular latencia de procesamiento
    await asyncio.sleep(0.15)
    
    order = ORDERS_DB.get(order_id)
    
    if not order:
        return {
            "success": False,
            "error": f"Orden {order_id} no encontrada"
        }
    
    # Verificar si se puede modificar la dirección
    modifiable_statuses = ["order_placed", "processing", "shipped"]
    
    if order["status"] not in modifiable_statuses:
        return {
            "success": False,
            "error": f"No se puede modificar la dirección. Estado actual: {order['status']}",
            "current_status": order["status"],
            "reason": "La orden ya está en tránsito o entregada",
            "alternatives": [
                "Contacta al transportista directamente",
                "Considera la opción de reenvío",
                "Solicita entrega en punto de recogida"
            ]
        }
    
    # Validar nueva dirección
    if len(new_address.strip()) < 10:
        return {
            "success": False,
            "error": "La dirección debe tener al menos 10 caracteres",
            "new_address": new_address
        }
    
    if len(postal_code.strip()) < 4:
        return {
            "success": False,
            "error": "Código postal inválido",
            "postal_code": postal_code
        }
    
    # Calcular costo adicional por cambio de dirección
    additional_cost = 0
    cost_reason = None
    
    if order["status"] == "shipped":
        additional_cost = 12.99
        cost_reason = "Costo por redirección en tránsito"
    elif city.lower() != order["shipping_address"]["city"].lower():
        additional_cost = 8.50
        cost_reason = "Costo por cambio de ciudad"
    
    # Simular actualización exitosa
    old_address = order["shipping_address"].copy()
    
    new_address_data = {
        "street": new_address,
        "city": city,
        "postal_code": postal_code,
        "country": order["shipping_address"]["country"]  # Mantener país
    }
    
    # Actualizar en base de datos (simulado)
    # order["shipping_address"] = new_address_data
    
    # Recalcular fecha de entrega si es necesario
    delivery_adjustment = None
    if additional_cost > 0:
        # Simular recálculo de fecha de entrega
        if order["estimated_delivery"]:
            est_date = datetime.strptime(order["estimated_delivery"], "%Y-%m-%d")
            new_est_date = est_date + timedelta(days=1)
            delivery_adjustment = {
                "old_date": order["estimated_delivery"],
                "new_date": new_est_date.strftime("%Y-%m-%d"),
                "reason": "Ajuste por cambio de dirección"
            }
    
    return {
        "success": True,
        "order_id": order_id,
        "address_update": {
            "old_address": old_address,
            "new_address": new_address_data,
            "phone": phone,
            "updated_at": datetime.now().isoformat()
        },
        "additional_cost": additional_cost,
        "cost_reason": cost_reason,
        "delivery_adjustment": delivery_adjustment,
        "confirmation": {
            "update_id": f"UPD-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "status": "Dirección actualizada exitosamente",
            "notifications": [
                "Recibirás confirmación por WhatsApp",
                "La nueva dirección aparecerá en el tracking",
                "Se enviará notificación al transportista"
            ]
        },
        "next_steps": [
            "Verifica la nueva dirección en el tracking",
            "Confirma disponibilidad en la nueva dirección",
            "Mantén el teléfono de contacto actualizado"
        ]
    }