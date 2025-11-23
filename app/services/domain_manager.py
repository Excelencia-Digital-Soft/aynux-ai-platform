"""
Domain Manager - Factory pattern para servicios de dominio

DEPRECATED: Reemplazado por SuperOrchestrator con domain-specific agents
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

from app.config.settings import get_settings
from app.core.shared.deprecation import deprecated
from app.models.message import BotResponse, Contact, WhatsAppMessage

logger = logging.getLogger(__name__)


@deprecated(
    reason="Legacy domain service factory replaced by SuperOrchestrator with domain agents",
    replacement="Use SuperOrchestrator (app/orchestration/) + Domain Agents (app/domains/*/agents/)",
    removal_version="2.0.0",
)
class BaseDomainService(ABC):
    """
    Clase base abstracta para todos los servicios de dominio.

    DEPRECATED: Este patrón de factory con herencia ha sido reemplazado
    por SuperOrchestrator con domain-specific agents siguiendo Clean Architecture.

    Problemas del enfoque legacy:
    - Tight coupling a WhatsApp models (Contact, WhatsAppMessage)
    - Factory pattern complejo para agregar dominios
    - Herencia forzada (todos extienden BaseDomainService)
    - Difícil testear (requiere objetos WhatsApp reales)
    - No usa interfaces (ABC vs Protocol)

    Ventajas de nueva arquitectura:
    - Domain Agents independientes (IAgent interface)
    - SuperOrchestrator maneja routing automáticamente
    - No coupling a WhatsApp (state-based, platform-agnostic)
    - Testeable con mocks simples
    - Composition over inheritance

    Define la interfaz común que deben implementar todos los
    servicios especializados por dominio.

    Migración recomendada:
        # ❌ Antes (legacy)
        from app.services.domain_manager import get_domain_manager

        domain_manager = get_domain_manager()
        service = domain_manager.get_service("ecommerce")
        response = await service.process_webhook_message(message, contact)

        # ✅ Después (Clean Architecture)
        from app.core.container import get_container

        container = get_container()
        orchestrator = container.create_super_orchestrator()

        state = {
            "messages": [{"role": "user", "content": message.text}],
            "user_id": contact.phone,
        }

        result = await orchestrator.route_message(state)
        # result["messages"][-1]["content"] contiene la respuesta
    """

    def __init__(self, domain: str, config: Optional[Dict[str, Any]] = None):
        self.domain = domain
        self.config = config or {}
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> None:
        """
        Inicializar el servicio de forma asíncrona
        Debe implementarse en cada servicio específico
        """
        pass

    @abstractmethod
    async def process_webhook_message(self, message: WhatsAppMessage, contact: Contact) -> BotResponse:
        """
        Procesar mensaje de WhatsApp para este dominio específico
        
        Args:
            message: Mensaje de WhatsApp recibido
            contact: Información de contacto del usuario
            
        Returns:
            Respuesta estructurada del bot
        """
        pass

    @abstractmethod
    async def get_system_health(self) -> Dict[str, Any]:
        """
        Obtener estado de salud del sistema de este dominio
        
        Returns:
            Dict con información de salud del sistema
        """
        pass

    async def get_conversation_history(self, user_number: str, limit: int = 50) -> Dict[str, Any]:
        """
        Obtener historial de conversación (implementación por defecto)
        
        Args:
            user_number: Número de usuario
            limit: Límite de mensajes
            
        Returns:
            Historial de conversación
        """
        # Implementación básica - puede ser sobrescrita por servicios específicos
        return {
            "user_number": user_number,
            "domain": self.domain,
            "messages": [],
            "total": 0,
            "limit": limit,
            "note": "Default implementation - override in specific domain service"
        }

    def is_initialized(self) -> bool:
        """Verificar si el servicio está inicializado"""
        return self._initialized

    def get_domain_info(self) -> Dict[str, Any]:
        """Obtener información del dominio"""
        return {
            "domain": self.domain,
            "service_class": self.__class__.__name__,
            "initialized": self._initialized,
            "config": self.config,
        }


class EcommerceDomainService(BaseDomainService):
    """
    Servicio de dominio para E-commerce
    Wrapper del servicio LangGraph existente
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("ecommerce", config)
        self._langgraph_service = None

    async def initialize(self) -> None:
        """Inicializar servicio e-commerce usando LangGraph existente"""
        try:
            # Import lazy para evitar dependencias circulares
            from app.services.langgraph_chatbot_service import LangGraphChatbotService
            
            self._langgraph_service = LangGraphChatbotService()
            await self._langgraph_service.initialize()
            
            self._initialized = True
            self.logger.info("EcommerceDomainService initialized with LangGraph")
            
        except Exception as e:
            self.logger.error(f"Error initializing EcommerceDomainService: {e}")
            raise

    async def process_webhook_message(self, message: WhatsAppMessage, contact: Contact) -> BotResponse:
        """Procesar mensaje usando el servicio LangGraph existente"""
        if not self._initialized:
            await self.initialize()

        # Pasar el dominio al servicio de LangGraph
        return await self._langgraph_service.process_webhook_message(
            message, contact, business_domain=self.domain
        )

    async def get_system_health(self) -> Dict[str, Any]:
        """Obtener salud del sistema e-commerce"""
        if not self._initialized:
            return {"status": "not_initialized", "domain": self.domain}
        
        return await self._langgraph_service.get_system_health()

    async def get_conversation_history(self, user_number: str, limit: int = 50) -> Dict[str, Any]:
        """Obtener historial usando LangGraph service"""
        if not self._initialized:
            await self.initialize()
        
        return await self._langgraph_service.get_conversation_history_langgraph(user_number, limit)


class HospitalDomainService(BaseDomainService):
    """
    Servicio de dominio para Hospital
    Implementación básica que se expandirá
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("hospital", config)

    async def initialize(self) -> None:
        """Inicializar servicio hospitalario"""
        try:
            # TODO: Implementar inicialización del sistema hospitalario
            # - Cargar agentes médicos
            # - Configurar base de conocimiento médico
            # - Inicializar integraciones con sistemas hospitalarios
            
            self._initialized = True
            self.logger.info("HospitalDomainService initialized (basic implementation)")
            
        except Exception as e:
            self.logger.error(f"Error initializing HospitalDomainService: {e}")
            raise

    async def process_webhook_message(self, message: WhatsAppMessage, contact: Contact) -> BotResponse:
        """Procesar mensaje médico"""
        if not self._initialized:
            await self.initialize()
        
        # Implementación básica - respuesta estática
        user_number = contact.wa_id
        message_text = message.text.body if message.text else "Mensaje no de texto"
        
        response_text = f"""🏥 **Sistema Hospitalario - En Desarrollo**

Hola! Soy el asistente médico virtual. Actualmente estoy en desarrollo.

📋 **Servicios Disponibles (Próximamente):**
- 📅 Agendar citas médicas
- 👨‍⚕️ Consultar especialistas disponibles
- 🆘 Atención de urgencias
- 📞 Información de contacto

📞 **Para urgencias médicas, llama al 107**

Tu mensaje: "{message_text[:100]}..."
Contacto: {user_number}

Pronto tendré funcionalidades completas. ¡Gracias por tu paciencia!"""

        self.logger.info(f"Hospital message processed: {user_number}")
        
        return BotResponse(status="success", message=response_text)

    async def get_system_health(self) -> Dict[str, Any]:
        """Obtener salud del sistema hospitalario"""
        return {
            "status": "development" if self._initialized else "not_initialized",
            "domain": self.domain,
            "services": {
                "appointments": "not_implemented",
                "emergency": "not_implemented", 
                "specialists": "not_implemented",
            },
            "note": "Hospital domain service in development"
        }


class ExcelenciaDomainService(BaseDomainService):
    """
    Servicio de dominio para Software Excelencia
    Demo y soporte del ERP
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("excelencia", config)

    async def initialize(self) -> None:
        """Inicializar servicio de software Excelencia"""
        try:
            # TODO: Implementar inicialización del sistema Excelencia
            # - Cargar documentación del software
            # - Configurar demos interactivas
            # - Preparar casos de uso
            
            self._initialized = True
            self.logger.info("ExcelenciaDomainService initialized (basic implementation)")
            
        except Exception as e:
            self.logger.error(f"Error initializing ExcelenciaDomainService: {e}")
            raise

    async def process_webhook_message(self, message: WhatsAppMessage, contact: Contact) -> BotResponse:
        """Procesar consulta sobre software Excelencia"""
        if not self._initialized:
            await self.initialize()
        
        user_number = contact.wa_id
        message_text = message.text.body if message.text else "Mensaje no de texto"
        
        response_text = f"""💻 **Software Excelencia - ERP Empresarial**

¡Hola! Soy tu asistente especializado en el Software Excelencia.

🚀 **¿Qué puedo hacer por ti?**
- 📊 Demostrar funcionalidades del ERP
- 📋 Explicar módulos disponibles
- 🎯 Mostrar casos de uso específicos
- 🛠️ Brindar soporte técnico
- 📞 Coordinar reuniones comerciales

💡 **Módulos Principales:**
- Contabilidad y Finanzas
- Gestión de Inventarios  
- Recursos Humanos
- Ventas y CRM
- Reportes y Analytics

Tu consulta: "{message_text[:100]}..."

¿En qué módulo te gustaría que me enfoque? ¡Estoy aquí para ayudarte!"""

        self.logger.info(f"Excelencia message processed: {user_number}")
        
        return BotResponse(status="success", message=response_text)

    async def get_system_health(self) -> Dict[str, Any]:
        """Obtener salud del sistema Excelencia"""
        return {
            "status": "development" if self._initialized else "not_initialized",
            "domain": self.domain,
            "modules": {
                "accounting": "demo_available",
                "inventory": "demo_available",
                "hr": "demo_available",
                "sales": "demo_available",
                "reports": "demo_available",
            },
            "note": "Excelencia domain service in development"
        }


class CreditDomainService(BaseDomainService):
    """
    Servicio de dominio para Créditos
    Servicios financieros y préstamos
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("credit", config)

    async def initialize(self) -> None:
        """Inicializar servicio crediticio"""
        try:
            # TODO: Implementar inicialización del sistema crediticio
            # - Configurar validaciones financieras
            # - Cargar productos crediticios
            # - Integrar con sistemas de scoring
            
            self._initialized = True
            self.logger.info("CreditDomainService initialized (basic implementation)")
            
        except Exception as e:
            self.logger.error(f"Error initializing CreditDomainService: {e}")
            raise

    async def process_webhook_message(self, message: WhatsAppMessage, contact: Contact) -> BotResponse:
        """Procesar consulta crediticia"""
        if not self._initialized:
            await self.initialize()
        
        user_number = contact.wa_id
        message_text = message.text.body if message.text else "Mensaje no de texto"
        
        response_text = f"""💰 **Servicios Crediticios - En Desarrollo**

¡Hola! Soy tu asesor financiero virtual.

🏦 **Servicios Disponibles (Próximamente):**
- 💳 Préstamos personales
- 🏠 Créditos hipotecarios  
- 🚗 Financiamiento vehicular
- 💼 Créditos empresariales
- 📊 Análisis crediticio

📋 **Para evaluar tu solicitud necesitaré:**
- DNI y datos personales
- Comprobantes de ingresos
- Historial crediticio

Tu consulta: "{message_text[:100]}..."
Contacto: {user_number}

⚠️ **Importante:** Este servicio está en desarrollo. Para consultas urgentes, contacta directamente con nuestro equipo comercial."""

        self.logger.info(f"Credit message processed: {user_number}")
        
        return BotResponse(status="success", message=response_text)

    async def get_system_health(self) -> Dict[str, Any]:
        """Obtener salud del sistema crediticio"""
        return {
            "status": "development" if self._initialized else "not_initialized",
            "domain": self.domain,
            "services": {
                "personal_loans": "not_implemented",
                "mortgage": "not_implemented",
                "vehicle_financing": "not_implemented",
                "business_credit": "not_implemented",
            },
            "note": "Credit domain service in development"
        }


class DomainManager:
    """
    Manager que implementa el patrón Factory para servicios de dominio
    
    Gestiona la creación, inicialización y ciclo de vida de los
    servicios especializados por dominio.
    """

    # Registro de servicios disponibles
    DOMAIN_REGISTRY: Dict[str, Type[BaseDomainService]] = {
        "ecommerce": EcommerceDomainService,
        "hospital": HospitalDomainService,
        "excelencia": ExcelenciaDomainService,
        "credit": CreditDomainService,
    }

    def __init__(self):
        self.settings = get_settings()
        self._services: Dict[str, BaseDomainService] = {}
        self._initialized_domains = set()
        
        logger.info(f"DomainManager initialized with {len(self.DOMAIN_REGISTRY)} registered domains")

    async def get_service(self, domain: str) -> Optional[BaseDomainService]:
        """
        Obtener servicio para un dominio específico
        
        Args:
            domain: Nombre del dominio
            
        Returns:
            Instancia del servicio de dominio o None si no existe
        """
        # Verificar si el dominio está registrado
        if domain not in self.DOMAIN_REGISTRY:
            logger.warning(f"Domain not registered: {domain}")
            return None
        
        # Verificar si el servicio ya está instanciado
        if domain in self._services:
            service = self._services[domain]
            if not service.is_initialized():
                await service.initialize()
            return service
        
        # Crear nueva instancia del servicio
        try:
            service_class = self.DOMAIN_REGISTRY[domain]
            config = self._get_domain_config(domain)
            
            service = service_class(config)
            await service.initialize()
            
            self._services[domain] = service
            self._initialized_domains.add(domain)
            
            logger.info(f"Domain service created and initialized: {domain}")
            return service
            
        except Exception as e:
            logger.error(f"Error creating service for domain {domain}: {e}")
            return None

    def _get_domain_config(self, domain: str) -> Dict[str, Any]:
        """Obtener configuración específica para un dominio"""
        # TODO: Cargar desde variables de entorno o base de datos
        base_config = {
            "domain": domain,
            "enabled": True,
        }
        
        # Configuraciones específicas por dominio
        domain_configs = {
            "ecommerce": {
                "model": getattr(self.settings, "ECOMMERCE_MODEL", "deepseek-r1:7b"),
                "vector_collection": "products",
            },
            "hospital": {
                "model": getattr(self.settings, "HOSPITAL_MODEL", "deepseek-r1:7b"),
                "vector_collection": "medical_knowledge",
            },
            "excelencia": {
                "model": getattr(self.settings, "EXCELENCIA_MODEL", "deepseek-r1:7b"),
                "vector_collection": "software_knowledge",
            },
            "credit": {
                "model": getattr(self.settings, "CREDIT_MODEL", "deepseek-r1:7b"),
                "vector_collection": "credit_products",
            },
        }
        
        return {**base_config, **domain_configs.get(domain, {})}

    def get_available_domains(self) -> List[str]:
        """Obtener lista de dominios disponibles"""
        return list(self.DOMAIN_REGISTRY.keys())

    def get_initialized_domains(self) -> List[str]:
        """Obtener lista de dominios inicializados"""
        return list(self._initialized_domains)

    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Verificar salud de todos los dominios"""
        health_status = {}
        
        for domain in self.DOMAIN_REGISTRY.keys():
            try:
                service = await self.get_service(domain)
                if service:
                    health_status[domain] = await service.get_system_health()
                else:
                    health_status[domain] = {
                        "status": "unavailable",
                        "error": "Service could not be created"
                    }
            except Exception as e:
                health_status[domain] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return health_status

    @classmethod
    def register_domain(cls, domain: str, service_class: Type[BaseDomainService]):
        """
        Registrar un nuevo tipo de servicio de dominio
        
        Args:
            domain: Nombre del dominio
            service_class: Clase del servicio
        """
        cls.DOMAIN_REGISTRY[domain] = service_class
        logger.info(f"Registered new domain service: {domain} -> {service_class.__name__}")


# Instancia global del manager
_global_manager: Optional[DomainManager] = None


def get_domain_manager() -> DomainManager:
    """
    Obtener instancia global del domain manager (singleton)
    
    Returns:
        Instancia de DomainManager
    """
    global _global_manager
    
    if _global_manager is None:
        _global_manager = DomainManager()
    
    return _global_manager