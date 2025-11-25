"""
Customer Use Cases

Use cases for customer management following Clean Architecture.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.database import get_db_context
from app.models.db import Customer

logger = logging.getLogger(__name__)


class GetOrCreateCustomerUseCase:
    """
    Use Case: Get or Create Customer

    Handles the business logic for getting an existing customer or creating a new one.
    This is the most common operation in customer management.

    Responsibilities:
    - Check if customer exists
    - Create new customer if needed
    - Update last contact timestamp
    - Handle race conditions safely
    """

    async def execute(self, phone_number: str, profile_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get or create a customer by phone number.

        Args:
            phone_number: Customer's phone number (unique identifier)
            profile_name: Optional profile/display name

        Returns:
            Customer data as dictionary, or None if operation fails

        Example:
            use_case = GetOrCreateCustomerUseCase()
            customer = await use_case.execute("+5491123456789", "John Doe")
        """
        try:
            with get_db_context() as db:
                # Try to get existing customer
                customer = db.query(Customer).filter(Customer.phone_number == phone_number).first()

                if not customer:
                    # Create new customer
                    try:
                        customer = Customer(
                            phone_number=phone_number,
                            profile_name=profile_name,
                            first_contact=datetime.now(timezone.utc),
                            last_contact=datetime.now(timezone.utc),
                            total_interactions=1,
                        )
                        db.add(customer)
                        db.commit()
                        db.refresh(customer)
                        logger.info(f"New customer created: {phone_number}")
                    except Exception as e:
                        # Handle race condition (duplicate key)
                        if "unique constraint" in str(e).lower() or "duplicate key" in str(e).lower():
                            db.rollback()
                            customer = db.query(Customer).filter(Customer.phone_number == phone_number).first()
                            if not customer:
                                logger.error(f"Customer creation failed: {phone_number}")
                                return None
                            logger.info(f"Customer found after race condition: {phone_number}")
                        else:
                            raise
                else:
                    # Update existing customer
                    customer.last_contact = datetime.now(timezone.utc)  # type: ignore
                    customer.total_interactions = (customer.total_interactions or 0) + 1  # type: ignore
                    if profile_name and not customer.profile_name:
                        customer.profile_name = profile_name  # type: ignore
                    db.commit()
                    db.refresh(customer)

                # Convert to dictionary
                customer_dict = {k: v for k, v in customer.__dict__.items() if not k.startswith("_")}
                customer_dict["id"] = str(customer_dict["id"])
                customer_dict.pop("created_at", None)
                customer_dict.pop("updated_at", None)

                return customer_dict

        except Exception as e:
            logger.error(f"Error in GetOrCreateCustomerUseCase: {e}")
            return None
