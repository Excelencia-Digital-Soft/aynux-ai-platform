"""
Prompt template renderer using Jinja2.

This module provides rendering capabilities for prompt templates
with variable substitution and validation.
"""

import logging
from typing import Any, Dict, Optional

from jinja2 import Environment, StrictUndefined, Template, TemplateSyntaxError, UndefinedError

from .models import PromptRenderContext, PromptTemplate

logger = logging.getLogger(__name__)


class PromptRenderError(Exception):
    """Raised when a prompt cannot be rendered."""

    pass


class PromptRenderer:
    """
    Renders prompt templates with variable substitution.

    Uses Jinja2 for template rendering with strict undefined checking.
    Follows SRP: Only responsible for rendering templates.
    """

    def __init__(self, strict: bool = True):
        """
        Initialize the renderer.

        Args:
            strict: If True, raise error on missing variables. If False, use empty string.
        """
        self.strict = strict
        self._env = Environment(
            autoescape=False,  # Don't escape for prompt templates
            undefined=StrictUndefined if strict else None,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

    def render(
        self,
        template: PromptTemplate,
        context: Optional[PromptRenderContext] = None,
        **kwargs: Any,
    ) -> str:
        """
        Render a prompt template with variables.

        Args:
            template: The PromptTemplate to render
            context: Optional PromptRenderContext with variables
            **kwargs: Additional variables to merge with context

        Returns:
            Rendered prompt string

        Raises:
            PromptRenderError: If rendering fails or required variables missing
        """
        # Merge variables from context and kwargs
        variables = {}
        if context:
            variables.update(context.variables)
        variables.update(kwargs)

        # Validate required variables
        if self.strict or (context and context.strict):
            missing = set(template.get_required_variables()) - set(variables.keys())
            if missing:
                raise PromptRenderError(
                    f"Missing required variables for prompt '{template.key}': {missing}"
                )

        # Apply defaults for missing optional variables
        for var in template.variables:
            if not var.required and var.name not in variables and var.default is not None:
                variables[var.name] = var.default

        try:
            # Create Jinja2 template and render
            jinja_template = self._env.from_string(template.template)
            rendered = jinja_template.render(**variables)

            logger.debug(f"Successfully rendered prompt: {template.key}")
            return rendered.strip()

        except UndefinedError as e:
            raise PromptRenderError(f"Missing variable in prompt '{template.key}': {e}")
        except TemplateSyntaxError as e:
            raise PromptRenderError(f"Invalid template syntax in prompt '{template.key}': {e}")
        except Exception as e:
            raise PromptRenderError(f"Error rendering prompt '{template.key}': {e}")

    def render_string(self, template_str: str, **kwargs: Any) -> str:
        """
        Render a template string directly (without PromptTemplate).

        Args:
            template_str: Template string with {variables}
            **kwargs: Variables to substitute

        Returns:
            Rendered string

        Raises:
            PromptRenderError: If rendering fails
        """
        try:
            jinja_template = self._env.from_string(template_str)
            rendered = jinja_template.render(**kwargs)
            return rendered.strip()

        except UndefinedError as e:
            raise PromptRenderError(f"Missing variable: {e}")
        except TemplateSyntaxError as e:
            raise PromptRenderError(f"Invalid template syntax: {e}")
        except Exception as e:
            raise PromptRenderError(f"Error rendering template: {e}")

    def validate_template(self, template: PromptTemplate) -> Dict[str, Any]:
        """
        Validate that a template can be compiled.

        Args:
            template: The PromptTemplate to validate

        Returns:
            Dict with validation results:
                - valid: bool
                - errors: List of error messages
        """
        errors = []

        try:
            # Try to compile the template
            self._env.from_string(template.template)
        except TemplateSyntaxError as e:
            errors.append(f"Template syntax error: {e}")
        except Exception as e:
            errors.append(f"Template validation error: {e}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    def preview_render(
        self,
        template: PromptTemplate,
        context: Optional[PromptRenderContext] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Preview rendering with detailed information.

        Args:
            template: The PromptTemplate to preview
            context: Optional PromptRenderContext
            **kwargs: Additional variables

        Returns:
            Dict with preview information:
                - success: bool
                - rendered: str (if successful)
                - error: str (if failed)
                - missing_required: List of missing required variables
                - used_defaults: List of variables using defaults
        """
        # Merge variables
        variables = {}
        if context:
            variables.update(context.variables)
        variables.update(kwargs)

        # Check required variables
        required_vars = set(template.get_required_variables())
        provided_vars = set(variables.keys())
        missing_required = list(required_vars - provided_vars)

        # Check defaults used
        used_defaults = []
        for var in template.variables:
            if not var.required and var.name not in variables and var.default is not None:
                used_defaults.append(var.name)
                variables[var.name] = var.default

        # Try to render
        try:
            rendered = self.render(template, context, **kwargs)
            return {
                "success": True,
                "rendered": rendered,
                "missing_required": missing_required,
                "used_defaults": used_defaults,
            }
        except PromptRenderError as e:
            return {
                "success": False,
                "error": str(e),
                "missing_required": missing_required,
                "used_defaults": used_defaults,
            }
