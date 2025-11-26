"""
Test simple para verificar el greeting agent multi-dominio
"""
import asyncio
import logging
from typing import Dict, Any

from app.domains.shared.agents import GreetingAgent

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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

    # Crear el agente
    agent = GreetingAgent()

    # Crear estado simulado con el dominio
    state_dict: Dict[str, Any] = {
        "business_domain": domain,
        "messages": [],
        "customer": {"customer_id": "test_user", "name": "Test User"},
        "conversation": {"conversation_id": "test_session", "channel": "test"},
    }

    try:
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

        return result

    except Exception as e:
        logger.error(f"Error testing domain {domain}: {e}")
        raise


async def main():
    """Ejecuta pruebas para todos los dominios"""
    domains = ["ecommerce", "hospital", "credit", "excelencia"]
    messages = [
        "Hola",
        "Hello",
        "Olá",
    ]

    logger.info("\n" + "="*60)
    logger.info("MULTI-DOMAIN GREETING AGENT TEST")
    logger.info("="*60 + "\n")

    for domain in domains:
        for message in messages:
            try:
                await test_greeting_with_domain(domain, message)
                await asyncio.sleep(1)  # Pequeña pausa entre tests
            except Exception as e:
                logger.error(f"Failed to test {domain} with message '{message}': {e}")
                continue

    logger.info("\n" + "="*60)
    logger.info("ALL TESTS COMPLETED")
    logger.info("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
