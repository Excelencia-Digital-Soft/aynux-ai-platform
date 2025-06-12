"""
Sistema de routing e interpretación de intenciones
"""

import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

from app.agents.langgraph_system.models import IntentInfo

logger = logging.getLogger(__name__)


class IntentRouter:
    """Router inteligente para dirigir a los agentes correctos"""

    def __init__(self, llm):
        self.llm = llm

        # Patrones de intención mejorados con más variaciones
        self.intent_patterns = {
            "category_browsing": [
                r"mostrar.*categor",
                r"ver.*productos",
                r"qué.*vend",
                r"qué.*tien",
                r"explorar.*tienda",
                r"catálogo",
                r"tipos.*product",
                r"opciones.*dispon",
            ],
            "product_inquiry": [
                r"precio.*producto",
                r"cuánto.*cuest",
                r"valor.*",
                r"característic",
                r"especificacion",
                r"detalles.*",
                r"información.*producto",
                r"stock",
                r"disponib",
                r"hay.*unidad",
                r"quedan.*",
            ],
            "promotions": [
                r"oferta",
                r"descuento",
                r"promocion",
                r"promoción",
                r"rebaja",
                r"ahorro",
                r"sale",
                r"black.*friday",
                r"cyber.*monday",
                r"cupón",
                r"cupon",
                r"código.*descuento",
            ],
            "order_tracking": [
                r"dónde.*pedido",
                r"donde.*pedido",
                r"rastrear",
                r"tracking",
                r"seguimiento",
                r"estado.*envío",
                r"estado.*envio",
                r"cuándo.*llega",
                r"cuando.*llega",
                r"número.*orden",
                r"numero.*orden",
                r"#\d{5,}",
            ],
            "technical_support": [
                r"no.*funciona",
                r"problema",
                r"error",
                r"ayuda.*técnica",
                r"ayuda.*tecnica",
                r"soporte",
                r"falla",
                r"defecto",
                r"roto",
                r"dañado",
                r"danado",
                r"garantía",
                r"garantia",
                r"devol",
                r"cambio",
            ],
            "invoice_request": [
                r"factura",
                r"comprobante",
                r"recibo",
                r"ticket",
                r"documento.*fiscal",
                r"cfdi",
                r"nota.*venta",
                r"constancia.*compra",
            ],
        }

        # Mapeo de intenciones a agentes
        self.agent_mapping = {
            "category_browsing": "category_agent",
            "product_inquiry": "product_agent",
            "promotions": "promotions_agent",
            "order_tracking": "tracking_agent",
            "technical_support": "support_agent",
            "invoice_request": "invoice_agent",
            "general_inquiry": "category_agent",  # Por defecto
        }

        # Intenciones que requieren transferencia humana
        self.human_required_intents = {"complaint", "legal_issue", "payment_problem", "urgent_support"}

    async def analyze_intent(self, state_dict: Dict[str, Any]) -> IntentInfo:
        """Analiza la intención usando múltiples estrategias"""
        last_message = self._get_last_user_message(state_dict)
        if not last_message:
            return IntentInfo(
                primary_intent="general_inquiry", confidence=0.5, target_agent=self.agent_mapping.get("general_inquiry")
            )

        # 1. Intentar con patrones regex (rápido)
        intent, pattern_confidence = self._pattern_matching(last_message)

        # 2. Si no hay match claro o baja confianza, usar LLM
        if not intent or pattern_confidence < 0.7:
            context_summary = self._get_context_summary(state_dict)
            llm_intent, llm_confidence = await self._llm_intent_detection(last_message, context_summary)

            # Combinar resultados
            if llm_confidence > pattern_confidence:
                intent = llm_intent
                confidence = llm_confidence
            else:
                confidence = pattern_confidence
        else:
            confidence = pattern_confidence

        # 3. Extraer entidades relevantes
        entities = await self._extract_entities(last_message, intent)

        # 4. Determinar si requiere handoff
        requires_handoff = self._check_handoff_requirement(
            intent, confidence, state_dict.get("error_count", 0), entities
        )

        # 5. Crear objeto IntentInfo
        intent_info = IntentInfo(
            primary_intent=intent or "general_inquiry",
            confidence=confidence,
            entities=entities,
            requires_handoff=requires_handoff,
            target_agent=self.agent_mapping.get(intent, "category_agent"),
        )

        logger.info(f"Intent detected: {intent_info.primary_intent} (confidence: {intent_info.confidence:.2f})")

        return intent_info

    def _pattern_matching(self, text: str) -> Tuple[Optional[str], float]:
        """Detección rápida basada en patrones regex"""
        text_lower = text.lower().strip()

        # Contar matches por intención
        intent_scores = {}

        for intent, patterns in self.intent_patterns.items():
            score = 0
            matches = 0

            for pattern in patterns:
                if re.search(pattern, text_lower):
                    matches += 1
                    # Dar más peso a matches exactos
                    if re.search(f"\\b{pattern}\\b", text_lower):
                        score += 2
                    else:
                        score += 1

            if matches > 0:
                # Normalizar score por número de patrones
                intent_scores[intent] = score / len(patterns)

        if not intent_scores:
            return None, 0.0

        # Obtener la intención con mayor score
        best_intent = max(intent_scores, key=intent_scores.get)
        confidence = min(intent_scores[best_intent], 0.95)  # Cap at 0.95

        return best_intent, confidence

    async def _llm_intent_detection(self, message: str, context: Dict[str, Any]) -> Tuple[str, float]:
        """Detección de intención usando LLM"""
        try:
            prompt = f"""
Analiza el siguiente mensaje del cliente y clasifícalo en UNA de estas intenciones:

INTENCIONES DISPONIBLES:
- category_browsing: El cliente quiere explorar categorías o ver qué productos hay disponibles
- product_inquiry: Consultas sobre productos específicos, precios, características o stock
- promotions: Búsqueda de ofertas, descuentos o promociones
- order_tracking: Rastreo de pedidos o consultas sobre envíos
- technical_support: Problemas técnicos, garantías o soporte
- invoice_request: Solicitud de facturas o comprobantes
- general_inquiry: Consultas generales que no encajan en las anteriores

CONTEXTO DE LA CONVERSACIÓN:
- Mensajes enviados: {context.get('message_count', 0)}
- Cliente tipo: {context.get('customer_tier', 'basic')}
- Intención previa: {context.get('current_intent', 'ninguna')}

MENSAJE DEL CLIENTE:
"{message}"

Responde ÚNICAMENTE con un JSON válido en este formato exacto:
{{
    "intent": "nombre_de_la_intención",
    "confidence": 0.85,
    "reasoning": "breve explicación de por qué elegiste esta intención"
}}
"""

            response = await self.llm.ainvoke(prompt)

            # Extraer JSON de la respuesta
            json_match = re.search(r"\{.*\}", response.content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                intent = result.get("intent", "general_inquiry")
                confidence = float(result.get("confidence", 0.5))

                # Validar que la intención existe
                if intent not in self.agent_mapping:
                    intent = "general_inquiry"
                    confidence = 0.5

                return intent, confidence

        except Exception as e:
            logger.error(f"Error in LLM intent detection: {e}")

        return "general_inquiry", 0.5

    async def _extract_entities(self, message: str, intent: str) -> Dict[str, Any]:
        """Extrae entidades relevantes del mensaje según la intención"""
        entities = {}
        message_lower = message.lower()

        # Extraer números de orden/tracking
        if intent == "order_tracking":
            # Patrones para diferentes formatos de orden
            order_patterns = [
                r"#(\d{5,})",  # #12345
                r"orden\s*[:‑–—-]?\s*(\d{5,})",  # orden: 12345
                r"pedido\s*[:‑–—-]?\s*(\d{5,})",  # pedido: 12345
                r"tracking\s*[:‑–—-]?\s*([A-Z0-9]{8,})",  # tracking: ABC123XYZ
            ]

            for pattern in order_patterns:
                matches = re.findall(pattern, message, re.IGNORECASE)
                if matches:
                    entities["order_numbers"] = matches
                    break

        # Extraer montos/precios
        price_pattern = r"\$?\s*(\d+(?:[.,]\d{3})*(?:[.,]\d{2})?)"
        price_matches = re.findall(price_pattern, message)
        if price_matches:
            # Convertir a números
            prices = []
            for price in price_matches:
                # Normalizar separadores
                normalized = price.replace(",", "").replace(".", "")
                try:
                    prices.append(float(normalized) / 100 if len(normalized) > 2 else float(normalized))
                except:
                    pass
            if prices:
                entities["price_mentions"] = prices
                entities["budget"] = max(prices)  # Asumir el mayor como presupuesto

        # Extraer marcas mencionadas
        brand_patterns = [
            r"\b(dell|hp|lenovo|asus|acer|apple|samsung|lg|sony|msi|razer)\b",
            r"\b(macbook|thinkpad|pavilion|inspiron|latitude|surface)\b",
        ]
        brands_found = []
        for pattern in brand_patterns:
            matches = re.findall(pattern, message_lower)
            brands_found.extend(matches)
        if brands_found:
            entities["brands"] = list(set(brands_found))

        # Extraer categorías de producto
        product_categories = {
            "laptop": ["laptop", "notebook", "portátil", "portatil"],
            "desktop": ["desktop", "pc", "computadora", "torre"],
            "monitor": ["monitor", "pantalla", "display"],
            "mouse": ["mouse", "ratón", "raton"],
            "keyboard": ["teclado", "keyboard"],
            "printer": ["impresora", "printer"],
            "headphones": ["audífonos", "audifonos", "headphones", "auriculares"],
        }

        categories_found = []
        for category, keywords in product_categories.items():
            for keyword in keywords:
                if keyword in message_lower:
                    categories_found.append(category)
                    break

        if categories_found:
            entities["product_categories"] = list(set(categories_found))

        # Extraer especificaciones técnicas
        tech_specs = {}

        # RAM
        ram_match = re.search(r"(\d+)\s*gb\s*(?:de\s*)?ram", message_lower)
        if ram_match:
            tech_specs["ram_gb"] = int(ram_match.group(1))

        # Almacenamiento
        storage_match = re.search(r"(\d+)\s*(?:gb|tb)\s*(?:ssd|hdd|disco)", message_lower)
        if storage_match:
            size = storage_match.group(1)
            unit = "tb" if "tb" in storage_match.group(0) else "gb"
            tech_specs["storage"] = f"{size}{unit}"

        # Procesador
        cpu_patterns = [r"(i[357]|ryzen\s*[357]|core\s*i[357])", r"(intel|amd)\s*(\w+)?"]
        for pattern in cpu_patterns:
            cpu_match = re.search(pattern, message_lower)
            if cpu_match:
                tech_specs["processor"] = cpu_match.group(0)
                break

        if tech_specs:
            entities["technical_specs"] = tech_specs

        # Extraer urgencia
        urgency_keywords = ["urgente", "hoy", "ahora", "inmediato", "rápido", "rapido", "ya"]
        if any(keyword in message_lower for keyword in urgency_keywords):
            entities["urgency"] = "high"

        return entities

    def _check_handoff_requirement(
        self, intent: str, confidence: float, error_count: int, entities: Dict[str, Any]
    ) -> bool:
        """Determina si se requiere transferencia a humano"""
        # Transferir si hay muchos errores
        if error_count >= 3:
            return True

        # Transferir si la confianza es muy baja
        if confidence < 0.4:
            return True

        # Transferir para intenciones específicas
        if intent in self.human_required_intents:
            return True

        # Transferir si detectamos urgencia alta en soporte
        if intent == "technical_support" and entities.get("urgency") == "high":
            return True

        # Transferir si hay palabras clave de problemas serios
        serious_keywords = ["fraude", "estafa", "robo", "demanda", "legal", "abogado", "denuncia", "peligro", "urgente"]

        message = entities.get("original_message", "").lower()
        if any(keyword in message for keyword in serious_keywords):
            return True

        return False

    def _get_last_user_message(self, state_dict: Dict[str, Any]) -> Optional[str]:
        """Obtiene el último mensaje del usuario desde el diccionario"""
        messages = state_dict.get("messages", [])
        for message in reversed(messages):
            if hasattr(message, "type") and message.type == "human":
                return message.content
        return None

    def _get_context_summary(self, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Obtiene un resumen del contexto desde el diccionario"""
        return {
            "message_count": len(state_dict.get("messages", [])),
            "current_intent": (
                state_dict.get("current_intent", {}).get("primary_intent") if state_dict.get("current_intent") else None
            ),
            "customer_tier": (
                state_dict.get("customer", {}).get("tier", "basic") if state_dict.get("customer") else "basic"
            ),
            "agent_history": state_dict.get("agent_history", []),
            "error_count": state_dict.get("error_count", 0),
        }


class SupervisorAgent:
    """Agente supervisor que coordina el flujo entre agentes"""

    def __init__(self, router: IntentRouter):
        self.router = router
        self.max_agent_switches = 5  # Límite de cambios entre agentes

    async def process(self, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Procesa el estado y determina el siguiente paso"""
        try:
            # Trabajar directamente con el diccionario
            # Verificar si necesita transferencia humana
            needs_handoff = (
                state_dict.get("requires_human", False)
                or state_dict.get("error_count", 0) >= state_dict.get("max_errors", 3)
                or (state_dict.get("current_intent") and state_dict["current_intent"].get("requires_handoff", False))
                or (len(state_dict.get("messages", [])) > 20 and not state_dict.get("is_complete", False))
            )

            if needs_handoff:
                logger.info("Transferring to human agent")
                state_dict["requires_human"] = True
                state_dict["current_agent"] = "human_agent"
                return state_dict

            # Verificar si ya completamos
            if state_dict.get("is_complete", False):
                logger.info("Conversation marked as complete")
                return state_dict

            # Analizar intención del último mensaje usando el diccionario
            intent_info = await self.router.analyze_intent(state_dict)

            # Actualizar intención en el diccionario
            if state_dict.get("current_intent"):
                if "intent_history" not in state_dict:
                    state_dict["intent_history"] = []
                state_dict["intent_history"].append(state_dict["current_intent"])
            state_dict["current_intent"] = intent_info.model_dump()

            # Verificar límite de cambios de agente
            agent_history = state_dict.get("agent_history", [])
            if len(agent_history) >= self.max_agent_switches:
                logger.warning("Max agent switches reached, transferring to human")
                state_dict["requires_human"] = True
                state_dict["current_agent"] = "human_agent"
                return state_dict

            # Determinar siguiente agente basado en la intención
            if intent_info.requires_handoff:
                state_dict["requires_human"] = True
                state_dict["current_agent"] = "human_agent"
            else:
                next_agent = intent_info.target_agent or "category_agent"

                # Actualizar agente actual y historial
                state_dict["current_agent"] = next_agent
                if next_agent not in agent_history:
                    agent_history.append(next_agent)
                    state_dict["agent_history"] = agent_history

                logger.info(f"Routing to {next_agent}")

            return state_dict

        except Exception as e:
            logger.error(f"Error in supervisor processing: {e}")

            # Incrementar error count
            error_count = state_dict.get("error_count", 0) + 1
            state_dict["error_count"] = error_count

            # En caso de error, intentar con agente de categorías
            state_dict["current_agent"] = "category_agent"
            agent_history = state_dict.get("agent_history", [])
            if "category_agent" not in agent_history:
                agent_history.append("category_agent")
                state_dict["agent_history"] = agent_history

            return state_dict

    def should_continue(self, state_dict: Dict[str, Any]) -> bool:
        """Determina si debe continuar el procesamiento"""
        if state_dict.get("requires_human", False):
            return False

        if state_dict.get("is_complete", False):
            return False

        error_count = state_dict.get("error_count", 0)
        max_errors = state_dict.get("max_errors", 3)
        if error_count >= max_errors:
            return False

        # Continuar si hay mensajes sin procesar
        messages = state_dict.get("messages", [])
        agent_responses = state_dict.get("agent_responses", [])
        
        return len(messages) > len(agent_responses)
