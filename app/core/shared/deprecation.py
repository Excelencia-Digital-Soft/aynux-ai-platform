"""
Deprecation Utilities

Proporciona decoradores y utilidades para marcar código legacy como deprecado
de forma clara y consistente, facilitando la migración a Clean Architecture.
"""

import functools
import warnings
from typing import Any, Callable, Optional


def deprecated(
    reason: str,
    replacement: Optional[str] = None,
    removal_version: Optional[str] = None,
    category: type[Warning] = DeprecationWarning,
) -> Callable:
    """
    Decorator para marcar funciones/clases como deprecadas.

    Args:
        reason: Razón por la cual está deprecado
        replacement: Qué usar en su lugar (opcional)
        removal_version: Versión en la que será eliminado (opcional)
        category: Tipo de warning (default: DeprecationWarning)

    Example:
        @deprecated(
            reason="Legacy service no longer maintained",
            replacement="Use ProductRepository + SearchProductsUseCase",
            removal_version="2.0.0"
        )
        class ProductService:
            pass
    """

    def decorator(obj: Any) -> Any:
        # Construir mensaje de warning
        msg_parts = [f"DEPRECATED: {obj.__name__}"]

        if reason:
            msg_parts.append(f"Reason: {reason}")

        if replacement:
            msg_parts.append(f"Use instead: {replacement}")

        if removal_version:
            msg_parts.append(f"Will be removed in version: {removal_version}")

        warning_message = ". ".join(msg_parts)

        # Si es una clase
        if isinstance(obj, type):
            # Wrap __init__ para mostrar warning
            original_init = obj.__init__

            @functools.wraps(original_init)
            def new_init(self, *args, **kwargs):
                warnings.warn(warning_message, category=category, stacklevel=2)
                original_init(self, *args, **kwargs)

            obj.__init__ = new_init

            # Agregar atributo para identificar que está deprecado
            obj._is_deprecated = True
            obj._deprecation_info = {
                "reason": reason,
                "replacement": replacement,
                "removal_version": removal_version,
                "message": warning_message,
            }

            # Actualizar docstring
            if obj.__doc__:
                deprecation_notice = f"\n\n.. deprecated:: LEGACY\n   {warning_message}\n"
                obj.__doc__ = deprecation_notice + obj.__doc__
            else:
                obj.__doc__ = f"DEPRECATED: {warning_message}"

            return obj

        # Si es una función
        elif callable(obj):

            @functools.wraps(obj)
            def wrapper(*args, **kwargs):
                warnings.warn(warning_message, category=category, stacklevel=2)
                return obj(*args, **kwargs)

            # Agregar atributos usando setattr para evitar errores de tipo
            setattr(wrapper, "_is_deprecated", True)
            setattr(
                wrapper,
                "_deprecation_info",
                {
                    "reason": reason,
                    "replacement": replacement,
                    "removal_version": removal_version,
                    "message": warning_message,
                },
            )

            # Actualizar docstring
            if wrapper.__doc__:
                deprecation_notice = f"\n\n.. deprecated:: LEGACY\n   {warning_message}\n"
                wrapper.__doc__ = deprecation_notice + wrapper.__doc__
            else:
                wrapper.__doc__ = f"DEPRECATED: {warning_message}"

            return wrapper

        else:
            # Para otros tipos, solo agregar atributos
            obj._is_deprecated = True
            obj._deprecation_info = {
                "reason": reason,
                "replacement": replacement,
                "removal_version": removal_version,
                "message": warning_message,
            }
            return obj

    return decorator


def is_deprecated(obj: Any) -> bool:
    """
    Check if an object is marked as deprecated.

    Args:
        obj: Object to check

    Returns:
        True if deprecated, False otherwise
    """
    return getattr(obj, "_is_deprecated", False)


def get_deprecation_info(obj: Any) -> Optional[dict]:
    """
    Get deprecation information for an object.

    Args:
        obj: Object to check

    Returns:
        Dict with deprecation info or None if not deprecated
    """
    return getattr(obj, "_deprecation_info", None)


# Alias común
deprecated_class = deprecated
deprecated_function = deprecated
