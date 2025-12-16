"""
Pharmacy Use Cases

Application use cases for pharmacy operations.
"""

from app.domains.pharmacy.application.use_cases.check_debt import (
    CheckDebtRequest,
    CheckDebtResponse,
    CheckDebtUseCase,
)
from app.domains.pharmacy.application.use_cases.confirm_debt import (
    ConfirmDebtRequest,
    ConfirmDebtResponse,
    ConfirmDebtUseCase,
)
from app.domains.pharmacy.application.use_cases.generate_invoice import (
    GenerateInvoiceRequest,
    GenerateInvoiceResponse,
    GenerateInvoiceUseCase,
)
from app.domains.pharmacy.application.use_cases.identify_customer import (
    IdentificationStatus,
    IdentifyCustomerRequest,
    IdentifyCustomerResponse,
    IdentifyCustomerUseCase,
)
from app.domains.pharmacy.application.use_cases.register_customer import (
    RegisterCustomerRequest,
    RegisterCustomerResponse,
    RegisterCustomerUseCase,
    RegistrationData,
    RegistrationStatus,
    RegistrationStep,
)

__all__ = [
    # Debt management
    "CheckDebtUseCase",
    "CheckDebtRequest",
    "CheckDebtResponse",
    "ConfirmDebtUseCase",
    "ConfirmDebtRequest",
    "ConfirmDebtResponse",
    "GenerateInvoiceUseCase",
    "GenerateInvoiceRequest",
    "GenerateInvoiceResponse",
    # Customer identification
    "IdentifyCustomerUseCase",
    "IdentifyCustomerRequest",
    "IdentifyCustomerResponse",
    "IdentificationStatus",
    # Customer registration
    "RegisterCustomerUseCase",
    "RegisterCustomerRequest",
    "RegisterCustomerResponse",
    "RegistrationData",
    "RegistrationStatus",
    "RegistrationStep",
]
