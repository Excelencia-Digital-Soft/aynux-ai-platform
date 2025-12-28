"""
Tests for Bypass Routing Service.

Tests bypass rule evaluation and pattern matching.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.tenancy import BypassRule
from app.services.bypass_routing_service import (
    BypassMatch,
    BypassRoutingService,
    get_bypass_routing_service,
)


class TestBypassMatch:
    """Tests for BypassMatch dataclass."""

    def test_create_bypass_match(self):
        """Test creating a BypassMatch."""
        org_id = uuid.uuid4()
        match = BypassMatch(
            organization_id=org_id,
            domain="excelencia",
            target_agent="support_agent",
        )

        assert match.organization_id == org_id
        assert match.domain == "excelencia"
        assert match.target_agent == "support_agent"

    def test_bypass_match_is_frozen(self):
        """Test that BypassMatch is immutable."""
        org_id = uuid.uuid4()
        match = BypassMatch(
            organization_id=org_id,
            domain="excelencia",
            target_agent="support_agent",
        )

        with pytest.raises(AttributeError):
            match.domain = "ecommerce"


class TestBypassRuleMatches:
    """Tests for BypassRule.matches() method."""

    def test_phone_pattern_exact_match(self):
        """Test exact phone pattern match."""
        rule = BypassRule(
            id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            rule_name="test",
            rule_type="phone_number",
            pattern="5491155001234",
            target_agent="test_agent",
            enabled=True,
        )

        assert rule.matches("5491155001234") is True
        assert rule.matches("5491155001235") is False

    def test_phone_pattern_wildcard_match(self):
        """Test wildcard phone pattern match."""
        rule = BypassRule(
            id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            rule_name="test",
            rule_type="phone_number",
            pattern="549115*",
            target_agent="test_agent",
            enabled=True,
        )

        assert rule.matches("5491155001234") is True
        assert rule.matches("5491156789012") is True
        assert rule.matches("5492645001234") is False

    def test_phone_pattern_no_match_when_disabled(self):
        """Test that disabled rules don't match."""
        rule = BypassRule(
            id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            rule_name="test",
            rule_type="phone_number",
            pattern="549115*",
            target_agent="test_agent",
            enabled=False,
        )

        assert rule.matches("5491155001234") is False

    def test_phone_number_list_match(self):
        """Test phone number list match."""
        rule = BypassRule(
            id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            rule_name="test",
            rule_type="phone_number_list",
            phone_numbers=["5491155001234", "5491155001235", "5491155001236"],
            target_agent="test_agent",
            enabled=True,
        )

        assert rule.matches("5491155001234") is True
        assert rule.matches("5491155001235") is True
        assert rule.matches("5491155001237") is False

    def test_whatsapp_phone_number_id_match(self):
        """Test WhatsApp phone number ID match."""
        rule = BypassRule(
            id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            rule_name="test",
            rule_type="whatsapp_phone_number_id",
            phone_number_id="123456789",
            target_agent="test_agent",
            enabled=True,
        )

        assert rule.matches("any_wa_id", "123456789") is True
        assert rule.matches("any_wa_id", "987654321") is False

    def test_no_match_with_none_inputs(self):
        """Test that None inputs don't cause errors."""
        rule = BypassRule(
            id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            rule_name="test",
            rule_type="phone_number",
            pattern="549115*",
            target_agent="test_agent",
            enabled=True,
        )

        assert rule.matches(None) is False
        assert rule.matches(None, None) is False


class TestBypassRoutingService:
    """Tests for BypassRoutingService."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def service(self, mock_db):
        """Create service with mock db."""
        return BypassRoutingService(mock_db)

    @pytest.mark.asyncio
    async def test_evaluate_bypass_rules_returns_match(self, mock_db, service):
        """Test that matching rule returns BypassMatch."""
        org_id = uuid.uuid4()

        # Create mock rule
        mock_rule = MagicMock(spec=BypassRule)
        mock_rule.matches.return_value = True
        mock_rule.rule_name = "test_rule"
        mock_rule.target_domain = "pharmacy"
        mock_rule.target_agent = "pharmacy_agent"

        # Create mock org
        mock_org = MagicMock()
        mock_org.id = org_id
        mock_org.slug = "test-org"

        # Create mock tenant config
        mock_tenant_config = MagicMock()
        mock_tenant_config.default_domain = "excelencia"

        # Setup mock query result
        mock_result = MagicMock()
        mock_result.all.return_value = [(mock_rule, mock_org, mock_tenant_config)]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.evaluate_bypass_rules("5491155001234", "123456789")

        assert result is not None
        assert isinstance(result, BypassMatch)
        assert result.organization_id == org_id
        assert result.domain == "pharmacy"
        assert result.target_agent == "pharmacy_agent"

    @pytest.mark.asyncio
    async def test_evaluate_bypass_rules_uses_tenant_default_domain(self, mock_db, service):
        """Test that tenant default domain is used when rule has no target_domain."""
        org_id = uuid.uuid4()

        mock_rule = MagicMock(spec=BypassRule)
        mock_rule.matches.return_value = True
        mock_rule.rule_name = "test_rule"
        mock_rule.target_domain = None  # No target domain
        mock_rule.target_agent = "test_agent"

        mock_org = MagicMock()
        mock_org.id = org_id
        mock_org.slug = "test-org"

        mock_tenant_config = MagicMock()
        mock_tenant_config.default_domain = "ecommerce"

        mock_result = MagicMock()
        mock_result.all.return_value = [(mock_rule, mock_org, mock_tenant_config)]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.evaluate_bypass_rules("5491155001234")

        assert result.domain == "ecommerce"

    @pytest.mark.asyncio
    async def test_evaluate_bypass_rules_uses_fallback_domain(self, mock_db, service):
        """Test that 'excelencia' is used as fallback domain."""
        org_id = uuid.uuid4()

        mock_rule = MagicMock(spec=BypassRule)
        mock_rule.matches.return_value = True
        mock_rule.rule_name = "test_rule"
        mock_rule.target_domain = None
        mock_rule.target_agent = "test_agent"

        mock_org = MagicMock()
        mock_org.id = org_id
        mock_org.slug = "test-org"

        # No tenant config
        mock_result = MagicMock()
        mock_result.all.return_value = [(mock_rule, mock_org, None)]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.evaluate_bypass_rules("5491155001234")

        assert result.domain == "excelencia"

    @pytest.mark.asyncio
    async def test_evaluate_bypass_rules_returns_none_when_no_match(self, mock_db, service):
        """Test that None is returned when no rules match."""
        mock_rule = MagicMock(spec=BypassRule)
        mock_rule.matches.return_value = False

        mock_org = MagicMock()
        mock_tenant_config = MagicMock()

        mock_result = MagicMock()
        mock_result.all.return_value = [(mock_rule, mock_org, mock_tenant_config)]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.evaluate_bypass_rules("5491155001234")

        assert result is None

    @pytest.mark.asyncio
    async def test_evaluate_bypass_rules_returns_none_when_no_rules(self, mock_db, service):
        """Test that None is returned when no rules exist."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.evaluate_bypass_rules("5491155001234")

        assert result is None

    @pytest.mark.asyncio
    async def test_evaluate_bypass_rules_handles_exception(self, mock_db, service):
        """Test that exceptions are handled gracefully."""
        mock_db.execute = AsyncMock(side_effect=Exception("Database error"))

        result = await service.evaluate_bypass_rules("5491155001234")

        assert result is None

    @pytest.mark.asyncio
    async def test_evaluate_bypass_rules_for_org(self, mock_db, service):
        """Test evaluating rules for a specific organization."""
        org_id = uuid.uuid4()

        mock_rule = MagicMock(spec=BypassRule)
        mock_rule.matches.return_value = True
        mock_rule.rule_name = "test_rule"
        mock_rule.target_domain = "pharmacy"
        mock_rule.target_agent = "pharmacy_agent"

        mock_tenant_config = MagicMock()
        mock_tenant_config.default_domain = "excelencia"

        mock_result = MagicMock()
        mock_result.all.return_value = [(mock_rule, mock_tenant_config)]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.evaluate_bypass_rules_for_org(org_id, "5491155001234")

        assert result is not None
        assert result.organization_id == org_id
        assert result.domain == "pharmacy"


class TestFactoryFunction:
    """Tests for get_bypass_routing_service factory function."""

    def test_creates_service_instance(self):
        """Test that factory function creates service instance."""
        mock_db = AsyncMock(spec=AsyncSession)

        service = get_bypass_routing_service(mock_db)

        assert isinstance(service, BypassRoutingService)
