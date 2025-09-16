"""
Super Orchestrator Service - Clasificación inteligente de dominio usando IA
"""

import logging
import time
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.models.message import BotResponse, Contact, WhatsAppMessage
from app.services.domain_detector import get_domain_detector
from app.services.domain_manager import get_domain_manager

logger = logging.getLogger(__name__)


class SuperOrchestratorService:
    """
    Super Orquestador que usa IA para clasificar mensajes cuando
    el dominio del contacto no está determinado.

    Solo se activa para contactos nuevos o sin dominio asignado.
    """

    def __init__(self):
        self.settings = get_settings()
        self.domain_detector = get_domain_detector()
        self.domain_manager = get_domain_manager()

        # Configuración de clasificación IA
        self.confidence_threshold = getattr(self.settings, "SUPER_ORCHESTRATOR_CONFIDENCE_THRESHOLD", 0.7)
        self.model = getattr(self.settings, "SUPER_ORCHESTRATOR_MODEL", "deepseek-r1:7b")

        # Estadísticas del super orquestador
        self._stats = {
            "total_classifications": 0,
            "successful_classifications": 0,
            "fallback_classifications": 0,
            "avg_classification_time": 0.0,
            "total_classification_time": 0.0,
            "domain_distribution": {},
        }

        # Cache de patrones por dominio
        self._domain_patterns = {
            "ecommerce": {
                "keywords": [
                    "comprar",
                    "producto",
                    "precio",
                    "tienda",
                    "envío",
                    "stock",
                    "descuento",
                    "carrito",
                    "pago",
                    "factura",
                    "garantía",
                    "devolución",
                    "catálogo",
                    "disponible",
                    "oferta",
                    "promoción",
                    "entrega",
                ],
                "phrases": [
                    "quiero comprar",
                    "cuánto cuesta",
                    "está disponible",
                    "hacer pedido",
                    "ver productos",
                    "necesito cotización",
                ],
                "indicators": ["$", "precio", "pesos", "dolares", "envío gratis"],
            },
            "hospital": {
                "keywords": [
                    "cita",
                    "doctor",
                    "médico",
                    "consulta",
                    "urgencia",
                    "emergencia",
                    "síntoma",
                    "turno",
                    "especialista",
                    "hospital",
                    "clínica",
                    "paciente",
                    "dolor",
                    "fiebre",
                    "medicamento",
                    "receta",
                    "análisis",
                ],
                "phrases": [
                    "necesito cita",
                    "consulta médica",
                    "me duele",
                    "tengo síntomas",
                    "urgencia médica",
                    "agendar turno",
                    "ver doctor",
                ],
                "indicators": ["107", "urgencia", "ambulancia", "guardia"],
            },
            "credit": {
                "keywords": [
                    "préstamo",
                    "crédito",
                    "financiamiento",
                    "cuota",
                    "tasa",
                    "interés",
                    "DNI",
                    "ingresos",
                    "garantía",
                    "aval",
                    "banco",
                    "plata",
                    "dinero",
                    "solicitar",
                    "CUIT",
                    "CUIL",
                    "sueldo",
                    "trabajo",
                ],
                "phrases": [
                    "necesito préstamo",
                    "solicitar crédito",
                    "cuánto me prestan",
                    "tasa de interés",
                    "cuotas mensuales",
                    "financiación",
                ],
                "indicators": ["$", "cuotas", "mensual", "anual", "%"],
            },
            "excelencia": {
                "keywords": [
                    "software",
                    "sistema",
                    "ERP",
                    "excelencia",
                    "demo",
                    "funcionalidad",
                    "módulo",
                    "reporte",
                    "gestión",
                    "automatización",
                    "programa",
                    "instalación",
                    "licencia",
                    "soporte",
                    "capacitación",
                ],
                "phrases": [
                    "mostrar software",
                    "demo del sistema",
                    "qué puede hacer",
                    "cómo funciona",
                    "necesito sistema",
                    "gestionar empresa",
                ],
                "indicators": ["ERP", "módulos", "reportes", "automatización"],
            },
        }

        logger.info("SuperOrchestratorService initialized for intelligent domain classification")

    async def process_webhook_message(
        self, message: WhatsAppMessage, contact: Contact, db_session: AsyncSession
    ) -> BotResponse:
        """
        Procesar mensaje usando super orquestador para clasificación de dominio

        Args:
            message: Mensaje de WhatsApp
            contact: Información de contacto
            db_session: Sesión de base de datos

        Returns:
            Respuesta procesada por el dominio correspondiente
        """
        start_time = time.time()
        self._stats["total_classifications"] += 1

        wa_id = contact.wa_id
        message_text = self._extract_message_text(message)

        logger.info(f"SuperOrchestrator processing new contact: {wa_id}")

        try:
            # 1. Clasificar dominio usando IA
            classification_result = await self._classify_domain(message_text, contact)

            domain = classification_result["domain"]
            confidence = classification_result["confidence"]
            method = classification_result["method"]

            logger.info(f"Domain classified: {wa_id} -> {domain} (confidence: {confidence:.2f}, method: {method})")

            # 2. Persistir la clasificación si la confianza es suficiente
            if confidence >= self.confidence_threshold:
                await self.domain_detector.assign_domain(
                    wa_id=wa_id, domain=domain, method=method, confidence=confidence, db_session=db_session
                )
                self._stats["successful_classifications"] += 1
            else:
                self._stats["fallback_classifications"] += 1
                logger.warning(f"Low confidence classification: {wa_id} -> {domain} ({confidence:.2f})")

            # 3. Obtener servicio del dominio y procesar mensaje
            domain_service = await self.domain_manager.get_service(domain)

            if not domain_service:
                logger.error(f"Domain service not available: {domain}")
                return BotResponse(
                    status="failure",
                    message="Lo siento, el servicio para tu consulta no está disponible en este momento.",
                )

            # 4. Procesar con el servicio de dominio
            response = await domain_service.process_webhook_message(message, contact)

            # 5. Actualizar estadísticas
            self._update_stats(domain, time.time() - start_time)

            return response

        except Exception as e:
            logger.error(f"Error in super orchestrator processing: {e}")

            # Fallback a dominio por defecto
            default_domain = getattr(self.settings, "DEFAULT_DOMAIN", "ecommerce")
            domain_service = await self.domain_manager.get_service(default_domain)

            if domain_service:
                return await domain_service.process_webhook_message(message, contact)
            else:
                return BotResponse(
                    status="failure", message="Lo siento, hay un problema técnico. Por favor intenta más tarde."
                )

    async def _classify_domain(self, message: str, contact: Contact) -> Dict[str, Any]:
        """
        Clasificar dominio usando múltiples estrategias

        Args:
            message: Texto del mensaje
            contact: Información de contacto

        Returns:
            Resultado de clasificación con dominio, confianza y método
        """
        # 1. Intentar clasificación rápida por palabras clave
        keyword_result = self._classify_by_keywords(message)
        if keyword_result["confidence"] >= 0.8:
            return keyword_result

        # 2. Clasificación avanzada usando IA (si está disponible)
        try:
            ai_result = await self._classify_with_ai(message, contact)
            if ai_result["confidence"] >= self.confidence_threshold:
                return ai_result
        except Exception as e:
            logger.warning(f"AI classification failed: {e}")

        # 3. Combinar resultados y usar el mejor
        if keyword_result["confidence"] > 0.5:
            return keyword_result

        # 4. Fallback al dominio por defecto
        default_domain = getattr(self.settings, "DEFAULT_DOMAIN", "ecommerce")
        return {
            "domain": default_domain,
            "confidence": 0.3,
            "method": "fallback_default",
            "details": "No clear domain identified, using default",
        }

    def _classify_by_keywords(self, message: str) -> Dict[str, Any]:
        """Clasificación rápida basada en palabras clave"""
        message_lower = message.lower()
        domain_scores = {}

        # Evaluar cada dominio
        for domain, patterns in self._domain_patterns.items():
            score = 0.0
            matches = []

            # Palabras clave (peso 0.4)
            keyword_matches = 0
            for keyword in patterns["keywords"]:
                if keyword in message_lower:
                    keyword_matches += 1
                    matches.append(f"keyword:{keyword}")

            if patterns["keywords"]:
                keyword_score = min(keyword_matches / len(patterns["keywords"]), 1.0)
                score += keyword_score * 0.4

            # Frases completas (peso 0.4)
            phrase_matches = 0
            for phrase in patterns["phrases"]:
                if phrase in message_lower:
                    phrase_matches += 1
                    matches.append(f"phrase:{phrase}")

            if patterns["phrases"]:
                phrase_score = min(phrase_matches / len(patterns["phrases"]), 1.0)
                score += phrase_score * 0.4

            # Indicadores específicos (peso 0.2)
            indicator_matches = 0
            for indicator in patterns["indicators"]:
                if indicator in message_lower:
                    indicator_matches += 1
                    matches.append(f"indicator:{indicator}")

            if patterns["indicators"]:
                indicator_score = min(indicator_matches / len(patterns["indicators"]), 1.0)
                score += indicator_score * 0.2

            domain_scores[domain] = {"score": score, "matches": matches}

        # Encontrar el mejor dominio
        if domain_scores:
            best_domain = max(domain_scores.items(), key=lambda x: x[1]["score"])
            domain = best_domain[0]
            score_data = best_domain[1]

            return {
                "domain": domain,
                "confidence": min(score_data["score"], 1.0),
                "method": "keyword_analysis",
                "details": {
                    "all_scores": {k: v["score"] for k, v in domain_scores.items()},
                    "matches": score_data["matches"],
                },
            }

        # Sin matches significativos
        return {
            "domain": "ecommerce",  # Default
            "confidence": 0.1,
            "method": "keyword_analysis_fallback",
            "details": "No significant keyword matches found",
        }

    async def _classify_with_ai(self, message: str) -> Dict[str, Any]:
        """Clasificación avanzada usando IA"""
        try:
            # Import lazy para evitar dependencias circulares
            from app.agents.integrations.ollama_integration import OllamaIntegration

            ollama = OllamaIntegration()
            llm = ollama.get_llm(temperature=0.1, model=self.model)

            # Optimized prompt for domain classification
            prompt = f"""Analyze the following WhatsApp message and determine the most appropriate domain.

MESSAGE: "{message}"

AVAILABLE DOMAINS:
1. **ecommerce**: Online store, products, purchases, prices, shipping
2. **hospital**: Health, medical appointments, doctors, symptoms, emergencies
3. **credit**: Loans, credits, financing, rates, banks
4. **excelencia**: ERP software, systems, demos, technical support

INSTRUCTIONS:
- Respond ONLY with the domain name (ecommerce, hospital, credit, excelencia)
- If unsure, use "ecommerce" as default
- Consider the context and intention of the message

DOMAIN:"""

            response = await llm.ainvoke(prompt)

            # Procesar respuesta
            if hasattr(response, "content"):
                content = response.content
                if isinstance(content, list):
                    # Si content es una lista, extraer el texto de todos los elementos
                    domain_text = (
                        " ".join(
                            str(item.get("text", str(item))) if isinstance(item, dict) else str(item)
                            for item in content
                        )
                        .strip()
                        .lower()
                    )
                else:
                    domain_text = str(content).strip().lower()
            else:
                domain_text = str(response).strip().lower()

            # Validar dominio
            valid_domains = list(self._domain_patterns.keys())

            for domain in valid_domains:
                if domain in domain_text:
                    return {
                        "domain": domain,
                        "confidence": 0.8,  # Alta confianza en IA
                        "method": "ai_classification",
                        "details": {"raw_response": domain_text, "model": self.model},
                    }

            # Si no reconoce el dominio, usar default
            return {
                "domain": "ecommerce",
                "confidence": 0.5,
                "method": "ai_classification_fallback",
                "details": {"raw_response": domain_text, "error": "Domain not recognized in AI response"},
            }

        except Exception as e:
            logger.error(f"AI classification error: {e}")
            raise

    def _extract_message_text(self, message: WhatsAppMessage) -> str:
        """Extraer texto del mensaje de WhatsApp"""
        if message.text and message.text.body:
            return message.text.body
        elif message.interactive:
            # Manejar mensajes interactivos
            if message.interactive.button_reply:
                return message.interactive.button_reply.title
            elif message.interactive.list_reply:
                return message.interactive.list_reply.title

        return "Mensaje sin texto"

    def _update_stats(self, domain: str, classification_time: float):
        """Actualizar estadísticas del super orquestador"""
        # Tiempo de respuesta
        self._stats["total_classification_time"] += classification_time
        self._stats["avg_classification_time"] = (
            self._stats["total_classification_time"] / self._stats["total_classifications"]
        )

        # Distribución por dominio
        if domain not in self._stats["domain_distribution"]:
            self._stats["domain_distribution"][domain] = 0
        self._stats["domain_distribution"][domain] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del super orquestador"""
        success_rate = 0.0
        if self._stats["total_classifications"] > 0:
            success_rate = self._stats["successful_classifications"] / self._stats["total_classifications"] * 100

        return {
            **self._stats,
            "success_rate": f"{success_rate:.1f}%",
            "confidence_threshold": self.confidence_threshold,
            "model": self.model,
            "available_domains": list(self._domain_patterns.keys()),
        }

    async def test_classification(self, message: str) -> Dict[str, Any]:
        """
        Probar clasificación sin persistir (para testing)

        Args:
            message: Mensaje a clasificar

        Returns:
            Resultado de clasificación
        """
        # Crear contacto ficticio para testing
        fake_contact = type("Contact", (), {"wa_id": "test_user", "profile": {"name": "Test User"}})()

        return await self._classify_domain(message, fake_contact)


# Instancia global del super orquestador
_global_orchestrator: Optional[SuperOrchestratorService] = None


def get_super_orchestrator() -> SuperOrchestratorService:
    """
    Obtener instancia global del super orquestador (singleton)

    Returns:
        Instancia de SuperOrchestratorService
    """
    global _global_orchestrator

    if _global_orchestrator is None:
        _global_orchestrator = SuperOrchestratorService()

    return _global_orchestrator

