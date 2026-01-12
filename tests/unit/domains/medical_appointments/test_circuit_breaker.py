# ============================================================================
# Tests for CircuitBreaker resilience pattern
# ============================================================================
"""Unit tests for CircuitBreaker.

Tests the circuit breaker pattern implementation that protects against
cascading failures when external services are unavailable.
"""

import asyncio

import pytest

from app.domains.medical_appointments.infrastructure.external.hcweb.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError,
    CircuitState,
    ValidationError,
    validate_dni,
    validate_id,
    validate_phone,
    validate_required,
)


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig."""

    def test_default_config_values(self) -> None:
        """Should have sensible default values."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60.0
        assert config.success_threshold == 2

    def test_custom_config_values(self) -> None:
        """Should accept custom values."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
            success_threshold=1,
        )
        assert config.failure_threshold == 3
        assert config.recovery_timeout == 30.0
        assert config.success_threshold == 1


class TestCircuitBreakerInitialState:
    """Tests for CircuitBreaker initial state."""

    def test_starts_closed(self) -> None:
        """Should start in CLOSED state."""
        breaker = CircuitBreaker()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed is True
        assert breaker.is_open is False

    def test_accepts_custom_config(self) -> None:
        """Should accept custom configuration."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(config)
        assert breaker._config.failure_threshold == 3


class TestCircuitBreakerSuccessfulCalls:
    """Tests for successful calls through circuit breaker."""

    @pytest.mark.asyncio
    async def test_successful_call_passes_through(self) -> None:
        """Should pass through successful calls."""
        breaker = CircuitBreaker()

        async def success_func() -> str:
            return "success"

        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.is_closed is True

    @pytest.mark.asyncio
    async def test_successful_call_with_args(self) -> None:
        """Should pass arguments to function."""
        breaker = CircuitBreaker()

        async def add_func(a: int, b: int) -> int:
            return a + b

        result = await breaker.call(add_func, 2, 3)
        assert result == 5

    @pytest.mark.asyncio
    async def test_successful_call_with_kwargs(self) -> None:
        """Should pass keyword arguments to function."""
        breaker = CircuitBreaker()

        async def greet_func(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"

        result = await breaker.call(greet_func, "World", greeting="Hi")
        assert result == "Hi, World!"

    @pytest.mark.asyncio
    async def test_multiple_successful_calls(self) -> None:
        """Should handle multiple successful calls."""
        breaker = CircuitBreaker()

        async def counter() -> int:
            return 1

        for _ in range(10):
            result = await breaker.call(counter)
            assert result == 1

        assert breaker.is_closed is True


class TestCircuitBreakerFailures:
    """Tests for failure handling in circuit breaker."""

    @pytest.mark.asyncio
    async def test_single_failure_stays_closed(self) -> None:
        """Should stay closed after single failure."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(config)

        async def fail_func() -> None:
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await breaker.call(fail_func)

        assert breaker.is_closed is True
        assert breaker._state.failure_count == 1

    @pytest.mark.asyncio
    async def test_failures_below_threshold_stay_closed(self) -> None:
        """Should stay closed when failures are below threshold."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(config)

        async def fail_func() -> None:
            raise ValueError("Test error")

        # Fail twice (below threshold of 3)
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        assert breaker.is_closed is True
        assert breaker._state.failure_count == 2

    @pytest.mark.asyncio
    async def test_failures_at_threshold_opens_circuit(self) -> None:
        """Should open circuit when failures reach threshold."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(config)

        async def fail_func() -> None:
            raise ValueError("Test error")

        # Fail 3 times (equals threshold)
        for _ in range(3):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        assert breaker.is_open is True
        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_calls(self) -> None:
        """Should reject calls when circuit is open."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker(config)

        async def fail_func() -> None:
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        assert breaker.is_open is True

        # Next call should be rejected immediately
        async def success_func() -> str:
            return "success"

        with pytest.raises(CircuitOpenError) as exc_info:
            await breaker.call(success_func)

        assert "Circuit breaker is open" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self) -> None:
        """Should reset failure count after successful call."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(config)

        async def fail_func() -> None:
            raise ValueError("Test error")

        async def success_func() -> str:
            return "success"

        # Fail twice
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        assert breaker._state.failure_count == 2

        # Success should reset count
        await breaker.call(success_func)
        assert breaker._state.failure_count == 0


class TestCircuitBreakerRecovery:
    """Tests for circuit breaker recovery behavior."""

    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_timeout(self) -> None:
        """Should transition to HALF_OPEN after recovery timeout."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,  # 100ms for fast test
        )
        breaker = CircuitBreaker(config)

        async def fail_func() -> None:
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        assert breaker.is_open is True

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Next call should trigger state check
        async def success_func() -> str:
            return "success"

        result = await breaker.call(success_func)
        assert result == "success"
        # Should be in HALF_OPEN or CLOSED depending on success threshold
        assert breaker.state in [CircuitState.HALF_OPEN, CircuitState.CLOSED]

    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(self) -> None:
        """Should close circuit after successes in HALF_OPEN state."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.05,
            success_threshold=2,
        )
        breaker = CircuitBreaker(config)

        async def fail_func() -> None:
            raise ValueError("Test error")

        async def success_func() -> str:
            return "success"

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        # Wait for recovery
        await asyncio.sleep(0.1)

        # Successful calls in HALF_OPEN should eventually close
        await breaker.call(success_func)
        await breaker.call(success_func)

        assert breaker.is_closed is True

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(self) -> None:
        """Should reopen circuit on failure during HALF_OPEN."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.05,
            success_threshold=2,
        )
        breaker = CircuitBreaker(config)

        async def fail_func() -> None:
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        # Wait for recovery
        await asyncio.sleep(0.1)

        # Trigger transition to HALF_OPEN and then fail
        with pytest.raises(ValueError):
            await breaker.call(fail_func)

        assert breaker.is_open is True


class TestCircuitBreakerReset:
    """Tests for circuit breaker reset functionality."""

    @pytest.mark.asyncio
    async def test_reset_closes_open_circuit(self) -> None:
        """Should reset circuit to CLOSED state."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker(config)

        async def fail_func() -> None:
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        assert breaker.is_open is True

        # Reset should close it
        breaker.reset()
        assert breaker.is_closed is True
        assert breaker._state.failure_count == 0


class TestCircuitOpenError:
    """Tests for CircuitOpenError exception."""

    def test_error_message(self) -> None:
        """Should have descriptive error message."""
        error = CircuitOpenError("Test message")
        assert str(error) == "Test message"

    def test_is_exception(self) -> None:
        """Should be a proper exception."""
        error = CircuitOpenError("Test")
        assert isinstance(error, Exception)


# ============================================================================
# Validation Function Tests
# ============================================================================


class TestValidateDni:
    """Tests for validate_dni function."""

    def test_valid_dni(self) -> None:
        """Should accept valid DNI."""
        assert validate_dni("30123456") == "30123456"

    def test_dni_with_dots(self) -> None:
        """Should normalize DNI by removing dots."""
        assert validate_dni("30.123.456") == "30123456"

    def test_dni_with_spaces(self) -> None:
        """Should normalize DNI by removing spaces."""
        assert validate_dni("30 123 456") == "30123456"

    def test_dni_with_dashes(self) -> None:
        """Should normalize DNI by removing dashes."""
        assert validate_dni("30-123-456") == "30123456"

    def test_dni_minimum_length(self) -> None:
        """Should accept DNI with minimum 6 digits."""
        assert validate_dni("123456") == "123456"

    def test_dni_maximum_length(self) -> None:
        """Should accept DNI with maximum 11 digits."""
        assert validate_dni("12345678901") == "12345678901"

    def test_empty_dni_raises_error(self) -> None:
        """Should reject empty DNI."""
        with pytest.raises(ValidationError) as exc_info:
            validate_dni("")
        assert exc_info.value.field == "dni"
        assert "required" in exc_info.value.message.lower()

    def test_dni_too_short_raises_error(self) -> None:
        """Should reject DNI shorter than 6 digits."""
        with pytest.raises(ValidationError) as exc_info:
            validate_dni("12345")
        assert exc_info.value.field == "dni"
        assert "6-11" in exc_info.value.message

    def test_dni_too_long_raises_error(self) -> None:
        """Should reject DNI longer than 11 digits."""
        with pytest.raises(ValidationError) as exc_info:
            validate_dni("123456789012")
        assert exc_info.value.field == "dni"
        assert "6-11" in exc_info.value.message

    def test_dni_no_digits_raises_error(self) -> None:
        """Should reject DNI with no digits."""
        with pytest.raises(ValidationError) as exc_info:
            validate_dni("abc")
        assert exc_info.value.field == "dni"
        assert "digits" in exc_info.value.message.lower()


class TestValidatePhone:
    """Tests for validate_phone function."""

    def test_valid_phone(self) -> None:
        """Should accept valid phone."""
        assert validate_phone("2645551234") == "2645551234"

    def test_phone_with_country_code(self) -> None:
        """Should normalize phone with country code."""
        assert validate_phone("+542645551234") == "542645551234"

    def test_phone_with_spaces(self) -> None:
        """Should normalize phone by removing spaces."""
        assert validate_phone("264 555 1234") == "2645551234"

    def test_phone_with_dashes(self) -> None:
        """Should normalize phone by removing dashes."""
        assert validate_phone("264-555-1234") == "2645551234"

    def test_phone_minimum_length(self) -> None:
        """Should accept phone with minimum 8 digits."""
        assert validate_phone("12345678") == "12345678"

    def test_empty_phone_raises_error(self) -> None:
        """Should reject empty phone."""
        with pytest.raises(ValidationError) as exc_info:
            validate_phone("")
        assert exc_info.value.field == "phone"

    def test_phone_too_short_raises_error(self) -> None:
        """Should reject phone shorter than 8 digits."""
        with pytest.raises(ValidationError) as exc_info:
            validate_phone("1234567")
        assert exc_info.value.field == "phone"
        assert "8 digits" in exc_info.value.message


class TestValidateRequired:
    """Tests for validate_required function."""

    def test_valid_value(self) -> None:
        """Should accept non-empty value."""
        validate_required("value", "field_name")  # Should not raise

    def test_none_raises_error(self) -> None:
        """Should reject None value."""
        with pytest.raises(ValidationError) as exc_info:
            validate_required(None, "test_field")
        assert exc_info.value.field == "test_field"
        assert "required" in exc_info.value.message.lower()

    def test_empty_string_raises_error(self) -> None:
        """Should reject empty string."""
        with pytest.raises(ValidationError) as exc_info:
            validate_required("", "test_field")
        assert exc_info.value.field == "test_field"

    def test_whitespace_only_raises_error(self) -> None:
        """Should reject whitespace-only string."""
        with pytest.raises(ValidationError) as exc_info:
            validate_required("   ", "test_field")
        assert exc_info.value.field == "test_field"


class TestValidateId:
    """Tests for validate_id function."""

    def test_valid_id(self) -> None:
        """Should accept valid ID."""
        assert validate_id("12345", "patient_id") == "12345"

    def test_id_with_whitespace(self) -> None:
        """Should strip whitespace from ID."""
        assert validate_id("  12345  ", "patient_id") == "12345"

    def test_empty_id_raises_error(self) -> None:
        """Should reject empty ID."""
        with pytest.raises(ValidationError) as exc_info:
            validate_id("", "patient_id")
        assert exc_info.value.field == "patient_id"
        assert "required" in exc_info.value.message.lower()

    def test_whitespace_only_id_raises_error(self) -> None:
        """Should reject whitespace-only ID."""
        with pytest.raises(ValidationError) as exc_info:
            validate_id("   ", "provider_id")
        assert exc_info.value.field == "provider_id"


class TestValidationError:
    """Tests for ValidationError exception."""

    def test_error_attributes(self) -> None:
        """Should have field and message attributes."""
        error = ValidationError("test_field", "Test message")
        assert error.field == "test_field"
        assert error.message == "Test message"

    def test_error_string_format(self) -> None:
        """Should format as descriptive string."""
        error = ValidationError("dni", "DNI is required")
        assert "dni" in str(error)
        assert "DNI is required" in str(error)

    def test_is_exception(self) -> None:
        """Should be a proper exception."""
        error = ValidationError("field", "message")
        assert isinstance(error, Exception)
