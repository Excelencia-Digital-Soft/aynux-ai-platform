"""Tests for DebtFormatterService and DebtFormatTemplates."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domains.pharmacy.agents.utils.debt_format_templates import (
    DebtFormatTemplates,
    TemplateNotFoundError,
    get_debt_format_templates,
)
from app.domains.pharmacy.agents.utils.debt_formatter_service import (
    DebtFormatterService,
)
from app.domains.pharmacy.domain.entities.pharmacy_debt import DebtItem, PharmacyDebt
from app.domains.pharmacy.domain.services.auth_level_service import AuthLevel
from app.domains.pharmacy.domain.value_objects.debt_status import DebtStatus


class TestDebtFormatTemplates:
    """Tests for DebtFormatTemplates class."""

    @pytest.fixture
    def valid_templates(self) -> dict:
        """Return valid template structure."""
        return {
            "utility": {
                "no_details": "- Sin detalle",
                "no_invoice": "Sin comprobante",
                "more_products": "... y {remaining} productos mas",
                "more_invoices": "... y {remaining} comprobantes mas",
                "more_items": "... y {remaining} items mas",
                "products_summary": "Productos ({item_count}): ${total}",
            },
            "payment_options": {
                "full": "1. Pago Total: ${amount}",
                "half": "2. Pago Parcial ({percent}%): ${amount}",
                "minimum": "3. Pago Minimo ({percent}%): ${amount}",
                "custom": "4. Otro monto",
            },
            "action_menu": {
                "pay_full": "1. Pagar Total (${amount})",
                "pay_partial": "2. Pagar Parcial ({percent}% = ${amount})",
                "pay_other": "2. Pagar Otro Monto",
                "view_invoices": "3. Ver Detalle",
                "back_to_menu": "4. Volver",
            },
            "smart_debt_response": "Deuda: ${total_debt}",
            "payment_confirm": {
                "partial": "Pago Parcial: ${payment_amount}",
                "full": "Pago Total: ${total_debt}",
            },
        }

    def test_utility_properties_return_values(self, valid_templates: dict) -> None:
        """Test utility properties return correct values."""
        templates = DebtFormatTemplates(valid_templates)

        assert templates.no_details == "- Sin detalle"
        assert templates.no_invoice == "Sin comprobante"
        assert templates.more_products == "... y {remaining} productos mas"
        assert templates.more_invoices == "... y {remaining} comprobantes mas"
        assert templates.more_items == "... y {remaining} items mas"
        assert templates.products_summary == "Productos ({item_count}): ${total}"

    def test_payment_options_returns_values(self, valid_templates: dict) -> None:
        """Test payment option getter returns correct values."""
        templates = DebtFormatTemplates(valid_templates)

        assert templates.get_payment_option("full") == "1. Pago Total: ${amount}"
        assert templates.get_payment_option("half") == "2. Pago Parcial ({percent}%): ${amount}"
        assert templates.get_payment_option("custom") == "4. Otro monto"

    def test_action_menu_returns_values(self, valid_templates: dict) -> None:
        """Test action menu getter returns correct values."""
        templates = DebtFormatTemplates(valid_templates)

        assert templates.get_action_menu_item("pay_full") == "1. Pagar Total (${amount})"
        assert templates.get_action_menu_item("view_invoices") == "3. Ver Detalle"

    def test_response_templates_return_values(self, valid_templates: dict) -> None:
        """Test response templates return correct values."""
        templates = DebtFormatTemplates(valid_templates)

        assert templates.smart_debt_response == "Deuda: ${total_debt}"
        assert templates.payment_confirm_partial == "Pago Parcial: ${payment_amount}"
        assert templates.payment_confirm_full == "Pago Total: ${total_debt}"

    def test_missing_section_raises_error(self) -> None:
        """Test missing section raises TemplateNotFoundError."""
        templates = DebtFormatTemplates({})

        with pytest.raises(TemplateNotFoundError) as exc_info:
            _ = templates.no_details

        assert "utility.no_details" in str(exc_info.value)

    def test_missing_key_raises_error(self, valid_templates: dict) -> None:
        """Test missing key in section raises TemplateNotFoundError."""
        valid_templates["utility"].pop("no_details")
        templates = DebtFormatTemplates(valid_templates)

        with pytest.raises(TemplateNotFoundError) as exc_info:
            _ = templates.no_details

        assert "no_details" in str(exc_info.value)

    def test_missing_smart_debt_response_raises_error(self) -> None:
        """Test missing smart_debt_response raises TemplateNotFoundError."""
        templates = DebtFormatTemplates({"utility": {}})

        with pytest.raises(TemplateNotFoundError) as exc_info:
            _ = templates.smart_debt_response

        assert "smart_debt_response" in str(exc_info.value)

    def test_get_debt_format_templates_returns_singleton(self) -> None:
        """Test get_debt_format_templates returns singleton instance."""
        # This test verifies the singleton pattern works
        templates1 = get_debt_format_templates()
        templates2 = get_debt_format_templates()

        assert templates1 is templates2


class TestDebtFormatterService:
    """Tests for DebtFormatterService class."""

    @pytest.fixture
    def sample_items(self) -> list[DebtItem]:
        """Create sample debt items for testing."""
        return [
            DebtItem(
                description="Producto 1",
                amount=Decimal("100.00"),
                invoice_number="FAC-001",
                invoice_date="2024-01-01",
            ),
            DebtItem(
                description="Producto 2",
                amount=Decimal("200.00"),
                invoice_number="FAC-001",
                invoice_date="2024-01-01",
            ),
            DebtItem(
                description="Producto 3",
                amount=Decimal("150.00"),
                invoice_number="FAC-002",
                invoice_date="2024-01-02",
            ),
        ]

    @pytest.fixture
    def sample_debt(self, sample_items: list[DebtItem]) -> PharmacyDebt:
        """Create sample PharmacyDebt for testing."""
        return PharmacyDebt(
            id="DEBT-001",
            customer_id="123",
            customer_name="Juan Perez",
            total_debt=Decimal("450.00"),
            status=DebtStatus.PENDING,
            items=sample_items,
        )

    class TestFormatItems:
        """Tests for format_items method."""

        def test_empty_items_returns_no_details(self) -> None:
            """Test empty items list returns no_details template."""
            result = DebtFormatterService.format_items([])
            assert "Sin detalle" in result or "no_details" in result.lower()

        def test_formats_items_with_amounts(self, sample_items: list) -> None:
            """Test items are formatted with descriptions and amounts."""
            result = DebtFormatterService.format_items(sample_items)

            assert "Producto 1" in result
            assert "100" in result
            assert "Producto 2" in result

        def test_limits_displayed_items(self) -> None:
            """Test items are limited to MAX_ITEMS_DISPLAY."""
            many_items = [
                DebtItem(description=f"Item {i}", amount=Decimal("10.00"))
                for i in range(15)
            ]

            result = DebtFormatterService.format_items(many_items)

            # Should show "more products" message
            assert "productos" in result.lower() or "mas" in result.lower()

    class TestFormatItemsByAuthLevel:
        """Tests for format_items_by_auth_level method."""

        def test_strong_auth_shows_full_details(self, sample_items: list) -> None:
            """Test STRONG auth level shows full item details."""
            result = DebtFormatterService.format_items_by_auth_level(
                sample_items, AuthLevel.STRONG
            )

            assert "Producto 1" in result
            assert "100" in result

        def test_medium_auth_shows_summary(self, sample_items: list) -> None:
            """Test MEDIUM auth level shows summary only."""
            result = DebtFormatterService.format_items_by_auth_level(
                sample_items, AuthLevel.MEDIUM
            )

            # Should show item count and total, not individual items
            assert "3" in result or "items" in result.lower()
            assert "450" in result

        def test_weak_auth_shows_summary(self, sample_items: list) -> None:
            """Test WEAK auth level shows summary only."""
            result = DebtFormatterService.format_items_by_auth_level(
                sample_items, AuthLevel.WEAK
            )

            # Should show item count and total, not individual items
            assert "3" in result or "items" in result.lower()

    class TestFormatItemsWithInvoices:
        """Tests for format_items_with_invoices method."""

        def test_groups_items_by_invoice(self, sample_items: list) -> None:
            """Test items are grouped by invoice number."""
            result = DebtFormatterService.format_items_with_invoices(sample_items)

            assert "FAC-001" in result
            assert "FAC-002" in result

        def test_shows_invoice_totals(self, sample_items: list) -> None:
            """Test each invoice group shows total amount."""
            result = DebtFormatterService.format_items_with_invoices(sample_items)

            # FAC-001 total = 100 + 200 = 300
            assert "300" in result
            # FAC-002 total = 150
            assert "150" in result

        def test_empty_items_returns_no_details(self) -> None:
            """Test empty items returns no_details template."""
            result = DebtFormatterService.format_items_with_invoices([])
            assert "Sin detalle" in result or "no_details" in result.lower()

    class TestFormatPaymentOptions:
        """Tests for format_payment_options method."""

        def test_formats_full_payment_option(self) -> None:
            """Test full payment option is formatted."""
            options = {"full": 1000.0, "half": 500.0, "minimum": 300.0}

            result = DebtFormatterService.format_payment_options(options, None)

            assert "1,000" in result or "1000" in result
            assert "Total" in result or "total" in result.lower()

        def test_formats_partial_options(self) -> None:
            """Test partial payment options are formatted."""
            options = {"full": 1000.0, "half": 500.0}

            result = DebtFormatterService.format_payment_options(options, None)

            assert "500" in result

    class TestFormatSmartDebtResponse:
        """Tests for format_smart_debt_response method."""

        def test_includes_customer_name(self, sample_debt: PharmacyDebt) -> None:
            """Test response includes customer name."""
            options = {"full": 450.0}

            result = DebtFormatterService.format_smart_debt_response(
                sample_debt, options, None, AuthLevel.STRONG
            )

            assert "Juan Perez" in result

        def test_includes_total_debt(self, sample_debt: PharmacyDebt) -> None:
            """Test response includes total debt amount."""
            options = {"full": 450.0}

            result = DebtFormatterService.format_smart_debt_response(
                sample_debt, options, None, AuthLevel.STRONG
            )

            assert "450" in result

    class TestFormatPaymentReadyResponse:
        """Tests for format_payment_ready_response method."""

        def test_full_payment_response(self, sample_debt: PharmacyDebt) -> None:
            """Test full payment confirmation response."""
            result = DebtFormatterService.format_payment_ready_response(sample_debt)

            assert "Juan Perez" in result
            assert "450" in result

        def test_partial_payment_response(self, sample_debt: PharmacyDebt) -> None:
            """Test partial payment confirmation response."""
            result = DebtFormatterService.format_payment_ready_response(
                sample_debt, payment_amount=200.0
            )

            assert "Juan Perez" in result
            assert "200" in result
            # Should show remaining amount (450 - 200 = 250)
            assert "250" in result


class TestTemplateNotFoundError:
    """Tests for TemplateNotFoundError exception."""

    def test_error_message_with_section(self) -> None:
        """Test error message includes section and key."""
        error = TemplateNotFoundError("no_details", "utility")

        assert "utility.no_details" in str(error)
        assert "debt_format.yaml" in str(error)

    def test_error_message_without_section(self) -> None:
        """Test error message with only key."""
        error = TemplateNotFoundError("smart_debt_response")

        assert "smart_debt_response" in str(error)
        assert "debt_format.yaml" in str(error)

    def test_error_attributes(self) -> None:
        """Test error attributes are set correctly."""
        error = TemplateNotFoundError("key", "section")

        assert error.template_key == "key"
        assert error.section == "section"
