import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.database import get_db_context
from app.models.database import (
    Customer,
    ProductInquiry,
)

logger = logging.getLogger(__name__)


class CustomerService:
    """Servicio para gestionar clientes"""

    async def get_or_create_customer(
        self, phone_number: str, profile_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Obtiene o crea un cliente y devuelve sus datos como diccionario"""
        try:
            with get_db_context() as db:
                customer = db.query(Customer).filter(Customer.phone_number == phone_number).first()

                if not customer:
                    customer = Customer(
                        phone_number=phone_number,
                        profile_name=profile_name,
                        first_contact=datetime.now(timezone.utc),
                        last_contact=datetime.now(timezone.utc),
                    )
                    db.add(customer)
                    db.commit()
                    db.refresh(customer)
                    logger.info(f"New customer created: {phone_number}")
                else:
                    # Actualizar último contacto
                    customer.last_contact = datetime.now(timezone.utc)  # type: ignore
                    customer.total_interactions = customer.total_interactions + 1  # type: ignore
                    if profile_name and customer.profile_name is None:
                        customer.profile_name = profile_name  # type: ignore
                    db.commit()
                    db.refresh(customer)

                # Convertir a diccionario para evitar problemas de sesión
                return {
                    "id": str(customer.id),
                    "phone_number": customer.phone_number,
                    "name": customer.name,
                    "profile_name": customer.profile_name,
                    "total_interactions": customer.total_interactions,
                    "total_inquiries": customer.total_inquiries,
                    "interests": customer.interests,
                    "budget_range": customer.budget_range,
                    "preferred_brands": customer.preferred_brands,
                    "active": customer.active,
                    "blocked": customer.blocked,
                    "vip": customer.vip,
                    "first_contact": customer.first_contact,
                    "last_contact": customer.last_contact,
                }

        except Exception as e:
            logger.error(f"Error getting/creating customer: {e}")
            return None

    async def update_customer_interests(self, customer_id: str, interests: List[str]) -> bool:
        """Actualiza los intereses del cliente"""
        try:
            with get_db_context() as db:
                customer = db.query(Customer).filter(Customer.id == customer_id).first()

                if customer:
                    customer.interests = interests  # type: ignore
                    customer.updated_at = datetime.now(timezone.utc)  # type: ignore
                    db.commit()
                    return True

                return False

        except Exception as e:
            logger.error(f"Error updating customer interests: {e}")
            return False

    async def log_product_inquiry(
        self,
        customer_id: str,
        inquiry_type: str,
        inquiry_text: str,
        product_id: Optional[str] = None,
        category_id: Optional[str] = None,
        budget_mentioned: Optional[float] = None,
    ) -> bool:
        """Registra una consulta de producto"""
        try:
            with get_db_context() as db:
                inquiry = ProductInquiry(
                    customer_id=customer_id,
                    product_id=product_id,
                    category_id=category_id,
                    inquiry_type=inquiry_type,
                    inquiry_text=inquiry_text,
                    budget_mentioned=budget_mentioned,
                )
                db.add(inquiry)

                # Actualizar contador de consultas del cliente
                customer = db.query(Customer).filter(Customer.id == customer_id).first()
                if customer:
                    customer.total_inquiries = customer.total_inquiries + 1  # type: ignore

                db.commit()
                return True

        except Exception as e:
            logger.error(f"Error logging product inquiry: {e}")
            return False
