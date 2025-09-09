"""
Agente especializado en promociones y ofertas
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..utils.tracing import trace_async_method
from .base_agent import BaseAgent


class PromotionsAgent(BaseAgent):
    """Agente especializado en promociones, ofertas y descuentos"""

    def __init__(self, ollama=None, chroma=None, config: Optional[Dict[str, Any]] = None):
        super().__init__("promotions_agent", config or {}, ollama=ollama, chroma=chroma)

        # Inicializar herramientas simuladas
        self.active_tool = ActivePromotionsTool(None)
        self.personalized_tool = PersonalizedOffersTool(None)
        self.eligibility_tool = PromotionEligibilityTool()
        self.coupon_tool = CouponGeneratorTool()

    @trace_async_method(
        name="promotions_agent_process",
        run_type="chain",
        metadata={"agent_type": "promotions", "personalization": "enabled"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Procesa consultas sobre promociones"""
        user_message = message
        customer = state_dict.get("customer", {})
        customer_tier = customer.get("tier", "basic") if customer else "basic"

        # Obtener promociones activas (simulado - en producción sería con caché)
        active_promos = self.active_tool.get_active_promotions_sync()

        # Filtrar por elegibilidad del cliente
        eligible_promos = self._filter_eligible_promotions_sync(active_promos, customer_tier, customer)

        # Generar ofertas personalizadas
        personalized_offers = self.personalized_tool.generate_personalized_offers_sync(
            customer, eligible_promos, user_message
        )

        # Determinar tipo de respuesta
        response_type = self._determine_response_type(user_message)

        if response_type == "specific_product":
            return self._handle_product_promotions(user_message, eligible_promos, personalized_offers)
        elif response_type == "coupon_request":
            return self._handle_coupon_request(customer, eligible_promos)
        else:
            return self._handle_general_promotions(eligible_promos, personalized_offers, customer_tier)

    def _determine_response_type(self, message: str) -> str:
        """Determina el tipo de consulta sobre promociones"""
        message_lower = message.lower()

        if any(word in message_lower for word in ["cupón", "cupon", "código", "codigo"]):
            return "coupon_request"
        elif any(word in message_lower for word in ["laptop", "computadora", "producto"]):
            return "specific_product"
        else:
            return "general"

    def _handle_general_promotions(
        self, promotions: List[Dict], personalized: List[Dict], customer_tier: str
    ) -> Dict[str, Any]:
        """Maneja consultas generales sobre promociones"""
        response = "🎉 **Promociones Activas**"

        if customer_tier in ["premium", "vip"]:
            response += f" - Exclusivas para clientes {customer_tier} 🌟\n\n"
        else:
            response += "\n\n"

        # Promociones destacadas
        featured_promos = [p for p in promotions if p.get("featured", False)]

        if featured_promos:
            response += "⭐ **DESTACADAS:**\n"
            for promo in featured_promos[:3]:
                response += self._format_promotion(promo)
                response += "\n"

        # Promociones personalizadas
        if personalized:
            response += "\n🎯 **Recomendadas para ti:**\n"
            for offer in personalized[:3]:
                response += self._format_personalized_offer(offer)
                response += "\n"

        # Otras promociones
        other_promos = [p for p in promotions if not p.get("featured", False)][:5]

        if other_promos:
            response += "\n📢 **Más ofertas:**\n"
            for promo in other_promos:
                response += self._format_promotion_brief(promo)
            response += "\n"

        # Información adicional
        response += "\n💡 **Tips:**\n"
        response += "• Las promociones son acumulables con tu descuento de cliente\n"
        response += "• Algunas ofertas requieren código de cupón\n"
        response += "• Los precios mostrados ya incluyen descuentos\n"

        # Call to action
        response += "\n¿Te interesa alguna promoción en particular?"

        return {
            "messages": [{"role": "assistant", "content": response}],
            "current_agent": self.name,
            "agent_history": [self.name],
            "retrieved_data": {
                "promotions": promotions,
                "personalized_offers": personalized,
                "total_promotions": len(promotions),
            },
            "is_complete": True,
        }

    def _handle_product_promotions(
        self, message: str, promotions: List[Dict], personalized: List[Dict]
    ) -> Dict[str, Any]:
        """Maneja consultas sobre promociones de productos específicos"""
        print("Handling product promotions...", personalized)
        # Buscar promociones relacionadas con el producto mencionado
        relevant_promos = []

        for promo in promotions:
            if self._is_promo_relevant(promo, message):
                relevant_promos.append(promo)

        if not relevant_promos:
            response = "🔍 No encontré promociones específicas para ese producto.\n\n"
            response += "Pero tengo estas ofertas generales que podrían interesarte:\n\n"

            # Mostrar promociones generales
            for promo in promotions[:3]:
                response += self._format_promotion_brief(promo)
        else:
            response = f"🎯 Encontré {len(relevant_promos)} promociones relacionadas:\n\n"

            for promo in relevant_promos:
                response += self._format_promotion(promo)
                response += "\n"

        return {
            "messages": [{"role": "assistant", "content": response}],
            "current_agent": self.name,
            "agent_history": [self.name],
            "retrieved_data": {"relevant_promotions": relevant_promos},
            "is_complete": True,
        }

    def _handle_coupon_request(self, customer, promotions: List[Dict]) -> Dict[str, Any]:
        """Maneja solicitudes de cupones"""
        # Filtrar promociones que tienen cupones
        coupon_promos = [p for p in promotions if p.get("requires_coupon", False)]

        if not coupon_promos:
            response = "😔 No hay cupones activos en este momento.\n\n"
            response += "Pero estas promociones están activas automáticamente:\n\n"

            auto_promos = [p for p in promotions if not p.get("requires_coupon", False)][:3]
            for promo in auto_promos:
                response += self._format_promotion_brief(promo)
        else:
            # Generar cupón personalizado si es cliente premium/vip
            if customer and customer.get("tier") in ["premium", "vip"]:
                coupon = self.coupon_tool.generate_personal_coupon_sync(
                    customer.get("customer_id"), customer.get("tier")
                )

                response = f"🎟️ **Tu cupón exclusivo {customer.get('tier')}:**\n\n"
                response += f"📱 Código: **{coupon['code']}**\n"
                response += f"💰 Descuento: {coupon['discount']}% adicional\n"
                response += f"⏰ Válido hasta: {coupon['valid_until']}\n\n"
            else:
                response = "🎟️ **Cupones disponibles:**\n\n"

            # Mostrar cupones públicos
            for promo in coupon_promos[:3]:
                if promo.get("coupon_code"):
                    response += f"**{promo['name']}**\n"
                    response += f"📱 Código: `{promo['coupon_code']}`\n"
                    response += f"💰 Descuento: {promo['discount_text']}\n"
                    response += f"✅ {promo['description']}\n\n"

        response += "\n💡 Aplica el código en el carrito de compras"

        return {
            "messages": [{"role": "assistant", "content": response}],
            "current_agent": self.name,
            "agent_history": [self.name],
            "retrieved_data": {"coupon_promotions": coupon_promos},
            "is_complete": True,
        }

    def _filter_eligible_promotions_sync(self, promotions: List[Dict], customer_tier: str, customer) -> List[Dict]:
        """Filtra promociones según elegibilidad del cliente"""
        eligible = []

        for promo in promotions:
            # Verificar elegibilidad
            is_eligible = self.eligibility_tool.check_eligibility_sync(promo, customer_tier, customer)

            if is_eligible:
                eligible.append(promo)

        return eligible

    def _format_promotion(self, promo: Dict) -> str:
        """Formatea una promoción completa"""
        text = f"🏷️ **{promo['name']}**\n"

        # Descuento
        if promo.get("discount_percentage"):
            text += f"   💰 {promo['discount_percentage']}% de descuento\n"
        elif promo.get("discount_amount"):
            text += f"   💰 ${promo['discount_amount']} de descuento\n"
        elif promo.get("discount_text"):
            text += f"   💰 {promo['discount_text']}\n"

        # Descripción
        text += f"   📝 {promo['description']}\n"

        # Vigencia
        if promo.get("valid_until"):
            text += f"   ⏰ Válido hasta: {promo['valid_until']}\n"

        # Condiciones
        if promo.get("conditions"):
            text += f"   ⚠️ {promo['conditions']}\n"

        # Cupón si requiere
        if promo.get("requires_coupon") and promo.get("coupon_code"):
            text += f"   🎟️ Usa el código: `{promo['coupon_code']}`\n"

        return text

    def _format_promotion_brief(self, promo: Dict) -> str:
        """Formatea una promoción de forma breve"""
        emoji = "🔥" if promo.get("featured") else "•"
        text = f"{emoji} **{promo['name']}** - {promo.get('discount_text', promo['description'])}\n"
        return text

    def _format_personalized_offer(self, offer: Dict) -> str:
        """Formatea una oferta personalizada"""
        text = f"🎯 **{offer['title']}**\n"
        text += f"   {offer['description']}\n"
        text += f"   💰 Tu precio especial: ${offer['special_price']:,.2f}\n"

        if offer.get("savings"):
            text += f"   💸 Ahorras: ${offer['savings']:,.2f}\n"

        return text

    def _is_promo_relevant(self, promo: Dict, message: str) -> bool:
        """Verifica si una promoción es relevante para el mensaje"""
        message_lower = message.lower()

        # Verificar por categorías
        if promo.get("categories"):
            for cat in promo["categories"]:
                if cat.lower() in message_lower:
                    return True

        # Verificar por productos
        if promo.get("products"):
            for product in promo["products"]:
                if product.lower() in message_lower:
                    return True

        # Verificar por palabras clave
        if promo.get("keywords"):
            for keyword in promo["keywords"]:
                if keyword.lower() in message_lower:
                    return True

        return False


# Herramientas del PromotionsAgent
class ActivePromotionsTool:
    """Obtiene promociones activas"""

    def __init__(self, db_connection):
        self.db = db_connection

    def get_active_promotions_sync(self) -> List[Dict]:
        """Obtiene todas las promociones activas"""
        # En producción esto vendría de la BD
        # Simulación de promociones
        today = datetime.now()
        next_week = today + timedelta(days=7)

        promotions = [
            {
                "id": "promo_bf_2024",
                "name": "Black Friday Tech 2024",
                "description": "Hasta 40% de descuento en laptops gaming",
                "discount_percentage": 40,
                "discount_text": "Hasta 40% OFF",
                "categories": ["laptops", "gaming"],
                "featured": True,
                "requires_coupon": False,
                "valid_until": next_week.strftime("%d/%m/%Y"),
                "conditions": "En productos seleccionados",
            },
            {
                "id": "promo_3x2",
                "name": "3x2 en Accesorios",
                "description": "Lleva 3 accesorios y paga solo 2",
                "discount_text": "3x2",
                "categories": ["accesorios", "mouse", "teclado"],
                "featured": True,
                "requires_coupon": True,
                "coupon_code": "3X2ACC",
                "valid_until": next_week.strftime("%d/%m/%Y"),
            },
            {
                "id": "promo_estudiantes",
                "name": "Descuento Estudiantes",
                "description": "15% adicional con credencial estudiantil",
                "discount_percentage": 15,
                "discount_text": "15% OFF adicional",
                "requires_coupon": True,
                "coupon_code": "STUDENT15",
                "valid_until": (today + timedelta(days=30)).strftime("%d/%m/%Y"),
                "conditions": "Requiere verificación de estudiante",
            },
        ]

        return promotions


class PersonalizedOffersTool:
    """Genera ofertas personalizadas"""

    def __init__(self, llm):
        self.llm = llm

    def generate_personalized_offers_sync(self, customer, promotions: List[Dict], context: str = "") -> List[Dict]:
        """Genera ofertas personalizadas basadas en el cliente"""

        print(f"Genera ofertas...{promotions} {context}")
        if not customer:
            return []

        personalized = []

        # Analizar historial de compras
        purchase_categories = self._analyze_purchase_history(customer)

        # Crear ofertas basadas en patrones
        if "laptops" in purchase_categories:
            personalized.append(
                {
                    "title": "Upgrade tu Laptop",
                    "description": "Descuento especial en tu próxima laptop gaming",
                    "special_price": 45000,
                    "savings": 5000,
                    "based_on": "historial de compras",
                }
            )

        # Ofertas por tier
        if customer and customer.get("tier") == "vip":
            personalized.append(
                {
                    "title": "Oferta VIP Exclusiva",
                    "description": "20% adicional en cualquier compra superior a $50,000",
                    "special_price": 0,  # Calculado al aplicar
                    "discount_percentage": 20,
                    "based_on": "estatus VIP",
                }
            )

        return personalized

    def _analyze_purchase_history(self, customer) -> List[str]:
        """Analiza historial de compras para determinar preferencias"""
        categories = []

        if customer and customer.get("purchase_history"):
            for purchase in customer.get("purchase_history", []):
                if purchase.get("category"):
                    categories.append(purchase["category"])

        return list(set(categories))


class PromotionEligibilityTool:
    """Verifica elegibilidad para promociones"""

    def check_eligibility_sync(self, promotion: Dict, customer_tier: str, customer) -> bool:
        """Verifica si un cliente es elegible para una promoción"""
        # Verificar restricciones de tier
        if promotion.get("min_tier"):
            tier_levels = {"basic": 1, "premium": 2, "vip": 3}
            customer_level = tier_levels.get(customer_tier, 1)
            required_level = tier_levels.get(promotion["min_tier"], 1)

            if customer_level < required_level:
                return False

        # Verificar restricciones de compra mínima
        if promotion.get("min_purchase_amount") and customer:
            total_purchases = sum(p.get("amount", 0) for p in customer.get("purchase_history", []))

            if total_purchases < promotion["min_purchase_amount"]:
                return False

        # Verificar fecha de vigencia
        if promotion.get("valid_until"):
            try:
                valid_until = datetime.strptime(promotion["valid_until"], "%d/%m/%Y")
                if datetime.now() > valid_until:
                    return False
            except ValueError:
                pass

        return True


class CouponGeneratorTool:
    """Genera cupones personalizados"""

    def generate_personal_coupon_sync(self, customer_id: str, customer_tier: str) -> Dict[str, Any]:
        """Genera un cupón personalizado para el cliente"""
        # Generar código único
        import random
        import string

        code_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        code = f"{customer_tier.upper()}{code_suffix}"

        # Descuento según tier
        discounts = {"basic": 5, "premium": 10, "vip": 15}

        discount = discounts.get(customer_tier, 5)

        # Validez
        valid_until = datetime.now() + timedelta(days=7)

        return {
            "code": code,
            "discount": discount,
            "type": "percentage",
            "customer_id": customer_id,
            "valid_until": valid_until.strftime("%d/%m/%Y"),
            "conditions": "Válido en tu próxima compra",
        }
