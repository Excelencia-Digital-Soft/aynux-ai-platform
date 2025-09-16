"""
Agente especializado en saludos y presentación de capacidades del sistema
"""

import logging
from typing import Any, Dict, Optional

from app.utils.language_detector import LanguageDetector

from ..integrations.ollama_integration import OllamaIntegration
from ..utils.tracing import trace_async_method
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class GreetingAgent(BaseAgent):
    """Agente especializado en saludos y presentación completa de capacidades del sistema"""

    def __init__(self, ollama=None, postgres=None, config: Optional[Dict[str, Any]] = None):
        super().__init__("greeting_agent", config or {}, ollama=ollama, postgres=postgres)
        self.ollama = ollama or OllamaIntegration()

        # Configuración específica del agente
        self.model = "llama3.2:1b"  # Modelo rápido para saludos
        self.temperature = 0.7  # Un poco de creatividad para respuestas amigables

        # Inicializar detector de idioma
        self.language_detector = LanguageDetector(
            config={"default_language": "es", "supported_languages": ["es", "en", "pt"]}
        )

    @trace_async_method(
        name="greeting_agent_process",
        run_type="chain",
        metadata={"agent_type": "greeting", "model": "llama3.2:1b"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa saludos y proporciona información completa sobre las capacidades del sistema.

        Args:
            message: Mensaje del usuario (saludo)
            state_dict: Estado actual como diccionario

        Returns:
            Diccionario con actualizaciones para el estado
        """
        try:
            # Detectar idioma y generar respuesta personalizada
            response_text = await self._generate_greeting_response(message)

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "is_complete": True,
                "greeting_completed": True,
            }

        except Exception as e:
            logger.error(f"Error in greeting agent: {str(e)}")

            # Respuesta de fallback simple en español
            fallback_response = (
                "¡Hola! 👋 Bienvenido a ConversaShop. "
                "Soy tu asistente de e-commerce y puedo ayudarte con productos, "
                "categorías, promociones, seguimiento de pedidos, soporte técnico, "
                "facturación y análisis de datos. ¿En qué te puedo ayudar hoy?"
            )

            return {
                "messages": [{"role": "assistant", "content": fallback_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
                "is_complete": True,
            }

    async def _generate_greeting_response(self, message: str) -> str:
        """
        Genera respuesta de saludo personalizada usando IA multilingüe.

        Args:
            message: Mensaje del usuario

        Returns:
            Respuesta de saludo con información completa del sistema
        """
        # Detectar idioma usando LanguageDetector
        try:
            detection_result = self.language_detector.detect_language(message)
            detected_language = detection_result["language"]
            confidence = detection_result["confidence"]
            
            logger.info(f"Language detected: {detected_language} (confidence: {confidence:.2f})")
            
        except Exception as e:
            logger.warning(f"Error detecting language: {e}, using default")
            detected_language = "es"
            confidence = 0.5

        # Prompt simplificado ya con idioma detectado
        prompt = f"""# E-COMMERCE GREETING ASSISTANT

## 1. User Message
`"{message}"`

## 2. Detected Language: {detected_language.upper()}
Your response MUST be in {detected_language.upper()} language.

---

## 3. Instructions
You are the friendly greeting agent for **ConversaShop**, an advanced e-commerce chatbot.

### System Capabilities
- **Product Services:** Catalog, stock, pricing, comparisons.
- **Category Management:** Browse and filter by category.
- **Promotions & Offers:** Discounts, coupons, special deals.
- **Order Tracking:** Shipment status and delivery updates.
- **Technical Support:** Troubleshooting and assistance.
- **Billing & Invoicing:** Invoices, payments, refunds.
- **Data & Analytics:** Sales reports and business insights.

### Language-Specific Templates

**For English (en):**
1. **Welcome:** "Hello! 👋 Welcome to ConversaShop."
2. **Introduction:** "I'm your e-commerce assistant."
3. **Capabilities:** Briefly list 3-4 main areas (e.g., "I can help with products, orders, and support.").
4. **Call to Action:** "How can I help you today?"

**For Spanish (es):**
1. **Bienvenida:** "¡Hola! 👋 Bienvenido a ConversaShop."
2. **Introducción:** "Soy tu asistente de e-commerce."
3. **Capacidades:** Menciona 3-4 áreas principales (ej: "Puedo ayudarte con productos, pedidos y soporte.").
4. **Llamada a la Acción:** "¿En qué te puedo ayudar hoy?"

**For Portuguese (pt):**
1. **Boas-vindas:** "Olá! 👋 Bem-vindo ao ConversaShop."
2. **Apresentação:** "Sou seu assistente de e-commerce."
3. **Capacidades:** Mencione 3-4 áreas principais (ex: "Posso ajudar com produtos, pedidos e suporte.").
4. **Chamada para Ação:** "Como posso ajudá-lo hoje?"

---

## 4. Generate Response
Generate a warm, professional, and concise greeting using the template for the detected language ({detected_language.upper()}). Add 1-2 relevant emojis.

Generate your response now:"""

        try:
            llm = self.ollama.get_llm(temperature=self.temperature, model=self.model)
            response = await llm.ainvoke(prompt)

            # Extraer el contenido de la respuesta
            if hasattr(response, "content"):
                content = response.content
                # Manejar content que puede ser string o lista
                if isinstance(content, str):
                    return content.strip()
                elif isinstance(content, list):
                    # Si es lista, unir todos los elementos como texto
                    return " ".join(str(item) for item in content).strip()
                else:
                    return str(content).strip()
            else:
                return str(response).strip()

        except Exception as e:
            logger.error(f"Error generating greeting with AI: {str(e)}")

            # Usar fallback apropiado basado en idioma detectado o detección básica
            try:
                detection_result = self.language_detector.detect_language(message)
                fallback_language = detection_result["language"]
            except Exception:
                # Detección básica como último recurso
                fallback_language = "en" if self._is_english(message) else "es"

            if fallback_language == "en":
                return self._get_fallback_greeting_english()
            elif fallback_language == "pt":
                return self._get_fallback_greeting_portuguese()
            else:
                return self._get_fallback_greeting_spanish()

    def _is_english(self, message: str) -> bool:
        """Detección básica de inglés basada en palabras clave"""
        english_keywords = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in english_keywords)

    def _get_fallback_greeting_spanish(self) -> str:
        """Respuesta de fallback en español"""
        return """¡Hola! 👋 Bienvenido a ConversaShop.

Soy tu asistente inteligente de e-commerce y puedo ayudarte con:

🛍️ **Productos**: Catálogo, stock, precios y especificaciones
📂 **Categorías**: Exploración y navegación por tipos de productos  
🎯 **Promociones**: Descuentos, cupones y ofertas especiales
📦 **Seguimiento**: Estado de pedidos y envíos
🛠️ **Soporte**: Asistencia técnica y resolución de problemas
💰 **Facturación**: Facturas, pagos y reembolsos
📊 **Datos**: Reportes, estadísticas y análisis

¿En qué te puedo ayudar hoy?"""

    def _get_fallback_greeting_english(self) -> str:
        """Respuesta de fallback en inglés"""
        return """Hello! 👋 Welcome to ConversaShop.

I'm your intelligent e-commerce assistant and I can help you with:

🛍️ **Products**: Catalog, stock, pricing and specifications
📂 **Categories**: Product type exploration and navigation
🎯 **Promotions**: Discounts, coupons and special offers  
📦 **Tracking**: Order and shipment status
🛠️ **Support**: Technical assistance and troubleshooting
💰 **Billing**: Invoices, payments and refunds
📊 **Data**: Reports, statistics and analytics

How can I help you today?"""

    def _get_fallback_greeting_portuguese(self) -> str:
        """Respuesta de fallback en portugués"""
        return """Olá! 👋 Bem-vindo ao ConversaShop.

Sou seu assistente inteligente de e-commerce e posso ajudá-lo com:

🛍️ **Produtos**: Catálogo, estoque, preços e especificações
📂 **Categorias**: Exploração e navegação por tipos de produtos  
🎯 **Promoções**: Descontos, cupons e ofertas especiais
📦 **Rastreamento**: Status de pedidos e envios
🛠️ **Suporte**: Assistência técnica e resolução de problemas
💰 **Faturamento**: Faturas, pagamentos e reembolsos
📊 **Dados**: Relatórios, estatísticas e análise

Como posso ajudá-lo hoje?"""

