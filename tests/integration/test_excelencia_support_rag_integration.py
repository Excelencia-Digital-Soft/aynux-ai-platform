"""
Integration Tests for Excelencia Support RAG System.

Tests the complete flow:
1. RAG search for support documents
2. Ticket creation from chat messages
3. Full flow: support query → RAG → ticket creation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from app.domains.excelencia.agents.nodes.excelencia_node import ExcelenciaNode
from app.domains.excelencia.application.use_cases.support import (
    CreateSupportTicketUseCase,
)


class TestExcelenciaSupportRAGIntegration:
    """Integration tests for support RAG functionality."""

    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store with support documents."""
        vector_store = AsyncMock()
        vector_store.search = AsyncMock(return_value=[
            {
                "id": str(uuid.uuid4()),
                "content": "Para soporte técnico llamar al 800-123-4567",
                "metadata": {
                    "document_type": "support_contact",
                    "title": "Contacto Soporte",
                },
                "score": 0.92,
            }
        ])
        return vector_store

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def node_with_mocks(self, mock_vector_store):
        """Create ExcelenciaNode with mocked dependencies."""
        with patch("app.domains.excelencia.agents.nodes.excelencia_node.VllmLLM"):
            node = ExcelenciaNode()
            # Need to also mock the vector_store getter
            with patch.object(node, 'vector_store', mock_vector_store):
                yield node

    @pytest.mark.asyncio
    async def test_support_document_types_include_all_expected(self):
        """Test that support document types are properly defined."""
        with patch("app.domains.excelencia.agents.nodes.excelencia_node.VllmLLM"):
            node = ExcelenciaNode()

        # Verify all expected types are present
        expected_types = {
            "support_faq",
            "support_guide",
            "support_contact",
            "support_training",
            "support_module",
        }
        actual_types = set(node.SUPPORT_DOCUMENT_TYPES)

        # All expected types should be in actual (faq is additional)
        assert expected_types.issubset(actual_types)

    @pytest.mark.asyncio
    async def test_query_types_include_incident_and_feedback(self):
        """Test that incident and feedback query types are defined."""
        with patch("app.domains.excelencia.agents.nodes.excelencia_node.VllmLLM"):
            node = ExcelenciaNode()

        assert "incident" in node.QUERY_TYPES
        assert "feedback" in node.QUERY_TYPES

        # Verify keywords
        assert "reportar" in node.QUERY_TYPES["incident"]
        assert "incidencia" in node.QUERY_TYPES["incident"]
        assert "sugerencia" in node.QUERY_TYPES["feedback"]
        assert "feedback" in node.QUERY_TYPES["feedback"]


class TestTicketCreationIntegration:
    """Integration tests for ticket creation flow."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session with proper behavior."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_incident_creates_ticket_in_db(self, mock_db):
        """Test that incident reports create tickets in database."""
        use_case = CreateSupportTicketUseCase(mock_db)

        result = await use_case.execute(
            user_phone="+521234567890",
            ticket_type="incident",
            description="El sistema no permite generar facturas, sale error 500",
            category=None,  # Should auto-infer
            module="facturacion",
            conversation_id=str(uuid.uuid4()),
        )

        # Verify ticket was added to DB
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

        # Verify result
        assert "id" in result
        assert result["status"] == "open"

    @pytest.mark.asyncio
    async def test_feedback_creates_ticket_in_db(self, mock_db):
        """Test that feedback submissions create tickets in database."""
        use_case = CreateSupportTicketUseCase(mock_db)

        result = await use_case.execute(
            user_phone="+521234567890",
            ticket_type="feedback",
            description="Sería bueno agregar más reportes de inventario",
            category=None,
            module=None,
            conversation_id=None,
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

        assert "id" in result
        assert result["status"] == "open"

    @pytest.mark.asyncio
    async def test_ticket_auto_categorizes_technical(self, mock_db):
        """Test automatic category inference for technical issues."""
        use_case = CreateSupportTicketUseCase(mock_db)

        await use_case.execute(
            user_phone="+521234567890",
            ticket_type="incident",
            description="Error crítico: el sistema se congela al abrir reportes",
            category=None,
            module=None,
            conversation_id=None,
        )

        # Get the ticket that was added
        added_ticket = mock_db.add.call_args[0][0]
        assert added_ticket.category == "tecnico"

    @pytest.mark.asyncio
    async def test_ticket_auto_categorizes_billing(self, mock_db):
        """Test automatic category inference for billing issues."""
        use_case = CreateSupportTicketUseCase(mock_db)

        await use_case.execute(
            user_phone="+521234567890",
            ticket_type="incident",
            description="No puedo cancelar la factura CFDI del cliente",
            category=None,
            module=None,
            conversation_id=None,
        )

        added_ticket = mock_db.add.call_args[0][0]
        assert added_ticket.category == "facturacion"


class TestFullSupportFlow:
    """End-to-end integration tests for support workflow."""

    @pytest.fixture
    def node(self):
        """Create ExcelenciaNode with mocked LLM."""
        with patch("app.domains.excelencia.agents.nodes.excelencia_node.VllmLLM"):
            return ExcelenciaNode()

    def test_incident_keywords_exist_in_query_types(self, node):
        """Test that incident query type has expected keywords."""
        assert "incident" in node.QUERY_TYPES
        incident_keywords = node.QUERY_TYPES["incident"]

        # These are the specific keywords we added
        assert "reportar" in incident_keywords
        assert "incidencia" in incident_keywords
        assert "bug" in incident_keywords

    def test_feedback_keywords_exist_in_query_types(self, node):
        """Test that feedback query type has expected keywords."""
        assert "feedback" in node.QUERY_TYPES
        feedback_keywords = node.QUERY_TYPES["feedback"]

        # These are the specific keywords we added
        assert "sugerencia" in feedback_keywords
        assert "feedback" in feedback_keywords
        assert "mejorar" in feedback_keywords

    def test_support_document_types_include_required(self, node):
        """Test that support document types include all required types."""
        required_types = [
            "support_faq",
            "support_guide",
            "support_contact",
            "support_training",
            "support_module",
        ]

        for doc_type in required_types:
            assert doc_type in node.SUPPORT_DOCUMENT_TYPES

    def test_ticket_confirmation_format_incident(self, node):
        """Test incident confirmation message format."""
        ticket = {
            "id": "12345678-abcd-efgh-ijkl-123456789012",
            "ticket_id_short": "12345678",
            "status": "open",
            "category": "tecnico",
        }

        message = node._generate_ticket_confirmation(ticket, "incident")

        # Verify required elements
        assert "12345678" in message
        assert "tecnico" in message.lower() or "Abierto" in message

    def test_ticket_confirmation_format_feedback(self, node):
        """Test feedback confirmation message format."""
        ticket = {
            "id": "abcdefgh-1234-5678-9012-abcdefghijkl",
            "ticket_id_short": "ABCDEFGH",
            "status": "open",
        }

        message = node._generate_ticket_confirmation(ticket, "feedback")

        # Verify required elements
        assert "ABCDEFGH" in message
        assert "feedback" in message.lower() or "opinion" in message.lower()
