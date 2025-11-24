"""
State Inspector - Displays detailed state information for debugging and analysis
"""

from typing import Any, Dict

import streamlit as st


class StateInspector:
    """Inspects and displays the complete LangGraph state"""

    def __init__(self):
        pass

    def display_state(self, state: Dict[str, Any]):
        """
        Display the complete state in an organized manner.

        Args:
            state: LangGraph state dictionary
        """
        if not state:
            st.info("No hay estado disponible")
            return

        # Create tabs for different state sections
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["📋 Resumen", "💬 Mensajes", "🎯 Intención & Routing", "📊 Datos", "⚙️ Control de Flujo"]
        )

        with tab1:
            self._display_state_summary(state)

        with tab2:
            self._display_messages(state)

        with tab3:
            self._display_intent_routing(state)

        with tab4:
            self._display_data(state)

        with tab5:
            self._display_flow_control(state)

        # Raw state viewer
        with st.expander("🔧 Estado Completo (Raw JSON)"):
            # Convert messages to serializable format
            safe_state = self._prepare_state_for_display(state)
            st.json(safe_state)

    def _display_state_summary(self, state: Dict[str, Any]):
        """Display high-level state summary"""
        st.subheader("📋 Resumen del Estado")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            current_agent = state.get("current_agent", "N/A")
            st.metric("Agente Actual", current_agent)

        with col2:
            next_agent = state.get("next_agent", "N/A")
            st.metric("Próximo Agente", next_agent)

        with col3:
            is_complete = state.get("is_complete", False)
            st.metric("Completado", "✅ Sí" if is_complete else "❌ No")

        with col4:
            error_count = state.get("error_count", 0)
            st.metric("Errores", error_count)

        # Additional info
        col1, col2, col3 = st.columns(3)

        with col1:
            business_domain = state.get("business_domain", "N/A")
            st.metric("Dominio", business_domain)

        with col2:
            conversation_id = state.get("conversation_id", "N/A")
            st.metric("ID Conversación", conversation_id)

        with col3:
            processing_time = state.get("total_processing_time_ms", 0)
            st.metric("Tiempo Total (ms)", f"{processing_time:.2f}")

        # Agent history
        agent_history = state.get("agent_history", [])
        if agent_history:
            st.markdown("#### 🛤️ Historial de Agentes")
            history_str = " → ".join(agent_history)
            st.code(history_str)

    def _display_messages(self, state: Dict[str, Any]):
        """Display conversation messages"""
        st.subheader("💬 Mensajes de la Conversación")

        messages = state.get("messages", [])

        if not messages:
            st.info("No hay mensajes disponibles")
            return

        st.write(f"**Total de mensajes:** {len(messages)}")

        for idx, msg in enumerate(messages, 1):
            with st.expander(f"Mensaje {idx}: {self._get_message_type(msg)}"):
                # Message content
                if hasattr(msg, "content"):
                    st.markdown("**Contenido:**")
                    st.write(msg.content)
                elif isinstance(msg, dict):
                    st.markdown("**Contenido:**")
                    st.write(msg.get("content", "N/A"))

                # Message metadata
                st.markdown("**Tipo:**")
                st.code(type(msg).__name__ if hasattr(msg, "__name__") else str(type(msg)))

                # Additional fields
                if hasattr(msg, "additional_kwargs"):
                    st.markdown("**Metadata Adicional:**")
                    st.json(msg.additional_kwargs)

    def _display_intent_routing(self, state: Dict[str, Any]):
        """Display intent detection and routing information"""
        st.subheader("🎯 Intención y Routing")

        # Current intent
        current_intent = state.get("current_intent")
        if current_intent:
            st.markdown("#### 🎯 Intención Actual")
            col1, col2 = st.columns(2)

            with col1:
                intent_type = current_intent.get("intent_type", "unknown")
                st.metric("Tipo", intent_type)

            with col2:
                confidence = current_intent.get("confidence", 0)
                st.metric("Confianza", f"{confidence:.2%}" if isinstance(confidence, (int, float)) else confidence)

            st.json(current_intent)

        # Routing decision
        routing_decision = state.get("routing_decision")
        if routing_decision:
            st.markdown("#### 🧭 Decisión de Routing")
            st.json(routing_decision)

        # Orchestrator analysis
        orchestrator_analysis = state.get("orchestrator_analysis")
        if orchestrator_analysis:
            st.markdown("#### 🎯 Análisis del Orquestador")
            st.json(orchestrator_analysis)

        # Supervisor analysis
        supervisor_analysis = state.get("supervisor_analysis")
        if supervisor_analysis:
            st.markdown("#### 👁️ Análisis del Supervisor")
            st.json(supervisor_analysis)

        # Intent history
        intent_history = state.get("intent_history", [])
        if intent_history:
            st.markdown("#### 📜 Historial de Intenciones")
            st.write(f"Total: {len(intent_history)}")
            for idx, intent in enumerate(intent_history, 1):
                with st.expander(f"Intención {idx}"):
                    st.json(intent)

    def _display_data(self, state: Dict[str, Any]):
        """Display retrieved data and agent responses"""
        st.subheader("📊 Datos Recuperados y Respuestas")

        # Retrieved data
        retrieved_data = state.get("retrieved_data", {})
        if retrieved_data:
            st.markdown("#### 📦 Datos Recuperados")
            st.json(retrieved_data)
        else:
            st.info("No hay datos recuperados")

        # Agent responses
        agent_responses = state.get("agent_responses", [])
        if agent_responses:
            st.markdown("#### 🤖 Respuestas de Agentes")
            st.write(f"Total: {len(agent_responses)}")
            for idx, response in enumerate(agent_responses, 1):
                with st.expander(f"Respuesta {idx}: {response.get('agent', 'unknown')}"):
                    st.json(response)
        else:
            st.info("No hay respuestas de agentes")

        # Customer context
        customer = state.get("customer")
        if customer:
            st.markdown("#### 👤 Contexto del Cliente")
            st.json(customer)

        # Conversation context
        conversation = state.get("conversation")
        if conversation:
            st.markdown("#### 💬 Contexto de Conversación")
            st.json(conversation)

    def _display_flow_control(self, state: Dict[str, Any]):
        """Display flow control and system state"""
        st.subheader("⚙️ Control de Flujo")

        col1, col2, col3 = st.columns(3)

        with col1:
            requires_human = state.get("requires_human", False)
            st.metric("Requiere Humano", "✅ Sí" if requires_human else "❌ No")

        with col2:
            is_complete = state.get("is_complete", False)
            st.metric("Completado", "✅ Sí" if is_complete else "❌ No")

        with col3:
            human_handoff = state.get("human_handoff_requested", False)
            st.metric("Handoff Solicitado", "✅ Sí" if human_handoff else "❌ No")

        # Error handling
        st.markdown("#### ⚠️ Manejo de Errores")

        col1, col2, col3 = st.columns(3)

        with col1:
            error_count = state.get("error_count", 0)
            st.metric("Contador de Errores", error_count)

        with col2:
            max_errors = state.get("max_errors", 3)
            st.metric("Máximo de Errores", max_errors)

        with col3:
            routing_attempts = state.get("routing_attempts", 0)
            st.metric("Intentos de Routing", routing_attempts)

        # Re-routing state
        st.markdown("#### 🔄 Estado de Re-routing")

        col1, col2 = st.columns(2)

        with col1:
            needs_rerouting = state.get("needs_re_routing", False)
            st.metric("Requiere Re-routing", "✅ Sí" if needs_rerouting else "❌ No")

        with col2:
            supervisor_retries = state.get("supervisor_retry_count", 0)
            st.metric("Reintentos del Supervisor", supervisor_retries)

        # Performance metrics
        st.markdown("#### 📈 Métricas de Rendimiento")

        col1, col2 = st.columns(2)

        with col1:
            processing_time = state.get("total_processing_time_ms", 0)
            st.metric("Tiempo Total (ms)", f"{processing_time:.2f}")

        with col2:
            cache_keys = state.get("cache_keys", [])
            st.metric("Claves de Cache", len(cache_keys))

        if cache_keys:
            st.markdown("**Claves de Cache:**")
            for key in cache_keys:
                st.code(key)

        # Conversation flow
        conversation_flow = state.get("conversation_flow")
        if conversation_flow:
            st.markdown("#### 🌊 Flujo de Conversación")
            st.json(conversation_flow)

    def _get_message_type(self, msg) -> str:
        """Get human-readable message type"""
        if hasattr(msg, "__class__"):
            class_name = msg.__class__.__name__
            if "Human" in class_name:
                return "👤 Usuario"
            elif "AI" in class_name or "Assistant" in class_name:
                return "🤖 Asistente"
            elif "System" in class_name:
                return "⚙️ Sistema"
            else:
                return class_name
        return "Unknown"

    def _prepare_state_for_display(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare state for JSON display by converting non-serializable objects.

        Args:
            state: Original state dictionary

        Returns:
            Safe state dictionary for JSON serialization
        """
        safe_state = {}

        for key, value in state.items():
            if key == "messages":
                # Convert messages to dictionaries
                safe_state[key] = []
                for msg in value:
                    if hasattr(msg, "content"):
                        safe_state[key].append(
                            {"type": type(msg).__name__, "content": msg.content, "id": getattr(msg, "id", None)}
                        )
                    else:
                        safe_state[key].append(str(msg))
            elif isinstance(value, (dict, list, str, int, float, bool, type(None))):
                safe_state[key] = value
            else:
                # Convert other objects to string representation
                safe_state[key] = str(value)

        return safe_state
