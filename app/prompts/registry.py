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

    # === ECOMMERCE ===
    ECOMMERCE_ROUTER_INTENT_CLASSIFIER = "ecommerce.router.intent_classifier"
    ECOMMERCE_ROUTER_USER_CONTEXT = "ecommerce.router.user_context"
    ECOMMERCE_PRODUCT_RESPONSE = "ecommerce.product.response"
    ECOMMERCE_PRODUCT_NO_RESULTS = "ecommerce.product.no_results"
    ECOMMERCE_PRODUCT_STOCK_ALL_AVAILABLE = "ecommerce.product.stock_info.all_available"
    ECOMMERCE_PRODUCT_STOCK_MIXED = "ecommerce.product.stock_info.mixed"
    ECOMMERCE_PRODUCT_STOCK_NONE_AVAILABLE = "ecommerce.product.stock_info.none_available"
    # E-commerce Product SQL System Prompts
    ECOMMERCE_PRODUCT_SQL_BUILDER_SYSTEM = "ecommerce.product_sql.builder_system"
    ECOMMERCE_PRODUCT_SQL_AGGREGATION_SYSTEM = "ecommerce.product_sql.aggregation_system"
    ECOMMERCE_PRODUCT_SQL_ANALYZER_SYSTEM = "ecommerce.product_sql.analyzer_system"
    # E-commerce Product SQL User Prompts
    ECOMMERCE_PRODUCT_SQL_COMPLEXITY_ANALYSIS = "ecommerce.product_sql.complexity_analysis"
    ECOMMERCE_PRODUCT_SQL_BUILDER_USER = "ecommerce.product_sql.builder_user"
    ECOMMERCE_PRODUCT_SQL_AGGREGATION_USER = "ecommerce.product_sql.aggregation_user"
    ECOMMERCE_PRODUCT_QUERY_ENHANCEMENT = "ecommerce.product.query_enhancement"
    ECOMMERCE_PRODUCT_BASE_RESPONSE = "ecommerce.product.base_response"

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
    ORCHESTRATOR_ROUTING_DOMAIN_CLASSIFIER = "orchestrator.routing.domain_classifier"
    ORCHESTRATOR_ROUTING_DOMAIN_CLASSIFIER_WITH_REASONING = "orchestrator.routing.domain_classifier_with_reasoning"

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

    # === EXCELENCIA INCIDENT FLOW (Conversational 3-step flow) ===
    EXCELENCIA_INCIDENT_FLOW_START = "excelencia.incident.flow_start"
    EXCELENCIA_INCIDENT_ASK_PRIORITY = "excelencia.incident.ask_priority"
    EXCELENCIA_INCIDENT_CONFIRMATION = "excelencia.incident.confirmation"
    EXCELENCIA_INCIDENT_CREATED = "excelencia.incident.created_success"
    EXCELENCIA_INCIDENT_CANCELLED = "excelencia.incident.cancelled"
    EXCELENCIA_INCIDENT_INVALID_SELECTION = "excelencia.incident.invalid_selection"

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
    # Data Insights System Prompts
    AGENTS_DATA_INSIGHTS_SYSTEM_CLASSIFIER = "agents.data_insights.system.classifier"
    AGENTS_DATA_INSIGHTS_SYSTEM_ANALYST = "agents.data_insights.system.analyst"
    AGENTS_DATA_INSIGHTS_SYSTEM_NO_RESULTS = "agents.data_insights.system.no_results"
    AGENTS_DATA_INSIGHTS_SYSTEM_ERROR_HANDLER = "agents.data_insights.system.error_handler"

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

    # === TOOLS - DYNAMIC SQL ===
    TOOLS_DYNAMIC_SQL_QUERY_GENERATOR_SYSTEM = "tools.dynamic_sql.query_generator_system"
    TOOLS_DYNAMIC_SQL_INTENT_ANALYZER_SYSTEM = "tools.dynamic_sql.intent_analyzer_system"
    TOOLS_DYNAMIC_SQL_CONTEXT_GENERATOR_SYSTEM = "tools.dynamic_sql.context_generator_system"
    # Dynamic SQL User Prompts
    TOOLS_DYNAMIC_SQL_QUERY_GENERATOR_USER = "tools.dynamic_sql.query_generator_user"
    TOOLS_DYNAMIC_SQL_INTENT_ANALYZER_USER = "tools.dynamic_sql.intent_analyzer_user"
    TOOLS_DYNAMIC_SQL_CONTEXT_GENERATOR_USER = "tools.dynamic_sql.context_generator_user"

    # === HEALTHCARE AGENTS ===
    HEALTHCARE_AGENTS_APPOINTMENT_SYSTEM = "healthcare.agents.appointment_system"
    HEALTHCARE_AGENTS_PATIENT_RECORDS_SYSTEM = "healthcare.agents.patient_records_system"
    HEALTHCARE_AGENTS_TRIAGE_SYSTEM = "healthcare.agents.triage_system"
    HEALTHCARE_AGENTS_DOCTOR_SEARCH_SYSTEM = "healthcare.agents.doctor_search_system"
    HEALTHCARE_AGENTS_EMERGENCY_RESPONSE = "healthcare.agents.emergency_response"

    # === CORE - CIRCUIT BREAKER ===
    CORE_CIRCUIT_BREAKER_HEALTH_CHECK_SYSTEM = "core.circuit_breaker.health_check_system"
    CORE_CIRCUIT_BREAKER_HEALTH_CHECK_USER = "core.circuit_breaker.health_check_user"

    # === AGENTS - SUPERVISOR ===
    AGENTS_SUPERVISOR_ENHANCEMENT_FALLBACK = "agents.supervisor.enhancement_fallback"
    AGENTS_SUPERVISOR_ANALYSIS = "agents.supervisor.analysis"

    # === EXCELENCIA - INCIDENT ERROR ===
    EXCELENCIA_INCIDENT_ERROR_CREATION = "excelencia.incident.error_creation"

    # === EXCELENCIA - INTENT ANALYSIS ===
    EXCELENCIA_INTENT_ANALYSIS = "excelencia.intent.analysis"
    EXCELENCIA_RESPONSE_GENERATION = "excelencia.response.generation"

    # === EXCELENCIA - SMART INPUT (LLM interpreters) ===
    EXCELENCIA_SMART_INPUT_DESCRIPTION_CHECK = "excelencia.smart_input.description_check"
    EXCELENCIA_SMART_INPUT_PRIORITY_INTERPRET = "excelencia.smart_input.priority_interpret"
    EXCELENCIA_SMART_INPUT_CONFIRMATION_INTERPRET = "excelencia.smart_input.confirmation_interpret"
    EXCELENCIA_SMART_INPUT_INCIDENT_DETECT = "excelencia.smart_input.incident_detect"

    # ==========================================================================
    # PHARMACY DOMAIN - Templates organizados por tema/funcionalidad
    # Naming convention: pharmacy.{topic}.{action}
    # ==========================================================================

    # === PHARMACY - CORE ===
    PHARMACY_CORE_SYSTEM_CONTEXT = "pharmacy.core.system_context"

    # === PHARMACY - CRITICAL (Templates fijos, nunca usar LLM) ===
    PHARMACY_CRITICAL_PAYMENT_CONFIRMATION = "pharmacy.critical.payment_confirmation"
    PHARMACY_CRITICAL_PAYMENT_LINK = "pharmacy.critical.payment_link"
    PHARMACY_CRITICAL_PAYMENT_TOTAL_CONFIRM = "pharmacy.critical.payment_total_confirm"
    PHARMACY_CRITICAL_IDENTITY_VERIFIED = "pharmacy.critical.identity_verified"

    # === PHARMACY - GREETING ===
    PHARMACY_GREETING_DEFAULT = "pharmacy.greeting.default"
    PHARMACY_GREETING_RETURNING = "pharmacy.greeting.returning"
    PHARMACY_GREETING_NO_DEBT = "pharmacy.greeting.no_debt"
    PHARMACY_GREETING_FALLBACK = "pharmacy.greeting.fallback"

    # === PHARMACY - IDENTIFICATION ===
    PHARMACY_IDENTIFICATION_REQUEST_IDENTIFIER = "pharmacy.identification.request_identifier"
    PHARMACY_IDENTIFICATION_DNI_INVALID = "pharmacy.identification.dni_invalid"
    PHARMACY_IDENTIFICATION_DNI_NOT_FOUND = "pharmacy.identification.dni_not_found"
    PHARMACY_IDENTIFICATION_REQUEST_NAME = "pharmacy.identification.request_name"
    PHARMACY_IDENTIFICATION_NAME_INVALID = "pharmacy.identification.name_invalid"
    PHARMACY_IDENTIFICATION_MULTIPLE_MATCHES = "pharmacy.identification.multiple_matches"
    PHARMACY_IDENTIFICATION_VERIFIED = "pharmacy.identification.verified"
    PHARMACY_IDENTIFICATION_REQUIRE_ID = "pharmacy.identification.require_id"
    PHARMACY_IDENTIFICATION_NOT_IDENTIFIED = "pharmacy.identification.not_identified"
    PHARMACY_IDENTIFICATION_OFFER_REGISTRATION = "pharmacy.identification.offer_registration"
    PHARMACY_IDENTIFICATION_WELCOME_NEW = "pharmacy.identification.welcome_new"
    PHARMACY_IDENTIFICATION_FALLBACK = "pharmacy.identification.fallback"
    # Legacy keys (mantener compatibilidad)
    PHARMACY_IDENTIFICATION_WELCOME = "pharmacy.identification.welcome_new_customer"
    PHARMACY_IDENTIFICATION_REQUEST_DNI = "pharmacy.identification.request_dni_short"
    PHARMACY_IDENTIFICATION_REQUEST_DNI_DISAMBIGUATION = "pharmacy.identification.request_dni_from_disambiguation"

    # === PHARMACY - CONFIRMATION ===
    PHARMACY_CONFIRMATION_REQUEST = "pharmacy.confirmation.request"
    PHARMACY_CONFIRMATION_CANCELLED = "pharmacy.confirmation.cancelled"
    PHARMACY_CONFIRMATION_CONSULTING_DEBT = "pharmacy.confirmation.consulting_debt"
    PHARMACY_CONFIRMATION_ERROR = "pharmacy.confirmation.error"
    PHARMACY_CONFIRMATION_NOT_IDENTIFIED = "pharmacy.confirmation.not_identified"
    PHARMACY_CONFIRMATION_SELECTED = "pharmacy.confirmation.selected"
    PHARMACY_CONFIRMATION_PAYMENT_SUCCESS = "pharmacy.confirmation.payment_success"
    PHARMACY_CONFIRMATION_PAYMENT_LINK = "pharmacy.confirmation.payment_link"
    PHARMACY_CONFIRMATION_YES_NO_UNCLEAR = "pharmacy.confirmation.yes_no_unclear"
    PHARMACY_CONFIRMATION_FALLBACK = "pharmacy.confirmation.fallback"

    # === PHARMACY - DEBT ===
    PHARMACY_DEBT_SHOW_INFO = "pharmacy.debt.show_info"
    PHARMACY_DEBT_NO_DEBT = "pharmacy.debt.no_debt"
    PHARMACY_DEBT_ERROR = "pharmacy.debt.error"
    PHARMACY_DEBT_FALLBACK = "pharmacy.debt.fallback"

    # === PHARMACY - ERROR ===
    PHARMACY_ERROR_TECHNICAL = "pharmacy.error.technical"
    PHARMACY_ERROR_VALIDATION = "pharmacy.error.validation"
    PHARMACY_ERROR_NOT_FOUND = "pharmacy.error.not_found"
    PHARMACY_ERROR_RETRY = "pharmacy.error.retry"
    PHARMACY_ERROR_MULTIPLE_FAILURES = "pharmacy.error.multiple_failures"
    PHARMACY_ERROR_PHARMACY_NOT_FOUND = "pharmacy.error.pharmacy_not_found"
    PHARMACY_ERROR_FALLBACK = "pharmacy.error.fallback"

    # === PHARMACY - FALLBACK ===
    PHARMACY_FALLBACK_DEFAULT = "pharmacy.fallback.default"
    PHARMACY_FALLBACK_OUT_OF_SCOPE = "pharmacy.fallback.out_of_scope"
    PHARMACY_FALLBACK_CAPABILITIES = "pharmacy.fallback.capabilities"
    PHARMACY_FALLBACK_CANCELLATION = "pharmacy.fallback.cancellation"
    PHARMACY_FALLBACK_FAREWELL = "pharmacy.fallback.farewell"
    PHARMACY_FALLBACK_THANKS = "pharmacy.fallback.thanks"
    PHARMACY_FALLBACK_UNKNOWN_INTENT = "pharmacy.fallback.unknown_intent"

    # === PHARMACY - PERSON RESOLUTION ===
    PHARMACY_PERSON_RESOLUTION_OWN_OR_OTHER = "pharmacy.person_resolution.own_or_other"
    PHARMACY_PERSON_RESOLUTION_OWN_OR_OTHER_UNCLEAR = "pharmacy.person_resolution.own_or_other_unclear"
    PHARMACY_PERSON_RESOLUTION_ACCOUNT_SELECTION = "pharmacy.person_resolution.account_selection"
    PHARMACY_PERSON_RESOLUTION_OFFER_EXISTING_ACCOUNTS = "pharmacy.person_resolution.offer_existing_accounts"
    PHARMACY_PERSON_RESOLUTION_ACCOUNT_SELECTED = "pharmacy.person_resolution.account_selected"
    PHARMACY_PERSON_RESOLUTION_ACCOUNT_UNCLEAR = "pharmacy.person_resolution.account_unclear"
    PHARMACY_PERSON_RESOLUTION_ACCOUNT_INVALID = "pharmacy.person_resolution.account_invalid"
    PHARMACY_PERSON_RESOLUTION_NAME_VERIFICATION = "pharmacy.person_resolution.name_verification"
    PHARMACY_PERSON_RESOLUTION_NAME_MISMATCH = "pharmacy.person_resolution.name_mismatch"
    PHARMACY_PERSON_RESOLUTION_ESCALATION = "pharmacy.person_resolution.escalation"
    PHARMACY_PERSON_RESOLUTION_ESCALATION_VERIFICATION = "pharmacy.person_resolution.escalation_verification"
    PHARMACY_PERSON_RESOLUTION_IDENTIFIER_INVALID = "pharmacy.person_resolution.identifier_invalid"
    PHARMACY_PERSON_RESOLUTION_IDENTIFIER_NOT_FOUND = "pharmacy.person_resolution.identifier_not_found"
    PHARMACY_PERSON_RESOLUTION_REQUEST_OTHER_DNI = "pharmacy.person_resolution.request_other_dni"
    PHARMACY_PERSON_RESOLUTION_START_REGISTRATION = "pharmacy.person_resolution.start_registration"
    PHARMACY_PERSON_RESOLUTION_REQUEST_IDENTIFIER = "pharmacy.person_resolution.request_identifier"
    PHARMACY_PERSON_RESOLUTION_WELCOME_REQUEST_DNI = "pharmacy.person_resolution.welcome_request_dni"
    PHARMACY_PERSON_RESOLUTION_FALLBACK = "pharmacy.person_resolution.fallback"

    # === PHARMACY - INFO ===
    PHARMACY_INFO_QUERY = "pharmacy.info.query"
    PHARMACY_INFO_NO_INFO = "pharmacy.info.no_info"
    PHARMACY_INFO_CAPABILITIES = "pharmacy.info.capabilities"
    PHARMACY_INFO_FALLBACK = "pharmacy.info.fallback"
    # Legacy keys (mantener compatibilidad)
    PHARMACY_INFO_QUERY_GENERATE = "pharmacy.info_query.generate"
    PHARMACY_INFO_QUERY_NO_INFO = "pharmacy.info_query.no_info"
    PHARMACY_INFO_QUERY_CAPABILITY = "pharmacy.info_query.capability_response"

    # === PHARMACY - PAYMENT ===
    PHARMACY_PAYMENT_TOTAL_REQUEST = "pharmacy.payment.total_request"
    PHARMACY_PAYMENT_PARTIAL_REQUEST = "pharmacy.payment.partial_request"
    PHARMACY_PAYMENT_AMOUNT_INVALID = "pharmacy.payment.amount_invalid"
    PHARMACY_PAYMENT_AMOUNT_OUT_OF_RANGE = "pharmacy.payment.amount_out_of_range"
    PHARMACY_PAYMENT_LINK_FAILED = "pharmacy.payment.link_failed"
    PHARMACY_PAYMENT_FOLLOWUP_PENDING = "pharmacy.payment.followup_pending"
    PHARMACY_PAYMENT_LINK_EXPIRED = "pharmacy.payment.link_expired"
    PHARMACY_PAYMENT_PROBLEM_OPTIONS = "pharmacy.payment.problem_options"
    PHARMACY_PAYMENT_FALLBACK = "pharmacy.payment.fallback"

    # === PHARMACY - DATA QUERY ===
    PHARMACY_DATA_QUERY_ANALYZE = "pharmacy.data_query.analyze"
    PHARMACY_DATA_QUERY_NO_DATA = "pharmacy.data_query.no_data"
    PHARMACY_DATA_QUERY_FALLBACK = "pharmacy.data_query.fallback"
    # Legacy key (mantener compatibilidad)
    PHARMACY_DATA_QUERY_ERROR = "pharmacy.data_query.error"

    # === PHARMACY - SUMMARY ===
    PHARMACY_SUMMARY_GENERATE = "pharmacy.summary.generate"
    PHARMACY_SUMMARY_NO_DATA = "pharmacy.summary.no_data"
    PHARMACY_SUMMARY_FALLBACK = "pharmacy.summary.fallback"

    # === PHARMACY - REGISTRATION (Legacy) ===
    PHARMACY_REGISTRATION_YES_NO_VALIDATION = "pharmacy.registration.yes_no_validation"
    PHARMACY_REGISTRATION_START = "pharmacy.registration.start"
    PHARMACY_REGISTRATION_NAME_ERROR = "pharmacy.registration.name_error"
    PHARMACY_REGISTRATION_DOCUMENT_PROMPT = "pharmacy.registration.document_prompt"
    PHARMACY_REGISTRATION_DOCUMENT_ERROR = "pharmacy.registration.document_error"
    PHARMACY_REGISTRATION_CONFIRM_DATA = "pharmacy.registration.confirm_data"
    PHARMACY_REGISTRATION_SUCCESS = "pharmacy.registration.success"
    PHARMACY_REGISTRATION_DUPLICATE_WITH_NAME = "pharmacy.registration.duplicate_with_name"
    PHARMACY_REGISTRATION_DUPLICATE_NO_NAME = "pharmacy.registration.duplicate_no_name"
    PHARMACY_REGISTRATION_NOT_SUPPORTED = "pharmacy.registration.not_supported"
    PHARMACY_REGISTRATION_ERROR = "pharmacy.registration.error"
    PHARMACY_REGISTRATION_CANCELLED = "pharmacy.registration.cancelled"
    PHARMACY_REGISTRATION_EXCEPTION = "pharmacy.registration.exception"

    # === PHARMACY - RESPONSE (Legacy) ===
    PHARMACY_RESPONSE_DEBT_INFO = "pharmacy.response.debt_info"
    PHARMACY_RESPONSE_PAYMENT_LINK = "pharmacy.response.payment_link"
    PHARMACY_RESPONSE_CONFIRMATION = "pharmacy.response.confirmation"
    PHARMACY_RESPONSE_OUT_OF_SCOPE = "pharmacy.response.out_of_scope"
    PHARMACY_RESPONSE_ERROR = "pharmacy.response.error"
    PHARMACY_RESPONSE_DEBT_REJECTED = "pharmacy.response.debt_rejected"
    PHARMACY_RESPONSE_FAREWELL = "pharmacy.response.farewell"
    PHARMACY_RESPONSE_THANKS = "pharmacy.response.thanks"
    PHARMACY_RESPONSE_CAPABILITIES = "pharmacy.response.capabilities"

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
