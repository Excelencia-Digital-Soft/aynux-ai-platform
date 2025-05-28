import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import joinedload

from app.config.settings import get_settings
from app.database import get_db_context
from app.models.database import (
    Brand,
    Category,
    Customer,
    PriceHistory,
    Product,
    ProductInquiry,
    Promotion,
    StockMovement,
    Subcategory,
)

logger = logging.getLogger(__name__)


class ProductService:
    """Servicio para gestionar productos desde PostgreSQL"""

    def __init__(self):
        self.settings = get_settings()

    async def get_products_by_category(
        self, category_name: str, subcategory_name: Optional[str] = None, active_only: bool = True, limit: int = 50
    ) -> List[Product]:
        """Obtiene productos por categoría y subcategoría"""
        try:
            with get_db_context() as db:
                query = (
                    db.query(Product)
                    .join(Category)
                    .options(joinedload(Product.category), joinedload(Product.subcategory), joinedload(Product.brand))
                )

                # Filtro por categoría
                query = query.filter(Category.name == category_name.lower())

                # Filtro por subcategoría si se especifica
                if subcategory_name:
                    query = query.join(Subcategory).filter(Subcategory.name == subcategory_name.lower())

                # Solo productos activos si se especifica
                if active_only:
                    query = query.filter(Product.active)

                # Ordenar por featured primero, luego por nombre
                query = query.order_by(desc(Product.featured), Product.name)

                return query.limit(limit).all()

        except Exception as e:
            logger.error(f"Error getting products by category: {e}")
            return []

    async def get_products_by_price_range(
        self, min_price: float, max_price: float, category_name: Optional[str] = None, limit: int = 50
    ) -> List[Product]:
        """Obtiene productos por rango de precio"""
        try:
            with get_db_context() as db:
                query = (
                    db.query(Product)
                    .options(joinedload(Product.category), joinedload(Product.subcategory), joinedload(Product.brand))
                    .filter(and_(Product.price >= min_price, Product.price <= max_price, Product.active))
                )

                # Filtro adicional por categoría si se especifica
                if category_name:
                    query = query.join(Category).filter(Category.name == category_name.lower())

                # Ordenar por precio
                query = query.order_by(Product.price)

                return query.limit(limit).all()

        except Exception as e:
            logger.error(f"Error getting products by price range: {e}")
            return []

    async def search_products(
        self,
        search_term: str,
        category_filter: Optional[str] = None,
        brand_filter: Optional[str] = None,
        limit: int = 20,
    ) -> List[Product]:
        """Búsqueda de productos por texto"""
        try:
            with get_db_context() as db:
                query = db.query(Product).options(
                    joinedload(Product.category), joinedload(Product.subcategory), joinedload(Product.brand)
                )

                # Búsqueda en nombre, specs y descripción
                search_filter = or_(
                    Product.name.ilike(f"%{search_term}%"),
                    Product.specs.ilike(f"%{search_term}%"),
                    Product.description.ilike(f"%{search_term}%"),
                )
                query = query.filter(search_filter)

                # Filtros adicionales
                if category_filter:
                    query = query.join(Category).filter(Category.name == category_filter.lower())

                if brand_filter:
                    query = query.join(Brand).filter(Brand.name.ilike(f"%{brand_filter}%"))

                # Solo productos activos
                query = query.filter(Product.active)

                # Ordenar por relevancia (featured primero)
                query = query.order_by(desc(Product.featured), Product.name)

                return query.limit(limit).all()

        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return []

    async def get_featured_products(self, limit: int = 10) -> List[Product]:
        """Obtiene productos destacados"""
        try:
            with get_db_context() as db:
                return (
                    db.query(Product)
                    .options(joinedload(Product.category), joinedload(Product.subcategory), joinedload(Product.brand))
                    .filter(and_(Product.featured, Product.active))
                    .order_by(Product.name)
                    .limit(limit)
                    .all()
                )

        except Exception as e:
            logger.error(f"Error getting featured products: {e}")
            return []

    async def get_products_on_sale(self, limit: int = 20) -> List[Product]:
        """Obtiene productos en oferta"""
        try:
            with get_db_context() as db:
                return (
                    db.query(Product)
                    .options(joinedload(Product.category), joinedload(Product.subcategory), joinedload(Product.brand))
                    .filter(and_(Product.on_sale, Product.active))
                    .order_by(desc(Product.featured), Product.price)
                    .limit(limit)
                    .all()
                )

        except Exception as e:
            logger.error(f"Error getting products on sale: {e}")
            return []

    async def get_low_stock_products(self, threshold: Optional[int] = None) -> List[Product]:
        """Obtiene productos con stock bajo"""
        try:
            if threshold is None:
                threshold = 1  # TODO: por base de datos o api.

            with get_db_context() as db:
                return (
                    db.query(Product)
                    .options(joinedload(Product.category), joinedload(Product.brand))
                    .filter(and_(Product.stock <= threshold, Product.stock > 0, Product.active))
                    .order_by(Product.stock)
                    .all()
                )

        except Exception as e:
            logger.error(f"Error getting low stock products: {e}")
            return []

    async def get_active_promotions(self) -> List[Promotion]:
        """Obtiene promociones vigentes"""
        try:
            with get_db_context() as db:
                now = datetime.now(timezone.utc)
                return (
                    db.query(Promotion)
                    .options(joinedload(Promotion.products))
                    .filter(and_(Promotion.active, Promotion.valid_from <= now, Promotion.valid_until >= now))
                    .order_by(desc(Promotion.discount_percentage))
                    .all()
                )

        except Exception as e:
            logger.error(f"Error getting active promotions: {e}")
            return []

    async def get_brands(self, active_only: bool = True) -> List[Brand]:
        """Obtiene todas las marcas"""
        try:
            with get_db_context() as db:
                query = db.query(Brand)

                if active_only:
                    query = query.filter(Brand.active)

                return query.order_by(Brand.name).all()

        except Exception as e:
            logger.error(f"Error getting brands: {e}")
            return []

    async def get_categories_with_counts(self) -> List[Dict[str, Any]]:
        """Obtiene categorías con conteo de productos"""
        try:
            with get_db_context() as db:
                result = (
                    db.query(
                        Category.name,
                        Category.display_name,
                        func.count(Product.id).label("product_count"),
                        func.avg(Product.price).label("avg_price"),
                        func.min(Product.price).label("min_price"),
                        func.max(Product.price).label("max_price"),
                    )
                    .join(Product)
                    .filter(and_(Category.active, Product.active))
                    .group_by(Category.id)
                    .all()
                )

                return [
                    {
                        "name": row.name,
                        "display_name": row.display_name,
                        "product_count": row.product_count,
                        "avg_price": float(row.avg_price) if row.avg_price else 0,
                        "min_price": float(row.min_price) if row.min_price else 0,
                        "max_price": float(row.max_price) if row.max_price else 0,
                    }
                    for row in result
                ]

        except Exception as e:
            logger.error(f"Error getting categories with counts: {e}")
            return []

    async def get_product_recommendations(
        self, customer_interests: List[str], budget: float, limit: int = 5
    ) -> List[Product]:
        """Genera recomendaciones basadas en intereses y presupuesto"""
        try:
            with get_db_context() as db:
                query = (
                    db.query(Product)
                    .options(joinedload(Product.category), joinedload(Product.subcategory), joinedload(Product.brand))
                    .join(Category)
                    .filter(and_(Product.price <= budget, Product.active, Product.stock > 0))
                )

                # Filtrar por intereses (categorías)
                if customer_interests:
                    category_filters = [Category.name.ilike(f"%{interest}%") for interest in customer_interests]
                    query = query.filter(or_(*category_filters))

                # Priorizar productos destacados y en stock
                query = query.order_by(desc(Product.featured), desc(Product.stock), Product.price)

                return query.limit(limit).all()

        except Exception as e:
            logger.error(f"Error getting product recommendations: {e}")
            return []

    async def update_stock(
        self,
        product_id: str,
        new_stock: int,
        movement_type: str = "adjustment",
        reason: str = "manual_update",
        notes: Optional[str] = None,
    ) -> bool:
        """Actualiza el stock de un producto"""
        try:
            with get_db_context() as db:
                product = db.query(Product).filter(Product.id == product_id).first()

                if not product:
                    logger.error(f"Product not found: {product_id}")
                    return False

                previous_stock = product.stock
                # Use setattr for SQLAlchemy models
                product["stock"] = new_stock
                product["updated_at"] = datetime.now(timezone.utc)

                # Registrar movimiento de stock
                movement = StockMovement(
                    product_id=product_id,
                    movement_type=movement_type,
                    quantity=new_stock - previous_stock,
                    previous_stock=previous_stock,
                    new_stock=new_stock,
                    reason=reason,
                    notes=notes,
                )
                db.add(movement)

                db.commit()
                logger.info(f"Stock updated for product {product.name}: {previous_stock} -> {new_stock}")
                return True

        except Exception as e:
            logger.error(f"Error updating stock: {e}")
            return False

    async def update_price(
        self, product_id: str, new_price: float, reason: str = "manual_update", notes: Optional[str] = None
    ) -> bool:
        """Actualiza el precio de un producto"""
        try:
            with get_db_context() as db:
                product = db.query(Product).filter(Product.id == product_id).first()

                if not product:
                    logger.error(f"Product not found: {product_id}")
                    return False

                # Registrar historial de precios
                price_history = PriceHistory(
                    product_id=product_id, price=product.price, change_reason=reason, notes=notes
                )
                db.add(price_history)

                # Actualizar precio
                product["price"] = new_price
                product["updated_at"] = datetime.now(timezone.utc)

                db.commit()
                logger.info(f"Price updated for product {product.name}: ${product.price} -> ${new_price}")
                return True

        except Exception as e:
            logger.error(f"Error updating price: {e}")
            return False

    async def get_stock_report(self) -> Dict[str, Any]:
        """Genera reporte de inventario"""
        try:
            with get_db_context() as db:
                # Estadísticas generales
                total_products = db.query(Product).filter(Product.active).count()
                total_stock_value = (
                    db.query(func.sum(Product.price * Product.stock)).filter(Product.active).scalar() or 0
                )

                # Productos con stock bajo
                low_stock_products = await self.get_low_stock_products()

                # Productos sin stock
                out_of_stock = db.query(Product).filter(and_(Product.stock == 0, Product.active)).count()

                # Stock por categoría
                category_stock = (
                    db.query(
                        Category.display_name,
                        func.count(Product.id).label("products"),
                        func.sum(Product.stock).label("total_stock"),
                        func.sum(Product.price * Product.stock).label("stock_value"),
                    )
                    .join(Product)
                    .filter(and_(Category.active, Product.active))
                    .group_by(Category.id)
                    .all()
                )

                return {
                    "summary": {
                        "total_products": total_products,
                        "total_stock_value": float(total_stock_value),
                        "low_stock_count": len(low_stock_products),
                        "out_of_stock_count": out_of_stock,
                    },
                    "low_stock_products": [
                        {
                            "name": p.name,
                            "current_stock": p.stock,
                            "category": p.category.display_name,
                            "price": p.price,
                        }
                        for p in low_stock_products
                    ],
                    "category_breakdown": [
                        {
                            "category": row.display_name,
                            "products": row.products,
                            "total_stock": row.total_stock or 0,
                            "stock_value": float(row.stock_value or 0),
                        }
                        for row in category_stock
                    ],
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }

        except Exception as e:
            logger.error(f"Error generating stock report: {e}")
            return {}

    async def get_sales_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Obtiene analytics de ventas e interacciones"""
        try:
            with get_db_context() as db:
                # Período de análisis
                start_date = datetime.now(timezone.utc) - timedelta(days=days)

                # Consultas más frecuentes por categoría
                category_inquiries = (
                    db.query(Category.display_name, func.count(ProductInquiry.id).label("inquiry_count"))
                    .join(ProductInquiry)
                    .filter(ProductInquiry.created_at >= start_date)
                    .group_by(Category.id)
                    .order_by(desc("inquiry_count"))
                    .all()
                )

                # Productos más consultados
                product_inquiries = (
                    db.query(Product.name, func.count(ProductInquiry.id).label("inquiry_count"))
                    .join(ProductInquiry)
                    .filter(ProductInquiry.created_at >= start_date)
                    .group_by(Product.id)
                    .order_by(desc("inquiry_count"))
                    .limit(10)
                    .all()
                )

                # Clientes activos
                active_customers = db.query(Customer).filter(Customer.last_contact >= start_date).count()

                return {
                    "period_days": days,
                    "active_customers": active_customers,
                    "category_inquiries": [
                        {"category": row.display_name, "inquiries": row.inquiry_count} for row in category_inquiries
                    ],
                    "top_products": [
                        {"product": row.name, "inquiries": row.inquiry_count} for row in product_inquiries
                    ],
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }

        except Exception as e:
            logger.error(f"Error getting sales analytics: {e}")
            return {}


class CustomerService:
    """Servicio para gestionar clientes"""

    async def get_or_create_customer(self, phone_number: str, profile_name: Optional[str] = None) -> Optional[Customer]:
        """Obtiene o crea un cliente"""
        try:
            with get_db_context() as db:
                customer = db.query(Customer).filter(Customer.phone_number == phone_number).first()

                if not customer:
                    customer = Customer(
                        phone_number=phone_number,
                        profile_name=profile_name,
                        first_contact=datetime.now(timezone.utc),
                        last_contact=datetime.now(timezone.utc),
                    )
                    db.add(customer)
                    db.commit()
                    db.refresh(customer)
                    logger.info(f"New customer created: {phone_number}")
                else:
                    # Actualizar último contacto
                    customer["last_contact"] = datetime.now(timezone.utc)
                    customer["total_interactions"] = customer.total_interactions + 1
                    if profile_name and customer.profile_name is None:
                        customer["profile_name"] = profile_name
                    db.commit()

                return customer

        except Exception as e:
            logger.error(f"Error getting/creating customer: {e}")
            return None

    async def update_customer_interests(self, customer_id: str, interests: List[str]) -> bool:
        """Actualiza los intereses del cliente"""
        try:
            with get_db_context() as db:
                customer = db.query(Customer).filter(Customer.id == customer_id).first()

                if customer:
                    customer["interests"] = interests
                    customer["updated_at"] = datetime.now(timezone.utc)
                    db.commit()
                    return True

                return False

        except Exception as e:
            logger.error(f"Error updating customer interests: {e}")
            return False

    async def log_product_inquiry(
        self,
        customer_id: str,
        inquiry_type: str,
        inquiry_text: str,
        product_id: Optional[str] = None,
        category_id: Optional[str] = None,
        budget_mentioned: Optional[float] = None,
    ) -> bool:
        """Registra una consulta de producto"""
        try:
            with get_db_context() as db:
                inquiry = ProductInquiry(
                    customer_id=customer_id,
                    product_id=product_id,
                    category_id=category_id,
                    inquiry_type=inquiry_type,
                    inquiry_text=inquiry_text,
                    budget_mentioned=budget_mentioned,
                )
                db.add(inquiry)

                # Actualizar contador de consultas del cliente
                customer = db.query(Customer).filter(Customer.id == customer_id).first()
                if customer:
                    customer["total_inquiries"] = customer.total_inquiries + 1

                db.commit()
                return True

        except Exception as e:
            logger.error(f"Error logging product inquiry: {e}")
            return False
