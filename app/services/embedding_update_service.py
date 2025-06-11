import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document
from sqlalchemy import and_, select

from app.database.async_db import get_async_db
from app.models.database import Brand, Category, Product, Promotion, Subcategory

logger = logging.getLogger(__name__)


class EmbeddingUpdateService:
    def __init__(self):
        self.embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url="http://localhost:11434")
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        self.chroma_path = "data/chroma/products"
        os.makedirs(self.chroma_path, exist_ok=True)

        self.category_collections = {}
        self._initialize_collections()

    def _initialize_collections(self):
        """Initialize ChromaDB collections for each category"""
        categories = ["laptops", "desktops", "components", "peripherals", "all_products"]

        for category in categories:
            collection_path = os.path.join(self.chroma_path, category)
            os.makedirs(collection_path, exist_ok=True)

            self.category_collections[category] = Chroma(
                collection_name=f"products_{category}",
                embedding_function=self.embeddings,
                persist_directory=collection_path,
            )

    def _create_product_document(
        self, product: Product, category: str, subcategory: Optional[str], brand: str, promotions: List[Promotion]
    ) -> Document:
        """Create a document from a product with all relevant information"""

        # Build comprehensive product description
        content_parts = [
            f"Producto: {product.name}",
            f"Modelo: {product.model}",
            f"Marca: {brand}",
            f"Categoría: {category}",
        ]

        if subcategory:
            content_parts.append(f"Subcategoría: {subcategory}")

        content_parts.extend(
            [
                f"Precio: ${product.price}",
                f"Stock: {product.stock} unidades",
                f"SKU: {product.sku}",
                "",
                "Especificaciones:",
            ]
        )

        # Add specifications
        if product.specs.is_not(None):
            content_parts.append(product.specs)

        # Add technical specs
        if product.technical_specs.is_not(None):
            content_parts.append("\nEspecificaciones técnicas:")
            for key, value in product.technical_specs.items():
                content_parts.append(f"- {key}: {value}")

        # Add features
        if product.features.is_not(None):
            content_parts.append("\nCaracterísticas:")
            for feature in product.features:
                content_parts.append(f"- {feature}")

        # Add promotions
        if promotions:
            content_parts.append("\nPromociones activas:")
            for promo in promotions:
                content_parts.append(f"- {promo.name}: {promo.discount_percentage}% de descuento")

        content = "\n".join(content_parts)

        # Create metadata
        metadata = {
            "product_id": str(product.id),  # Convert UUID to string
            "name": product.name,
            "model": product.model,
            "category": category,
            "subcategory": subcategory or "",
            "brand": brand,
            "price": float(product.price),
            "stock": product.stock,
            "sku": product.sku,
            "has_promotion": len(promotions) > 0,
            "updated_at": datetime.now().isoformat(),
        }

        return Document(page_content=content, metadata=metadata)

    async def update_product_embeddings(self, product_id: Optional[int] = None):
        """Update embeddings for products"""
        async for db in get_async_db():
            try:
                # Build query
                query = select(Product).join(Category).join(Brand).outerjoin(Subcategory)

                if product_id:
                    query = query.where(Product.id == product_id)

                result = await db.execute(query)
                products = result.scalars().all()

                logger.info(f"Updating embeddings for {len(products)} products")

                # Process each product
                for product in products:
                    # Get category and subcategory
                    category_result = await db.execute(select(Category).where(Category.id == product.category_id))
                    category = category_result.scalar_one()

                    subcategory = None
                    if product.subcategory_id is not None:
                        subcategory_result = await db.execute(
                            select(Subcategory).where(Subcategory.id == product.subcategory_id)
                        )
                        subcategory = subcategory_result.scalar_one()

                    # Get brand
                    brand_result = await db.execute(select(Brand).where(Brand.id == product.brand_id))
                    brand = brand_result.scalar_one()

                    # Get active promotions (through many-to-many relationship)
                    promotions_result = await db.execute(
                        select(Promotion)
                        .join(Product.promotions)
                        .where(
                            and_(
                                Product.id == product.id,
                                Promotion.active is True,
                                Promotion.valid_from <= datetime.now(timezone.utc),
                                Promotion.valid_until >= datetime.now(timezone.utc),
                            )
                        )
                    )
                    promotions = promotions_result.scalars().all()

                    # Create document
                    doc = self._create_product_document(
                        product=product,
                        category=category.name.lower(),
                        subcategory=subcategory.name if subcategory else None,
                        brand=brand.name,
                        promotions=promotions,
                    )

                    # Delete existing embeddings for this product
                    for collection in self.category_collections.values():
                        collection.delete(where={"product_id": str(product.id)})

                    # Add to appropriate category collection
                    category_key = category.name.lower()
                    if category_key in self.category_collections:
                        self.category_collections[category_key].add_documents([doc])

                    # Also add to all_products collection
                    self.category_collections["all_products"].add_documents([doc])

                    logger.info(f"Updated embeddings for product: {product.name}")

                logger.info("Embedding update completed successfully")

            except Exception as e:
                logger.error(f"Error updating embeddings: {str(e)}")
                raise

    async def update_all_embeddings(self):
        """Update embeddings for all products in the database"""
        await self.update_product_embeddings()

    async def search_products(self, query: str, category: Optional[str] = None, k: int = 5) -> List[Dict[str, Any]]:
        """Search products using embeddings"""
        try:
            # Determine which collection to search
            if category and category.lower() in self.category_collections:
                collection = self.category_collections[category.lower()]
            else:
                collection = self.category_collections["all_products"]

            # Perform similarity search
            results = collection.similarity_search_with_score(query, k=k)

            # Format results
            formatted_results = []
            for doc, score in results:
                formatted_results.append(
                    {
                        "product_id": doc.metadata.get("product_id"),
                        "name": doc.metadata.get("name"),
                        "model": doc.metadata.get("model"),
                        "category": doc.metadata.get("category"),
                        "subcategory": doc.metadata.get("subcategory"),
                        "brand": doc.metadata.get("brand"),
                        "price": doc.metadata.get("price"),
                        "stock": doc.metadata.get("stock"),
                        "similarity_score": score,
                        "content": doc.page_content,
                    }
                )

            return formatted_results

        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            return []

    def get_collection_stats(self) -> Dict[str, int]:
        """Get statistics about the vector collections"""
        stats = {}
        for category, collection in self.category_collections.items():
            try:
                # Get collection info
                chroma_collection = collection._collection
                count = chroma_collection.count()
                stats[category] = count
            except Exception:
                stats[category] = 0

        return stats
