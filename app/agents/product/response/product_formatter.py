"""
Product Formatter

Handles formatting of product data for user-facing display.
Single Responsibility: Product formatting only.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProductFormatter:
    """
    Formats product data for display.

    Follows Single Responsibility Principle - only handles formatting.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize product formatter.

        Args:
            config: Configuration dict with display settings
        """
        self.config = config or {}
        self.show_stock = self.config.get("show_stock", True)
        self.show_prices = self.config.get("show_prices", True)
        self.max_products_shown = self.config.get("max_products_shown", 10)

    def format_single_product(self, product: Dict[str, Any]) -> str:
        """
        Format a single product for display.

        Args:
            product: Product dictionary

        Returns:
            Formatted product string
        """
        parts = []

        # Product name
        name = product.get("name", "Producto sin nombre")
        parts.append(f"📦 *{name}*")

        # Brand
        brand = product.get("brand", {})
        if isinstance(brand, dict) and brand.get("name"):
            parts.append(f"Marca: {brand['name']}")
        elif isinstance(brand, str) and brand:
            parts.append(f"Marca: {brand}")

        # Category
        category = product.get("category", {})
        if isinstance(category, dict) and category.get("display_name"):
            parts.append(f"Categoría: {category['display_name']}")

        # Model
        model = product.get("model")
        if model:
            parts.append(f"Modelo: {model}")

        # Description (truncated)
        description = product.get("description", "")
        if description:
            # Truncate long descriptions
            if len(description) > 150:
                description = description[:147] + "..."
            parts.append(f"\n{description}")

        # Price
        if self.show_prices:
            price = product.get("price")
            if price is not None and price > 0:
                parts.append(f"\n💰 Precio: ${price:,.2f}")
            else:
                parts.append("\n💰 Precio: Consultar")

        # Stock
        if self.show_stock:
            stock = product.get("stock", 0)
            if stock > 0:
                parts.append(f"✅ Stock: {stock} unidades disponibles")
            else:
                parts.append("⏰ Disponible por pedido (puede tener demoras)")

        # Similarity score (if available)
        similarity = product.get("similarity_score")
        if similarity:
            parts.append(f"🎯 Relevancia: {similarity:.0%}")

        return "\n".join(parts)

    def format_multiple_products(self, products: List[Dict[str, Any]]) -> str:
        """
        Format multiple products for display.

        Args:
            products: List of product dictionaries

        Returns:
            Formatted products string
        """
        if not products:
            return "No se encontraron productos."

        # Limit products shown
        products_to_show = products[: self.max_products_shown]
        total_count = len(products)

        formatted_products = []

        for i, product in enumerate(products_to_show, 1):
            formatted_products.append(f"\n{i}. {self.format_single_product(product)}")

        result = "\n".join(formatted_products)

        # Add truncation message if needed
        if total_count > self.max_products_shown:
            remaining = total_count - self.max_products_shown
            result += f"\n\n_... y {remaining} productos más disponibles_"

        return result

    def format_product_summary(self, products: List[Dict[str, Any]]) -> str:
        """
        Format a brief summary of products.

        Args:
            products: List of product dictionaries

        Returns:
            Summary string
        """
        if not products:
            return "No hay productos disponibles."

        count = len(products)
        product_word = "producto" if count == 1 else "productos"

        # Calculate price range
        prices = [p.get("price", 0) for p in products if p.get("price") is not None]
        if prices:
            min_price = min(prices)
            max_price = max(prices)
            if min_price == max_price:
                price_info = f"Precio: ${min_price:,.2f}"
            else:
                price_info = f"Precios: ${min_price:,.2f} - ${max_price:,.2f}"
        else:
            price_info = "Precios no disponibles"

        # Count in-stock products
        in_stock_count = sum(1 for p in products if p.get("stock", 0) > 0)

        summary_parts = [
            f"📦 {count} {product_word} encontrados",
            f"💰 {price_info}",
            f"✅ {in_stock_count} con stock disponible",
        ]

        return "\n".join(summary_parts)

    def format_catalog_confirmation(
        self, product_count: int, intent_analysis: Dict[str, Any]
    ) -> str:
        """
        Format confirmation text for catalog response.

        Args:
            product_count: Number of products in catalog
            intent_analysis: User intent analysis

        Returns:
            Confirmation text
        """
        category = intent_analysis.get("category")
        brand = intent_analysis.get("brand")

        if category and brand:
            context = f"de *{brand}* en categoría *{category}*"
        elif category:
            context = f"en categoría *{category}*"
        elif brand:
            context = f"de marca *{brand}*"
        else:
            context = "disponibles"

        product_word = "producto" if product_count == 1 else "productos"

        text = f"📱 Te he enviado un catálogo con *{product_count} {product_word}* {context}.\n\n"
        text += "Puedes explorar los productos y ver detalles completos directamente en el catálogo. "
        text += "Si necesitas más información sobre algún producto, déjame saber. 😊"

        return text

    def format_no_results_message(self, intent_analysis: Dict[str, Any]) -> str:
        """
        Format message when no products found.

        Args:
            intent_analysis: User intent analysis

        Returns:
            No results message
        """
        search_terms = intent_analysis.get("search_terms", [])
        category = intent_analysis.get("category")
        brand = intent_analysis.get("brand")

        # Build context from intent
        context_parts = []
        if search_terms:
            context_parts.append(f"'{' '.join(search_terms)}'")
        if category:
            context_parts.append(f"categoría '{category}'")
        if brand:
            context_parts.append(f"marca '{brand}'")

        if context_parts:
            context = " en " + " y ".join(context_parts)
        else:
            context = ""

        message = f"😕 No encontré productos{context}.\n\n"
        message += "Algunas sugerencias:\n"
        message += "• Intenta con palabras clave diferentes\n"
        message += "• Verifica la ortografía\n"
        message += "• Busca por categoría o marca\n"
        message += "• Pregunta por productos similares\n\n"
        message += "¿Qué más puedo ayudarte a buscar?"

        return message

    def format_products_as_cards(
        self, products: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Format products as card-ready data structures for frontend rendering.

        Args:
            products: List of product dictionaries

        Returns:
            List of card-ready product data
        """
        if not products:
            return []

        # Limit products shown
        products_to_show = products[: self.max_products_shown]
        cards = []

        for product in products_to_show:
            # Extract product data
            name = product.get("name", "Producto sin nombre")
            brand = product.get("brand", {})
            category = product.get("category", {})
            price = product.get("price")
            stock = product.get("stock", 0)
            description = product.get("description", "")
            similarity = product.get("similarity_score")
            model = product.get("model", "")

            # Format brand
            if isinstance(brand, dict):
                brand_name = brand.get("name", "")
            elif isinstance(brand, str):
                brand_name = brand
            else:
                brand_name = ""

            # Format category
            if isinstance(category, dict):
                category_name = category.get("display_name", "")
            elif isinstance(category, str):
                category_name = category
            else:
                category_name = ""

            # Truncate description for cards
            if description and len(description) > 100:
                description = description[:97] + "..."

            # Build card data
            card = {
                "name": name,
                "brand": brand_name,
                "category": category_name,
                "model": model,
                "price": float(price) if price is not None else None,
                "stock": stock,
                "stock_available": stock > 0,
                "description": description,
                "similarity_score": float(similarity) if similarity else None,
            }

            cards.append(card)

        return cards

    def format_products_as_markdown(self, products: List[Dict[str, Any]]) -> str:
        """
        Format products as markdown text (fallback for text-only display).

        Args:
            products: List of product dictionaries

        Returns:
            Formatted markdown string
        """
        if not products:
            return "No se encontraron productos."

        # Limit products shown
        products_to_show = products[: self.max_products_shown]
        total_count = len(products)

        formatted_products = []

        for i, product in enumerate(products_to_show, 1):
            parts = []

            # Product name
            name = product.get("name", "Producto sin nombre")
            parts.append(f"**{i}. {name}**")

            # Brand and category
            brand = product.get("brand", {})
            category = product.get("category", {})

            if isinstance(brand, dict) and brand.get("name"):
                parts.append(f"🏷️ {brand['name']}")
            elif isinstance(brand, str) and brand:
                parts.append(f"🏷️ {brand}")

            if isinstance(category, dict) and category.get("display_name"):
                parts.append(f"📂 {category['display_name']}")

            # Model
            model = product.get("model")
            if model:
                parts.append(f"Modelo: {model}")

            # Price and stock
            if self.show_prices:
                price = product.get("price")
                if price is not None and price > 0:
                    parts.append(f"💰 ${price:,.2f}")
                else:
                    parts.append("💰 Precio: Consultar")

            if self.show_stock:
                stock = product.get("stock", 0)
                if stock > 0:
                    parts.append(f"✅ {stock} unidades disponibles")
                else:
                    parts.append("⏰ Disponible por pedido (puede tener demoras)")

            formatted_products.append("\n".join(parts))

        result = "\n\n".join(formatted_products)

        # Add truncation message if needed
        if total_count > self.max_products_shown:
            remaining = total_count - self.max_products_shown
            result += f"\n\n_... y {remaining} productos más disponibles_"

        return result
