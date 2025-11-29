"""
Show Modules Use Case

Use case for displaying available ERP modules.
Follows Clean Architecture and SOLID principles.
"""

import logging
from dataclasses import dataclass, field

from app.domains.excelencia.domain.value_objects.erp_types import ModuleType, LicenseType

logger = logging.getLogger(__name__)


@dataclass
class ShowModulesRequest:
    """Request for showing modules."""

    license_type: LicenseType | None = None
    include_description: bool = True
    language: str = "es"


@dataclass
class ModuleInfo:
    """Information about a single module."""

    module_type: ModuleType
    display_name: str
    description: str
    features: list[str]
    is_available: bool = True


@dataclass
class ShowModulesResponse:
    """Response containing available modules."""

    success: bool
    modules: list[ModuleInfo] = field(default_factory=list)
    total_count: int = 0
    license_info: dict | None = None
    error: str | None = None


class ShowModulesUseCase:
    """
    Use case for showing ERP modules.

    Displays available modules based on license type and configuration.
    """

    # Module descriptions in Spanish
    MODULE_DESCRIPTIONS = {
        ModuleType.SALES: {
            "name": "Ventas",
            "description": "Gestion completa de ventas, cotizaciones, pedidos y facturacion.",
            "features": [
                "Cotizaciones y presupuestos",
                "Ordenes de venta",
                "Facturacion electronica",
                "Gestion de clientes",
                "Reportes de ventas",
            ],
        },
        ModuleType.INVENTORY: {
            "name": "Inventario",
            "description": "Control de stock, almacenes y movimientos de inventario.",
            "features": [
                "Control de stock en tiempo real",
                "Multiples almacenes",
                "Movimientos de inventario",
                "Lotes y series",
                "Alertas de stock bajo",
            ],
        },
        ModuleType.PURCHASING: {
            "name": "Compras",
            "description": "Gestion de compras, proveedores y ordenes de compra.",
            "features": [
                "Ordenes de compra",
                "Gestion de proveedores",
                "Comparacion de precios",
                "Recepcion de mercaderia",
                "Evaluacion de proveedores",
            ],
        },
        ModuleType.ACCOUNTING: {
            "name": "Contabilidad",
            "description": "Contabilidad general, asientos, balances y estados financieros.",
            "features": [
                "Plan de cuentas",
                "Asientos contables",
                "Balance general",
                "Estado de resultados",
                "Conciliacion bancaria",
            ],
        },
        ModuleType.HR: {
            "name": "Recursos Humanos",
            "description": "Gestion de empleados, nomina y control de asistencia.",
            "features": [
                "Legajos de personal",
                "Liquidacion de sueldos",
                "Control de asistencia",
                "Vacaciones y licencias",
                "Reportes AFIP",
            ],
        },
        ModuleType.CRM: {
            "name": "CRM",
            "description": "Gestion de relaciones con clientes y oportunidades.",
            "features": [
                "Gestion de leads",
                "Pipeline de ventas",
                "Seguimiento de oportunidades",
                "Campanas de marketing",
                "Reportes de conversion",
            ],
        },
        ModuleType.PRODUCTION: {
            "name": "Produccion",
            "description": "Control de produccion, ordenes de trabajo y planificacion.",
            "features": [
                "Ordenes de produccion",
                "Listas de materiales (BOM)",
                "Planificacion de produccion",
                "Control de calidad",
                "Costos de produccion",
            ],
        },
        ModuleType.REPORTS: {
            "name": "Reportes",
            "description": "Reportes avanzados y analisis de datos.",
            "features": [
                "Reportes personalizados",
                "Exportacion a Excel/PDF",
                "Graficos interactivos",
                "KPIs y metricas",
                "Programacion de reportes",
            ],
        },
        ModuleType.DASHBOARD: {
            "name": "Dashboard",
            "description": "Panel de control con indicadores clave del negocio.",
            "features": [
                "Indicadores en tiempo real",
                "Widgets personalizables",
                "Alertas automaticas",
                "Visualizacion de datos",
                "Acceso rapido a funciones",
            ],
        },
    }

    # Modules available per license type
    LICENSE_MODULES = {
        LicenseType.TRIAL: [ModuleType.SALES, ModuleType.INVENTORY, ModuleType.DASHBOARD],
        LicenseType.BASIC: [
            ModuleType.SALES,
            ModuleType.INVENTORY,
            ModuleType.PURCHASING,
            ModuleType.REPORTS,
            ModuleType.DASHBOARD,
        ],
        LicenseType.PROFESSIONAL: [
            ModuleType.SALES,
            ModuleType.INVENTORY,
            ModuleType.PURCHASING,
            ModuleType.ACCOUNTING,
            ModuleType.HR,
            ModuleType.CRM,
            ModuleType.REPORTS,
            ModuleType.DASHBOARD,
        ],
        LicenseType.ENTERPRISE: list(ModuleType),  # All modules
    }

    def __init__(self):
        """Initialize use case."""
        pass

    async def execute(self, request: ShowModulesRequest) -> ShowModulesResponse:
        """
        Execute show modules use case.

        Args:
            request: Request parameters

        Returns:
            Response with available modules
        """
        try:
            # Determine available modules based on license
            if request.license_type:
                available_types = self.LICENSE_MODULES.get(request.license_type, [])
            else:
                available_types = list(ModuleType)  # Show all if no license specified

            # Build module info list
            modules: list[ModuleInfo] = []
            for module_type in ModuleType:
                info = self.MODULE_DESCRIPTIONS.get(module_type, {})
                is_available = module_type in available_types

                # Extract values with proper type handling
                display_name = info.get("name", module_type.get_display_name())
                description_val = info.get("description", "")
                features_val = info.get("features", [])

                module_info = ModuleInfo(
                    module_type=module_type,
                    display_name=str(display_name) if display_name else module_type.get_display_name(),
                    description=str(description_val) if request.include_description else "",
                    features=list(features_val) if request.include_description and isinstance(features_val, list) else [],
                    is_available=is_available,
                )
                modules.append(module_info)

            # Build license info
            license_info = None
            if request.license_type:
                license_info = {
                    "type": request.license_type.value,
                    "max_users": request.license_type.get_max_users(),
                    "available_modules_count": len(available_types),
                }

            logger.info(f"Showing {len(modules)} modules for license: {request.license_type}")

            return ShowModulesResponse(
                success=True,
                modules=modules,
                total_count=len(modules),
                license_info=license_info,
            )

        except Exception as e:
            logger.error(f"Error showing modules: {e}", exc_info=True)
            return ShowModulesResponse(
                success=False,
                error=f"Failed to show modules: {str(e)}",
            )

    def get_module_summary_text(self, response: ShowModulesResponse) -> str:
        """
        Generate text summary of modules for chat response.

        Args:
            response: ShowModulesResponse

        Returns:
            Formatted text summary
        """
        if not response.success:
            return f"Error: {response.error}"

        lines = ["Modulos disponibles en Excelencia ERP:\n"]

        for module in response.modules:
            status = "[Disponible]" if module.is_available else "[No incluido]"
            lines.append(f"- {module.display_name} {status}")
            if module.description:
                lines.append(f"  {module.description}")

        if response.license_info:
            lines.append(f"\nLicencia: {response.license_info['type'].title()}")
            lines.append(f"Usuarios maximos: {response.license_info['max_users']}")

        return "\n".join(lines)
