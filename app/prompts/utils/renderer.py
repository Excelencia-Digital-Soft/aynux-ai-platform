"""
PromptRenderer - Renderizador de templates de prompts con soporte para variables.
"""

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PromptRenderer:
    """
    Renderizador de templates de prompts.

    Soporta:
    - Sustitución de variables usando {variable} o ${variable}
    - Variables anidadas
    - Valores por defecto
    - Validación de variables requeridas
    """

    # Placeholder for escaped braces during rendering
    _ESCAPED_OPEN = "\x00ESC_OPEN\x00"
    _ESCAPED_CLOSE = "\x00ESC_CLOSE\x00"

    @staticmethod
    def render(template: str, variables: Dict[str, Any], strict: bool = True) -> str:
        """
        Renderiza un template con las variables proporcionadas.

        Args:
            template: Template string con variables en formato {variable}
            variables: Diccionario con valores para las variables
            strict: Si True, lanza error si falta una variable requerida

        Returns:
            Template renderizado con valores sustituidos

        Raises:
            ValueError: Si strict=True y falta una variable requerida

        Note:
            Use {{ and }} to include literal braces in the template.
            Example: {{"key": "value"}} renders as {"key": "value"}
        """
        try:
            # Pre-process: Replace escaped braces {{ and }} with placeholders
            rendered = template.replace("{{", PromptRenderer._ESCAPED_OPEN)
            rendered = rendered.replace("}}", PromptRenderer._ESCAPED_CLOSE)

            # Encontrar todas las variables requeridas (now only single braces)
            required_vars = re.findall(r"\{([^}]+)\}", rendered)

            # Validar que existan todas las variables requeridas
            if strict:
                missing_vars = [var for var in required_vars if var not in variables]
                if missing_vars:
                    raise ValueError(f"Missing required variables: {', '.join(missing_vars)}")

            # Renderizar con valores disponibles
            for var in required_vars:
                if var in variables:
                    value = variables[var]
                    # Convertir a string si no lo es
                    if not isinstance(value, str):
                        value = str(value)
                    rendered = rendered.replace(f"{{{var}}}", value)
                elif not strict:
                    # Si no es strict, dejar la variable sin reemplazar
                    logger.warning(f"Variable '{var}' not found in variables dict, leaving unreplaced")

            # Post-process: Restore literal braces from placeholders
            rendered = rendered.replace(PromptRenderer._ESCAPED_OPEN, "{")
            rendered = rendered.replace(PromptRenderer._ESCAPED_CLOSE, "}")

            return rendered

        except Exception as e:
            logger.error(f"Error rendering template: {e}")
            if strict:
                raise
            return template

    @staticmethod
    def render_with_defaults(
        template: str, variables: Dict[str, Any], defaults: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Renderiza un template usando variables y valores por defecto.

        Args:
            template: Template string
            variables: Variables principales
            defaults: Valores por defecto para variables faltantes

        Returns:
            Template renderizado
        """
        merged_vars = {**(defaults or {}), **variables}
        return PromptRenderer.render(template, merged_vars, strict=False)

    @staticmethod
    def validate_template(template: str) -> Dict[str, Any]:
        """
        Valida un template y retorna información sobre las variables.

        Args:
            template: Template string a validar

        Returns:
            Diccionario con información de validación:
            {
                "is_valid": bool,
                "required_variables": list,
                "errors": list
            }
        """
        result: Dict[str, Any] = {"is_valid": True, "required_variables": [], "errors": []}

        try:
            # Pre-process: Remove escaped braces before finding variables
            processed = template.replace("{{", "").replace("}}", "")

            # Encontrar todas las variables (only single braces after pre-processing)
            variables = re.findall(r"\{([^}]+)\}", processed)
            result["required_variables"] = list(set(variables))

            # Validar sintaxis básica
            if not template.strip():
                result["is_valid"] = False
                result["errors"].append("Template is empty")

            # Verificar balance de llaves (account for escaped braces)
            single_open = template.count("{") - template.count("{{") * 2
            single_close = template.count("}") - template.count("}}") * 2
            if single_open != single_close:
                result["is_valid"] = False
                result["errors"].append("Unbalanced braces in template")

        except Exception as e:
            result["is_valid"] = False
            result["errors"].append(f"Template validation error: {str(e)}")

        return result

    @staticmethod
    def extract_variables(template: str) -> list[str]:
        """
        Extrae todas las variables de un template.

        Args:
            template: Template string

        Returns:
            Lista de nombres de variables encontradas

        Note:
            Escaped braces {{ and }} are ignored.
        """
        # Pre-process: Remove escaped braces before extracting variables
        processed = template.replace("{{", "").replace("}}", "")
        return list(set(re.findall(r"\{([^}]+)\}", processed)))
