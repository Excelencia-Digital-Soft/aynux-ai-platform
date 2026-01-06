"""
Test simple para verificar el greeting agent multi-dominio
"""
import asyncio
import logging
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.domains.shared.agents import GreetingAgent

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.mark.asyncio
@pytest.mark.parametrize("domain", ["ecommerce", "hospital", "credit", "excelencia"])
async def test_greeting_with_domain(domain: str, message: str = "Hola"):
    """
    Prueba el greeting agent con un dominio específico.

    Args:
        domain: Dominio de negocio (ecommerce, hospital, credit, excelencia)
        message: Mensaje de saludo del usuario
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing greeting agent with domain: {domain}")
    logger.info(f"{'='*60}\n")

    # Crear mocks
    mock_llm_provider = AsyncMock()
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value.content = "mocked response"
    mock_llm_provider.get_llm.return_value = mock_llm

    # Crear el agente con mocks
    agent = GreetingAgent(llm=mock_llm_provider)

    # Crear estado simulado con el dominio
    state_dict: Dict[str, Any] = {
        "business_domain": domain,
        "messages": [],
        "customer": {"customer_id": "test_user", "name": "Test User"},
        "conversation": {"conversation_id": "test_session", "channel": "test"},
    }

    try:
        # Mockear el prompt_manager para que no acceda al filesystem
        with patch.object(agent.prompt_manager, "get_prompt", new_callable=AsyncMock) as mock_get_prompt:
            mock_get_prompt.return_value = "Hola, bienvenido. Soy tu asistente virtual."
            # Mockear el LLM para evitar llamadas reales
            with patch.object(agent.llm, "get_llm") as mock_get_llm:
                mock_llm_instance = AsyncMock()
                mock_llm_instance.ainvoke.return_value = MagicMock(content="¡Hola! Bienvenido. ¿En qué puedo ayudarte?")
                mock_get_llm.return_value = mock_llm_instance
                # Procesar el mensaje
                result = await agent._process_internal(message, state_dict)

                # Mostrar resultados
                logger.info(f"Domain: {domain}")
                logger.info(f"Input: {message}")
                logger.info(f"\nResponse:")
                logger.info(f"{result['messages'][0]['content']}")
                logger.info(f"\nAgent: {result['current_agent']}")
                logger.info(f"Is Complete: {result['is_complete']}")
                logger.info(f"Greeting Completed: {result.get('greeting_completed', False)}")

                assert result is not None
                assert result['current_agent'] == "greeting_agent"
                assert result['is_complete'] is True

    except Exception as e:
        logger.error(f"Error testing domain {domain}: {e}")
        raise
