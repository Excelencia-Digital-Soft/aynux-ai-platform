"""
Configuración de productos y catálogo para el asesor de ventas IT
"""

from typing import Any, Dict, List

# Catálogo de productos con precios y especificaciones
PRODUCTS_CATALOG = {
    "laptops": {
        "gaming": [
            {
                "name": "ASUS ROG Strix G15",
                "specs": "AMD Ryzen 7, RTX 4060, 16GB RAM, 512GB SSD",
                "price": 1299,
                "category": "gaming",
                "stock": 15,
            },
            {
                "name": "MSI Katana 15",
                "specs": "Intel i7-13620H, RTX 4050, 16GB RAM, 1TB SSD",
                "price": 1099,
                "category": "gaming",
                "stock": 8,
            },
            {
                "name": "Acer Predator Helios 300",
                "specs": "Intel i5-12500H, RTX 4060, 16GB RAM, 512GB SSD",
                "price": 1199,
                "category": "gaming",
                "stock": 12,
            },
        ],
        "work": [
            {
                "name": "Lenovo ThinkPad E15",
                "specs": "Intel i5-1235U, Intel Iris Xe, 8GB RAM, 256GB SSD",
                "price": 699,
                "category": "work",
                "stock": 25,
            },
            {
                "name": "HP ProBook 450 G9",
                "specs": "Intel i7-1255U, Intel Iris Xe, 16GB RAM, 512GB SSD",
                "price": 899,
                "category": "work",
                "stock": 18,
            },
            {
                "name": "Dell Latitude 5530",
                "specs": "Intel i5-1245U, Intel Iris Xe, 8GB RAM, 256GB SSD",
                "price": 749,
                "category": "work",
                "stock": 22,
            },
        ],
        "budget": [
            {
                "name": "ASUS VivoBook 15",
                "specs": "AMD Ryzen 5 5500U, Radeon Graphics, 8GB RAM, 256GB SSD",
                "price": 449,
                "category": "budget",
                "stock": 30,
            },
            {
                "name": "HP Pavilion 15",
                "specs": "Intel i3-1215U, Intel UHD Graphics, 8GB RAM, 256GB SSD",
                "price": 399,
                "category": "budget",
                "stock": 35,
            },
        ],
    },
    "desktops": {
        "gaming": [
            {
                "name": "Gaming PC RTX 4070",
                "specs": "AMD Ryzen 5 7600X, RTX 4070, 16GB DDR5, 1TB NVMe SSD",
                "price": 1599,
                "category": "gaming",
                "stock": 10,
            },
            {
                "name": "Gaming PC RTX 4080",
                "specs": "Intel i7-13700K, RTX 4080, 32GB DDR5, 1TB NVMe SSD",
                "price": 2299,
                "category": "gaming",
                "stock": 5,
            },
        ],
        "work": [
            {
                "name": "Office PC Standard",
                "specs": "Intel i5-13400, Intel UHD 730, 16GB DDR4, 512GB SSD",
                "price": 649,
                "category": "work",
                "stock": 20,
            },
            {
                "name": "Workstation Pro",
                "specs": "AMD Ryzen 7 7700X, RTX 4060, 32GB DDR5, 1TB SSD",
                "price": 1399,
                "category": "work",
                "stock": 8,
            },
        ],
    },
    "components": {
        "cpus": [
            {
                "name": "AMD Ryzen 5 7600X",
                "specs": "6 cores, 12 threads, 4.7GHz boost",
                "price": 249,
                "category": "cpu",
                "stock": 15,
            },
            {
                "name": "Intel Core i7-13700K",
                "specs": "16 cores, 24 threads, 5.4GHz boost",
                "price": 399,
                "category": "cpu",
                "stock": 12,
            },
        ],
        "gpus": [
            {
                "name": "RTX 4060 Ti",
                "specs": "16GB VRAM, DLSS 3, Ray Tracing",
                "price": 499,
                "category": "gpu",
                "stock": 8,
            },
            {
                "name": "RTX 4070 Super",
                "specs": "12GB VRAM, DLSS 3, Ray Tracing",
                "price": 699,
                "category": "gpu",
                "stock": 6,
            },
        ],
        "ram": [
            {
                "name": "Corsair Vengeance LPX 16GB",
                "specs": "DDR4-3200, 2x8GB kit",
                "price": 79,
                "category": "ram",
                "stock": 25,
            },
            {
                "name": "G.Skill Trident Z5 32GB",
                "specs": "DDR5-5600, 2x16GB kit",
                "price": 199,
                "category": "ram",
                "stock": 15,
            },
        ],
    },
    "peripherals": [
        {
            "name": "Logitech G Pro X Superlight",
            "specs": "Gaming mouse, 25,600 DPI, wireless",
            "price": 149,
            "category": "mouse",
            "stock": 20,
        },
        {
            "name": "Corsair K70 RGB MK.2",
            "specs": "Mechanical keyboard, Cherry MX switches, RGB",
            "price": 169,
            "category": "keyboard",
            "stock": 18,
        },
        {
            "name": 'ASUS VG248QE 24"',
            "specs": "144Hz, 1ms, Full HD gaming monitor",
            "price": 199,
            "category": "monitor",
            "stock": 12,
        },
    ],
}

# Promociones actuales
CURRENT_PROMOTIONS = {
    "gaming_combo": {
        "name": "Combo Gaming Completo",
        "description": "PC Gaming + Monitor + Periféricos",
        "discount": 15,  # porcentaje
        "valid_until": "2025-06-30",
        "items": ["Gaming PC RTX 4070", 'ASUS VG248QE 24"', "Corsair K70 RGB MK.2"],
    },
    "office_deal": {
        "name": "Paquete Oficina",
        "description": "Laptop + Software Office",
        "discount": 10,
        "valid_until": "2025-07-15",
        "items": ["Lenovo ThinkPad E15", "Microsoft Office 2021"],
    },
}

# Configuración de respuestas por rango de precios
PRICE_RANGES = {
    "budget": {"min": 0, "max": 600, "message": "Tengo excelentes opciones económicas que te van a encantar"},
    "mid": {"min": 600, "max": 1500, "message": "En este rango tienes las mejores opciones calidad-precio"},
    "high": {"min": 1500, "max": 3000, "message": "Aquí están los equipos premium, lo mejor del mercado"},
    "premium": {"min": 3000, "max": float("inf"), "message": "Equipos de alta gama para profesionales exigentes"},
}

# Marcas disponibles y su reputación
BRANDS_INFO = {
    "ASUS": {"reputation": "premium", "specialty": "gaming", "warranty": "3 años"},
    "MSI": {"reputation": "gaming", "specialty": "gaming", "warranty": "2 años"},
    "Lenovo": {"reputation": "business", "specialty": "work", "warranty": "3 años"},
    "HP": {"reputation": "versatile", "specialty": "general", "warranty": "2 años"},
    "Dell": {"reputation": "business", "specialty": "work", "warranty": "3 años"},
    "Corsair": {"reputation": "premium", "specialty": "components", "warranty": "5 años"},
    "Logitech": {"reputation": "reliable", "specialty": "peripherals", "warranty": "2 años"},
}


def get_products_by_category(category: str) -> List[Dict[str, Any]]:
    """Obtiene productos por categoría"""
    if category in PRODUCTS_CATALOG:
        return PRODUCTS_CATALOG[category]
    return []


def get_products_by_price_range(min_price: int, max_price: int) -> List[Dict[str, Any]]:
    """Obtiene productos por rango de precio"""
    products = []
    for category in PRODUCTS_CATALOG.values():
        if isinstance(category, dict):
            for subcategory in category.values():
                if isinstance(subcategory, list):
                    products.extend([p for p in subcategory if min_price <= p["price"] <= max_price])
        elif isinstance(category, list):
            products.extend([p for p in category if min_price <= p["price"] <= max_price])
    return products


def get_product_recommendations(user_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Genera recomendaciones basadas en el perfil del usuario"""
    recommendations = []

    # Lógica de recomendación basada en intereses
    interests = user_profile.get("interests", [])
    budget = user_profile.get("budget", 1000)

    if "gaming" in interests:
        gaming_products = []
        for subcategory in PRODUCTS_CATALOG["laptops"]["gaming"]:
            if subcategory["price"] <= budget:
                gaming_products.append(subcategory)
        recommendations.extend(gaming_products[:3])

    if "work" in interests:
        work_products = []
        for subcategory in PRODUCTS_CATALOG["laptops"]["work"]:
            if subcategory["price"] <= budget:
                work_products.append(subcategory)
        recommendations.extend(work_products[:3])

    return recommendations[:5]  # Máximo 5 recomendaciones
