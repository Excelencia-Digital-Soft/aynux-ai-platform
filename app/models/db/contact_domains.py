"""
Contact domains management models - Multi-domain contact classification
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy import Column, DateTime, Float, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base, TimestampMixin
from .schemas import CORE_SCHEMA


class ContactDomain(Base, TimestampMixin):
    """
    Mapeo de contactos WhatsApp a dominios específicos del negocio

    Esta tabla es el corazón del sistema multi-dominio, permitiendo
    identificar rápidamente qué servicio usar para cada contacto.
    """

    __tablename__ = "contact_domains"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wa_id = Column(String(20), unique=True, nullable=False, index=True)  # WhatsApp ID del contacto
    domain = Column(String(50), nullable=False, index=True)  # ecommerce, hospital, credit, excelencia

    # Métricas de confianza y método de asignación
    confidence = Column(Float, default=1.0)  # 0.0-1.0, confidence en la asignación
    assigned_method = Column(String(50), nullable=False)  # manual, auto, pattern, ai, admin

    # Metadatos flexibles por dominio
    domain_metadata = Column(JSONB, default=dict)  # Información específica del dominio

    # Timestamps para auditoría
    assigned_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_verified = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Índices optimizados
    __table_args__ = (
        Index("idx_contact_domains_wa_id", wa_id),  # Búsqueda principal
        Index("idx_contact_domains_domain", domain),  # Estadísticas por dominio
        Index("idx_contact_domains_method", assigned_method),  # Análisis de métodos
        Index("idx_contact_domains_assigned_at", assigned_at),  # Consultas temporales
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self):
        return f"<ContactDomain(wa_id='{self.wa_id}', domain='{self.domain}', method='{self.assigned_method}')>"

    def to_dict(self) -> Dict:
        """Convertir a diccionario para API responses"""
        return {
            "id": str(self.id),
            "wa_id": self.wa_id,
            "domain": self.domain,
            "confidence": self.confidence,
            "assigned_method": self.assigned_method,
            "domain_metadata": self.domain_metadata,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at is not None else None,
            "last_verified": self.last_verified.isoformat() if self.last_verified is not None else None,
            "created_at": self.created_at.isoformat() if self.created_at is not None else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at is not None else None,
        }

    @classmethod
    def create_from_detection(
        cls,
        wa_id: str,
        domain: str,
        confidence: float = 1.0,
        method: str = "auto",
        domain_metadata: Optional[Dict] = None,
    ) -> "ContactDomain":
        """
        Factory method para crear desde detección automática

        Args:
            wa_id: WhatsApp ID del contacto
            domain: Dominio detectado
            confidence: Nivel de confianza (0.0-1.0)
            method: Método de detección
            domain_metadata: Metadatos adicionales
        """
        return cls(
            wa_id=wa_id,
            domain=domain,
            confidence=confidence,
            assigned_method=method,
            domain_metadata=domain_metadata or {},
        )


class DomainConfig(Base, TimestampMixin):
    """
    Configuración dinámica de dominios disponibles

    Permite habilitar/deshabilitar dominios y configurar
    patrones de detección sin reiniciar el sistema.
    """

    __tablename__ = "domain_configs"

    domain = Column(String(50), primary_key=True)  # ecommerce, hospital, credit, etc.
    enabled = Column(String(10), default="true")  # "true", "false", "maintenance"
    display_name = Column(String(100), nullable=False)  # Nombre para mostrar
    description = Column(String(500))  # Descripción del dominio

    # Configuración técnica
    service_class = Column(String(100))  # Clase del servicio Python
    model_config = Column(JSONB, default=dict)  # Configuración del modelo IA

    # Patrones de detección automática
    phone_patterns = Column(JSONB, default=list)  # Patrones de números de teléfono
    keyword_patterns = Column(JSONB, default=list)  # Palabras clave para clasificación

    # Configuración avanzada
    priority = Column(Float, default=0.5)  # Prioridad en clasificación (0.0-1.0)
    fallback_enabled = Column(String(10), default="true")  # Permitir como fallback

    # Metadatos extensibles
    config_metadata = Column(JSONB, default=dict)

    # Índices
    __table_args__ = (
        Index("idx_domain_configs_enabled", enabled),
        Index("idx_domain_configs_priority", priority),
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self):
        return f"<DomainConfig(domain='{self.domain}', enabled='{self.enabled}', display_name='{self.display_name}')>"

    def to_dict(self) -> Dict:
        """Convertir a diccionario para API responses"""
        return {
            "domain": self.domain,
            "enabled": self.enabled,
            "display_name": self.display_name,
            "description": self.description,
            "service_class": self.service_class,
            "model_config": self.model_config,
            "phone_patterns": self.phone_patterns,
            "keyword_patterns": self.keyword_patterns,
            "priority": self.priority,
            "fallback_enabled": self.fallback_enabled,
            "config_metadata": self.config_metadata,
            "created_at": self.created_at.isoformat() if self.created_at is not None else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at is not None else None,
        }

    @property
    def is_enabled(self) -> bool:
        """Verificar si el dominio está habilitado"""
        return str(self.enabled).lower() == "true"

    @property
    def is_maintenance(self) -> bool:
        """Verificar si el dominio está en mantenimiento"""
        return str(self.enabled).lower() == "maintenance"
