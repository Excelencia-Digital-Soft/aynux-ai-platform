"""PostgreSQL schema constants for multi-schema architecture.

This module defines the schema names used to organize database tables
into logical groups:
- core: System tables (auth, tenancy, configuration, shared knowledge)
- ecommerce: E-commerce domain (products, customers, orders)
- healthcare: Healthcare domain (patients, doctors, appointments)
- credit: Credit/finance domain (accounts, payments)
- soporte: Support/incidents domain (tickets, categories, Jira integration)
"""

# Core system schema - auth, tenancy, and shared resources
CORE_SCHEMA = "core"

# E-commerce domain schema
ECOMMERCE_SCHEMA = "ecommerce"

# Healthcare domain schema
HEALTHCARE_SCHEMA = "healthcare"

# Credit/finance domain schema
CREDIT_SCHEMA = "credit"

# Support/incidents domain schema
SOPORTE_SCHEMA = "soporte"

# Excelencia domain schema (Software Excelencia ERP)
EXCELENCIA_SCHEMA = "excelencia"

# Default search path for SQLAlchemy connections
DEFAULT_SEARCH_PATH = f"public,{CORE_SCHEMA},{ECOMMERCE_SCHEMA},{HEALTHCARE_SCHEMA},{CREDIT_SCHEMA},{SOPORTE_SCHEMA},{EXCELENCIA_SCHEMA}"

# All managed schemas (for Alembic configuration)
MANAGED_SCHEMAS = frozenset({
    "public",
    CORE_SCHEMA,
    ECOMMERCE_SCHEMA,
    HEALTHCARE_SCHEMA,
    CREDIT_SCHEMA,
    SOPORTE_SCHEMA,
    EXCELENCIA_SCHEMA,
})
