"""
Module Manager

Handles software module catalog loading with caching and fallback.
Single responsibility: manage software modules from database.
"""

from __future__ import annotations

import logging
from typing import Any

from app.database.async_db import get_async_db_context

logger = logging.getLogger(__name__)


# Fallback modules when database is unavailable
FALLBACK_MODULES: dict[str, dict[str, Any]] = {
    "ZM-001": {
        "name": "ZisMed - Sistema Medico Integral",
        "description": "Suite medica completa que incluye Historia Clinica Electronica y Turnos Medicos",
        "features": ["Historia Clinica", "Turnos Medicos", "Registro Pacientes", "Prescripciones"],
        "target": "healthcare",
    },
    "HC-001": {
        "name": "Historia Clinica Electronica",
        "description": "Sistema de gestion de historias clinicas digitales",
        "features": ["Registro de pacientes", "Consultas medicas", "Prescripciones"],
        "target": "healthcare",
    },
    "TM-001": {
        "name": "Sistema de Turnos Medicos",
        "description": "Gestion de agendas y turnos de pacientes",
        "features": ["Agenda medica", "Turnos online", "Recordatorios"],
        "target": "healthcare",
    },
    "HO-001": {
        "name": "Gestion Hotelera",
        "description": "Software para administracion de hoteles",
        "features": ["Reservas", "Check-in/out", "Facturacion"],
        "target": "hospitality",
    },
}


class ModuleManager:
    """
    Manages software module catalog loading with caching.

    Loads modules from database on first access, caches for session.
    Falls back to FALLBACK_MODULES if database unavailable.
    """

    def __init__(self):
        """Initialize module manager with empty cache."""
        self._cache: dict[str, dict[str, Any]] | None = None
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def get_modules(self) -> dict[str, dict[str, Any]]:
        """
        Get software catalog with caching.

        Returns cached modules if available, otherwise loads from database.
        Falls back to FALLBACK_MODULES if database unavailable.

        Returns:
            Dict of module_code -> module_info
        """
        if self._cache is not None:
            return self._cache

        try:
            from app.domains.excelencia.infrastructure.repositories import SoftwareModuleRepository

            async with get_async_db_context() as db:
                repository = SoftwareModuleRepository(db)
                self._cache = await repository.get_all_as_dict(active_only=True)

                if self._cache:
                    self.logger.info(f"Loaded {len(self._cache)} software modules from database")
                    return self._cache

                # If no modules in DB, use fallback
                self.logger.warning("No modules found in database, using fallback")
                self._cache = FALLBACK_MODULES.copy()
                return self._cache

        except Exception as e:
            self.logger.warning(f"Failed to load modules from database: {e}, using fallback")
            self._cache = FALLBACK_MODULES.copy()
            return self._cache

    def clear_cache(self) -> None:
        """Clear module cache to force reload on next access."""
        self._cache = None
        self.logger.debug("Module cache cleared")
