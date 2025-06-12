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
        Determina la intención del usuario y el agente objetivo usando IA.

        Args:
            message: Mensaje del usuario
            customer_data: Datos del cliente (opcional)
            conversation_data: Datos de conversación (opcional)

        Returns:
            Diccionario con información de intención
        """
        try:
            # Si tenemos Ollama disponible, usar análisis con IA
            if self.ollama:
                import asyncio
                result = asyncio.create_task(self.analyze_intent_with_llm(message, {
                    "customer_data": customer_data,
                    "conversation_data": conversation_data
                }))
                # Ejecutar de forma síncrona si estamos en contexto síncrono
                try:
                    return asyncio.get_event_loop().run_until_complete(result)
                except RuntimeError:
                    # Si ya estamos en un loop, crear uno nuevo
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, self.analyze_intent_with_llm(message, {
                            "customer_data": customer_data,
                            "conversation_data": conversation_data
                        }))
                        return future.result()
            
            # Fallback simple si no hay IA disponible
            return self._simple_fallback_detection(message)

        except Exception as e:
            self.logger.error(f"Error determining intent: {str(e)}")
            return self._simple_fallback_detection(message)

    def _simple_fallback_detection(self, message: str) -> Dict[str, Any]:
        """Fallback simple cuando no hay IA disponible"""
        # Fallback muy básico - siempre usar category_agent para empezar
        return {
            "primary_intent": "categoria",
            "confidence": 0.5,
            "entities": {},
            "requires_handoff": False,
            "target_agent": "category_agent",
        }


    async def analyze_intent_with_llm(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Usa LLM para análisis profundo de intención cuando sea necesario"""
        if not self.ollama:
            return self._simple_fallback_detection(message)

        # Construir contexto del cliente y conversación
        customer_context = ""
        if state_dict.get("customer_data"):
            customer_context = f"Cliente: {state_dict['customer_data']}"
        
        conversation_context = ""
        if state_dict.get("conversation_data"):
            conversation_context = f"Conversación previa: {state_dict['conversation_data']}"

        system_prompt = """Eres un asistente de IA experto en análisis de intenciones para un chatbot de e-commerce especializado en tecnología.

INTENCIONES DISPONIBLES:
- producto: Búsqueda, consultas, comparación o información específica de productos (laptops, smartphones, tablets, etc.)
- soporte: Problemas técnicos, errores, devoluciones, garantías, asistencia general
- seguimiento: Estado de pedidos, órdenes, envíos, tracking, información de entrega
- facturacion: Consultas sobre pagos, facturas, métodos de pago, cobros
- promociones: Ofertas, descuentos, cupones, promociones especiales, rebajas
- categoria: Información general sobre categorías de productos, catálogo general
- agradecimiento: Agradecimientos, despedidas, confirmaciones positivas

REGLAS DE ANÁLISIS:
1. Si el usuario menciona un producto específico (laptop, teléfono, etc.) o sus características → "producto"
2. Si pregunta sobre características, precios, disponibilidad de un producto → "producto" 
3. Si dice "necesito", "busco", "quiero" + producto → "producto"
4. Si menciona programación, gaming, trabajo con productos → "producto"
5. Si pregunta sobre pedidos, tracking, envíos → "seguimiento"
6. Si hay problemas, errores, garantías → "soporte"
7. Si pregunta sobre descuentos, ofertas → "promociones"
8. Si es un saludo general o pregunta qué tienen → "categoria"
9. Si agradece o confirma algo → "agradecimiento"

Analiza el mensaje y responde ÚNICAMENTE con JSON válido."""

        user_prompt = f"""
Analiza este mensaje del usuario: "{message}"

{customer_context}
{conversation_context}

Responde SOLO con JSON:
{{
    "intent": "nombre_intencion",
    "confidence": 0.85,
    "entities": {{}},
    "reasoning": "explicación breve de por qué elegiste esta intención"
}}
"""

        try:
            response = await self.ollama.generate_response(
                system_prompt=system_prompt, 
                user_prompt=user_prompt, 
                model=None,  # Use default configured model
                temperature=0.1
            )

            # Limpiar respuesta para extraer solo el JSON
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:-3]
            elif response.startswith("```"):
                response = response[3:-3]
            
            result = json.loads(response)
            
            # Validar que la intención sea válida
            valid_intents = ["producto", "soporte", "seguimiento", "facturacion", "promociones", "categoria", "agradecimiento"]
            if result["intent"] not in valid_intents:
                result["intent"] = "categoria"
                result["confidence"] = 0.5
            
            self.logger.info(f"LLM Intent analysis for '{message}': {result['intent']} (confidence: {result['confidence']:.2f}) - {result.get('reasoning', '')}")
            
            return {
                "primary_intent": result["intent"],
                "confidence": result["confidence"],
                "entities": result.get("entities", {}),
                "requires_handoff": False,
                "target_agent": self._map_intent_to_agent(result["intent"]),
            }
            
        except Exception as e:
            logger.error(f"Error in LLM analysis: {e}")
            return self._simple_fallback_detection(message)

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
