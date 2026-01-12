"""
TaskRegistry - Registro centralizado de todas las claves de tasks del sistema.

Este modulo define constantes tipo-seguro para referenciar tasks en todo el codigo.
Mejora el autocompletado y previene errores de typos.
"""


class TaskRegistry:
    """
    Registro centralizado de claves de tasks.

    Naming convention: {domain}.{flow}.{action}
    Ejemplo: "pharmacy.identification.request_dni"
    """

    # === PHARMACY - GREETING ===
    PHARMACY_GREETING_DEFAULT = "pharmacy.greeting.default"
    PHARMACY_GREETING_RETURNING = "pharmacy.greeting.returning"

    # === PHARMACY - IDENTIFICATION ===
    PHARMACY_IDENTIFICATION_REQUEST_IDENTIFIER = "pharmacy.identification.request_identifier"
    PHARMACY_IDENTIFICATION_DNI_INVALID = "pharmacy.identification.dni_invalid"
    PHARMACY_IDENTIFICATION_DNI_NOT_FOUND = "pharmacy.identification.dni_not_found"
    PHARMACY_IDENTIFICATION_NAME_INVALID = "pharmacy.identification.name_invalid"
    PHARMACY_IDENTIFICATION_REQUEST_NAME = "pharmacy.identification.request_name"
    PHARMACY_IDENTIFICATION_MULTIPLE_MATCHES = "pharmacy.identification.multiple_matches"
    PHARMACY_IDENTIFICATION_VERIFIED = "pharmacy.identification.verified"
    PHARMACY_IDENTIFICATION_REQUIRE_ID = "pharmacy.identification.require_id"
    PHARMACY_IDENTIFICATION_NOT_IDENTIFIED = "pharmacy.identification.not_identified"
    PHARMACY_IDENTIFICATION_OFFER_REGISTRATION = "pharmacy.identification.offer_registration"

    # === PHARMACY - CONFIRMATION ===
    PHARMACY_CONFIRMATION_REQUEST = "pharmacy.confirmation.request"
    PHARMACY_CONFIRMATION_CANCELLED = "pharmacy.confirmation.cancelled"
    PHARMACY_CONFIRMATION_CONSULTING_DEBT = "pharmacy.confirmation.consulting_debt"
    PHARMACY_CONFIRMATION_ERROR = "pharmacy.confirmation.error"
    PHARMACY_CONFIRMATION_NOT_IDENTIFIED = "pharmacy.confirmation.not_identified"
    PHARMACY_CONFIRMATION_SELECTED = "pharmacy.confirmation.selected"
    PHARMACY_CONFIRMATION_PAYMENT_SUCCESS = "pharmacy.confirmation.payment_success"
    PHARMACY_CONFIRMATION_PAYMENT_LINK = "pharmacy.confirmation.payment_link"

    # === PHARMACY - DEBT ===
    PHARMACY_DEBT_SHOW_INFO = "pharmacy.debt.show_info"
    PHARMACY_DEBT_NO_DEBT = "pharmacy.debt.no_debt"
    PHARMACY_DEBT_ERROR = "pharmacy.debt.error"

    # === PHARMACY - ERROR ===
    PHARMACY_ERROR_TECHNICAL = "pharmacy.error.technical"
    PHARMACY_ERROR_VALIDATION = "pharmacy.error.validation"
    PHARMACY_ERROR_NOT_FOUND = "pharmacy.error.not_found"
    PHARMACY_ERROR_RETRY = "pharmacy.error.retry"
    PHARMACY_ERROR_MULTIPLE_FAILURES = "pharmacy.error.multiple_failures"
    PHARMACY_ERROR_PHARMACY_NOT_FOUND = "pharmacy.error.pharmacy_not_found"

    # === PHARMACY - FALLBACK ===
    PHARMACY_FALLBACK_DEFAULT = "pharmacy.fallback.default"
    PHARMACY_FALLBACK_OUT_OF_SCOPE = "pharmacy.fallback.out_of_scope"
    PHARMACY_FALLBACK_CAPABILITIES = "pharmacy.fallback.capabilities"
    PHARMACY_FALLBACK_CANCELLATION = "pharmacy.fallback.cancellation"
    PHARMACY_FALLBACK_FAREWELL = "pharmacy.fallback.farewell"
    PHARMACY_FALLBACK_THANKS = "pharmacy.fallback.thanks"

    # === PHARMACY - PERSON RESOLUTION ===
    PHARMACY_PERSON_OWN_OR_OTHER = "pharmacy.person_resolution.own_or_other"
    PHARMACY_PERSON_OWN_OR_OTHER_UNCLEAR = "pharmacy.person_resolution.own_or_other_unclear"
    PHARMACY_PERSON_ACCOUNT_SELECTION = "pharmacy.person_resolution.account_selection"
    PHARMACY_PERSON_OFFER_EXISTING_ACCOUNTS = "pharmacy.person_resolution.offer_existing_accounts"
    PHARMACY_PERSON_ACCOUNT_SELECTED = "pharmacy.person_resolution.account_selected"
    PHARMACY_PERSON_ACCOUNT_UNCLEAR = "pharmacy.person_resolution.account_unclear"
    PHARMACY_PERSON_ACCOUNT_INVALID = "pharmacy.person_resolution.account_invalid"
    PHARMACY_PERSON_NAME_VERIFICATION = "pharmacy.person_resolution.name_verification"
    PHARMACY_PERSON_NAME_MISMATCH = "pharmacy.person_resolution.name_mismatch"
    PHARMACY_PERSON_ESCALATION = "pharmacy.person_resolution.escalation"
    PHARMACY_PERSON_ESCALATION_VERIFICATION = "pharmacy.person_resolution.escalation_verification"
    PHARMACY_PERSON_IDENTIFIER_INVALID = "pharmacy.person_resolution.identifier_invalid"
    PHARMACY_PERSON_IDENTIFIER_NOT_FOUND = "pharmacy.person_resolution.identifier_not_found"
    PHARMACY_PERSON_REQUEST_OTHER_DNI = "pharmacy.person_resolution.request_other_dni"
    PHARMACY_PERSON_START_REGISTRATION = "pharmacy.person_resolution.start_registration"
    PHARMACY_PERSON_REQUEST_IDENTIFIER = "pharmacy.person_resolution.request_identifier"
    PHARMACY_PERSON_WELCOME_REQUEST_DNI = "pharmacy.person_resolution.welcome_request_dni"

    # === PHARMACY - DATA QUERY ===
    PHARMACY_DATA_QUERY_ANALYZE = "pharmacy.data_query.analyze"
    PHARMACY_DATA_QUERY_NO_DATA = "pharmacy.data_query.no_data"

    # === PHARMACY - SUMMARY ===
    PHARMACY_SUMMARY_GENERATE = "pharmacy.summary.generate"
    PHARMACY_SUMMARY_NO_DATA = "pharmacy.summary.no_data"

    # === PHARMACY - INFO ===
    PHARMACY_INFO_QUERY = "pharmacy.info.query"
    PHARMACY_INFO_NO_INFO = "pharmacy.info.no_info"
    PHARMACY_INFO_CAPABILITIES = "pharmacy.info.capabilities"

    @classmethod
    def get_all_keys(cls) -> list[str]:
        """Retorna todas las claves de tasks registradas."""
        return [
            value
            for key, value in cls.__dict__.items()
            if not key.startswith("_") and isinstance(value, str) and "." in value
        ]

    @classmethod
    def get_by_domain(cls, domain: str) -> list[str]:
        """
        Retorna todas las claves de un dominio especifico.

        Args:
            domain: El dominio a filtrar (ej: "pharmacy")

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
