"""
Router inteligente que usa IA para detectar intenciones y enrutar conversaciones
"""

import json
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.agents.langgraph_system.integrations.chroma_integration import ChromaDBIntegration
from app.agents.langgraph_system.integrations.ollama_integration import OllamaIntegration
from app.agents.langgraph_system.models import IntentInfo, SharedState

logger = logging.getLogger(__name__)


class IntentPattern(BaseModel):
    """Patrón de intención para detección rápida"""

    intent: str
    keywords: List[str]
    patterns: List[str]
    confidence_boost: float = 0.1


class IntentRouter:
    """Router inteligente que combina patrones y IA para detectar intenciones"""

    def __init__(self, ollama: OllamaIntegration, vector_store: ChromaDBIntegration):
        self.ollama = ollama
        self.vector_store = vector_store

        # Patrones rápidos para detección inicial
        self.quick_patterns = [
            IntentPattern(
                intent="consulta_producto",
                keywords=["producto", "precio", "stock", "disponible", "comprar"],
                patterns=["quiero comprar", "cuánto cuesta", "tienen disponible"],
            ),
            IntentPattern(
                intent="soporte_tecnico",
                keywords=["error", "problema", "no funciona", "ayuda", "soporte"],
                patterns=["tengo un problema", "no puedo", "error al"],
            ),
            IntentPattern(
                intent="seguimiento_pedido",
                keywords=["pedido", "orden", "envío", "tracking", "entrega"],
                patterns=["dónde está mi", "cuándo llega", "estado del pedido"],
            ),
            IntentPattern(
                intent="facturacion",
                keywords=["factura", "pago", "cobro", "tarjeta", "billing"],
                patterns=["mi factura", "cobro incorrecto", "problema de pago"],
            ),
            IntentPattern(
                intent="promociones",
                keywords=["oferta", "descuento", "promoción", "rebaja", "sale"],
                patterns=["hay ofertas", "descuentos disponibles", "promociones"],
            ),
        ]

    async def analyze_intent(self, state: SharedState) -> IntentInfo:
        """Analiza la intención del usuario usando múltiples estrategias"""
        user_message = state.get_last_user_message()
        if not user_message:
            return self._create_unknown_intent()

        # Estrategia 1: Detección rápida por patrones
        quick_result = await self._quick_pattern_detection(user_message)
        if quick_result and quick_result.confidence > 0.8:
            logger.info(f"Quick pattern match: {quick_result.primary_intent}")
            return quick_result

        # Estrategia 2: Búsqueda vectorial para contexto
        context_result = await self._vector_search_context(user_message, state)

        # Estrategia 3: Análisis con LLM para casos complejos
        llm_result = await self._llm_intent_analysis(user_message, state, context_result)

        # Combinar resultados y seleccionar el mejor
        final_intent = await self._combine_intent_results(quick_result, context_result, llm_result)

        logger.info(f"Final intent: {final_intent.primary_intent} (confidence: {final_intent.confidence})")
        return final_intent

    async def _quick_pattern_detection(self, message: str) -> Optional[IntentInfo]:
        """Detección rápida usando patrones predefinidos"""
        message_lower = message.lower()
        best_match = None
        best_score = 0.0

        for pattern in self.quick_patterns:
            score = 0.0

            # Puntaje por keywords
            keyword_matches = sum(1 for keyword in pattern.keywords if keyword in message_lower)
            if keyword_matches > 0:
                score += (keyword_matches / len(pattern.keywords)) * 0.6

            # Puntaje por patrones exactos
            pattern_matches = sum(1 for p in pattern.patterns if p in message_lower)
            if pattern_matches > 0:
                score += (pattern_matches / len(pattern.patterns)) * 0.4

            # Boost adicional
            score += pattern.confidence_boost

            if score > best_score:
                best_score = score
                best_match = pattern

        if best_match and best_score > 0.3:
            return IntentInfo(
                primary_intent=best_match.intent,
                confidence=min(best_score, 0.95),  # Cap confidence para pattern matching
                entities=self._extract_basic_entities(message, best_match),
                target_agent=self._map_intent_to_agent(best_match.intent),
            )

        return None

    async def _vector_search_context(self, message: str, state: SharedState) -> Dict[str, Any]:
        """Busca contexto relevante usando búsqueda vectorial"""
        try:
            # Buscar conversaciones similares
            similar_conversations = await self.vector_store.similarity_search(
                query=message, collection_name="conversation_examples", n_results=3
            )

            # Buscar documentos de knowledge base
            knowledge_docs = await self.vector_store.similarity_search(
                query=message, collection_name="knowledge_base", n_results=5
            )

            return {
                "similar_conversations": similar_conversations,
                "knowledge_docs": knowledge_docs,
                "context_available": len(similar_conversations) > 0 or len(knowledge_docs) > 0,
            }

        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return {"context_available": False}

    async def _llm_intent_analysis(self, message: str, state: SharedState, context: Dict) -> IntentInfo:
        """Usa LLM para análisis profundo de intención"""

        # Construir prompt inteligente
        system_prompt = self._build_intent_analysis_prompt(state, context)

        user_prompt = f"""
        Analiza este mensaje del usuario y determina su intención:
        
        Mensaje: "{message}"
        
        Responde SOLO con un JSON válido en este formato:
        {{
            "primary_intent": "nombre_de_la_intencion",
            "confidence": 0.85,
            "entities": {{"entity_type": ["values"]}},
            "requires_handoff": false,
            "reasoning": "breve explicación"
        }}
        """

        try:
            response = await self.ollama.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model="llama3.1:8b",
                temperature=0.1,  # Baja temperatura para respuestas consistentes
            )

            # Parse JSON response
            result_data = json.loads(response)

            return IntentInfo(
                primary_intent=result_data["primary_intent"],
                confidence=result_data["confidence"],
                entities=result_data.get("entities", {}),
                requires_handoff=result_data.get("requires_handoff", False),
                target_agent=self._map_intent_to_agent(result_data["primary_intent"]),
            )

        except Exception as e:
            logger.error(f"Error in LLM intent analysis: {e}")
            return self._create_unknown_intent()

    def _build_intent_analysis_prompt(self, state: SharedState, context: Dict) -> str:
        """Construye prompt contextual para análisis de intención"""

        base_prompt = """
        Eres un experto en análisis de intenciones para un chatbot de e-commerce.
        
        INTENCIONES DISPONIBLES:
        - consulta_producto: Búsqueda, información o comparación de productos
        - soporte_tecnico: Problemas técnicos, errores, asistencia
        - seguimiento_pedido: Estado de órdenes, envíos, tracking
        - facturacion: Consultas sobre pagos, facturas, cobros
        - promociones: Ofertas, descuentos, promociones especiales
        - informacion_general: Información sobre la empresa, políticas, etc.
        - escalation: Casos complejos que requieren intervención humana
        
        REGLAS:
        1. Analiza el contexto completo, no solo palabras clave
        2. Considera el historial de conversación si está disponible
        3. Asigna confianza alta (>0.8) solo si estás muy seguro
        4. Para casos ambiguos, usa confidence media (0.5-0.7)
        5. Extrae entidades relevantes cuando sea posible
        6. Marca requires_handoff=true para casos muy complejos o emocionales
        """

        # Añadir contexto de conversación
        if state.conversation and state.messages:
            recent_messages = state.messages[-3:]  # Últimos 3 mensajes
            conversation_context = "\n".join([f"- {msg.content}" for msg in recent_messages])
            base_prompt += f"\n\nCONTEXTO DE CONVERSACIÓN RECIENTE:\n{conversation_context}"

        # Añadir contexto del cliente
        if state.customer:
            customer_context = f"""
            INFORMACIÓN DEL CLIENTE:
            - Tier: {state.customer.tier}
            - Historial de compras: {len(state.customer.purchase_history)} compras anteriores
            """
            base_prompt += customer_context

        # Añadir contexto vectorial si está disponible
        if context.get("context_available"):
            base_prompt += "\n\nSe encontró contexto relevante en la base de conocimientos."

        return base_prompt

    async def _combine_intent_results(
        self, quick: Optional[IntentInfo], vector_context: Dict, llm: IntentInfo
    ) -> IntentInfo:
        """Combina resultados de diferentes estrategias para obtener el mejor"""

        # Si quick pattern tiene alta confianza, usarlo
        if quick and quick.confidence > 0.85:
            return quick

        # Si LLM tiene alta confianza, usarlo
        if llm.confidence > 0.8:
            return llm

        # Si quick pattern y LLM coinciden, boost confidence
        if quick and quick.primary_intent == llm.primary_intent:
            combined_confidence = min((quick.confidence + llm.confidence) / 2 + 0.1, 0.95)
            return IntentInfo(
                primary_intent=llm.primary_intent,
                confidence=combined_confidence,
                entities={**quick.entities, **llm.entities},
                requires_handoff=llm.requires_handoff,
                target_agent=llm.target_agent,
            )

        # Default: usar resultado de LLM
        return llm

    def _extract_basic_entities(self, message: str, pattern: IntentPattern) -> Dict[str, Any]:
        """Extrae entidades básicas del mensaje"""
        entities = {}

        # Extraer números (posibles precios, cantidades, IDs)
        import re

        numbers = re.findall(r"\d+(?:\.\d+)?", message)
        if numbers:
            entities["numbers"] = numbers

        # Extraer menciones de productos comunes
        product_terms = ["laptop", "teléfono", "celular", "computadora", "tablet"]
        found_products = [term for term in product_terms if term in message.lower()]
        if found_products:
            entities["product_mentions"] = found_products

        return entities

    def _map_intent_to_agent(self, intent: str) -> str:
        """Mapea intenciones a agentes específicos"""
        mapping = {
            "consulta_producto": "product_agent",
            "soporte_tecnico": "support_agent",
            "seguimiento_pedido": "tracking_agent",
            "facturacion": "invoice_agent",
            "promociones": "promotions_agent",
            "informacion_general": "category_agent",
            "escalation": "support_agent",
        }
        return mapping.get(intent, "category_agent")

    def _create_unknown_intent(self) -> IntentInfo:
        """Crea intención desconocida como fallback"""
        return IntentInfo(
            primary_intent="unknown", confidence=0.0, entities={}, requires_handoff=False, target_agent="category_agent"
        )
