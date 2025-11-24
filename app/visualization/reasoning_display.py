"""
Reasoning Display - Shows the internal reasoning and analysis of agents
"""

import streamlit as st
from typing import Any, Dict, Optional


class ReasoningDisplay:
    """Displays agent reasoning, analysis, and decision-making process"""

    def __init__(self):
        pass

    def display_orchestrator_analysis(self, analysis: Dict[str, Any]):
        """
        Display orchestrator's intent analysis and routing decision.

        Args:
            analysis: Orchestrator analysis dictionary
        """
        if not analysis:
            st.info("No hay análisis del orquestador disponible")
            return

        # Intent detection
        st.markdown("#### 🎯 Detección de Intención")

        col1, col2 = st.columns(2)

        with col1:
            intent_type = analysis.get("intent_type", "unknown")
            st.metric("Tipo de Intención", intent_type)

        with col2:
            confidence = analysis.get("confidence", 0)
            st.metric("Confianza", f"{confidence:.2%}" if isinstance(confidence, (int, float)) else confidence)

        # Routing decision
        st.markdown("#### 🧭 Decisión de Routing")

        next_agent = analysis.get("next_agent", "unknown")
        st.info(f"**Agente seleccionado:** `{next_agent}`")

        # Reasoning
        if analysis.get("reasoning"):
            st.markdown("#### 💭 Razonamiento")
            st.write(analysis["reasoning"])

        # Extracted entities
        if analysis.get("entities"):
            st.markdown("#### 🏷️ Entidades Extraídas")
            st.json(analysis["entities"])

        # Raw analysis
        with st.expander("📄 Análisis Completo (Raw)"):
            st.json(analysis)

    def display_supervisor_analysis(self, analysis: Dict[str, Any]):
        """
        Display supervisor's quality analysis and flow control decisions.

        Args:
            analysis: Supervisor analysis dictionary
        """
        if not analysis:
            st.info("No hay análisis del supervisor disponible")
            return

        # Response quality
        st.markdown("#### ✅ Evaluación de Calidad")

        col1, col2, col3 = st.columns(3)

        with col1:
            quality_score = analysis.get("quality_score", 0)
            st.metric("Puntuación de Calidad", f"{quality_score:.2f}" if isinstance(quality_score, (int, float)) else quality_score)

        with col2:
            is_complete = analysis.get("is_complete", False)
            st.metric("Completitud", "✅ Sí" if is_complete else "❌ No")

        with col3:
            needs_improvement = analysis.get("needs_improvement", False)
            st.metric("Requiere Mejora", "⚠️ Sí" if needs_improvement else "✅ No")

        # Flow control
        st.markdown("#### 🎮 Control de Flujo")

        should_continue = analysis.get("should_continue", False)
        if should_continue:
            st.warning("🔄 Se requiere re-routing para mejorar la respuesta")
        else:
            st.success("✅ Respuesta satisfactoria, finalizando conversación")

        # Supervisor feedback
        if analysis.get("feedback"):
            st.markdown("#### 💬 Feedback del Supervisor")
            st.info(analysis["feedback"])

        # Raw analysis
        with st.expander("📄 Análisis Completo (Raw)"):
            st.json(analysis)

    def display_supervisor_evaluation(self, evaluation: Dict[str, Any]):
        """
        Display supervisor's final evaluation of the response.

        Args:
            evaluation: Supervisor evaluation dictionary
        """
        if not evaluation:
            st.info("No hay evaluación del supervisor disponible")
            return

        st.markdown("#### 📋 Evaluación Final")

        # Overall assessment
        assessment = evaluation.get("assessment", "unknown")
        if assessment == "approved":
            st.success("✅ Respuesta aprobada")
        elif assessment == "needs_revision":
            st.warning("⚠️ Requiere revisión")
        else:
            st.info(f"Estado: {assessment}")

        # Evaluation criteria
        st.markdown("#### 📊 Criterios de Evaluación")

        criteria = evaluation.get("criteria", {})

        col1, col2, col3 = st.columns(3)

        with col1:
            relevance = criteria.get("relevance", "N/A")
            st.metric("Relevancia", relevance)

        with col2:
            accuracy = criteria.get("accuracy", "N/A")
            st.metric("Precisión", accuracy)

        with col3:
            completeness = criteria.get("completeness", "N/A")
            st.metric("Completitud", completeness)

        # Suggestions
        if evaluation.get("suggestions"):
            st.markdown("#### 💡 Sugerencias de Mejora")
            for idx, suggestion in enumerate(evaluation["suggestions"], 1):
                st.write(f"{idx}. {suggestion}")

        # Raw evaluation
        with st.expander("📄 Evaluación Completa (Raw)"):
            st.json(evaluation)

    def display_agent_response(self, response: Dict[str, Any]):
        """
        Display individual agent response details.

        Args:
            response: Agent response dictionary
        """
        if not response:
            st.info("No hay respuesta del agente disponible")
            return

        st.markdown("#### 🤖 Respuesta del Agente")

        # Agent information
        col1, col2 = st.columns(2)

        with col1:
            agent_name = response.get("agent", "unknown")
            st.metric("Agente", agent_name)

        with col2:
            timestamp = response.get("timestamp", "N/A")
            st.metric("Timestamp", timestamp)

        # Response content
        if response.get("content"):
            st.markdown("#### 💬 Contenido")
            st.write(response["content"])

        # Retrieved data
        if response.get("retrieved_data"):
            st.markdown("#### 📦 Datos Recuperados")
            st.json(response["retrieved_data"])

        # Confidence and metadata
        col1, col2 = st.columns(2)

        with col1:
            confidence = response.get("confidence", "N/A")
            st.metric("Confianza", confidence)

        with col2:
            processing_time = response.get("processing_time_ms", "N/A")
            st.metric("Tiempo de Procesamiento (ms)", processing_time)

        # Raw response
        with st.expander("📄 Respuesta Completa (Raw)"):
            st.json(response)

    def display_intent_history(self, intent_history: list[Dict[str, Any]]):
        """
        Display the history of intent detections throughout the conversation.

        Args:
            intent_history: List of intent detection results
        """
        if not intent_history:
            st.info("No hay historial de intenciones disponible")
            return

        st.markdown("#### 📜 Historial de Intenciones")

        for idx, intent in enumerate(intent_history, 1):
            with st.expander(f"Intención {idx}: {intent.get('intent_type', 'unknown')}"):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Tipo", intent.get("intent_type", "unknown"))

                with col2:
                    confidence = intent.get("confidence", 0)
                    st.metric("Confianza", f"{confidence:.2%}" if isinstance(confidence, (int, float)) else confidence)

                with col3:
                    agent = intent.get("routed_to", "unknown")
                    st.metric("Agente", agent)

                if intent.get("reasoning"):
                    st.write(f"**Razonamiento:** {intent['reasoning']}")

                st.json(intent)

    def display_conversation_flow(self, flow: Dict[str, Any]):
        """
        Display the conversation flow analysis.

        Args:
            flow: Conversation flow dictionary
        """
        if not flow:
            st.info("No hay análisis de flujo disponible")
            return

        st.markdown("#### 🌊 Análisis de Flujo de Conversación")

        # Flow metrics
        col1, col2, col3 = st.columns(3)

        with col1:
            turn_count = flow.get("turn_count", 0)
            st.metric("Turnos", turn_count)

        with col2:
            agent_switches = flow.get("agent_switches", 0)
            st.metric("Cambios de Agente", agent_switches)

        with col3:
            avg_response_time = flow.get("avg_response_time", 0)
            st.metric("Tiempo Promedio (s)", f"{avg_response_time:.2f}")

        # Flow path
        if flow.get("path"):
            st.markdown("#### 🛤️ Ruta de Ejecución")
            path_str = " → ".join(flow["path"])
            st.code(path_str)

        # Flow summary
        if flow.get("summary"):
            st.markdown("#### 📝 Resumen")
            st.write(flow["summary"])

        # Raw flow
        with st.expander("📄 Flujo Completo (Raw)"):
            st.json(flow)
