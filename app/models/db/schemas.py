"""PostgreSQL schema constants for multi-schema architecture.

This module defines the schema names used to organize database tables
into logical groups:
- core: System tables (auth, tenancy, configuration, shared knowledge)
- ecommerce: E-commerce domain (products, customers, orders)
- healthcare: Healthcare domain (patients, doctors, appointments)
- credit: Credit/finance domain (accounts, payments)
"""

# Core system schema - auth, tenancy, and shared resources
CORE_SCHEMA = "core"

# E-commerce domain schema
ECOMMERCE_SCHEMA = "ecommerce"

# Healthcare domain schema
HEALTHCARE_SCHEMA = "healthcare"

# Credit/finance domain schema
CREDIT_SCHEMA = "credit"

# Default search path for SQLAlchemy connections
DEFAULT_SEARCH_PATH = f"public,{CORE_SCHEMA},{ECOMMERCE_SCHEMA},{HEALTHCARE_SCHEMA},{CREDIT_SCHEMA}"

# All managed schemas (for Alembic configuration)
MANAGED_SCHEMAS = frozenset({
    "public",
    CORE_SCHEMA,
    ECOMMERCE_SCHEMA,
    HEALTHCARE_SCHEMA,
    CREDIT_SCHEMA,
})
