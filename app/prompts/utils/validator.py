"""
PromptValidator - Validador de prompts y templates.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class PromptValidator:
    """
    Validador de prompts y templates.

    Valida:
    - Sintaxis del template
    - Metadata requerida
    - Longitud máxima
    - Variables requeridas
    """

    # Configuración de validación
    MAX_TEMPLATE_LENGTH = 50000  # 50K caracteres
    MIN_TEMPLATE_LENGTH = 10
    REQUIRED_METADATA_KEYS = []  # Opcional, puede estar vacío

    @classmethod
    def validate_prompt(cls, prompt_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida un prompt completo.

        Args:
            prompt_data: Diccionario con datos del prompt
                {
                    "key": str,
                    "name": str,
                    "template": str,
                    "metadata": dict
                }

        Returns:
            Diccionario con resultado de validación:
            {
                "is_valid": bool,
                "errors": List[str],
                "warnings": List[str]
            }
        """
        result: Dict[str, Any] = {"is_valid": True, "errors": [], "warnings": []}

        # Validar campos requeridos
        required_fields = ["key", "name", "template"]
        for field in required_fields:
            if field not in prompt_data or not prompt_data[field]:
                result["errors"].append(f"Missing required field: {field}")
                result["is_valid"] = False

        if not result["is_valid"]:
            return result

        # Validar key format
        key_validation = cls.validate_key(prompt_data["key"])
        if not key_validation["is_valid"]:
            result["errors"].extend(key_validation["errors"])
            result["is_valid"] = False

        # Validar template
        template_validation = cls.validate_template(prompt_data["template"])
        if not template_validation["is_valid"]:
            result["errors"].extend(template_validation["errors"])
            result["is_valid"] = False
        else:
            result["warnings"].extend(template_validation.get("warnings", []))

        # Validar metadata si existe
        if "metadata" in prompt_data and prompt_data["metadata"]:
            metadata_validation = cls.validate_metadata(prompt_data["metadata"])
            result["warnings"].extend(metadata_validation.get("warnings", []))

        return result

    @classmethod
    def validate_key(cls, key: str) -> Dict[str, Any]:
        """
        Valida el formato de una clave de prompt.

        Args:
            key: Clave a validar (ej: "product.search.intent")

        Returns:
            Resultado de validación
        """
        result: Dict[str, Any] = {"is_valid": True, "errors": []}

        if not key:
            result["errors"].append("Key cannot be empty")
            result["is_valid"] = False
            return result

        # Validar formato: domain.subdomain.action
        parts = key.split(".")
        if len(parts) < 2:
            result["errors"].append("Key must have at least two parts separated by dots (e.g., domain.action)")
            result["is_valid"] = False

        # Validar caracteres permitidos
        if not all(part.replace("_", "").isalnum() for part in parts):
            result["errors"].append("Key parts must contain only alphanumeric characters and underscores")
            result["is_valid"] = False

        return result

    @classmethod
    def validate_template(cls, template: str) -> Dict[str, Any]:
        """
        Valida un template de prompt.

        Args:
            template: Template string a validar

        Returns:
            Resultado de validación
        """
        result: Dict[str, Any] = {"is_valid": True, "errors": [], "warnings": []}

        if not template:
            result["errors"].append("Template cannot be empty")
            result["is_valid"] = False
            return result

        # Validar longitud
        if len(template) < cls.MIN_TEMPLATE_LENGTH:
            result["warnings"].append(f"Template is very short ({len(template)} characters)")

        if len(template) > cls.MAX_TEMPLATE_LENGTH:
            result["errors"].append(f"Template exceeds maximum length ({len(template)} > {cls.MAX_TEMPLATE_LENGTH})")
            result["is_valid"] = False

        # Validar balance de llaves
        if template.count("{") != template.count("}"):
            result["errors"].append("Unbalanced braces in template")
            result["is_valid"] = False

        # Advertir si no hay variables
        if "{" not in template:
            result["warnings"].append("Template has no variables")

        return result

    @classmethod
    def validate_metadata(cls, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida metadata de un prompt.

        Args:
            metadata: Diccionario de metadata

        Returns:
            Resultado de validación
        """
        result = {"is_valid": True, "warnings": []}

        # Validar campos comunes de metadata
        if "temperature" in metadata:
            temp = metadata["temperature"]
            if not isinstance(temp, (int, float)) or temp < 0 or temp > 2:
                result["warnings"].append("Temperature should be between 0 and 2")

        if "max_tokens" in metadata:
            max_tokens = metadata["max_tokens"]
            if not isinstance(max_tokens, int) or max_tokens < 1:
                result["warnings"].append("max_tokens should be a positive integer")

        if "model" in metadata:
            model = metadata["model"]
            if not isinstance(model, str) or not model.strip():
                result["warnings"].append("model should be a non-empty string")

        return result

    @classmethod
    def validate_variables(cls, template: str, provided_variables: List[str]) -> Dict[str, Any]:
        """
        Valida que las variables proporcionadas coincidan con las del template.

        Args:
            template: Template string
            provided_variables: Lista de nombres de variables proporcionadas

        Returns:
            Resultado de validación
        """
        import re

        result: Dict[str, Any] = {"is_valid": True, "errors": [], "warnings": []}

        # Extraer variables del template
        template_variables = set(re.findall(r"\{([^}]+)\}", template))
        provided_set = set(provided_variables)

        # Variables faltantes
        missing = template_variables - provided_set
        if missing:
            result["errors"].append(f"Missing variables: {', '.join(missing)}")
            result["is_valid"] = False

        # Variables extra (no son error, solo advertencia)
        extra = provided_set - template_variables
        if extra:
            result["warnings"].append(f"Extra variables provided: {', '.join(extra)}")

        return result
