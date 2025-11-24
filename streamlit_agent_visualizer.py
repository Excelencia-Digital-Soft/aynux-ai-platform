"""
Streamlit Agent Visualizer - Visualización interactiva del sistema multi-agente

Esta aplicación permite visualizar en tiempo real:
- Grafo de ejecución con nodos activos resaltados
- Razonamiento interno de cada agente (análisis del orquestador, supervisor)
- Estado completo del grafo en cada paso
- Historia de conversación
- Métricas de rendimiento

Ejecutar con: streamlit run streamlit_agent_visualizer.py
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.agents.graph import AynuxGraph
from app.config.settings import Settings
from app.visualization.graph_visualizer import GraphVisualizer
from app.visualization.metrics_tracker import MetricsTracker
from app.visualization.reasoning_display import ReasoningDisplay
from app.visualization.state_inspector import StateInspector

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Aynux Agent Visualizer",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


class AgentVisualizerApp:
    """Main application class for agent visualization"""

    def __init__(self):
        self.settings = Settings()
        self.graph: Optional[AynuxGraph] = None
        self.graph_visualizer = GraphVisualizer()
        self.state_inspector = StateInspector()
        self.reasoning_display = ReasoningDisplay()
        self.metrics_tracker = MetricsTracker()

    def initialize_session_state(self):
        """Initialize Streamlit session state"""
        if "conversation_history" not in st.session_state:
            st.session_state.conversation_history = []

        if "execution_steps" not in st.session_state:
            st.session_state.execution_steps = []

        if "current_state" not in st.session_state:
            st.session_state.current_state = None

        if "metrics" not in st.session_state:
            st.session_state.metrics = {}

        if "graph_initialized" not in st.session_state:
            st.session_state.graph_initialized = False

    def initialize_graph(self):
        """Initialize the LangGraph multi-agent system"""
        if not st.session_state.graph_initialized:
            with st.spinner("Inicializando sistema multi-agente..."):
                try:
                    # Get enabled agents from settings
                    enabled_agents = self.settings.enabled_agents

                    # Create graph configuration
                    config = {
                        "enabled_agents": enabled_agents,
                        "integrations": {
                            "ollama": {"api_url": self.settings.ollama_api_url, "model": self.settings.ollama_api_model},
                            "chromadb": {
                                "persist_directory": self.settings.chroma_persist_directory,
                                "collection_name": self.settings.chroma_collection_name,
                            },
                            "postgres": {"db_url": self.settings.database_url},
                        },
                    }

                    # Create and initialize graph
                    self.graph = AynuxGraph(config)
                    self.graph.initialize(db_url=self.settings.database_url)

                    st.session_state.graph_initialized = True
                    st.success(f"✅ Grafo inicializado con {len(enabled_agents)} agentes habilitados")

                except Exception as e:
                    st.error(f"Error inicializando grafo: {e}")
                    raise

    def render_header(self):
        """Render application header"""
        st.title("🤖 Aynux Agent Visualizer")
        st.markdown("### Visualización en tiempo real del sistema multi-agente LangGraph")

        # Status indicators
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Estado", "🟢 Activo" if st.session_state.graph_initialized else "🔴 Inactivo")

        with col2:
            agent_count = len(self.settings.enabled_agents) if self.settings else 0
            st.metric("Agentes Habilitados", agent_count)

        with col3:
            conv_count = len(st.session_state.conversation_history)
            st.metric("Mensajes", conv_count)

        with col4:
            step_count = len(st.session_state.execution_steps)
            st.metric("Pasos de Ejecución", step_count)

    def render_sidebar(self):
        """Render sidebar with controls and information"""
        st.sidebar.header("⚙️ Configuración")

        # Graph initialization
        if not st.session_state.graph_initialized:
            if st.sidebar.button("🚀 Inicializar Grafo", use_container_width=True):
                self.initialize_graph()
        else:
            st.sidebar.success("✅ Grafo inicializado")

        st.sidebar.divider()

        # Agent configuration
        st.sidebar.subheader("🤖 Agentes Habilitados")
        if self.settings:
            for agent in self.settings.enabled_agents:
                st.sidebar.text(f"✓ {agent}")

        st.sidebar.divider()

        # Clear history
        if st.sidebar.button("🗑️ Limpiar Historia", use_container_width=True):
            st.session_state.conversation_history = []
            st.session_state.execution_steps = []
            st.session_state.current_state = None
            st.session_state.metrics = {}
            st.rerun()

        # Export data
        st.sidebar.divider()
        st.sidebar.subheader("📥 Exportar Datos")

        if st.sidebar.button("💾 Exportar Sesión (JSON)", use_container_width=True):
            export_data = {
                "timestamp": datetime.now().isoformat(),
                "conversation_history": st.session_state.conversation_history,
                "execution_steps": st.session_state.execution_steps,
                "metrics": st.session_state.metrics,
            }
            st.sidebar.download_button(
                label="⬇️ Descargar",
                data=json.dumps(export_data, indent=2),
                file_name=f"agent_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
            )

    def render_main_content(self):
        """Render main content area"""
        # Input area
        st.subheader("💬 Interfaz de Conversación")

        col1, col2 = st.columns([4, 1])

        with col1:
            user_input = st.text_input(
                "Mensaje:",
                placeholder="Escribe tu mensaje aquí...",
                key="user_input",
                label_visibility="collapsed",
            )

        with col2:
            send_button = st.button("📤 Enviar", use_container_width=True, type="primary")

        # Process message
        if send_button and user_input and st.session_state.graph_initialized:
            self.process_message(user_input)

        st.divider()

        # Create tabs for different visualizations
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["📊 Grafo de Ejecución", "🧠 Razonamiento", "🔍 Estado Detallado", "💬 Conversación", "📈 Métricas"]
        )

        with tab1:
            self.render_graph_visualization()

        with tab2:
            self.render_reasoning_display()

        with tab3:
            self.render_state_inspector()

        with tab4:
            self.render_conversation_history()

        with tab5:
            self.render_metrics()

    def process_message(self, message: str):
        """Process user message through the graph with real-time visualization"""
        # Add user message to history
        st.session_state.conversation_history.append({"role": "user", "content": message, "timestamp": datetime.now()})

        # Clear previous execution steps
        st.session_state.execution_steps = []

        # Create containers for real-time updates
        status_container = st.empty()
        progress_container = st.empty()

        # Start metrics tracking
        self.metrics_tracker.start_conversation()

        try:
            # Process message with streaming
            status_container.markdown("""
                <div style="
                    padding: 15px;
                    border-radius: 10px;
                    background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
                    color: white;
                    text-align: center;
                    font-weight: bold;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                ">
                    🔄 Procesando mensaje...
                </div>
            """, unsafe_allow_html=True)

            # Run async streaming
            asyncio.run(self._stream_graph_execution(message, progress_container))

            # Show completion summary
            metrics = self.metrics_tracker.get_metrics()
            execution_path = " → ".join(metrics.get('execution_path', []))

            status_container.markdown(f"""
                <div style="
                    padding: 20px;
                    border-radius: 10px;
                    background: linear-gradient(135deg, #2ecc71 0%, #27ae60 100%);
                    color: white;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                ">
                    <div style="display: flex; align-items: center; gap: 15px;">
                        <div style="font-size: 40px;">✅</div>
                        <div style="flex: 1;">
                            <div style="font-size: 20px; font-weight: bold; margin-bottom: 8px;">
                                Mensaje procesado exitosamente
                            </div>
                            <div style="font-size: 14px; opacity: 0.9;">
                                📊 {metrics.get('total_steps', 0)} pasos ejecutados en {metrics.get('total_time', 0):.2f}s
                            </div>
                            <div style="
                                font-size: 12px;
                                margin-top: 8px;
                                padding: 8px;
                                background: rgba(255,255,255,0.2);
                                border-radius: 5px;
                            ">
                                🛤️ Ruta: {execution_path}
                            </div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        except Exception as e:
            status_container.markdown(f"""
                <div style="
                    padding: 20px;
                    border-radius: 10px;
                    background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
                    color: white;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                ">
                    <div style="display: flex; align-items: center; gap: 15px;">
                        <div style="font-size: 40px;">❌</div>
                        <div style="flex: 1;">
                            <div style="font-size: 20px; font-weight: bold; margin-bottom: 8px;">
                                Error en el procesamiento
                            </div>
                            <div style="font-size: 14px; opacity: 0.9;">
                                {str(e)}
                            </div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            st.exception(e)

        finally:
            # Stop metrics tracking
            self.metrics_tracker.end_conversation()
            st.session_state.metrics = self.metrics_tracker.get_metrics()

    def _get_agent_activity_info(self, agent_name: str) -> Dict[str, str]:
        """
        Get rich visual information for an agent's activity.

        Returns dict with emoji, action, and description.
        """
        agent_info = {
            "orchestrator": {
                "emoji": "🎯",
                "action": "Analizando intención",
                "description": "Detectando qué necesita el usuario y decidiendo qué agente debe responder",
                "color": "blue"
            },
            "supervisor": {
                "emoji": "👁️",
                "action": "Evaluando respuesta",
                "description": "Verificando calidad y completitud de la respuesta generada",
                "color": "green"
            },
            "greeting_agent": {
                "emoji": "👋",
                "action": "Generando saludo",
                "description": "Preparando respuesta de bienvenida y presentación del sistema",
                "color": "orange"
            },
            "product_agent": {
                "emoji": "🛍️",
                "action": "Buscando productos",
                "description": "Consultando catálogo y generando recomendaciones de productos",
                "color": "purple"
            },
            "data_insights_agent": {
                "emoji": "📊",
                "action": "Analizando datos",
                "description": "Generando reportes y análisis de business intelligence",
                "color": "cyan"
            },
            "promotions_agent": {
                "emoji": "🎁",
                "action": "Buscando ofertas",
                "description": "Consultando promociones activas y descuentos disponibles",
                "color": "pink"
            },
            "tracking_agent": {
                "emoji": "📦",
                "action": "Rastreando pedido",
                "description": "Consultando estado y ubicación del envío",
                "color": "teal"
            },
            "support_agent": {
                "emoji": "🆘",
                "action": "Asistencia técnica",
                "description": "Proporcionando soporte y resolviendo problemas técnicos",
                "color": "red"
            },
            "invoice_agent": {
                "emoji": "💰",
                "action": "Procesando factura",
                "description": "Consultando información de facturación y pagos",
                "color": "yellow"
            },
            "excelencia_agent": {
                "emoji": "🏢",
                "action": "Consulta ERP",
                "description": "Accediendo a datos del sistema Excelencia",
                "color": "indigo"
            },
            "fallback_agent": {
                "emoji": "❓",
                "action": "Respuesta genérica",
                "description": "Proporcionando respuesta de respaldo cuando no hay coincidencia",
                "color": "gray"
            },
            "farewell_agent": {
                "emoji": "👋",
                "action": "Despedida",
                "description": "Finalizando conversación y agradeciendo al usuario",
                "color": "orange"
            }
        }

        return agent_info.get(agent_name, {
            "emoji": "🤖",
            "action": "Procesando",
            "description": f"Ejecutando {agent_name}",
            "color": "blue"
        })

    async def _stream_graph_execution(self, message: str, progress_container):
        """Stream graph execution with real-time updates and rich visual feedback"""
        conversation_id = f"viz_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        step_count = 0
        final_response = None

        try:
            async for event in self.graph.astream(message, conversation_id=conversation_id):
                event_type = event.get("type")

                if event_type == "stream_event":
                    data = event.get("data", {})
                    step_count += 1
                    current_node = data.get("current_node")

                    # Track metrics
                    self.metrics_tracker.record_step(
                        node=current_node,
                        timestamp=data.get("timestamp"),
                    )

                    # Store execution step
                    st.session_state.execution_steps.append(
                        {
                            "step": step_count,
                            "node": current_node,
                            "timestamp": data.get("timestamp"),
                            "state_preview": data.get("state_preview"),
                        }
                    )

                    # Get rich agent information
                    agent_info = self._get_agent_activity_info(current_node)

                    # Create rich progress display with animation
                    progress_html = f"""
                    <div style="
                        padding: 15px;
                        border-radius: 10px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        border-left: 5px solid #{agent_info.get('color', 'blue')};
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                        animation: pulse 2s infinite;
                    ">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <span style="font-size: 32px;">{agent_info['emoji']}</span>
                            <div style="flex: 1;">
                                <div style="color: white; font-weight: bold; font-size: 18px; margin-bottom: 5px;">
                                    Paso {step_count}: {agent_info['action']}
                                </div>
                                <div style="color: rgba(255,255,255,0.9); font-size: 14px;">
                                    {agent_info['description']}
                                </div>
                                <div style="color: rgba(255,255,255,0.7); font-size: 12px; margin-top: 5px;">
                                    🔧 Agente: <code style="background: rgba(255,255,255,0.2); padding: 2px 6px; border-radius: 3px;">{current_node}</code>
                                </div>
                            </div>
                            <div style="
                                width: 40px;
                                height: 40px;
                                border: 3px solid white;
                                border-top: 3px solid transparent;
                                border-radius: 50%;
                                animation: spin 1s linear infinite;
                            "></div>
                        </div>
                    </div>
                    <style>
                        @keyframes spin {{
                            0% {{ transform: rotate(0deg); }}
                            100% {{ transform: rotate(360deg); }}
                        }}
                        @keyframes pulse {{
                            0%, 100% {{ opacity: 1; }}
                            50% {{ opacity: 0.85; }}
                        }}
                    </style>
                    """

                    progress_container.markdown(progress_html, unsafe_allow_html=True)

                elif event_type == "final_result":
                    final_response = event.get("data")
                    st.session_state.current_state = final_response

                    # Extract assistant response
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

    def render_graph_visualization(self):
        """Render graph visualization with highlighted current node"""
        st.subheader("📊 Grafo de Ejecución")

        if not st.session_state.graph_initialized:
            st.info("ℹ️ Inicializa el grafo para ver la visualización")
            return

        if not st.session_state.execution_steps:
            st.info("ℹ️ Envía un mensaje para ver el flujo de ejecución")
            return

        # Get current and historical nodes
        current_node = None
        visited_nodes = set()

        if st.session_state.execution_steps:
            for step in st.session_state.execution_steps:
                visited_nodes.add(step["node"])
            current_node = st.session_state.execution_steps[-1]["node"]

        # Render graph
        graph_viz = self.graph_visualizer.create_graph_visualization(
            enabled_agents=self.settings.enabled_agents, current_node=current_node, visited_nodes=visited_nodes
        )

        st.graphviz_chart(graph_viz)

        # Show execution timeline with rich visualization
        st.subheader("🕐 Timeline de Ejecución")

        # Create a visual timeline
        for idx, step in enumerate(st.session_state.execution_steps):
            agent_info = self._get_agent_activity_info(step['node'])
            is_last = (idx == len(st.session_state.execution_steps) - 1)

            # Create timeline entry with visual styling
            timeline_html = f"""
            <div style="
                margin: 10px 0;
                padding: 12px;
                border-radius: 8px;
                background: {'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' if is_last else '#f8f9fa'};
                border-left: 4px solid {agent_info.get('color', 'blue')};
                box-shadow: {'0 3px 10px rgba(0,0,0,0.2)' if is_last else '0 2px 4px rgba(0,0,0,0.1)'};
            ">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="
                        font-size: 28px;
                        background: {'rgba(255,255,255,0.2)' if is_last else 'white'};
                        padding: 8px;
                        border-radius: 50%;
                        min-width: 50px;
                        min-height: 50px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    ">
                        {agent_info['emoji']}
                    </div>
                    <div style="flex: 1;">
                        <div style="
                            color: {'white' if is_last else '#333'};
                            font-weight: bold;
                            font-size: 16px;
                            margin-bottom: 4px;
                        ">
                            Paso {step['step']}: {agent_info['action']}
                        </div>
                        <div style="
                            color: {'rgba(255,255,255,0.9)' if is_last else '#666'};
                            font-size: 13px;
                        ">
                            {agent_info['description']}
                        </div>
                    </div>
                    <div style="
                        color: {'rgba(255,255,255,0.8)' if is_last else '#999'};
                        font-size: 11px;
                        text-align: right;
                    ">
                        {step.get('timestamp', '')[:19] if step.get('timestamp') else 'N/A'}
                    </div>
                </div>
            </div>
            """
            st.markdown(timeline_html, unsafe_allow_html=True)

            # Show state preview in expander
            with st.expander(f"🔍 Ver detalles del paso {step['step']}", expanded=False):
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.metric("🏷️ Agente", step['node'])
                    state_preview = step.get('state_preview', {})
                    if state_preview.get('message_count'):
                        st.metric("💬 Mensajes", state_preview['message_count'])
                with col2:
                    st.markdown("**Estado:**")
                    st.json(step.get('state_preview', {}))

    def render_reasoning_display(self):
        """Render agent reasoning and analysis"""
        st.subheader("🧠 Razonamiento del Agente")

        if not st.session_state.current_state:
            st.info("ℹ️ Envía un mensaje para ver el razonamiento del agente")
            return

        state = st.session_state.current_state

        # Display orchestrator analysis
        if state.get("orchestrator_analysis"):
            with st.expander("🎯 Análisis del Orquestador", expanded=True):
                self.reasoning_display.display_orchestrator_analysis(state["orchestrator_analysis"])

        # Display supervisor analysis
        if state.get("supervisor_analysis"):
            with st.expander("👁️ Análisis del Supervisor", expanded=True):
                self.reasoning_display.display_supervisor_analysis(state["supervisor_analysis"])

        # Display supervisor evaluation
        if state.get("supervisor_evaluation"):
            with st.expander("✅ Evaluación del Supervisor", expanded=True):
                self.reasoning_display.display_supervisor_evaluation(state["supervisor_evaluation"])

        # Display intent history
        if state.get("intent_history"):
            with st.expander("📜 Historial de Intenciones"):
                for idx, intent in enumerate(state["intent_history"]):
                    st.write(f"**Intención {idx + 1}:**")
                    st.json(intent)

    def render_state_inspector(self):
        """Render detailed state inspection"""
        st.subheader("🔍 Inspector de Estado Detallado")

        if not st.session_state.current_state:
            st.info("ℹ️ Envía un mensaje para inspeccionar el estado")
            return

        state = st.session_state.current_state

        # Display state in organized sections
        self.state_inspector.display_state(state)

    def render_conversation_history(self):
        """Render conversation history"""
        st.subheader("💬 Historia de Conversación")

        if not st.session_state.conversation_history:
            st.info("ℹ️ La historia de conversación aparecerá aquí")
            return

        for idx, msg in enumerate(st.session_state.conversation_history):
            role = msg["role"]
            content = msg["content"]
            timestamp = msg.get("timestamp", "")

            if role == "user":
                with st.chat_message("user"):
                    st.write(content)
                    st.caption(f"🕐 {timestamp}")
            else:
                with st.chat_message("assistant"):
                    st.write(content)
                    agent = msg.get("agent", "unknown")
                    st.caption(f"🤖 {agent} • 🕐 {timestamp}")

    def render_metrics(self):
        """Render performance metrics"""
        st.subheader("📈 Métricas de Rendimiento")

        if not st.session_state.metrics:
            st.info("ℹ️ Las métricas aparecerán después de procesar mensajes")
            return

        metrics = st.session_state.metrics

        # Display metrics in columns
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Tiempo Total (s)", f"{metrics.get('total_time', 0):.2f}")

        with col2:
            st.metric("Pasos Totales", metrics.get("total_steps", 0))

        with col3:
            avg_time = metrics.get("avg_step_time", 0)
            st.metric("Tiempo Promedio/Paso (s)", f"{avg_time:.2f}")

        # Agent visit frequency
        if metrics.get("agent_visits"):
            st.subheader("📊 Frecuencia de Visitas por Agente")
            agent_visits = metrics["agent_visits"]

            # Create bar chart data
            import pandas as pd

            df = pd.DataFrame(list(agent_visits.items()), columns=["Agente", "Visitas"])
            st.bar_chart(df.set_index("Agente"))

        # Step timeline
        if metrics.get("step_timeline"):
            st.subheader("⏱️ Timeline de Pasos")
            timeline = metrics["step_timeline"]
            for step in timeline:
                st.text(f"{step['timestamp']}: {step['node']} ({step.get('duration', 'N/A')}s)")

    def run(self):
        """Run the Streamlit application"""
        self.initialize_session_state()
        self.render_header()
        self.render_sidebar()
        self.render_main_content()


# Run application
if __name__ == "__main__":
    app = AgentVisualizerApp()
    app.run()
