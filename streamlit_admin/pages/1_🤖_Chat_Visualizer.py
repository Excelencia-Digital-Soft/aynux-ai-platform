"""
Chat Visualizer - Agent Flow Visualization

Interactive chat testing with real-time visualization of:
- Graph execution with highlighted active nodes
- Agent reasoning (orchestrator, supervisor analysis)
- Complete graph state at each step
- Conversation history
- Performance metrics
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.config.settings import Settings
from app.core.graph import AynuxGraph
from app.visualization.graph_visualizer import GraphVisualizer
from app.visualization.metrics_tracker import MetricsTracker
from app.visualization.reasoning_display import ReasoningDisplay
from app.visualization.state_inspector import StateInspector

# Load environment variables
load_dotenv()

# Initialize session state
from lib.session_state import init_session_state

init_session_state()


class ChatVisualizerPage:
    """Chat Visualizer Page with agent flow visualization"""

    def __init__(self):
        self.settings = Settings()
        self.graph_visualizer = GraphVisualizer()
        self.state_inspector = StateInspector()
        self.reasoning_display = ReasoningDisplay()
        self.metrics_tracker = MetricsTracker()

    @property
    def graph(self) -> AynuxGraph | None:
        """Get graph from session state (persists across reruns)."""
        return st.session_state.get("graph_instance")

    @graph.setter
    def graph(self, value: AynuxGraph | None):
        """Store graph in session state (persists across reruns)."""
        st.session_state.graph_instance = value

    def initialize_graph(self):
        """Initialize the LangGraph multi-agent system"""
        if not st.session_state.graph_initialized:
            with st.spinner("Inicializando sistema multi-agente..."):
                try:
                    enabled_agents = self.settings.ENABLED_AGENTS
                    config = {
                        "enabled_agents": enabled_agents,
                        "integrations": {
                            "postgres": {"db_url": self.settings.database_url},
                        },
                    }
                    self.graph = AynuxGraph(config)
                    self.graph.initialize(db_url=self.settings.database_url)
                    st.session_state.graph_initialized = True
                    st.success(f"✅ Grafo inicializado con {len(enabled_agents)} agentes habilitados")
                except Exception as e:
                    st.error(f"Error inicializando grafo: {e}")
                    raise

    def _get_agent_activity_info(self, agent_name: str) -> dict[str, str]:
        """Get rich visual information for an agent's activity."""
        agent_info = {
            "orchestrator": {
                "emoji": "🎯",
                "action": "Analizando intención",
                "description": "Detectando qué necesita el usuario",
                "color": "blue",
            },
            "supervisor": {
                "emoji": "👁️",
                "action": "Evaluando respuesta",
                "description": "Verificando calidad de la respuesta",
                "color": "green",
            },
            "greeting_agent": {
                "emoji": "👋",
                "action": "Generando saludo",
                "description": "Preparando respuesta de bienvenida",
                "color": "orange",
            },
            "product_agent": {
                "emoji": "🛍️",
                "action": "Buscando productos",
                "description": "Consultando catálogo",
                "color": "purple",
            },
            "data_insights_agent": {
                "emoji": "📊",
                "action": "Analizando datos",
                "description": "Generando reportes",
                "color": "cyan",
            },
            "excelencia_agent": {
                "emoji": "🏢",
                "action": "Consulta ERP",
                "description": "Accediendo a Excelencia",
                "color": "indigo",
            },
            "fallback_agent": {
                "emoji": "❓",
                "action": "Respuesta genérica",
                "description": "Respuesta de respaldo",
                "color": "gray",
            },
            "farewell_agent": {
                "emoji": "👋",
                "action": "Despedida",
                "description": "Finalizando conversación",
                "color": "orange",
            },
        }
        return agent_info.get(
            agent_name,
            {"emoji": "🤖", "action": "Procesando", "description": f"Ejecutando {agent_name}", "color": "blue"},
        )

    async def _stream_graph_execution(self, message: str, progress_container):
        """Stream graph execution with real-time updates"""
        conversation_id = f"viz_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        step_count = 0

        try:
            async for event in self.graph.astream(message, conversation_id=conversation_id):
                event_type = event.get("type")

                if event_type == "stream_event":
                    data = event.get("data", {})
                    step_count += 1
                    current_node = data.get("current_node")

                    self.metrics_tracker.record_step(node=current_node, timestamp=data.get("timestamp"))

                    st.session_state.execution_steps.append(
                        {
                            "step": step_count,
                            "node": current_node,
                            "timestamp": data.get("timestamp"),
                            "state_preview": data.get("state_preview"),
                        }
                    )

                    agent_info = self._get_agent_activity_info(current_node)
                    progress_html = f"""
                    <div style="padding: 15px; border-radius: 10px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <span style="font-size: 32px;">{agent_info['emoji']}</span>
                            <div style="flex: 1;">
                                <div style="color: white; font-weight: bold; font-size: 18px;">
                                    Paso {step_count}: {agent_info['action']}
                                </div>
                                <div style="color: rgba(255,255,255,0.9); font-size: 14px;">
                                    {agent_info['description']}
                                </div>
                            </div>
                        </div>
                    </div>
                    """
                    progress_container.markdown(progress_html, unsafe_allow_html=True)

                elif event_type == "final_result":
                    final_response = event.get("data")
                    st.session_state.current_state = final_response

                    if final_response and final_response.get("messages"):
                        last_message = final_response["messages"][-1]
                        if hasattr(last_message, "content"):
                            st.session_state.conversation_history.append(
                                {
                                    "role": "assistant",
                                    "content": last_message.content,
                                    "timestamp": datetime.now(),
                                    "agent": final_response.get("current_agent"),
                                }
                            )

                elif event_type == "error":
                    st.error(f"Error en streaming: {event.get('data', {}).get('error')}")

        except Exception as e:
            st.error(f"Error en ejecución del grafo: {e}")
            raise

    def process_message(self, message: str):
        """Process user message through the graph"""
        st.session_state.conversation_history.append(
            {"role": "user", "content": message, "timestamp": datetime.now()}
        )
        st.session_state.execution_steps = []

        status_container = st.empty()
        progress_container = st.empty()

        self.metrics_tracker.start_conversation()

        try:
            status_container.info("🔄 Procesando mensaje...")
            asyncio.run(self._stream_graph_execution(message, progress_container))

            metrics = self.metrics_tracker.get_metrics()
            execution_path = " → ".join(metrics.get("execution_path", []))
            status_container.success(
                f"✅ Procesado en {metrics.get('total_time', 0):.2f}s | Ruta: {execution_path}"
            )

        except Exception as e:
            status_container.error(f"❌ Error: {e}")
            st.exception(e)

        finally:
            self.metrics_tracker.end_conversation()
            st.session_state.metrics = self.metrics_tracker.get_metrics()

    def render(self):
        """Render the page"""
        st.title("🤖 Chat Visualizer")
        st.markdown("### Visualización en tiempo real del sistema multi-agente")

        # Status indicators
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Estado", "🟢 Activo" if st.session_state.graph_initialized else "🔴 Inactivo")
        with col2:
            st.metric("Agentes", len(self.settings.ENABLED_AGENTS) if self.settings else 0)
        with col3:
            st.metric("Mensajes", len(st.session_state.conversation_history))
        with col4:
            st.metric("Pasos", len(st.session_state.execution_steps))

        # Sidebar
        with st.sidebar:
            st.header("⚙️ Configuración")

            if not st.session_state.graph_initialized:
                if st.button("🚀 Inicializar Grafo", use_container_width=True):
                    self.initialize_graph()
            else:
                st.success("✅ Grafo inicializado")

            st.divider()
            st.subheader("🤖 Agentes Habilitados")
            for agent in self.settings.ENABLED_AGENTS:
                st.text(f"✓ {agent}")

            st.divider()
            if st.button("🗑️ Limpiar Historia", use_container_width=True):
                st.session_state.conversation_history = []
                st.session_state.execution_steps = []
                st.session_state.current_state = None
                st.session_state.metrics = {}
                st.rerun()

            st.divider()
            if st.button("💾 Exportar Sesión", use_container_width=True):
                export_data = {
                    "timestamp": datetime.now().isoformat(),
                    "conversation_history": [
                        {**msg, "timestamp": str(msg.get("timestamp", ""))}
                        for msg in st.session_state.conversation_history
                    ],
                    "execution_steps": st.session_state.execution_steps,
                    "metrics": st.session_state.metrics,
                }
                st.download_button(
                    label="⬇️ Descargar JSON",
                    data=json.dumps(export_data, indent=2, default=str),
                    file_name=f"agent_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                )

        # Input area
        st.subheader("💬 Interfaz de Conversación")
        col1, col2 = st.columns([4, 1])
        with col1:
            user_input = st.text_input(
                "Mensaje:", placeholder="Escribe tu mensaje aquí...", key="user_input", label_visibility="collapsed"
            )
        with col2:
            send_button = st.button("📤 Enviar", use_container_width=True, type="primary")

        if send_button and user_input and st.session_state.graph_initialized:
            self.process_message(user_input)

        st.divider()

        # Tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["📊 Grafo", "🧠 Razonamiento", "🔍 Estado", "💬 Conversación", "📈 Métricas"]
        )

        with tab1:
            self._render_graph_visualization()

        with tab2:
            self._render_reasoning()

        with tab3:
            self._render_state_inspector()

        with tab4:
            self._render_conversation()

        with tab5:
            self._render_metrics()

    def _render_graph_visualization(self):
        """Render graph visualization"""
        if not st.session_state.graph_initialized:
            st.info("ℹ️ Inicializa el grafo para ver la visualización")
            return

        if not st.session_state.execution_steps:
            st.info("ℹ️ Envía un mensaje para ver el flujo de ejecución")
            return

        visited_nodes = {step["node"] for step in st.session_state.execution_steps}
        current_node = st.session_state.execution_steps[-1]["node"]

        graph_viz = self.graph_visualizer.create_graph_visualization(
            enabled_agents=self.settings.ENABLED_AGENTS, current_node=current_node, visited_nodes=visited_nodes
        )
        st.graphviz_chart(graph_viz)

        st.subheader("🕐 Timeline")
        for step in st.session_state.execution_steps:
            agent_info = self._get_agent_activity_info(step["node"])
            st.markdown(f"**Paso {step['step']}:** {agent_info['emoji']} {agent_info['action']} ({step['node']})")

    def _render_reasoning(self):
        """Render agent reasoning"""
        if not st.session_state.current_state:
            st.info("ℹ️ Envía un mensaje para ver el razonamiento")
            return

        state = st.session_state.current_state

        if state.get("orchestrator_analysis"):
            with st.expander("🎯 Análisis del Orquestador", expanded=True):
                self.reasoning_display.display_orchestrator_analysis(state["orchestrator_analysis"])

        if state.get("supervisor_analysis"):
            with st.expander("👁️ Análisis del Supervisor"):
                self.reasoning_display.display_supervisor_analysis(state["supervisor_analysis"])

    def _render_state_inspector(self):
        """Render state inspector"""
        if not st.session_state.current_state:
            st.info("ℹ️ Envía un mensaje para inspeccionar el estado")
            return

        self.state_inspector.display_state(st.session_state.current_state)

    def _render_conversation(self):
        """Render conversation history"""
        if not st.session_state.conversation_history:
            st.info("ℹ️ La historia aparecerá aquí")
            return

        for msg in st.session_state.conversation_history:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                with st.chat_message("user"):
                    st.write(content)
            else:
                with st.chat_message("assistant"):
                    st.write(content)
                    st.caption(f"🤖 {msg.get('agent', 'unknown')}")

    def _render_metrics(self):
        """Render metrics"""
        if not st.session_state.metrics:
            st.info("ℹ️ Las métricas aparecerán después de procesar mensajes")
            return

        metrics = st.session_state.metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Tiempo Total (s)", f"{metrics.get('total_time', 0):.2f}")
        with col2:
            st.metric("Pasos Totales", metrics.get("total_steps", 0))
        with col3:
            st.metric("Tiempo Promedio/Paso", f"{metrics.get('avg_step_time', 0):.2f}s")

        if metrics.get("agent_visits"):
            st.subheader("📊 Visitas por Agente")
            import pandas as pd

            df = pd.DataFrame(list(metrics["agent_visits"].items()), columns=["Agente", "Visitas"])
            st.bar_chart(df.set_index("Agente"))


# Run page
page = ChatVisualizerPage()
page.render()
