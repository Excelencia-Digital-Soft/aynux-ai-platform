"""
SpaCy Intent Analyzer - Fallback inteligente para análisis de intents sin Ollama
"""

import logging
import subprocess
import sys
from typing import Any, Dict, List, Tuple

from app.core.schemas import get_intent_to_agent_mapping

logger = logging.getLogger(__name__)


class SpacyIntentAnalyzer:
    """
    Analizador de intents usando spaCy como fallback cuando Ollama no está disponible.

    Características:
    - Análisis de entidades nombradas (NER)
    - Similitud semántica con vectores de palabras
    - Detección de patrones específicos del dominio e-commerce
    - Análisis de sentiment para casos de soporte

    Implementado como Singleton para evitar cargar el modelo múltiples veces.
    """

    # Singleton instance and shared NLP model
    _instance: "SpacyIntentAnalyzer | None" = None
    _nlp_model = None  # Class-level shared model

    def __new__(cls, model_name: str = "es_core_news_sm"):
        """Singleton pattern - only create one instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str = "es_core_news_sm"):
        # Skip re-initialization if already done
        if self._initialized:
            return

        self.model_name = model_name
        self.nlp = None
        self._load_model()

        # Patrones específicos del dominio
        self._init_domain_patterns()

        # Cache para mejorar performance
        self._similarity_cache = {}

        self._initialized = True
        logger.info("SpacyIntentAnalyzer singleton initialized")

    def _load_model(self):
        """Carga el modelo de spaCy, descargándolo si es necesario. Uses class-level cache."""
        # Use cached model if available
        if SpacyIntentAnalyzer._nlp_model is not None:
            self.nlp = SpacyIntentAnalyzer._nlp_model
            logger.info(f"Using cached spaCy model: {self.model_name}")
            return

        try:
            import spacy

            # Intentar cargar el modelo
            try:
                SpacyIntentAnalyzer._nlp_model = spacy.load(self.model_name)
                self.nlp = SpacyIntentAnalyzer._nlp_model
                logger.info(f"Modelo spaCy {self.model_name} cargado exitosamente")
            except OSError:
                logger.warning(f"Modelo {self.model_name} no encontrado, intentando descarga...")
                # Intentar descargar el modelo
                try:
                    subprocess.check_call([sys.executable, "-m", "spacy", "download", self.model_name])
                    SpacyIntentAnalyzer._nlp_model = spacy.load(self.model_name)
                    self.nlp = SpacyIntentAnalyzer._nlp_model
                    logger.info(f"Modelo {self.model_name} descargado y cargado")
                except Exception as e:
                    logger.error(f"No se pudo descargar el modelo {self.model_name}: {e}")
                    # Fallback a modelo base sin vectores
                    logger.warning("Usando modelo base sin vectores...")
                    SpacyIntentAnalyzer._nlp_model = spacy.blank("es")
                    self.nlp = SpacyIntentAnalyzer._nlp_model

        except ImportError:
            logger.error("spaCy no está instalado. Usando fallback básico.")
            self.nlp = None

    def _init_domain_patterns(self):
        """Inicializa patrones específicos del dominio e-commerce"""

        # Palabras clave por intent con pesos
        self.intent_keywords = {
            "saludo": {
                "high": ["hola", "buenos días", "buenos dias", "buenas tardes", "buenas noches", "saludos", "hey", "hi", "hello"],
                "medium": ["buen día", "buen dia", "qué tal", "que tal", "cómo estás", "como estas", "cómo está", "como esta", "qué onda", "que onda"],
                "low": ["buenas", "ey", "alo", "holi", "holaa"],
            },
            "producto": {
                "high": ["producto", "productos", "catálogo", "stock", "disponible", "venden", "tienen"],
                "medium": ["precio", "cuesta", "cuánto", "características", "especificaciones"],
                "low": ["ver", "mostrar", "buscar", "qué", "que"],
            },
            "promociones": {
                "high": ["oferta", "ofertas", "descuento", "promoción", "cupón", "rebaja"],
                "medium": ["barato", "económico", "sale", "liquidación"],
                "low": ["precio", "costo"],
            },
            "seguimiento": {
                "high": ["pedido", "orden", "envío", "tracking", "seguimiento", "entrega"],
                "medium": ["dónde está", "cuándo llega", "rastrear"],
                "low": ["estado", "ubicación"],
            },
            "soporte": {
                "high": ["problema", "error", "ayuda", "soporte", "reclamo", "queja"],
                "medium": ["no funciona", "defectuoso", "roto", "mal"],
                "low": ["asistencia", "técnico"],
            },
            "facturacion": {
                "high": ["factura", "recibo", "pago", "cobro", "reembolso"],
                "medium": ["devolver", "cancelar", "tarjeta", "cuenta"],
                "low": ["billing", "compra"],
            },
            "categoria": {
                "high": ["categoría", "tipo", "clase"],
                "medium": ["tecnología", "ropa", "zapatos", "televisores", "laptops"],
                "low": ["accesorios", "celulares"],
            },
            "despedida": {
                "high": ["adiós", "chau", "bye", "gracias", "eso es todo"],
                "medium": ["hasta luego", "nada más", "terminar"],
                "low": ["ok", "bien"],
            },
            "excelencia": {
                "high": ["excelencia", "excelencia digital", "erp", "demo", "módulo", "módulos"],
                "medium": ["software", "historia clínica", "turnos médicos", "healthcare", "hotel", "hoteles"],
                "low": ["capacitación", "obras sociales", "gremio", "gremios", "validtek", "turmedica", "mediflow"],
            },
            # Excelencia Software Support/Incidents
            "excelencia_soporte": {
                "high": ["incidencia", "ticket", "reportar", "bug", "falla"],
                "medium": ["problema módulo", "error sistema", "levantar ticket"],
                "low": ["soporte técnico", "ayuda software"],
            },
            # Excelencia-specific intents
            "excelencia_facturacion": {
                "high": ["factura cliente", "factura de cliente", "estado de cuenta", "cobranza"],
                "medium": ["deuda cliente", "pago cliente", "cobrar cliente", "facturar cliente"],
                "low": ["generar factura", "cuenta cliente"],
            },
            "excelencia_promociones": {
                "high": ["promoción software", "descuento módulo", "oferta implementación", "promoción excelencia"],
                "medium": ["descuento capacitación", "promo software", "oferta software"],
                "low": ["descuento software", "precio especial software"],
            },
        }

        # Entidades relevantes para cada intent
        self.intent_entities = {
            "producto": ["ORG", "MISC"],  # Marcas, productos
            "seguimiento": ["NUM", "ID"],  # Números de pedido
            "facturacion": ["MONEY", "NUM"],  # Montos, números
            "categoria": ["ORG", "MISC"],  # Categorías, marcas
        }

        # Patrones de urgencia para soporte
        self.urgency_patterns = ["urgente", "rápido", "ya", "inmediatamente", "ahora", "importante", "crítico", "grave"]

        # Patrones de negación
        self.negation_patterns = ["no", "nunca", "jamás", "sin", "nada", "ningún", "ninguna"]

    def analyze_intent(self, message: str) -> Dict[str, Any]:
        """
        Analiza un mensaje y determina el intent más probable

        Args:
            message: Mensaje del usuario

        Returns:
            Diccionario con intent, confianza y análisis detallado
        """
        if not self.nlp:
            return self._keyword_fallback(message)

        try:
            # Procesar mensaje con spaCy
            doc = self.nlp(message.lower())

            # Análisis multi-dimensional
            keyword_scores = self._analyze_keywords(doc)
            entity_scores = self._analyze_entities(doc)
            similarity_scores = self._analyze_similarity(doc)
            pattern_scores = self._analyze_patterns(doc)

            # Combinar scores con pesos
            final_scores = self._combine_scores(keyword_scores, entity_scores, similarity_scores, pattern_scores)

            # Determinar el mejor intent
            best_intent, confidence = self._get_best_intent(final_scores)

            # Análisis adicional
            entities = self._extract_entities(doc)
            sentiment = self._analyze_sentiment(doc)
            urgency = self._detect_urgency(doc)

            return {
                "intent": best_intent,
                "confidence": confidence,
                "method": "spacy_nlp",
                "analysis": {
                    "entities": entities,
                    "sentiment": sentiment,
                    "urgency": urgency,
                    "scores": final_scores,
                    "tokens": len(doc),
                    "lemmas": [token.lemma_ for token in doc if not token.is_stop],
                },
            }

        except Exception as e:
            logger.error(f"Error en análisis spaCy: {e}")
            return self._keyword_fallback(message)

    def _analyze_keywords(self, doc) -> Dict[str, float]:
        """Analiza keywords en el documento"""
        scores = {}
        text = doc.text.lower()

        for intent, keyword_groups in self.intent_keywords.items():
            score = 0

            # High weight keywords
            for keyword in keyword_groups.get("high", []):
                if keyword in text:
                    score += 1.0

            # Medium weight keywords
            for keyword in keyword_groups.get("medium", []):
                if keyword in text:
                    score += 0.7

            # Low weight keywords
            for keyword in keyword_groups.get("low", []):
                if keyword in text:
                    score += 0.3

            # Normalizar por número de tokens
            if len(doc) > 0:
                scores[intent] = min(score / len(doc) * 10, 1.0)
            else:
                scores[intent] = 0

        return scores

    def get_supported_intents(self) -> List[str]:
        """
        Get list of supported intents.

        Returns:
            List of intent names that can be recognized
        """
        return list(self.intent_keywords.keys())

    def _analyze_entities(self, doc) -> Dict[str, float]:
        """Analiza entidades nombradas relevantes"""
        scores = {intent: 0.0 for intent in self.intent_keywords.keys()}

        for ent in doc.ents:
            for intent, relevant_entities in self.intent_entities.items():
                if ent.label_ in relevant_entities:
                    scores[intent] += 0.5

        return scores

    def _analyze_similarity(self, doc) -> Dict[str, float]:
        """Analiza similitud semántica (si el modelo tiene vectores)"""
        scores = {intent: 0.0 for intent in self.intent_keywords.keys()}

        if not doc.has_vector:
            return scores

        # Crear textos de referencia para cada intent
        reference_texts = {
            "saludo": "hola buenos días buenas tardes saludos qué tal cómo estás",
            "producto": "ver productos disponibles precio stock catálogo",
            "promociones": "ofertas descuentos promociones cupones rebajas pedido compra",
            "seguimiento": "pedido envío tracking seguimiento entrega orden",
            "soporte": "problema ayuda error soporte técnico reclamo incidencia",
            "facturacion": "factura pago recibo cobro reembolso pedido orden",
            "categoria": "categoría tipo clase tecnología ropa",
            "despedida": "adiós gracias chau bye hasta luego",
            "excelencia": "excelencia digital erp demo módulos software historia clínica turnos médicos healthcare hotel",
            # NEW: Excelencia-specific intents
            "excelencia_facturacion": "factura cliente estado cuenta cobranza deuda pago cliente",
            "excelencia_promociones": "promoción software descuento módulo oferta implementación capacitación",
        }

        for intent, ref_text in reference_texts.items():
            if self.nlp:
                ref_doc = self.nlp(ref_text)
                if ref_doc.has_vector:
                    similarity = doc.similarity(ref_doc)
                    scores[intent] = max(similarity, 0.0)

        return scores

    def _analyze_patterns(self, doc) -> Dict[str, float]:
        """Analiza patrones específicos del dominio"""
        scores = {intent: 0.0 for intent in self.intent_keywords.keys()}
        text = doc.text.lower()

        # Patrones de números (para pedidos)
        if any(token.like_num or token.is_digit for token in doc):
            scores["seguimiento"] += 0.3
            scores["facturacion"] += 0.2

        # Patrones de precios/moneda
        if any(char in text for char in ["$", "€", "USD", "pesos"]):
            scores["producto"] += 0.3
            scores["facturacion"] += 0.4

        # Patrones de urgencia (para soporte)
        if any(pattern in text for pattern in self.urgency_patterns):
            scores["soporte"] += 0.4

        # Patrones de pregunta (¿qué?, ¿dónde?, etc.)
        if any(token.text in ["qué", "que", "dónde", "donde", "cuándo", "cuando", "cómo", "como"] for token in doc):
            scores["producto"] += 0.2
            scores["seguimiento"] += 0.2

        return scores

    def _combine_scores(self, *score_dicts) -> Dict[str, float]:
        """Combina múltiples diccionarios de scores con pesos"""
        weights = [0.4, 0.2, 0.3, 0.1]  # keywords, entities, similarity, patterns
        combined = {}

        # Inicializar con ceros
        for intent in self.intent_keywords.keys():
            combined[intent] = 0.0

        # Combinar scores con pesos
        for i, score_dict in enumerate(score_dicts):
            weight = weights[i] if i < len(weights) else 0.1
            for intent, score in score_dict.items():
                combined[intent] += score * weight

        return combined

    def _get_best_intent(self, scores: Dict[str, float]) -> Tuple[str, float]:
        """Determina el mejor intent y su confianza"""
        if not scores or all(score == 0 for score in scores.values()):
            return "fallback", 0.4

        best_intent = max(scores.items(), key=lambda x: x[1])
        intent_name, raw_score = best_intent

        # Ajustar confianza (spaCy es más confiable que keywords pero menos que AI)
        confidence = min(raw_score * 0.9, 0.9)  # Max 90% para spaCy

        # Si la confianza es muy baja, usar fallback
        if confidence < 0.3:
            return "fallback", 0.4

        return intent_name, confidence

    def _extract_entities(self, doc) -> List[Dict[str, str]]:
        """Extrae entidades relevantes del documento"""
        entities = []

        for ent in doc.ents:
            entities.append({"text": ent.text, "label": ent.label_, "start": ent.start_char, "end": ent.end_char})

        # Detectar números de pedido (patrones como #123, orden 456, etc.)
        text = doc.text
        import re

        # Patrón para números de pedido
        pedido_patterns = [r"#\d+", r"pedido\s*\d+", r"orden\s*\d+", r"número\s*\d+"]

        for pattern in pedido_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities.append({"text": match.group(), "label": "PEDIDO", "start": match.start(), "end": match.end()})

        return entities

    def _analyze_sentiment(self, doc) -> str:
        """Análisis básico de sentiment"""
        negative_words = [
            "malo",
            "terrible",
            "pésimo",
            "horrible",
            "molesto",
            "frustrado",
            "enojado",
            "furioso",
            "disgustado",
            "problema",
            "error",
            "falla",
        ]

        positive_words = [
            "bueno",
            "excelente",
            "genial",
            "fantástico",
            "perfecto",
            "increíble",
            "satisfecho",
            "contento",
            "feliz",
            "gracias",
            "agradecido",
        ]

        text = doc.text.lower()
        negative_count = sum(1 for word in negative_words if word in text)
        positive_count = sum(1 for word in positive_words if word in text)

        if negative_count > positive_count:
            return "negative"
        elif positive_count > negative_count:
            return "positive"
        else:
            return "neutral"

    def _detect_urgency(self, doc) -> str:
        """Detecta nivel de urgencia en el mensaje"""
        text = doc.text.lower()

        high_urgency = ["urgente", "inmediatamente", "ya", "rápido", "ahora", "crítico"]
        medium_urgency = ["pronto", "necesito", "importante", "ayuda"]

        if any(word in text for word in high_urgency):
            return "high"
        elif any(word in text for word in medium_urgency):
            return "medium"
        else:
            return "low"

    def _keyword_fallback(self, message: str) -> Dict[str, Any]:
        """Fallback básico usando solo keywords cuando spaCy no está disponible"""
        message_lower = message.lower()
        scores = {}

        for intent, keyword_groups in self.intent_keywords.items():
            score = 0
            for group_name, keywords in keyword_groups.items():
                weight = {"high": 1.0, "medium": 0.7, "low": 0.3}.get(group_name, 0.1)
                for keyword in keywords:
                    if keyword in message_lower:
                        score += weight

            scores[intent] = min(score, 1.0)

        if not scores or all(score == 0 for score in scores.values()):
            return {
                "intent": "fallback",
                "confidence": 0.4,
                "method": "keyword_fallback",
                "analysis": {"reason": "No patterns matched"},
            }

        best_intent = max(scores.items(), key=lambda x: x[1])
        intent_name, confidence = best_intent

        return {
            "intent": intent_name,
            "confidence": confidence * 0.7,  # Reducir confianza para keyword-only
            "method": "keyword_fallback",
            "analysis": {"scores": scores, "reason": f"Keyword match for '{intent_name}'"},
        }

    def get_agent_for_intent(self, intent: str) -> str:
        """Mapea un intent a su agente correspondiente"""
        mapping = get_intent_to_agent_mapping()
        return mapping.get(intent, "fallback_agent")

    def is_available(self) -> bool:
        """Verifica si spaCy está disponible y funcionando"""
        return self.nlp is not None

    def get_model_info(self) -> Dict[str, Any]:
        """Obtiene información sobre el modelo cargado"""
        if not self.nlp:
            return {"available": False, "reason": "spaCy not loaded"}

        return {
            "available": True,
            "model_name": self.model_name,
            "has_vectors": self.nlp.has_pipe("vectors"),
            "has_ner": self.nlp.has_pipe("ner"),
            "lang": self.nlp.lang,
            "vocab_size": len(self.nlp.vocab),
        }
