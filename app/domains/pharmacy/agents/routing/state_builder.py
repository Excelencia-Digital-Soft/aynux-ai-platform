"""
Routing State Builder

Builds state update dictionaries for routing decisions.
Single responsibility: state update construction.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class RoutingStateBuilder:
    """
    Builds state update dictionaries for routing decisions.

    Responsibility: Construct consistent state update dictionaries.
    """

    def build_intent_state_update(
        self,
        intent: str,
        next_node: str,
        confidence: float,
        method: str,
        entities: dict[str, Any] | None = None,
        **extra_fields: Any,
    ) -> dict[str, Any]:
        """
        Build state update for a routed intent.

        Args:
            intent: The detected intent
            next_node: The node to route to
            confidence: Intent confidence score
            method: Detection method used
            entities: Extracted entities
            **extra_fields: Additional state fields

        Returns:
            State update dictionary
        """
        updates: dict[str, Any] = {
            "pharmacy_intent_type": intent,
            "next_agent": next_node,
            "intent_confidence": confidence,
            "intent_method": method,
            "extracted_entities": entities or {},
            "routing_decision": {
                "domain": "pharmacy",
                "intent_type": intent,
                "confidence": confidence,
                "method": method,
                "routed_to": next_node,
                "timestamp": datetime.now().isoformat(),
            },
        }

        # Add confirmation flag for confirm intent
        if intent == "confirm":
            updates["confirmation_received"] = True

        # Merge extra fields
        updates.update(extra_fields)

        return updates

    def build_greeting_state_update(
        self,
        greeting_message: str,
        sent_pending: bool = False,
    ) -> dict[str, Any]:
        """
        Build state update for a greeting response.

        Args:
            greeting_message: The greeting message content
            sent_pending: Whether this was a pending greeting

        Returns:
            State update dictionary
        """
        from langchain_core.messages import AIMessage

        return {
            "just_identified": False,
            "pending_greeting": None if sent_pending else greeting_message,
            "greeting_sent": True,
            "messages": [AIMessage(content=greeting_message)],
            "pharmacy_intent_type": "greeting",
            "next_agent": "__end__",
            "is_complete": False,
        }

    def build_end_state_update(
        self,
        is_complete: bool = True,
        **extra_fields: Any,
    ) -> dict[str, Any]:
        """
        Build state update for ending the conversation flow.

        Args:
            is_complete: Whether the conversation is complete
            **extra_fields: Additional state fields

        Returns:
            State update dictionary
        """
        updates = {
            "next_agent": "__end__",
            "is_complete": is_complete,
        }
        updates.update(extra_fields)
        return updates

    def build_payment_state_update(
        self,
        payment_amount: float,
        total_debt: float,
        base_updates: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Build state update for payment-related routing.

        Args:
            payment_amount: The extracted payment amount
            total_debt: Total debt amount
            base_updates: Base updates to extend

        Returns:
            State update dictionary with payment info
        """
        updates = dict(base_updates) if base_updates else {}

        # Cap payment amount at total debt
        capped_amount = min(payment_amount, total_debt) if total_debt > 0 else payment_amount

        updates["payment_amount"] = capped_amount
        updates["is_partial_payment"] = capped_amount < total_debt if total_debt > 0 else False

        return updates

    def build_auto_debt_fetch_update(
        self,
        intent: str,
        confidence: float,
        entities: dict[str, Any] | None = None,
        **extra_fields: Any,
    ) -> dict[str, Any]:
        """
        Build state update for auto-fetching debt before invoice.

        Args:
            intent: Original intent
            confidence: Intent confidence
            entities: Extracted entities
            **extra_fields: Additional state fields

        Returns:
            State update dictionary
        """
        from app.domains.pharmacy.agents.graph import PharmacyNodeType

        updates = {
            "pharmacy_intent_type": "debt_query",
            "next_agent": PharmacyNodeType.DEBT_CHECK,
            "auto_proceed_to_invoice": True,
            "intent_confidence": confidence,
            "extracted_entities": entities or {},
        }
        updates.update(extra_fields)
        return updates

    def merge_identification_updates(
        self,
        updates: dict[str, Any],
        identification_updates: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Merge identification updates into the main updates.

        Args:
            updates: Main updates dictionary
            identification_updates: Updates from just-identified handling

        Returns:
            Merged updates dictionary
        """
        return {**updates, **identification_updates}
