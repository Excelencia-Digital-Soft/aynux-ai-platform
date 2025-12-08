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

# Mapeo de agentes a dominios (basado en builtin_agents.py domain_key)
# Agentes con None siempre se muestran, los demás solo si su dominio está habilitado
AGENT_DOMAIN_MAPPING: dict[str, str | None] = {
    # E-commerce domain agents (subgraph handles internal routing)
    "ecommerce_agent": "ecommerce",
    # Legacy e-commerce agents (deprecated)
    "product_agent": "ecommerce",
    "promotions_agent": "ecommerce",
    "tracking_agent": "ecommerce",
    "invoice_agent": "ecommerce",
    # Excelencia domain agents (independent agents)
    "excelencia_agent": "excelencia",
    "excelencia_invoice_agent": "excelencia",  # NEW: Client invoices
    "excelencia_promotions_agent": "excelencia",  # NEW: Software promotions
    "data_insights_agent": "excelencia",  # Moved from None to Excelencia domain
    # Credit domain
    "credit_agent": "credit",
    # Always available agents (domain_key=None)
    "greeting_agent": None,
    "support_agent": None,  # Enhanced for Excelencia software knowledge
    "fallback_agent": None,
    "farewell_agent": None,
}

# Cache para evitar cargas repetidas del YAML
_services_cache: dict | None = None


def _filter_agents_by_domain(
    enabled_agents: list[str],
    enabled_domains: list[str] | None = None,
) -> list[str]:
    """
    Filtra agentes según los dominios habilitados.

    Args:
        enabled_agents: Lista de agentes habilitados
        enabled_domains: Lista de dominios habilitados para el tenant

    Returns:
        Lista de agentes filtrados. Si enabled_domains es None o vacío,
        retorna todos los agentes. Si un agente no tiene domain_key (None),
        siempre se incluye.
    """
    if not enabled_domains:
        return enabled_agents

    return [
        agent
        for agent in enabled_agents
        if AGENT_DOMAIN_MAPPING.get(agent) is None  # Sin dominio = siempre
        or AGENT_DOMAIN_MAPPING.get(agent) in enabled_domains
    ]


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
    enabled_domains: list[str] | None = None,
) -> list[dict]:
    """
    Retorna informacion de servicios para agentes habilitados.

    Args:
        enabled_agents: Lista de nombres de agentes habilitados
        language: Codigo de idioma (es, en, pt)
        enabled_domains: Lista de dominios habilitados para el tenant.
            Si se proporciona, filtra agentes por dominio.

    Returns:
        Lista de dicts con info de servicio para cada agente habilitado
    """
    # Filtrar agentes por dominio primero
    filtered_agents = _filter_agents_by_domain(enabled_agents, enabled_domains)

    config = _load_services_config_sync()
    services_config = config.get("services", {})

    services = []
    for agent in filtered_agents:
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
    enabled_domains: list[str] | None = None,
) -> str:
    """
    Retorna lista formateada de servicios disponibles.

    Args:
        enabled_agents: Lista de agentes habilitados
        language: Codigo de idioma
        enabled_domains: Lista de dominios habilitados para el tenant

    Returns:
        String formateado con bullets para cada servicio
    """
    services = get_available_services(enabled_agents, language, enabled_domains)

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
    enabled_domains: list[str] | None = None,
) -> list[str]:
    """
    Retorna solo los nombres de servicios.

    Args:
        enabled_agents: Lista de agentes habilitados
        language: Codigo de idioma
        enabled_domains: Lista de dominios habilitados para el tenant

    Returns:
        Lista de nombres de servicios
    """
    services = get_available_services(enabled_agents, language, enabled_domains)
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
