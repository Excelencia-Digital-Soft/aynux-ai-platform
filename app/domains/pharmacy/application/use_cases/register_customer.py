"""
Register Customer Use Case

Application use case for registering new customers in Plex ERP.
Used when a WhatsApp user is not found in the system.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from app.domains.pharmacy.domain.entities.plex_customer import PlexCustomer

if TYPE_CHECKING:
    from app.clients.plex_client import PlexClient


class RegistrationStatus(str, Enum):
    """Status of customer registration."""

    REGISTERED = "registered"  # Successfully registered
    VALIDATION_ERROR = "validation_error"  # Invalid input data
    DUPLICATE = "duplicate"  # Customer already exists
    API_ERROR = "api_error"  # Plex API error
    NOT_SUPPORTED = "not_supported"  # Registration not supported by Plex


class RegistrationStep(str, Enum):
    """Steps in the registration flow."""

    NOMBRE = "nombre"
    DOCUMENTO = "documento"
    CONFIRMAR = "confirmar"
    COMPLETE = "complete"


@dataclass
class RegisterCustomerRequest:
    """Request to register a new customer."""

    nombre: str
    documento: str
    telefono: str
    email: str | None = None
    direccion: str | None = None


@dataclass
class RegisterCustomerResponse:
    """Response from customer registration."""

    status: RegistrationStatus
    customer: PlexCustomer | None = None
    error: str | None = None

    @property
    def is_success(self) -> bool:
        """Check if registration was successful."""
        return self.status == RegistrationStatus.REGISTERED and self.customer is not None


@dataclass
class RegistrationData:
    """Data collected during registration flow."""

    nombre: str | None = None
    documento: str | None = None
    telefono: str | None = None
    email: str | None = None
    direccion: str | None = None
    current_step: RegistrationStep = RegistrationStep.NOMBRE

    def is_complete(self) -> bool:
        """Check if all required data is collected."""
        return all([self.nombre, self.documento, self.telefono])

    def to_request(self) -> RegisterCustomerRequest:
        """Convert to registration request."""
        if not self.is_complete():
            raise ValueError("Registration data is incomplete")
        return RegisterCustomerRequest(
            nombre=self.nombre,  # type: ignore
            documento=self.documento,  # type: ignore
            telefono=self.telefono,  # type: ignore
            email=self.email,
            direccion=self.direccion,
        )


class RegisterCustomerUseCase:
    """
    Use case for registering new customers in Plex ERP.

    This is used when a WhatsApp user cannot be found in Plex
    and chooses to register.

    Single Responsibility: Customer registration
    Dependency Inversion: Depends on PlexClient abstraction
    """

    def __init__(self, plex_client: PlexClient):
        """
        Initialize use case with Plex client.

        Args:
            plex_client: PlexClient instance for API calls
        """
        self._plex = plex_client

    async def execute(
        self,
        request: RegisterCustomerRequest,
    ) -> RegisterCustomerResponse:
        """
        Execute customer registration.

        Args:
            request: RegisterCustomerRequest with customer data

        Returns:
            RegisterCustomerResponse with status and created customer
        """
        try:
            # Validate input
            validation_error = self._validate_request(request)
            if validation_error:
                return RegisterCustomerResponse(
                    status=RegistrationStatus.VALIDATION_ERROR,
                    error=validation_error,
                )

            # Check if customer already exists
            existing = await self._check_existing_customer(request)
            if existing:
                return RegisterCustomerResponse(
                    status=RegistrationStatus.DUPLICATE,
                    customer=existing,
                    error="Ya existe una cuenta con estos datos",
                )

            # Create customer in Plex
            customer = await self._plex.create_customer(
                nombre=request.nombre,
                documento=request.documento,
                telefono=request.telefono,
                email=request.email,
                direccion=request.direccion,
            )

            return RegisterCustomerResponse(
                status=RegistrationStatus.REGISTERED,
                customer=customer,
            )

        except Exception as e:
            error_str = str(e)

            # Check for specific error types
            if "NOT_SUPPORTED" in error_str:
                return RegisterCustomerResponse(
                    status=RegistrationStatus.NOT_SUPPORTED,
                    error="El registro de clientes no está disponible",
                )

            return RegisterCustomerResponse(
                status=RegistrationStatus.API_ERROR,
                error=error_str,
            )

    def _validate_request(self, request: RegisterCustomerRequest) -> str | None:
        """
        Validate registration request data.

        Args:
            request: Registration request to validate

        Returns:
            Error message if invalid, None if valid
        """
        # Validate nombre
        if not request.nombre or len(request.nombre.strip()) < 3:
            return "El nombre debe tener al menos 3 caracteres"

        # Validate documento (DNI)
        documento = request.documento.strip()
        if not documento.isdigit():
            return "El documento debe contener solo números"
        if len(documento) < 6 or len(documento) > 11:
            return "El documento debe tener entre 6 y 11 dígitos"

        # Validate telefono
        telefono = "".join(c for c in request.telefono if c.isdigit())
        if len(telefono) < 8:
            return "El teléfono debe tener al menos 8 dígitos"

        # Email validation (optional)
        if request.email:
            if "@" not in request.email or "." not in request.email:
                return "El formato del email no es válido"

        return None

    async def _check_existing_customer(
        self,
        request: RegisterCustomerRequest,
    ) -> PlexCustomer | None:
        """
        Check if a customer already exists with the same document.

        Args:
            request: Registration request

        Returns:
            Existing customer if found, None otherwise
        """
        try:
            customers = await self._plex.search_customer(document=request.documento)
            valid_customers = [c for c in customers if c.is_valid_for_identification]

            if valid_customers:
                return valid_customers[0]
            return None
        except Exception:
            # If search fails, proceed with registration
            return None

    def process_registration_step(
        self,
        current_data: RegistrationData,
        user_input: str,
    ) -> tuple[RegistrationData, str | None]:
        """
        Process a step in the registration flow.

        Args:
            current_data: Current registration data
            user_input: User's input for current step

        Returns:
            Tuple of (updated_data, next_prompt_or_none)
            If next_prompt is None, registration data is complete.
        """
        user_input = user_input.strip()

        if current_data.current_step == RegistrationStep.NOMBRE:
            if len(user_input) < 3:
                return current_data, "El nombre debe tener al menos 3 caracteres. Intenta de nuevo:"

            current_data.nombre = user_input.upper()
            current_data.current_step = RegistrationStep.DOCUMENTO
            return current_data, "Gracias. Ahora ingresa tu número de DNI:"

        elif current_data.current_step == RegistrationStep.DOCUMENTO:
            cleaned = "".join(c for c in user_input if c.isdigit())
            if len(cleaned) < 6 or len(cleaned) > 11:
                return current_data, "El DNI debe tener entre 6 y 11 dígitos. Intenta de nuevo:"

            current_data.documento = cleaned
            current_data.current_step = RegistrationStep.CONFIRMAR
            return current_data, (
                f"¿Confirmas estos datos?\n\n"
                f"Nombre: {current_data.nombre}\n"
                f"DNI: {current_data.documento}\n\n"
                f"Responde SI para confirmar o NO para cancelar."
            )

        elif current_data.current_step == RegistrationStep.CONFIRMAR:
            if user_input.upper() in ["SI", "SÍ", "YES", "S"]:
                current_data.current_step = RegistrationStep.COMPLETE
                return current_data, None  # Ready to register
            elif user_input.upper() in ["NO", "N", "CANCELAR"]:
                # Reset registration
                return RegistrationData(), "Registro cancelado. ¿En qué más puedo ayudarte?"
            else:
                return current_data, "Por favor responde SI para confirmar o NO para cancelar."

        return current_data, None
