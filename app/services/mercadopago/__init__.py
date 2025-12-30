"""
MercadoPago webhook support services.

Provides utilities for:
- HTML response page generation for payment redirects
- Payment data extraction and normalization
- Receipt generation and notification workflows
"""

from app.services.mercadopago.payment_mapper import MercadoPagoPaymentMapper
from app.services.mercadopago.receipt_workflow import (
    generate_and_store_receipt,
    send_payment_notification,
    send_text_only_notification,
)
from app.services.mercadopago.response_pages import MercadoPagoResponsePages

__all__ = [
    "MercadoPagoPaymentMapper",
    "MercadoPagoResponsePages",
    "generate_and_store_receipt",
    "send_payment_notification",
    "send_text_only_notification",
]
