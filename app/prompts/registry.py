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
    PRODUCT_SEARCH_SIMPLE_INTENT = "product.search.simple_intent"
    PRODUCT_CATEGORY_RESPONSE = "product.category.response"
    PRODUCT_FEATURED_RESPONSE = "product.featured.response"

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
    ORCHESTRATOR_ERROR_RESPONSE = "orchestrator.error.response"

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

    # === EXCELENCIA SUPPORT (RAG-based) ===
    EXCELENCIA_SUPPORT_RESPONSE = "excelencia.support.response"
    EXCELENCIA_SUPPORT_TRAINING = "excelencia.support.training"
    EXCELENCIA_SUPPORT_INCIDENT_CONFIRMATION = "excelencia.support.incident_confirmation"
    EXCELENCIA_SUPPORT_FEEDBACK_CONFIRMATION = "excelencia.support.feedback_confirmation"
    EXCELENCIA_SUPPORT_FALLBACK = "excelencia.support.fallback"
    EXCELENCIA_SUPPORT_TRAINING_FALLBACK = "excelencia.support.training_fallback"

    # === AGENTS ===
    AGENTS_FAREWELL_CONTEXTUAL = "agents.farewell.contextual"
    AGENTS_FAREWELL_DEFAULT_INTERACTED = "agents.farewell.default_interacted"
    AGENTS_FAREWELL_DEFAULT_BRIEF = "agents.farewell.default_brief"
    AGENTS_FALLBACK_HELPFUL_RESPONSE = "agents.fallback.helpful_response"
    AGENTS_FALLBACK_DEFAULT_RESPONSE = "agents.fallback.default_response"
    AGENTS_FALLBACK_ERROR_RESPONSE = "agents.fallback.error_response"
    AGENTS_SUPERVISOR_ENHANCEMENT = "agents.supervisor.enhancement"
    AGENTS_SERVICES_CONFIG = "agents.services.config"

    # === SUPPORT AGENT ===
    AGENTS_SUPPORT_RESPONSE_PAYMENT = "agents.support.response.payment"
    AGENTS_SUPPORT_RESPONSE_DELIVERY = "agents.support.response.delivery"
    AGENTS_SUPPORT_RESPONSE_PRODUCT = "agents.support.response.product"
    AGENTS_SUPPORT_RESPONSE_ACCOUNT = "agents.support.response.account"
    AGENTS_SUPPORT_RESPONSE_RETURN = "agents.support.response.return"
    AGENTS_SUPPORT_RESPONSE_TECHNICAL = "agents.support.response.technical"
    AGENTS_SUPPORT_RESPONSE_GENERAL = "agents.support.response.general"
    AGENTS_SUPPORT_EXCELENCIA_GENERAL = "agents.support.excelencia.general"
    AGENTS_SUPPORT_EXCELENCIA_MODULE = "agents.support.excelencia.module_response"
    # Support FAQ
    AGENTS_SUPPORT_FAQ_PAYMENT_REJECTED = "agents.support.faq.payment.rejected_card"
    AGENTS_SUPPORT_FAQ_PAYMENT_METHODS = "agents.support.faq.payment.methods"
    AGENTS_SUPPORT_FAQ_DELIVERY_TIME = "agents.support.faq.delivery.time"
    AGENTS_SUPPORT_FAQ_EXCELENCIA_LICENSE = "agents.support.faq.excelencia.license"
    AGENTS_SUPPORT_FAQ_EXCELENCIA_TRAINING = "agents.support.faq.excelencia.training"
    AGENTS_SUPPORT_FAQ_EXCELENCIA_UPDATE = "agents.support.faq.excelencia.update"
    AGENTS_SUPPORT_FAQ_EXCELENCIA_BACKUP = "agents.support.faq.excelencia.backup"
    AGENTS_SUPPORT_FAQ_EXCELENCIA_TIMBRADO = "agents.support.faq.excelencia.timbrado"
    AGENTS_SUPPORT_FAQ_EXCELENCIA_CANCEL = "agents.support.faq.excelencia.cancel_invoice"
    AGENTS_SUPPORT_FAQ_EXCELENCIA_MONTH_CLOSE = "agents.support.faq.excelencia.month_close"
    AGENTS_SUPPORT_FAQ_EXCELENCIA_NEGATIVE_STOCK = "agents.support.faq.excelencia.negative_stock"
    AGENTS_SUPPORT_FAQ_GENERAL_SCHEDULE = "agents.support.faq.general.schedule"
    AGENTS_SUPPORT_FAQ_GENERAL_CONTACT = "agents.support.faq.general.contact"

    # === DATA INSIGHTS AGENT ===
    AGENTS_DATA_INSIGHTS_CLASSIFICATION = "agents.data_insights.query_classification"
    AGENTS_DATA_INSIGHTS_RESPONSE = "agents.data_insights.response_generation"
    AGENTS_DATA_INSIGHTS_NO_RESULTS = "agents.data_insights.no_results"
    AGENTS_DATA_INSIGHTS_ERROR = "agents.data_insights.error_response"
    AGENTS_DATA_INSIGHTS_FALLBACK = "agents.data_insights.fallback"

    # === FALLBACK AGENT (Multi-language) ===
    AGENTS_FALLBACK_DYNAMIC_ES = "agents.fallback.dynamic.es"
    AGENTS_FALLBACK_DYNAMIC_EN = "agents.fallback.dynamic.en"
    AGENTS_FALLBACK_DYNAMIC_PT = "agents.fallback.dynamic.pt"
    AGENTS_FALLBACK_DEFAULT_ES = "agents.fallback.default.es"
    AGENTS_FALLBACK_DEFAULT_EN = "agents.fallback.default.en"
    AGENTS_FALLBACK_DEFAULT_PT = "agents.fallback.default.pt"
    AGENTS_FALLBACK_ERROR_ES = "agents.fallback.error.es"
    AGENTS_FALLBACK_ERROR_EN = "agents.fallback.error.en"
    AGENTS_FALLBACK_ERROR_PT = "agents.fallback.error.pt"

    # === GREETING AGENT ===
    AGENTS_GREETING_FALLBACK_ES = "agents.greeting.fallback.es"
    AGENTS_GREETING_FALLBACK_EN = "agents.greeting.fallback.en"
    AGENTS_GREETING_FALLBACK_PT = "agents.greeting.fallback.pt"
    AGENTS_GREETING_FALLBACK_GENERIC = "agents.greeting.fallback.generic"

    # === HISTORY AGENT ===
    AGENTS_HISTORY_SUMMARIZE = "agents.history.summarize"
    AGENTS_HISTORY_EXTRACT_ENTITIES = "agents.history.extract_entities"

    # === EXCELENCIA INVOICE ===
    EXCELENCIA_INVOICE_INTENT = "excelencia.invoice.intent_analysis"
    EXCELENCIA_INVOICE_RESPONSE = "excelencia.invoice.response_generation"
    EXCELENCIA_INVOICE_FALLBACK_INVOICE = "excelencia.invoice.fallback.invoice"
    EXCELENCIA_INVOICE_FALLBACK_STATEMENT = "excelencia.invoice.fallback.statement"
    EXCELENCIA_INVOICE_FALLBACK_COLLECTION = "excelencia.invoice.fallback.collection"
    EXCELENCIA_INVOICE_FALLBACK_PAYMENT = "excelencia.invoice.fallback.payment"
    EXCELENCIA_INVOICE_FALLBACK_GENERAL = "excelencia.invoice.fallback.general"
    EXCELENCIA_INVOICE_ERROR = "excelencia.invoice.error"

    # === EXCELENCIA PROMOTIONS ===
    EXCELENCIA_PROMOTIONS_INTENT = "excelencia.promotions.intent_analysis"
    EXCELENCIA_PROMOTIONS_RESPONSE = "excelencia.promotions.response_generation"
    EXCELENCIA_PROMOTIONS_FALLBACK_DISCOUNT = "excelencia.promotions.fallback.discount"
    EXCELENCIA_PROMOTIONS_FALLBACK_BUNDLE = "excelencia.promotions.fallback.bundle"
    EXCELENCIA_PROMOTIONS_FALLBACK_TRAINING = "excelencia.promotions.fallback.training"
    EXCELENCIA_PROMOTIONS_FALLBACK_IMPLEMENTATION = "excelencia.promotions.fallback.implementation"
    EXCELENCIA_PROMOTIONS_FALLBACK_GENERAL = "excelencia.promotions.fallback.general"
    EXCELENCIA_PROMOTIONS_ERROR = "excelencia.promotions.error"

    # === ORCHESTRATOR (additional) ===
    ORCHESTRATOR_DOMAIN_DETECTION = "orchestrator.domain.detection"
    ORCHESTRATOR_DOMAIN_CLASSIFICATION = "orchestrator.domain.classification"

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
