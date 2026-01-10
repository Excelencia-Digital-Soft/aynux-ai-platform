"""
Excelencia Software Domain Value Objects

Value objects for ERP-related types and configurations.
"""

from enum import Enum


class ModuleType(str, Enum):
    """ERP module types."""

    SALES = "sales"
    INVENTORY = "inventory"
    PURCHASING = "purchasing"
    ACCOUNTING = "accounting"
    HR = "hr"
    CRM = "crm"
    PRODUCTION = "production"
    REPORTS = "reports"
    DASHBOARD = "dashboard"

    def get_display_name(self) -> str:
        """Get human-readable name."""
        names = {
            ModuleType.SALES: "Ventas",
            ModuleType.INVENTORY: "Inventario",
            ModuleType.PURCHASING: "Compras",
            ModuleType.ACCOUNTING: "Contabilidad",
            ModuleType.HR: "Recursos Humanos",
            ModuleType.CRM: "CRM",
            ModuleType.PRODUCTION: "Produccion",
            ModuleType.REPORTS: "Reportes",
            ModuleType.DASHBOARD: "Dashboard",
        }
        return names.get(self, self.value.title())


class LicenseType(str, Enum):
    """License types."""

    TRIAL = "trial"
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"

    def get_max_users(self) -> int:
        """Get maximum users for license type."""
        limits = {
            LicenseType.TRIAL: 3,
            LicenseType.BASIC: 10,
            LicenseType.PROFESSIONAL: 50,
            LicenseType.ENTERPRISE: 999,
        }
        return limits.get(self, 1)
