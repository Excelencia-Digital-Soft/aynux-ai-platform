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
                # Intentar obtener cliente existente
                customer = db.query(Customer).filter(Customer.phone_number == phone_number).first()

                if not customer:
                    try:
                        # Crear nuevo cliente
                        customer = Customer(
                            phone_number=phone_number,
                            profile_name=profile_name,
                            first_contact=datetime.now(timezone.utc),
                            last_contact=datetime.now(timezone.utc),
                            total_interactions=1
                        )
                        db.add(customer)
                        db.commit()
                        db.refresh(customer)
                        logger.info(f"DB: New customer created: {phone_number}")
                    except Exception as e:
                        # Manejar posible condición de carrera
                        if "unique constraint" in str(e).lower() or "duplicate key" in str(e).lower():
                            db.rollback()
                            # Intentar obtener el cliente que fue creado por otro proceso
                            customer = db.query(Customer).filter(Customer.phone_number == phone_number).first()
                            if not customer:
                                logger.error(f"Customer creation failed and customer not found: {phone_number}")
                                return None
                            logger.info(f"DB: Customer existed after race condition: {phone_number}")
                        else:
                            raise
                else:
                    # Actualizar último contacto
                    customer.last_contact = datetime.now(timezone.utc)  # type: ignore
                    customer.total_interactions = (customer.total_interactions or 0) + 1  # type: ignore
                    if profile_name and customer.profile_name is None:
                        customer.profile_name = profile_name  # type: ignore
                    db.commit()
                    db.refresh(customer)

                # Convertir a diccionario para evitar problemas de sesión
                # Usar el método __dict__ de SQLAlchemy y filtrar columnas internas
                customer_dict = {k: v for k, v in customer.__dict__.items() if not k.startswith("_")}
                # Convertir UUID a string
                customer_dict["id"] = str(customer_dict["id"])
                # Excluir campos no necesarios
                customer_dict.pop("created_at", None)
                customer_dict.pop("updated_at", None)
                return customer_dict

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
