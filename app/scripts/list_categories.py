#!/usr/bin/env python3
"""
Script to list all categories in the database
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy import func

from app.database import get_db_context
from app.models.db import Category, Product


async def list_all_categories():
    """List all categories with their product counts"""
    print("📁 CATEGORIES IN DATABASE")
    print("=" * 80)

    try:
        with get_db_context() as db:
            # Query all categories with product counts
            categories = (
                db.query(
                    Category.id,
                    Category.name,
                    Category.display_name,
                    Category.description,
                    Category.active,
                    func.count(Product.id).label("product_count"),
                )
                .outerjoin(Product, Category.id == Product.category_id)
                .group_by(Category.id)
                .order_by(Category.name)
                .all()
            )

            if not categories:
                print("❌ No categories found in the database")
                return

            # Display categories
            print(f"Found {len(categories)} categories:\n")

            # Header
            print(f"{'Name':<20} {'Display Name':<30} {'Active':<8} {'Products':<10} {'Description'}")
            print("-" * 80)

            # Category details
            for cat in categories:
                cat_id, name, display_name, description, active, product_count = cat
                active_str = "✅" if active else "❌"
                desc_str = (description[:40] + "...") if description and len(description) > 40 else (description or "")

                print(f"{name:<20} {display_name:<30} {active_str:<8} {product_count:<10} {desc_str}")

            # Summary
            print("-" * 80)
            total_products = sum(cat[5] for cat in categories)  # cat[5] is product_count
            active_categories = sum(1 for cat in categories if cat[4])  # cat[4] is active

            print("\nSummary:")
            print(f"  • Total categories: {len(categories)}")
            print(f"  • Active categories: {active_categories}")
            print(f"  • Total products: {total_products}")

            # Categories with products
            categories_with_products = [cat for cat in categories if cat[5] > 0]
            if categories_with_products:
                print("\nCategories with products:")
                for cat in categories_with_products:
                    print(f"  • {cat[2]}: {cat[5]} products")  # cat[2] is display_name, cat[5] is product_count

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


async def list_categories_detailed():
    """List categories with more detailed information"""
    print("\n\n📊 DETAILED CATEGORY INFORMATION")
    print("=" * 80)

    try:
        with get_db_context() as db:
            # Get categories with aggregated data
            categories_data = (
                db.query(
                    Category.name,
                    Category.display_name,
                    func.count(Product.id).label("product_count"),
                    func.avg(Product.price).label("avg_price"),
                    func.min(Product.price).label("min_price"),
                    func.max(Product.price).label("max_price"),
                    func.sum(Product.stock).label("total_stock"),
                )
                .outerjoin(Product, (Category.id == Product.category_id) & Product.active)
                .filter(Category.active)
                .group_by(Category.id)
                .order_by(Category.name)
                .all()
            )

            if categories_data:
                for cat in categories_data:
                    name, display_name, count, avg_price, min_price, max_price, total_stock = cat

                    print(f"\n{display_name} ({name})")
                    print("  " + "-" * 40)

                    if count > 0:
                        print(f"  • Products: {count}")
                        print(f"  • Total stock: {total_stock or 0}")
                        print(f"  • Price range: ${min_price or 0:.2f} - ${max_price or 0:.2f}")
                        print(f"  • Average price: ${avg_price or 0:.2f}")
                    else:
                        print("  • No products in this category")

    except Exception as e:
        print(f"❌ Error getting detailed information: {e}")


async def main():
    """Main function"""
    # List basic categories
    await list_all_categories()

    # List detailed information
    await list_categories_detailed()


if __name__ == "__main__":
    asyncio.run(main())

