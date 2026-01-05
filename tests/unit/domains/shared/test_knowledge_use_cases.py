"""
Unit tests for Knowledge Use Cases (Shared Domain).

Tests key use cases:
- CreateKnowledgeUseCase
- SearchKnowledgeUseCase
- GetKnowledgeUseCase
- UpdateKnowledgeUseCase
- DeleteKnowledgeUseCase
"""

import pytest
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock

from app.domains.shared.application.use_cases.knowledge import (
    CreateKnowledgeUseCase,
    SearchKnowledgeUseCase,
    GetKnowledgeUseCase,
    UpdateKnowledgeUseCase,
    DeleteKnowledgeUseCase,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_db_session():
    """Create a mock async database session."""
    session = AsyncMock()
    return session


@pytest.fixture
def mock_knowledge_repository():
    """Create a mock knowledge repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service."""
    service = AsyncMock()
    service.update_knowledge_embeddings = AsyncMock()
    service.search_knowledge = AsyncMock(return_value=[])
    service.delete_knowledge_embeddings = AsyncMock()
    service.get_embedding_stats = MagicMock(return_value={})
    service.embedding_model = "nomic-embed-text"
    return service


@pytest.fixture
def sample_knowledge_document():
    """Sample knowledge document."""
    doc = MagicMock()
    doc.id = uuid4()
    doc.title = "Test Document"
    doc.content = "This is test content for the knowledge base."
    doc.document_type = "faq"
    doc.category = "general"
    doc.tags = ["test", "sample"]
    doc.meta_data = {}
    doc.active = True
    doc.sort_order = 0
    doc.embedding = None
    doc.created_at = MagicMock()
    doc.created_at.isoformat.return_value = "2025-01-01T00:00:00"
    doc.updated_at = MagicMock()
    doc.updated_at.isoformat.return_value = "2025-01-01T00:00:00"
    return doc


# ============================================================================
# CreateKnowledgeUseCase Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_create_knowledge_success(
    mock_db_session,
    mock_knowledge_repository,
    mock_embedding_service,
    sample_knowledge_document,
):
    """Test successfully creating a knowledge document."""
    # Arrange
    mock_knowledge_repository.create.return_value = sample_knowledge_document

    use_case = CreateKnowledgeUseCase(
        db=mock_db_session,
        repository=mock_knowledge_repository,
        embedding_service=mock_embedding_service,
    )

    knowledge_data = {
        "title": "Test Document",
        "content": "This is test content for the knowledge base with sufficient length.",
        "document_type": "faq",
        "category": "general",
        "tags": ["test"],
    }

    # Act
    result = await use_case.execute(knowledge_data, auto_embed=True)

    # Assert
    assert result is not None
    assert result["title"] == "Test Document"
    assert result["document_type"] == "faq"

    # Verify repository and service calls
    mock_knowledge_repository.create.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_embedding_service.update_knowledge_embeddings.assert_called_once()


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_create_knowledge_missing_title(
    mock_db_session,
    mock_knowledge_repository,
):
    """Test creating knowledge without required title."""
    # Arrange
    use_case = CreateKnowledgeUseCase(
        db=mock_db_session,
        repository=mock_knowledge_repository,
    )

    knowledge_data = {
        "content": "Content without title",
        "document_type": "faq",
    }

    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        await use_case.execute(knowledge_data)

    assert "Title is required" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_create_knowledge_content_too_short(
    mock_db_session,
    mock_knowledge_repository,
):
    """Test creating knowledge with insufficient content length."""
    # Arrange
    use_case = CreateKnowledgeUseCase(
        db=mock_db_session,
        repository=mock_knowledge_repository,
    )

    knowledge_data = {
        "title": "Test",
        "content": "Too short",  # Less than 50 characters
        "document_type": "faq",
    }

    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        await use_case.execute(knowledge_data)

    assert "at least 50 characters" in str(exc_info.value)


# ============================================================================
# SearchKnowledgeUseCase Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_search_knowledge_success(
    mock_db_session,
    mock_knowledge_repository,
    mock_embedding_service,
):
    """Test successful knowledge search."""
    # Arrange
    search_results = [
        {"id": str(uuid4()), "title": "Result 1", "content": "Content 1"},
        {"id": str(uuid4()), "title": "Result 2", "content": "Content 2"},
    ]

    mock_embedding_service.search_knowledge.return_value = search_results

    use_case = SearchKnowledgeUseCase(
        db=mock_db_session,
        search_repository=mock_knowledge_repository,
        embedding_service=mock_embedding_service,
    )

    # Act
    results = await use_case.execute(
        query="test query",
        max_results=10,
        search_strategy="hybrid",
    )

    # Assert
    assert len(results) == 2
    assert results[0]["title"] == "Result 1"
    mock_embedding_service.search_knowledge.assert_called_once()


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_search_knowledge_query_too_short(
    mock_db_session,
    mock_knowledge_repository,
):
    """Test search with query too short."""
    # Arrange
    use_case = SearchKnowledgeUseCase(
        db=mock_db_session,
        search_repository=mock_knowledge_repository,
    )

    # Act
    results = await use_case.execute(query="ab")  # Only 2 characters

    # Assert
    assert results == []  # Should return empty list


# ============================================================================
# GetKnowledgeUseCase Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_knowledge_success(
    mock_db_session,
    mock_knowledge_repository,
    sample_knowledge_document,
):
    """Test successfully getting a knowledge document."""
    # Arrange
    mock_knowledge_repository.get_by_id.return_value = sample_knowledge_document

    use_case = GetKnowledgeUseCase(
        db=mock_db_session,
        repository=mock_knowledge_repository,
    )

    doc_id = sample_knowledge_document.id

    # Act
    result = await use_case.execute(doc_id)

    # Assert
    assert result is not None
    assert result["title"] == "Test Document"
    mock_knowledge_repository.get_by_id.assert_called_once_with(doc_id)


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_knowledge_not_found(
    mock_db_session,
    mock_knowledge_repository,
):
    """Test getting non-existent knowledge document."""
    # Arrange
    mock_knowledge_repository.get_by_id.return_value = None

    use_case = GetKnowledgeUseCase(
        db=mock_db_session,
        repository=mock_knowledge_repository,
    )

    doc_id = uuid4()

    # Act
    result = await use_case.execute(doc_id)

    # Assert
    assert result is None


# ============================================================================
# UpdateKnowledgeUseCase Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_update_knowledge_success(
    mock_db_session,
    mock_knowledge_repository,
    mock_embedding_service,
    sample_knowledge_document,
):
    """Test successfully updating a knowledge document."""
    # Arrange
    mock_knowledge_repository.update.return_value = sample_knowledge_document

    use_case = UpdateKnowledgeUseCase(
        db=mock_db_session,
        repository=mock_knowledge_repository,
        embedding_service=mock_embedding_service,
    )

    doc_id = sample_knowledge_document.id
    update_data = {
        "title": "Updated Title",
        "content": "Updated content for the knowledge base document.",
    }

    # Act
    result = await use_case.execute(
        knowledge_id=doc_id,
        update_data=update_data,
        regenerate_embedding=True,
    )

    # Assert
    assert result is not None
    mock_knowledge_repository.update.assert_called_once_with(doc_id, update_data)
    mock_db_session.commit.assert_called_once()
    mock_embedding_service.update_knowledge_embeddings.assert_called_once()


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_update_knowledge_not_found(
    mock_db_session,
    mock_knowledge_repository,
):
    """Test updating non-existent knowledge document."""
    # Arrange
    mock_knowledge_repository.update.return_value = None

    use_case = UpdateKnowledgeUseCase(
        db=mock_db_session,
        repository=mock_knowledge_repository,
    )

    doc_id = uuid4()
    update_data = {"title": "New Title"}

    # Act
    result = await use_case.execute(doc_id, update_data)

    # Assert
    assert result is None


# ============================================================================
# DeleteKnowledgeUseCase Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_delete_knowledge_soft_delete(
    mock_db_session,
    mock_knowledge_repository,
    sample_knowledge_document,
):
    """Test soft deleting a knowledge document."""
    # Arrange
    mock_knowledge_repository.soft_delete.return_value = sample_knowledge_document

    use_case = DeleteKnowledgeUseCase(
        db=mock_db_session,
        repository=mock_knowledge_repository,
    )

    doc_id = sample_knowledge_document.id

    # Act
    result = await use_case.execute(doc_id, soft_delete=True)

    # Assert
    assert result is True
    mock_knowledge_repository.soft_delete.assert_called_once_with(doc_id)
    mock_db_session.commit.assert_called_once()


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_delete_knowledge_hard_delete(
    mock_db_session,
    mock_knowledge_repository,
    mock_embedding_service,
):
    """Test hard deleting a knowledge document."""
    # Arrange
    mock_knowledge_repository.delete.return_value = True

    use_case = DeleteKnowledgeUseCase(
        db=mock_db_session,
        repository=mock_knowledge_repository,
        embedding_service=mock_embedding_service,
    )

    doc_id = uuid4()

    # Act
    result = await use_case.execute(doc_id, soft_delete=False)

    # Assert
    assert result is True
    mock_knowledge_repository.delete.assert_called_once_with(doc_id)
    mock_embedding_service.delete_knowledge_embeddings.assert_called_once()
    mock_db_session.commit.assert_called_once()
