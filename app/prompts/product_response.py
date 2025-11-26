"""
Product Response Prompts

This module contains all prompt templates for AI-generated product responses.
Follows Single Responsibility Principle - separates prompt content from business logic.
"""


def build_product_response_prompt(
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
    # Build stock availability context
    has_out_of_stock = products_without_stock > 0

    if has_out_of_stock:
        if products_with_stock > 0:
            stock_info = f"""

# INFORMACIÓN DE DISPONIBILIDAD
- {products_with_stock} producto(s) con stock disponible para entrega inmediata
- {products_without_stock} producto(s) disponible(s) por pedido (pueden tener demoras de entrega)"""
        else:
            stock_info = f"""

# INFORMACIÓN DE DISPONIBILIDAD
- Todos los {product_count} productos están disponibles por pedido (pueden tener demoras de entrega)"""
    else:
        stock_info = f"""

# INFORMACIÓN DE DISPONIBILIDAD
- Todos los {product_count} productos tienen stock disponible"""

    prompt = f"""# CONTEXTO
Eres un asistente de e-commerce ayudando a un cliente con su búsqueda de productos.

# CONSULTA DEL USUARIO
"{user_query}"

# INTENCIÓN DETECTADA
{intent}

# PRODUCTOS ENCONTRADOS ({product_count})
{formatted_products}{stock_info}

# INSTRUCCIONES CRÍTICAS - DEBES SEGUIR ESTRICTAMENTE
1. **NUNCA inventes datos**: NO inventes precios, marcas, modelos, o cantidades que NO estén
                            en los productos mostrados arriba
2. **SOLO usa datos reales**: Si un producto tiene precio $0 o "Precio no disponible",
                              NO lo menciones o di "consultar precio"
3. **Brevedad**: Responde en máximo 2-3 oraciones (1 párrafo corto)
4. **Sin listado de productos**: Los productos se mostrarán automáticamente en cards visuales abajo, NO los listes
5. **Contexto útil**: Da una introducción amigable mencionando cuántos productos encontraste
6. **Disponibilidad**: Si hay productos sin stock, menciona que pueden solicitarse por pedido con posibles demoras
7. **Tono**: Amigable, profesional, servicial
8. **Emojis**: Usa 1-2 emojis apropiados
9. **Cierre**: Ofrece ayuda adicional de forma concisa

# EJEMPLOS DE RESPUESTAS CORRECTAS

## Todos con stock:
"¡Hola! 😊 Encontré {product_count} productos disponibles con entrega inmediata.
Puedes ver los detalles a continuación. ¿Necesitas ayuda con algo específico?"

## Mixto (con y sin stock):
"¡Hola! 😊 Encontré {product_count} productos relacionados. Algunos tienen stock para entrega
inmediata, mientras que otros pueden solicitarse por pedido (con posibles demoras).
¿Te gustaría más información?"

## Todos sin stock:
"¡Hola! 😊 Encontré {product_count} productos que pueden solicitarse por pedido.
Ten en cuenta que pueden tener demoras de entrega. ¿Te interesa alguno en particular?"

# EJEMPLO DE RESPUESTA INCORRECTA (NO HAGAS ESTO)
"Tengo estas motos: ECHO CS-7310P a $760,500 con 10 unidades disponibles..."
❌ NUNCA inventes precios o stock

# RESPUESTA"""

    return prompt


def build_no_results_prompt(user_query: str) -> str:
    """
    Build prompt for AI response when no products are found.

    Args:
        user_query: Original user query

    Returns:
        Complete prompt string for LLM
    """
    prompt = f"""# CONTEXTO
Eres un asistente de e-commerce. El cliente buscó productos pero no se encontraron resultados.

# CONSULTA DEL USUARIO
"{user_query}"

# INSTRUCCIONES
1. Expresa empatía por no encontrar resultados
2. Sugiere alternativas o búsquedas similares
3. Ofrece ayuda para refinar la búsqueda
4. Mantén un tono positivo y servicial
5. Pregunta si hay algo más en lo que puedas ayudar

# RESPUESTA"""

    return prompt
