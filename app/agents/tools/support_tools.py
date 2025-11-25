"""
Tools especializadas para el Support Agent
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FAQSearchInput(BaseModel):
    """Input para búsqueda en FAQ"""

    query: str = Field(description="Consulta o problema del usuario")
    category: Optional[str] = Field(default=None, description="Categoría específica")


class TicketInput(BaseModel):
    """Input para crear ticket de soporte"""

    user_id: str = Field(description="ID del usuario")
    subject: str = Field(description="Asunto del problema")
    description: str = Field(description="Descripción detallada del problema")
    priority: str = Field(default="medium", description="Prioridad: low, medium, high")
    category: str = Field(default="general", description="Categoría del problema")


class WarrantyInput(BaseModel):
    """Input para información de garantía"""

    product_id: str = Field(description="ID del producto")
    purchase_date: Optional[str] = Field(default=None, description="Fecha de compra (YYYY-MM-DD)")


# Base de datos simulada de FAQ
FAQ_DB = [
    {
        "id": "faq_001",
        "category": "envios",
        "question": "¿Cuánto tiempo tarda el envío?",
        "answer": (
            "Los envíos estándar tardan 5-7 días hábiles. "
            "El envío express tarda 2-3 días y el overnight 1 día hábil."
        ),
        "keywords": ["envío", "tiempo", "entrega", "días", "estándar", "express"],
        "popularity": 95,
    },
    {
        "id": "faq_002",
        "category": "devoluciones",
        "question": "¿Cómo puedo devolver un producto?",
        "answer": (
            "Tienes 30 días para devolver productos. "
            "Contacta soporte para generar una etiqueta de devolución gratuita."
        ),
        "keywords": ["devolver", "devolución", "retorno", "30 días", "etiqueta"],
        "popularity": 88,
    },
    {
        "id": "faq_003",
        "category": "pagos",
        "question": "¿Qué métodos de pago aceptan?",
        "answer": (
            "Aceptamos tarjetas de crédito/débito, PayPal y transferencia bancaria. "
            "Puedes pagar en cuotas con tarjeta de crédito."
        ),
        "keywords": ["pago", "tarjeta", "crédito", "débito", "paypal", "transferencia", "cuotas"],
        "popularity": 82,
    },
    {
        "id": "faq_004",
        "category": "garantia",
        "question": "¿Qué cubre la garantía?",
        "answer": "Ofrecemos 1 año de garantía contra defectos de fábrica. Cubre reparación o reemplazo gratuito.",
        "keywords": ["garantía", "defectos", "fábrica", "1 año", "reparación", "reemplazo"],
        "popularity": 76,
    },
    {
        "id": "faq_005",
        "category": "cuenta",
        "question": "¿Cómo cambio mi contraseña?",
        "answer": (
            "Ve a 'Mi Cuenta' > 'Configuración' > 'Cambiar Contraseña'. "
            "También puedes usar 'Olvidé mi contraseña'."
        ),
        "keywords": ["contraseña", "cambiar", "olvidé", "cuenta", "configuración"],
        "popularity": 71,
    },
    {
        "id": "faq_006",
        "category": "stock",
        "question": "¿Cuándo estará disponible un producto agotado?",
        "answer": (
            "Recibimos stock nuevo semanalmente. "
            "Puedes suscribirte a notificaciones para ser informado cuando llegue."
        ),
        "keywords": ["stock", "agotado", "disponible", "semanal", "notificaciones"],
        "popularity": 68,
    },
    {
        "id": "faq_007",
        "category": "envios",
        "question": "¿Hacen envíos internacionales?",
        "answer": (
            "Sí, enviamos a varios países. Los costos y tiempos varían por destino. "
            "Consulta al momento de la compra."
        ),
        "keywords": ["internacional", "países", "costos", "destino", "compra"],
        "popularity": 65,
    },
    {
        "id": "faq_008",
        "category": "promociones",
        "question": "¿Cómo uso un código de descuento?",
        "answer": (
            "Ingresa el código en 'Código de descuento' durante el checkout. "
            "El descuento se aplicará automáticamente."
        ),
        "keywords": ["código", "descuento", "checkout", "aplicar", "automático"],
        "popularity": 63,
    },
]

# Productos con información de garantía
WARRANTY_INFO = {
    "laptop_001": {
        "warranty_period": 365,  # días
        "warranty_type": "Garantía del fabricante",
        "covered_issues": ["Defectos de fábrica", "Fallas de hardware", "Problemas de software preinstalado"],
        "not_covered": ["Daño físico", "Derrame de líquidos", "Modificaciones no autorizadas"],
        "support_contact": "soporte@asus.com",
        "repair_centers": ["Centro Autorizado ASUS - Ciudad", "Servicio Técnico Express"],
    },
    "laptop_002": {
        "warranty_period": 365,
        "warranty_type": "AppleCare Limited Warranty",
        "covered_issues": ["Defectos de materiales", "Fallas de funcionamiento", "Batería (menos de 80% capacidad)"],
        "not_covered": ["Daño accidental", "Desgaste normal", "Daño por agua"],
        "support_contact": "800-APL-CARE",
        "repair_centers": ["Apple Store", "Proveedor de Servicios Autorizado Apple"],
    },
    "phone_001": {
        "warranty_period": 365,
        "warranty_type": "Garantía limitada de Apple",
        "covered_issues": ["Defectos de fábrica", "Fallas de hardware", "Problemas de software iOS"],
        "not_covered": ["Pantalla rota", "Daño por agua", "Pérdida o robo"],
        "support_contact": "800-APL-CARE",
        "repair_centers": ["Apple Store", "Centro de Reparación Autorizado"],
    },
}


@tool(args_schema=FAQSearchInput)
async def search_faq_tool(query: str, category: Optional[str] = None) -> Dict[str, Any]:
    """
    Busca en la base de conocimientos de preguntas frecuentes (FAQ) para encontrar respuestas relevantes.

    Útil para resolver dudas comunes del cliente de forma rápida y precisa.
    """
    logger.info(f"Searching FAQ: query='{query}', category={category}")

    # Simular latencia de búsqueda
    await asyncio.sleep(0.08)

    query_lower = query.lower()
    results = []

    for faq in FAQ_DB:
        # Filtrar por categoría si se especifica
        if category and faq["category"] != category.lower():
            continue

        # Calcular relevancia basada en palabras clave
        relevance_score = 0
        query_words = query_lower.split()

        for word in query_words:
            if word in faq["question"].lower():
                relevance_score += 3  # Coincidencia en pregunta vale más
            if word in faq["answer"].lower():
                relevance_score += 2  # Coincidencia en respuesta
            for keyword in faq["keywords"]:
                if word in keyword.lower() or keyword.lower() in word:
                    relevance_score += 1

        # Agregar bonus por popularidad
        popularity_value = float(faq.get("popularity", 0)) if isinstance(faq.get("popularity"), (int, float)) else 0
        popularity_bonus = popularity_value / 100
        final_score = relevance_score + popularity_bonus

        if final_score > 0.5:  # Umbral mínimo de relevancia
            results.append(
                {
                    "id": faq["id"],
                    "question": faq["question"],
                    "answer": faq["answer"],
                    "category": faq["category"],
                    "relevance_score": round(final_score, 2),
                    "popularity": faq["popularity"],
                }
            )

    # Ordenar por relevancia
    results.sort(key=lambda x: x["relevance_score"], reverse=True)

    # Limitar a top 5 resultados
    results = results[:5]

    return {
        "success": True,
        "results": results,
        "total_found": len(results),
        "query": query,
        "category_filter": category,
        "suggestions": (
            ["¿Es sobre envíos o devoluciones?", "¿Necesitas ayuda con tu cuenta?", "¿Tienes problemas con un pedido?"]
            if not results
            else None
        ),
    }


@tool(args_schema=TicketInput)
async def create_ticket_tool(
    user_id: str, subject: str, description: str, priority: str = "medium", category: str = "general"
) -> Dict[str, Any]:
    """
    Crea un ticket de soporte para problemas que requieren atención personalizada.

    Útil cuando las FAQ no resuelven el problema del cliente o necesita asistencia directa.
    """
    logger.info(f"Creating support ticket for user {user_id}, priority: {priority}")

    # Simular latencia de creación
    await asyncio.sleep(0.15)

    # Validar prioridad
    valid_priorities = ["low", "medium", "high"]
    if priority not in valid_priorities:
        return {"success": False, "error": f"Prioridad '{priority}' no válida", "valid_priorities": valid_priorities}

    # Generar ID de ticket
    ticket_id = f"TKT-{datetime.now().strftime('%Y%m%d')}-{hash(user_id + subject) % 10000:04d}"

    # Estimar tiempo de respuesta basado en prioridad
    response_times = {"high": "2-4 horas", "medium": "8-12 horas", "low": "24-48 horas"}

    # Asignar departamento basado en categoría
    departments = {
        "general": "Soporte General",
        "technical": "Soporte Técnico",
        "billing": "Facturación",
        "shipping": "Envíos y Logística",
        "returns": "Devoluciones",
        "account": "Gestión de Cuenta",
    }

    assigned_department = departments.get(category, "Soporte General")

    # Crear ticket
    ticket = {
        "ticket_id": ticket_id,
        "user_id": user_id,
        "subject": subject,
        "description": description,
        "priority": priority,
        "category": category,
        "status": "open",
        "assigned_department": assigned_department,
        "created_at": datetime.now().isoformat(),
        "estimated_response": response_times[priority],
        "updates": [
            {"timestamp": datetime.now().isoformat(), "status": "created", "note": "Ticket creado exitosamente"}
        ],
    }

    return {
        "success": True,
        "ticket": ticket,
        "next_steps": [
            f"Tu ticket {ticket_id} ha sido creado",
            f"Departamento asignado: {assigned_department}",
            f"Tiempo estimado de respuesta: {response_times[priority]}",
            "Recibirás actualizaciones por WhatsApp y email",
        ],
        "contact_options": [
            "WhatsApp: Responderemos por este mismo chat",
            "Email: soporte@aynux.com",
            "Teléfono: 1-800-SUPPORT (solo prioridad alta)",
        ],
    }


@tool(args_schema=WarrantyInput)
async def get_warranty_info_tool(product_id: str, purchase_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Obtiene información detallada sobre la garantía de un producto específico.

    Útil para informar al cliente sobre cobertura, términos y proceso de reclamos de garantía.
    """
    logger.info(f"Getting warranty info for product {product_id}, purchase_date: {purchase_date}")

    # Simular latencia
    await asyncio.sleep(0.1)

    # Buscar información de garantía
    warranty = WARRANTY_INFO.get(product_id)

    if not warranty:
        return {
            "success": False,
            "error": f"Información de garantía no encontrada para el producto {product_id}",
            "product_id": product_id,
            "support_contact": "soporte@aynux.com",
        }

    warranty_info = warranty.copy()

    # Calcular estado de garantía si se proporciona fecha de compra
    warranty_status = None
    days_remaining = None

    if purchase_date:
        try:
            purchase_dt = datetime.strptime(purchase_date, "%Y-%m-%d")
            warranty_end_date = purchase_dt + timedelta(days=warranty["warranty_period"])
            today = datetime.now()

            if today <= warranty_end_date:
                days_remaining = (warranty_end_date - today).days
                warranty_status = "active"
            else:
                days_expired = (today - warranty_end_date).days
                warranty_status = "expired"
                warranty_info["days_expired"] = days_expired

            warranty_info.update(
                {
                    "purchase_date": purchase_date,
                    "warranty_end_date": warranty_end_date.strftime("%Y-%m-%d"),
                    "warranty_status": warranty_status,
                    "days_remaining": days_remaining,
                }
            )

        except ValueError:
            return {
                "success": False,
                "error": "Formato de fecha inválido. Use YYYY-MM-DD",
                "purchase_date": purchase_date,
            }

    # Generar pasos para reclamar garantía
    claim_steps = [
        "1. Contacta al soporte técnico del fabricante",
        "2. Proporciona el número de serie del producto",
        "3. Describe detalladamente el problema",
        "4. Envía fotos o videos si es necesario",
        "5. Sigue las instrucciones del técnico",
    ]

    # Información adicional basada en estado
    additional_info = []
    if warranty_status == "active":
        additional_info = [
            f"✅ Tu garantía está activa por {days_remaining} días más",
            "Cualquier defecto de fábrica está cubierto",
            "Reparación o reemplazo sin costo adicional",
        ]
    elif warranty_status == "expired":
        additional_info = [
            "❌ Tu garantía ha expirado",
            "Puedes solicitar reparación con costo",
            "Consulta opciones de garantía extendida",
        ]
    else:
        additional_info = [
            "Proporciona la fecha de compra para verificar estado",
            "Conserva tu factura como comprobante",
            "La garantía inicia desde la fecha de compra",
        ]

    return {
        "success": True,
        "product_id": product_id,
        "warranty_info": warranty_info,
        "claim_process": claim_steps,
        "additional_info": additional_info,
        "emergency_contact": "1-800-URGENTE (para problemas críticos de seguridad)",
        "warranty_extensions": [
            "Garantía Extendida Premium: +2 años adicionales",
            "Protección contra Accidentes: Cobertura de daños",
            "Soporte Técnico Prioritario: Respuesta en 1 hora",
        ],
    }
