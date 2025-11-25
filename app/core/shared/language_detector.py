"""
Utilidad para detección de idioma usando spaCy con fallback robusto
"""

import hashlib
import logging
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LanguageDetector:
    """
    Detector de idioma inteligente usando spaCy con múltiples estrategias de detección

    Características:
    - Detección usando modelos spaCy cuando están disponibles
    - Fallback a análisis de palabras clave
    - Sistema de caché para optimizar rendimiento
    - Configuración flexible de idiomas soportados
    - Métricas de confianza
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # Configuración
        self.supported_languages = self.config.get("supported_languages", ["es", "en"])
        self.default_language = self.config.get("default_language", "es")
        self.confidence_threshold = self.config.get("confidence_threshold", 0.6)
        self.cache_size = self.config.get("cache_size", 1000)
        self.cache_ttl = self.config.get("cache_ttl", 3600)  # 1 hora

        # Sistema de caché
        self._detection_cache = OrderedDict()
        self._cache_timestamps = {}

        # Modelos spaCy disponibles
        self._spacy_models = {}
        self._spacy_available = False

        # Estadísticas
        self._stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "spacy_detections": 0,
            "keyword_detections": 0,
            "avg_response_time": 0.0,
            "total_response_time": 0.0,
        }

        # Inicializar modelos spaCy
        self._initialize_spacy_models()

        # Patrones de palabras clave por idioma (fallback)
        self._keyword_patterns = {
            "es": {
                "common_words": [
                    "el",
                    "la",
                    "de",
                    "que",
                    "y",
                    "a",
                    "en",
                    "un",
                    "es",
                    "se",
                    "no",
                    "te",
                    "lo",
                    "le",
                    "da",
                    "su",
                    "por",
                    "son",
                    "con",
                    "para",
                    "hola",
                    "como",
                    "donde",
                    "cuando",
                    "porque",
                    "pero",
                    "muy",
                    "todo",
                ],
                "patterns": [
                    "ñ",  # Carácter específico del español
                    "qu",
                    "ch",
                    "ll",
                    "rr",  # Dígrafos comunes
                ],
                "endings": ["ción", "dad", "mente", "ado", "ida", "ero", "oso"],
            },
            "en": {
                "common_words": [
                    "the",
                    "be",
                    "to",
                    "of",
                    "and",
                    "a",
                    "in",
                    "that",
                    "have",
                    "i",
                    "it",
                    "for",
                    "not",
                    "on",
                    "with",
                    "as",
                    "you",
                    "do",
                    "at",
                    "hello",
                    "how",
                    "where",
                    "when",
                    "what",
                    "why",
                    "very",
                    "all",
                ],
                "patterns": [
                    "th",
                    "sh",
                    "ch",
                    "wh",  # Dígrafos comunes en inglés
                ],
                "endings": ["tion", "ness", "ment", "able", "ible", "ing", "ed", "ly"],
            },
        }

        logger.info(
            f"LanguageDetector initialized - spaCy available: {self._spacy_available}, "
            f"supported languages: {self.supported_languages}"
        )

    def _initialize_spacy_models(self):
        """Inicializa los modelos spaCy disponibles"""
        model_mapping = {"es": "es_core_news_sm", "en": "en_core_web_sm"}

        for lang_code in self.supported_languages:
            model_name = model_mapping.get(lang_code)
            if model_name:
                try:
                    import spacy

                    nlp = spacy.load(model_name)
                    self._spacy_models[lang_code] = nlp
                    self._spacy_available = True
                    logger.info(f"spaCy model loaded for {lang_code}: {model_name}")
                except (OSError, ImportError) as e:
                    logger.warning(f"Could not load spaCy model for {lang_code}: {e}")
                    continue

        if not self._spacy_available:
            logger.warning("No spaCy models available, using keyword-based detection only")

    def detect_language(self, text: str) -> Dict[str, Any]:
        """
        Detecta el idioma del texto usando múltiples estrategias

        Args:
            text: Texto a analizar

        Returns:
            Dict con información de detección:
            {
                'language': str,
                'confidence': float,
                'method': str,
                'details': Dict[str, any]
            }
        """
        start_time = time.time()
        self._stats["total_requests"] += 1

        if not text or len(text.strip()) == 0:
            return self._create_result(
                language=self.default_language, confidence=0.5, method="default", details={"reason": "Empty text"}
            )

        # Normalizar texto para caché
        text_normalized = text.lower().strip()
        cache_key = self._get_cache_key(text_normalized)

        # Verificar caché
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            self._update_response_time_stats(time.time() - start_time)
            return cached_result

        # Detectar idioma
        result = None

        # 1. Intentar con spaCy si está disponible
        if self._spacy_available:
            result = self._detect_with_spacy(text_normalized)
            if result and result["confidence"] >= self.confidence_threshold:
                self._stats["spacy_detections"] += 1
                self._store_in_cache(cache_key, result)
                self._update_response_time_stats(time.time() - start_time)
                return result

        # 2. Fallback a detección por palabras clave
        result = self._detect_with_keywords(text_normalized)
        self._stats["keyword_detections"] += 1

        # Almacenar en caché y devolver
        self._store_in_cache(cache_key, result)
        self._update_response_time_stats(time.time() - start_time)
        return result

    def _detect_with_spacy(self, text: str) -> Optional[Dict[str, Any]]:
        """Detecta idioma usando modelos spaCy"""
        try:
            scores = {}
            details = {}

            for lang_code, nlp in self._spacy_models.items():
                # Procesar texto con el modelo
                doc = nlp(text[:1000])  # Limitar longitud para rendimiento

                # Calcular score basado en diferentes características
                score = 0.0
                features = {}

                # 1. Análisis de tokens conocidos
                known_tokens = sum(1 for token in doc if not token.is_oov)
                total_tokens = len([token for token in doc if token.is_alpha])
                if total_tokens > 0:
                    token_score = known_tokens / total_tokens
                    score += token_score * 0.4
                    features["token_score"] = token_score

                # 2. Análisis de entidades nombradas
                if doc.ents:
                    ner_score = min(len(doc.ents) / max(total_tokens, 1), 1.0)
                    score += ner_score * 0.2
                    features["ner_score"] = ner_score

                # 3. Análisis de POS tagging
                pos_tags = [token.pos_ for token in doc if token.is_alpha]
                if pos_tags:
                    # Diversidad de etiquetas POS indica buena comprensión del idioma
                    pos_diversity = len(set(pos_tags)) / len(pos_tags)
                    score += pos_diversity * 0.3
                    features["pos_diversity"] = pos_diversity

                # 4. Análisis sintáctico
                parsed_tokens = sum(1 for token in doc if token.dep_ != "ROOT" and token.head != token)
                if total_tokens > 0:
                    syntax_score = parsed_tokens / total_tokens
                    score += syntax_score * 0.1
                    features["syntax_score"] = syntax_score

                scores[lang_code] = score
                details[lang_code] = features

            if scores:
                # Encontrar el idioma con mayor score
                best_lang = max(scores.items(), key=lambda x: x[1])
                language, confidence = best_lang

                return self._create_result(
                    language=language,
                    confidence=min(confidence, 1.0),
                    method="spacy_nlp",
                    details={
                        "scores": scores,
                        "features": details,
                        "model_used": self._spacy_models[language].meta.get("name", "unknown"),
                    },
                )

        except Exception as e:
            logger.warning(f"Error in spaCy language detection: {e}")
            return None

        return None

    def _detect_with_keywords(self, text: str) -> Dict[str, Any]:
        """Detecta idioma usando análisis de palabras clave"""
        scores = {}
        details = {}

        for lang_code in self.supported_languages:
            if lang_code not in self._keyword_patterns:
                continue

            patterns = self._keyword_patterns[lang_code]
            score = 0.0
            matches = {}

            text_lower = text.lower()
            words = text_lower.split()

            # 1. Palabras comunes
            common_matches = sum(1 for word in words if word in patterns["common_words"])
            if words:
                common_score = common_matches / len(words)
                score += common_score * 0.5
                matches["common_words"] = common_matches

            # 2. Patrones de caracteres
            pattern_matches = sum(1 for pattern in patterns["patterns"] if pattern in text_lower)
            pattern_score = min(pattern_matches / max(len(patterns["patterns"]), 1), 1.0)
            score += pattern_score * 0.3
            matches["patterns"] = pattern_matches

            # 3. Terminaciones típicas
            ending_matches = sum(1 for word in words for ending in patterns["endings"] if word.endswith(ending))
            if words:
                ending_score = min(ending_matches / len(words), 1.0)
                score += ending_score * 0.2
                matches["endings"] = ending_matches

            scores[lang_code] = score
            details[lang_code] = matches

        # Encontrar el mejor match
        if scores and max(scores.values()) > 0:
            best_lang = max(scores.items(), key=lambda x: x[1])
            language, confidence = best_lang

            # Ajustar confianza para keywords (máximo 0.8)
            confidence = min(confidence, 0.8)

            return self._create_result(
                language=language,
                confidence=confidence,
                method="keyword_analysis",
                details={"scores": scores, "matches": details},
            )
        else:
            # Ningún match - usar idioma por defecto
            return self._create_result(
                language=self.default_language,
                confidence=0.4,
                method="default_fallback",
                details={"reason": "No keyword patterns matched"},
            )

    def _create_result(self, language: str, confidence: float, method: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un resultado de detección estructurado"""
        return {
            "language": language,
            "confidence": round(confidence, 3),
            "method": method,
            "details": details,
            "timestamp": time.time(),
        }

    def _get_cache_key(self, text: str) -> str:
        """Genera clave de caché para el texto"""
        # Usar primeras 200 caracteres para balance entre precisión y eficiencia
        text_sample = text[:200]
        return hashlib.md5(text_sample.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Obtiene resultado del caché si está disponible y vigente"""
        current_time = time.time()

        if cache_key not in self._detection_cache:
            return None

        # Verificar TTL
        cache_time = self._cache_timestamps.get(cache_key, 0)
        if current_time - cache_time > self.cache_ttl:
            del self._detection_cache[cache_key]
            del self._cache_timestamps[cache_key]
            return None

        # Cache hit válido
        result = self._detection_cache.pop(cache_key)
        self._detection_cache[cache_key] = result  # Mover al final (LRU)
        self._stats["cache_hits"] += 1

        return result.copy()

    def _store_in_cache(self, cache_key: str, result: Dict[str, Any]):
        """Almacena resultado en caché con gestión LRU"""
        current_time = time.time()

        # Gestión de tamaño del caché (LRU)
        if len(self._detection_cache) >= self.cache_size:
            oldest_key = next(iter(self._detection_cache))
            del self._detection_cache[oldest_key]
            del self._cache_timestamps[oldest_key]

        # Almacenar nuevo resultado
        self._detection_cache[cache_key] = result.copy()
        self._cache_timestamps[cache_key] = current_time
        self._stats["cache_misses"] += 1

    def _update_response_time_stats(self, response_time: float):
        """Actualiza estadísticas de tiempo de respuesta"""
        self._stats["total_response_time"] += response_time
        self._stats["avg_response_time"] = self._stats["total_response_time"] / self._stats["total_requests"]

    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del detector"""
        hit_rate = (self._stats["cache_hits"] / max(self._stats["total_requests"], 1)) * 100

        return {
            "total_requests": self._stats["total_requests"],
            "cache_hits": self._stats["cache_hits"],
            "cache_misses": self._stats["cache_misses"],
            "cache_hit_rate": f"{hit_rate:.1f}%",
            "spacy_detections": self._stats["spacy_detections"],
            "keyword_detections": self._stats["keyword_detections"],
            "avg_response_time": f"{self._stats['avg_response_time']:.3f}s",
            "spacy_available": self._spacy_available,
            "supported_languages": self.supported_languages,
            "cache_size": len(self._detection_cache),
            "max_cache_size": self.cache_size,
        }

    def clear_cache(self):
        """Limpia el caché manualmente"""
        cache_size = len(self._detection_cache)
        self._detection_cache.clear()
        self._cache_timestamps.clear()
        logger.info(f"Language detection cache cleared - removed {cache_size} entries")

    def is_spacy_available(self) -> bool:
        """Verifica si spaCy está disponible"""
        return self._spacy_available

    def get_supported_languages(self) -> List[str]:
        """Obtiene lista de idiomas soportados"""
        return self.supported_languages.copy()


# Instancia global del detector (lazy loading)
_global_detector: Optional[LanguageDetector] = None


def get_language_detector(config: Optional[Dict[str, Any]] = None) -> LanguageDetector:
    """
    Obtiene una instancia global del detector de idiomas (singleton)

    Args:
        config: Configuración opcional (solo usado en primera inicialización)

    Returns:
        Instancia de LanguageDetector
    """
    global _global_detector

    if _global_detector is None:
        _global_detector = LanguageDetector(config)

    return _global_detector


def detect_language(text: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Función de conveniencia para detección de idioma

    Args:
        text: Texto a analizar
        config: Configuración opcional

    Returns:
        Dict con resultado de detección
    """
    detector = get_language_detector(config)
    return detector.detect_language(text)
