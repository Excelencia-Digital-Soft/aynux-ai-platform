"""
Tests for Organization Resolver Service.

Tests organization resolution from query params, headers, and defaults.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.organization_resolver_service import (
    OrganizationResolutionError,
    OrganizationResolverService,
    get_organization_resolver,
)


class TestOrganizationResolverService:
    """Tests for OrganizationResolverService."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def mock_credential_service(self):
        """Create a mock credential service."""
        mock = MagicMock()
        mock.get_whatsapp_credentials = AsyncMock()
        return mock

    @pytest.fixture
    def resolver(self, mock_db, mock_credential_service):
        """Create resolver with mocked dependencies."""
        with patch(
            "app.services.organization_resolver_service.get_credential_service",
            return_value=mock_credential_service,
        ):
            return OrganizationResolverService(mock_db)

    @pytest.mark.asyncio
    async def test_resolve_from_query_param(self, resolver):
        """Test resolving organization from org_id query parameter."""
        org_id = uuid.uuid4()
        query_params = {"org_id": str(org_id)}
        headers = {}

        result = await resolver.resolve_organization(query_params, headers)

        assert result == org_id

    @pytest.mark.asyncio
    async def test_resolve_from_header(self, resolver):
        """Test resolving organization from X-Organization-ID header."""
        org_id = uuid.uuid4()
        query_params = {}
        headers = {"x-organization-id": str(org_id)}

        result = await resolver.resolve_organization(query_params, headers)

        assert result == org_id

    @pytest.mark.asyncio
    async def test_query_param_takes_precedence_over_header(self, resolver):
        """Test that query param takes precedence over header."""
        query_org_id = uuid.uuid4()
        header_org_id = uuid.uuid4()
        query_params = {"org_id": str(query_org_id)}
        headers = {"x-organization-id": str(header_org_id)}

        result = await resolver.resolve_organization(query_params, headers)

        assert result == query_org_id

    @pytest.mark.asyncio
    async def test_resolve_from_default_organization(self, mock_db, mock_credential_service):
        """Test falling back to default organization."""
        org_id = uuid.uuid4()
        mock_org = MagicMock()
        mock_org.id = org_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_org
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.organization_resolver_service.get_credential_service",
            return_value=mock_credential_service,
        ):
            resolver = OrganizationResolverService(mock_db)
            result = await resolver.resolve_organization({}, {})

        assert result == org_id

    @pytest.mark.asyncio
    async def test_raises_error_when_no_organization_found(self, mock_db, mock_credential_service):
        """Test that error is raised when no organization can be resolved."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.organization_resolver_service.get_credential_service",
            return_value=mock_credential_service,
        ):
            resolver = OrganizationResolverService(mock_db)

            with pytest.raises(OrganizationResolutionError) as exc_info:
                await resolver.resolve_organization({}, {})

            assert "No organization found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_error_for_invalid_uuid_in_query_param(self, resolver):
        """Test that error is raised for invalid UUID in query param."""
        query_params = {"org_id": "not-a-valid-uuid"}
        headers = {}

        with pytest.raises(OrganizationResolutionError) as exc_info:
            await resolver.resolve_organization(query_params, headers)

        assert "Invalid org_id format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_error_for_invalid_uuid_in_header(self, resolver):
        """Test that error is raised for invalid UUID in header."""
        query_params = {}
        headers = {"x-organization-id": "invalid-uuid"}

        with pytest.raises(OrganizationResolutionError) as exc_info:
            await resolver.resolve_organization(query_params, headers)

        assert "Invalid X-Organization-ID format" in str(exc_info.value)


class TestGetDefaultOrganization:
    """Tests for get_default_organization method."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def mock_credential_service(self):
        """Create a mock credential service."""
        mock = MagicMock()
        return mock

    @pytest.mark.asyncio
    async def test_returns_excelencia_organization(self, mock_db, mock_credential_service):
        """Test that 'excelencia' org is returned first."""
        mock_org = MagicMock()
        mock_org.slug = "excelencia"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_org
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.organization_resolver_service.get_credential_service",
            return_value=mock_credential_service,
        ):
            resolver = OrganizationResolverService(mock_db)
            result = await resolver.get_default_organization()

        assert result == mock_org
        # Should only call execute once (found on first try)
        assert mock_db.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_returns_system_organization_when_excelencia_not_found(
        self, mock_db, mock_credential_service
    ):
        """Test that 'system' org is returned if 'excelencia' not found."""
        mock_system_org = MagicMock()
        mock_system_org.slug = "system"

        # First call returns None (excelencia not found), second returns system
        mock_result_none = MagicMock()
        mock_result_none.scalar_one_or_none.return_value = None

        mock_result_system = MagicMock()
        mock_result_system.scalar_one_or_none.return_value = mock_system_org

        mock_db.execute = AsyncMock(side_effect=[mock_result_none, mock_result_system])

        with patch(
            "app.services.organization_resolver_service.get_credential_service",
            return_value=mock_credential_service,
        ):
            resolver = OrganizationResolverService(mock_db)
            result = await resolver.get_default_organization()

        assert result == mock_system_org
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_none_when_no_default_organization(self, mock_db, mock_credential_service):
        """Test that None is returned when neither default org exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.organization_resolver_service.get_credential_service",
            return_value=mock_credential_service,
        ):
            resolver = OrganizationResolverService(mock_db)
            result = await resolver.get_default_organization()

        assert result is None


class TestGetVerifyToken:
    """Tests for get_verify_token method."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.mark.asyncio
    async def test_returns_verify_token(self, mock_db):
        """Test successful retrieval of verify token."""
        org_id = uuid.uuid4()
        expected_token = "test-verify-token"

        mock_creds = MagicMock()
        mock_creds.verify_token = expected_token

        mock_credential_service = MagicMock()
        mock_credential_service.get_whatsapp_credentials = AsyncMock(return_value=mock_creds)

        with patch(
            "app.services.organization_resolver_service.get_credential_service",
            return_value=mock_credential_service,
        ):
            resolver = OrganizationResolverService(mock_db)
            result = await resolver.get_verify_token(org_id)

        assert result == expected_token
        mock_credential_service.get_whatsapp_credentials.assert_called_once_with(mock_db, org_id)


class TestFactoryFunction:
    """Tests for get_organization_resolver factory function."""

    def test_creates_resolver_instance(self):
        """Test that factory function creates resolver instance."""
        mock_db = AsyncMock(spec=AsyncSession)

        with patch("app.services.organization_resolver_service.get_credential_service"):
            resolver = get_organization_resolver(mock_db)

        assert isinstance(resolver, OrganizationResolverService)
