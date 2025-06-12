"""
Tools especializadas para agentes ReAct
"""

from .product_tools import (
    search_products_tool,
    get_product_details_tool,
    check_stock_tool,
    compare_products_tool
)

from .ecommerce_tools import (
    get_categories_tool,
    get_promotions_tool,
    calculate_shipping_tool,
    get_payment_methods_tool
)

from .support_tools import (
    search_faq_tool,
    create_ticket_tool,
    get_warranty_info_tool
)

from .tracking_tools import (
    track_order_tool,
    get_delivery_info_tool,
    update_shipping_address_tool
)

__all__ = [
    # Product tools
    "search_products_tool",
    "get_product_details_tool", 
    "check_stock_tool",
    "compare_products_tool",
    
    # Ecommerce tools
    "get_categories_tool",
    "get_promotions_tool",
    "calculate_shipping_tool",
    "get_payment_methods_tool",
    
    # Support tools
    "search_faq_tool",
    "create_ticket_tool", 
    "get_warranty_info_tool",
    
    # Tracking tools
    "track_order_tool",
    "get_delivery_info_tool",
    "update_shipping_address_tool"
]