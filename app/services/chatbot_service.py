import logging
import re
import traceback
from typing import List, Optional, Tuple

from app.config.settings import get_settings
from app.models.conversation import ConversationHistory
from app.models.database import Customer, Product
from app.models.message import BotResponse, Contact, WhatsAppMessage
from app.repositories.redis_repository import RedisRepository
from app.services.ai_service import AIService
from app.services.product_service import CustomerService, ProductService
from app.services.whatsapp_service import WhatsAppService
from app.utils.certificate_utils import CertificateGenerator

# Configurar expiración de conversación (24 horas)
CONVERSATION_EXPIRATION = 86400  # 24 horas en segundos

# Constantes para palabras clave organizadas por categoría
KEYWORDS = {
    "saludos": ["hola", "hello", "buenas", "hey", "hi", "buenos días", "buenas tardes", "buenas noches"],
    "computadoras": ["computadora", "laptop", "notebook", "pc", "ordenador", "equipo", "desktop"],
    "gaming": ["gaming", "juegos", "gamer", "videojuegos", "fps", "rtx", "gpu", "gaming pc"],
    "precios": ["precio", "costo", "cuanto", "cuánto", "vale", "barato", "caro", "oferta", "descuento"],
    "software": ["software", "programa", "office", "windows", "antivirus", "adobe", "licencia"],
    "componentes": ["procesador", "cpu", "ram", "memoria", "disco", "ssd", "hdd", "motherboard", "fuente"],
    "trabajo": ["trabajo", "oficina", "empresa", "negocio", "profesional", "productividad"],
    "specs": ["especificaciones", "specs", "rendimiento", "benchmarks", "comparar", "diferencia"],
    "despedidas": ["gracias", "bye", "adiós", "hasta luego", "nos vemos", "chau"],
    "soporte": ["garantía", "soporte", "problema", "ayuda técnica", "reparación", "servicio"],
    "stock": ["stock", "disponible", "hay", "tienen", "cuando llega", "disponibilidad"],
    "marcas": ["asus", "msi", "lenovo", "hp", "dell", "corsair", "logitech", "amd", "intel", "nvidia"],
}

BUSINESS_NAME = "Conversa Shop"


class ChatbotService:
    """
    Servicio principal que coordina la interacción con el chatbot
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.settings = get_settings()

        # Servicios
        self.redis_repo = RedisRepository[ConversationHistory](ConversationHistory, prefix="chat")
        self.whatsapp_service = WhatsAppService()
        self.ai_service = AIService()
        self.product_service = ProductService()
        self.customer_service = CustomerService()
        self.certificate_generator = CertificateGenerator()

    async def procesar_mensaje(self, message: WhatsAppMessage, contact: Contact) -> BotResponse:
        """
        Procesa un mensaje entrante de WhatsApp

        Args:
            message: Mensaje entrante
            contact: Información del contacto

        Returns:
            Respuesta del procesamiento
        """

        user_number = None
        customer = None

        try:
            # 1. Extraer message_text y validar datos
            user_number = contact.wa_id
            message_text = self._extract_message_text(message)

            if not message_text.strip():
                self.logger.warning(f"Mensaje vacío recibido de {user_number}")
                return BotResponse(status="failure", message="No se pudo procesar el mensaje vacío")

            self.logger.info(f"Procesando mensaje de {user_number}: '{message_text[:50]}...'")

            # 2. Obtener o crear cliente
            customer = await self.customer_service.get_or_create_customer(
                phone_number=user_number, profile_name=contact.profile.get("name")
            )

            if not customer:
                self.logger.error(f"No se pudo crear/obtener cliente para {user_number}")
                return BotResponse(status="failure", message="Error interno del sistema")

            # 3. Buscar historial de conversación
            conversation = await self._get_or_create_conversation(user_number)

            # Añadir mensaje del usuario al historial
            conversation.add_message("persona", message_text)

            # Obtener historial formateado para el contexto
            historial_str = conversation.to_formatted_history()
            self.logger.debug(f"Historial de conversación para {user_number}: {len(conversation.messages)} mensajes")

            # 4. Detectar intención y generar respuesta usando la base de datos
            intent, confidence = self._detect_intent(message_text)
            bot_response = await self._generate_response_from_db(
                customer, message_text, intent, confidence, historial_str
            )

            # 5. Añadir respuesta del bot al historial
            conversation.add_message("bot", bot_response)

            # 6. Guardar conversación actualizada en Redis
            await self._save_conversation(user_number, conversation)

            # 7. Enviar respuesta por WhatsApp
            await self._send_whatsapp_response(user_number, bot_response)

            self.logger.info(f"Mensaje procesado exitosamente para {user_number}")
            return BotResponse(status="success", message=bot_response)

        except Exception as e:
            tb = traceback.format_exc()
            error_msg = f"Error procesando mensaje para {user_number or 'unknown'}"
            self.logger.error(f"{error_msg}: {e}\n{tb}")
            # Intentar enviar mensaje de error al usuario
            if user_number:
                try:
                    await self._send_whatsapp_response(
                        user_number,
                        "Lo siento, ocurrió un error técnico. Por favor, intenta nuevamente en un momento. 🔧",
                    )
                except Exception as send_error:
                    self.logger.error(f"No se pudo enviar mensaje de error a {user_number}: {send_error}")

            return BotResponse(status="failure", message="Error en el procesamiento del mensaje")

    def _detect_intent(self, message_text: str) -> Tuple[str, float]:
        """
        Detecta la intención del mensaje basándose en palabras clave

        Returns:
            Tuple con (categoría, confianza)
        """
        ### TODO: hacerlo con AI.
        message_lower = message_text.lower()
        detected_intents = []

        for category, keywords in KEYWORDS.items():
            matches = sum(1 for keyword in keywords if keyword in message_lower)
            if matches > 0:
                confidence = matches / len(keywords)
                detected_intents.append((category, confidence))

        if detected_intents:
            # Ordenar por confianza y retornar el más alto
            detected_intents.sort(key=lambda x: x[1], reverse=True)
            return detected_intents[0]

        return ("general", 0.0)

    async def _generate_response_from_db(
        self, customer: Customer, message_text: str, intent: str, confidence: float, historial: str
    ) -> str:
        """Genera respuestas usando datos de PostgreSQL"""
        ### TODO: Hacerlo con AI. Usar confidence e historial
        print(f"Usar con AI - Confidencia: {confidence} - Historial: {historial}")
        message_lower = message_text.lower()

        # Registrar la consulta del cliente
        await self.customer_service.log_product_inquiry(
            customer_id=str(customer.id), inquiry_type=intent, inquiry_text=message_text
        )

        # Detectar saludos
        if intent == "saludos":
            return await self._handle_greeting_db()

        # Detectar consultas sobre laptops
        elif intent == "computadoras" or any(palabra in message_lower for palabra in ["laptop", "notebook"]):
            return await self._handle_laptop_inquiry_db(message_lower, customer)

        # Detectar consultas sobre gaming
        elif intent == "gaming":
            return await self._handle_gaming_inquiry_db(message_lower, customer)

        # Detectar consultas sobre precios
        elif intent == "precios":
            return await self._handle_price_inquiry_db(message_lower, customer)

        # Detectar consultas sobre componentes
        elif intent == "componentes":
            return await self._handle_components_inquiry_db(message_lower, customer)

        # Detectar consultas sobre marcas
        elif intent == "marcas" or any(marca in message_lower for marca in KEYWORDS["marcas"]):
            return await self._handle_brand_inquiry_db(message_lower, customer)

        # Detectar consultas sobre stock
        elif intent == "stock":
            return await self._handle_stock_inquiry_db(message_lower, customer)

        # Detectar consultas sobre trabajo
        elif intent == "trabajo":
            return await self._handle_work_inquiry_db(message_lower, customer)

        # Detectar despedidas
        elif intent == "despedidas":
            return await self._handle_farewell_db(customer)

        # Respuesta general con datos de la DB
        else:
            return await self._handle_general_response_db(customer)

    async def _handle_greeting_db(self) -> str:
        """Mensaje de bienvenida con datos reales de la DB"""
        try:
            # Obtener categorías con conteos
            categories = await self.product_service.get_categories_with_counts()

            # Obtener promociones activas
            promotions = await self.product_service.get_active_promotions()

            response = f"¡Hola! 👋 Soy tu asesor virtual de **{BUSINESS_NAME}**.\n\n"
            response += "🖥️ **Productos disponibles:**\n"

            for category in categories[:4]:  # Mostrar máximo 4 categorías
                response += f"• {category['display_name']} ({category['product_count']} productos) -"
                response += f" desde ${category['min_price']:,.0f}\n"

            if promotions:
                response += "\n🔥 **¡Promociones vigentes!**\n"
                for promo in promotions[:3]:  # Mostrar máximo 3 promociones
                    discount = promo.discount_percentage or (promo.discount_amount or 0)
                    response += f"• {promo.name} - {discount}% OFF\n"

            response += "\n¿En qué puedo ayudarte hoy?"
            return response

        except Exception as e:
            self.logger.error(f"Error in greeting handler: {e}")
            return (
                "¡Hola! 👋 Soy tu asesor virtual especializado en productos informáticos.\n¿En qué puedo ayudarte hoy?"
            )

    async def _handle_laptop_inquiry_db(self, message_lower: str, customer: Customer) -> str:
        """Maneja consultas sobre laptops usando datos reales de la DB"""
        print(f"Mensaje en lower: {message_lower}")
        print(f"Customer: {customer}")
        try:
            # Detectar subcategoría
            subcategory = None
            if any(word in message_lower for word in ["gaming", "juegos", "gamer"]):
                subcategory = "gaming"
            elif any(word in message_lower for word in ["trabajo", "oficina", "empresa"]):
                subcategory = "work"
            elif any(word in message_lower for word in ["barato", "económico", "básico"]):
                subcategory = "budget"

            # Obtener laptops de la base de datos
            laptops: List[Product] = await self.product_service.get_products_by_category(
                category_name="laptops", subcategory_name=subcategory, limit=5
            )

            if not laptops:
                return "Lo siento, no tengo laptops disponibles en este momento. ¿Te interesa algún otro producto?"

            # Construir respuesta
            category_name = subcategory.title() if subcategory else "Disponibles"
            response = f"💻 **Laptops {category_name}:**\n\n"

            for laptop in laptops:
                stock_emoji = "✅" if laptop["stock"] > 5 else "⚠️" if laptop["stock"] > 0 else "❌"
                response += f"{stock_emoji} **{laptop.name}**\n"
                response += f"   📋 {laptop.specs}\n"
                response += f"   💰 ${laptop.price:,.0f}\n"

                if laptop.brand is not None:
                    response += f"   🏷️ {laptop.brand.display_name}\n"

                response += f"   📦 Stock: {laptop.stock} unidades\n\n"

            response += "¿Te interesa alguna en particular? ¿Tienes un presupuesto específico?"
            return response

        except Exception as e:
            self.logger.error(f"Error in laptop inquiry handler: {e}")
            return "Tengo una excelente selección de laptops. ¿Qué tipo buscas? ¿Gaming, trabajo o uso general?"

    async def _handle_components_inquiry_db(self, message_lower: str, customer: Customer) -> str:
        """Maneja consultas sobre componentes"""
        print(f"Customer: {customer}")
        try:
            # Detectar tipo de componente
            component_type = None
            if any(word in message_lower for word in ["procesador", "cpu", "ryzen", "intel"]):
                component_type = "cpu"
            elif any(word in message_lower for word in ["gpu", "tarjeta", "video", "rtx", "nvidia"]):
                component_type = "gpu"
            elif any(word in message_lower for word in ["ram", "memoria"]):
                component_type = "ram"
            elif any(word in message_lower for word in ["disco", "ssd", "hdd", "almacenamiento"]):
                component_type = "storage"

            components = await self.product_service.get_products_by_category(
                category_name="components", subcategory_name=component_type, limit=6
            )

            response = "🔧 **Componentes Disponibles:**\n\n"

            if components:
                for component in components:
                    response += f"• **{component.name}**\n"
                    response += f"  📋 {component.specs}\n"
                    response += f"  💰 ${component.price:,.0f}\n"
                    if component.brand is not None:
                        response += f"  🏷️ {component.brand.display_name}\n"
                    response += f"  📦 Stock: {component.stock} unidades\n\n"
            else:
                response += "No tengo componentes disponibles en este momento.\n"

            response += "¿Buscas algo específico? ¿Estás armando una PC completa?"
            return response

        except Exception as e:
            self.logger.error(f"Error in components inquiry handler: {e}")
            return "🔧 Tenemos una amplia variedad de componentes. ¿Qué tipo de componente necesitas?"

    async def _handle_brand_inquiry_db(self, message_lower: str, customer: Customer) -> str:
        """Maneja consultas sobre marcas específicas"""
        print(f"Customer: {customer}")
        try:
            # Detectar marca mencionada
            brand_mentioned = None
            brand_keywords = {
                "asus": ["asus", "rog"],
                "msi": ["msi"],
                "lenovo": ["lenovo", "thinkpad"],
                "hp": ["hp"],
                "dell": ["dell", "latitude"],
                "corsair": ["corsair"],
                "logitech": ["logitech"],
                "amd": ["amd", "ryzen"],
                "intel": ["intel"],
                "nvidia": ["nvidia", "geforce", "rtx"],
            }

            for brand, keywords in brand_keywords.items():
                if any(keyword in message_lower for keyword in keywords):
                    brand_mentioned = brand
                    break

            if brand_mentioned:
                # Buscar productos de esa marca
                products = await self.product_service.search_products(
                    search_term="", brand_filter=brand_mentioned, limit=6
                )

                if products:
                    response = f"🏷️ **Productos {brand_mentioned.upper()} disponibles:**\n\n"
                    for product in products:
                        response += f"• **{product.name}** - ${product.price:,.0f}\n"
                        response += f"  📋 {product.specs[:60]}...\n"
                        response += f"  📦 Stock: {product.stock}\n\n"

                    response += "¿Te interesa algún modelo en particular?"
                else:
                    response = f"No tengo productos {brand_mentioned.upper()} disponibles en este momento."
            else:
                # Mostrar marcas disponibles
                brands = await self.product_service.get_brands()
                response = "🏷️ **Marcas disponibles:**\n\n"

                for brand in brands[:10]:
                    response += f"• **{brand.display_name}**"
                    if brand.specialty is not None:
                        response += f" - Especialidad: {brand.specialty}"
                    response += "\n"

                response += "\n¿Qué marca te interesa?"

            return response

        except Exception as e:
            self.logger.error(f"Error in brand inquiry handler: {e}")
            return "🏷️ Trabajamos con las mejores marcas del mercado. ¿Cuál te interesa?"

    async def _handle_gaming_inquiry_db(self, message_lower: str, customer: Customer) -> str:
        """Maneja consultas sobre gaming con datos reales"""
        print(f"Mensaje en lower: {message_lower}")
        print(f"Customer: {customer}")
        try:
            # Obtener productos gaming
            gaming_laptops = await self.product_service.get_products_by_category("laptops", "gaming", limit=3)
            gaming_desktops = await self.product_service.get_products_by_category("desktops", "gaming", limit=3)

            response = "🎮 **¡Equipos Gaming Disponibles!**\n\n"

            if gaming_laptops:
                response += "**💻 Laptops Gaming:**\n"
                for laptop in gaming_laptops:
                    response += f"• {laptop.name} - ${laptop.price:,.0f} (Stock: {laptop.stock})\n"

            if gaming_desktops:
                response += "\n**🖥️ PCs Gaming:**\n"
                for pc in gaming_desktops:
                    response += f"• {pc.name} - ${pc.price:,.0f} (Stock: {pc.stock})\n"

            # Agregar promociones gaming si existen
            promotions = await self.product_service.get_active_promotions()
            gaming_promos = [p for p in promotions if "gaming" in p.name.lower()]

            if gaming_promos:
                response += "\n🔥 **¡OFERTAS GAMING!**\n"
                for promo in gaming_promos[:2]:
                    discount = promo.discount_percentage or promo.discount_amount
                    response += f"• {promo.name} - {discount}% OFF\n"

            response += "\n¿Qué juegos planeas usar? ¿Cuál es tu presupuesto aproximado?"
            return response

        except Exception as e:
            self.logger.error(f"Error in gaming inquiry handler: {e}")
            return "🎮 Tengo excelentes equipos gaming. ¿Prefieres laptop o PC de escritorio?"

    async def _handle_price_inquiry_db(self, message_lower: str, customer: Customer) -> str:
        """Maneja consultas sobre precios con datos reales"""
        try:
            # Extraer números del mensaje para detectar presupuesto
            numbers = re.findall(r"\d+", message_lower)

            if numbers:
                budget = float(numbers[0])

                # Registrar presupuesto mencionado
                await self.customer_service.log_product_inquiry(
                    customer_id=str(customer.id),
                    inquiry_type="price_budget",
                    inquiry_text=message_lower,
                    budget_mentioned=budget,
                )

                # Obtener productos dentro del presupuesto
                products = await self.product_service.get_products_by_price_range(0, budget, limit=6)

                if products:
                    response = f"💰 **Productos dentro de tu presupuesto de ${budget:,.0f}:**\n\n"

                    for product in products:
                        response += f"• **{product.name}** - ${product.price:,.0f}\n"
                        response += f"  📋 {product.specs[:60]}...\n"
                        response += f"  📦 Stock: {product.stock}\n\n"

                    response += "¿Alguno te llama la atención? ¿Necesitas más detalles?"
                    return response
                else:
                    return (
                        f"Con un presupuesto de ${budget:,.0f}, te recomiendo "
                        "contactarme para opciones personalizadas. ¿Qué tipo de equipo específicamente necesitas?"
                    )

            # Respuesta general con rangos de precios
            categories = await self.product_service.get_categories_with_counts()

            response = "💰 **Rangos de Precios por Categoría:**\n\n"

            for category in categories:
                response += (
                    f"• **{category['display_name']}**: ${category['min_price']:,.0f} - ${category['max_price']:,.0f}\n"
                )
                response += f"  📊 Precio promedio: ${category['avg_price']:,.0f}\n\n"

            # Mostrar promociones
            promotions = await self.product_service.get_active_promotions()
            if promotions:
                response += "🔥 **Promociones vigentes:**\n"
                for promo in promotions[:3]:
                    discount = promo.discount_percentage or promo.discount_amount
                    response += f"• {promo.name} - {discount}% OFF\n"

            response += "\n¿Tienes un presupuesto específico en mente?"
            return response

        except Exception as e:
            self.logger.error(f"Error in price inquiry handler: {e}")
            return "💰 ¿Cuál es tu presupuesto? Te puedo mostrar las mejores opciones disponibles."

    async def _handle_stock_inquiry_db(self, message_lower: str, customer: Customer) -> str:
        """Maneja consultas sobre stock con datos reales"""
        print(f"Mensaje en lower: {message_lower}")
        print(f"Customer: {customer}")
        try:
            # Obtener reporte de stock
            stock_report = await self.product_service.get_stock_report()

            response = "📦 **Estado de Inventario Actual:**\n\n"

            if stock_report and "category_breakdown" in stock_report:
                for category in stock_report["category_breakdown"]:
                    total_stock = category.get("total_stock", 0)
                    status_emoji = "✅" if total_stock > 50 else "⚠️" if total_stock > 0 else "❌"
                    response += f"{status_emoji} **{category['category']}**: {total_stock} unidades\n"

            # Productos con stock bajo
            low_stock = await self.product_service.get_low_stock_products()
            if low_stock:
                response += "\n⚠️ **Últimas unidades disponibles:**\n"
                for product in low_stock[:5]:
                    response += f"• {product.name} - Solo {product.stock} unidades\n"

            response += (
                "\n💡 **¿Necesitas algo específico?**\n"
                "Si no tengo stock inmediato, puedo conseguirlo en 24-48hs.\n"
                "También puedes reservar con una seña del 20%."
            )

            return response

        except Exception as e:
            self.logger.error(f"Error in stock inquiry handler: {e}")
            return "📦 Tengo buena disponibilidad en la mayoría de productos. ¿Qué específicamente te interesa?"

    async def _handle_work_inquiry_db(self, message_lower: str, customer: Customer) -> str:
        """Maneja consultas sobre equipos de trabajo"""
        print(f"Mensaje en lower: {message_lower}")
        print(f"Customer: {customer}")
        try:
            work_laptops = await self.product_service.get_products_by_category("laptops", "work", limit=4)
            work_desktops = await self.product_service.get_products_by_category("desktops", "work", limit=3)

            response = "👔 **Equipos Empresariales Disponibles:**\n\n"

            if work_laptops:
                response += "**💻 Laptops Empresariales:**\n"
                for laptop in work_laptops:
                    response += f"• **{laptop.name}** - ${laptop.price:,.0f}\n"
                    response += f"  📋 {laptop.specs}\n"
                    response += f"  📦 Stock: {laptop.stock} unidades\n\n"

            if work_desktops:
                response += "**🖥️ PCs de Escritorio:**\n"
                for desktop in work_desktops:
                    response += f"• **{desktop.name}** - ${desktop.price:,.0f}\n"
                    response += f"  📋 {desktop.specs}\n"
                    response += f"  📦 Stock: {desktop.stock} unidades\n\n"

            # Promociones empresariales
            promotions = await self.product_service.get_active_promotions()
            business_promos = [
                p
                for p in promotions
                if any(word in p.name.lower() for word in ["office", "business", "empresa", "oficina"])
            ]

            if business_promos:
                response += "🔥 **¡OFERTAS EMPRESARIALES!**\n"
                for promo in business_promos:
                    discount = promo.discount_percentage or promo.discount_amount
                    response += f"• {promo.name} - {discount}% OFF\n"

            response += "\n¿Cuántos equipos necesitas? ¿Requieren software específico?"
            return response

        except Exception as e:
            self.logger.error(f"Error in work inquiry handler: {e}")
            return "👔 Tengo excelentes equipos para empresas. ¿Cuántos equipos necesitas?"

    async def _handle_farewell_db(self, customer: Customer) -> str:
        """Mensaje de despedida personalizado"""
        name = customer.profile_name or "amigo/a"

        return (
            f"¡Ha sido un placer ayudarte, {name}! 😊\n\n"
            f"📞 **Recuerda que estoy disponible 24/7 en {BUSINESS_NAME}:**\n"
            "• Cotizaciones personalizadas\n"
            "• Consultas técnicas\n"
            "• Verificar stock y precios\n"
            "• Información sobre garantías\n\n"
            "🚚 **Envíos a todo el país**\n"
            "🛡️ **Garantía oficial en todos los productos**\n\n"
            "¡Que tengas un excelente día! 🚀"
        )

    async def _handle_general_response_db(self, customer: Customer) -> str:
        """Respuesta general con información de la base de datos"""
        print(f"Customer: {customer}")
        try:
            categories = await self.product_service.get_categories_with_counts()
            featured_products = await self.product_service.get_featured_products(limit=3)

            response = f"¡Hola! Soy tu asesor personal de **{BUSINESS_NAME}** 🖥️\n\n"

            # Mostrar categorías principales
            response += "📋 **Categorías disponibles:**\n"
            for category in categories[:4]:
                response += f"• **{category['display_name']}** - {category['product_count']} productos "
                response += f"desde ${category['min_price']:,.0f}\n"

            # Productos destacados
            if featured_products:
                response += "\n⭐ **Productos destacados:**\n"
                for product in featured_products:
                    response += f"• {product.name} - ${product.price:,.0f}\n"

            response += "\n💬 ¿Qué tipo de equipo te interesa? ¿Gaming, trabajo, o tienes algo específico en mente?"
            return response

        except Exception as e:
            self.logger.error(f"Error in general response handler: {e}")
            return "¡Hola! Soy tu asesor personal en tecnología 🖥️\n¿En qué puedo ayudarte hoy?"

    async def _get_or_create_conversation(self, user_number: str) -> ConversationHistory:
        """Obtiene o crea una nueva conversación"""
        conversation_key = f"conversation:{user_number}"
        conversation = self.redis_repo.get(conversation_key)

        if conversation is None:
            self.logger.info(f"Creando nueva conversación para {user_number}")
            conversation = ConversationHistory(user_id=user_number)
        else:
            self.logger.debug(f"Recuperando conversación existente para {user_number}")

        return conversation

    async def _save_conversation(self, user_number: str, conversation: ConversationHistory) -> bool:
        """Guarda la conversación en Redis"""
        conversation_key = f"conversation:{user_number}"
        success = self.redis_repo.set(conversation_key, conversation, expiration=CONVERSATION_EXPIRATION)

        if success:
            self.logger.debug(f"Conversación guardada para {user_number}")
        else:
            self.logger.error(f"Error al guardar conversación para {user_number}")

        return success

    async def _send_whatsapp_response(self, user_number: str, message: str) -> bool:
        """Envía la respuesta por WhatsApp"""
        try:
            response = await self.whatsapp_service.enviar_mensaje_texto(user_number, message)

            if response.get("success", True):  # Asumir éxito si no se especifica
                self.logger.info(f"Mensaje enviado exitosamente a {user_number}")
                return True
            else:
                self.logger.error(f"Error enviando mensaje a {user_number}: {response.get('error')}")
                return False

        except Exception as e:
            self.logger.error(f"Excepción al enviar mensaje a {user_number}: {e}")
            return False

    def _extract_message_text(self, message: WhatsAppMessage) -> str:
        """
        Extrae el texto del mensaje según su tipo
        """
        try:
            if message.type == "text" and message.text:
                return message.text.body
            elif message.type == "interactive" and message.interactive:
                if message.interactive.type == "button_reply" and message.interactive.button_reply:
                    return message.interactive.button_reply.title
                elif message.interactive.type == "list_reply" and message.interactive.list_reply:
                    return message.interactive.list_reply.title

            # Si no podemos extraer el texto, registrar el tipo de mensaje
            self.logger.warning(f"No se pudo extraer texto del mensaje tipo: {message.type}")
            return ""

        except Exception as e:
            self.logger.error(f"Error extrayendo texto del mensaje: {e}")
            return ""

    async def get_conversation_stats(self, user_number: str) -> Optional[dict]:
        """Obtiene estadísticas de la conversación"""
        try:
            conversation_key = f"conversation:{user_number}"
            conversation = self.redis_repo.get(conversation_key)

            if not conversation:
                return None

            return {
                "user_id": conversation.user_id,
                "total_messages": len(conversation.messages),
                "user_messages": len([msg for msg in conversation.messages if msg.role == "persona"]),
                "bot_messages": len([msg for msg in conversation.messages if msg.role == "bot"]),
                "created_at": conversation.created_at.isoformat(),
                "updated_at": conversation.updated_at.isoformat(),
                "summary": conversation.get_conversation_summary(),
            }

        except Exception as e:
            self.logger.error(f"Error obteniendo estadísticas para {user_number}: {e}")
            return None

    async def get_sales_insights(self, user_number: str) -> Optional[dict]:
        """
        Analiza la conversación para obtener insights de ventas
        """
        try:
            conversation_key = f"conversation:{user_number}"
            conversation = self.redis_repo.get(conversation_key)

            if not conversation:
                return None

            # Analizar mensajes del usuario para detectar intención de compra
            user_messages = [msg.content.lower() for msg in conversation.messages if msg.role == "persona"]

            insights = {
                "interest_level": "low",
                "product_interests": [],
                "price_sensitive": False,
                "ready_to_buy": False,
                "technical_level": "beginner",
            }

            # Detectar nivel de interés
            buy_signals = ["comprar", "compra", "precio", "cuando", "disponible", "quiero"]
            if any(signal in " ".join(user_messages) for signal in buy_signals):
                insights["interest_level"] = (
                    "high" if len([m for m in user_messages if any(s in m for s in buy_signals)]) > 2 else "medium"
                )

            # Detectar sensibilidad al precio
            price_keywords = ["barato", "descuento", "oferta", "precio", "costo"]
            insights["price_sensitive"] = any(keyword in " ".join(user_messages) for keyword in price_keywords)

            # Detectar productos de interés
            for category, keywords in KEYWORDS.items():
                if category in ["computadoras", "gaming", "componentes", "software"]:
                    if any(keyword in " ".join(user_messages) for keyword in keywords):
                        insights["product_interests"].append(category)

            return insights

        except Exception as e:
            self.logger.error(f"Error obteniendo insights para {user_number}: {e}")
            return None
