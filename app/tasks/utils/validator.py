"""
TaskValidator - Validador de tareas y templates.
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class TaskValidator:
    """
    Validador de tareas y templates.

    Valida:
    - Sintaxis del template
    - Campos requeridos
    - Formato de key
    - Longitud de descripcion
    """

    # Configuracion de validacion
    MAX_DESCRIPTION_LENGTH = 10000  # 10K caracteres
    MIN_DESCRIPTION_LENGTH = 10

    @classmethod
    def validate_task(cls, task_data: dict[str, Any]) -> dict[str, Any]:
        """
        Valida un task completo.

        Args:
            task_data: Diccionario con datos del task
                {
                    "key": str,
                    "name": str,
                    "description": str,
                    "metadata": dict (optional)
                }

        Returns:
            Diccionario con resultado de validacion:
            {
                "is_valid": bool,
                "errors": List[str],
                "warnings": List[str]
            }
        """
        result: dict[str, Any] = {"is_valid": True, "errors": [], "warnings": []}

        # Validar campos requeridos
        required_fields = ["key", "name", "description"]
        for field in required_fields:
            if field not in task_data or not task_data[field]:
                result["errors"].append(f"Missing required field: {field}")
                result["is_valid"] = False

        if not result["is_valid"]:
            return result

        # Validar key format
        key_validation = cls.validate_key(task_data["key"])
        if not key_validation["is_valid"]:
            result["errors"].extend(key_validation["errors"])
            result["is_valid"] = False

        # Validar description
        desc_validation = cls.validate_description(task_data["description"])
        if not desc_validation["is_valid"]:
            result["errors"].extend(desc_validation["errors"])
            result["is_valid"] = False
        else:
            result["warnings"].extend(desc_validation.get("warnings", []))

        return result

    @classmethod
    def validate_key(cls, key: str) -> dict[str, Any]:
        """
        Valida el formato de una clave de task.

        Args:
            key: Clave a validar (ej: "pharmacy.identification.request_dni")

        Returns:
            Resultado de validacion
        """
        result: dict[str, Any] = {"is_valid": True, "errors": []}

        if not key:
            result["errors"].append("Key cannot be empty")
            result["is_valid"] = False
            return result

        # Validar formato: domain.flow.action
        parts = key.split(".")
        if len(parts) < 2:
            result["errors"].append(
                "Key must have at least two parts separated by dots (e.g., domain.action)"
            )
            result["is_valid"] = False

        # Validar caracteres permitidos
        if not all(part.replace("_", "").isalnum() for part in parts):
            result["errors"].append(
                "Key parts must contain only alphanumeric characters and underscores"
            )
            result["is_valid"] = False

        return result

    @classmethod
    def validate_description(cls, description: str) -> dict[str, Any]:
        """
        Valida una descripcion de task.

        Args:
            description: Descripcion string a validar

        Returns:
            Resultado de validacion
        """
        result: dict[str, Any] = {"is_valid": True, "errors": [], "warnings": []}

        if not description:
            result["errors"].append("Description cannot be empty")
            result["is_valid"] = False
            return result

        # Validar longitud
        if len(description) < cls.MIN_DESCRIPTION_LENGTH:
            result["warnings"].append(
                f"Description is very short ({len(description)} characters)"
            )

        if len(description) > cls.MAX_DESCRIPTION_LENGTH:
            result["errors"].append(
                f"Description exceeds maximum length "
                f"({len(description)} > {cls.MAX_DESCRIPTION_LENGTH})"
            )
            result["is_valid"] = False

        # Validar balance de llaves si hay variables
        if "{" in description or "}" in description:
            if description.count("{") != description.count("}"):
                result["errors"].append("Unbalanced braces in description")
                result["is_valid"] = False

        return result

    @classmethod
    def validate_variables(
        cls, description: str, provided_variables: list[str]
    ) -> dict[str, Any]:
        """
        Valida que las variables proporcionadas coincidan con las de la descripcion.

        Args:
            description: Description string
            provided_variables: Lista de nombres de variables proporcionadas

        Returns:
            Resultado de validacion
        """
        result: dict[str, Any] = {"is_valid": True, "errors": [], "warnings": []}

        # Extraer variables de la descripcion
        desc_variables = set(re.findall(r"\{([^}]+)\}", description))
        provided_set = set(provided_variables)

        # Variables faltantes
        missing = desc_variables - provided_set
        if missing:
            result["errors"].append(f"Missing variables: {', '.join(missing)}")
            result["is_valid"] = False

        # Variables extra (no son error, solo advertencia)
        extra = provided_set - desc_variables
        if extra:
            result["warnings"].append(f"Extra variables provided: {', '.join(extra)}")

        return result
