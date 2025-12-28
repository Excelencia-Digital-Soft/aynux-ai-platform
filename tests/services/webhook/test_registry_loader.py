"""
Tests for Tenant Registry Loader.

Tests loading tenant agent registries from context and organization.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenancy.registry_loader import (
    TenantRegistryLoader,
    get_registry_loader,
)


class TestTenantRegistryLoader:
    """Tests for TenantRegistryLoader."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def loader(self, mock_db):
        """Create loader with mock db."""
        return TenantRegistryLoader(mock_db)

    def test_agent_service_is_lazy_loaded(self, loader):
        """Test that agent_service is not loaded until accessed."""
        # Before access, should be None
        assert loader._agent_service is None

    @pytest.mark.asyncio
    async def test_load_from_context_returns_none_when_no_context(self, loader):
        """Test that None is returned when no tenant context exists."""
        with patch(
            "app.core.tenancy.registry_loader.get_tenant_context",
            return_value=None,
        ):
            result = await loader.load_from_context()

        assert result is None

    @pytest.mark.asyncio
    async def test_load_from_context_returns_none_when_no_org_id(self, loader):
        """Test that None is returned when context has no organization_id."""
        mock_ctx = MagicMock()
        mock_ctx.organization_id = None

        with patch(
            "app.core.tenancy.registry_loader.get_tenant_context",
            return_value=mock_ctx,
        ):
            result = await loader.load_from_context()

        assert result is None

    @pytest.mark.asyncio
    async def test_load_from_context_delegates_to_load_for_organization(self, mock_db):
        """Test that load_from_context delegates to load_for_organization."""
        org_id = uuid.uuid4()
        mock_ctx = MagicMock()
        mock_ctx.organization_id = org_id

        mock_registry = MagicMock()
        mock_agent_service = MagicMock()
        mock_agent_service.get_agent_registry = AsyncMock(return_value=mock_registry)

        loader = TenantRegistryLoader(mock_db)
        # Directly set the private attribute to bypass the property
        loader._agent_service = mock_agent_service

        with patch(
            "app.core.tenancy.registry_loader.get_tenant_context",
            return_value=mock_ctx,
        ):
            result = await loader.load_from_context()

        assert result == mock_registry
        mock_agent_service.get_agent_registry.assert_called_once_with(org_id)

    @pytest.mark.asyncio
    async def test_load_for_organization_returns_registry(self, mock_db):
        """Test successful registry loading for an organization."""
        org_id = uuid.uuid4()
        mock_registry = MagicMock()

        mock_agent_service = MagicMock()
        mock_agent_service.get_agent_registry = AsyncMock(return_value=mock_registry)

        loader = TenantRegistryLoader(mock_db)
        # Directly set the private attribute to bypass the property
        loader._agent_service = mock_agent_service

        result = await loader.load_for_organization(org_id)

        assert result == mock_registry
        mock_agent_service.get_agent_registry.assert_called_once_with(org_id)

    @pytest.mark.asyncio
    async def test_load_for_organization_handles_import_error(self, mock_db):
        """Test that ImportError is handled gracefully."""
        org_id = uuid.uuid4()

        # Patch the import inside the property getter
        with patch.dict("sys.modules", {"app.core.tenancy.agent_service": None}):
            loader = TenantRegistryLoader(mock_db)
            # Force the property to re-evaluate by resetting the cached service
            loader._agent_service = None

            # The import error will be caught and result in None
            result = await loader.load_for_organization(org_id)

        # Since the property catches ImportError, it returns None
        assert result is None

    @pytest.mark.asyncio
    async def test_load_for_organization_handles_exception(self, mock_db):
        """Test that general exceptions are handled gracefully."""
        org_id = uuid.uuid4()

        mock_agent_service = MagicMock()
        mock_agent_service.get_agent_registry = AsyncMock(
            side_effect=Exception("Database error")
        )

        loader = TenantRegistryLoader(mock_db)
        # Directly set the private attribute to bypass the property
        loader._agent_service = mock_agent_service

        result = await loader.load_for_organization(org_id)

        assert result is None


class TestAgentServiceProperty:
    """Tests for the agent_service lazy property."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return AsyncMock(spec=AsyncSession)

    def test_agent_service_is_created_on_first_access(self, mock_db):
        """Test that TenantAgentService is created on first property access."""
        loader = TenantRegistryLoader(mock_db)

        mock_service = MagicMock()

        with patch(
            "app.core.tenancy.agent_service.TenantAgentService",
            return_value=mock_service,
        ):
            # First access should create the service
            service1 = loader.agent_service

            assert service1 == mock_service

    def test_agent_service_is_cached(self, mock_db):
        """Test that TenantAgentService is only created once."""
        loader = TenantRegistryLoader(mock_db)

        mock_service = MagicMock()

        with patch(
            "app.core.tenancy.agent_service.TenantAgentService",
            return_value=mock_service,
        ) as MockAgentService:
            # First access
            service1 = loader.agent_service
            # Second access
            service2 = loader.agent_service

            assert service1 is service2
            # Should only be created once (the import happens once, then cached)
            assert MockAgentService.call_count == 1


class TestFactoryFunction:
    """Tests for get_registry_loader factory function."""

    def test_creates_loader_instance(self):
        """Test that factory function creates loader instance."""
        mock_db = AsyncMock(spec=AsyncSession)

        loader = get_registry_loader(mock_db)

        assert isinstance(loader, TenantRegistryLoader)
