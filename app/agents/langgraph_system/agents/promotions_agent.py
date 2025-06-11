"""
Agente especializado en promociones y ofertas
"""
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List

from app.agents.langgraph_system.agents.base_agent import BaseAgent
from app.agents.langgraph_system.models import SharedState


class PromotionsAgent(BaseAgent):
    """Agente especializado en promociones, ofertas y descuentos"""
    
    def __init__(self, db_connection, cache_service, llm):
        super().__init__("promotions_agent")
        self.db = db_connection
        self.cache = cache_service
        self.llm = llm
        
        # Inicializar herramientas
        self.tools = [
            ActivePromotionsTool(db_connection),
            PersonalizedOffersTool(llm),
            PromotionEligibilityTool(),
            CouponGeneratorTool()
        ]
    
    async def _process_internal(self, state: SharedState) -> Dict[str, Any]:
        """Procesa consultas sobre promociones"""
        user_message = state.get_last_user_message()
        customer_tier = state.customer.tier if state.customer else "basic"
        customer_id = state.customer.customer_id if state.customer else None
        
        # Verificar caché primero
        cache_key = f"promos_{customer_id}_{datetime.now().strftime('%Y%m%d')}"
        state.add_cache_key(cache_key)
        
        cached_promos = await self._get_cached_promotions(cache_key)
        
        if cached_promos:
            active_promos = cached_promos
        else:
            # Obtener promociones activas
            active_promos = await self.tools[0].get_active_promotions()
            
            # Cachear por 1 hora
            await self._cache_promotions(cache_key, active_promos, ttl=3600)
        
        # Filtrar por elegibilidad del cliente
        eligible_promos = await self._filter_eligible_promotions(
            active_promos,
            customer_tier,
            state.customer
        )
        
        # Generar ofertas personalizadas
        personalized_offers = await self.tools[1].generate_personalized_offers(
            state.customer,
            eligible_promos,
            user_message
        )
        
        # Determinar tipo de respuesta
        response_type = self._determine_response_type(user_message)
        
        if response_type == "specific_product":
            return await self._handle_product_promotions(
                user_message, 
                eligible_promos,
                personalized_offers
            )
        elif response_type == "coupon_request":
            return await self._handle_coupon_request(
                state.customer,
                eligible_promos
            )
        else:
            return await self._handle_general_promotions(
                eligible_promos,
                personalized_offers,
                customer_tier
            )
    
    def _determine_response_type(self, message: str) -> str:
        """Determina el tipo de consulta sobre promociones"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["cupón", "cupon", "código", "codigo"]):
            return "coupon_request"
        elif any(word in message_lower for word in ["laptop", "computadora", "producto"]):
            return "specific_product"
        else:
            return "general"
    
    async def _handle_general_promotions(
        self, 
        promotions: List[Dict],
        personalized: List[Dict],
        customer_tier: str
    ) -> Dict[str, Any]:
        """Maneja consultas generales sobre promociones"""
        response = "🎉 **Promociones Activas**"
        
        if customer_tier in ["premium", "vip"]:
            response += f" - Exclusivas para clientes {customer_tier} 🌟\n\n"
        else:
            response += "\n\n"
        
        # Promociones destacadas
        featured_promos = [p for p in promotions if p.get('featured', False)]
        
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
        other_promos = [p for p in promotions if not p.get('featured', False)][:5]
        
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
            "text": response,
            "data": {
                "promotions": promotions,
                "personalized_offers": personalized,
                "total_promotions": len(promotions)
            },
            "tools_used": ["ActivePromotionsTool", "PersonalizedOffersTool"]
        }
    
    async def _handle_product_promotions(
        self,
        message: str,
        promotions: List[Dict],
        personalized: List[Dict]
    ) -> Dict[str, Any]:
        """Maneja consultas sobre promociones de productos específicos"""
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
            "text": response,
            "data": {
                "relevant_promotions": relevant_promos
            },
            "tools_used": ["ActivePromotionsTool"]
        }
    
    async def _handle_coupon_request(
        self,
        customer,
        promotions: List[Dict]
    ) -> Dict[str, Any]:
        """Maneja solicitudes de cupones"""
        # Filtrar promociones que tienen cupones
        coupon_promos = [p for p in promotions if p.get('requires_coupon', False)]
        
        if not coupon_promos:
            response = "😔 No hay cupones activos en este momento.\n\n"
            response += "Pero estas promociones están activas automáticamente:\n\n"
            
            auto_promos = [p for p in promotions if not p.get('requires_coupon', False)][:3]
            for promo in auto_promos:
                response += self._format_promotion_brief(promo)
        else:
            # Generar cupón personalizado si es cliente premium/vip
            if customer and customer.tier in ["premium", "vip"]:
                coupon = await self.tools[3].generate_personal_coupon(
                    customer.customer_id,
                    customer.tier
                )
                
                response = f"🎟️ **Tu cupón exclusivo {customer.tier}:**\n\n"
                response += f"📱 Código: **{coupon['code']}**\n"
                response += f"💰 Descuento: {coupon['discount']}% adicional\n"
                response += f"⏰ Válido hasta: {coupon['valid_until']}\n\n"
            else:
                response = "🎟️ **Cupones disponibles:**\n\n"
            
            # Mostrar cupones públicos
            for promo in coupon_promos[:3]:
                if promo.get('coupon_code'):
                    response += f"**{promo['name']}**\n"
                    response += f"📱 Código: `{promo['coupon_code']}`\n"
                    response += f"💰 Descuento: {promo['discount_text']}\n"
                    response += f"✅ {promo['description']}\n\n"
        
        response += "\n💡 Aplica el código en el carrito de compras"
        
        return {
            "text": response,
            "data": {
                "coupon_promotions": coupon_promos
            },
            "tools_used": ["CouponGeneratorTool"]
        }
    
    async def _filter_eligible_promotions(
        self,
        promotions: List[Dict],
        customer_tier: str,
        customer
    ) -> List[Dict]:
        """Filtra promociones según elegibilidad del cliente"""
        eligible = []
        
        for promo in promotions:
            # Verificar elegibilidad
            is_eligible = await self.tools[2].check_eligibility(
                promo,
                customer_tier,
                customer
            )
            
            if is_eligible:
                eligible.append(promo)
        
        return eligible
    
    def _format_promotion(self, promo: Dict) -> str:
        """Formatea una promoción completa"""
        text = f"🏷️ **{promo['name']}**\n"
        
        # Descuento
        if promo.get('discount_percentage'):
            text += f"   💰 {promo['discount_percentage']}% de descuento\n"
        elif promo.get('discount_amount'):
            text += f"   💰 ${promo['discount_amount']} de descuento\n"
        elif promo.get('discount_text'):
            text += f"   💰 {promo['discount_text']}\n"
        
        # Descripción
        text += f"   📝 {promo['description']}\n"
        
        # Vigencia
        if promo.get('valid_until'):
            text += f"   ⏰ Válido hasta: {promo['valid_until']}\n"
        
        # Condiciones
        if promo.get('conditions'):
            text += f"   ⚠️ {promo['conditions']}\n"
        
        # Cupón si requiere
        if promo.get('requires_coupon') and promo.get('coupon_code'):
            text += f"   🎟️ Usa el código: `{promo['coupon_code']}`\n"
        
        return text
    
    def _format_promotion_brief(self, promo: Dict) -> str:
        """Formatea una promoción de forma breve"""
        emoji = "🔥" if promo.get('featured') else "•"
        text = f"{emoji} **{promo['name']}** - {promo.get('discount_text', promo['description'])}\n"
        return text
    
    def _format_personalized_offer(self, offer: Dict) -> str:
        """Formatea una oferta personalizada"""
        text = f"🎯 **{offer['title']}**\n"
        text += f"   {offer['description']}\n"
        text += f"   💰 Tu precio especial: ${offer['special_price']:,.2f}\n"
        
        if offer.get('savings'):
            text += f"   💸 Ahorras: ${offer['savings']:,.2f}\n"
        
        return text
    
    def _is_promo_relevant(self, promo: Dict, message: str) -> bool:
        """Verifica si una promoción es relevante para el mensaje"""
        message_lower = message.lower()
        
        # Verificar por categorías
        if promo.get('categories'):
            for cat in promo['categories']:
                if cat.lower() in message_lower:
                    return True
        
        # Verificar por productos
        if promo.get('products'):
            for product in promo['products']:
                if product.lower() in message_lower:
                    return True
        
        # Verificar por palabras clave
        if promo.get('keywords'):
            for keyword in promo['keywords']:
                if keyword.lower() in message_lower:
                    return True
        
        return False
    
    async def _get_cached_promotions(self, cache_key: str) -> List[Dict]:
        """Obtiene promociones del caché"""
        try:
            if self.cache:
                cached = await self.cache.get(cache_key)
                if cached:
                    return json.loads(cached)
        except Exception as e:
            self.logger.warning(f"Error getting cached promotions: {e}")
        
        return None
    
    async def _cache_promotions(self, cache_key: str, promotions: List[Dict], ttl: int):
        """Guarda promociones en caché"""
        try:
            if self.cache:
                await self.cache.set(
                    cache_key,
                    json.dumps(promotions),
                    expire=ttl
                )
        except Exception as e:
            self.logger.warning(f"Error caching promotions: {e}")


# Herramientas del PromotionsAgent
class ActivePromotionsTool:
    """Obtiene promociones activas"""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    async def get_active_promotions(self) -> List[Dict]:
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
                "conditions": "En productos seleccionados"
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
                "valid_until": next_week.strftime("%d/%m/%Y")
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
                "conditions": "Requiere verificación de estudiante"
            }
        ]
        
        return promotions


class PersonalizedOffersTool:
    """Genera ofertas personalizadas"""
    
    def __init__(self, llm):
        self.llm = llm
    
    async def generate_personalized_offers(
        self,
        customer,
        promotions: List[Dict],
        context: str = ""
    ) -> List[Dict]:
        """Genera ofertas personalizadas basadas en el cliente"""
        if not customer:
            return []
        
        personalized = []
        
        # Analizar historial de compras
        purchase_categories = self._analyze_purchase_history(customer)
        
        # Crear ofertas basadas en patrones
        if "laptops" in purchase_categories:
            personalized.append({
                "title": "Upgrade tu Laptop",
                "description": "Descuento especial en tu próxima laptop gaming",
                "special_price": 45000,
                "savings": 5000,
                "based_on": "historial de compras"
            })
        
        # Ofertas por tier
        if customer.tier == "vip":
            personalized.append({
                "title": "Oferta VIP Exclusiva",
                "description": "20% adicional en cualquier compra superior a $50,000",
                "special_price": 0,  # Calculado al aplicar
                "discount_percentage": 20,
                "based_on": "estatus VIP"
            })
        
        return personalized
    
    def _analyze_purchase_history(self, customer) -> List[str]:
        """Analiza historial de compras para determinar preferencias"""
        categories = []
        
        if customer and customer.purchase_history:
            for purchase in customer.purchase_history:
                if purchase.get('category'):
                    categories.append(purchase['category'])
        
        return list(set(categories))


class PromotionEligibilityTool:
    """Verifica elegibilidad para promociones"""
    
    async def check_eligibility(
        self,
        promotion: Dict,
        customer_tier: str,
        customer
    ) -> bool:
        """Verifica si un cliente es elegible para una promoción"""
        # Verificar restricciones de tier
        if promotion.get('min_tier'):
            tier_levels = {"basic": 1, "premium": 2, "vip": 3}
            customer_level = tier_levels.get(customer_tier, 1)
            required_level = tier_levels.get(promotion['min_tier'], 1)
            
            if customer_level < required_level:
                return False
        
        # Verificar restricciones de compra mínima
        if promotion.get('min_purchase_amount') and customer:
            total_purchases = sum(
                p.get('amount', 0) 
                for p in customer.purchase_history
            )
            
            if total_purchases < promotion['min_purchase_amount']:
                return False
        
        # Verificar fecha de vigencia
        if promotion.get('valid_until'):
            try:
                valid_until = datetime.strptime(promotion['valid_until'], "%d/%m/%Y")
                if datetime.now() > valid_until:
                    return False
            except:
                pass
        
        return True


class CouponGeneratorTool:
    """Genera cupones personalizados"""
    
    async def generate_personal_coupon(
        self,
        customer_id: str,
        customer_tier: str
    ) -> Dict[str, Any]:
        """Genera un cupón personalizado para el cliente"""
        # Generar código único
        import random
        import string
        
        code_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        code = f"{customer_tier.upper()}{code_suffix}"
        
        # Descuento según tier
        discounts = {
            "basic": 5,
            "premium": 10,
            "vip": 15
        }
        
        discount = discounts.get(customer_tier, 5)
        
        # Validez
        valid_until = datetime.now() + timedelta(days=7)
        
        return {
            "code": code,
            "discount": discount,
            "type": "percentage",
            "customer_id": customer_id,
            "valid_until": valid_until.strftime("%d/%m/%Y"),
            "conditions": "Válido en tu próxima compra"
        }