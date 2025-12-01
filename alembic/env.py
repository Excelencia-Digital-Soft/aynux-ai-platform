"""
Alembic environment configuration for Aynux multi-tenant system.

This module configures Alembic to use the application's database settings
and SQLAlchemy models for migration autogeneration.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import settings to get database URL
from app.config.settings import get_settings

# Import Base and all models for autogenerate support
from app.models.db.base import Base

# Import all existing models to register them with Base.metadata
from app.models.db.catalog import Brand, Category, Product  # noqa: F401
from app.models.db.contact_domains import ContactDomain, DomainConfig  # noqa: F401
from app.models.db.conversations import Conversation, Message  # noqa: F401
from app.models.db.customers import Customer  # noqa: F401
from app.models.db.inquiries import ProductInquiry  # noqa: F401
from app.models.db.knowledge_base import CompanyKnowledge  # noqa: F401
from app.models.db.orders import Order, OrderItem  # noqa: F401
from app.models.db.promotions import Promotion  # noqa: F401
from app.models.db.prompts import Prompt, PromptVersion  # noqa: F401
from app.models.db.reviews import ProductReview  # noqa: F401
from app.models.db.user import UserDB  # noqa: F401
from app.models.db.analytics import Analytics, PriceHistory, StockMovement  # noqa: F401

# Import tenancy models
from app.models.db.tenancy import (  # noqa: F401
    Organization,
    OrganizationUser,
    TenantAgent,
    TenantConfig,
    TenantDocument,
    TenantPrompt,
)

# Import domain-specific models
from app.domains.healthcare.infrastructure.persistence.sqlalchemy.models import (  # noqa: F401
    PatientModel,
    DoctorModel,
    AppointmentModel,
)
from app.domains.credit.infrastructure.persistence.sqlalchemy.models import (  # noqa: F401
    CreditAccountModel,
    PaymentModel,
    PaymentScheduleItemModel,
)

# Import schema definitions for multi-schema support
from app.models.db.schemas import DEFAULT_SEARCH_PATH, MANAGED_SCHEMAS

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Get settings and set database URL
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    """
    Include objects from our managed schemas.

    This function filters which database objects should be included
    in migration autogeneration.
    """
    if type_ == "table":
        schema = getattr(object, "schema", None) or "public"
        return schema in MANAGED_SCHEMAS
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
        include_object=include_object,
        version_table_schema="public",
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    from sqlalchemy import text

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Set search_path to include all schemas
        connection.execute(text(f"SET search_path TO {DEFAULT_SEARCH_PATH}"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_schemas=True,
            include_object=include_object,
            version_table_schema="public",
            transaction_per_migration=True,
        )

        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
