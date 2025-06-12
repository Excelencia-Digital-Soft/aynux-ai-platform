"""
Router inteligente que usa IA para detectar intenciones y enrutar conversaciones
"""

import json
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class IntentRouter:
    """
    Router que determina la intención del usuario y dirige al agente apropiado.
    """

    def __init__(self, ollama=None, config: Optional[Dict[str, Any]] = None):
        self.ollama = ollama
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # Configuración
        self.confidence_threshold = self.config.get("confidence_threshold", 0.75)
        self.fallback_agent = self.config.get("fallback_agent", "support_agent")

    def determine_intent(
        self,
        message: str,
        customer_data: Optional[Dict[str, Any]] = None,
        conversation_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Determina la intención del usuario y el agente objetivo.

        Args:
            message: Mensaje del usuario
            customer_data: Datos del cliente (opcional)
            conversation_data: Datos de conversación (opcional)

        Returns:
            Diccionario con información de intención
        """
        try:
            # Normalizar mensaje
            message_lower = message.lower().strip()

            # Detectar intención usando patrones
            detected_intent = self._detect_intent_with_patterns(message_lower)

            # Mapear intención a agente
            target_agent = self._map_intent_to_agent(detected_intent["intent"])

            # Extraer entidades
            entities = self._extract_entities(message, detected_intent["intent"])

            return {
                "primary_intent": detected_intent["intent"],
                "confidence": detected_intent["confidence"],
                "entities": entities,
                "requires_handoff": False,
                "target_agent": target_agent,
            }

        except Exception as e:
            self.logger.error(f"Error determining intent: {str(e)}")

            # Fallback a agente de soporte
            return {
                "primary_intent": "support",
                "confidence": 0.5,
                "entities": {},
                "requires_handoff": False,
                "target_agent": self.fallback_agent,
            }

    def _detect_intent_with_patterns(self, message: str) -> Dict[str, Any]:
        """Detección usando patrones predefinidos con matching más flexible"""
        message_lower = message.lower()

        # Patrones mejorados para detectar intenciones
        patterns = {
            "producto": {
                "keywords": ["laptop", "computadora", "pc", "teléfono", "celular", "tablet", "precio", "cuánto", "cuesta", "disponible", "stock", "características", "especificaciones", "gaming", "diseño"],
                "confidence": 0.9,
            },
            "seguimiento": {
                "keywords": ["pedido", "orden", "envío", "tracking", "rastreo", "dónde", "donde", "está", "llega", "entrega", "#", "número"],
                "confidence": 0.9,
            },
            "soporte": {
                "keywords": ["problema", "error", "no funciona", "no enciende", "soporte", "asistencia", "ayuda", "devolución", "garantía", "roto", "dañado"],
                "confidence": 0.85,
            },
            "facturacion": {
                "keywords": ["factura", "pago", "cobro", "invoice", "billing", "tarjeta", "transferencia", "crédito", "débito"],
                "confidence": 0.9
            },
            "promociones": {
                "keywords": ["oferta", "descuento", "promoción", "sale", "barato", "cupón", "código", "estudiante", "rebaja"],
                "confidence": 0.85
            },
            "categoria": {
                "keywords": ["categoría", "tipos", "qué tienen", "qué ofreces", "opciones", "catálogo", "productos", "hola"],
                "confidence": 0.8
            },
        }

        best_intent = "categoria"  # Por defecto categoria en lugar de general
        best_confidence = 0.3  # Umbral más bajo

        intent_scores = {}
        
        for intent, pattern_data in patterns.items():
            score = 0
            matches = 0
            
            for keyword in pattern_data["keywords"]:
                if keyword in message_lower:
                    matches += 1
                    # Dar más peso a matches exactos de palabras
                    if f" {keyword} " in f" {message_lower} " or message_lower.startswith(keyword) or message_lower.endswith(keyword):
                        score += 2
                    else:
                        score += 1
            
            if matches > 0:
                # Calcular confianza basada en cantidad y calidad de matches
                base_confidence = min((score / len(pattern_data["keywords"])) * pattern_data["confidence"], 0.95)
                # Bonus por múltiples matches
                if matches > 1:
                    base_confidence = min(base_confidence * 1.2, 0.95)
                
                intent_scores[intent] = base_confidence

        # Encontrar la mejor intención
        if intent_scores:
            best_intent = max(intent_scores, key=intent_scores.get)
            best_confidence = intent_scores[best_intent]

        # Logging para debugging
        logger.info(f"Intent detection for '{message}': {best_intent} (confidence: {best_confidence:.2f})")
        if intent_scores:
            logger.debug(f"All intent scores: {intent_scores}")

        return {"intent": best_intent, "confidence": best_confidence}

    def _extract_entities(self, message: str, intent: str) -> Dict[str, Any]:
        """Extrae entidades del mensaje basándose en la intención"""
        entities = {}

        # Extraer números (posibles precios, cantidades, IDs)
        numbers = re.findall(r"\d+(?:\.\d+)?", message)
        if numbers:
            entities["numbers"] = numbers

        # Extraer menciones de productos
        product_terms = ["laptop", "teléfono", "celular", "computadora", "tablet", "iphone", "samsung"]
        found_products = [term for term in product_terms if term in message.lower()]
        if found_products:
            entities["product_mentions"] = found_products

        # Extraer números de orden para seguimiento
        if intent == "seguimiento":
            order_pattern = re.findall(r"#?\d{6,}", message)
            if order_pattern:
                entities["order_numbers"] = order_pattern

        return entities

    async def analyze_intent_with_llm(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Usa LLM para análisis profundo de intención cuando sea necesario"""
        if not self.ollama:
            return self.determine_intent(message)

        system_prompt = """
        Eres un experto en análisis de intenciones para un chatbot de e-commerce.
        
        INTENCIONES DISPONIBLES:
        - producto: Búsqueda, información o comparación de productos
        - soporte: Problemas técnicos, errores, asistencia
        - seguimiento: Estado de órdenes, envíos, tracking
        - facturacion: Consultas sobre pagos, facturas, cobros
        - promociones: Ofertas, descuentos, promociones especiales
        - categoria: Información sobre categorías de productos
        - general: Consultas generales
        
        Analiza el mensaje y responde con un JSON válido.
        """

        user_prompt = f"""
        Analiza este mensaje: "{message}"
        
        Responde SOLO con JSON:
        {{
            "intent": "nombre_intencion",
            "confidence": 0.85,
            "entities": {{}},
            "reasoning": "explicación breve"
        }}
        """

        try:
            response = await self.ollama.generate_response(
                system_prompt=system_prompt, user_prompt=user_prompt, model="llama3.1:8b", temperature=0.1
            )

            result = json.loads(response)
            return {
                "primary_intent": result["intent"],
                "confidence": result["confidence"],
                "entities": result.get("entities", {}),
                "requires_handoff": False,
                "target_agent": self._map_intent_to_agent(result["intent"]),
            }
        except Exception as e:
            logger.error(f"Error in LLM analysis: {e}")
            return self.determine_intent(message)

    def _map_intent_to_agent(self, intent: str) -> str:
        """Mapea intenciones a agentes específicos"""
        mapping = {
            "producto": "product_agent",
            "soporte": "support_agent", 
            "seguimiento": "tracking_agent",
            "facturacion": "invoice_agent",
            "promociones": "promotions_agent",
            "categoria": "category_agent",
            "general": "category_agent",
        }
        
        agent = mapping.get(intent, "category_agent")
        logger.info(f"Mapping intent '{intent}' to agent '{agent}'")
        return agent
