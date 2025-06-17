"""
Category database query tool for LangGraph agents.
"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select

from app.database.async_db import get_async_db_context
from app.models.db import Category, Product

logger = logging.getLogger(__name__)


class CategoryTool:
    """Tool for querying category information from the database."""
    
    def __init__(self):
        self.name = "category_database_tool"
        self.description = "Query category information from the database including products counts and price statistics"
    
    async def get_all_categories(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch all categories from the database with product counts and price statistics.
        
        Args:
            include_inactive: Whether to include inactive categories
            
        Returns:
            List of category dictionaries with detailed information
        """
        try:
            async with get_async_db_context() as db:
                # Build base query
                query = select(
                    Category,
                    func.count(Product.id).label('product_count'),
                    func.min(Product.price).label('min_price'),
                    func.max(Product.price).label('max_price'),
                    func.avg(Product.price).label('avg_price'),
                    func.sum(Product.stock).label('total_stock')
                ).outerjoin(
                    Product, 
                    (Category.id == Product.category_id) & Product.active.is_(True)
                ).group_by(Category.id)
                
                # Filter by active status if needed
                if not include_inactive:
                    query = query.where(Category.active.is_(True))
                
                result = await db.execute(query)
                rows = result.all()
                
                categories = []
                for row in rows:
                    category = row[0]
                    categories.append({
                        "id": category.name,
                        "name": category.display_name,
                        "description": category.description,
                        "is_active": category.active,
                        "product_count": row[1] or 0,
                        "min_price": float(row[2]) if row[2] else None,
                        "max_price": float(row[3]) if row[3] else None,
                        "avg_price": float(row[4]) if row[4] else None,
                        "total_stock": row[5] or 0
                    })
                
                return categories
                
        except Exception as e:
            logger.error(f"Error fetching categories: {str(e)}")
            return []
    
    async def get_category_by_name(self, category_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a specific category by name or display name.
        
        Args:
            category_name: The category name to search for
            
        Returns:
            Category dictionary or None if not found
        """
        try:
            async with get_async_db_context() as db:
                # Search by both name and display_name
                query = select(
                    Category,
                    func.count(Product.id).label('product_count'),
                    func.min(Product.price).label('min_price'),
                    func.max(Product.price).label('max_price'),
                    func.avg(Product.price).label('avg_price'),
                    func.sum(Product.stock).label('total_stock')
                ).outerjoin(
                    Product,
                    (Category.id == Product.category_id) & Product.active.is_(True)
                ).where(
                    (func.lower(Category.name) == category_name.lower()) |
                    (func.lower(Category.display_name) == category_name.lower())
                ).group_by(Category.id)
                
                result = await db.execute(query)
                row = result.first()
                
                if row:
                    category = row[0]
                    return {
                        "id": category.name,
                        "name": category.display_name,
                        "description": category.description,
                        "is_active": category.active,
                        "product_count": row[1] or 0,
                        "min_price": float(row[2]) if row[2] else None,
                        "max_price": float(row[3]) if row[3] else None,
                        "avg_price": float(row[4]) if row[4] else None,
                        "total_stock": row[5] or 0
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Error fetching category by name: {str(e)}")
            return None
    
    async def get_categories_with_products(self) -> List[Dict[str, Any]]:
        """
        Fetch only categories that have active products.
        
        Returns:
            List of category dictionaries with product information
        """
        categories = await self.get_all_categories(include_inactive=False)
        return [cat for cat in categories if cat["product_count"] > 0]
    
    async def search_categories(self, search_term: str) -> List[Dict[str, Any]]:
        """
        Search categories by name or description.
        
        Args:
            search_term: Term to search for in category names and descriptions
            
        Returns:
            List of matching categories
        """
        try:
            async with get_async_db_context() as db:
                search_pattern = f"%{search_term}%"
                
                query = select(
                    Category,
                    func.count(Product.id).label('product_count'),
                    func.min(Product.price).label('min_price'),
                    func.max(Product.price).label('max_price'),
                    func.avg(Product.price).label('avg_price'),
                    func.sum(Product.stock).label('total_stock')
                ).outerjoin(
                    Product,
                    (Category.id == Product.category_id) & Product.active.is_(True)
                ).where(
                    Category.active.is_(True),
                    (Category.name.ilike(search_pattern)) |
                    (Category.display_name.ilike(search_pattern)) |
                    (Category.description.ilike(search_pattern))
                ).group_by(Category.id)
                
                result = await db.execute(query)
                rows = result.all()
                
                categories = []
                for row in rows:
                    category = row[0]
                    categories.append({
                        "id": category.name,
                        "name": category.display_name,
                        "description": category.description,
                        "is_active": category.active,
                        "product_count": row[1] or 0,
                        "min_price": float(row[2]) if row[2] else None,
                        "max_price": float(row[3]) if row[3] else None,
                        "avg_price": float(row[4]) if row[4] else None,
                        "total_stock": row[5] or 0
                    })
                
                return categories
                
        except Exception as e:
            logger.error(f"Error searching categories: {str(e)}")
            return []
    
    async def __call__(self, action: str, **kwargs) -> Dict[str, Any]:
        """
        Execute tool action.
        
        Args:
            action: The action to perform (get_all, get_by_name, search, with_products)
            **kwargs: Additional parameters for the action
            
        Returns:
            Dictionary with results or error
        """
        try:
            if action == "get_all":
                include_inactive = kwargs.get("include_inactive", False)
                categories = await self.get_all_categories(include_inactive)
                return {"success": True, "categories": categories}
            
            elif action == "get_by_name":
                category_name = kwargs.get("category_name")
                if not category_name:
                    return {"success": False, "error": "category_name is required"}
                category = await self.get_category_by_name(category_name)
                return {"success": True, "category": category}
            
            elif action == "search":
                search_term = kwargs.get("search_term")
                if not search_term:
                    return {"success": False, "error": "search_term is required"}
                categories = await self.search_categories(search_term)
                return {"success": True, "categories": categories}
            
            elif action == "with_products":
                categories = await self.get_categories_with_products()
                return {"success": True, "categories": categories}
            
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
                
        except Exception as e:
            logger.error(f"Error executing category tool action: {str(e)}")
            return {"success": False, "error": str(e)}