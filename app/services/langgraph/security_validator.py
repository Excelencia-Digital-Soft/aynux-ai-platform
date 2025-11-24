"""
Security validation and health checking for LangGraph chatbot service
"""

import logging
from typing import Any, Dict, Tuple

from app.database import check_db_connection

logger = logging.getLogger(__name__)


class SecurityValidator:
    """Handles security validation and system health checks"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.security = self._create_security_placeholder()

    def _create_security_placeholder(self):
        """Crea un placeholder simplificado para el sistema de seguridad"""

        class SecurityPlaceholder:
            async def check_rate_limit(self, _: str) -> bool:
                return True  # Permitir por defecto

            async def check_message_content(self, _: str) -> Tuple[bool, Dict[str, Any]]:
                return True, {"safe": True}

        return SecurityPlaceholder()

    async def check_message_security(self, user_number: str, message_text: str) -> Dict[str, Any]:
        """Verificación de seguridad simplificada del mensaje"""
        try:
            # Verificar rate limiting (simplificado)
            if not await self.security.check_rate_limit(user_number):
                return {"allowed": False, "message": "Has enviado demasiados mensajes. Por favor espera un momento."}

            # Verificar contenido (simplificado)
            is_safe, _ = await self.security.check_message_content(message_text)
            if not is_safe:
                return {"allowed": False, "message": "Tu mensaje contiene contenido no permitido."}

            return {"allowed": True}

        except Exception as e:
            self.logger.warning(f"Security check error: {e}")
            return {"allowed": True}  # Permitir por defecto en caso de error

    async def check_database_health(self) -> bool:
        """Verifica la salud de la base de datos"""
        try:
            return await check_db_connection()
        except Exception as e:
            self.logger.warning(f"Database health check failed: {e}")
            return False
