"""
Debt Formatter Service

Utility for formatting debt information for user presentation.
Handles different display formats based on authentication level and context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.domains.pharmacy.domain.entities.pharmacy_debt import DebtItem, PharmacyDebt
from app.domains.pharmacy.domain.services.auth_level_service import AuthLevel

if TYPE_CHECKING:
    from app.core.tenancy.pharmacy_config_service import PharmacyConfig


# Maximum number of items to display in debt response
MAX_ITEMS_DISPLAY = 10


class DebtFormatterService:
    """
    Formats debt information for user presentation.

    Handles:
    - Item formatting with display limits
    - Auth level-based ofuscation
    - Invoice grouping and details
    - Payment options formatting
    - Smart debt response formatting

    Single Responsibility: Format debt data for presentation.
    """

    @classmethod
    def format_items(cls, items: list[DebtItem]) -> str:
        """
        Format debt items with display limit.

        Args:
            items: List of DebtItem objects

        Returns:
            Formatted items string
        """
        if not items:
            return "- Sin detalle disponible"

        # Limit items shown to avoid huge messages
        display_items = items[:MAX_ITEMS_DISPLAY]
        formatted = "\n".join(
            [f"- {item.description}: ${float(item.amount):,.2f}" for item in display_items]
        )

        # Add summary if there are more items
        if len(items) > MAX_ITEMS_DISPLAY:
            remaining = len(items) - MAX_ITEMS_DISPLAY
            formatted += f"\n\n... y {remaining} productos más en tu cuenta."

        return formatted

    @classmethod
    def format_items_by_auth_level(
        cls,
        items: list[DebtItem],
        auth_level: str,
    ) -> str:
        """
        Format debt items with ofuscation based on auth level.

        Args:
            items: List of debt items
            auth_level: Authentication level (STRONG, MEDIUM, WEAK)

        Returns:
            Formatted items string
        """
        if not items:
            return "- Sin detalle disponible"

        if auth_level == AuthLevel.STRONG:
            # Full details for phone-verified customers
            return cls.format_items(items)

        # Ofuscated view for MEDIUM/WEAK auth
        total = sum(float(item.amount) for item in items)
        item_count = len(items)
        return f"- Productos en cuenta ({item_count} items): *${total:,.2f}*"

    @classmethod
    def format_items_with_invoices(cls, items: list[DebtItem]) -> str:
        """
        Format debt items grouped by invoice with date and invoice number.

        CASO 3 from pharmacy_flujo_mejorado_v2.md:
        Shows invoice-level details with dates.

        Args:
            items: List of debt items

        Returns:
            Formatted string with invoice details
        """
        if not items:
            return "- Sin detalle disponible"

        # Group items by invoice
        invoices: dict[str, list[DebtItem]] = {}
        for item in items:
            invoice_key = item.invoice_number or "Sin comprobante"
            if invoice_key not in invoices:
                invoices[invoice_key] = []
            invoices[invoice_key].append(item)

        # Format each invoice group
        lines: list[str] = []
        for invoice_num, invoice_items in list(invoices.items())[:5]:  # Limit to 5 invoices
            invoice_total = sum(float(item.amount) for item in invoice_items)
            # Get date from first item
            date_str = ""
            if invoice_items and invoice_items[0].invoice_date:
                date_str = f" ({invoice_items[0].invoice_date})"
            lines.append(f"📄 *{invoice_num}*{date_str}: ${invoice_total:,.2f}")

        if len(invoices) > 5:
            remaining = len(invoices) - 5
            lines.append(f"... y {remaining} comprobantes más")

        return "\n".join(lines)

    @classmethod
    def format_invoice_details(cls, items: list[DebtItem]) -> str:
        """
        Format full invoice details with all products.

        Args:
            items: List of debt items

        Returns:
            Formatted string with full product details per invoice
        """
        if not items:
            return "Sin detalle disponible"

        # Group items by invoice
        invoices: dict[str, list[DebtItem]] = {}
        for item in items:
            invoice_key = item.invoice_number or "Sin comprobante"
            if invoice_key not in invoices:
                invoices[invoice_key] = []
            invoices[invoice_key].append(item)

        # Format each invoice with products
        lines: list[str] = []
        for invoice_num, invoice_items in invoices.items():
            invoice_total = sum(float(item.amount) for item in invoice_items)
            date_str = ""
            if invoice_items and invoice_items[0].invoice_date:
                date_str = f" - {invoice_items[0].invoice_date}"
            lines.append(f"\n📄 *{invoice_num}*{date_str}")
            lines.append(f"Total: ${invoice_total:,.2f}")
            lines.append("─" * 20)
            for item in invoice_items[:10]:  # Max 10 items per invoice
                lines.append(f"  • {item.description}: ${float(item.amount):,.2f}")
            if len(invoice_items) > 10:
                lines.append(f"  ... y {len(invoice_items) - 10} items más")

        return "\n".join(lines)

    @classmethod
    def format_payment_options(
        cls,
        options: dict[str, float],
        pharmacy_config: PharmacyConfig | None,
    ) -> str:
        """
        Format payment options as a numbered list for user selection.

        Args:
            options: Payment options dictionary
            pharmacy_config: Pharmacy configuration for percentage labels

        Returns:
            Formatted string with numbered options
        """
        if pharmacy_config:
            half_pct = pharmacy_config.payment_option_half_percent
            min_pct = pharmacy_config.payment_option_minimum_percent
        else:
            half_pct = 50
            min_pct = 30

        lines: list[str] = []
        lines.append(f"*1.* Pago Total: *${options['full']:,.2f}*")

        if "half" in options:
            lines.append(f"*2.* Pago Parcial ({half_pct}%): *${options['half']:,.2f}*")

        if "minimum" in options:
            lines.append(f"*3.* Pago Mínimo ({min_pct}%): *${options['minimum']:,.2f}*")

        lines.append("*4.* Otro monto (personalizado)")

        return "\n".join(lines)

    @classmethod
    def format_debt_action_menu(
        cls,
        options: dict[str, float],
        pharmacy_config: PharmacyConfig | None,
    ) -> str:
        """
        Format post-debt action menu.

        CASO 3 from pharmacy_flujo_mejorado_v2.md:
        1️⃣ Pagar total
        2️⃣ Pagar parcial
        3️⃣ Ver detalle de facturas
        4️⃣ Volver al menú

        Args:
            options: Payment options dictionary
            pharmacy_config: Pharmacy configuration

        Returns:
            Formatted menu string
        """
        lines: list[str] = []

        # Option 1: Pay total
        lines.append(f"1️⃣ *Pagar Total* (${options['full']:,.2f})")

        # Option 2: Pay partial (show half or minimum if available)
        if "half" in options:
            half_pct = pharmacy_config.payment_option_half_percent if pharmacy_config else 50
            lines.append(f"2️⃣ *Pagar Parcial* ({half_pct}% = ${options['half']:,.2f})")
        elif "minimum" in options:
            min_pct = pharmacy_config.payment_option_minimum_percent if pharmacy_config else 30
            lines.append(f"2️⃣ *Pagar Parcial* ({min_pct}% = ${options['minimum']:,.2f})")
        else:
            lines.append("2️⃣ *Pagar Otro Monto*")

        # Option 3: View invoice details
        lines.append("3️⃣ *Ver Detalle de Facturas*")

        # Option 4: Return to menu
        lines.append("4️⃣ *Volver al Menú*")

        return "\n".join(lines)

    @classmethod
    def format_smart_debt_response(
        cls,
        debt: PharmacyDebt,
        payment_options: dict[str, float],
        pharmacy_config: PharmacyConfig | None,
        auth_level: str,
    ) -> str:
        """
        Format debt response with Smart Debt Negotiation payment options.

        CASO 3 from pharmacy_flujo_mejorado_v2.md:
        Shows debt with invoice details followed by action menu.

        Args:
            debt: PharmacyDebt entity
            payment_options: Pre-calculated payment options
            pharmacy_config: Pharmacy configuration
            auth_level: Authentication level for ofuscation

        Returns:
            Formatted response with payment options and action menu
        """
        total_debt = float(debt.total_debt)

        # Get pharmacy name for personalization
        pharmacy_name = pharmacy_config.pharmacy_name if pharmacy_config else "Farmacia"

        # Format items based on auth level - use invoice format for STRONG auth
        if auth_level == AuthLevel.STRONG and debt.items:
            items_text = cls.format_items_with_invoices(debt.items)
        else:
            items_text = cls.format_items_by_auth_level(debt.items, auth_level)

        # Format action menu
        options_text = cls.format_debt_action_menu(payment_options, pharmacy_config)

        response = f"""💊 *{pharmacy_name}*

Hola *{debt.customer_name}*, tu cuenta:

━━━━━━━━━━━━━━━━━━━━
💰 *Deuda Total: ${total_debt:,.2f}*
━━━━━━━━━━━━━━━━━━━━

📄 *Comprobantes:*
{items_text}

━━━━━━━━━━━━━━━━━━━━
📋 *¿Qué deseas hacer?*

{options_text}

_Responde con el número de la opción (1-4)_"""

        return response

    @classmethod
    def format_payment_ready_response(
        cls,
        debt: PharmacyDebt,
        payment_amount: float | None = None,
    ) -> str:
        """
        Format response when user wants to pay directly.

        This is called when the user said "quiero pagar" and we auto-fetched debt.

        Args:
            debt: PharmacyDebt entity
            payment_amount: Optional payment amount if user specified one

        Returns:
            Formatted response asking for payment confirmation
        """
        items_text = cls.format_items(debt.items[:5])  # Show fewer items for payment flow
        total_debt = float(debt.total_debt)

        if payment_amount and payment_amount < total_debt:
            # Partial payment
            remaining = total_debt - payment_amount
            return f"""💰 **Pago Parcial**

Hola {debt.customer_name}, tu deuda total es **${total_debt:,.2f}**.

Quieres pagar: **${payment_amount:,.2f}**
Saldo restante: **${remaining:,.2f}**

**Algunos productos en tu cuenta:**
{items_text}

Para confirmar este pago parcial, responde *SI*.
Para cancelar, responde *NO*."""
        else:
            # Full payment
            return f"""💰 **Confirmar Pago**

Hola {debt.customer_name}, tu deuda pendiente es **${total_debt:,.2f}**.

**Algunos productos en tu cuenta:**
{items_text}

Para confirmar y generar el recibo de pago, responde *SI*.
Para cancelar, responde *NO*.

💡 *Tip: También puedes pagar un monto parcial escribiendo "pagar X" (ej: "pagar 5000").*"""


# Singleton instance
_formatter: DebtFormatterService | None = None


def get_debt_formatter() -> DebtFormatterService:
    """
    Get singleton formatter instance.

    Returns:
        DebtFormatterService instance
    """
    global _formatter
    if _formatter is None:
        _formatter = DebtFormatterService()
    return _formatter


__all__ = [
    "DebtFormatterService",
    "get_debt_formatter",
    "MAX_ITEMS_DISPLAY",
]
