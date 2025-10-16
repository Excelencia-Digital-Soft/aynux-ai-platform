"""
Streamlit Monitoring Dashboard for Aynux Bot

This dashboard provides real-time monitoring, graph visualization,
and performance analytics for the chatbot system with LangSmith integration.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# Page configuration
st.set_page_config(
    page_title="Aynux Monitoring Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Custom CSS
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .success-text {
        color: #28a745;
        font-weight: bold;
    }
    .error-text {
        color: #dc3545;
        font-weight: bold;
    }
    .warning-text {
        color: #ffc107;
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_langsmith_tracer():
    """Get LangSmith tracer (cached)"""
    from app.config.langsmith_config import get_tracer
    from app.config.langsmith_init import initialize_langsmith

    initialize_langsmith(force=True)
    return get_tracer()


@st.cache_resource
def get_chat_service():
    """Get chat service (cached)"""
    from app.services.langgraph_chatbot_service import LangGraphChatbotService

    service = LangGraphChatbotService()

    # Run async initialization in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(service.initialize())

    return service


def get_langsmith_metrics(tracer, hours: int = 24) -> Dict[str, Any]:
    """Get metrics from LangSmith"""
    if not tracer or not tracer.client:
        return {}

    try:
        # Get runs from last N hours
        runs = list(
            tracer.client.list_runs(
                project_name=tracer.config.project_name,
                limit=1000,
                order="-start_time",
            )
        )

        # Filter by time
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_runs = [r for r in runs if r.start_time and r.start_time.replace(tzinfo=None) > cutoff_time]

        # Calculate metrics
        total_runs = len(recent_runs)
        successful_runs = sum(1 for r in recent_runs if not r.error)
        error_runs = total_runs - successful_runs

        # Latency statistics
        latencies = [r.latency for r in recent_runs if r.latency]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0

        # Agent usage
        agent_counts = {}
        for run in recent_runs:
            agent = run.name or "unknown"
            agent_counts[agent] = agent_counts.get(agent, 0) + 1

        # Errors by type
        error_types = {}
        for run in recent_runs:
            if run.error:
                error_type = type(run.error).__name__ if hasattr(run.error, "__class__") else "Unknown"
                error_types[error_type] = error_types.get(error_type, 0) + 1

        # Runs over time (hourly)
        runs_by_hour = {}
        for run in recent_runs:
            if run.start_time:
                hour = run.start_time.replace(minute=0, second=0, microsecond=0)
                hour_str = hour.strftime("%Y-%m-%d %H:00")
                runs_by_hour[hour_str] = runs_by_hour.get(hour_str, 0) + 1

        return {
            "total_runs": total_runs,
            "successful_runs": successful_runs,
            "error_runs": error_runs,
            "success_rate": (successful_runs / total_runs * 100) if total_runs > 0 else 0,
            "error_rate": (error_runs / total_runs * 100) if total_runs > 0 else 0,
            "avg_latency": avg_latency,
            "p95_latency": p95_latency,
            "agent_counts": agent_counts,
            "error_types": error_types,
            "runs_by_hour": runs_by_hour,
            "recent_runs": recent_runs[:50],  # Keep last 50
        }

    except Exception as e:
        st.error(f"Error fetching LangSmith metrics: {str(e)}")
        return {}


def render_header():
    """Render dashboard header"""
    st.markdown('<div class="main-header">🤖 Aynux Monitoring Dashboard</div>', unsafe_allow_html=True)
    st.markdown("---")


def render_langsmith_status(tracer):
    """Render LangSmith connection status"""
    st.sidebar.header("⚙️ Configuración")

    if tracer and tracer.config.tracing_enabled:
        st.sidebar.success("✅ LangSmith Activo")
        st.sidebar.info(f"📊 Proyecto: {tracer.config.project_name}")
        st.sidebar.markdown(
            f"[🔗 Ver en LangSmith](https://smith.langchain.com/o/default/projects/p/{tracer.config.project_name})"
        )
    else:
        st.sidebar.error("❌ LangSmith Desactivado")
        st.sidebar.warning("Configura LANGSMITH_API_KEY en .env")


def render_overview_metrics(metrics: Dict[str, Any]):
    """Render overview metrics cards"""
    st.header("📊 Métricas Generales")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total de Ejecuciones",
            value=metrics.get("total_runs", 0),
            delta=None,
        )

    with col2:
        success_rate = metrics.get("success_rate", 0)
        st.metric(
            label="Tasa de Éxito",
            value=f"{success_rate:.1f}%",
            delta=f"{success_rate - 95:.1f}%" if success_rate < 95 else None,
            delta_color="inverse" if success_rate < 95 else "normal",
        )

    with col3:
        avg_latency = metrics.get("avg_latency", 0)
        st.metric(
            label="Latencia Promedio",
            value=f"{avg_latency:.2f}s",
            delta=f"{avg_latency - 2:.2f}s" if avg_latency > 2 else None,
            delta_color="inverse" if avg_latency > 2 else "normal",
        )

    with col4:
        p95_latency = metrics.get("p95_latency", 0)
        st.metric(
            label="P95 Latencia",
            value=f"{p95_latency:.2f}s",
            delta=f"{p95_latency - 5:.2f}s" if p95_latency > 5 else None,
            delta_color="inverse" if p95_latency > 5 else "normal",
        )


def render_agent_usage_chart(metrics: Dict[str, Any]):
    """Render agent usage pie chart"""
    st.header("🤖 Uso de Agentes")

    agent_counts = metrics.get("agent_counts", {})

    if agent_counts:
        # Create pie chart
        fig = px.pie(
            values=list(agent_counts.values()),
            names=list(agent_counts.keys()),
            title="Distribución de Uso de Agentes",
            hole=0.3,
        )

        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos de agentes disponibles")


def render_performance_charts(metrics: Dict[str, Any]):
    """Render performance charts"""
    st.header("⚡ Rendimiento")

    # Runs over time
    runs_by_hour = metrics.get("runs_by_hour", {})

    if runs_by_hour:
        df = pd.DataFrame(list(runs_by_hour.items()), columns=["Hora", "Ejecuciones"])
        df = df.sort_values("Hora")

        fig = px.line(df, x="Hora", y="Ejecuciones", title="Ejecuciones por Hora", markers=True)

        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos de rendimiento disponibles")


def render_error_analysis(metrics: Dict[str, Any]):
    """Render error analysis"""
    st.header("❌ Análisis de Errores")

    error_types = metrics.get("error_types", {})
    error_runs = metrics.get("error_runs", 0)

    col1, col2 = st.columns(2)

    with col1:
        st.metric(label="Total de Errores", value=error_runs)

    with col2:
        error_rate = metrics.get("error_rate", 0)
        st.metric(
            label="Tasa de Error",
            value=f"{error_rate:.2f}%",
            delta=f"{error_rate - 5:.2f}%" if error_rate > 5 else None,
            delta_color="inverse" if error_rate > 5 else "normal",
        )

    if error_types:
        df = pd.DataFrame(list(error_types.items()), columns=["Tipo de Error", "Cantidad"])

        fig = px.bar(df, x="Tipo de Error", y="Cantidad", title="Errores por Tipo")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.success("✅ No se registraron errores en el período seleccionado")


def render_recent_runs_table(metrics: Dict[str, Any]):
    """Render recent runs table"""
    st.header("📜 Ejecuciones Recientes")

    recent_runs = metrics.get("recent_runs", [])

    if recent_runs:
        # Prepare data
        data = []
        for run in recent_runs[:20]:  # Show last 20
            data.append(
                {
                    "Nombre": run.name or "N/A",
                    "Estado": "✅ OK" if not run.error else "❌ Error",
                    "Latencia (s)": f"{run.latency:.2f}" if run.latency else "N/A",
                    "Inicio": run.start_time.strftime("%Y-%m-%d %H:%M:%S") if run.start_time else "N/A",
                    "ID": str(run.id)[:12] + "...",
                }
            )

        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.info(
            f"Mostrando {len(data)} de {len(recent_runs)} ejecuciones recientes. "
            f"Ver todas en [LangSmith](https://smith.langchain.com)"
        )
    else:
        st.info("No hay ejecuciones recientes")


def render_agent_graph_viz():
    """Render agent graph visualization"""
    st.header("🔀 Flujo de Agentes (Graph Visualization)")

    st.info(
        """
    **Flujo del Sistema Multi-Agente:**

    1. **Orchestrator** → Analiza el mensaje y detecta la intención
    2. **Agentes Especializados** → Procesa según el tipo de consulta:
       - ProductAgent: Búsqueda de productos
       - CategoryAgent: Navegación de categorías
       - TrackingAgent: Seguimiento de pedidos
       - SupportAgent: Soporte al cliente
       - CreditAgent: Consultas de facturación/crédito
       - PromotionsAgent: Ofertas y promociones
       - FallbackAgent: Respuestas genéricas
    3. **Supervisor** → Valida la respuesta y decide si continuar
    """
    )

    # Create graph visualization using Plotly
    fig = go.Figure()

    # Define node positions (manual layout)
    nodes = {
        "Orchestrator": (0.5, 1.0),
        "ProductAgent": (0.2, 0.6),
        "CategoryAgent": (0.35, 0.6),
        "TrackingAgent": (0.5, 0.6),
        "SupportAgent": (0.65, 0.6),
        "CreditAgent": (0.8, 0.6),
        "PromotionsAgent": (0.2, 0.3),
        "FallbackAgent": (0.5, 0.3),
        "Supervisor": (0.5, 0.0),
    }

    # Add edges (arrows)
    for agent_name, (x, y) in nodes.items():
        if agent_name == "Orchestrator":
            # Orchestrator connects to all specialized agents
            for target, (tx, ty) in nodes.items():
                if target not in ["Orchestrator", "Supervisor"]:
                    fig.add_trace(
                        go.Scatter(
                            x=[x, tx],
                            y=[y, ty],
                            mode="lines",
                            line=dict(color="lightblue", width=2),
                            hoverinfo="none",
                            showlegend=False,
                        )
                    )
        elif agent_name != "Supervisor":
            # All agents connect to Supervisor
            sx, sy = nodes["Supervisor"]
            fig.add_trace(
                go.Scatter(
                    x=[x, sx],
                    y=[y, sy],
                    mode="lines",
                    line=dict(color="lightgreen", width=2),
                    hoverinfo="none",
                    showlegend=False,
                )
            )

    # Add nodes
    for agent_name, (x, y) in nodes.items():
        color = "blue" if agent_name == "Orchestrator" else "green" if agent_name == "Supervisor" else "orange"

        fig.add_trace(
            go.Scatter(
                x=[x],
                y=[y],
                mode="markers+text",
                marker=dict(size=30, color=color, line=dict(color="white", width=2)),
                text=[agent_name],
                textposition="bottom center",
                hoverinfo="text",
                name=agent_name,
                showlegend=False,
            )
        )

    fig.update_layout(
        title="Arquitectura del Sistema Multi-Agente",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=600,
        hovermode="closest",
    )

    st.plotly_chart(fig, use_container_width=True)


def render_test_interface():
    """Render interactive test interface"""
    st.header("💬 Interfaz de Prueba")

    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "session_id" not in st.session_state:
        st.session_state.session_id = f"streamlit_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if "metadata" in msg:
                with st.expander("Ver metadatos"):
                    st.json(msg["metadata"])

    # Chat input
    if prompt := st.chat_input("Escribe tu mensaje aquí..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.write(prompt)

        # Get bot response
        with st.chat_message("assistant"):
            with st.spinner("Procesando..."):
                try:
                    service = get_chat_service()

                    # Run async process_chat_message
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(
                        service.process_chat_message(
                            message=prompt,
                            user_id="streamlit_user",
                            session_id=st.session_state.session_id,
                            metadata={"source": "streamlit_dashboard"},
                        )
                    )

                    response = result.get("response", "Lo siento, no pude procesar tu mensaje.")
                    agent = result.get("agent_used", "unknown")
                    time_ms = result.get("processing_time_ms", 0)

                    st.write(response)

                    # Show metadata
                    with st.expander("Ver metadatos"):
                        metadata = {
                            "agent_used": agent,
                            "processing_time_ms": time_ms,
                            "session_id": st.session_state.session_id,
                            "requires_human": result.get("requires_human", False),
                            "is_complete": result.get("is_complete", False),
                        }
                        st.json(metadata)

                    # Add to messages
                    st.session_state.messages.append(
                        {"role": "assistant", "content": response, "metadata": metadata}
                    )

                except Exception as e:
                    st.error(f"Error: {str(e)}")


def main():
    """Main dashboard function"""
    render_header()

    # Sidebar
    tracer = get_langsmith_tracer()
    render_langsmith_status(tracer)

    # Time range selector
    st.sidebar.header("📅 Rango de Tiempo")
    time_range = st.sidebar.selectbox("Seleccionar período", ["Últimas 24 horas", "Últimas 48 horas", "Última semana"])

    hours = {"Últimas 24 horas": 24, "Últimas 48 horas": 48, "Última semana": 168}[time_range]

    # Refresh button
    if st.sidebar.button("🔄 Actualizar Datos"):
        st.cache_resource.clear()
        st.rerun()

    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "🔀 Graph Viz", "💬 Test Chat", "📖 Documentación"])

    with tab1:
        # Get metrics
        with st.spinner("Cargando métricas..."):
            metrics = get_langsmith_metrics(tracer, hours=hours)

        if metrics:
            render_overview_metrics(metrics)
            st.markdown("---")

            col1, col2 = st.columns(2)

            with col1:
                render_agent_usage_chart(metrics)

            with col2:
                render_error_analysis(metrics)

            st.markdown("---")
            render_performance_charts(metrics)

            st.markdown("---")
            render_recent_runs_table(metrics)
        else:
            st.warning("⚠️ No se pudieron cargar las métricas. Verifica la configuración de LangSmith.")

    with tab2:
        render_agent_graph_viz()

    with tab3:
        render_test_interface()

    with tab4:
        st.markdown(
            """
        # 📖 Documentación del Dashboard

        ## Características Principales

        ### 1. Métricas en Tiempo Real
        - **Total de Ejecuciones**: Número total de conversaciones procesadas
        - **Tasa de Éxito**: Porcentaje de conversaciones sin errores
        - **Latencia**: Tiempo promedio de respuesta
        - **P95 Latencia**: Percentil 95 de latencia (peor caso)

        ### 2. Análisis de Agentes
        - Visualización de uso de cada agente especializado
        - Identificación de agentes más utilizados
        - Distribución de consultas por tipo

        ### 3. Monitoreo de Rendimiento
        - Gráficos de ejecuciones por hora
        - Tendencias de uso en el tiempo
        - Identificación de picos de tráfico

        ### 4. Análisis de Errores
        - Tipos de errores y frecuencia
        - Tasa de error por período
        - Identificación de problemas comunes

        ### 5. Visualización del Grafo
        - Arquitectura del sistema multi-agente
        - Flujo de decisiones y routing
        - Relaciones entre agentes

        ### 6. Interfaz de Prueba
        - Chat interactivo en tiempo real
        - Mismo backend que WhatsApp
        - Trazas automáticas en LangSmith

        ## Integración con LangSmith

        Todas las conversaciones se rastrean automáticamente en LangSmith:
        - ✅ Trazas de cada agente
        - ✅ Decisiones de routing
        - ✅ Tiempos de procesamiento
        - ✅ Errores y excepciones
        - ✅ Metadatos de conversación

        ## Cómo Usar

        1. **Verificar Configuración**: Sidebar muestra estado de LangSmith
        2. **Seleccionar Rango**: Elegir período de análisis
        3. **Dashboard**: Ver métricas generales y tendencias
        4. **Graph Viz**: Entender el flujo de agentes
        5. **Test Chat**: Probar conversaciones en vivo
        6. **LangSmith**: Ver trazas detalladas en el dashboard web

        ## Requisitos

        - LANGSMITH_API_KEY configurada en .env
        - LANGSMITH_TRACING=true
        - Servicio de chat inicializado
        - Streamlit instalado (`pip install streamlit`)

        ## Ejecución

        ```bash
        streamlit run tests/monitoring_dashboard.py
        ```
        """
        )


if __name__ == "__main__":
    main()
