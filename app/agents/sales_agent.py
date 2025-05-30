from typing import Any, Dict

from app.agents.base_agent import BaseAgent


class SalesAgent(BaseAgent):
    """Agente para manejar el cierre de ventas y proceso de compra"""
    
    async def process(self, customer: Dict[str, Any], message_text: str, historial: str) -> str:
        """Procesa intenciones de compra y guía el cierre de venta con AI"""
        
        # Identificar productos de interés en el historial
        interested_products = await self._identify_interested_products(historial, message_text)
        
        # Obtener información de pago y envío
        payment_shipping_info = self._get_payment_shipping_info()
        
        # Calcular totales si hay productos específicos
        order_summary = self._prepare_order_summary(interested_products)
        
        # Construir contexto específico
        context_info = {
            "Productos de interés": self._format_interested_products(interested_products),
            "Resumen de orden": order_summary,
            "Información de pago y envío": payment_shipping_info,
            "Cliente VIP": customer.get('vip', False),
            "Compras previas": customer.get('total_inquiries', 0),
        }
        
        context = self._build_context(customer, context_info)
        
        # Prompt específico para cierre de venta
        prompt = f"""
        Eres un asesor de ventas de Conversa Shop guiando al cliente para concretar la compra.
        
        CONTEXTO:
        {context}
        
        HISTORIAL:
        {historial}
        
        MENSAJE DEL CLIENTE:
        {message_text}
        
        INSTRUCCIONES:
        1. Confirma el interés de compra con entusiasmo profesional
        2. Resume claramente los productos que el cliente quiere comprar
        3. Presenta el total con cualquier descuento aplicable
        4. Explica las opciones de pago disponibles
        5. Detalla las opciones de envío/retiro con tiempos
        6. Si hay stock limitado, mencionalo para crear urgencia sutil
        7. Proporciona los pasos siguientes claros y numerados
        8. Ofrece asistencia adicional si necesita ayuda
        
        PROCESO DE COMPRA:
        1. Confirmación de productos y cantidades
        2. Datos de facturación
        3. Selección de método de pago
        4. Dirección de envío o coordinación de retiro
        5. Confirmación final del pedido
        
        MÉTODOS DE PAGO:
        - Efectivo (10% descuento)
        - Transferencia bancaria (5% descuento)
        - MercadoPago (cuotas sin interés disponibles)
        - Tarjetas de crédito (3, 6, 12 cuotas)
        - Tarjetas de débito
        
        OPCIONES DE ENVÍO:
        - Retiro en local (Gratis) - Inmediato con stock
        - Envío CABA/GBA (24-48hs) - $X
        - Envío al interior (3-5 días) - Calculado por peso
        - Envío express (24hs) - Tarifa premium
        
        BENEFICIOS ADICIONALES:
        - Factura A o B
        - Garantía oficial extendida disponible
        - Soporte técnico post-venta
        - Descuentos en próximas compras para clientes
        
        Genera una respuesta que facilite y concrete la venta de manera profesional.
        """
        
        response = await self.ai_service._generate_content(prompt=prompt, temperature=0.6)
        return response
    
    async def _identify_interested_products(self, historial: str, message_text: str):
        """Identifica productos mencionados en el historial que el cliente quiere comprar"""
        # Buscar menciones de productos en el historial
        all_text = historial + " " + message_text
        
        # Buscar productos por términos mencionados
        products = []
        
        # Patrones para identificar productos de interés
        import re
        product_patterns = [
            r"quiero (?:el|la|comprar) (.+?)(?:\.|,|$)",
            r"me (?:interesa|gusta) (?:el|la) (.+?)(?:\.|,|$)",
            r"(?:el|la) (.+?) (?:que|de) .+? (?:mencionaste|dijiste)",
        ]
        
        search_terms = []
        for pattern in product_patterns:
            matches = re.findall(pattern, all_text.lower())
            search_terms.extend(matches)
        
        # Buscar productos específicos mencionados
        for term in search_terms[:3]:  # Limitar búsquedas
            found_products = await self.product_service.search_products(
                search_term=term.strip(), limit=2
            )
            products.extend(found_products)
        
        # Si no se encontraron productos específicos, buscar los últimos consultados
        if not products and "laptop" in all_text.lower():
            products = await self.product_service.get_products_by_category("laptops", limit=2)
        
        return products[:3]  # Máximo 3 productos
    
    def _get_payment_shipping_info(self) -> str:
        """Obtiene información de métodos de pago y envío"""
        info = []
        
        # Métodos de pago
        info.append("PAGOS: Efectivo (10% dto), Transferencia (5% dto), MercadoPago, Tarjetas")
        
        # Opciones de envío
        info.append("ENVÍOS: Retiro gratis, CABA 24hs ($1500), Interior 3-5 días")
        
        # Beneficios
        info.append("BENEFICIOS: Factura A/B, Garantía oficial, Soporte post-venta")
        
        return " | ".join(info)
    
    def _prepare_order_summary(self, products: list) -> str:
        """Prepara un resumen de la orden"""
        if not products:
            return "A definir según productos seleccionados"
        
        summary_parts = []
        total = 0
        
        for product in products:
            summary_parts.append(f"{product.name}: ${product.price:,.0f}")
            total += product.price
        
        summary_parts.append(f"SUBTOTAL: ${total:,.0f}")
        
        # Calcular descuentos potenciales
        descuento_efectivo = total * 0.10
        summary_parts.append(f"Descuento efectivo: -${descuento_efectivo:,.0f}")
        summary_parts.append(f"TOTAL EFECTIVO: ${total - descuento_efectivo:,.0f}")
        
        return " | ".join(summary_parts)
    
    def _format_interested_products(self, products: list) -> str:
        """Formatea los productos de interés"""
        if not products:
            return "A confirmar según selección del cliente"
        
        formatted = []
        for product in products:
            status = "✅ Disponible" if product.stock > 0 else "❌ Sin stock"
            formatted.append(f"{product.name} ({status}) - ${product.price:,.0f}")
        
        return "; ".join(formatted)