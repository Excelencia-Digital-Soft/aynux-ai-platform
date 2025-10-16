"""
PromptRenderer - Renderizador de templates de prompts con soporte para variables.
"""

import logging
import re
from string import Template
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
        """
        try:
            # Primero intentar con format para variables {variable}
            rendered = template

            # Encontrar todas las variables requeridas
            required_vars = re.findall(r"\{([^}]+)\}", template)

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
        result = {"is_valid": True, "required_variables": [], "errors": []}

        try:
            # Encontrar todas las variables
            variables = re.findall(r"\{([^}]+)\}", template)
            result["required_variables"] = list(set(variables))

            # Validar sintaxis básica
            if not template.strip():
                result["is_valid"] = False
                result["errors"].append("Template is empty")

            # Verificar balance de llaves
            if template.count("{") != template.count("}"):
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
        """
        return list(set(re.findall(r"\{([^}]+)\}", template)))
