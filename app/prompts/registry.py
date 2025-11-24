"""
PromptRegistry - Registro centralizado de todas las claves de prompts del sistema.

Este módulo define constantes tipo-seguro para referenciar prompts en todo el código.
Mejora el autocompletado y previene errores de typos.
"""


class PromptRegistry:
    """
    Registro centralizado de claves de prompts.

    Naming convention: {domain}.{subdomain}.{action}
    Ejemplo: "product.search.intent_analysis"
    """

    # === INTENT ANALYSIS ===
    INTENT_ANALYZER_SYSTEM = "intent.analyzer.system"
    INTENT_ANALYZER_USER = "intent.analyzer.user"
    INTENT_ROUTER_SYSTEM = "intent.router.system"

    # === PRODUCT ===
    PRODUCT_SEARCH_INTENT = "product.search.intent_analysis"
    PRODUCT_SEARCH_RESPONSE = "product.search.response"
    PRODUCT_SEARCH_NO_RESULTS = "product.search.no_results"
    PRODUCT_SEARCH_ERROR = "product.search.error"

    PRODUCT_SQL_COMPLEXITY = "product.sql.complexity_analysis"
    PRODUCT_SQL_GENERATION = "product.sql.generation"
    PRODUCT_SQL_AGGREGATION = "product.sql.aggregation"

    # === CONVERSATION ===
    CONVERSATION_GREETING_SYSTEM = "conversation.greeting.system"
    CONVERSATION_FAREWELL_SYSTEM = "conversation.farewell.system"
    CONVERSATION_SUPPORT_SYSTEM = "conversation.support.system"
    CONVERSATION_FALLBACK_SYSTEM = "conversation.fallback.system"

    # === ORCHESTRATOR ===
    ORCHESTRATOR_SUPER_SYSTEM = "orchestrator.super.system"
    ORCHESTRATOR_DOMAIN_ROUTER = "orchestrator.domain.router"
    ORCHESTRATOR_INTENT_DETECTION = "orchestrator.intent.detection"

    # === SALES ===
    SALES_ASSISTANT_SYSTEM = "sales.assistant.system"
    SALES_ASSISTANT_IMPROVED = "sales.assistant.improved"
    SALES_CROSS_SELL = "sales.cross_sell"
    SALES_UPSELL = "sales.upsell"

    # === CATEGORY ===
    CATEGORY_ANALYSIS = "category.analysis"
    CATEGORY_RECOMMENDATIONS = "category.recommendations"

    # === TRACKING ===
    TRACKING_ORDER_STATUS = "tracking.order.status"
    TRACKING_SHIPMENT_INFO = "tracking.shipment.info"

    # === INVOICE ===
    INVOICE_QUERY = "invoice.query"
    INVOICE_PAYMENT_INFO = "invoice.payment.info"

    # === CREDIT ===
    CREDIT_INTENT_ANALYSIS = "credit.intent.analysis"
    CREDIT_BALANCE_RESPONSE = "credit.balance.response"
    CREDIT_PAYMENT_CONFIRMATION = "credit.payment.confirmation"
    CREDIT_SCHEDULE_RESPONSE = "credit.schedule.response"

    # === HEALTHCARE ===
    HEALTHCARE_APPOINTMENT_INTENT = "healthcare.appointment.intent"
    HEALTHCARE_APPOINTMENT_CONFIRMATION = "healthcare.appointment.confirmation"
    HEALTHCARE_APPOINTMENT_LIST = "healthcare.appointment.list"
    HEALTHCARE_PATIENT_INTENT = "healthcare.patient.intent"
    HEALTHCARE_PATIENT_INFO_RESPONSE = "healthcare.patient.info_response"
    HEALTHCARE_PRESCRIPTION_RESPONSE = "healthcare.prescription.response"

    # === EXCELENCIA ===
    EXCELENCIA_QUERY_INTENT = "excelencia.query.intent"
    EXCELENCIA_RESPONSE_GENERAL = "excelencia.response.general"
    EXCELENCIA_DEMO_REQUEST = "excelencia.demo.request"
    EXCELENCIA_MODULE_INFO = "excelencia.module.info"

    # === AGENTS ===
    AGENTS_FAREWELL_CONTEXTUAL = "agents.farewell.contextual"
    AGENTS_FAREWELL_DEFAULT_INTERACTED = "agents.farewell.default_interacted"
    AGENTS_FAREWELL_DEFAULT_BRIEF = "agents.farewell.default_brief"
    AGENTS_FALLBACK_HELPFUL_RESPONSE = "agents.fallback.helpful_response"
    AGENTS_FALLBACK_DEFAULT_RESPONSE = "agents.fallback.default_response"
    AGENTS_FALLBACK_ERROR_RESPONSE = "agents.fallback.error_response"
    AGENTS_SUPERVISOR_ENHANCEMENT = "agents.supervisor.enhancement"

    # === ORCHESTRATOR (additional) ===
    ORCHESTRATOR_DOMAIN_DETECTION = "orchestrator.domain.detection"

    @classmethod
    def get_all_keys(cls) -> list[str]:
        """Retorna todas las claves de prompts registradas."""
        return [
            value
            for key, value in cls.__dict__.items()
            if not key.startswith("_") and isinstance(value, str) and "." in value
        ]

    @classmethod
    def get_by_domain(cls, domain: str) -> list[str]:
        """
        Retorna todas las claves de un dominio específico.

        Args:
            domain: El dominio a filtrar (ej: "product", "intent", "conversation")

        Returns:
            Lista de claves que pertenecen al dominio
        """
        all_keys = cls.get_all_keys()
        return [key for key in all_keys if key.startswith(f"{domain}.")]

    @classmethod
    def validate_key(cls, key: str) -> bool:
        """
        Valida si una clave existe en el registro.

        Args:
            key: La clave a validar

        Returns:
            True si la clave existe, False en caso contrario
        """
        return key in cls.get_all_keys()
