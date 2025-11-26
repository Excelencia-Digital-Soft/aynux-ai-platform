"""
SKU (Stock Keeping Unit) Value Object for E-commerce Domain

Represents a unique product identifier with validation.
"""

import re
from dataclasses import dataclass

from app.core.domain import ValueObject


@dataclass(frozen=True)
class SKU(ValueObject):
    """
    SKU value object for product identification.

    SKUs follow a standardized format for easy categorization and tracking.
    Format: CATEGORY-SUBCATEGORY-SEQUENCE (e.g., "ELEC-LAPTOP-00123")

    Example:
        ```python
        sku = SKU(value="ELEC-LAPTOP-00123")
        category = sku.get_category()  # "ELEC"
        ```
    """

    value: str

    # SKU pattern: 2-6 uppercase letters, optional hyphen-separated parts
    SKU_PATTERN = re.compile(r"^[A-Z0-9]{2,10}(-[A-Z0-9]{2,10})*$")

    def _validate(self) -> None:
        """Validate SKU format."""
        # Normalize to uppercase
        normalized = self.value.upper().strip()
        object.__setattr__(self, "value", normalized)

        if not self.value:
            raise ValueError("SKU cannot be empty")

        if len(self.value) < 3:
            raise ValueError("SKU must be at least 3 characters")

        if len(self.value) > 50:
            raise ValueError("SKU cannot exceed 50 characters")

        if not self.SKU_PATTERN.match(self.value):
            raise ValueError(f"Invalid SKU format: {self.value}. Expected format: CATEGORY-SUBCATEGORY-SEQUENCE")

    def get_category(self) -> str:
        """
        Extract category code from SKU.

        Returns:
            First segment of SKU (category code)
        """
        parts = self.value.split("-")
        return parts[0] if parts else ""

    def get_subcategory(self) -> str | None:
        """
        Extract subcategory code from SKU.

        Returns:
            Second segment of SKU or None if not present
        """
        parts = self.value.split("-")
        return parts[1] if len(parts) > 1 else None

    def get_sequence(self) -> str | None:
        """
        Extract sequence/serial from SKU.

        Returns:
            Last segment of SKU (usually the unique identifier)
        """
        parts = self.value.split("-")
        return parts[-1] if len(parts) > 1 else None

    def matches_category(self, category: str) -> bool:
        """Check if SKU belongs to a category."""
        return self.get_category().upper() == category.upper()

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"SKU('{self.value}')"

    @classmethod
    def generate(cls, category: str, subcategory: str | None = None, sequence: int = 1) -> "SKU":
        """
        Generate a new SKU.

        Args:
            category: Category code (2-6 chars)
            subcategory: Optional subcategory code
            sequence: Sequence number

        Returns:
            New SKU instance
        """
        parts = [category.upper()[:6]]
        if subcategory:
            parts.append(subcategory.upper()[:6])
        parts.append(f"{sequence:05d}")

        return cls(value="-".join(parts))
