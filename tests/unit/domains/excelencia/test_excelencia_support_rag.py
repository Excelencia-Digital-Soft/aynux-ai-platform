"""
Unit tests for Excelencia Support RAG and Ticket functionality.

Tests:
- Query type detection for incidents and feedback
- Support ticket creation
- Ticket confirmation message generation
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.domains.excelencia.agents.nodes.handlers import (
    IntentAnalysisHandler,
    TicketHandler,
    ResponseGenerationHandler,
)


class TestExcelenciaQueryTypeDetection:
    """Tests for query type detection including incident/feedback."""

    def test_query_types_include_incident(self):
        """Verify incident query type is defined."""
        assert "incident" in IntentAnalysisHandler.QUERY_TYPES
        keywords = IntentAnalysisHandler.QUERY_TYPES["incident"]
        assert "reportar" in keywords
        assert "incidencia" in keywords
        assert "bug" in keywords

    def test_query_types_include_feedback(self):
        """Verify feedback query type is defined."""
        assert "feedback" in IntentAnalysisHandler.QUERY_TYPES
        keywords = IntentAnalysisHandler.QUERY_TYPES["feedback"]
        assert "sugerencia" in keywords
        assert "feedback" in keywords
        assert "mejorar" in keywords

    def test_all_query_types_defined(self):
        """Verify all expected query types are defined."""
        expected_types = [
            "demo", "modules", "training", "support", "products",
            "corporate", "clients", "general", "incident", "feedback"
        ]
        for qtype in expected_types:
            assert qtype in IntentAnalysisHandler.QUERY_TYPES, f"Missing query type: {qtype}"


class TestExcelenciaTicketConfirmation:
    """Tests for ticket confirmation message generation."""

    @pytest.fixture
    def ticket_handler(self):
        """Create TicketHandler instance with mocked LLM."""
        with patch("app.domains.excelencia.agents.nodes.handlers.ticket_handler.BaseExcelenciaHandler.__init__", return_value=None):
            handler = TicketHandler.__new__(TicketHandler)
            handler._llm = None
            handler.logger = patch("logging.getLogger").start()()
            return handler

    def test_incident_confirmation_message(self, ticket_handler):
        """Test incident ticket confirmation message."""
        ticket = {
            "id": "12345678-1234-1234-1234-123456789012",
            "ticket_id_short": "12345678",
            "status": "open",
            "category": "tecnico",
        }

        message = ticket_handler._generate_confirmation(ticket, "incident")

        assert "Incidencia Registrada" in message
        assert "12345678" in message
        assert "tecnico" in message
        assert "Abierto" in message

    def test_feedback_confirmation_message(self, ticket_handler):
        """Test feedback confirmation message."""
        ticket = {
            "id": "abcdefgh-1234-1234-1234-123456789012",
            "ticket_id_short": "ABCDEFGH",
            "status": "open",
        }

        message = ticket_handler._generate_confirmation(ticket, "feedback")

        assert "Gracias por tu Feedback" in message
        assert "ABCDEFGH" in message
        assert "opinion" in message.lower()

    def test_failed_ticket_message(self, ticket_handler):
        """Test message when ticket creation fails."""
        ticket = {
            "id": "error",
            "ticket_id_short": "ERROR",
            "status": "failed",
            "error": "Database connection error",
        }

        message = ticket_handler._generate_confirmation(ticket, "incident")

        assert "problema" in message.lower()
        assert "soporte tecnico" in message.lower()


class TestExcelenciaFallbackResponses:
    """Tests for fallback response messages."""

    @pytest.fixture
    def response_handler(self):
        """Create ResponseGenerationHandler instance with mocked LLM."""
        with patch("app.domains.excelencia.agents.nodes.handlers.response_handler.BaseExcelenciaHandler.__init__", return_value=None):
            handler = ResponseGenerationHandler.__new__(ResponseGenerationHandler)
            handler._llm = None
            handler.logger = patch("logging.getLogger").start()()
            return handler

    def test_support_fallback_suggests_ticket(self, response_handler):
        """Test support fallback suggests creating a ticket."""
        response = response_handler.generate_fallback("support", [], {})

        assert "quiero reportar una incidencia" in response.lower()
        assert "ticket" in response.lower()

    def test_training_fallback_message(self, response_handler):
        """Test training fallback provides alternatives."""
        response = response_handler.generate_fallback("training", [], {})

        assert "capacitacion" in response.lower()
        assert "ejecutivo" in response.lower() or "portal" in response.lower()

    def test_demo_fallback_message(self, response_handler):
        """Test demo fallback lists modules."""
        modules = {
            "ZM-001": {"name": "ZisMed", "description": "Suite medica"},
            "HC-001": {"name": "Historia Clinica", "description": "Gestion de historias"},
        }
        response = response_handler.generate_fallback("demo", [], modules)

        assert "demo" in response.lower()
        assert "zismed" in response.lower()


class TestCreateSupportTicketUseCase:
    """Tests for CreateSupportTicketUseCase."""

    @pytest.mark.asyncio
    async def test_category_inference_tecnico(self):
        """Test category inference for technical issues."""
        from app.domains.excelencia.application.use_cases.support import (
            CreateSupportTicketUseCase,
        )

        # Mock DB
        mock_db = AsyncMock()

        use_case = CreateSupportTicketUseCase(mock_db)

        # Test technical category inference
        category = use_case._infer_category(
            "El sistema no funciona, sale un error en pantalla",
            "incident",
        )
        assert category == "tecnico"

    @pytest.mark.asyncio
    async def test_category_inference_facturacion(self):
        """Test category inference for billing issues."""
        from app.domains.excelencia.application.use_cases.support import (
            CreateSupportTicketUseCase,
        )

        mock_db = AsyncMock()
        use_case = CreateSupportTicketUseCase(mock_db)

        # Use a message that clearly indicates billing without "error" keyword
        category = use_case._infer_category(
            "Necesito cancelar una factura CFDI del mes pasado",
            "incident",
        )
        assert category == "facturacion"

    @pytest.mark.asyncio
    async def test_category_inference_capacitacion(self):
        """Test category inference for training requests."""
        from app.domains.excelencia.application.use_cases.support import (
            CreateSupportTicketUseCase,
        )

        mock_db = AsyncMock()
        use_case = CreateSupportTicketUseCase(mock_db)

        category = use_case._infer_category(
            "Necesito un curso de capacitacion para el modulo de ventas",
            "question",
        )
        assert category == "capacitacion"

    @pytest.mark.asyncio
    async def test_category_inference_feedback(self):
        """Test category inference for feedback."""
        from app.domains.excelencia.application.use_cases.support import (
            CreateSupportTicketUseCase,
        )

        mock_db = AsyncMock()
        use_case = CreateSupportTicketUseCase(mock_db)

        category = use_case._infer_category(
            "Me gustaria que agregaran mas reportes",
            "feedback",
        )
        assert category == "sugerencias"
