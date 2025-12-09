"""
Debt Status Value Object

Enumeration of valid debt statuses with transition validation.
"""

from enum import Enum


class DebtStatus(str, Enum):
    """Status of pharmacy debt in the workflow."""

    PENDING = "pending"  # Initial state - awaiting customer action
    CONFIRMED = "confirmed"  # Customer confirmed the debt
    INVOICED = "invoiced"  # Invoice generated
    PAID = "paid"  # Debt paid
    CANCELLED = "cancelled"  # Debt cancelled

    def can_transition_to(self, new_status: "DebtStatus") -> bool:
        """
        Check if transition to new status is valid.

        Args:
            new_status: Target status to transition to

        Returns:
            True if transition is valid, False otherwise
        """
        transitions: dict[DebtStatus, list[DebtStatus]] = {
            DebtStatus.PENDING: [DebtStatus.CONFIRMED, DebtStatus.CANCELLED],
            DebtStatus.CONFIRMED: [DebtStatus.INVOICED, DebtStatus.CANCELLED],
            DebtStatus.INVOICED: [DebtStatus.PAID],
            DebtStatus.PAID: [],
            DebtStatus.CANCELLED: [],
        }
        return new_status in transitions.get(self, [])

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal state."""
        return self in (DebtStatus.PAID, DebtStatus.CANCELLED)

    @property
    def is_actionable(self) -> bool:
        """Check if debt can have actions performed on it."""
        return self in (DebtStatus.PENDING, DebtStatus.CONFIRMED)
