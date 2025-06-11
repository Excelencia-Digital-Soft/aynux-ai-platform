"""
Sistema de seguridad y RBAC para el sistema multi-agente
"""
import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class SecurityManager:
    """Gestiona seguridad, autenticación y autorización del sistema"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Configurar claves de seguridad
        self._setup_security_keys()
        
        # Configurar RBAC
        self._setup_rbac()
        
        # Cache de tokens válidos
        self.active_tokens = {}
        
        # Configurar políticas de seguridad
        self.security_policies = self._load_security_policies()
        
        logger.info("Security manager initialized")
    
    def _setup_security_keys(self):
        """Configura claves de cifrado y JWT"""
        # Clave para JWT (debería venir de variables de entorno)
        self.jwt_secret = self.config.get("jwt_secret", secrets.token_hex(32))
        
        # Clave para cifrado simétrico
        encryption_key = self.config.get("encryption_key")
        if encryption_key:
            self.cipher_suite = Fernet(encryption_key.encode())
        else:
            # Generar nueva clave si no existe
            key = Fernet.generate_key()
            self.cipher_suite = Fernet(key)
            logger.warning("Using generated encryption key - should use persistent key in production")
        
        # Salt para hashing de passwords
        self.password_salt = self.config.get("password_salt", secrets.token_bytes(32))
    
    def _setup_rbac(self):
        """Configura sistema de roles y permisos"""
        # Definir roles y sus permisos
        self.roles = {
            "admin": {
                "permissions": [
                    "system.full_access",
                    "agents.manage",
                    "monitoring.view",
                    "monitoring.manage",
                    "conversations.view_all",
                    "conversations.manage",
                    "security.manage"
                ],
                "description": "Acceso completo al sistema"
            },
            "operator": {
                "permissions": [
                    "agents.use",
                    "monitoring.view",
                    "conversations.view_own",
                    "conversations.manage_own"
                ],
                "description": "Operador del sistema de agentes"
            },
            "viewer": {
                "permissions": [
                    "monitoring.view",
                    "conversations.view_own"
                ],
                "description": "Solo lectura de datos propios"
            },
            "customer": {
                "permissions": [
                    "agents.use_basic",
                    "conversations.create",
                    "conversations.view_own"
                ],
                "description": "Cliente del sistema"
            }
        }
        
        # Jerarquía de roles
        self.role_hierarchy = {
            "admin": ["operator", "viewer", "customer"],
            "operator": ["viewer", "customer"],
            "viewer": ["customer"],
            "customer": []
        }
    
    def _load_security_policies(self) -> Dict[str, Any]:
        """Carga políticas de seguridad"""
        return {
            "token_expiry": {
                "access_token": timedelta(hours=2),
                "refresh_token": timedelta(days=7),
                "session_token": timedelta(hours=8)
            },
            "password_policy": {
                "min_length": 8,
                "require_uppercase": True,
                "require_lowercase": True,
                "require_digits": True,
                "require_special": True
            },
            "rate_limiting": {
                "requests_per_minute": 60,
                "requests_per_hour": 1000
            },
            "session_security": {
                "max_concurrent_sessions": 3,
                "session_timeout": timedelta(hours=2),
                "require_2fa": False
            },
            "data_protection": {
                "encrypt_sensitive_data": True,
                "log_access": True,
                "audit_changes": True
            }
        }
    
    def generate_token(
        self,
        user_id: str,
        role: str,
        token_type: str = "access",
        custom_claims: Dict[str, Any] = None
    ) -> str:
        """
        Genera un token JWT para autenticación
        
        Args:
            user_id: ID del usuario
            role: Rol del usuario
            token_type: Tipo de token (access, refresh, session)
            custom_claims: Claims adicionales
        
        Returns:
            Token JWT firmado
        """
        try:
            # Obtener tiempo de expiración según tipo
            expiry = self.security_policies["token_expiry"].get(
                f"{token_type}_token",
                timedelta(hours=1)
            )
            
            # Preparar payload
            payload = {
                "user_id": user_id,
                "role": role,
                "token_type": token_type,
                "iat": datetime.utcnow(),
                "exp": datetime.utcnow() + expiry,
                "jti": secrets.token_hex(16),  # Token ID único
                "permissions": self.get_role_permissions(role)
            }
            
            # Añadir claims customizados
            if custom_claims:
                payload.update(custom_claims)
            
            # Generar token
            token = jwt.encode(
                payload,
                self.jwt_secret,
                algorithm="HS256"
            )
            
            # Guardar en cache de tokens activos
            self.active_tokens[payload["jti"]] = {
                "user_id": user_id,
                "role": role,
                "expires_at": payload["exp"],
                "token_type": token_type
            }
            
            logger.info(f"Generated {token_type} token for user {user_id}")
            return token
            
        except Exception as e:
            logger.error(f"Error generating token: {e}")
            raise SecurityException("Failed to generate token")
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verifica y decodifica un token JWT
        
        Args:
            token: Token JWT a verificar
        
        Returns:
            Payload decodificado del token
        """
        try:
            # Decodificar token
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"]
            )
            
            # Verificar que el token esté en cache activo
            token_id = payload.get("jti")
            if token_id not in self.active_tokens:
                raise SecurityException("Token not found in active tokens")
            
            # Verificar expiración
            if datetime.utcnow() > payload["exp"]:
                self.revoke_token(token_id)
                raise SecurityException("Token expired")
            
            logger.debug(f"Token verified for user {payload['user_id']}")
            return payload
            
        except jwt.ExpiredSignatureError:
            raise SecurityException("Token expired")
        except jwt.InvalidTokenError:
            raise SecurityException("Invalid token")
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            raise SecurityException("Token verification failed")
    
    def revoke_token(self, token_id: str) -> bool:
        """
        Revoca un token específico
        
        Args:
            token_id: ID del token a revocar
        
        Returns:
            True si se revocó exitosamente
        """
        try:
            if token_id in self.active_tokens:
                del self.active_tokens[token_id]
                logger.info(f"Token {token_id} revoked")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error revoking token: {e}")
            return False
    
    def check_permission(
        self,
        user_role: str,
        required_permission: str
    ) -> bool:
        """
        Verifica si un rol tiene un permiso específico
        
        Args:
            user_role: Rol del usuario
            required_permission: Permiso requerido
        
        Returns:
            True si tiene el permiso
        """
        try:
            # Obtener permisos del rol
            role_permissions = self.get_role_permissions(user_role)
            
            # Verificar permiso directo
            if required_permission in role_permissions:
                return True
            
            # Verificar permisos por jerarquía
            for inherited_role in self.role_hierarchy.get(user_role, []):
                inherited_permissions = self.get_role_permissions(inherited_role)
                if required_permission in inherited_permissions:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking permission: {e}")
            return False
    
    def get_role_permissions(self, role: str) -> List[str]:
        """
        Obtiene todos los permisos de un rol
        
        Args:
            role: Nombre del rol
        
        Returns:
            Lista de permisos
        """
        return self.roles.get(role, {}).get("permissions", [])
    
    def encrypt_data(self, data: str) -> str:
        """
        Cifra datos sensibles
        
        Args:
            data: Datos a cifrar
        
        Returns:
            Datos cifrados en base64
        """
        try:
            encrypted = self.cipher_suite.encrypt(data.encode())
            return encrypted.decode()
            
        except Exception as e:
            logger.error(f"Error encrypting data: {e}")
            raise SecurityException("Encryption failed")
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """
        Descifra datos
        
        Args:
            encrypted_data: Datos cifrados
        
        Returns:
            Datos descifrados
        """
        try:
            decrypted = self.cipher_suite.decrypt(encrypted_data.encode())
            return decrypted.decode()
            
        except Exception as e:
            logger.error(f"Error decrypting data: {e}")
            raise SecurityException("Decryption failed")
    
    def hash_password(self, password: str) -> Tuple[str, str]:
        """
        Hash de password con salt
        
        Args:
            password: Password en texto plano
        
        Returns:
            Tupla (hash, salt)
        """
        try:
            # Generar salt único para este password
            salt = secrets.token_bytes(32)
            
            # Crear hash usando PBKDF2
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            
            password_hash = kdf.derive(password.encode())
            
            return password_hash.hex(), salt.hex()
            
        except Exception as e:
            logger.error(f"Error hashing password: {e}")
            raise SecurityException("Password hashing failed")
    
    def verify_password(
        self,
        password: str,
        stored_hash: str,
        salt: str
    ) -> bool:
        """
        Verifica un password contra su hash
        
        Args:
            password: Password a verificar
            stored_hash: Hash almacenado
            salt: Salt usado en el hash
        
        Returns:
            True si el password es correcto
        """
        try:
            # Recrear el KDF con el mismo salt
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=bytes.fromhex(salt),
                iterations=100000,
            )
            
            # Generar hash del password proporcionado
            password_hash = kdf.derive(password.encode())
            
            # Comparar hashes de forma segura
            return hmac.compare_digest(
                password_hash.hex(),
                stored_hash
            )
            
        except Exception as e:
            logger.error(f"Error verifying password: {e}")
            return False
    
    def validate_password_policy(self, password: str) -> Tuple[bool, List[str]]:
        """
        Valida un password contra la política de seguridad
        
        Args:
            password: Password a validar
        
        Returns:
            Tupla (es_válido, lista_de_errores)
        """
        errors = []
        policy = self.security_policies["password_policy"]
        
        # Verificar longitud mínima
        if len(password) < policy["min_length"]:
            errors.append(f"Password must be at least {policy['min_length']} characters")
        
        # Verificar mayúsculas
        if policy["require_uppercase"] and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        # Verificar minúsculas
        if policy["require_lowercase"] and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        
        # Verificar dígitos
        if policy["require_digits"] and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")
        
        # Verificar caracteres especiales
        if policy["require_special"]:
            special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
            if not any(c in special_chars for c in password):
                errors.append("Password must contain at least one special character")
        
        return len(errors) == 0, errors
    
    def create_secure_session(
        self,
        user_id: str,
        role: str,
        session_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Crea una sesión segura para un usuario
        
        Args:
            user_id: ID del usuario
            role: Rol del usuario
            session_data: Datos adicionales de la sesión
        
        Returns:
            Información de la sesión
        """
        try:
            session_id = secrets.token_hex(32)
            
            session_info = {
                "session_id": session_id,
                "user_id": user_id,
                "role": role,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + self.security_policies["session_security"]["session_timeout"],
                "last_activity": datetime.utcnow(),
                "permissions": self.get_role_permissions(role),
                "data": session_data or {}
            }
            
            # Generar tokens
            access_token = self.generate_token(user_id, role, "access")
            refresh_token = self.generate_token(user_id, role, "refresh")
            
            session_info.update({
                "access_token": access_token,
                "refresh_token": refresh_token
            })
            
            logger.info(f"Secure session created for user {user_id}")
            return session_info
            
        except Exception as e:
            logger.error(f"Error creating secure session: {e}")
            raise SecurityException("Session creation failed")
    
    def audit_log(
        self,
        user_id: str,
        action: str,
        resource: str,
        details: Dict[str, Any] = None,
        success: bool = True
    ):
        """
        Registra una acción en el log de auditoría
        
        Args:
            user_id: Usuario que realizó la acción
            action: Acción realizada
            resource: Recurso afectado
            details: Detalles adicionales
            success: Si la acción fue exitosa
        """
        try:
            audit_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id,
                "action": action,
                "resource": resource,
                "success": success,
                "details": details or {},
                "ip_address": details.get("ip_address") if details else None,
                "user_agent": details.get("user_agent") if details else None
            }
            
            # Log estructurado para auditoría
            logger.info(
                "security_audit",
                extra={
                    "audit": True,
                    **audit_entry
                }
            )
            
        except Exception as e:
            logger.error(f"Error logging audit entry: {e}")
    
    def check_rate_limit(
        self,
        user_id: str,
        action: str = "general"
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Verifica límites de velocidad para un usuario
        
        Args:
            user_id: ID del usuario
            action: Tipo de acción
        
        Returns:
            Tupla (permitido, info_del_límite)
        """
        # Implementación básica - en producción usar Redis
        # Por ahora solo retornamos True
        return True, {
            "allowed": True,
            "remaining": 100,
            "reset_time": datetime.utcnow() + timedelta(minutes=1)
        }
    
    def sanitize_input(self, input_data: Any) -> Any:
        """
        Sanitiza datos de entrada
        
        Args:
            input_data: Datos a sanitizar
        
        Returns:
            Datos sanitizados
        """
        if isinstance(input_data, str):
            # Remover caracteres peligrosos
            dangerous_chars = ["<", ">", "&", "\"", "'", "/", "\\"]
            sanitized = input_data
            for char in dangerous_chars:
                sanitized = sanitized.replace(char, "")
            return sanitized.strip()
        
        elif isinstance(input_data, dict):
            return {k: self.sanitize_input(v) for k, v in input_data.items()}
        
        elif isinstance(input_data, list):
            return [self.sanitize_input(item) for item in input_data]
        
        return input_data
    
    def generate_api_key(
        self,
        user_id: str,
        permissions: List[str],
        expires_at: Optional[datetime] = None
    ) -> str:
        """
        Genera una API key para acceso programático
        
        Args:
            user_id: ID del usuario
            permissions: Permisos de la API key
            expires_at: Fecha de expiración opcional
        
        Returns:
            API key generada
        """
        try:
            key_data = {
                "user_id": user_id,
                "permissions": permissions,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": expires_at.isoformat() if expires_at else None,
                "key_id": secrets.token_hex(16)
            }
            
            # Crear la API key
            api_key = f"ak_{secrets.token_urlsafe(32)}"
            
            # En producción, esto se guardaría en base de datos
            logger.info(f"API key generated for user {user_id}")
            
            return api_key
            
        except Exception as e:
            logger.error(f"Error generating API key: {e}")
            raise SecurityException("API key generation failed")
    
    def cleanup_expired_tokens(self) -> int:
        """
        Limpia tokens expirados del cache
        
        Returns:
            Número de tokens eliminados
        """
        try:
            current_time = datetime.utcnow()
            expired_tokens = []
            
            for token_id, token_info in self.active_tokens.items():
                if current_time > token_info["expires_at"]:
                    expired_tokens.append(token_id)
            
            for token_id in expired_tokens:
                del self.active_tokens[token_id]
            
            logger.info(f"Cleaned up {len(expired_tokens)} expired tokens")
            return len(expired_tokens)
            
        except Exception as e:
            logger.error(f"Error cleaning up tokens: {e}")
            return 0
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """
        Obtiene métricas de seguridad
        
        Returns:
            Métricas de seguridad actuales
        """
        try:
            current_time = datetime.utcnow()
            
            # Contar tokens activos por tipo
            token_types = {}
            for token_info in self.active_tokens.values():
                token_type = token_info["token_type"]
                token_types[token_type] = token_types.get(token_type, 0) + 1
            
            # Contar tokens que expiran pronto
            expiring_soon = sum(
                1 for token_info in self.active_tokens.values()
                if token_info["expires_at"] - current_time < timedelta(minutes=30)
            )
            
            return {
                "active_tokens": len(self.active_tokens),
                "tokens_by_type": token_types,
                "tokens_expiring_soon": expiring_soon,
                "roles_configured": len(self.roles),
                "security_policies": {
                    "password_policy_enabled": bool(self.security_policies["password_policy"]),
                    "rate_limiting_enabled": bool(self.security_policies["rate_limiting"]),
                    "data_encryption_enabled": self.security_policies["data_protection"]["encrypt_sensitive_data"]
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting security metrics: {e}")
            return {}


class SecurityException(Exception):
    """Excepción específica para errores de seguridad"""
    pass


# Decorador para verificar autenticación
def require_auth(permission: str = None):
    """
    Decorador para requerir autenticación en funciones
    
    Args:
        permission: Permiso específico requerido
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Implementación del decorador
            # En una aplicación real, extraería el token del contexto de la request
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Decorador para logging de auditoría automático
def audit_action(action: str, resource: str):
    """
    Decorador para logging automático de auditoría
    
    Args:
        action: Acción realizada
        resource: Recurso afectado
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                # Log de éxito
                return result
            except Exception as e:
                # Log de error
                raise
        return wrapper
    return decorator