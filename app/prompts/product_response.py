"""
Product Response Prompts

This module contains all prompt templates for AI-generated product responses.
Follows Single Responsibility Principle - separates prompt content from business logic.
Uses YAML-based prompts via PromptManager for centralized management.
"""

from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry

# Module-level PromptManager instance
_prompt_manager = PromptManager()


def _build_stock_info(
    product_count: int,
    products_with_stock: int,
    products_without_stock: int,
) -> str:
    """Build stock availability context string."""
    has_out_of_stock = products_without_stock > 0

    if has_out_of_stock:
        if products_with_stock > 0:
            return (
                f"- {products_with_stock} producto(s) con stock disponible para entrega inmediata\n"
                f"- {products_without_stock} producto(s) disponible(s) por pedido (pueden tener demoras de entrega)"
            )
        else:
            return f"Todos los {product_count} productos estan disponibles por pedido (pueden tener demoras de entrega)"
    else:
        return f"Todos los {product_count} productos tienen stock disponible"


async def build_product_response_prompt(
    user_query: str,
    intent: str,
    product_count: int,
    formatted_products: str,
    products_with_stock: int,
    products_without_stock: int,
) -> str:
    """
    Build prompt for AI response when products are found.

    Args:
        user_query: Original user query
        intent: Detected intent
        product_count: Total number of products found
        formatted_products: Pre-formatted product list
        products_with_stock: Count of products with stock > 0
        products_without_stock: Count of products with stock = 0

    Returns:
        Complete prompt string for LLM
    """
    stock_info = _build_stock_info(product_count, products_with_stock, products_without_stock)

    prompt = await _prompt_manager.get_prompt(
        PromptRegistry.ECOMMERCE_PRODUCT_RESPONSE,
        variables={
            "user_query": user_query,
            "intent": intent,
            "product_count": product_count,
            "formatted_products": formatted_products,
            "stock_info": stock_info,
        },
    )

    return prompt


async def build_no_results_prompt(user_query: str) -> str:
    """
    Build prompt for AI response when no products are found.

    Args:
        user_query: Original user query

    Returns:
        Complete prompt string for LLM
    """
    prompt = await _prompt_manager.get_prompt(
        PromptRegistry.ECOMMERCE_PRODUCT_NO_RESULTS,
        variables={"user_query": user_query},
    )

    return prompt


# Legacy sync versions for backward compatibility
def build_product_response_prompt_sync(
    user_query: str,
    intent: str,
    product_count: int,
    formatted_products: str,
    products_with_stock: int,
    products_without_stock: int,
) -> str:
    """
    Synchronous fallback for build_product_response_prompt.

    Note: This is a legacy function. Use the async version when possible.
    """
    stock_info = _build_stock_info(product_count, products_with_stock, products_without_stock)

    prompt = f"""# CONTEXTO
Eres un asistente de e-commerce ayudando a un cliente con su busqueda de productos.

# CONSULTA DEL USUARIO
"{user_query}"

# INTENCION DETECTADA
{intent}

# PRODUCTOS ENCONTRADOS ({product_count})
{formatted_products}

# INFORMACION DE DISPONIBILIDAD
{stock_info}

# INSTRUCCIONES CRITICAS - DEBES SEGUIR ESTRICTAMENTE
1. **NUNCA inventes datos**: NO inventes precios, marcas, modelos, o cantidades que NO esten
                            en los productos mostrados arriba
2. **SOLO usa datos reales**: Si un producto tiene precio $0 o "Precio no disponible",
                              NO lo menciones o di "consultar precio"
3. **Brevedad**: Responde en maximo 2-3 oraciones (1 parrafo corto)
4. **Sin listado de productos**: Los productos se mostraran automaticamente en cards visuales abajo, NO los listes
5. **Contexto util**: Da una introduccion amigable mencionando cuantos productos encontraste
6. **Disponibilidad**: Si hay productos sin stock, menciona que pueden solicitarse por pedido con posibles demoras
7. **Tono**: Amigable, profesional, servicial
8. **Emojis**: Usa 1-2 emojis apropiados
9. **Cierre**: Ofrece ayuda adicional de forma concisa

# RESPUESTA"""

    return prompt


def build_no_results_prompt_sync(user_query: str) -> str:
    """
    Synchronous fallback for build_no_results_prompt.

    Note: This is a legacy function. Use the async version when possible.
    """
    prompt = f"""# CONTEXTO
Eres un asistente de e-commerce. El cliente busco productos pero no se encontraron resultados.

# CONSULTA DEL USUARIO
"{user_query}"

# INSTRUCCIONES
1. Expresa empatia por no encontrar resultados
2. Sugiere alternativas o busquedas similares
3. Ofrece ayuda para refinar la busqueda
4. Manten un tono positivo y servicial
5. Pregunta si hay algo mas en lo que puedas ayudar

# RESPUESTA"""

    return prompt
