"""
Ejemplo de uso del sistema de gestión de prompts.

Este archivo muestra cómo migrar código existente al nuevo sistema.
"""

import asyncio

from app.prompts import PromptManager, PromptRegistry


async def example_basic_usage():
    """Ejemplo básico de uso del PromptManager."""
    manager = PromptManager()

    # Obtener un prompt simple
    system_prompt = await manager.get_prompt(PromptRegistry.INTENT_ANALYZER_SYSTEM)
    print("System Prompt:", system_prompt[:100], "...")

    # Obtener un prompt con variables
    user_prompt = await manager.get_prompt(
        PromptRegistry.INTENT_ANALYZER_USER,
        variables={
            "customer_data": "Cliente VIP, historial de compras alto",
            "context_info": "Canal: WhatsApp, Idioma: Español",
            "message": "Quiero comprar una laptop",
        },
    )
    print("\nUser Prompt:", user_prompt[:200], "...")


async def example_before_after():
    """Ejemplo de código antes y después de la migración."""

    # ===== ANTES (código antiguo) =====
    print("\n=== ANTES (hardcoded prompt) ===")
    message = "busco laptop"
    user_context = "Sin contexto previo"

    old_prompt = f"""
    # ANÁLISIS DE INTENCIÓN DE PRODUCTO

    ## MENSAJE DEL USUARIO:
    "{message}"

    ## CONTEXTO DEL USUARIO:
    {user_context}

    ## INSTRUCCIONES:
    Analiza la intención del usuario...
    """
    print("Old prompt length:", len(old_prompt))

    # ===== DESPUÉS (usando PromptManager) =====
    print("\n=== DESPUÉS (usando PromptManager) ===")
    manager = PromptManager()

    new_prompt = await manager.get_prompt(
        PromptRegistry.PRODUCT_SEARCH_INTENT,
        variables={"message": message, "user_context": user_context},
    )
    print("New prompt length:", len(new_prompt))
    print("Benefits:")
    print("- ✅ Centralizado y mantenible")
    print("- ✅ Versionado automático")
    print("- ✅ Cacheable")
    print("- ✅ Editable sin redeploy")


async def example_dynamic_prompt():
    """Ejemplo de creación de prompt dinámico."""
    manager = PromptManager()

    # Crear un nuevo prompt dinámico
    new_prompt = await manager.save_dynamic_prompt(
        key="product.custom.analysis",
        name="Custom Product Analysis",
        template="""
        Analiza el siguiente producto:
        {product_name}

        Precio: {price}
        Stock: {stock}

        Genera un análisis breve de su competitividad.
        """,
        description="Análisis personalizado de productos",
        metadata={"temperature": 0.6, "max_tokens": 400},
        created_by="admin",
    )

    print("\n=== Prompt Dinámico Creado ===")
    print(f"ID: {new_prompt.id}")
    print(f"Key: {new_prompt.key}")
    print(f"Is Dynamic: {new_prompt.is_dynamic}")

    # Usar el prompt dinámico
    rendered = await manager.get_prompt(
        "product.custom.analysis", variables={"product_name": "Laptop HP", "price": "45000", "stock": "5"}
    )

    print("\nPrompt Renderizado:", rendered[:100], "...")


async def example_stats_and_cache():
    """Ejemplo de métricas y caché."""
    manager = PromptManager()

    # Hacer varias peticiones
    for _i in range(5):
        await manager.get_prompt(PromptRegistry.INTENT_ANALYZER_SYSTEM)  # Primera vez: cache miss, luego: cache hits

    # Ver estadísticas
    stats = manager.get_stats()
    print("\n=== Estadísticas ===")
    print(f"Total requests: {stats['total_requests']}")
    print(f"Cache hits: {stats['cache_hits']}")
    print(f"Cache hit rate: {stats['cache_hit_rate']}")
    print(f"Cache size: {stats['cache_size']}/{stats['max_cache_size']}")


async def example_list_prompts():
    """Ejemplo de listado de prompts."""
    manager = PromptManager()

    # Listar todos los prompts de producto
    product_prompts = await manager.list_prompts(domain="product")

    print("\n=== Prompts del dominio 'product' ===")
    for prompt in product_prompts:
        print(f"- {prompt['key']}: {prompt['name']}")


async def main():
    """Ejecuta todos los ejemplos."""
    print("=" * 60)
    print("EJEMPLOS DE USO DEL SISTEMA DE PROMPTS")
    print("=" * 60)

    await example_basic_usage()
    await example_before_after()
    await example_dynamic_prompt()
    await example_stats_and_cache()
    await example_list_prompts()

    print("\n" + "=" * 60)
    print("¡Ejemplos completados!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
