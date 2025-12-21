"""
Payment Receipt PDF Generator

Generates professional PDF receipts for pharmacy payments using fpdf2.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from fpdf import FPDF

logger = logging.getLogger(__name__)


class PaymentReceiptGenerator:
    """
    Generates PDF receipts for pharmacy payments.

    Creates professional receipts with:
    - Pharmacy branding (header)
    - Payment details (amount, receipt number)
    - Customer balance info
    - MercadoPago operation reference
    - QR code (optional, for verification)
    """

    # Page dimensions and margins (A4)
    PAGE_WIDTH = 210
    PAGE_HEIGHT = 297
    MARGIN = 20

    # Colors (RGB)
    PRIMARY_COLOR = (0, 102, 179)  # Blue
    SECONDARY_COLOR = (100, 100, 100)  # Gray
    ACCENT_COLOR = (0, 150, 0)  # Green for positive values
    TEXT_COLOR = (50, 50, 50)  # Dark gray

    def __init__(
        self,
        pharmacy_name: str = "Farmacia",
        pharmacy_address: str | None = None,
        pharmacy_phone: str | None = None,
        logo_path: str | None = None,
    ):
        """
        Initialize the receipt generator.

        Args:
            pharmacy_name: Name to display on receipt header
            pharmacy_address: Optional address line
            pharmacy_phone: Optional phone number
            logo_path: Optional path to logo image
        """
        self.pharmacy_name = pharmacy_name
        self.pharmacy_address = pharmacy_address
        self.pharmacy_phone = pharmacy_phone
        self.logo_path = logo_path

    def generate(
        self,
        amount: float | Decimal,
        receipt_number: str,
        new_balance: float | Decimal | str,
        mp_payment_id: str,
        customer_name: str | None = None,
        payment_date: datetime | None = None,
    ) -> bytes:
        """
        Generate a PDF receipt for a payment.

        Args:
            amount: Payment amount
            receipt_number: PLEX receipt number (e.g., "RC X 0001-00016790")
            new_balance: Customer's new balance after payment
            mp_payment_id: MercadoPago payment ID for reference
            customer_name: Optional customer name
            payment_date: Payment date/time (defaults to now)

        Returns:
            PDF content as bytes
        """
        if payment_date is None:
            payment_date = datetime.now(UTC)

        # Parse new_balance if it's a string
        if isinstance(new_balance, str):
            try:
                new_balance = float(new_balance.replace(",", ".").replace(" ", ""))
            except ValueError:
                new_balance = 0.0

        amount_float = float(amount) if isinstance(amount, Decimal) else amount
        balance_float = float(new_balance) if isinstance(new_balance, Decimal) else new_balance

        logger.info(
            f"Generating receipt PDF: receipt={receipt_number}, "
            f"amount=${amount_float:,.2f}, mp_id={mp_payment_id}"
        )

        # Create PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Set default font
        pdf.set_font("Helvetica", size=10)

        # Generate receipt content
        self._add_header(pdf)
        self._add_title(pdf)
        self._add_payment_details(
            pdf,
            payment_date=payment_date,
            receipt_number=receipt_number,
            mp_payment_id=mp_payment_id,
            customer_name=customer_name,
        )
        self._add_amounts(pdf, amount=amount_float, new_balance=balance_float)
        self._add_footer(pdf)

        # Output to bytes
        # fpdf2's output() returns bytearray, convert to bytes
        pdf_bytes = bytes(pdf.output())

        logger.info(f"Receipt PDF generated: {len(pdf_bytes)} bytes")
        return pdf_bytes

    def _add_header(self, pdf: FPDF) -> None:
        """Add pharmacy header with optional logo."""
        pdf.set_y(self.MARGIN)

        # Add logo if available
        if self.logo_path:
            try:
                pdf.image(self.logo_path, x=self.MARGIN, y=self.MARGIN, w=30)
                pdf.set_x(self.MARGIN + 35)
            except Exception as e:
                logger.warning(f"Could not load logo: {e}")

        # Pharmacy name
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(*self.PRIMARY_COLOR)
        pdf.cell(0, 10, self.pharmacy_name, align="C", new_x="LMARGIN", new_y="NEXT")

        # Address and phone
        if self.pharmacy_address or self.pharmacy_phone:
            pdf.set_font("Helvetica", size=9)
            pdf.set_text_color(*self.SECONDARY_COLOR)
            contact_info = []
            if self.pharmacy_address:
                contact_info.append(self.pharmacy_address)
            if self.pharmacy_phone:
                contact_info.append(f"Tel: {self.pharmacy_phone}")
            pdf.cell(0, 5, " | ".join(contact_info), align="C", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(5)

    def _add_title(self, pdf: FPDF) -> None:
        """Add receipt title with decorative line."""
        # Decorative line
        pdf.set_draw_color(*self.PRIMARY_COLOR)
        pdf.set_line_width(0.5)
        y_pos = pdf.get_y()
        pdf.line(self.MARGIN, y_pos, self.PAGE_WIDTH - self.MARGIN, y_pos)

        pdf.ln(8)

        # Title
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(*self.PRIMARY_COLOR)
        pdf.cell(0, 12, "COMPROBANTE DE PAGO", align="C", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(3)

        # Another line
        y_pos = pdf.get_y()
        pdf.line(self.MARGIN, y_pos, self.PAGE_WIDTH - self.MARGIN, y_pos)

        pdf.ln(10)

    def _add_payment_details(
        self,
        pdf: FPDF,
        payment_date: datetime,
        receipt_number: str,
        mp_payment_id: str,
        customer_name: str | None,
    ) -> None:
        """Add payment details section."""
        pdf.set_text_color(*self.TEXT_COLOR)

        # Details box
        box_x = self.MARGIN
        box_y = pdf.get_y()
        box_width = self.PAGE_WIDTH - 2 * self.MARGIN
        box_height = 50 if customer_name else 40

        # Draw rounded rectangle background
        pdf.set_fill_color(245, 245, 245)
        pdf.set_draw_color(200, 200, 200)
        pdf.rect(box_x, box_y, box_width, box_height, style="FD")

        pdf.set_xy(box_x + 5, box_y + 5)

        # Date
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(40, 7, "Fecha:", new_x="RIGHT")
        pdf.set_font("Helvetica", size=10)
        date_str = payment_date.strftime("%d/%m/%Y %H:%M")
        pdf.cell(0, 7, date_str, new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(box_x + 5)

        # Receipt number
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(40, 7, "Comprobante:", new_x="RIGHT")
        pdf.set_font("Helvetica", size=10)
        pdf.cell(0, 7, receipt_number, new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(box_x + 5)

        # MP Payment ID
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(40, 7, "Operacion MP:", new_x="RIGHT")
        pdf.set_font("Helvetica", size=10)
        pdf.cell(0, 7, mp_payment_id, new_x="LMARGIN", new_y="NEXT")

        # Customer name (if provided)
        if customer_name:
            pdf.set_x(box_x + 5)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(40, 7, "Cliente:", new_x="RIGHT")
            pdf.set_font("Helvetica", size=10)
            pdf.cell(0, 7, customer_name, new_x="LMARGIN", new_y="NEXT")

        pdf.set_y(box_y + box_height + 10)

    def _add_amounts(self, pdf: FPDF, amount: float, new_balance: float) -> None:
        """Add payment amounts section with emphasis."""
        # Amounts section
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*self.TEXT_COLOR)

        # Create a centered box for amounts
        box_width = 120
        box_x = (self.PAGE_WIDTH - box_width) / 2
        box_y = pdf.get_y()

        # Amount paid - green background
        pdf.set_fill_color(230, 255, 230)
        pdf.set_draw_color(*self.ACCENT_COLOR)
        pdf.rect(box_x, box_y, box_width, 25, style="FD")

        pdf.set_xy(box_x + 5, box_y + 5)
        pdf.cell(60, 7, "Monto Pagado:", new_x="RIGHT")
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(*self.ACCENT_COLOR)
        pdf.cell(0, 7, f"${amount:,.2f}", new_x="LMARGIN", new_y="NEXT")

        pdf.set_xy(box_x + 5, box_y + 15)
        pdf.set_font("Helvetica", size=9)
        pdf.set_text_color(*self.SECONDARY_COLOR)
        pdf.cell(0, 5, "Pago acreditado exitosamente", align="C", new_x="LMARGIN", new_y="NEXT")

        # New balance
        pdf.set_y(box_y + 30)
        pdf.set_fill_color(240, 240, 255)
        pdf.set_draw_color(*self.PRIMARY_COLOR)
        pdf.rect(box_x, pdf.get_y(), box_width, 20, style="FD")

        pdf.set_xy(box_x + 5, pdf.get_y() + 5)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*self.TEXT_COLOR)
        pdf.cell(60, 7, "Nuevo Saldo:", new_x="RIGHT")
        pdf.set_font("Helvetica", "B", 13)

        # Color based on balance (negative = debt)
        if new_balance < 0:
            pdf.set_text_color(200, 50, 50)  # Red for debt
            balance_str = f"-${abs(new_balance):,.2f}"
        else:
            pdf.set_text_color(*self.PRIMARY_COLOR)
            balance_str = f"${new_balance:,.2f}"

        pdf.cell(0, 7, balance_str, new_x="LMARGIN", new_y="NEXT")

        pdf.ln(15)

    def _add_footer(self, pdf: FPDF) -> None:
        """Add footer with thank you message."""
        pdf.set_text_color(*self.SECONDARY_COLOR)
        pdf.set_font("Helvetica", "I", 10)

        # Thank you message
        pdf.ln(10)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*self.PRIMARY_COLOR)
        pdf.cell(0, 8, "Gracias por su pago", align="C", new_x="LMARGIN", new_y="NEXT")

        # Timestamp
        pdf.set_font("Helvetica", size=8)
        pdf.set_text_color(*self.SECONDARY_COLOR)
        generated_at = datetime.now(UTC).strftime("%d/%m/%Y %H:%M:%S UTC")
        pdf.cell(0, 5, f"Generado: {generated_at}", align="C", new_x="LMARGIN", new_y="NEXT")

        # Decorative line at bottom
        pdf.ln(5)
        y_pos = pdf.get_y()
        pdf.set_draw_color(*self.PRIMARY_COLOR)
        pdf.set_line_width(0.3)
        pdf.line(self.MARGIN + 30, y_pos, self.PAGE_WIDTH - self.MARGIN - 30, y_pos)
