"""
User authentication models for PostgreSQL persistence
"""

import uuid

from sqlalchemy import Boolean, Column, Index, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from .base import Base, TimestampMixin
from .schemas import CORE_SCHEMA


class UserDB(Base, TimestampMixin):
    """
    Modelo de usuario para autenticación con persistencia en PostgreSQL

    Attributes:
        id: UUID único del usuario
        username: Nombre de usuario único para login
        email: Email único del usuario
        password_hash: Hash bcrypt de la contraseña
        full_name: Nombre completo del usuario
        disabled: Indica si el usuario está deshabilitado
        scopes: Lista de permisos/roles del usuario
    """

    __tablename__ = "users"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Authentication fields
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    # User information
    full_name = Column(String(255), nullable=True)

    # Status and permissions
    disabled = Column(Boolean, default=False, nullable=False)
    scopes = Column(ARRAY(String), default=list, nullable=False)

    # Timestamps are inherited from TimestampMixin
    # - created_at: DateTime
    # - updated_at: DateTime

    # Índices adicionales
    __table_args__ = (
        Index("idx_users_username", username),
        Index("idx_users_email", email),
        Index("idx_users_disabled", disabled),
        Index("idx_users_created_at", "created_at"),
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self):
        return f"<UserDB(id='{self.id}', username='{self.username}', email='{self.email}')>"

    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario (sin password_hash)"""
        return {
            "id": str(self.id),
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "disabled": self.disabled,
            "scopes": self.scopes or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
