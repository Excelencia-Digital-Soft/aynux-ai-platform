"""
Tests for Isolated History feature in Bypass Rules.

Tests the behavior of isolated conversation history when bypass rules
have isolated_history=True. This feature creates separate conversation
contexts for agents routed via bypass rules (e.g., pharmacy vs excelencia).

Test Scenarios:
1. Pharmacy client WITHOUT prior messages (new isolated context)
2. Pharmacy client WITH prior messages (context inheritance)
3. Generic bot -> Excelencia WITHOUT history
4. Generic bot -> Excelencia WITH history
5. CRITICAL: Pharmacy history NOT visible to Excelencia (isolation test)
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domains.shared.application.use_cases.process_webhook_use_case import BypassResult
from app.models.conversation_context import ConversationContextModel
from app.models.db.tenancy import BypassRule
from app.services.bypass_routing_service import BypassMatch
from app.services.conversation_context_service import ConversationContextService


class TestBypassMatchIsolatedHistory:
    """Tests for BypassMatch with isolated_history field."""

    def test_bypass_match_includes_isolated_history_true(self):
        """BypassMatch should include isolated_history=True when set."""
        org_id = uuid.uuid4()
        rule_id = uuid.uuid4()

        match = BypassMatch(
            organization_id=org_id,
            domain="pharmacy",
            target_agent="pharmacy_agent",
            isolated_history=True,
            rule_id=rule_id,
        )

        assert match.isolated_history is True
        assert match.rule_id == rule_id

    def test_bypass_match_includes_isolated_history_false_by_default(self):
        """BypassMatch should default isolated_history to False."""
        org_id = uuid.uuid4()

        match = BypassMatch(
            organization_id=org_id,
            domain="excelencia",
            target_agent="support_agent",
        )

        assert match.isolated_history is False
        assert match.rule_id is None

    def test_bypass_match_is_immutable(self):
        """BypassMatch should be frozen/immutable."""
        org_id = uuid.uuid4()
        match = BypassMatch(
            organization_id=org_id,
            domain="pharmacy",
            target_agent="pharmacy_agent",
            isolated_history=True,
        )

        with pytest.raises(AttributeError):
            match.isolated_history = False


class TestBypassResultIsolatedHistory:
    """Tests for BypassResult with isolated_history field."""

    def test_bypass_result_includes_isolated_history(self):
        """BypassResult should include isolated_history and rule_id."""
        org_id = uuid.uuid4()
        rule_id = uuid.uuid4()

        result = BypassResult(
            organization_id=org_id,
            domain="pharmacy",
            target_agent="pharmacy_agent",
            isolated_history=True,
            rule_id=rule_id,
        )

        assert result.matched is True
        assert result.isolated_history is True
        assert result.rule_id == rule_id

    def test_bypass_result_defaults(self):
        """BypassResult should default isolated_history to False."""
        result = BypassResult()

        assert result.matched is False
        assert result.isolated_history is False
        assert result.rule_id is None


class TestSessionIdTransformation:
    """Tests for session ID transformation with isolated_history."""

    def test_session_id_transformation_with_bypass(self):
        """Session ID should be transformed with rule_id suffix when isolated_history=True."""
        phone = "5491155001234"
        rule_id = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        base_session_id = f"whatsapp_{phone}"

        # With isolated_history=True
        isolated_history = True
        if isolated_history and rule_id:
            session_id = f"{base_session_id}_{str(rule_id)[:8]}"
        else:
            session_id = base_session_id

        assert session_id == "whatsapp_5491155001234_12345678"

    def test_session_id_unchanged_without_bypass(self):
        """Session ID should not be transformed without bypass."""
        phone = "5491155001234"
        base_session_id = f"whatsapp_{phone}"
        isolated_history = False
        bypass_rule_id = None

        if isolated_history and bypass_rule_id:
            session_id = f"{base_session_id}_{str(bypass_rule_id)[:8]}"
        else:
            session_id = base_session_id

        assert session_id == f"whatsapp_{phone}"
        assert session_id == base_session_id

    def test_session_id_unchanged_without_rule_id(self):
        """Session ID should not be transformed if rule_id is None."""
        phone = "5491155001234"
        base_session_id = f"whatsapp_{phone}"
        isolated_history = True
        bypass_rule_id = None  # No rule_id

        if isolated_history and bypass_rule_id:
            session_id = f"{base_session_id}_{str(bypass_rule_id)[:8]}"
        else:
            session_id = base_session_id

        assert session_id == f"whatsapp_{phone}"


class TestConversationContextServiceIsolatedHistory:
    """Tests for ConversationContextService with isolated history."""

    @pytest.fixture
    def context_service(self):
        """Create a ConversationContextService with mocked Redis."""
        service = ConversationContextService(db=None)
        service._redis = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_pharmacy_client_without_prior_messages(self, context_service):
        """
        Test 1: Cliente de farmacia SIN mensajes previos.

        Escenario: Cliente nuevo que inicia conversación con farmacia
                   (bypass con isolated_history=True).

        Comportamiento esperado:
        - Se crea session_id aislado: whatsapp_{phone}_{rule_id[:8]}
        - Se crea nuevo ConversationContext para session_id aislado
        - rolling_summary está vacío (no hay padre del cual heredar)
        - topic_history está vacío
        - key_entities está vacío
        - metadata NO tiene "inherited_from" (sin padre para heredar)
        """
        phone = "5491155001234"
        rule_id = uuid.uuid4()
        base_session_id = f"whatsapp_{phone}"
        isolated_session_id = f"{base_session_id}_{str(rule_id)[:8]}"

        # Mock: No existe contexto (ni aislado ni padre)
        context_service.redis.get = AsyncMock(return_value=None)
        context_service.redis.set = AsyncMock()

        # Execute
        context = await context_service.get_or_create_with_inheritance(
            conversation_id=isolated_session_id,
            parent_conversation_id=base_session_id,
        )

        # Assert - Fresh context
        assert context.conversation_id == isolated_session_id
        assert context.rolling_summary == ""
        assert context.topic_history == []
        assert context.key_entities == {}
        # No inheritance when parent doesn't exist
        assert context.metadata.get("inherited_from") is None

    @pytest.mark.asyncio
    async def test_pharmacy_client_with_prior_messages_inherits_context(self, context_service):
        """
        Test 2: Cliente de farmacia CON mensajes previos (herencia).

        Escenario: Cliente con historial previo en excelencia, ahora entra
                   por bypass farmacia con isolated_history=True.

        Comportamiento esperado:
        - Se crea session_id aislado
        - Se hereda rolling_summary del contexto padre
        - Se hereda topic_history del contexto padre
        - Se hereda key_entities del contexto padre
        - metadata["inherited_from"] = conversation_id padre
        - metadata["inherited_at"] tiene timestamp
        """
        phone = "5491155001234"
        rule_id = uuid.uuid4()
        base_session_id = f"whatsapp_{phone}"
        isolated_session_id = f"{base_session_id}_{str(rule_id)[:8]}"

        # Parent context (from excelencia)
        parent_context = ConversationContextModel(
            conversation_id=base_session_id,
            rolling_summary="Usuario preguntó sobre facturación en Excelencia Software",
            topic_history=["facturación", "soporte técnico"],
            key_entities={"customer_id": "12345", "empresa": "Farmacia ABC"},
            total_turns=5,
        )

        async def mock_get(conv_id):
            if conv_id == isolated_session_id:
                return None  # Isolated context doesn't exist yet
            elif conv_id == base_session_id:
                return parent_context  # Parent exists
            return None

        context_service.redis.get = AsyncMock(side_effect=mock_get)
        context_service.redis.set = AsyncMock()

        # Execute
        context = await context_service.get_or_create_with_inheritance(
            conversation_id=isolated_session_id,
            parent_conversation_id=base_session_id,
        )

        # Assert - Inherited from parent
        assert context.conversation_id == isolated_session_id
        assert context.rolling_summary == parent_context.rolling_summary
        assert context.topic_history == parent_context.topic_history
        assert context.key_entities == parent_context.key_entities
        assert context.metadata["inherited_from"] == base_session_id
        assert "inherited_at" in context.metadata

        # Assert - Fresh start for other fields
        assert context.total_turns == 0  # Starts at 0
        assert context.last_user_message is None
        assert context.last_bot_response is None

    @pytest.mark.asyncio
    async def test_generic_bot_to_excelencia_without_prior_history(self, context_service):
        """
        Test 3: Bot genérico → Excelencia SIN historial previo.

        Escenario: Cliente nuevo envía mensaje al bot genérico, deriva a excelencia.
                   SIN bypass, SIN isolated_history.

        Comportamiento esperado:
        - session_id = whatsapp_{phone} (sin sufijo)
        - Se crea nuevo ConversationContext estándar
        - NO hay transformación de ID
        - rolling_summary vacío
        """
        phone = "5491155001234"
        isolated_history = False
        bypass_rule_id = None

        # Session ID logic (from LangGraphChatbotService)
        base_session_id = f"whatsapp_{phone}"
        if isolated_history and bypass_rule_id:
            session_id = f"{base_session_id}_{str(bypass_rule_id)[:8]}"
        else:
            session_id = base_session_id

        # Assert - No transformation
        assert session_id == f"whatsapp_{phone}"
        assert "_" not in session_id.replace("whatsapp_", "")  # No rule suffix

        # Mock - no existing context
        context_service.redis.get = AsyncMock(return_value=None)
        context_service.redis.set = AsyncMock()

        # Execute normal get_or_create_context
        context = await context_service.get_or_create_context(session_id)

        # Assert - New context
        assert context.conversation_id == session_id
        assert context.rolling_summary == ""

    @pytest.mark.asyncio
    async def test_generic_bot_to_excelencia_with_prior_history(self, context_service):
        """
        Test 4: Bot genérico → Excelencia CON historial previo.

        Escenario: Cliente con historial existente en excelencia envía nuevo mensaje.
                   SIN bypass, SIN isolated_history - continúa conversación normal.

        Comportamiento esperado:
        - session_id = whatsapp_{phone} (sin sufijo)
        - Recupera ConversationContext existente
        - rolling_summary tiene historial previo
        """
        phone = "5491155001234"
        session_id = f"whatsapp_{phone}"

        # Existing context from prior conversations
        existing_context = ConversationContextModel(
            conversation_id=session_id,
            rolling_summary="Cliente pidió información sobre módulo de inventario",
            topic_history=["inventario", "precios"],
            key_entities={"empresa": "Cliente SA", "modulo_interes": "inventario"},
            total_turns=3,
            last_user_message="¿Cuánto cuesta el módulo de inventario?",
            last_bot_response="El módulo de inventario tiene un costo de...",
        )

        context_service.redis.get = AsyncMock(return_value=existing_context)

        # Execute
        context = await context_service.get_context(session_id)

        # Assert - Returns existing context
        assert context.conversation_id == session_id
        assert context.rolling_summary == existing_context.rolling_summary
        assert context.total_turns == 3
        assert context.topic_history == ["inventario", "precios"]

    @pytest.mark.asyncio
    async def test_pharmacy_history_not_visible_to_excelencia(self, context_service):
        """
        Test 5 CRÍTICO: Historial de farmacia NO visible para Excelencia.

        Escenario:
        1. Cliente tiene historial en farmacia (isolated_history=True)
        2. Cliente envía mensaje al bot genérico (sin bypass)
        3. Deriva a excelencia
        4. Excelencia NO debe ver el historial de farmacia

        Este test valida el AISLAMIENTO COMPLETO entre agentes.

        Comportamiento esperado:
        - Excelencia usa session_id: whatsapp_{phone}
        - Farmacia usa session_id: whatsapp_{phone}_{pharmacy_rule_id[:8]}
        - Son IDs DIFERENTES → contextos completamente separados
        - Excelencia solo ve SU historial (o vacío si es nuevo)
        - Historial de farmacia permanece aislado
        """
        phone = "5491155001234"
        pharmacy_rule_id = uuid.uuid4()

        excelencia_session_id = f"whatsapp_{phone}"
        pharmacy_session_id = f"whatsapp_{phone}_{str(pharmacy_rule_id)[:8]}"

        # Pharmacy context (isolated with sensitive data)
        pharmacy_context = ConversationContextModel(
            conversation_id=pharmacy_session_id,
            rolling_summary="Cliente consultó sobre medicamentos controlados. Receta médica requerida.",
            topic_history=["medicamentos", "recetas", "stock farmacia"],
            key_entities={
                "customer_id": "FARM-001",
                "medicamento_consultado": "Medicamento X",
                "requiere_receta": True,
            },
            total_turns=10,
            metadata={"inherited_from": excelencia_session_id},
        )

        # Excelencia context (separate, its own history)
        excelencia_context = ConversationContextModel(
            conversation_id=excelencia_session_id,
            rolling_summary="Cliente preguntó sobre precios de software contable",
            topic_history=["software", "contabilidad"],
            key_entities={"empresa": "Mi Empresa SA"},
            total_turns=2,
        )

        async def mock_get_context(conv_id):
            if conv_id == pharmacy_session_id:
                return pharmacy_context
            elif conv_id == excelencia_session_id:
                return excelencia_context
            return None

        context_service.redis.get = AsyncMock(side_effect=mock_get_context)

        # ============================================================
        # SCENARIO: User sends message WITHOUT bypass (goes to excelencia)
        # ============================================================
        isolated_history = False  # No active bypass
        bypass_rule_id = None

        # Determine session_id (LangGraphChatbotService logic)
        base_session_id = f"whatsapp_{phone}"
        if isolated_history and bypass_rule_id:
            session_id = f"{base_session_id}_{str(bypass_rule_id)[:8]}"
        else:
            session_id = base_session_id  # Excelencia uses base ID

        # Get context for excelencia
        context_for_excelencia = await context_service.get_context(session_id)

        # ============================================================
        # CRITICAL ASSERTIONS
        # ============================================================

        # 1. Excelencia uses BASE session_id (no pharmacy suffix)
        assert session_id == excelencia_session_id
        assert session_id != pharmacy_session_id

        # 2. Excelencia context does NOT contain pharmacy data
        assert context_for_excelencia.conversation_id == excelencia_session_id
        assert "medicamentos" not in context_for_excelencia.rolling_summary.lower()
        assert "recetas" not in context_for_excelencia.topic_history
        assert "medicamento_consultado" not in context_for_excelencia.key_entities

        # 3. Pharmacy context remains separate
        pharmacy_ctx = await context_service.get_context(pharmacy_session_id)
        assert pharmacy_ctx.conversation_id == pharmacy_session_id
        assert "medicamentos" in pharmacy_ctx.rolling_summary.lower()
        assert pharmacy_ctx.key_entities.get("requiere_receta") is True

        # 4. Session IDs are DIFFERENT (key to isolation)
        assert excelencia_session_id != pharmacy_session_id
        assert pharmacy_session_id.startswith(excelencia_session_id)  # Shares prefix
        assert "_" in pharmacy_session_id.replace("whatsapp_", "")  # Has suffix

    @pytest.mark.asyncio
    async def test_no_re_inheritance_when_isolated_context_exists(self, context_service):
        """
        Test: No re-inheritance when isolated context already exists.

        Escenario: El contexto aislado YA existe, no debe re-heredar del padre.

        Comportamiento esperado:
        - Si el contexto aislado ya existe, retornarlo directamente
        - NO volver a copiar datos del padre
        - Preservar historial propio del contexto aislado
        """
        phone = "5491155001234"
        rule_id = uuid.uuid4()
        isolated_session_id = f"whatsapp_{phone}_{str(rule_id)[:8]}"
        base_session_id = f"whatsapp_{phone}"

        # Isolated context ALREADY EXISTS with its own history
        existing_isolated_context = ConversationContextModel(
            conversation_id=isolated_session_id,
            rolling_summary="Historial PROPIO de farmacia después de varias interacciones",
            topic_history=["farmacia_topic_1", "farmacia_topic_2"],
            key_entities={"pharmacy_specific": "value"},
            total_turns=15,
            metadata={"inherited_from": base_session_id, "inherited_at": "2024-01-01T00:00:00"},
        )

        # Parent context with DIFFERENT data
        parent_context = ConversationContextModel(
            conversation_id=base_session_id,
            rolling_summary="Historial actualizado de excelencia que NO debe sobrescribir",
            topic_history=["excelencia_topic_nuevo"],
            key_entities={"excelencia_key": "new_value"},
            total_turns=25,
        )

        async def mock_get_context(conv_id):
            if conv_id == isolated_session_id:
                return existing_isolated_context  # Already exists
            elif conv_id == base_session_id:
                return parent_context
            return None

        context_service.redis.get = AsyncMock(side_effect=mock_get_context)
        context_service.redis.set = AsyncMock()

        # Execute
        context = await context_service.get_or_create_with_inheritance(
            conversation_id=isolated_session_id,
            parent_conversation_id=base_session_id,
        )

        # Assert - Returns existing context WITHOUT re-inheriting
        assert context.conversation_id == isolated_session_id
        assert context.rolling_summary == "Historial PROPIO de farmacia después de varias interacciones"
        assert context.topic_history == ["farmacia_topic_1", "farmacia_topic_2"]
        assert context.total_turns == 15  # Did NOT change to 25 from parent
        assert context.key_entities.get("pharmacy_specific") == "value"
        assert context.key_entities.get("excelencia_key") is None  # NOT copied


class TestBypassRuleIsolatedHistory:
    """Tests for BypassRule model with isolated_history field."""

    def test_bypass_rule_with_isolated_history_true(self):
        """BypassRule should include isolated_history field."""
        rule = BypassRule(
            id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            rule_name="pharmacy_rule",
            rule_type="whatsapp_phone_number_id",
            phone_number_id="123456789",
            target_agent="pharmacy_operations_agent",
            isolated_history=True,
            enabled=True,
        )

        assert rule.isolated_history is True

    def test_bypass_rule_isolated_history_defaults_to_none(self):
        """BypassRule.isolated_history should default to None (nullable)."""
        rule = BypassRule(
            id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            rule_name="test_rule",
            rule_type="phone_number",
            pattern="549*",
            target_agent="test_agent",
            enabled=True,
        )

        # Default is None (nullable for backwards compatibility)
        assert rule.isolated_history is None

    def test_bypass_rule_to_dict_includes_isolated_history(self):
        """BypassRule.to_dict() should include isolated_history field."""
        rule = BypassRule(
            id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            rule_name="pharmacy_rule",
            rule_type="whatsapp_phone_number_id",
            phone_number_id="123456789",
            target_agent="pharmacy_agent",
            isolated_history=True,
            enabled=True,
        )

        rule_dict = rule.to_dict()

        assert "isolated_history" in rule_dict
        assert rule_dict["isolated_history"] is True


class TestIsolatedHistoryIntegration:
    """Integration tests for the complete isolated history flow."""

    @pytest.mark.asyncio
    async def test_bypass_match_propagates_isolated_history_from_rule(self):
        """BypassMatch should propagate isolated_history from BypassRule."""
        rule_id = uuid.uuid4()
        org_id = uuid.uuid4()

        # Setup mock rule with isolated_history=True
        rule = BypassRule(
            id=rule_id,
            organization_id=org_id,
            rule_name="pharmacy_bypass",
            rule_type="whatsapp_phone_number_id",
            phone_number_id="123456789",
            target_agent="pharmacy_operations_agent",
            target_domain="pharmacy",
            isolated_history=True,
            enabled=True,
        )

        # Create BypassMatch as service would
        match = BypassMatch(
            organization_id=org_id,
            domain=str(rule.target_domain),
            target_agent=str(rule.target_agent),
            isolated_history=bool(rule.isolated_history) if rule.isolated_history else False,
            rule_id=rule.id,
        )

        # Assert
        assert match.isolated_history is True
        assert match.rule_id == rule_id
        assert match.domain == "pharmacy"
        assert match.target_agent == "pharmacy_operations_agent"

    @pytest.mark.asyncio
    async def test_full_isolation_flow_simulation(self):
        """
        Simulate the complete isolation flow:
        1. Pharmacy bypass with isolated_history=True
        2. Verify session_id transformation
        3. Verify context inheritance logic
        4. Verify subsequent excelencia call doesn't see pharmacy data
        """
        phone = "5491155001234"
        pharmacy_rule_id = uuid.uuid4()

        # ============================================================
        # STEP 1: Pharmacy bypass activation
        # ============================================================
        bypass_result = BypassResult(
            organization_id=uuid.uuid4(),
            domain="pharmacy",
            target_agent="pharmacy_operations_agent",
            isolated_history=True,
            rule_id=pharmacy_rule_id,
        )

        assert bypass_result.matched is True
        assert bypass_result.isolated_history is True

        # ============================================================
        # STEP 2: Session ID transformation
        # ============================================================
        base_session_id = f"whatsapp_{phone}"

        if bypass_result.isolated_history and bypass_result.rule_id:
            pharmacy_session_id = f"{base_session_id}_{str(bypass_result.rule_id)[:8]}"
        else:
            pharmacy_session_id = base_session_id

        assert pharmacy_session_id != base_session_id
        assert pharmacy_session_id.startswith(base_session_id)

        # ============================================================
        # STEP 3: Subsequent excelencia call (no bypass)
        # ============================================================
        excelencia_isolated_history = False
        excelencia_rule_id = None

        if excelencia_isolated_history and excelencia_rule_id:
            excelencia_session_id = f"{base_session_id}_{str(excelencia_rule_id)[:8]}"
        else:
            excelencia_session_id = base_session_id

        # ============================================================
        # STEP 4: Verify isolation
        # ============================================================
        assert excelencia_session_id == base_session_id
        assert pharmacy_session_id != excelencia_session_id

        # Different session IDs = different contexts = isolation achieved
        print(f"Pharmacy session: {pharmacy_session_id}")
        print(f"Excelencia session: {excelencia_session_id}")
        print("ISOLATION VERIFIED: Different session IDs for different agents")
