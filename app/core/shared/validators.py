"""
Shared Validators

Common validation utilities for the application.
"""

import re
from typing import Any, Callable


class ValidationError(Exception):
    """Validation error with field information."""

    def __init__(self, message: str, field: str | None = None, code: str | None = None):
        self.message = message
        self.field = field
        self.code = code or "validation_error"
        super().__init__(message)


class Validator:
    """Base validator class."""

    @staticmethod
    def required(value: Any, field_name: str = "field") -> Any:
        """Validate that value is not None or empty."""
        if value is None:
            raise ValidationError(f"{field_name} is required", field=field_name, code="required")
        if isinstance(value, str) and not value.strip():
            raise ValidationError(f"{field_name} cannot be empty", field=field_name, code="empty")
        return value

    @staticmethod
    def min_length(value: str, min_len: int, field_name: str = "field") -> str:
        """Validate minimum string length."""
        if len(value) < min_len:
            raise ValidationError(
                f"{field_name} must be at least {min_len} characters",
                field=field_name,
                code="min_length",
            )
        return value

    @staticmethod
    def max_length(value: str, max_len: int, field_name: str = "field") -> str:
        """Validate maximum string length."""
        if len(value) > max_len:
            raise ValidationError(
                f"{field_name} must be at most {max_len} characters",
                field=field_name,
                code="max_length",
            )
        return value

    @staticmethod
    def in_range(value: int | float, min_val: int | float, max_val: int | float, field_name: str = "field") -> int | float:
        """Validate that number is in range."""
        if value < min_val or value > max_val:
            raise ValidationError(
                f"{field_name} must be between {min_val} and {max_val}",
                field=field_name,
                code="out_of_range",
            )
        return value

    @staticmethod
    def positive(value: int | float, field_name: str = "field") -> int | float:
        """Validate that number is positive."""
        if value <= 0:
            raise ValidationError(
                f"{field_name} must be positive",
                field=field_name,
                code="not_positive",
            )
        return value

    @staticmethod
    def non_negative(value: int | float, field_name: str = "field") -> int | float:
        """Validate that number is non-negative."""
        if value < 0:
            raise ValidationError(
                f"{field_name} cannot be negative",
                field=field_name,
                code="negative",
            )
        return value


class EmailValidator:
    """Email validation utilities."""

    EMAIL_PATTERN = re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    )

    @classmethod
    def validate(cls, email: str, field_name: str = "email") -> str:
        """Validate email format."""
        Validator.required(email, field_name)
        email = email.strip().lower()

        if not cls.EMAIL_PATTERN.match(email):
            raise ValidationError(
                f"Invalid email format",
                field=field_name,
                code="invalid_email",
            )
        return email

    @classmethod
    def is_valid(cls, email: str) -> bool:
        """Check if email is valid without raising."""
        try:
            cls.validate(email)
            return True
        except ValidationError:
            return False


class PhoneValidator:
    """Phone number validation utilities."""

    # Argentina phone patterns
    AR_PHONE_PATTERN = re.compile(r"^(?:\+54)?(?:9)?(?:11|[2368]\d{2})\d{6,8}$")

    @classmethod
    def validate(cls, phone: str, field_name: str = "phone") -> str:
        """Validate phone number."""
        Validator.required(phone, field_name)

        # Normalize: remove spaces, dashes, parentheses
        normalized = re.sub(r"[\s\-\(\)]", "", phone)

        if not normalized:
            raise ValidationError(
                "Phone number is required",
                field=field_name,
                code="required",
            )

        return normalized

    @classmethod
    def normalize_ar(cls, phone: str) -> str:
        """Normalize Argentine phone number."""
        normalized = cls.validate(phone)

        # Remove country code if present
        if normalized.startswith("+54"):
            normalized = normalized[3:]
        elif normalized.startswith("54"):
            normalized = normalized[2:]

        # Remove mobile prefix 9 if present
        if normalized.startswith("9"):
            normalized = normalized[1:]

        return normalized


class DNIValidator:
    """Argentine DNI validation."""

    DNI_PATTERN = re.compile(r"^\d{7,8}$")

    @classmethod
    def validate(cls, dni: str, field_name: str = "dni") -> str:
        """Validate Argentine DNI."""
        Validator.required(dni, field_name)

        # Remove dots and spaces
        normalized = re.sub(r"[\.\s]", "", dni)

        if not cls.DNI_PATTERN.match(normalized):
            raise ValidationError(
                "DNI must be 7 or 8 digits",
                field=field_name,
                code="invalid_dni",
            )

        return normalized


class CUITValidator:
    """Argentine CUIT/CUIL validation."""

    CUIT_PATTERN = re.compile(r"^(20|23|24|27|30|33|34)\d{8}\d$")

    @classmethod
    def validate(cls, cuit: str, field_name: str = "cuit") -> str:
        """Validate Argentine CUIT/CUIL with check digit."""
        Validator.required(cuit, field_name)

        # Remove dashes and spaces
        normalized = re.sub(r"[\-\s]", "", cuit)

        if not cls.CUIT_PATTERN.match(normalized):
            raise ValidationError(
                "Invalid CUIT format",
                field=field_name,
                code="invalid_cuit_format",
            )

        # Validate check digit
        if not cls._validate_check_digit(normalized):
            raise ValidationError(
                "Invalid CUIT check digit",
                field=field_name,
                code="invalid_cuit_check",
            )

        return normalized

    @classmethod
    def _validate_check_digit(cls, cuit: str) -> bool:
        """Validate CUIT check digit."""
        multipliers = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]

        total = sum(int(digit) * mult for digit, mult in zip(cuit[:10], multipliers))
        remainder = total % 11

        if remainder == 0:
            expected_check = 0
        elif remainder == 1:
            expected_check = 9
        else:
            expected_check = 11 - remainder

        return int(cuit[10]) == expected_check


def validate_all(validations: list[tuple[Callable[..., Any], tuple, dict]]) -> list[ValidationError]:
    """
    Run multiple validations and collect all errors.

    Args:
        validations: List of (validator_func, args, kwargs) tuples

    Returns:
        List of validation errors
    """
    errors: list[ValidationError] = []

    for validator_func, args, kwargs in validations:
        try:
            validator_func(*args, **kwargs)
        except ValidationError as e:
            errors.append(e)

    return errors
