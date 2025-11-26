"""
Promotions Node - E-commerce domain node for promotions and offers.
"""

import random
import string
from datetime import datetime, timedelta
from typing import Any

from app.core.agents import BaseAgent
from app.core.utils.tracing import trace_async_method


class PromotionsNode(BaseAgent):
    """E-commerce node specialized in promotions, offers and discounts"""

    def __init__(self, ollama=None, config: dict[str, Any] | None = None):
        super().__init__("promotions_node", config or {}, ollama=ollama)

        # Initialize simulated tools
        self.active_tool = ActivePromotionsTool(None)
        self.personalized_tool = PersonalizedOffersTool(None)
        self.eligibility_tool = PromotionEligibilityTool()
        self.coupon_tool = CouponGeneratorTool()

    @trace_async_method(
        name="promotions_node_process",
        run_type="chain",
        metadata={"agent_type": "promotions_node", "domain": "ecommerce"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Process promotion queries"""
        user_message = message
        customer = state_dict.get("customer", {})
        customer_tier = customer.get("tier", "basic") if customer else "basic"

        # Get active promotions (simulated - in production would use cache)
        active_promos = self.active_tool.get_active_promotions_sync()

        # Filter by customer eligibility
        eligible_promos = self._filter_eligible_promotions_sync(active_promos, customer_tier, customer)

        # Generate personalized offers
        personalized_offers = self.personalized_tool.generate_personalized_offers_sync(
            customer, eligible_promos, user_message
        )

        # Determine response type
        response_type = self._determine_response_type(user_message)

        if response_type == "specific_product":
            return self._handle_product_promotions(user_message, eligible_promos, personalized_offers)
        elif response_type == "coupon_request":
            return self._handle_coupon_request(customer, eligible_promos)
        else:
            return self._handle_general_promotions(eligible_promos, personalized_offers, customer_tier)

    def _determine_response_type(self, message: str) -> str:
        """Determine the type of promotion query"""
        message_lower = message.lower()

        if any(word in message_lower for word in ["cupon", "codigo"]):
            return "coupon_request"
        elif any(word in message_lower for word in ["laptop", "computadora", "producto"]):
            return "specific_product"
        else:
            return "general"

    def _handle_general_promotions(
        self, promotions: list[dict], personalized: list[dict], customer_tier: str
    ) -> dict[str, Any]:
        """Handle general promotion queries"""
        response = "**Promociones Activas**"

        if customer_tier in ["premium", "vip"]:
            response += f" - Exclusivas para clientes {customer_tier}\n\n"
        else:
            response += "\n\n"

        # Featured promotions
        featured_promos = [p for p in promotions if p.get("featured", False)]

        if featured_promos:
            response += "**DESTACADAS:**\n"
            for promo in featured_promos[:3]:
                response += self._format_promotion(promo)
                response += "\n"

        # Personalized offers
        if personalized:
            response += "\n**Recomendadas para ti:**\n"
            for offer in personalized[:3]:
                response += self._format_personalized_offer(offer)
                response += "\n"

        # Other promotions
        other_promos = [p for p in promotions if not p.get("featured", False)][:5]

        if other_promos:
            response += "\n**Mas ofertas:**\n"
            for promo in other_promos:
                response += self._format_promotion_brief(promo)
            response += "\n"

        # Additional info
        response += "\n**Tips:**\n"
        response += "- Las promociones son acumulables con tu descuento de cliente\n"
        response += "- Algunas ofertas requieren codigo de cupon\n"
        response += "- Los precios mostrados ya incluyen descuentos\n"

        # Call to action
        response += "\nTe interesa alguna promocion en particular?"

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
        self, message: str, promotions: list[dict], personalized: list[dict]
    ) -> dict[str, Any]:
        """Handle queries about specific product promotions"""
        _ = personalized  # unused
        # Find promotions related to mentioned product
        relevant_promos = []

        for promo in promotions:
            if self._is_promo_relevant(promo, message):
                relevant_promos.append(promo)

        if not relevant_promos:
            response = "No encontre promociones especificas para ese producto.\n\n"
            response += "Pero tengo estas ofertas generales que podrian interesarte:\n\n"

            # Show general promotions
            for promo in promotions[:3]:
                response += self._format_promotion_brief(promo)
        else:
            response = f"Encontre {len(relevant_promos)} promociones relacionadas:\n\n"

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

    def _handle_coupon_request(self, customer, promotions: list[dict]) -> dict[str, Any]:
        """Handle coupon requests"""
        # Filter promotions that have coupons
        coupon_promos = [p for p in promotions if p.get("requires_coupon", False)]

        if not coupon_promos:
            response = "No hay cupones activos en este momento.\n\n"
            response += "Pero estas promociones estan activas automaticamente:\n\n"

            auto_promos = [p for p in promotions if not p.get("requires_coupon", False)][:3]
            for promo in auto_promos:
                response += self._format_promotion_brief(promo)
        else:
            # Generate personalized coupon for premium/vip customers
            if customer and customer.get("tier") in ["premium", "vip"]:
                coupon = self.coupon_tool.generate_personal_coupon_sync(
                    customer.get("customer_id"), customer.get("tier")
                )

                response = f"**Tu cupon exclusivo {customer.get('tier')}:**\n\n"
                response += f"Codigo: **{coupon['code']}**\n"
                response += f"Descuento: {coupon['discount']}% adicional\n"
                response += f"Valido hasta: {coupon['valid_until']}\n\n"
            else:
                response = "**Cupones disponibles:**\n\n"

            # Show public coupons
            for promo in coupon_promos[:3]:
                if promo.get("coupon_code"):
                    response += f"**{promo['name']}**\n"
                    response += f"Codigo: `{promo['coupon_code']}`\n"
                    response += f"Descuento: {promo['discount_text']}\n"
                    response += f"{promo['description']}\n\n"

        response += "\nAplica el codigo en el carrito de compras"

        return {
            "messages": [{"role": "assistant", "content": response}],
            "current_agent": self.name,
            "agent_history": [self.name],
            "retrieved_data": {"coupon_promotions": coupon_promos},
            "is_complete": True,
        }

    def _filter_eligible_promotions_sync(
        self, promotions: list[dict], customer_tier: str, customer
    ) -> list[dict]:
        """Filter promotions by customer eligibility"""
        eligible = []

        for promo in promotions:
            is_eligible = self.eligibility_tool.check_eligibility_sync(promo, customer_tier, customer)
            if is_eligible:
                eligible.append(promo)

        return eligible

    def _format_promotion(self, promo: dict) -> str:
        """Format a complete promotion"""
        text = f"**{promo['name']}**\n"

        # Discount
        if promo.get("discount_percentage"):
            text += f"   {promo['discount_percentage']}% de descuento\n"
        elif promo.get("discount_amount"):
            text += f"   ${promo['discount_amount']} de descuento\n"
        elif promo.get("discount_text"):
            text += f"   {promo['discount_text']}\n"

        # Description
        text += f"   {promo['description']}\n"

        # Validity
        if promo.get("valid_until"):
            text += f"   Valido hasta: {promo['valid_until']}\n"

        # Conditions
        if promo.get("conditions"):
            text += f"   {promo['conditions']}\n"

        # Coupon if required
        if promo.get("requires_coupon") and promo.get("coupon_code"):
            text += f"   Usa el codigo: `{promo['coupon_code']}`\n"

        return text

    def _format_promotion_brief(self, promo: dict) -> str:
        """Format a brief promotion"""
        emoji = "**" if promo.get("featured") else "-"
        text = f"{emoji} **{promo['name']}** - {promo.get('discount_text', promo['description'])}\n"
        return text

    def _format_personalized_offer(self, offer: dict) -> str:
        """Format a personalized offer"""
        text = f"**{offer['title']}**\n"
        text += f"   {offer['description']}\n"
        text += f"   Tu precio especial: ${offer['special_price']:,.2f}\n"

        if offer.get("savings"):
            text += f"   Ahorras: ${offer['savings']:,.2f}\n"

        return text

    def _is_promo_relevant(self, promo: dict, message: str) -> bool:
        """Check if a promotion is relevant for the message"""
        message_lower = message.lower()

        # Check by categories
        if promo.get("categories"):
            for cat in promo["categories"]:
                if cat.lower() in message_lower:
                    return True

        # Check by products
        if promo.get("products"):
            for product in promo["products"]:
                if product.lower() in message_lower:
                    return True

        # Check by keywords
        if promo.get("keywords"):
            for keyword in promo["keywords"]:
                if keyword.lower() in message_lower:
                    return True

        return False


# Promotion Tools
class ActivePromotionsTool:
    """Gets active promotions"""

    def __init__(self, db_connection):
        self.db = db_connection

    def get_active_promotions_sync(self) -> list[dict]:
        """Get all active promotions"""
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
                "conditions": "Requiere verificacion de estudiante",
            },
        ]

        return promotions


class PersonalizedOffersTool:
    """Generates personalized offers"""

    def __init__(self, llm):
        self.llm = llm

    def generate_personalized_offers_sync(
        self, customer, promotions: list[dict], context: str = ""
    ) -> list[dict]:
        """Generate personalized offers based on customer"""
        _ = promotions, context  # unused
        if not customer:
            return []

        personalized = []

        # Analyze purchase history
        purchase_categories = self._analyze_purchase_history(customer)

        # Create offers based on patterns
        if "laptops" in purchase_categories:
            personalized.append(
                {
                    "title": "Upgrade tu Laptop",
                    "description": "Descuento especial en tu proxima laptop gaming",
                    "special_price": 45000,
                    "savings": 5000,
                    "based_on": "historial de compras",
                }
            )

        # Offers by tier
        if customer and customer.get("tier") == "vip":
            personalized.append(
                {
                    "title": "Oferta VIP Exclusiva",
                    "description": "20% adicional en cualquier compra superior a $50,000",
                    "special_price": 0,
                    "discount_percentage": 20,
                    "based_on": "estatus VIP",
                }
            )

        return personalized

    def _analyze_purchase_history(self, customer) -> list[str]:
        """Analyze purchase history to determine preferences"""
        categories = []

        if customer and customer.get("purchase_history"):
            for purchase in customer.get("purchase_history", []):
                if purchase.get("category"):
                    categories.append(purchase["category"])

        return list(set(categories))


class PromotionEligibilityTool:
    """Verifies promotion eligibility"""

    def check_eligibility_sync(self, promotion: dict, customer_tier: str, customer) -> bool:
        """Check if a customer is eligible for a promotion"""
        # Check tier restrictions
        if promotion.get("min_tier"):
            tier_levels = {"basic": 1, "premium": 2, "vip": 3}
            customer_level = tier_levels.get(customer_tier, 1)
            required_level = tier_levels.get(promotion["min_tier"], 1)

            if customer_level < required_level:
                return False

        # Check minimum purchase restrictions
        if promotion.get("min_purchase_amount") and customer:
            total_purchases = sum(p.get("amount", 0) for p in customer.get("purchase_history", []))

            if total_purchases < promotion["min_purchase_amount"]:
                return False

        # Check validity date
        if promotion.get("valid_until"):
            try:
                valid_until = datetime.strptime(promotion["valid_until"], "%d/%m/%Y")
                if datetime.now() > valid_until:
                    return False
            except ValueError:
                pass

        return True


class CouponGeneratorTool:
    """Generates personalized coupons"""

    def generate_personal_coupon_sync(self, customer_id: str, customer_tier: str) -> dict[str, Any]:
        """Generate a personalized coupon for the customer"""
        _ = customer_id  # unused
        # Generate unique code
        code_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        code = f"{customer_tier.upper()}{code_suffix}"

        # Discount by tier
        discounts = {"basic": 5, "premium": 10, "vip": 15}

        discount = discounts.get(customer_tier, 5)

        # Validity
        valid_until = datetime.now() + timedelta(days=7)

        return {
            "code": code,
            "discount": discount,
            "type": "percentage",
            "customer_id": customer_id,
            "valid_until": valid_until.strftime("%d/%m/%Y"),
            "conditions": "Valido en tu proxima compra",
        }


# Alias for backward compatibility
PromotionsAgent = PromotionsNode
