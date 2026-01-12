"""
TaskRenderer - Renderizador de templates de tareas con soporte para variables.
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class TaskRenderer:
    """
    Renderizador de templates de tareas.

    Soporta:
    - Sustitucion de variables usando {variable}
    - Valores por defecto
    - Validacion de variables requeridas
    """

    # Placeholder for escaped braces during rendering
    _ESCAPED_OPEN = "\x00ESC_OPEN\x00"
    _ESCAPED_CLOSE = "\x00ESC_CLOSE\x00"

    @staticmethod
    def render(template: str, variables: dict[str, Any], strict: bool = False) -> str:
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
        """
        try:
            # Pre-process: Replace escaped braces {{ and }} with placeholders
            rendered = template.replace("{{", TaskRenderer._ESCAPED_OPEN)
            rendered = rendered.replace("}}", TaskRenderer._ESCAPED_CLOSE)

            # Encontrar todas las variables requeridas
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
                    logger.warning(
                        f"Variable '{var}' not found in variables dict, leaving unreplaced"
                    )

            # Post-process: Restore literal braces from placeholders
            rendered = rendered.replace(TaskRenderer._ESCAPED_OPEN, "{")
            rendered = rendered.replace(TaskRenderer._ESCAPED_CLOSE, "}")

            return rendered

        except Exception as e:
            logger.error(f"Error rendering task template: {e}")
            if strict:
                raise
            return template

    @staticmethod
    def render_with_defaults(
        template: str,
        variables: dict[str, Any],
        defaults: dict[str, Any] | None = None,
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
        return TaskRenderer.render(template, merged_vars, strict=False)

    @staticmethod
    def extract_variables(template: str) -> list[str]:
        """
        Extrae todas las variables de un template.

        Args:
            template: Template string

        Returns:
            Lista de nombres de variables encontradas
        """
        # Pre-process: Remove escaped braces before extracting variables
        processed = template.replace("{{", "").replace("}}", "")
        return list(set(re.findall(r"\{([^}]+)\}", processed)))
