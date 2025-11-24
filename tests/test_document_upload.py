"""
Tests for Document Upload Use Cases

Tests PDF upload, text upload, and agent configuration use cases.
"""

import pytest
from pathlib import Path

# Skip all tests if PyPDF is not installed
pytest.importorskip("pypdf")


class TestPDFExtractor:
    """Tests for PDF text extraction service."""

    def test_pdf_extractor_initialization(self):
        """Test PDF extractor can be initialized."""
        from app.integrations.document_processing import PDFExtractor

        extractor = PDFExtractor()
        assert extractor is not None

    def test_validate_pdf_invalid(self):
        """Test PDF validation with invalid data."""
        from app.integrations.document_processing import PDFExtractor

        extractor = PDFExtractor()
        invalid_bytes = b"not a pdf file"
        assert not extractor.validate_pdf(invalid_bytes)


class TestUploadTextUseCase:
    """Tests for text upload use case."""

    @pytest.mark.asyncio
    async def test_text_validation_too_short(self):
        """Test text upload fails with content too short."""
        from app.domains.shared.application.use_cases import UploadTextUseCase

        # Mock database session
        class MockDB:
            pass

        use_case = UploadTextUseCase(db=MockDB())

        with pytest.raises(ValueError, match="Content must be at least 50 characters"):
            await use_case.execute(
                content="Too short",
                title="Test",
                document_type="general",
            )

    @pytest.mark.asyncio
    async def test_text_validation_title_too_short(self):
        """Test text upload fails with title too short."""
        from app.domains.shared.application.use_cases import UploadTextUseCase

        # Mock database session
        class MockDB:
            pass

        use_case = UploadTextUseCase(db=MockDB())

        with pytest.raises(ValueError, match="Title must be at least 3 characters"):
            await use_case.execute(
                content="This is a long enough content for the validation to pass" * 10,
                title="AB",
                document_type="general",
            )


class TestAgentConfigUseCase:
    """Tests for agent configuration use cases."""

    @pytest.mark.asyncio
    async def test_get_agent_config(self):
        """Test getting agent configuration."""
        from app.domains.shared.application.use_cases import GetAgentConfigUseCase

        use_case = GetAgentConfigUseCase()
        config = await use_case.execute()

        # Verify config structure
        assert "modules" in config
        assert "query_types" in config
        assert "settings" in config
        assert "available_document_types" in config

        # Verify modules exist
        assert len(config["modules"]) > 0

        # Verify settings exist
        assert "model" in config["settings"]
        assert "temperature" in config["settings"]
        assert "use_rag" in config["settings"]

    @pytest.mark.asyncio
    async def test_update_agent_settings_validation(self):
        """Test agent settings validation."""
        from app.domains.shared.application.use_cases import UpdateAgentSettingsUseCase

        use_case = UpdateAgentSettingsUseCase()

        # Valid settings should pass
        result = await use_case.execute(settings={
            "temperature": 0.7,
            "max_response_length": 500,
        })
        assert result["success"] is True

        # Invalid temperature should fail
        with pytest.raises(ValueError, match="Temperature must be between"):
            await use_case.execute(settings={"temperature": 1.5})

        # Invalid max_response_length should fail
        with pytest.raises(ValueError, match="Max response length must be between"):
            await use_case.execute(settings={"max_response_length": 50})


class TestDependencyContainer:
    """Tests for dependency container factory methods."""

    def test_create_upload_pdf_use_case(self):
        """Test creating UploadPDFUseCase via container."""
        from app.core.container import DependencyContainer

        # Mock database session
        class MockDB:
            pass

        container = DependencyContainer()
        use_case = container.create_upload_pdf_use_case(MockDB())

        assert use_case is not None
        assert use_case.__class__.__name__ == "UploadPDFUseCase"

    def test_create_upload_text_use_case(self):
        """Test creating UploadTextUseCase via container."""
        from app.core.container import DependencyContainer

        # Mock database session
        class MockDB:
            pass

        container = DependencyContainer()
        use_case = container.create_upload_text_use_case(MockDB())

        assert use_case is not None
        assert use_case.__class__.__name__ == "UploadTextUseCase"

    def test_create_agent_config_use_cases(self):
        """Test creating agent config use cases via container."""
        from app.core.container import DependencyContainer

        container = DependencyContainer()

        # Get agent config use case
        get_use_case = container.create_get_agent_config_use_case()
        assert get_use_case is not None

        # Update modules use case
        update_modules_uc = container.create_update_agent_modules_use_case()
        assert update_modules_uc is not None

        # Update settings use case
        update_settings_uc = container.create_update_agent_settings_use_case()
        assert update_settings_uc is not None


def test_imports():
    """Test that all new modules can be imported."""
    # Document processing
    from app.integrations.document_processing import PDFExtractor

    # Use cases
    from app.domains.shared.application.use_cases import (
        UploadPDFUseCase,
        UploadTextUseCase,
        BatchUploadDocumentsUseCase,
        GetAgentConfigUseCase,
        UpdateAgentModulesUseCase,
        UpdateAgentSettingsUseCase,
    )

    # All imports successful
    assert True
