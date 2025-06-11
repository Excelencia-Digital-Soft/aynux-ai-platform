"""
Configuración específica para el sistema LangGraph multi-agente
"""
import os
from typing import Any, Dict, Optional

from app.config.settings import get_settings


class LangGraphConfig:
    """Configuración centralizada para el sistema LangGraph"""
    
    def __init__(self):
        self.settings = get_settings()
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Carga la configuración completa del sistema"""
        return {
            # Configuración de base de datos
            "database": self._get_database_config(),
            
            # Configuración de servicios externos
            "external_services": self._get_external_services_config(),
            
            # Configuración de agentes
            "agents": self._get_agents_config(),
            
            # Configuración de monitoreo
            "monitoring": self._get_monitoring_config(),
            
            # Configuración de seguridad
            "security": self._get_security_config(),
            
            # Configuración de performance
            "performance": self._get_performance_config(),
            
            # Configuración de fallbacks
            "fallbacks": self._get_fallbacks_config()
        }
    
    def _get_database_config(self) -> Dict[str, Any]:
        """Configuración de base de datos"""
        return {
            "primary_db_url": self.settings.database_url,
            "redis_url": getattr(self.settings, 'REDIS_URL', 'redis://localhost:6379'),
            "chromadb_path": getattr(self.settings, 'CHROMADB_PATH', './data/chromadb'),
            "connection_pool": {
                "min_size": 5,
                "max_size": 20,
                "pool_recycle": 3600
            },
            "checkpointing": {
                "enabled": True,
                "cleanup_interval": 3600,  # 1 hora
                "retention_days": 30
            }
        }
    
    def _get_external_services_config(self) -> Dict[str, Any]:
        """Configuración de servicios externos"""
        return {
            "ollama": {
                "base_url": getattr(self.settings, 'OLLAMA_API_URL', 'http://localhost:11434'),
                "model": getattr(self.settings, 'OLLAMA_MODEL', 'llama3.1:8b'),
                "embedding_model": getattr(self.settings, 'OLLAMA_EMBEDDING_MODEL', 'nomic-embed-text'),
                "timeout": 30,
                "max_retries": 3,
                "temperature": 0.7
            },
            "whatsapp": {
                "api_url": getattr(self.settings, 'WHATSAPP_API_URL', ''),
                "token": getattr(self.settings, 'WHATSAPP_ACCESS_TOKEN', ''),
                "verify_token": getattr(self.settings, 'WHATSAPP_VERIFY_TOKEN', ''),
                "webhook_url": getattr(self.settings, 'WHATSAPP_WEBHOOK_URL', '')
            },
            "shipping_apis": {
                "correo_argentino": {
                    "api_key": os.getenv('SHIPPING_API_KEY'),
                    "enabled": os.getenv('SHIPPING_ENABLED', 'false').lower() == 'true'
                },
                "oca": {
                    "api_key": os.getenv('OCA_API_KEY'),
                    "enabled": os.getenv('OCA_ENABLED', 'false').lower() == 'true'
                }
            },
            "invoice_api": {
                "provider": os.getenv('INVOICE_PROVIDER', 'local'),
                "api_key": os.getenv('INVOICE_API_KEY'),
                "enabled": os.getenv('INVOICE_ENABLED', 'false').lower() == 'true'
            }
        }
    
    def _get_agents_config(self) -> Dict[str, Any]:
        """Configuración específica de agentes"""
        return {
            "category_agent": {
                "enabled": True,
                "max_categories_shown": 6,
                "vector_search_k": 5,
                "confidence_threshold": 0.7
            },
            "product_agent": {
                "enabled": True,
                "max_products_shown": 5,
                "price_format": "ARS",
                "show_stock": True,
                "vector_search_k": 10
            },
            "promotions_agent": {
                "enabled": True,
                "max_promotions_shown": 3,
                "check_expiry": True,
                "personalization": True
            },
            "tracking_agent": {
                "enabled": True,
                "shipping_providers": ["correo_argentino", "oca"],
                "update_interval": 3600  # 1 hora
            },
            "support_agent": {
                "enabled": True,
                "knowledge_sources": ["faq", "manuals", "policies"],
                "escalation_keywords": ["gerente", "queja", "problema", "devolucion"],
                "max_attempts": 3
            },
            "invoice_agent": {
                "enabled": True,
                "tax_rate": 21.0,  # IVA en Argentina
                "currency": "ARS",
                "auto_generate": False
            }
        }
    
    def _get_monitoring_config(self) -> Dict[str, Any]:
        """Configuración de monitoreo"""
        return {
            "enabled": True,
            "prometheus": {
                "enabled": os.getenv('PROMETHEUS_ENABLED', 'false').lower() == 'true',
                "port": int(os.getenv('PROMETHEUS_PORT', '8001'))
            },
            "logging": {
                "level": os.getenv('LOG_LEVEL', 'INFO'),
                "structured": True,
                "file_path": os.getenv('LOG_FILE_PATH', './logs/langgraph.log')
            },
            "metrics": {
                "response_time_threshold": 3.0,  # 3 segundos
                "error_rate_threshold": 0.05,   # 5%
                "session_timeout": 7200         # 2 horas
            },
            "alerting": {
                "enabled": True,
                "webhook_url": os.getenv('ALERT_WEBHOOK_URL'),
                "email": os.getenv('ALERT_EMAIL')
            }
        }
    
    def _get_security_config(self) -> Dict[str, Any]:
        """Configuración de seguridad"""
        return {
            "authentication": {
                "jwt_secret": os.getenv('JWT_SECRET', 'change-this-in-production'),
                "token_expiry": 7200,  # 2 horas
                "refresh_token_expiry": 604800  # 7 días
            },
            "encryption": {
                "key": os.getenv('ENCRYPTION_KEY'),
                "algorithm": "fernet"
            },
            "rate_limiting": {
                "enabled": True,
                "requests_per_minute": 30,
                "requests_per_hour": 500
            },
            "rbac": {
                "enabled": True,
                "default_role": "customer",
                "admin_users": os.getenv('ADMIN_USERS', '').split(',') if os.getenv('ADMIN_USERS') else []
            },
            "data_protection": {
                "encrypt_pii": True,
                "audit_logs": True,
                "data_retention_days": 365
            }
        }
    
    def _get_performance_config(self) -> Dict[str, Any]:
        """Configuración de rendimiento"""
        return {
            "response_targets": {
                "max_response_time": 3.0,  # 3 segundos
                "target_response_time": 1.5,  # 1.5 segundos
                "timeout": 10.0  # 10 segundos
            },
            "caching": {
                "enabled": True,
                "ttl": 3600,  # 1 hora
                "max_size": 1000
            },
            "concurrency": {
                "max_concurrent_sessions": 100,
                "max_concurrent_requests": 200,
                "agent_pool_size": 10
            },
            "optimization": {
                "lazy_loading": True,
                "vector_cache": True,
                "model_pooling": True
            }
        }
    
    def _get_fallbacks_config(self) -> Dict[str, Any]:
        """Configuración de fallbacks y recuperación"""
        return {
            "enable_fallbacks": True,
            "traditional_service": {
                "enabled": True,
                "switch_threshold": 3  # Número de errores consecutivos
            },
            "offline_mode": {
                "enabled": True,
                "canned_responses": True,
                "basic_keywords": True
            },
            "circuit_breaker": {
                "enabled": True,
                "failure_threshold": 5,
                "recovery_timeout": 60,
                "half_open_max_calls": 3
            },
            "retry_policy": {
                "max_retries": 3,
                "backoff_factor": 2,
                "max_backoff": 30
            }
        }
    
    def get_config(self) -> Dict[str, Any]:
        """Obtiene la configuración completa"""
        return self._config
    
    def get_section(self, section: str) -> Optional[Dict[str, Any]]:
        """Obtiene una sección específica de la configuración"""
        return self._config.get(section)
    
    def get_value(self, path: str, default: Any = None) -> Any:
        """
        Obtiene un valor específico usando notación de punto
        
        Args:
            path: Ruta al valor (ej: "database.connection_pool.max_size")
            default: Valor por defecto si no se encuentra
        """
        keys = path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def update_config(self, updates: Dict[str, Any]):
        """Actualiza la configuración con nuevos valores"""
        def deep_update(base_dict, update_dict):
            for key, value in update_dict.items():
                if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                    deep_update(base_dict[key], value)
                else:
                    base_dict[key] = value
        
        deep_update(self._config, updates)
    
    def validate_config(self) -> Dict[str, bool]:
        """Valida la configuración y retorna el estado de cada sección"""
        validation_results = {}
        
        # Validar base de datos
        validation_results['database'] = bool(self.get_value('database.primary_db_url'))
        
        # Validar Ollama
        validation_results['ollama'] = bool(
            self.get_value('external_services.ollama.base_url') and
            self.get_value('external_services.ollama.model')
        )
        
        # Validar WhatsApp
        validation_results['whatsapp'] = bool(
            self.get_value('external_services.whatsapp.token') and
            self.get_value('external_services.whatsapp.verify_token')
        )
        
        # Validar seguridad
        validation_results['security'] = bool(
            self.get_value('security.authentication.jwt_secret') != 'change-this-in-production'
        )
        
        return validation_results
    
    def export_config(self, safe_mode: bool = True) -> Dict[str, Any]:
        """
        Exporta la configuración para debug/logging
        
        Args:
            safe_mode: Si True, oculta información sensible
        """
        config_copy = self._config.copy()
        
        if safe_mode:
            # Ocultar información sensible
            sensitive_paths = [
                'security.authentication.jwt_secret',
                'security.encryption.key',
                'external_services.whatsapp.token',
                'external_services.ollama.api_key'
            ]
            
            for path in sensitive_paths:
                keys = path.split('.')
                current = config_copy
                
                for key in keys[:-1]:
                    if key in current:
                        current = current[key]
                    else:
                        break
                else:
                    if keys[-1] in current:
                        current[keys[-1]] = "***HIDDEN***"
        
        return config_copy


# Instancia global de configuración
_langgraph_config = None


def get_langgraph_config() -> LangGraphConfig:
    """Obtiene la instancia global de configuración LangGraph"""
    global _langgraph_config
    if _langgraph_config is None:
        _langgraph_config = LangGraphConfig()
    return _langgraph_config


def reload_langgraph_config():
    """Recarga la configuración LangGraph"""
    global _langgraph_config
    _langgraph_config = LangGraphConfig()
    return _langgraph_config