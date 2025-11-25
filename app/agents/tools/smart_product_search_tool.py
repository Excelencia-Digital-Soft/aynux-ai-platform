"""
Smart Product Search Tool - Herramienta inteligente para búsquedas de productos.

Esta herramienta combina:
1. Búsqueda semántica usando embeddings
2. Búsqueda estructurada basada en intenciones
3. Análisis de relaciones entre productos
4. Filtrado inteligente por contexto
"""

import json
import logging
from typing import Any, Dict, List

from sqlalchemy import func, or_, select

from app.database.async_db import get_async_db_context
from app.models.db import Brand, Category, Product

from ..integrations.ollama_integration import OllamaIntegration

logger = logging.getLogger(__name__)


class SmartProductSearchTool:
    """
    Herramienta avanzada de búsqueda de productos usando AI.

    Capacidades:
    - Búsqueda semántica con embeddings
    - Interpretación inteligente de consultas
    - Filtrado contextual dinámico
    - Ranking por relevancia
    """

    def __init__(self, ollama: OllamaIntegration, postgres=None):
        self.ollama = ollama
        self.postgres = postgres

        # Configuración de búsqueda
        self.embedding_dimensions = 768  # nomic-embed-text:v1.5 generates 768-dimensional vectors
        self.semantic_threshold = 0.6  # Optimized for product catalog with nomic-embed-text:v1.5
        self.max_semantic_results = 50

        # Mapeos para normalización
        self.category_synonyms = {
            "celulares": ["móviles", "smartphones", "teléfonos"],
            "laptops": ["notebooks", "computadoras portátiles", "ordenadores"],
            "auriculares": ["headphones", "cascos", "audífonos"],
            "zapatillas": ["zapatos deportivos", "sneakers", "tenis"],
            "camisetas": ["playeras", "remeras", "polos"],
        }

        self.brand_synonyms = {
            "apple": ["iphone", "macbook", "ipad"],
            "samsung": ["galaxy", "note"],
            "nike": ["air jordan", "air max"],
            "adidas": ["ultraboost", "nmd"],
        }

    async def semantic_search(self, query: str, intent: Dict[str, Any], limit: int = 10) -> Dict[str, Any]:
        """
        Realiza búsqueda semántica usando embeddings y AI.
        """
        try:
            # 1. Generar embedding de la consulta
            query_embedding = await self._generate_query_embedding(query, intent)

            # 2. Buscar productos similares usando embeddings
            similar_products = await self._find_similar_products(query_embedding, intent, limit * 2)

            # 3. Re-rankear resultados usando contexto adicional
            ranked_products = await self._rerank_by_context(similar_products, query, intent)

            # 4. Aplicar filtros finales
            filtered_products = await self._apply_intent_filters(ranked_products[:limit], intent)

            return {
                "success": True,
                "products": filtered_products,
                "metadata": {
                    "search_type": "semantic",
                    "total_candidates": len(similar_products),
                    "final_count": len(filtered_products),
                },
            }

        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return {"success": False, "products": [], "error": str(e)}

    async def structured_search(self, intent: Dict[str, Any], limit: int = 10) -> Dict[str, Any]:
        """
        Realiza búsqueda estructurada basada en la intención analizada.
        """
        try:
            async with get_async_db_context() as db:
                # Construir query base
                query = (
                    select(Product, Category, Brand)
                    .join(Category, Product.category_id == Category.id, isouter=True)
                    .join(Brand, Product.brand_id == Brand.id, isouter=True)
                    .where(Product.active.is_(True))
                )

                # Aplicar filtros basados en la intención
                query = await self._apply_structured_filters(query, intent)

                # Ordenamiento inteligente
                query = await self._apply_intelligent_ordering(query, intent)

                # Ejecutar consulta
                query = query.limit(limit)
                result = await db.execute(query)
                rows = result.all()

                # Formatear resultados
                products = []
                for row in rows:
                    product, category, brand = row
                    formatted_product = self._format_product(product, category, brand)
                    products.append(formatted_product)

                return {
                    "success": True,
                    "products": products,
                    "metadata": {
                        "search_type": "structured",
                        "filters_applied": self._summarize_applied_filters(intent),
                    },
                }

        except Exception as e:
            logger.error(f"Error in structured search: {e}")
            return {"success": False, "products": [], "error": str(e)}

    async def _generate_query_embedding(self, query: str, intent: Dict[str, Any]) -> List[float]:
        """
        Genera embedding de la consulta enriquecida con contexto.
        """
        # Enriquecer la consulta con información de la intención
        enriched_query = await self._enrich_query_with_intent(query, intent)

        # Generar embedding usando el modelo local
        try:
            # Usar Ollama para generar embeddings si está disponible
            embedding_prompt = f"""Genera un embedding semántico para la siguiente consulta de producto:
            
Consulta original: "{query}"
Consulta enriquecida: "{enriched_query}"

Contexto adicional:
- Categoría: {intent.get("search_params", {}).get("category", "N/A")}
- Marca: {intent.get("search_params", {}).get("brand", "N/A")}
- Características: {intent.get("filters", {}).get("characteristics", [])}"""

            print("embedding_prompt", embedding_prompt)

            # Por ahora, usar un embedding simple basado en palabras clave
            # En producción, usar un modelo de embedding real
            keywords = self._extract_keywords_for_embedding(enriched_query, intent)

            # Simular embedding (en producción usar modelo real)
            embedding = await self._create_mock_embedding(keywords)

            return embedding

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            # Fallback a embedding basado en palabras clave
            return await self._create_keyword_based_embedding(query, intent)

    async def _enrich_query_with_intent(self, query: str, intent: Dict[str, Any]) -> str:
        """
        Enriquece la consulta original con información extraída de la intención.
        """
        enriched_parts = [query]

        search_params = intent.get("search_params", {})
        filters = intent.get("filters", {})

        # Agregar información estructurada
        if search_params.get("brand"):
            enriched_parts.append(f"marca {search_params['brand']}")

        if search_params.get("category"):
            enriched_parts.append(f"categoría {search_params['category']}")

        if search_params.get("model"):
            enriched_parts.append(f"modelo {search_params['model']}")

        # Agregar características
        characteristics = filters.get("characteristics", [])
        if characteristics:
            enriched_parts.extend(characteristics)

        # Agregar contexto de precio si está disponible
        price_range = filters.get("price_range", {})
        if price_range.get("min") or price_range.get("max"):
            if price_range.get("min"):
                enriched_parts.append(f"precio mínimo {price_range['min']}")
            if price_range.get("max"):
                enriched_parts.append(f"precio máximo {price_range['max']}")

        return " ".join(enriched_parts)

    def _extract_keywords_for_embedding(self, query: str, intent: Dict[str, Any]) -> List[str]:
        """
        Extrae palabras clave relevantes para el embedding.
        """
        keywords = []

        # Palabras de la consulta
        query_words = query.lower().split()
        keywords.extend(query_words)

        # Información estructurada
        search_params = intent.get("search_params", {})
        for param_value in search_params.values():
            if param_value and isinstance(param_value, str):
                keywords.extend(param_value.lower().split())
            elif param_value and isinstance(param_value, list):
                for item in param_value:
                    if isinstance(item, str):
                        keywords.extend(item.lower().split())

        # Filtros
        filters = intent.get("filters", {})
        characteristics = filters.get("characteristics", [])
        keywords.extend([char.lower() for char in characteristics])

        # Remover duplicados y palabras vacías
        keywords = list(set([kw for kw in keywords if len(kw) > 2]))

        return keywords

    async def _create_mock_embedding(self, keywords: List[str]) -> List[float]:
        """
        Crea un embedding simulado basado en palabras clave.
        En producción, usar un modelo de embeddings real.
        """
        # Simular embedding usando hash de palabras clave
        import hashlib

        # Crear un vector base
        embedding = [0.0] * self.embedding_dimensions

        for i, keyword in enumerate(keywords[:50]):  # Limitar a 50 keywords
            # Usar hash para generar valores consistentes
            hash_value = int(hashlib.md5(keyword.encode()).hexdigest(), 16)

            # Mapear a posiciones en el embedding
            for j in range(min(10, self.embedding_dimensions)):
                pos = (hash_value + j * i) % self.embedding_dimensions
                embedding[pos] += 0.1 * (1 + j * 0.1)

        # Normalizar
        magnitude = sum(x * x for x in embedding) ** 0.5
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]

        return embedding

    async def _create_keyword_based_embedding(self, query: str, intent: Dict[str, Any]) -> List[float]:
        """
        Crea embedding simple basado en palabras clave como fallback.
        """
        keywords = self._extract_keywords_for_embedding(query, intent)
        return await self._create_mock_embedding(keywords)

    async def _find_similar_products(self, _: List[float], intent: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """
        Encuentra productos similares usando el embedding.
        En producción, usar una base de datos vectorial real.
        """
        try:
            async with get_async_db_context() as db:
                # Por ahora, usar búsqueda basada en texto como aproximación
                # En producción, usar pgvector o similar

                search_params = intent.get("search_params", {})
                keywords = search_params.get("keywords", [])

                if not keywords:
                    # Extraer keywords del intent
                    keywords = []
                    for value in search_params.values():
                        if isinstance(value, str) and value:
                            keywords.extend(value.split())
                        elif isinstance(value, list):
                            keywords.extend([str(v) for v in value if v])

                # Construir query de búsqueda textual
                query = (
                    select(Product, Category, Brand)
                    .join(Category, Product.category_id == Category.id, isouter=True)
                    .join(Brand, Product.brand_id == Brand.id, isouter=True)
                    .where(Product.active.is_(True))
                )

                # Aplicar búsqueda por keywords
                if keywords:
                    search_conditions = []
                    for keyword in keywords[:5]:  # Limitar a 5 keywords principales
                        pattern = f"%{keyword}%"
                        search_conditions.append(
                            or_(
                                Product.name.ilike(pattern),
                                Product.description.ilike(pattern),
                                Product.model.ilike(pattern),
                                Category.name.ilike(pattern),
                                Category.display_name.ilike(pattern),
                                Brand.name.ilike(pattern),
                            )
                        )

                    # Combinar condiciones con OR para mayor recall
                    if search_conditions:
                        query = query.where(or_(*search_conditions))

                query = query.limit(limit)
                result = await db.execute(query)
                rows = result.all()

                products = []
                for row in rows:
                    product, category, brand = row
                    formatted_product = self._format_product(product, category, brand)

                    # Calcular score de similitud simulado
                    similarity_score = self._calculate_similarity_score(formatted_product, keywords, intent)
                    formatted_product["similarity_score"] = similarity_score

                    products.append(formatted_product)

                # Ordenar por score de similitud
                products.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)

                return products

        except Exception as e:
            logger.error(f"Error finding similar products: {e}")
            return []

    def _calculate_similarity_score(
        self, product: Dict[str, Any], keywords: List[str], intent: Dict[str, Any]
    ) -> float:
        """
        Calcula un score de similitud simulado.
        """
        score = 0.0

        # Texto del producto para búsqueda
        product_text = " ".join(
            [
                product.get("name", "").lower(),
                product.get("description", "").lower(),
                product.get("model", "").lower(),
                product.get("category", {}).get("name", "").lower(),
                product.get("brand", {}).get("name", "").lower(),
            ]
        )

        # Puntuación basada en coincidencias de keywords
        for keyword in keywords:
            if keyword.lower() in product_text:
                score += 1.0

                # Bonus si está en el nombre
                if keyword.lower() in product.get("name", "").lower():
                    score += 0.5

        # Bonus por categoría exacta
        search_category = intent.get("search_params", {}).get("category")
        if search_category:
            product_category = product.get("category", {}).get("name", "")
            if search_category.lower() in product_category.lower():
                score += 2.0

        # Bonus por marca exacta
        search_brand = intent.get("search_params", {}).get("brand")
        if search_brand:
            product_brand = product.get("brand", {}).get("name", "")
            if search_brand.lower() in product_brand.lower():
                score += 2.0

        # Penalty por falta de stock si se requiere disponibilidad
        if intent.get("filters", {}).get("availability_required", True):
            if product.get("stock", 0) <= 0:
                score *= 0.5

        return score

    async def _rerank_by_context(
        self, products: List[Dict[str, Any]], query: str, intent: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Re-rankea productos usando contexto adicional y AI.
        """
        if len(products) <= 1:
            return products

        try:
            # Usar AI para re-rankear si hay muchos productos
            if len(products) > 10:
                rerank_prompt = f"""# RE-RANKING DE PRODUCTOS

CONSULTA ORIGINAL: "{query}"

PRODUCTOS CANDIDATOS (Top 10):
{self._format_products_for_reranking(products[:10])}

INTENCIÓN DETECTADA:
{json.dumps(intent, indent=2)}

INSTRUCCIONES:
Reordena los productos del 1 al 10 según relevancia para la consulta.
Considera:
1. Coincidencia exacta de características
2. Relevancia del precio
3. Disponibilidad en stock
4. Popularidad implícita
5. Coherencia con la intención

Responde solo con los números en orden de relevancia, separados por comas:
Ejemplo: 3,1,7,2,5,4,8,6,10,9"""

                try:
                    response = await self.ollama.generate_response(
                        system_prompt="Eres un experto en ranking de productos para e-commerce.",
                        user_prompt=rerank_prompt,
                        temperature=0.3,
                    )

                    # Parsear respuesta
                    ranking_order = self._parse_ranking_response(response)
                    if ranking_order:
                        reranked_products = []
                        for idx in ranking_order:
                            if 0 <= idx < len(products):
                                reranked_products.append(products[idx])

                        # Agregar productos restantes
                        used_indices = set(ranking_order)
                        for i, product in enumerate(products):
                            if i not in used_indices:
                                reranked_products.append(product)

                        return reranked_products

                except Exception as e:
                    logger.warning(f"AI re-ranking failed, using original order: {e}")

            # Fallback: ordenar por similarity score
            return sorted(products, key=lambda x: x.get("similarity_score", 0), reverse=True)

        except Exception as e:
            logger.error(f"Error in re-ranking: {e}")
            return products

    def _format_products_for_reranking(self, products: List[Dict[str, Any]]) -> str:
        """
        Formatea productos para el prompt de re-ranking.
        """
        formatted = []
        for i, product in enumerate(products, 1):
            line = f"{i}. {product.get('name', 'N/A')}"

            if product.get("brand", {}).get("name"):
                line += f" ({product['brand']['name']})"

            line += f" - ${product.get('price', 0):,.2f}"

            stock = product.get("stock", 0)
            if stock > 0:
                line += f" ✅ Stock: {stock}"
            else:
                line += " ❌ Sin stock"

            if product.get("category", {}).get("display_name"):
                line += f" | {product['category']['display_name']}"

            formatted.append(line)

        return "\n".join(formatted)

    def _parse_ranking_response(self, response: str) -> List[int]:
        """
        Parsea la respuesta de ranking de AI.
        """
        try:
            # Extraer números de la respuesta
            import re

            numbers = re.findall(r"\d+", response.replace(" ", ""))

            # Convertir a índices (restando 1)
            indices = [int(num) - 1 for num in numbers if num.isdigit()]

            # Validar que son índices válidos
            valid_indices = [idx for idx in indices if 0 <= idx <= 9]

            return valid_indices[:10]  # Máximo 10

        except Exception as e:
            logger.error(f"Error parsing ranking response: {e}")
            return []

    async def _apply_intent_filters(
        self, products: List[Dict[str, Any]], intent: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Aplica filtros finales basados en la intención.
        """
        filtered_products = []

        filters = intent.get("filters", {})

        for product in products:
            # Filtro de precio
            price_range = filters.get("price_range", {})
            product_price = product.get("price", 0)

            if price_range.get("min") and product_price < price_range["min"]:
                continue
            if price_range.get("max") and product_price > price_range["max"]:
                continue

            # Filtro de disponibilidad
            if filters.get("availability_required", True):
                if product.get("stock", 0) <= 0:
                    continue

            # Filtro de características (implementación básica)
            characteristics = filters.get("characteristics", [])
            if characteristics:
                product_text = " ".join(
                    [
                        product.get("name", "").lower(),
                        product.get("description", "").lower(),
                    ]
                )

                # Verificar que al menos una característica esté presente
                has_characteristic = any(char.lower() in product_text for char in characteristics)

                if not has_characteristic:
                    continue

            filtered_products.append(product)

        return filtered_products

    async def _apply_structured_filters(self, query, intent: Dict[str, Any]):
        """
        Aplica filtros estructurados a la query SQL.
        """
        search_params = intent.get("search_params", {})
        filters = intent.get("filters", {})

        # Filtro por palabras clave
        keywords = search_params.get("keywords", [])
        if keywords:
            search_conditions = []
            for keyword in keywords[:3]:  # Limitar a 3 keywords principales
                pattern = f"%{keyword}%"
                search_conditions.append(
                    or_(Product.name.ilike(pattern), Product.description.ilike(pattern), Product.model.ilike(pattern))
                )

            if search_conditions:
                query = query.where(or_(*search_conditions))

        # Filtro por categoría
        category = search_params.get("category")
        if category:
            query = query.where(
                or_(
                    func.lower(Category.name).like(f"%{category.lower()}%"),
                    func.lower(Category.display_name).like(f"%{category.lower()}%"),
                )
            )

        # Filtro por marca
        brand = search_params.get("brand")
        if brand:
            query = query.where(func.lower(Brand.name).like(f"%{brand.lower()}%"))

        # Filtro por rango de precio
        price_range = filters.get("price_range", {})
        if price_range.get("min"):
            query = query.where(Product.price >= price_range["min"])
        if price_range.get("max"):
            query = query.where(Product.price <= price_range["max"])

        # Filtro por disponibilidad
        if filters.get("availability_required", True):
            query = query.where(Product.stock > 0)

        return query

    async def _apply_intelligent_ordering(self, query, intent: Dict[str, Any]):
        """
        Aplica ordenamiento inteligente basado en la intención.
        """
        intent_type = intent.get("intent_type", "search_general")
        user_emotion = intent.get("user_emotion", "neutral")

        # Ordenamiento por tipo de intención
        if intent_type == "price_inquiry" or "barato" in str(intent).lower():
            # Ordenar por precio ascendente
            query = query.order_by(Product.price.asc())
        elif "premium" in str(intent).lower() or "mejor" in str(intent).lower():
            # Ordenar por precio descendente (asumir que más caro = mejor)
            query = query.order_by(Product.price.desc())
        elif user_emotion == "urgent":
            # Priorizar productos con más stock
            query = query.order_by(Product.stock.desc())
        else:
            # Ordenamiento por defecto: fecha de creación (más nuevos primero)
            query = query.order_by(Product.created_at.desc())

        return query

    def _summarize_applied_filters(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resumne los filtros aplicados para metadata.
        """
        summary = {}

        search_params = intent.get("search_params", {})
        filters = intent.get("filters", {})

        if search_params.get("keywords"):
            summary["keywords"] = len(search_params["keywords"])

        if search_params.get("category"):
            summary["category_filter"] = True

        if search_params.get("brand"):
            summary["brand_filter"] = True

        if filters.get("price_range", {}).get("min") or filters.get("price_range", {}).get("max"):
            summary["price_filter"] = True

        if filters.get("availability_required"):
            summary["stock_filter"] = True

        return summary

    def _format_product(self, product, category, brand) -> Dict[str, Any]:
        """
        Formatea un producto en el formato estándar.
        """
        return {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "price": float(product.price) if product.price else 0.0,
            "stock": product.stock,
            "model": product.model,
            "active": product.active,
            "category": (
                {
                    "id": category.id if category else None,
                    "name": category.name if category else None,
                    "display_name": category.display_name if category else None,
                }
                if category
                else None
            ),
            "brand": (
                {
                    "id": brand.id if brand else None,
                    "name": brand.name if brand else None,
                }
                if brand
                else None
            ),
            "created_at": product.created_at.isoformat() if product.created_at else None,
            "updated_at": product.updated_at.isoformat() if product.updated_at else None,
        }
