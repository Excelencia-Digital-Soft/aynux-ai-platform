# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Template renderer for pharmacy domain responses.
#              Handles variable substitution and content extraction.
# Tenant-Aware: Yes - state contains organization-specific data.
# ============================================================================
"""
Pharmacy Template Renderer - Variable substitution and content extraction.

Responsibilities:
- Build variables dictionary from state and intent
- Render templates with variable substitution
- Format monetary amounts
- Extract content from LLM responses
"""

from __future__ import annotations

import re
from typing import Any


class PharmacyTemplateRenderer:
    """
    Renders templates with variable substitution for pharmacy domain.

    Single Responsibility: Template rendering and variable management.
    """

    def render(self, template: str, variables: dict[str, Any]) -> str:
        """
        Render template with variables.

        Uses {variable} format. Missing variables are cleaned up.

        Args:
            template: Template string with {placeholders}
            variables: Dictionary of variable values

        Returns:
            Rendered template string
        """
        if not template:
            return ""

        result = template

        for key, value in variables.items():
            placeholder = "{" + key + "}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))

        # Clean up remaining placeholders
        result = re.sub(r"\{[a-z_]+\}", "", result)

        return result.strip()

    def build_variables(
        self,
        intent: str,
        state: dict[str, Any],
        current_task: str,
    ) -> dict[str, Any]:
        """
        Build variables dictionary for template rendering.

        Args:
            intent: Current intent key
            state: Conversation state dictionary
            current_task: Description of current task

        Returns:
            Variables dictionary with all substitution values
        """
        variables = {
            # Required pharmacy context
            "pharmacy_name": state.get("pharmacy_name", "la farmacia"),
            "pharmacy_phone": state.get("pharmacy_phone", "la farmacia"),
            # Customer info
            "customer_name": state.get("customer_name", "No identificado"),
            "total_debt": self.format_amount(state.get("total_debt")),
            # Flow state
            "workflow_step": state.get("workflow_step", "inicio"),
            "is_first_interaction": str(not state.get("greeted", False)),
            "detected_intent": intent,
            # Person validation
            "registered_persons_count": str(len(state.get("registered_persons") or [])),
            "pending_dni": state.get("pending_dni", "No ingresado"),
            "expected_name": state.get("expected_name", "No disponible"),
            # Task
            "current_task": current_task,
        }

        # Add additional state values not already in variables
        for key, value in state.items():
            if key not in variables:
                variables[key] = str(value) if value is not None else ""

        return variables

    def format_amount(self, amount: Any) -> str:
        """
        Format amount as currency string.

        Args:
            amount: Amount value (can be None, str, int, float)

        Returns:
            Formatted currency string or placeholder
        """
        if amount is None:
            return "No consultada"
        try:
            value = float(amount)
            return f"${value:,.2f}"
        except (TypeError, ValueError):
            return str(amount) if amount else "No consultada"

    def extract_content(self, response: Any) -> str:
        """
        Extract content string from LLM response.

        Handles different response formats from LangChain.

        Args:
            response: LLM response object

        Returns:
            Extracted content string
        """
        if hasattr(response, "content"):
            content = response.content
        else:
            content = str(response)

        if isinstance(content, list):
            content = " ".join(str(item) for item in content)

        return str(content).strip()


__all__ = ["PharmacyTemplateRenderer"]
