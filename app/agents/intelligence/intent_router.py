"""
Router inteligente que usa IA con caché optimizado para detectar intenciones
"""

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Any, Dict, Optional

from app.utils import extract_json_from_text

from ..prompts.intent_analyzer import get_build_llm_prompt, get_system_prompt
from ..schemas import get_intent_to_agent_mapping, get_valid_intents
from .spacy_intent_analyzer import SpacyIntentAnalyzer

logger = logging.getLogger(__name__)


def _get_cache_key(message: str, context: Dict[str, Any] | None = None) -> str:
    """Generate cache key based on message and context"""
    # Normalize message for better hit rate but keep it unique
    normalized_message = message.lower().strip()

    # Include relevant context in the key
    context_str = ""
    if context:
        # Only include relevant context to avoid unnecessary cache misses
        relevant_context = {
            "language": context.get("language", "es"),
            "user_tier": context.get("customer_data", {}).get("tier", "basic"),
        }
        context_str = json.dumps(relevant_context, sort_keys=True)

    # Hash for compact key - IMPORTANT: include the full message to ensure uniqueness
    cache_input = f"{normalized_message}|{context_str}"
    return hashlib.md5(cache_input.encode()).hexdigest()


def _map_intent_to_agent(intent: str) -> str:
    """Mapea intenciones a agentes específicos"""
    mapping = get_intent_to_agent_mapping()

    agent = mapping.get(intent, "fallback_agent")
    logger.info(f"Mapping intent '{intent}' to agent '{agent}'")
    return agent


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
        self.cache_ttl = self.config.get("cache_ttl", 60)  # 1 minuto instead
        self._intent_cache = OrderedDict()
        self._cache_timestamps = {}

        # Inicializar SpacyIntentAnalyzer como fallback
        self.spacy_analyzer = SpacyIntentAnalyzer()
        self.use_spacy_fallback = self.config.get("use_spacy_fallback", True)

        # Métricas extendidas
        self._stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "llm_calls": 0,
            "spacy_calls": 0,
            "keyword_calls": 0,
            "fallback_calls": 0,
            "avg_response_time": 0.0,
            "total_response_time": 0.0,
        }

        logger.info(
            f"IntentRouter initialized - cache_size={self.cache_size}, cache_ttl={self.cache_ttl}s, "
            f"spacy_available={self.spacy_analyzer.is_available()}"
        )

    async def determine_intent(
        self,
        message: str,
        customer_data: Optional[Dict[str, Any]] = None,
        conversation_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Determina la intención del usuario usando sistema híbrido: Ollama → spaCy → Keywords

        Args:
            message: Mensaje del usuario
            customer_data: Datos del cliente (opcional)
            conversation_data: Datos de conversación (opcional)

        Returns:
            Diccionario con información de intención
        """
        start_time = time.time()
        self._stats["total_requests"] += 1

        # 1. Intentar con Ollama (IA) primero
        try:
            if self.ollama:
                logger.debug("Trying Ollama AI analysis...")
                result = await self._try_ollama_analysis(message, customer_data, conversation_data)
                if result["confidence"] >= 0.6:  # Umbral más bajo para AI
                    self._update_response_time_stats(time.time() - start_time)
                    return result
                else:
                    logger.debug(f"Ollama confidence too low ({result['confidence']:.2f}), trying spaCy...")
        except Exception as e:
            logger.warning(f"Ollama analysis failed: {e}, trying spaCy...")

        # 2. Fallback a spaCy si Ollama falla o tiene baja confianza
        if self.use_spacy_fallback and self.spacy_analyzer.is_available():
            try:
                logger.debug("Trying spaCy analysis...")
                self._stats["spacy_calls"] += 1
                spacy_result = self.spacy_analyzer.analyze_intent(message)

                if spacy_result["confidence"] >= 0.4:  # Umbral para spaCy
                    result = self._format_spacy_result(spacy_result)
                    self._update_response_time_stats(time.time() - start_time)
                    return result
                else:
                    logger.debug(
                        f"spaCy confidence too low ({spacy_result['confidence']:.2f}), using keyword fallback..."
                    )
            except Exception as e:
                logger.warning(f"spaCy analysis failed: {e}, using keyword fallback...")

        # 3. Último recurso: análisis por keywords
        logger.debug("Using keyword fallback analysis...")
        self._stats["keyword_calls"] += 1
        result = self._keyword_fallback_detection(message)
        self._update_response_time_stats(time.time() - start_time)
        return result

    async def _try_ollama_analysis(
        self,
        message: str,
        customer_data: Optional[Dict[str, Any]] = None,
        conversation_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Intenta análisis con Ollama"""
        state_dict = {"customer_data": customer_data, "conversation_data": conversation_data}

        # Ejecutar análisis asíncrono directamente
        result = await self.analyze_intent_with_llm(message, state_dict)
        self._stats["llm_calls"] += 1
        return result

    def _format_spacy_result(self, spacy_result: Dict[str, Any]) -> Dict[str, Any]:
        """Convierte resultado de spaCy al formato esperado"""
        intent = spacy_result.get("intent", "fallback")
        confidence = spacy_result.get("confidence", 0.4)

        return {
            "primary_intent": intent,
            "intent": intent,  # Para compatibilidad
            "confidence": confidence,
            "entities": spacy_result.get("analysis", {}).get("entities", []),
            "requires_handoff": False,
            "target_agent": _map_intent_to_agent(intent),
            "method": spacy_result.get("method", "spacy_nlp"),
            "analysis": spacy_result.get("analysis", {}),
            "reasoning": spacy_result.get("analysis", {}).get("reason", "spaCy NLP analysis"),
        }

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

    def _keyword_fallback_detection(self, message: str) -> Dict[str, Any]:
        """Fallback por keywords cuando spaCy y Ollama no están disponibles"""
        self._stats["fallback_calls"] += 1

        logger.debug(f"-> Keyword fallback for message: {message[:30]}...")

        message_lower = message.lower()

        # Palabras clave básicas por intent
        keyword_patterns = {
            "producto": [
                "producto",
                "productos",
                "stock",
                "precio",
                "cuesta",
                "venden",
                "tienen",
                "catálogo",
                "disponible",
            ],
            "promociones": ["oferta", "ofertas", "descuento", "promoción", "cupón", "rebaja", "barato"],
            "seguimiento": ["pedido", "orden", "envío", "tracking", "seguimiento", "dónde está", "cuando llega"],
            "soporte": ["problema", "error", "ayuda", "soporte", "reclamo", "no funciona", "defectuoso"],
            "facturacion": ["factura", "recibo", "pago", "cobro", "reembolso", "devolver", "cancelar"],
            "categoria": ["categoría", "tipo", "tecnología", "ropa", "zapatos", "televisores", "laptops"],
            "despedida": ["adiós", "chau", "bye", "gracias", "eso es todo", "hasta luego", "nada más"],
        }

        # Calcular scores
        scores = {}
        for intent, keywords in keyword_patterns.items():
            score = sum(1 for keyword in keywords if keyword in message_lower)
            scores[intent] = score

        # Encontrar el mejor match
        if scores and max(scores.values()) > 0:
            best_intent = max(scores.items(), key=lambda x: x[1])
            intent_name, match_count = best_intent

            # Confianza basada en número de matches
            confidence = min(match_count * 0.3, 0.7)  # Max 70% para keywords

            return {
                "primary_intent": intent_name,
                "intent": intent_name,
                "confidence": confidence,
                "entities": [],
                "requires_handoff": False,
                "target_agent": _map_intent_to_agent(intent_name),
                "method": "keyword_fallback",
                "reasoning": f"Keyword match: {match_count} keywords found for '{intent_name}'",
            }
        else:
            # Ningún keyword match - usar fallback
            return {
                "primary_intent": "fallback",
                "intent": "fallback",
                "confidence": 0.4,
                "entities": [],
                "requires_handoff": False,
                "target_agent": "fallback_agent",
                "method": "keyword_fallback",
                "reasoning": "No keyword patterns matched",
            }

    async def analyze_intent_with_llm(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Usa LLM para análisis profundo de intención con caché optimizado"""

        logger.debug(f"--> LLM analysis for message: {message[:8]}...")

        start_time = time.time()
        self._stats["total_requests"] += 1

        if not self.ollama:
            return self._keyword_fallback_detection(message)

        # Generar clave de caché
        cache_key = _get_cache_key(message, state_dict)
        logger.debug(f"Generated cache key for message '{message[:30]}...': {cache_key[:16]}...")

        if cached_result := self._get_from_cache(cache_key):
            self._stats["cache_hits"] += 1
            response_time = time.time() - start_time
            self._update_response_time_stats(response_time)
            logger.info(
                f"Intent cache hit for key '{cache_key[:50]}...':"
                f" {cached_result['primary_intent']} ({response_time:.3f}s)"
            )
            return cached_result

        # Cache miss - hacer llamada a LLM
        self._stats["cache_misses"] += 1
        self._stats["llm_calls"] += 1

        system_prompt = get_system_prompt()

        user_prompt = get_build_llm_prompt(message, state_dict)
        response_text = ""
        try:
            response_text = await asyncio.wait_for(
                self.ollama.generate_response(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=None,  # Use a default configured model
                    temperature=0.5,
                ),
                timeout=70.0,  # Add timeout to prevent hanging
            )

            # Extraer JSON usando la utilidad centralizada
            result = extract_json_from_text(
                response_text,
                default={"intent": "fallback", "confidence": 0.4, "reasoning": "Could not parse LLM response"},
                required_keys=["intent"],
            )

            # Si no se pudo extraer, usar fallback
            if not result or not isinstance(result, dict):
                logger.warning("Failed to extract JSON from LLM response")
                return self._keyword_fallback_detection(message)

            logger.debug(f"LLM response: {json.dumps(result)}")

            # Validar que la intención sea válida
            valid_intents = get_valid_intents()

            if result["intent"] not in valid_intents:
                logger.warning(f"Invalid intent detected: {result['intent']}. Using fallback intent.")
                result["intent"] = "fallback"
                result["confidence"] = 0.4
                result["reasoning"] = "LLM returned an invalid intent."

            # Crear resultado final
            final_result = {
                "primary_intent": result["intent"],
                "confidence": result["confidence"],
                "entities": result.get("entities", {}),
                "requires_handoff": False,
                "target_agent": _map_intent_to_agent(result["intent"]),
            }

            # Almacenar en caché
            self._store_in_cache(cache_key, final_result)

            # Actualizar métricas
            response_time = time.time() - start_time
            self._update_response_time_stats(response_time)

            self.logger.info(
                f"LLM Intent analysis for '{message}': {result['intent']} "
                f"(confidence: {result['confidence']:.2f}) - {response_time:.3f}s - "
                f"{result.get('reasoning', '')}"
            )

            return final_result

        except KeyError as e:
            logger.error(f"Missing required key in LLM response: {e}. Raw response: '{response_text}'")
            return self._keyword_fallback_detection(message)

        except asyncio.TimeoutError:
            logger.error(f"LLM analysis timed out after 8s for message: '{message[:50]}...'")
            return self._keyword_fallback_detection(message)

        except Exception as e:
            # Improved error logging with more context
            error_msg = str(e) if str(e) else "Unknown error"
            logger.error(
                f"Error in LLM analysis: {error_msg} | "
                f"Message: '{message[:100]}...' | "
                f"Response length: {len(response_text)} chars | "
                f"Response preview: '{response_text[:200]}...'"
            )
            return self._keyword_fallback_detection(message)

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
            "cache_ttl": self.cache_ttl,
        }

    def clear_cache(self):
        """Limpiar caché manualmente"""
        cache_size = len(self._intent_cache)
        self._intent_cache.clear()
        self._cache_timestamps.clear()
        logger.info(f"Intent cache cleared - removed {cache_size} entries")

    def clear_cache_for_message(self, message: str):
        """Clear cache for a specific message"""
        cache_key = _get_cache_key(message, {})
        if cache_key in self._intent_cache:
            del self._intent_cache[cache_key]
            del self._cache_timestamps[cache_key]
            logger.info(f"Cleared cache for message: '{message}' (key: {cache_key[:8]}...)")
        else:
            logger.info(f"No cache entry found for message: '{message}'")
