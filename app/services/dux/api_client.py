from typing import Any, Dict, List, Optional

import httpx
from config.settings import get_settings


class DuxAPIClient:
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.DUX_API_BASE_URL
        self.token = self.settings.DUX_API_KEY
        self.headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def get_products(self, search_term: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve products from Dux Software API"""
        async with httpx.AsyncClient() as client:
            params = {"search": search_term} if search_term else {}
            response = await client.get(f"{self.base_url}/items", headers=self.headers, params=params)
            response.raise_for_status()
            return response.json().get("data", [])

    async def get_sales_data(self, date_from: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve sales data"""
        async with httpx.AsyncClient() as client:
            params = {"fecha_desde": date_from} if date_from else {}
            response = await client.get(f"{self.base_url}/ventas", headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()

    async def get_orders(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve orders data"""
        async with httpx.AsyncClient() as client:
            params = {"estado": status} if status else {}
            response = await client.get(f"{self.base_url}/pedidos", headers=self.headers, params=params)
            response.raise_for_status()
            return response.json().get("data", [])
