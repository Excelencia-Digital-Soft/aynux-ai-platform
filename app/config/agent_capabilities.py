"""
Agent Capabilities Configuration

Carga la configuracion de servicios de agentes desde YAML usando el sistema de prompts.
Proporciona funciones para obtener servicios dinamicos basados en agentes habilitados.

Este modulo reemplaza el mapeo hardcodeado anterior con carga dinamica desde
app/prompts/templates/agents/services.yaml usando PromptLoader.
"""

import asyncio
import logging
from typing import Literal

import yaml

from app.prompts.loader import PromptLoader
from app.prompts.registry import PromptRegistry

logger = logging.getLogger(__name__)

SupportedLanguage = Literal["es", "en", "pt"]

# Cache para evitar cargas repetidas del YAML
_services_cache: dict | None = None


def _load_services_config_sync() -> dict:
    """
    Carga la configuracion de servicios desde YAML de forma sincrona.

    Returns:
        Dict con configuracion de servicios por agente
    """
    global _services_cache

    if _services_cache is not None:
        return _services_cache

    try:
        loader = PromptLoader()

        async def _load():
            return await loader.load(PromptRegistry.AGENTS_SERVICES_CONFIG, prefer_db=False)

        # Ejecutar async en contexto sync
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            # Si hay un loop corriendo, usar thread pool
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _load())
                template = future.result(timeout=5)
        else:
            template = asyncio.run(_load())

        if template and template.template:
            parsed = yaml.safe_load(template.template)
            if isinstance(parsed, dict):
                _services_cache = parsed
                logger.info("Agent services config loaded from YAML")
                return _services_cache

    except Exception as e:
        logger.warning(f"Failed to load services from YAML: {e}, using fallback")

    # Fallback minimo si YAML falla
    _services_cache = {
        "services": {},
        "fallback": {
            "emoji": "💬",
            "i18n": {
                "es": {"description": "Estamos aqui para ayudarte"},
                "en": {"description": "We're here to help you"},
                "pt": {"description": "Estamos aqui para ajuda-lo"},
            },
        },
    }
    return _services_cache


def get_available_services(
    enabled_agents: list[str],
    language: SupportedLanguage = "es",
) -> list[dict]:
    """
    Retorna informacion de servicios para agentes habilitados.

    Args:
        enabled_agents: Lista de nombres de agentes habilitados
        language: Codigo de idioma (es, en, pt)

    Returns:
        Lista de dicts con info de servicio para cada agente habilitado
    """
    config = _load_services_config_sync()
    services_config = config.get("services", {})

    services = []
    for agent in enabled_agents:
        if agent in services_config:
            agent_config = services_config[agent]
            i18n_data = agent_config.get("i18n", {})
            lang_data = i18n_data.get(language) or i18n_data.get("es", {})

            services.append({
                "agent": agent,
                "emoji": agent_config.get("emoji", "📌"),
                "service_name": lang_data.get("service_name", agent),
                "description": lang_data.get("description", ""),
                "keywords": agent_config.get("keywords", []),
            })

    return services


def format_service_list(
    enabled_agents: list[str],
    language: SupportedLanguage = "es",
) -> str:
    """
    Retorna lista formateada de servicios disponibles.

    Args:
        enabled_agents: Lista de agentes habilitados
        language: Codigo de idioma

    Returns:
        String formateado con bullets para cada servicio
    """
    services = get_available_services(enabled_agents, language)

    if not services:
        config = _load_services_config_sync()
        fallback = config.get("fallback", {})
        emoji = fallback.get("emoji", "💬")
        i18n = fallback.get("i18n", {})
        desc = i18n.get(language, {}).get("description") or i18n.get("es", {}).get(
            "description", "Estamos aqui para ayudarte"
        )
        return f"• {emoji} {desc}"

    return "\n".join([f"• {s['emoji']} {s['description']}" for s in services])


def get_service_names(
    enabled_agents: list[str],
    language: SupportedLanguage = "es",
) -> list[str]:
    """
    Retorna solo los nombres de servicios.

    Args:
        enabled_agents: Lista de agentes habilitados
        language: Codigo de idioma

    Returns:
        Lista de nombres de servicios
    """
    services = get_available_services(enabled_agents, language)
    return [s["service_name"] for s in services]


def get_agent_by_keyword(
    keyword: str,
    enabled_agents: list[str],
) -> str | None:
    """
    Encuentra un agente habilitado por palabra clave.

    Args:
        keyword: Palabra clave (case-insensitive)
        enabled_agents: Lista de agentes habilitados

    Returns:
        Nombre del agente si se encuentra, None si no
    """
    config = _load_services_config_sync()
    services_config = config.get("services", {})
    keyword_lower = keyword.lower()

    for agent in enabled_agents:
        if agent in services_config:
            keywords = services_config[agent].get("keywords", [])
            if keyword_lower in [k.lower() for k in keywords]:
                return agent
    return None


def clear_cache() -> None:
    """
    Limpia el cache de configuracion.

    Util para testing o hot-reload de configuracion.
    """
    global _services_cache
    _services_cache = None
    logger.debug("Agent services cache cleared")
