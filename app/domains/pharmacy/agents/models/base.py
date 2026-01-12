"""Base model configuration for pharmacy state models."""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, ConfigDict


class PharmacyStateModel(BaseModel):
    """
    Base class for all pharmacy state models.

    Provides common configuration and utility methods for
    state extraction and serialization.
    """

    model_config = ConfigDict(
        extra="ignore",  # Ignore extra fields when validating
        validate_default=True,
        populate_by_name=True,
    )

    @classmethod
    def from_state(cls, state_dict: dict[str, Any]) -> Self:
        """
        Extract model fields from a state dictionary.

        Uses model_validate with extra="ignore" to safely extract
        only the fields defined in this model.

        Args:
            state_dict: Current state dictionary (TypedDict or dict)

        Returns:
            Model instance with extracted values
        """
        return cls.model_validate(state_dict)

    def to_state_update(self) -> dict[str, Any]:
        """
        Convert to state update dictionary, excluding None values.

        Returns:
            Dictionary with only non-None values for state merging
        """
        return self.model_dump(exclude_none=True)

    def to_full_state(self) -> dict[str, Any]:
        """
        Convert to complete state dictionary, including None values.

        Returns:
            Dictionary with all fields including None values
        """
        return self.model_dump()


__all__ = ["PharmacyStateModel"]
