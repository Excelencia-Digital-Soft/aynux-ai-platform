"""
Base Pharmacy Handler

Abstract base class with shared utilities for pharmacy domain handlers.
Provides LLM generation, response extraction, and state formatting.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID

import yaml

from app.domains.pharmacy.agents.utils.response_generator import (
    PharmacyResponseGenerator,
    get_response_generator,
)
from app.integrations.llm import VllmLLM

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class BasePharmacyHandler:
    """
    Base class for pharmacy domain message handlers.

    Provides shared utilities for:
    - ResponseGenerator access (lazy initialization)
    - LLM response generation with fallback
    - Response content extraction and cleaning
    - State update formatting
    - YAML template loading and rendering
    """

    # Class-level cache for YAML templates (shared across all handler instances)
    _yaml_template_cache: ClassVar[dict[str, dict[str, str]]] = {}
    _templates_dir: ClassVar[Path | None] = None

    def __init__(
        self,
        response_generator: PharmacyResponseGenerator | None = None,
    ):
        """
        Initialize base handler.

        Args:
            response_generator: PharmacyResponseGenerator instance (creates one if not provided)
        """
        self._response_generator = response_generator
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def _get_response_generator(self) -> PharmacyResponseGenerator:
        """Get or create ResponseGenerator instance (lazy init)."""
        if self._response_generator is None:
            self._response_generator = get_response_generator()
        return self._response_generator

    def _extract_response_content(self, response: Any) -> str | None:
        """
        Extract and clean content from LLM response.

        Args:
            response: LLM response object

        Returns:
            Cleaned text content or None
        """
        if not hasattr(response, "content"):
            return None

        content = response.content
        if isinstance(content, str):
            cleaned = VllmLLM.clean_reasoning_response(content)
            return cleaned.strip()
        if isinstance(content, list):
            return " ".join(str(item) for item in content).strip()
        return None

    def _format_state_update(
        self,
        message: str,
        intent_type: str,
        workflow_step: str,
        is_complete: bool = False,
        next_agent: str = "__end__",
        state: dict[str, Any] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        """
        Format standard state update dictionary.

        Args:
            message: Response message content
            intent_type: Pharmacy intent type
            workflow_step: Current workflow step
            is_complete: Whether workflow is complete
            next_agent: Next agent to route to (default: "__end__" to terminate)
            state: Current state dict (used to combine pending_greeting)
            **extra: Additional state fields

        Returns:
            Formatted state update dictionary
        """
        state = state or {}

        # Combine pending_greeting with message if present
        final_message = message
        if state.get("pending_greeting"):
            final_message = f"{state['pending_greeting']}\n\n{message}"

        result = {
            "messages": [{"role": "assistant", "content": final_message}],
            "pharmacy_intent_type": intent_type,
            "workflow_step": workflow_step,
            "is_complete": is_complete,
            "next_agent": next_agent,
            "pending_greeting": None,  # Clear after use
            # Preserve pharmacy config fields to prevent them from being lost
            "pharmacy_id": state.get("pharmacy_id"),
            "pharmacy_name": state.get("pharmacy_name"),
            "pharmacy_phone": state.get("pharmacy_phone"),
            **extra,
        }

        # Reset confirmation state when handling fallback/out-of-scope queries
        # This prevents users from getting stuck in confirmation loops
        if state.get("awaiting_confirmation"):
            # Only reset if not explicitly handling a confirmation-related flow
            if intent_type not in ("confirm", "confirmation", "debt_confirmation"):
                result["awaiting_confirmation"] = False
                result["awaiting_payment"] = False

        return result

    # =========================================================================
    # Database and Multi-Tenant Helpers
    # =========================================================================

    def _get_organization_id(self, state: dict[str, Any]) -> UUID:
        """
        Extract organization_id from state.

        Args:
            state: Current state dictionary

        Returns:
            Organization UUID

        Raises:
            ValueError: If organization_id not found in state
        """
        org_id = state.get("organization_id")
        if org_id is None:
            # Fallback to system org for backward compatibility
            return UUID("00000000-0000-0000-0000-000000000000")
        if isinstance(org_id, UUID):
            return org_id
        return UUID(str(org_id))

    async def _get_db_session(self) -> AsyncSession:
        """
        Get a database session for response generation.

        Returns:
            AsyncSession instance

        Note:
            Caller is responsible for proper session management.
            For single operations, session will auto-close after use.
        """
        from app.database.async_db import AsyncSessionLocal

        return AsyncSessionLocal()

    async def _generate_response(
        self,
        intent: str,
        state: dict[str, Any],
        user_message: str = "",
        current_task: str = "",
    ) -> str:
        """
        Generate a response using ResponseGenerator with proper db and org_id.

        This is a convenience method that handles db session and organization_id
        extraction from state automatically.

        Args:
            intent: Intent key for response generation
            state: Current state dictionary (must contain organization_id)
            user_message: User's message
            current_task: Task description for LLM

        Returns:
            Generated response content string
        """
        response_generator = self._get_response_generator()
        org_id = self._get_organization_id(state)

        async with await self._get_db_session() as db:
            result = await response_generator.generate(
                db=db,
                organization_id=org_id,
                intent=intent,
                state=state,
                user_message=user_message,
                current_task=current_task,
            )
            return result.content

    # =========================================================================
    # YAML Template Rendering (for fallback responses without LLM)
    # =========================================================================

    @classmethod
    def _get_templates_dir(cls) -> Path:
        """Get the templates directory path (lazy initialization)."""
        if cls._templates_dir is None:
            cls._templates_dir = Path(__file__).parents[5] / "prompts" / "templates"
        return cls._templates_dir

    async def _load_yaml_templates(self, yaml_file: str) -> dict[str, str]:
        """
        Load templates from a YAML file (with caching).

        Args:
            yaml_file: Relative path to YAML file (e.g., "pharmacy/data_query.yaml")

        Returns:
            Dictionary mapping short template keys to template strings
        """
        if yaml_file in self._yaml_template_cache:
            return self._yaml_template_cache[yaml_file]

        templates: dict[str, str] = {}
        path = self._get_templates_dir() / yaml_file

        try:
            content = await asyncio.to_thread(path.read_text, encoding="utf-8")
            data = yaml.safe_load(content)

            if not isinstance(data, dict):
                self.logger.warning(f"Invalid template format in {yaml_file}, expected dict")
                return templates

            for prompt in data.get("prompts", []):
                key = prompt.get("key", "")
                template = prompt.get("template", "")
                if key and template:
                    # Extract short key (e.g., "product_found" from
                    # "pharmacy.data_query.fallback.product_found")
                    short_key = key.split(".")[-1]
                    templates[short_key] = template

            self.logger.debug(f"Loaded {len(templates)} templates from {yaml_file}")
        except FileNotFoundError:
            self.logger.error(f"Template file not found: {path}")
        except Exception as e:
            self.logger.error(f"Failed to load templates from {yaml_file}: {e}")

        # Cache the templates (even if empty, to avoid repeated load attempts)
        self._yaml_template_cache[yaml_file] = templates
        return templates

    def _render_template_string(
        self,
        template: str,
        variables: dict[str, Any],
    ) -> str:
        """
        Render a template string with variables.

        Uses {variable} format. Missing variables are replaced with empty string.

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
                result = result.replace(placeholder, str(value) if value else "")

        # Clean up any remaining placeholders
        result = re.sub(r"\{[a-z_]+\}", "", result)

        return result.strip()

    async def _render_fallback_template(
        self,
        template_key: str,
        variables: dict[str, Any],
        yaml_file: str = "pharmacy/data_query.yaml",
    ) -> str:
        """
        Load and render a fallback template from YAML.

        This method is used for inline fallback responses that don't need LLM
        generation. Templates are loaded from the specified YAML file and
        rendered with the provided variables.

        Args:
            template_key: Short key for template (e.g., "product_found")
            variables: Variables to substitute in template
            yaml_file: YAML file to load from (default: pharmacy/data_query.yaml)

        Returns:
            Rendered template string

        Raises:
            ValueError: If template not found in YAML file
        """
        templates = await self._load_yaml_templates(yaml_file)

        template = templates.get(template_key)
        if not template:
            self.logger.warning(
                f"Template '{template_key}' not found in {yaml_file}"
            )
            raise ValueError(f"Template not found: {template_key}")

        return self._render_template_string(template, variables)
