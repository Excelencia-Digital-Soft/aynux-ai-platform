import logging
import re
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from psycopg2.errors import UndefinedTable
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.agents import (
    DoubtsAgent,
    GreetingAgent,
    ProductInquiryAgent,
    PromotionsAgent,
    RecommendationAgent,
    SalesAgent,
    StockAgent,
    UnknownAgent,
)
from app.config.settings import get_settings
from app.database import check_db_connection, get_db_context
from app.models.chatbot import UserIntent
from app.models.conversation import ConversationHistory
from app.models.database import Conversation, Customer, Message, Product
from app.models.message import BotResponse, Contact, WhatsAppMessage
from app.repositories.redis_repository import RedisRepository
from app.services.ai_service import AIService
from app.services.customer_service import CustomerService
from app.services.product_service import ProductService
from app.services.prompt_service import PromptService
from app.services.whatsapp_service import WhatsAppService
from app.utils.certificate_utils import CertificateGenerator

# Configurar expiración de conversación (24 horas)
CONVERSATION_EXPIRATION = 86400  # 24 horas en segundos

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
        self.prompt_service = PromptService()
        self.customer_service = CustomerService()
        self.certificate_generator = CertificateGenerator()

        # Estado de la base de datos
        self._db_available = None

        # Inicializar agentes
        self._init_agents()

    async def _check_database_health(self) -> bool:
        """Verifica si la base de datos está disponible y saludable"""
        if self._db_available is None:
            self._db_available = await check_db_connection()
            if not self._db_available:
                self.logger.warning("Base de datos no disponible, usando modo de respuesta básica")
        return self._db_available

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
        message_text = None

        try:
            # 1. Extraer message_text y validar datos
            user_number = contact.wa_id
            message_text = self._extract_message_text(message)

            if not message_text.strip():
                self.logger.warning(f"Mensaje vacío recibido de {user_number}")
                return BotResponse(status="failure", message="No se pudo procesar el mensaje vacío")

            self.logger.info(f"Procesando mensaje de {user_number}: '{message_text[:50]}...'")

            # 2. Verificar estado de la base de datos
            db_available = await self._check_database_health()

            if not db_available:
                # Modo fallback sin base de datos
                return await self._handle_fallback_mode(message_text, user_number)

            # 3. Obtener o crear cliente (con manejo de errores mejorado)
            customer = await self._safe_get_or_create_customer(user_number, contact.profile.get("name"))

            if not customer:
                # Si falla la creación del cliente, usar modo básico
                self.logger.warning(f"No se pudo crear/obtener cliente para {user_number}, usando modo básico")
                return await self._handle_fallback_mode(message_text, user_number)

            # 4. Buscar historial de conversación
            conversation = await self._get_or_create_conversation(user_number)

            # Añadir mensaje del usuario al historial
            conversation.add_message("persona", message_text)

            # Obtener historial formateado para el contexto
            historial_str = conversation.to_formatted_history()
            self.logger.debug(f"↩️ Historial de conversación para {user_number}: {len(conversation.messages)} mensajes")

            # 5. Detectar intención y generar respuesta usando la base de datos
            intent, confidence = await self._detect_intent(message_text, historial_str)
            bot_response = await self._generate_response_from_db(
                customer, message_text, intent, confidence, historial_str
            )

            # 6. Añadir respuesta del bot al historial
            conversation.add_message("bot", bot_response)

            # 7. Guardar conversación actualizada en Redis
            await self._save_conversation(user_number, conversation)

            # 8. Guardar en base de datos
            db_conversation = await self._get_or_create_db_conversation(customer["id"])
            if db_conversation:
                # Guardar mensaje del usuario
                await self._save_message_to_db(
                    conversation_id=str(db_conversation.id),
                    message_type="user",
                    content=message_text,
                    intent=intent.value if intent else None,
                    confidence=confidence,
                    whatsapp_message_id=message.id if hasattr(message, 'id') else None
                )
                
                # Guardar respuesta del bot
                await self._save_message_to_db(
                    conversation_id=str(db_conversation.id),
                    message_type="bot",
                    content=bot_response
                )

            # 9. Enviar respuesta por WhatsApp
            await self._send_whatsapp_response(user_number, bot_response)

            self.logger.info(f"Mensaje procesado exitosamente para {user_number}")
            return BotResponse(status="success", message=bot_response)

        except (OperationalError, ProgrammingError, UndefinedTable) as db_error:
            # Errores específicos de base de datos
            self.logger.error(f"Error de base de datos para {user_number}: {db_error}")
            self._db_available = False  # Marcar BD como no disponible

            # Intentar respuesta de fallback
            if user_number:
                fallback_response = await self._handle_fallback_mode(message_text or "hola", user_number)
                return fallback_response

            return BotResponse(status="failure", message="Servicio temporalmente no disponible")

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

    async def _handle_fallback_mode(self, message_text: str, user_number: str) -> BotResponse:
        """
        Modo de respuesta básica cuando la base de datos no está disponible
        """
        try:
            self.logger.info(f"Usando modo fallback para {user_number}")

            # Detectar intención básica (sin historial en modo fallback)
            intent, _ = await self._detect_intent(message_text, "")

            # Respuestas predefinidas sin BD
            fallback_responses = {
                UserIntent.SALUDO_Y_NECESIDADES_INICIALES: (
                    f"¡Hola! 👋 Soy tu asesor virtual de **{BUSINESS_NAME}**.\n\n"
                    "Temporalmente estamos experimentando problemas técnicos, pero estaré encantado de ayudarte.\n\n"
                    "¿En qué puedo ayudarte específicamente?"
                ),
                UserIntent.CIERRE_VENTA_PROCESO: (
                    f"¡Gracias por contactar **{BUSINESS_NAME}**! 😊\n\n"
                    "📞 Estamos aquí cuando nos necesites\n"
                    "🛡️ Garantía oficial en todos los productos\n\n"
                    "¡Que tengas un excelente día! 🚀"
                ),
            }

            # Seleccionar respuesta apropiada
            response_text = fallback_responses.get(
                intent, fallback_responses[UserIntent.SALUDO_Y_NECESIDADES_INICIALES]
            )

            # Enviar respuesta
            await self._send_whatsapp_response(user_number, response_text)

            return BotResponse(status="success", message=response_text)

        except Exception as e:
            self.logger.error(f"Error en modo fallback para {user_number}: {e}")
            simple_message = f"¡Hola! Soy el asesor de {BUSINESS_NAME}. "
            simple_message += "Estamos disponibles para ayudarte con cualquier consulta sobre productos tecnológicos. 🖥️"

            try:
                await self._send_whatsapp_response(user_number, simple_message)
            except Exception as error:
                print("Error al enviar respuesta simple", error)
                pass  # Si falla el envío, no hacer nada más

            return BotResponse(status="success", message=simple_message)

    async def _safe_get_or_create_customer(
        self, phone_number: str, profile_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Versión segura de obtención/creación de cliente con manejo de errores"""
        try:
            return await self.customer_service.get_or_create_customer(phone_number, profile_name)
        except (OperationalError, ProgrammingError, UndefinedTable) as db_error:
            self.logger.error(f"Error de BD al obtener cliente {phone_number}: {db_error}")
            self._db_available = False
            return None
        except Exception as e:
            self.logger.error(f"Error general al obtener cliente {phone_number}: {e}")
            return None

    async def _detect_intent(self, message_text: str, historial: str) -> Tuple[UserIntent, float]:
        """
        Detecta la intención del mensaje usando AI

        Returns:
            Tuple con (UserIntent, confianza)
        """
        try:
            # Generar prompt para detección de intención
            full_prompt = self.prompt_service._orquestator_prompt(message_text, historial)

            # Llamar a AI para detectar intención
            intent_response = await self.ai_service._generate_content(prompt=full_prompt, temperature=0.1)

            # Parsear respuesta JSON
            import json

            intent_data = json.loads(intent_response.strip())

            # Obtener intención y confianza
            intent_str = intent_data.get("intent", "NO_RELACIONADO_O_CONFUSO")
            confidence = float(intent_data.get("confidence", 0.5))

            intent = UserIntent(intent_str)

            self.logger.info(f"Intención detectada: {intent.value} con confianza {confidence:.2f}")
            return (intent, confidence)

        except Exception as e:
            self.logger.error(f"Error detectando intención: {e}")
            return (UserIntent.NO_RELACIONADO_O_CONFUSO, 0.0)

    def _init_agents(self):
        """Inicializa todos los agentes"""
        self.agents = {
            UserIntent.SALUDO_Y_NECESIDADES_INICIALES: GreetingAgent(
                self.ai_service, self.product_service, self.customer_service
            ),
            UserIntent.CONSULTA_PRODUCTO_SERVICIO: ProductInquiryAgent(
                self.ai_service, self.product_service, self.customer_service
            ),
            UserIntent.VERIFICACION_STOCK: StockAgent(self.ai_service, self.product_service, self.customer_service),
            UserIntent.PROMOCIONES_DESCUENTOS: PromotionsAgent(
                self.ai_service, self.product_service, self.customer_service
            ),
            UserIntent.SUGERENCIAS_RECOMENDACIONES: RecommendationAgent(
                self.ai_service, self.product_service, self.customer_service
            ),
            UserIntent.MANEJO_DUDAS_OBJECIONES: DoubtsAgent(
                self.ai_service, self.product_service, self.customer_service
            ),
            UserIntent.CIERRE_VENTA_PROCESO: SalesAgent(self.ai_service, self.product_service, self.customer_service),
            UserIntent.NO_RELACIONADO_O_CONFUSO: UnknownAgent(
                self.ai_service, self.product_service, self.customer_service
            ),
        }

    async def _generate_response_from_db(
        self, customer: Dict[str, Any], message_text: str, intent: UserIntent, confidence: float, historial: str
    ) -> str:
        """Genera respuestas usando AI y agentes especializados"""
        try:
            self.logger.info(f"Procesando con agente: {intent.value} (confianza: {confidence:.2f})")

            # Registrar la consulta del cliente
            await self.customer_service.log_product_inquiry(
                customer_id=customer["id"], inquiry_type=intent.value, inquiry_text=message_text
            )

            # Obtener el agente correspondiente a la intención
            agent = self.agents.get(intent)

            if not agent:
                # Si no hay agente, usar el agente desconocido
                agent = self.agents[UserIntent.NO_RELACIONADO_O_CONFUSO]

            # Procesar con el agente
            response = await agent.process(customer, message_text, historial)

            return response

        except (OperationalError, ProgrammingError, UndefinedTable) as db_error:
            # Si falla la BD, usar respuesta básica
            self.logger.error(f"Error de BD en generación de respuesta: {db_error}")
            return (
                f"¡Hola! Gracias por contactar {BUSINESS_NAME}. "
                "Estamos experimentando problemas técnicos temporales, "
                "pero estaré encantado de ayudarte. ¿En qué puedo asistirte?"
            )
        except Exception as e:
            self.logger.error(f"Error generando respuesta: {e}")
            return (
                "Disculpa, tuve un problema al procesar tu mensaje. "
                "¿Podrías reformularlo o decirme en qué necesitas ayuda específicamente?"
            )

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
                    customer_id=str(customer["id"]),
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
        name = customer["profile_name"] or "amigo/a"

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

    async def _get_or_create_db_conversation(self, customer_id: str, session_id: str = None) -> Conversation:
        """Obtiene o crea una conversación en la base de datos"""
        try:
            with get_db_context() as db:
                # Buscar conversación activa (sin ended_at)
                conversation = db.query(Conversation).filter(
                    Conversation.customer_id == customer_id,
                    Conversation.ended_at.is_(None)
                ).order_by(Conversation.started_at.desc()).first()
                
                if not conversation:
                    # Crear nueva conversación
                    conversation = Conversation(
                        customer_id=customer_id,
                        session_id=session_id or f"session_{customer_id}_{datetime.now().timestamp()}"
                    )
                    db.add(conversation)
                    db.commit()
                    db.refresh(conversation)
                    self.logger.info(f"Nueva conversación creada en DB para cliente {customer_id}")
                else:
                    self.logger.debug(f"Conversación existente encontrada en DB para cliente {customer_id}")
                
                return conversation
                
        except Exception as e:
            self.logger.error(f"Error al obtener/crear conversación en DB: {e}")
            return None

    async def _save_message_to_db(
        self, 
        conversation_id: str, 
        message_type: str, 
        content: str, 
        intent: str = None,
        confidence: float = None,
        whatsapp_message_id: str = None
    ) -> bool:
        """Guarda un mensaje en la base de datos"""
        try:
            with get_db_context() as db:
                message = Message(
                    conversation_id=conversation_id,
                    message_type=message_type,
                    content=content,
                    intent=intent,
                    confidence=confidence,
                    whatsapp_message_id=whatsapp_message_id,
                    message_format="text"
                )
                db.add(message)
                
                # Actualizar contadores en la conversación
                conversation = db.query(Conversation).filter_by(id=conversation_id).first()
                if conversation:
                    conversation.total_messages += 1
                    if message_type == "user":
                        conversation.user_messages += 1
                    elif message_type == "bot":
                        conversation.bot_messages += 1
                    
                    # Actualizar intent y updated_at
                    if intent:
                        conversation.intent_detected = intent
                    conversation.updated_at = datetime.now(timezone.utc)
                
                db.commit()
                self.logger.debug(f"Mensaje guardado en DB: {message_type} - {content[:50]}...")
                return True
                
        except Exception as e:
            self.logger.error(f"Error al guardar mensaje en DB: {e}")
            return False

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
