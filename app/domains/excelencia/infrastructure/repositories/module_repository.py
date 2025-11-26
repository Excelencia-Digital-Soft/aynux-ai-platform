"""
Module Repository Implementation

In-memory implementation of module repository for Excelencia ERP.
Can be replaced with SQLAlchemy implementation when database is needed.
"""

import logging
from datetime import UTC, datetime

from app.domains.excelencia.domain.entities.module import (
    ERPModule,
    ModuleCategory,
    ModuleStatus,
)

logger = logging.getLogger(__name__)


class InMemoryModuleRepository:
    """
    In-memory implementation of IModuleRepository.

    Uses predefined module data for the Excelencia ERP system.
    Can be extended to use database in the future.
    """

    def __init__(self):
        self._modules: dict[str, ERPModule] = {}
        self._initialize_default_modules()

    def _initialize_default_modules(self) -> None:
        """Initialize with default Excelencia ERP modules"""
        default_modules = [
            ERPModule(
                id="mod-001",
                code="FIN-001",
                name="Contabilidad",
                description="Gestion contable completa con plan de cuentas configurable",
                category=ModuleCategory.FINANCE,
                status=ModuleStatus.ACTIVE,
                features=["Plan de cuentas", "Asientos automaticos", "Balance", "Estado de resultados"],
                pricing_tier="standard",
            ),
            ERPModule(
                id="mod-002",
                code="INV-001",
                name="Inventario",
                description="Control de stock en tiempo real con multiples depositos",
                category=ModuleCategory.INVENTORY,
                status=ModuleStatus.ACTIVE,
                features=["Multi-deposito", "Trazabilidad", "Alertas de stock", "Codigos de barras"],
                pricing_tier="standard",
            ),
            ERPModule(
                id="mod-003",
                code="VTA-001",
                name="Ventas",
                description="Gestion de ventas, cotizaciones y facturacion electronica",
                category=ModuleCategory.SALES,
                status=ModuleStatus.ACTIVE,
                features=["Cotizaciones", "Facturacion electronica", "Notas de credito", "Reportes"],
                pricing_tier="standard",
            ),
            ERPModule(
                id="mod-004",
                code="CMP-001",
                name="Compras",
                description="Gestion de compras y proveedores",
                category=ModuleCategory.PURCHASING,
                status=ModuleStatus.ACTIVE,
                features=["Ordenes de compra", "Gestion proveedores", "Recepcion", "Control de pagos"],
                pricing_tier="standard",
            ),
            ERPModule(
                id="mod-005",
                code="RH-001",
                name="Recursos Humanos",
                description="Gestion de personal, nomina y asistencia",
                category=ModuleCategory.HR,
                status=ModuleStatus.ACTIVE,
                features=["Legajos", "Liquidacion sueldos", "Asistencia", "Vacaciones"],
                pricing_tier="premium",
            ),
            ERPModule(
                id="mod-006",
                code="CRM-001",
                name="CRM",
                description="Gestion de relaciones con clientes y oportunidades",
                category=ModuleCategory.CRM,
                status=ModuleStatus.BETA,
                features=["Pipeline ventas", "Seguimiento clientes", "Campanas", "Reportes"],
                pricing_tier="premium",
            ),
            ERPModule(
                id="mod-007",
                code="PRD-001",
                name="Produccion",
                description="Control de produccion y ordenes de trabajo",
                category=ModuleCategory.PRODUCTION,
                status=ModuleStatus.ACTIVE,
                features=["Ordenes produccion", "Formula/BOM", "Control calidad", "Costos"],
                pricing_tier="enterprise",
            ),
            ERPModule(
                id="mod-008",
                code="RPT-001",
                name="Business Intelligence",
                description="Reportes avanzados y dashboards ejecutivos",
                category=ModuleCategory.REPORTING,
                status=ModuleStatus.ACTIVE,
                features=["Dashboards", "KPIs", "Reportes personalizados", "Exportacion"],
                pricing_tier="premium",
            ),
        ]

        for module in default_modules:
            self._modules[module.id] = module

        logger.info(f"Initialized {len(self._modules)} default modules")

    async def get_all(self) -> list[ERPModule]:
        """Get all modules"""
        return list(self._modules.values())

    async def get_by_id(self, module_id: str) -> ERPModule | None:
        """Get module by ID"""
        return self._modules.get(module_id)

    async def get_by_code(self, code: str) -> ERPModule | None:
        """Get module by code"""
        for module in self._modules.values():
            if module.code == code:
                return module
        return None

    async def get_by_category(self, category: ModuleCategory) -> list[ERPModule]:
        """Get modules by category"""
        return [m for m in self._modules.values() if m.category == category]

    async def save(self, module: ERPModule) -> ERPModule:
        """Save a module"""
        module.updated_at = datetime.now(UTC)
        self._modules[module.id] = module
        logger.info(f"Saved module: {module.code}")
        return module
