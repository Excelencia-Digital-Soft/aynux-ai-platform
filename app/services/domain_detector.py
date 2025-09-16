"""
Domain Detector - Detección rápida de dominio por contacto WhatsApp
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.models.db.contact_domains import ContactDomain, DomainConfig

logger = logging.getLogger(__name__)


class DomainDetector:
    """
    Detector de dominio usando PostgreSQL directo

    Estrategia de detección (por orden de velocidad):
    1. Base de datos con índices (milisegundos)
    2. Patrones configurables (milisegundos)
    3. Fallback al SuperOrquestador (segundos)
    """

    def __init__(self, db_session: Optional[AsyncSession] = None):
        self.settings = get_settings()
        self.db_session = db_session

        # Cache en memoria para configuraciones
        self._domain_configs: Dict[str, DomainConfig] = {}
        self._configs_loaded = False
        self._last_config_load = 0
        self._config_cache_ttl = 300  # 5 minutos

        # Estadísticas de performance
        self._stats = {
            "total_detections": 0,
            "db_hits": 0,
            "pattern_hits": 0,
            "fallbacks": 0,
            "avg_response_time": 0.0,
            "total_response_time": 0.0,
        }

        logger.info("DomainDetector initialized with PostgreSQL direct access")

    async def detect_domain(self, wa_id: str, db_session: AsyncSession) -> Dict[str, Any]:
        """
        Detectar dominio para un contacto WhatsApp

        Args:
            wa_id: WhatsApp ID del contacto
            db_session: Sesión de base de datos

        Returns:
            Dict con información de detección:
            {
                'domain': str,
                'confidence': float,
                'method': str,
                'cached': bool,
                'response_time': float
            }
        """
        start_time = time.time()
        self._stats["total_detections"] += 1

        # 1. Buscar en base de datos
        result = await self._detect_from_database(wa_id, db_session)
        if result:
            self._stats["db_hits"] += 1
            result["cached"] = False
            self._update_response_time_stats(time.time() - start_time)
            logger.debug(f"Domain detected from DB: {wa_id} -> {result['domain']}")
            return result

        # 2. Intentar detección por patrones
        result = await self._detect_from_patterns(wa_id, db_session)
        if result:
            self._stats["pattern_hits"] += 1
            result["cached"] = False
            # Guardar en BD para futuras consultas
            await self._store_detection_result(wa_id, result, db_session)
            self._update_response_time_stats(time.time() - start_time)
            logger.info(f"Domain detected by pattern: {wa_id} -> {result['domain']}")
            return result

        # 3. Fallback - dominio no encontrado
        self._stats["fallbacks"] += 1
        default_domain = getattr(self.settings, "DEFAULT_DOMAIN", "ecommerce")
        result = {
            "domain": default_domain,
            "confidence": 0.3,  # Baja confianza para fallback
            "method": "fallback_default",
            "cached": False,
            "response_time": time.time() - start_time,
        }

        self._update_response_time_stats(time.time() - start_time)
        logger.info(f"Domain fallback applied: {wa_id} -> {result['domain']}")
        return result

    async def _detect_from_database(self, wa_id: str, db_session: AsyncSession) -> Optional[Dict[str, Any]]:
        """Detectar desde base de datos"""
        try:
            # Consulta optimizada con índice en wa_id
            query = select(ContactDomain).where(ContactDomain.wa_id == wa_id)
            result = await db_session.execute(query)
            contact_domain = result.scalar_one_or_none()

            if contact_domain:
                return {
                    "domain": contact_domain.domain,
                    "confidence": contact_domain.confidence,
                    "method": contact_domain.assigned_method,
                    "response_time": 0.01,  # DB hit rápido
                }
        except Exception as e:
            logger.error(f"Error querying database for domain: {e}")

        return None

    async def _detect_from_patterns(self, wa_id: str, db_session: AsyncSession) -> Optional[Dict[str, Any]]:
        """Detectar usando patrones configurados"""
        try:
            # Cargar configuraciones de dominio
            await self._load_domain_configs(db_session)

            # Evaluar patrones por prioridad
            best_match = None
            best_score = 0.0

            for domain, config in self._domain_configs.items():
                if not config.is_enabled:
                    continue

                score = self._evaluate_phone_patterns(wa_id, config.phone_patterns)

                # Aplicar prioridad del dominio
                weighted_score = score * float(config.priority)

                if weighted_score > best_score:
                    best_score = weighted_score
                    best_match = {
                        "domain": domain,
                        "confidence": min(weighted_score, 1.0),
                        "method": "pattern_detection",
                    }

            return best_match

        except Exception as e:
            logger.error(f"Error in pattern detection: {e}")
            return None

    def _evaluate_phone_patterns(self, wa_id: str, patterns: List[str]) -> float:
        """Evaluar patrones de número de teléfono"""
        if not patterns:
            return 0.0

        matches = 0
        for pattern in patterns:
            try:
                # Convertir patrón a regex
                regex_pattern = pattern.replace("*", ".*").replace("?", ".")
                if re.match(regex_pattern, wa_id):
                    matches += 1
            except re.error:
                logger.warning(f"Invalid regex pattern: {pattern}")
                continue

        # Retornar score normalizado
        return min(matches / len(patterns), 1.0) if patterns else 0.0

    async def _load_domain_configs(self, db_session: AsyncSession):
        """Cargar configuraciones de dominio (con cache)"""
        current_time = time.time()

        # Verificar si necesitamos recargar configuraciones
        if self._configs_loaded and current_time - self._last_config_load < self._config_cache_ttl:
            return

        try:
            query = select(DomainConfig).where(DomainConfig.enabled == "true")
            result = await db_session.execute(query)
            configs = result.scalars().all()

            # Actualizar cache local
            self._domain_configs = {str(config.domain): config for config in configs}
            self._configs_loaded = True
            self._last_config_load = current_time

            logger.debug(f"Loaded {len(configs)} domain configurations")

        except Exception as e:
            logger.error(f"Error loading domain configurations: {e}")

    async def _store_detection_result(self, wa_id: str, result: Dict[str, Any], db_session: AsyncSession):
        """Almacenar resultado de detección en base de datos"""
        try:
            contact_domain = ContactDomain.create_from_detection(
                wa_id=wa_id, domain=result["domain"], confidence=result["confidence"], method=result["method"]
            )

            db_session.add(contact_domain)
            await db_session.commit()

            logger.info(f"Stored domain detection: {wa_id} -> {result['domain']}")

        except Exception as e:
            logger.error(f"Error storing detection result: {e}")
            await db_session.rollback()

    def _update_response_time_stats(self, response_time: float):
        """Actualizar estadísticas de tiempo de respuesta"""
        self._stats["total_response_time"] += response_time
        self._stats["avg_response_time"] = self._stats["total_response_time"] / self._stats["total_detections"]

    async def assign_domain(
        self,
        wa_id: str,
        domain: str,
        method: str = "manual",
        confidence: float = 1.0,
        db_session: Optional[AsyncSession] = None,
    ) -> bool:
        """
        Asignar dominio manualmente a un contacto

        Args:
            wa_id: WhatsApp ID
            domain: Dominio a asignar
            method: Método de asignación
            confidence: Nivel de confianza
            db_session: Sesión de base de datos

        Returns:
            True si se asignó correctamente
        """
        if not db_session:
            logger.error("Database session required for domain assignment")
            return False

        try:
            # Verificar si ya existe
            query = select(ContactDomain).where(ContactDomain.wa_id == wa_id)
            result = await db_session.execute(query)
            existing = result.scalar_one_or_none()

            if existing:
                # Actualizar existente usando SQLAlchemy update
                update_stmt = (
                    update(ContactDomain)
                    .where(ContactDomain.wa_id == wa_id)
                    .values(domain=domain, confidence=confidence, assigned_method=method)
                )
                await db_session.execute(update_stmt)
            else:
                # Crear nuevo
                contact_domain = ContactDomain.create_from_detection(
                    wa_id=wa_id, domain=domain, confidence=confidence, method=method
                )
                db_session.add(contact_domain)

            await db_session.commit()

            logger.info(f"Domain assigned: {wa_id} -> {domain} (method: {method})")
            return True

        except Exception as e:
            logger.error(f"Error assigning domain: {e}")
            await db_session.rollback()
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del detector"""
        db_hit_rate = 0.0
        if self._stats["total_detections"] > 0:
            db_hit_rate = self._stats["db_hits"] / self._stats["total_detections"] * 100

        return {
            **self._stats,
            "db_hit_rate": f"{db_hit_rate:.1f}%",
            "postgresql_direct": True,
            "configs_loaded": self._configs_loaded,
            "total_configs": len(self._domain_configs),
        }

    async def clear_domain_assignment(self, wa_id: str, db_session: AsyncSession) -> bool:
        """
        Eliminar asignación de dominio de la base de datos

        Args:
            wa_id: WhatsApp ID del contacto
            db_session: Sesión de base de datos

        Returns:
            True si se eliminó correctamente
        """
        try:
            from sqlalchemy import delete

            # Eliminar de la base de datos
            query = delete(ContactDomain).where(ContactDomain.wa_id == wa_id)
            result = await db_session.execute(query)
            await db_session.commit()

            deleted_count = result.rowcount
            logger.info(f"Cleared domain assignment for: {wa_id} (deleted: {deleted_count})")
            return deleted_count > 0

        except Exception as e:
            logger.warning(f"Error clearing domain assignment: {e}")
            await db_session.rollback()
            return False


# Instancia global del detector (lazy loading)
_global_detector: Optional[DomainDetector] = None


def get_domain_detector() -> DomainDetector:
    """
    Obtener instancia global del detector de dominios (singleton)

    Returns:
        Instancia de DomainDetector
    """
    global _global_detector

    if _global_detector is None:
        _global_detector = DomainDetector()

    return _global_detector

