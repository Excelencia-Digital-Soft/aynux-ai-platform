"""
Router inteligente que usa IA con caché optimizado para detectar intenciones
"""

import hashlib
import json
import logging
import re
import time
from typing import Any, Dict, Optional
from collections import OrderedDict

logger = logging.getLogger(__name__)


class IntentRouter:
    """
    Router optimizado que usa IA con sistema de caché inteligente.
    
    Características:
    - Caché LRU para respuestas de intenciones
    - Optimización de prompts con contexto
    - Métricas de performance y hit rate
    - Fallback robusto sin IA
    """

    def __init__(self, ollama=None, config: Optional[Dict[str, Any]] = None):
        self.ollama = ollama
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # Configuración
        self.confidence_threshold = self.config.get("confidence_threshold", 0.75)
        self.fallback_agent = self.config.get("fallback_agent", "support_agent")
        
        # Sistema de caché inteligente
        self.cache_size = self.config.get("cache_size", 1000)
        self.cache_ttl = self.config.get("cache_ttl", 3600)  # 1 hora
        self._intent_cache = OrderedDict()
        self._cache_timestamps = {}
        
        # Métricas
        self._stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "llm_calls": 0,
            "fallback_calls": 0,
            "avg_response_time": 0.0,
            "total_response_time": 0.0
        }
        
        logger.info(f"IntentRouter initialized with cache_size={self.cache_size}, cache_ttl={self.cache_ttl}s")

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

    def _get_cache_key(self, message: str, context: Dict[str, Any] = None) -> str:
        """Generar clave de caché basada en mensaje y contexto"""
        # Normalizar mensaje para mejor hit rate
        normalized_message = message.lower().strip()
        
        # Incluir contexto relevante en la clave
        context_str = ""
        if context:
            # Solo incluir contexto relevante para evitar cache misses innecesarios
            relevant_context = {
                "language": context.get("language", "es"),
                "user_tier": context.get("customer_data", {}).get("tier", "basic")
            }
            context_str = json.dumps(relevant_context, sort_keys=True)
        
        # Hash para clave compacta
        cache_input = f"{normalized_message}|{context_str}"
        return hashlib.md5(cache_input.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Obtener resultado del caché si está disponible y vigente"""
        current_time = time.time()
        
        # Verificar si existe en caché
        if cache_key not in self._intent_cache:
            return None
            
        # Verificar TTL
        cache_time = self._cache_timestamps.get(cache_key, 0)
        if current_time - cache_time > self.cache_ttl:
            # Expirado - remover del caché
            del self._intent_cache[cache_key]
            del self._cache_timestamps[cache_key]
            return None
        
        # Hit de caché válido - mover al final (LRU)
        result = self._intent_cache.pop(cache_key)
        self._intent_cache[cache_key] = result
        
        self._stats["cache_hits"] += 1
        logger.debug(f"Cache hit for key: {cache_key[:8]}...")
        
        return result

    def _store_in_cache(self, cache_key: str, result: Dict[str, Any]):
        """Almacenar resultado en caché con gestión LRU"""
        current_time = time.time()
        
        # Gestión de tamaño del caché (LRU)
        if len(self._intent_cache) >= self.cache_size:
            # Remover el más antiguo
            oldest_key = next(iter(self._intent_cache))
            del self._intent_cache[oldest_key]
            del self._cache_timestamps[oldest_key]
        
        # Almacenar nuevo resultado
        self._intent_cache[cache_key] = result.copy()
        self._cache_timestamps[cache_key] = current_time
        
        logger.debug(f"Stored in cache: {cache_key[:8]}... (cache size: {len(self._intent_cache)})")

    def _simple_fallback_detection(self, message: str) -> Dict[str, Any]:
        """Fallback simple cuando no hay IA disponible"""
        self._stats["fallback_calls"] += 1
        
        # Fallback muy básico - siempre usar category_agent para empezar
        return {
            "primary_intent": "categoria",
            "confidence": 0.5,
            "entities": {},
            "requires_handoff": False,
            "target_agent": "category_agent",
        }


    async def analyze_intent_with_llm(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Usa LLM para análisis profundo de intención con caché optimizado"""
        start_time = time.time()
        self._stats["total_requests"] += 1
        
        if not self.ollama:
            return self._simple_fallback_detection(message)

        # Generar clave de caché
        cache_key = self._get_cache_key(message, state_dict)
        
        # Intentar obtener del caché primero
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            # Hit de caché - registrar métricas y retornar
            response_time = time.time() - start_time
            self._update_response_time_stats(response_time)
            logger.info(f"Intent cache hit for '{message}': {cached_result['primary_intent']} (confidence: {cached_result['confidence']:.2f}) - {response_time:.3f}s")
            return cached_result
        
        # Cache miss - hacer llamada a LLM
        self._stats["cache_misses"] += 1
        self._stats["llm_calls"] += 1

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
            
            # Crear resultado final
            final_result = {
                "primary_intent": result["intent"],
                "confidence": result["confidence"],
                "entities": result.get("entities", {}),
                "requires_handoff": False,
                "target_agent": self._map_intent_to_agent(result["intent"]),
            }
            
            # Almacenar en caché
            self._store_in_cache(cache_key, final_result)
            
            # Actualizar métricas
            response_time = time.time() - start_time
            self._update_response_time_stats(response_time)
            
            self.logger.info(f"LLM Intent analysis for '{message}': {result['intent']} (confidence: {result['confidence']:.2f}) - {response_time:.3f}s - {result.get('reasoning', '')}")
            
            return final_result
            
        except Exception as e:
            logger.error(f"Error in LLM analysis: {e}")
            return self._simple_fallback_detection(message)

    def _update_response_time_stats(self, response_time: float):
        """Actualizar estadísticas de tiempo de respuesta"""
        self._stats["total_response_time"] += response_time
        self._stats["avg_response_time"] = self._stats["total_response_time"] / self._stats["total_requests"]

    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del caché y performance"""
        hit_rate = (self._stats["cache_hits"] / max(self._stats["total_requests"], 1)) * 100
        
        return {
            "cache_size": len(self._intent_cache),
            "max_cache_size": self.cache_size,
            "cache_hit_rate": f"{hit_rate:.1f}%",
            "total_requests": self._stats["total_requests"],
            "cache_hits": self._stats["cache_hits"],
            "cache_misses": self._stats["cache_misses"],
            "llm_calls": self._stats["llm_calls"],
            "fallback_calls": self._stats["fallback_calls"],
            "avg_response_time": f"{self._stats['avg_response_time']:.3f}s",
            "cache_ttl": self.cache_ttl
        }

    def clear_cache(self):
        """Limpiar caché manualmente"""
        cache_size = len(self._intent_cache)
        self._intent_cache.clear()
        self._cache_timestamps.clear()
        logger.info(f"Intent cache cleared - removed {cache_size} entries")

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
