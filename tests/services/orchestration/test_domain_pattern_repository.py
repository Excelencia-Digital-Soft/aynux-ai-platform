"""
Tests for DomainPatternRepository.

Tests pattern storage, retrieval, and dynamic configuration.
"""

import pytest

from app.services.orchestration import DomainPatternRepository


class TestDomainPatternRepository:
    """Test DomainPatternRepository."""

    @pytest.fixture
    def repo(self):
        """Create repository fixture."""
        return DomainPatternRepository()

    def test_get_all_domains(self, repo):
        """Test getting all available domains."""
        domains = repo.get_all_domains()

        assert isinstance(domains, list)
        assert len(domains) >= 3
        assert "ecommerce" in domains
        assert "hospital" in domains
        assert "credit" in domains

    def test_get_description(self, repo):
        """Test getting domain description."""
        desc = repo.get_description("ecommerce")

        assert isinstance(desc, str)
        assert len(desc) > 0
        assert "comercio" in desc.lower() or "ecommerce" in desc.lower()

    def test_get_keywords(self, repo):
        """Test getting domain keywords."""
        keywords = repo.get_keywords("ecommerce")

        assert isinstance(keywords, list)
        assert len(keywords) > 0
        assert "comprar" in keywords or "producto" in keywords

    def test_get_phrases(self, repo):
        """Test getting domain phrases."""
        phrases = repo.get_phrases("hospital")

        assert isinstance(phrases, list)
        assert len(phrases) > 0
        # At least one phrase should be medical-related
        assert any("cita" in p or "médica" in p for p in phrases)

    def test_get_indicators(self, repo):
        """Test getting domain indicators."""
        indicators = repo.get_indicators("credit")

        assert isinstance(indicators, list)
        assert len(indicators) > 0

    def test_get_pattern(self, repo):
        """Test getting complete pattern."""
        pattern = repo.get_pattern("ecommerce")

        assert isinstance(pattern, dict)
        assert "keywords" in pattern
        assert "phrases" in pattern
        assert "indicators" in pattern
        assert "description" in pattern

    def test_domain_exists(self, repo):
        """Test checking if domain exists."""
        assert repo.domain_exists("ecommerce") is True
        assert repo.domain_exists("hospital") is True
        assert repo.domain_exists("nonexistent") is False

    def test_add_domain(self, repo):
        """Test adding new domain."""
        repo.add_domain(
            domain="legal",
            description="Legal services",
            keywords=["contrato", "abogado", "legal"],
            phrases=["consulta legal", "necesito abogado"],
            indicators=["documento legal"],
        )

        assert repo.domain_exists("legal")
        assert "legal" in repo.get_all_domains()
        assert "contrato" in repo.get_keywords("legal")

    def test_update_keywords(self, repo):
        """Test updating domain keywords."""
        original_keywords = repo.get_keywords("ecommerce")
        new_keywords = ["nuevo", "keyword", "test"]

        repo.update_keywords("ecommerce", new_keywords)

        updated_keywords = repo.get_keywords("ecommerce")
        assert updated_keywords == new_keywords
        assert updated_keywords != original_keywords

    def test_get_stats(self, repo):
        """Test getting repository statistics."""
        stats = repo.get_stats()

        assert "total_domains" in stats
        assert "domains" in stats
        assert stats["total_domains"] >= 3

        # Check ecommerce stats
        ecommerce_stats = stats["domains"]["ecommerce"]
        assert "keywords_count" in ecommerce_stats
        assert "phrases_count" in ecommerce_stats
        assert "indicators_count" in ecommerce_stats


class TestDomainPatternRepositoryEdgeCases:
    """Test edge cases."""

    @pytest.fixture
    def repo(self):
        """Create repository fixture."""
        return DomainPatternRepository()

    def test_get_nonexistent_domain(self, repo):
        """Test getting pattern for nonexistent domain."""
        pattern = repo.get_pattern("nonexistent")

        assert isinstance(pattern, dict)
        assert len(pattern) == 0  # Empty dict for nonexistent

    def test_get_keywords_nonexistent_domain(self, repo):
        """Test getting keywords for nonexistent domain."""
        keywords = repo.get_keywords("nonexistent")

        assert isinstance(keywords, list)
        assert len(keywords) == 0

    def test_update_keywords_nonexistent_domain(self, repo):
        """Test updating keywords for nonexistent domain."""
        # Should not raise error, just do nothing
        repo.update_keywords("nonexistent", ["test"])

        # Domain still shouldn't exist
        assert not repo.domain_exists("nonexistent")
