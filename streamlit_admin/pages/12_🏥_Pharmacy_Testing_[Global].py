"""
Pruebas de Agente de Farmacia - Simulacion Interactiva de WhatsApp

Prueba el grafo PharmacyGraph con conversaciones simuladas de WhatsApp.
Soporta identificacion de cliente, consultas de deuda, confirmacion y generacion de recibos.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
import sys

logger = logging.getLogger(__name__)

import graphviz
import nest_asyncio
import streamlit as st

# Apply nest_asyncio for async support in Streamlit
nest_asyncio.apply()

# Path setup
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import os
from dotenv import load_dotenv

load_dotenv()

# Verify critical env vars are loaded
if not os.getenv("PLEX_API_BASE_URL"):
    logger.warning("PLEX_API_BASE_URL no configurado - revisar archivo .env")

from langchain_core.messages import AIMessage, HumanMessage

from app.clients.mercado_pago_client import MercadoPagoClient, MercadoPagoError
from app.core.tenancy import TEST_PHARMACY_ORG_ID
from app.core.tenancy.pharmacy_config_service import PharmacyConfigService
from app.database.async_db import get_async_db_context
from app.domains.pharmacy.agents.graph import PharmacyGraph
from lib.session_state import init_session_state

# Page config must be first Streamlit command
st.set_page_config(
    page_title="Pruebas Farmacia",
    page_icon="🏥",
    layout="wide",
)

# Initialize session state
init_session_state()


class PharmacyGraphVisualizer:
    """Visualizador del grafo de farmacia con graphviz."""

    COLORS = {
        "entry": "#4A90E2",       # Azul - nodo de entrada
        "router": "#9B59B6",      # Purpura - router
        "operation": "#F5A623",   # Naranja - operaciones
        "registration": "#3498DB", # Azul claro - registro
        "current": "#E74C3C",     # Rojo - nodo actual
        "visited": "#27AE60",     # Verde - visitados
        "inactive": "#BDC3C7",    # Gris claro - inactivos
        "end": "#95A5A6",         # Gris - fin
    }

    NODE_INFO = {
        "customer_identification_node": ("👤", "Identificacion", "entry"),
        "customer_registration_node": ("📝", "Registro", "registration"),
        "pharmacy_router": ("🔀", "Router", "router"),
        "debt_check_node": ("💰", "Consulta Deuda", "operation"),
        "confirmation_node": ("✅", "Confirmacion", "operation"),
        "invoice_generation_node": ("🧾", "Recibo", "operation"),
    }

    def create_visualization(
        self,
        current_node: str | None = None,
        visited_nodes: set[str] | None = None,
    ) -> graphviz.Digraph:
        """Crear visualizacion del grafo de farmacia."""
        visited_nodes = visited_nodes or set()

        dot = graphviz.Digraph(comment="Grafo de Farmacia")
        dot.attr(rankdir="TB")
        dot.attr("node", shape="box", style="rounded,filled", fontname="Arial", fontsize="11")
        dot.attr("edge", fontname="Arial", fontsize="9")

        # Nodo START
        dot.node("START", "🚀 INICIO", fillcolor="#2ECC71", shape="oval", fontcolor="white")

        # Agregar nodos del grafo
        for node_id, (emoji, label, node_type) in self.NODE_INFO.items():
            color = self._get_node_color(node_id, current_node, visited_nodes, node_type)
            fontcolor = "white" if node_id == current_node else "black"
            dot.node(node_id, f"{emoji} {label}", fillcolor=color, fontcolor=fontcolor)

        # Nodo END
        dot.node("END", "🏁 FIN", fillcolor=self.COLORS["end"], shape="oval")

        # Agregar conexiones
        self._add_edges(dot, visited_nodes, current_node)

        return dot

    def _get_node_color(
        self,
        node_id: str,
        current_node: str | None,
        visited_nodes: set[str],
        node_type: str,
    ) -> str:
        """Obtener color del nodo segun su estado."""
        if node_id == current_node:
            return self.COLORS["current"]
        if node_id in visited_nodes:
            return self.COLORS["visited"]
        return self.COLORS.get(node_type, self.COLORS["inactive"])

    def _add_edges(
        self,
        dot: graphviz.Digraph,
        visited_nodes: set[str],
        current_node: str | None,
    ) -> None:
        """Agregar conexiones entre nodos."""
        # START -> Identificacion
        self._add_edge(dot, "START", "customer_identification_node", visited_nodes, current_node)

        # Identificacion -> Router / Registro / END
        self._add_edge(dot, "customer_identification_node", "pharmacy_router", visited_nodes, current_node, label="identificado")
        self._add_edge(dot, "customer_identification_node", "customer_registration_node", visited_nodes, current_node, label="nuevo", style="dashed")
        self._add_edge(dot, "customer_identification_node", "END", visited_nodes, current_node, label="error", style="dotted")

        # Registro -> Router / END
        self._add_edge(dot, "customer_registration_node", "pharmacy_router", visited_nodes, current_node, label="registrado")
        self._add_edge(dot, "customer_registration_node", "END", visited_nodes, current_node, label="cancelado", style="dotted")

        # Router -> Operaciones (incluye auto-fetch)
        self._add_edge(dot, "pharmacy_router", "debt_check_node", visited_nodes, current_node, label="deuda/auto")
        self._add_edge(dot, "pharmacy_router", "confirmation_node", visited_nodes, current_node, label="confirmar")
        self._add_edge(dot, "pharmacy_router", "invoice_generation_node", visited_nodes, current_node, label="recibo")
        self._add_edge(dot, "pharmacy_router", "END", visited_nodes, current_node, label="saludo/query/fin", style="dashed")

        # Operaciones -> Router / END
        self._add_edge(dot, "debt_check_node", "pharmacy_router", visited_nodes, current_node, style="dashed")
        self._add_edge(dot, "debt_check_node", "END", visited_nodes, current_node, label="esperando", style="dotted")

        self._add_edge(dot, "confirmation_node", "pharmacy_router", visited_nodes, current_node, style="dashed")
        self._add_edge(dot, "confirmation_node", "END", visited_nodes, current_node, label="confirmado", style="dotted")

        self._add_edge(dot, "invoice_generation_node", "END", visited_nodes, current_node, label="completado")

    def _add_edge(
        self,
        dot: graphviz.Digraph,
        from_node: str,
        to_node: str,
        visited_nodes: set[str],
        current_node: str | None,
        label: str = "",
        style: str = "solid",
    ) -> None:
        """Agregar una conexion con estilo dinamico."""
        # Determinar si la conexion fue usada
        is_active = from_node in visited_nodes and to_node in visited_nodes
        is_current_transition = from_node in visited_nodes and to_node == current_node

        if is_current_transition:
            color = self.COLORS["current"]
            penwidth = "3"
        elif is_active:
            color = self.COLORS["visited"]
            penwidth = "2"
        else:
            color = "#CCCCCC"
            penwidth = "1"

        dot.edge(from_node, to_node, label=label, color=color, penwidth=penwidth, style=style)


class PharmacyTesterPage:
    """Interfaz interactiva para pruebas del agente de farmacia."""

    def __init__(self):
        self.graph_visualizer = PharmacyGraphVisualizer()
        self._init_pharmacy_state()

    def _init_pharmacy_state(self):
        """Inicializar estado de sesion para farmacia."""
        defaults = {
            "pharmacy_graph": None,
            "pharmacy_graph_initialized": False,
            "pharmacy_conversation": [],
            "pharmacy_state": {},
            "pharmacy_node_trace": [],
            "pharmacy_phone": "2645631000",  # Telefono de prueba (cliente conocido)
            "pharmacy_conversation_id": str(uuid.uuid4()),
            "pharmacy_error": None,
            # Pharmacy selector and resolution
            "available_pharmacies": [],  # Lista de farmacias desde DB
            "selected_pharmacy_phone": None,  # Numero de farmacia seleccionada
            "org_resolution_info": None,  # Info de debugging
            # Payment verification
            "payment_verification_result": None,  # Result of last payment check
            "payment_verification_loading": False,
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

    def initialize_graph(self) -> bool:
        """Inicializar PharmacyGraph."""
        try:
            # Recargar modulos para detectar cambios en codigo
            import importlib
            import app.domains.pharmacy.agents.state as state_module  # State schema first!
            import app.domains.pharmacy.agents.graph as graph_module
            import app.domains.pharmacy.agents.nodes.customer_identification_node as id_node
            import app.domains.pharmacy.agents.nodes.customer_registration_node as reg_node
            import app.domains.pharmacy.agents.nodes.confirmation_node as conf_node
            import app.domains.pharmacy.agents.nodes.debt_check_node as debt_node
            import app.domains.pharmacy.agents.nodes.payment_link_node as payment_node
            import app.domains.pharmacy.agents.nodes as nodes_pkg

            # Reload state schema FIRST (contains organization_id field)
            importlib.reload(state_module)
            importlib.reload(id_node)
            importlib.reload(reg_node)
            importlib.reload(conf_node)
            importlib.reload(debt_node)
            importlib.reload(payment_node)
            importlib.reload(nodes_pkg)
            importlib.reload(graph_module)

            from app.domains.pharmacy.agents.graph import PharmacyGraph as FreshPharmacyGraph

            graph = FreshPharmacyGraph()
            graph.initialize()
            st.session_state.pharmacy_graph = graph
            st.session_state.pharmacy_graph_initialized = True
            st.session_state.pharmacy_error = None
            return True
        except Exception as e:
            st.session_state.pharmacy_error = str(e)
            import traceback
            traceback.print_exc()
            return False

    async def _load_available_pharmacies(self) -> list[dict]:
        """Load list of pharmacies from database for dropdown."""
        try:
            async with get_async_db_context() as db:
                service = PharmacyConfigService(db)
                pharmacies = await service.list_all_pharmacies()
                return pharmacies
        except Exception as e:
            logger.error(f"Error loading pharmacies: {e}")
            return []

    def load_pharmacies_sync(self) -> list[dict]:
        """Sync wrapper for loading pharmacies."""
        return asyncio.run(self._load_available_pharmacies())

    async def _verify_payment_status(self, external_reference: str) -> dict:
        """
        Verify payment status by searching MP API for payments with the external_reference.

        Returns dict with:
            - found: bool
            - status: str (approved, pending, rejected, etc.)
            - payment_id: str
            - amount: float
            - date: str
            - error: str (if any)
        """
        result = {
            "found": False,
            "status": None,
            "payment_id": None,
            "amount": None,
            "date": None,
            "payer": None,
            "error": None,
        }

        try:
            # Force reload module to avoid Streamlit caching
            import importlib
            import app.clients.mercado_pago_client as mp_module
            importlib.reload(mp_module)
            MercadoPagoClient = mp_module.MercadoPagoClient
            MercadoPagoError = mp_module.MercadoPagoError

            # Load pharmacy config to get MP credentials
            async with get_async_db_context() as db:
                service = PharmacyConfigService(db)
                config = await service.get_any_active_mp_config()

                if not config or not config.mp_access_token:
                    result["error"] = "No hay configuración de Mercado Pago activa"
                    return result

                # Search for payments with this external_reference
                mp_client = MercadoPagoClient(
                    access_token=config.mp_access_token,
                    sandbox=config.mp_sandbox,
                    timeout=config.mp_timeout,
                )

                async with mp_client:
                    payments = await mp_client.search_payments_by_external_reference(
                        external_reference
                    )

                if not payments:
                    result["error"] = "No se encontraron pagos para esta referencia"
                    return result

                # Get the most recent payment
                payment = payments[0]  # Results are sorted by date desc
                result["found"] = True
                result["status"] = payment.get("status")
                result["payment_id"] = payment.get("id")
                result["amount"] = payment.get("transaction_amount")
                result["date"] = payment.get("date_approved") or payment.get("date_created")
                result["payer"] = payment.get("payer", {}).get("email")

                return result

        except MercadoPagoError as e:
            result["error"] = f"Error de Mercado Pago: {e}"
            return result
        except Exception as e:
            result["error"] = f"Error inesperado: {e}"
            logger.error(f"Payment verification error: {e}", exc_info=True)
            return result

    def verify_payment_sync(self, external_reference: str) -> dict:
        """Sync wrapper for payment verification."""
        return asyncio.run(self._verify_payment_status(external_reference))

    async def _resolve_org_by_pharmacy_phone(self, pharmacy_phone: str) -> tuple[str, dict]:
        """
        Resolve organization from pharmacy WhatsApp phone number.

        Args:
            pharmacy_phone: The pharmacy's WhatsApp number (e.g., TEST_PHARMACY_000)

        Returns:
            Tuple of (organization_id_str, resolution_info_dict)
        """
        resolution_info = {
            "method": None,
            "pharmacy_phone": pharmacy_phone,
            "org_id": None,
            "pharmacy_name": None,
            "mp_enabled": False,
            "fallback_used": False,
            "error": None,
        }

        try:
            async with get_async_db_context() as db:
                service = PharmacyConfigService(db)
                config = await service.get_config_by_whatsapp_phone(pharmacy_phone)

                resolution_info["method"] = "whatsapp_phone_number"
                resolution_info["org_id"] = str(config.organization_id)
                resolution_info["pharmacy_name"] = config.pharmacy_name
                resolution_info["mp_enabled"] = config.mp_enabled

                return str(config.organization_id), resolution_info

        except ValueError as e:
            resolution_info["error"] = str(e)
            resolution_info["fallback_used"] = True
            resolution_info["method"] = "fallback"
            resolution_info["org_id"] = str(TEST_PHARMACY_ORG_ID)

            return str(TEST_PHARMACY_ORG_ID), resolution_info

        except Exception as e:
            resolution_info["error"] = str(e)
            resolution_info["fallback_used"] = True
            resolution_info["method"] = "error_fallback"
            resolution_info["org_id"] = str(TEST_PHARMACY_ORG_ID)

            return str(TEST_PHARMACY_ORG_ID), resolution_info

    async def _process_message_async(self, message: str, phone: str) -> str:
        """Procesar mensaje a traves del grafo de farmacia (async)."""
        graph: PharmacyGraph = st.session_state.pharmacy_graph

        current_state = dict(st.session_state.pharmacy_state) if st.session_state.pharmacy_state else {}
        existing_messages = current_state.get("messages", [])
        new_messages = list(existing_messages) + [HumanMessage(content=message)]

        # Resolve organization from selected pharmacy phone (realistic flow)
        # Try to get phone from widget value first, then from explicit session state
        pharmacy_phone = st.session_state.get("selected_pharmacy_phone")

        # Fallback: extract from widget if explicit value not set
        if not pharmacy_phone:
            selector_value = st.session_state.get("pharmacy_selector")
            if selector_value and selector_value != "(Seleccionar farmacia)":
                # Extract phone from display_label format: "Name (PHONE)"
                pharmacies = st.session_state.get("available_pharmacies", [])
                for p in pharmacies:
                    if p.get("display_label") == selector_value:
                        pharmacy_phone = p.get("whatsapp_phone_number")
                        logger.info(f"[DEBUG] Extracted pharmacy_phone from selector: {pharmacy_phone!r}")
                        break

        logger.info(f"[DEBUG] Final pharmacy_phone: {pharmacy_phone!r}")
        if pharmacy_phone:
            org_id, resolution_info = await self._resolve_org_by_pharmacy_phone(pharmacy_phone)
        else:
            # Fallback if no pharmacy selected
            org_id = str(TEST_PHARMACY_ORG_ID)
            resolution_info = {
                "method": "no_selection_fallback",
                "org_id": org_id,
                "pharmacy_phone": None,
                "fallback_used": True,
            }

        # Store resolution info for debugging display
        st.session_state.org_resolution_info = resolution_info

        current_state.update({
            "messages": new_messages,
            "customer_id": phone,
            "is_bypass_route": True,
            "organization_id": org_id,
        })

        try:
            config = {"recursion_limit": 50}
            result = await graph.app.ainvoke(current_state, config)

            st.session_state.pharmacy_state = dict(result)

            # Rastrear ejecucion del nodo
            workflow_step = result.get("workflow_step", "unknown")
            next_agent = result.get("next_agent", "")

            # Determinar nodo actual basado en el estado
            current_node = self._determine_current_node(result)

            st.session_state.pharmacy_node_trace.append({
                "step": workflow_step,
                "node": current_node,
                "next_agent": next_agent,
                "timestamp": datetime.now().isoformat(),
                "message": message[:50],
                "customer_identified": result.get("customer_identified", False),
                "has_debt": result.get("has_debt", False),
            })

            # Extraer respuesta
            messages = result.get("messages", [])
            if messages:
                for msg in reversed(messages):
                    if isinstance(msg, AIMessage):
                        return msg.content
                last_msg = messages[-1]
                if hasattr(last_msg, "content"):
                    return last_msg.content

            return "[Sin respuesta generada]"

        except Exception as e:
            import traceback
            full_error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
            st.session_state.pharmacy_error = full_error
            logger.error(f"Error en PharmacyGraph: {full_error}")
            return f"[Error: {e}]"

    def _determine_current_node(self, result: dict) -> str:
        """Determinar el nodo actual basado en el estado del resultado."""
        # Logica para determinar que nodo se ejecuto
        if result.get("awaiting_registration_data"):
            return "customer_registration_node"
        if result.get("requires_disambiguation") or result.get("awaiting_document_input"):
            return "customer_identification_node"
        if not result.get("customer_identified"):
            return "customer_identification_node"
        if result.get("next_agent"):
            return result["next_agent"]
        if result.get("debt_status") == "confirmed":
            return "confirmation_node"
        if result.get("has_debt"):
            return "debt_check_node"
        if result.get("is_complete"):
            return "invoice_generation_node"
        return "pharmacy_router"

    def process_message(self, message: str, phone: str) -> str:
        """Procesar mensaje (wrapper sincrono)."""
        return asyncio.run(self._process_message_async(message, phone))

    def render_sidebar(self):
        """Renderizar controles del sidebar."""
        with st.sidebar:
            st.header("🏥 Pruebas de Farmacia")

            # Input de telefono
            phone = st.text_input(
                "📱 Telefono WhatsApp",
                value=st.session_state.pharmacy_phone,
                help="Numero de telefono simulado (ej: 2645631000)",
            )
            if phone != st.session_state.pharmacy_phone:
                st.session_state.pharmacy_phone = phone

            # Numeros de prueba rapida
            st.markdown("**Numeros de Prueba:**")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📞 Conocido", help="2645631000 - Cliente con deuda", use_container_width=True):
                    st.session_state.pharmacy_phone = "2645631000"
                    st.rerun()
            with col2:
                if st.button("🆕 Nuevo", help="1234567890 - Cliente desconocido", use_container_width=True):
                    st.session_state.pharmacy_phone = "1234567890"
                    st.rerun()

            st.divider()

            # Pharmacy Selector
            st.markdown("**🏥 Farmacia Destino:**")

            # Load pharmacies if not loaded
            if not st.session_state.available_pharmacies:
                with st.spinner("Cargando farmacias..."):
                    st.session_state.available_pharmacies = self.load_pharmacies_sync()

            pharmacies = st.session_state.available_pharmacies

            if pharmacies:
                # Create options for selectbox
                options = ["(Seleccionar farmacia)"] + [p["display_label"] for p in pharmacies]
                phone_map = {p["display_label"]: p["whatsapp_phone_number"] for p in pharmacies}

                # Find current index
                current_idx = 0
                if st.session_state.selected_pharmacy_phone:
                    for i, p in enumerate(pharmacies):
                        if p["whatsapp_phone_number"] == st.session_state.selected_pharmacy_phone:
                            current_idx = i + 1  # +1 because of "(Seleccionar farmacia)"
                            break

                selected = st.selectbox(
                    "Farmacia",
                    options=options,
                    index=current_idx,
                    key="pharmacy_selector",
                    label_visibility="collapsed",
                )

                if selected != "(Seleccionar farmacia)":
                    selected_phone = phone_map.get(selected)
                    logger.info(f"[DEBUG SELECTOR] selected={selected!r}, selected_phone={selected_phone!r}, current={st.session_state.selected_pharmacy_phone!r}")
                    if selected_phone != st.session_state.selected_pharmacy_phone:
                        st.session_state.selected_pharmacy_phone = selected_phone
                        st.session_state.org_resolution_info = None  # Reset on change
                        logger.info(f"[DEBUG SELECTOR] Updated selected_pharmacy_phone to {selected_phone!r}, calling rerun")
                        st.rerun()
            else:
                st.warning("⚠️ No hay farmacias configuradas")
                st.caption("Configura pharmacy_merchant_configs en la DB")

            # Show resolution info
            if st.session_state.get("org_resolution_info"):
                info = st.session_state.org_resolution_info
                st.divider()
                st.markdown("**📍 Resolucion:**")

                if info.get("fallback_used"):
                    st.warning(f"⚠️ Fallback: {info.get('method')}")
                    if info.get("error"):
                        st.caption(f"Error: {info['error'][:50]}...")
                else:
                    st.success(f"✅ {info.get('method')}")

                st.caption(f"**Farmacia:** {info.get('pharmacy_name', 'N/A')}")
                org_id_display = info.get('org_id', 'N/A')
                if org_id_display and len(org_id_display) > 8:
                    org_id_display = org_id_display[:8] + "..."
                st.caption(f"**Org ID:** `{org_id_display}`")
                st.caption(f"**MP Habilitado:** {'✅' if info.get('mp_enabled') else '❌'}")

            # Debug display
            with st.expander("🔍 Debug Session State", expanded=False):
                st.code(f"selected_pharmacy_phone: {st.session_state.get('selected_pharmacy_phone')!r}")
                st.code(f"pharmacy_selector: {st.session_state.get('pharmacy_selector')!r}")
                st.code(f"available_pharmacies count: {len(st.session_state.get('available_pharmacies', []))}")

            st.divider()

            # Inicializacion del grafo
            if not st.session_state.pharmacy_graph_initialized:
                if st.button("🚀 Inicializar Grafo", type="primary", use_container_width=True):
                    with st.spinner("Inicializando PharmacyGraph..."):
                        if self.initialize_graph():
                            st.success("✅ Grafo listo!")
                            st.rerun()
                        else:
                            st.error(f"❌ Error: {st.session_state.pharmacy_error}")
            else:
                st.success("✅ Grafo inicializado")

                col1, col2 = st.columns(2)

                with col1:
                    if st.button("🔄 Reiniciar", use_container_width=True, help="Limpiar conversacion, mantener grafo"):
                        st.session_state.pharmacy_conversation = []
                        st.session_state.pharmacy_state = {}
                        st.session_state.pharmacy_node_trace = []
                        st.session_state.pharmacy_conversation_id = str(uuid.uuid4())
                        st.session_state.pharmacy_error = None
                        st.rerun()

                with col2:
                    if st.button("🔁 Recargar", use_container_width=True, help="Reinicializar grafo con codigo fresco"):
                        st.session_state.pharmacy_graph = None
                        st.session_state.pharmacy_graph_initialized = False
                        st.session_state.pharmacy_conversation = []
                        st.session_state.pharmacy_state = {}
                        st.session_state.pharmacy_node_trace = []
                        st.session_state.pharmacy_conversation_id = str(uuid.uuid4())
                        st.session_state.pharmacy_error = None
                        with st.spinner("Recargando..."):
                            if self.initialize_graph():
                                st.rerun()

            st.divider()

            # Resumen del estado actual
            if st.session_state.pharmacy_state:
                st.markdown("**Estado Actual:**")
                state = st.session_state.pharmacy_state

                if state.get("customer_identified"):
                    customer = state.get("plex_customer", {})
                    st.success(f"👤 {customer.get('nombre', 'Desconocido')[:20]}")
                elif state.get("requires_disambiguation"):
                    st.warning("⚠️ Multiples coincidencias")
                elif state.get("awaiting_document_input"):
                    st.info("📄 Esperando DNI")
                elif state.get("awaiting_registration_data"):
                    step = state.get("registration_step", "")
                    st.info(f"📝 Registro: {step}")
                else:
                    st.info("🔍 Identificando...")

                step = state.get("workflow_step", "N/A")
                st.caption(f"Paso: `{step}`")

    def render_chat(self):
        """Renderizar interfaz de chat."""
        col1, col2 = st.columns([5, 1])
        with col1:
            message = st.text_input(
                "Mensaje",
                placeholder="Escribe un mensaje... (ej: Hola, consultar deuda, si)",
                key="pharmacy_message_input",
                label_visibility="collapsed",
            )
        with col2:
            send = st.button("📤", type="primary", use_container_width=True,
                           disabled=not st.session_state.pharmacy_graph_initialized)

        if send and message:
            st.session_state.pharmacy_conversation.append({
                "role": "user",
                "content": message,
                "timestamp": datetime.now().isoformat(),
            })

            with st.spinner("Procesando..."):
                response = self.process_message(message, st.session_state.pharmacy_phone)

            st.session_state.pharmacy_conversation.append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now().isoformat(),
            })

            st.rerun()

        st.markdown("---")

        if not st.session_state.pharmacy_conversation:
            st.info("💬 Envia un mensaje para iniciar la conversacion. Prueba con 'Hola'!")

            st.markdown("**Mensajes Rapidos:**")
            qcol1, qcol2, qcol3, qcol4 = st.columns(4)
            with qcol1:
                if st.button("👋 Hola", use_container_width=True, disabled=not st.session_state.pharmacy_graph_initialized):
                    self._send_quick_message("Hola")
            with qcol2:
                if st.button("💰 Deuda", use_container_width=True, disabled=not st.session_state.pharmacy_graph_initialized):
                    self._send_quick_message("consultar deuda")
            with qcol3:
                if st.button("✅ Si", use_container_width=True, disabled=not st.session_state.pharmacy_graph_initialized):
                    self._send_quick_message("si")
            with qcol4:
                if st.button("🧾 Recibo", use_container_width=True, disabled=not st.session_state.pharmacy_graph_initialized):
                    self._send_quick_message("generar recibo")

            # Segunda fila de botones inteligentes
            st.markdown("**Flujos Inteligentes:**")
            icol1, icol2, icol3 = st.columns(3)
            with icol1:
                if st.button("💳 Quiero pagar", use_container_width=True, disabled=not st.session_state.pharmacy_graph_initialized):
                    self._send_quick_message("quiero pagar")
            with icol2:
                if st.button("💊 Que debo mas?", use_container_width=True, disabled=not st.session_state.pharmacy_graph_initialized):
                    self._send_quick_message("cual es el medicamento que mas debo")
            with icol3:
                if st.button("💵 Pagar 4000", use_container_width=True, disabled=not st.session_state.pharmacy_graph_initialized):
                    self._send_quick_message("quiero pagar solo 4000")
        else:
            for msg in st.session_state.pharmacy_conversation:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

    def _send_quick_message(self, message: str):
        """Enviar mensaje rapido."""
        st.session_state.pharmacy_conversation.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        })
        with st.spinner("Procesando..."):
            response = self.process_message(message, st.session_state.pharmacy_phone)
        st.session_state.pharmacy_conversation.append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().isoformat(),
        })
        st.rerun()

    def render_graph_visualization(self):
        """Renderizar visualizacion del grafo."""
        if not st.session_state.pharmacy_graph_initialized:
            st.info("ℹ️ Inicializa el grafo para ver la visualizacion")
            return

        # Obtener nodos visitados y actual
        visited_nodes = set()
        current_node = None

        if st.session_state.pharmacy_node_trace:
            for trace in st.session_state.pharmacy_node_trace:
                if trace.get("node"):
                    visited_nodes.add(trace["node"])
            current_node = st.session_state.pharmacy_node_trace[-1].get("node")

        # Crear y mostrar grafo
        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("🔀 Flujo del Grafo")
            graph_viz = self.graph_visualizer.create_visualization(
                current_node=current_node,
                visited_nodes=visited_nodes,
            )
            st.graphviz_chart(graph_viz)

        with col2:
            st.subheader("📊 Leyenda")
            st.markdown("""
            | Color | Significado |
            |-------|-------------|
            | 🔴 Rojo | Nodo actual |
            | 🟢 Verde | Nodo visitado |
            | 🔵 Azul | Identificacion |
            | 🟣 Purpura | Router |
            | 🟠 Naranja | Operaciones |
            | ⚪ Gris | Inactivo |
            """)

            # Estadisticas
            st.divider()
            st.subheader("📈 Estadisticas")
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Nodos Visitados", len(visited_nodes))
            with col_b:
                st.metric("Total Pasos", len(st.session_state.pharmacy_node_trace))

        # Timeline
        if st.session_state.pharmacy_node_trace:
            st.divider()
            st.subheader("🕐 Timeline de Ejecucion")

            for i, trace in enumerate(st.session_state.pharmacy_node_trace, 1):
                node = trace.get("node", "unknown")
                node_info = self.graph_visualizer.NODE_INFO.get(node, ("🔄", node, ""))
                emoji, label, _ = node_info

                # Color del paso
                if i == len(st.session_state.pharmacy_node_trace):
                    bg_color = "#E74C3C"  # Rojo para actual
                    text_color = "white"
                else:
                    bg_color = "#27AE60"  # Verde para visitados
                    text_color = "white"

                step_html = f"""
                <div style="display: flex; align-items: center; margin: 5px 0; padding: 8px;
                            border-radius: 8px; background-color: {bg_color};">
                    <span style="font-size: 20px; margin-right: 10px;">{emoji}</span>
                    <div style="flex: 1;">
                        <span style="color: {text_color}; font-weight: bold;">Paso {i}: {label}</span>
                        <span style="color: rgba(255,255,255,0.8); font-size: 12px; margin-left: 10px;">
                            {trace.get('message', '')[:30]}...
                        </span>
                    </div>
                </div>
                """
                st.markdown(step_html, unsafe_allow_html=True)
        else:
            st.info("ℹ️ Envia un mensaje para ver el flujo de ejecucion")

    def render_state_inspector(self):
        """Renderizar inspector de estado."""
        state = st.session_state.pharmacy_state

        if not state:
            st.info("📊 Sin estado aun. Envia un mensaje para comenzar.")
            return

        # Indicadores clave
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            identified = state.get("customer_identified", False)
            st.metric("Cliente", "✅ ID" if identified else "❌ No")
        with col2:
            step = state.get("workflow_step", "N/A")
            st.metric("Paso", step[:10] if step else "N/A")
        with col3:
            has_debt = state.get("has_debt", False)
            total = state.get("total_debt", 0)
            st.metric("Deuda", f"${total:,.0f}" if has_debt else "Sin deuda")
        with col4:
            status = state.get("debt_status", "N/A")
            st.metric("Estado", status or "N/A")

        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("👤 Cliente")
            if state.get("plex_customer"):
                customer = state["plex_customer"]
                st.markdown(f"""
                - **ID**: {customer.get('id', 'N/A')}
                - **Nombre**: {customer.get('nombre', 'N/A')}
                - **Documento**: {customer.get('documento', 'N/A')}
                - **Telefono**: {customer.get('telefono', 'N/A')}
                - **Valido**: {'✅' if customer.get('is_valid') else '❌'}
                """)
            else:
                st.caption("Cliente no identificado aun")

        with col2:
            st.subheader("🚦 Flags del Flujo")
            flags = {
                "awaiting_confirmation": state.get("awaiting_confirmation", False),
                "confirmation_received": state.get("confirmation_received", False),
                "requires_disambiguation": state.get("requires_disambiguation", False),
                "awaiting_document_input": state.get("awaiting_document_input", False),
                "awaiting_registration_data": state.get("awaiting_registration_data", False),
                "is_complete": state.get("is_complete", False),
            }
            for flag, value in flags.items():
                emoji = "✅" if value else "⬜"
                st.caption(f"{emoji} `{flag}`")

            # Auto-flow flags
            st.markdown("**🤖 Auto-Flow:**")
            auto_flags = {
                "auto_proceed_to_invoice": state.get("auto_proceed_to_invoice", False),
                "auto_return_to_query": state.get("auto_return_to_query", False),
                "is_partial_payment": state.get("is_partial_payment", False),
            }
            for flag, value in auto_flags.items():
                emoji = "🔄" if value else "⬜"
                st.caption(f"{emoji} `{flag}`")

            # Payment info
            if state.get("payment_amount"):
                st.caption(f"💰 payment_amount: ${state['payment_amount']:,.2f}")

        # Detalles de deuda
        if state.get("debt_data"):
            st.divider()
            st.subheader("💰 Detalle de Deuda")
            debt = state["debt_data"]

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Deuda Total", f"${state.get('total_debt', 0):,.2f}")
            with col2:
                st.metric("Items", len(debt.get("items", [])))

            if debt.get("items"):
                with st.expander("📋 Items de Deuda", expanded=False):
                    for i, item in enumerate(debt["items"][:10], 1):
                        st.caption(f"{i}. {item.get('description', 'N/A')}: ${item.get('amount', 0):,.2f}")
                    if len(debt["items"]) > 10:
                        st.caption(f"... y {len(debt['items']) - 10} items mas")

        # Payment Debug Section
        st.divider()
        st.subheader("💳 Estado de Pago Mercado Pago")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**🔗 Link de Pago**")
            if state.get("mp_init_point"):
                st.success("✅ Link generado")
                with st.expander("Ver URL", expanded=False):
                    st.code(state["mp_init_point"], language=None)
                st.caption(f"**Preference ID:** `{state.get('mp_preference_id', 'N/A')[:20]}...`")
            else:
                st.info("⏳ Sin link de pago generado")

            st.markdown("**📊 Estado del Pago**")
            mp_status = state.get("mp_payment_status", "N/A")
            if mp_status == "approved":
                st.success(f"✅ {mp_status}")
            elif mp_status == "pending":
                st.warning(f"⏳ {mp_status}")
            elif mp_status in ("rejected", "cancelled"):
                st.error(f"❌ {mp_status}")
            else:
                st.caption(f"Estado: `{mp_status}`")

            awaiting = state.get("awaiting_payment", False)
            st.caption(f"**Esperando pago:** {'🔄 Sí' if awaiting else '⬜ No'}")

            if state.get("mp_external_reference"):
                st.caption(f"**External Ref:** `{state['mp_external_reference'][:30]}...`")

        with col2:
            st.markdown("**🧾 Registro PLEX**")
            if state.get("plex_receipt_number"):
                st.success("✅ Pago registrado en PLEX")
                st.markdown(f"**Comprobante:** `{state['plex_receipt_number']}`")
                if state.get("plex_new_balance") is not None:
                    st.markdown(f"**Nuevo Saldo:** `${state['plex_new_balance']:,.2f}`")
            else:
                st.info("⏳ Pendiente de pago/registro")

            st.markdown("**📄 Recibo PDF**")
            pdf_url = state.get("pdf_url")
            if pdf_url:
                st.success("✅ PDF generado")
                st.markdown(f"[📥 Descargar Recibo]({pdf_url})")
            else:
                st.caption("Sin PDF generado")

            # Partial payment info
            if state.get("is_partial_payment"):
                st.markdown("**💵 Pago Parcial**")
                st.info(f"Monto: ${state.get('payment_amount', 0):,.2f}")
                remaining = state.get("remaining_balance")
                if remaining is not None:
                    st.caption(f"Saldo restante: ${remaining:,.2f}")

        # Payment Verification Button
        external_ref = state.get("mp_external_reference")
        if external_ref:
            st.divider()
            st.markdown("**🔄 Verificar Estado del Pago en MP**")

            col_btn, col_result = st.columns([1, 2])

            with col_btn:
                if st.button(
                    "🔍 Verificar Pago",
                    type="primary",
                    use_container_width=True,
                    help="Consulta la API de Mercado Pago para ver si el pago fue procesado",
                ):
                    with st.spinner("Consultando Mercado Pago..."):
                        result = self.verify_payment_sync(external_ref)
                        st.session_state.payment_verification_result = result
                    st.rerun()

            with col_result:
                verification = st.session_state.get("payment_verification_result")
                if verification:
                    if verification.get("error"):
                        st.error(f"❌ {verification['error']}")
                    elif verification.get("found"):
                        status = verification.get("status", "unknown")
                        if status == "approved":
                            st.success("✅ **PAGO APROBADO**")
                            st.markdown(f"""
                            - **Payment ID:** `{verification.get('payment_id')}`
                            - **Monto:** `${verification.get('amount', 0):,.2f}`
                            - **Fecha:** `{verification.get('date', 'N/A')}`
                            - **Payer:** `{verification.get('payer', 'N/A')}`
                            """)

                            # Auto-sync local state with MP status
                            state = st.session_state.get("pharmacy_state", {})
                            if state.get("mp_payment_status") != "approved":
                                state["mp_payment_status"] = "approved"
                                state["mp_payment_id"] = verification.get("payment_id")
                                state["awaiting_payment"] = False
                                st.session_state.pharmacy_state = state

                            # Find and show PDF download button
                            payment_id = str(verification.get("payment_id", ""))
                            receipts_dir = Path("app/static/receipts")
                            pdf_path = None
                            if receipts_dir.exists():
                                pdfs = list(receipts_dir.glob(f"recibo_{payment_id}_*.pdf"))
                                if pdfs:
                                    pdf_path = sorted(pdfs)[-1]  # Most recent

                            if pdf_path and pdf_path.exists():
                                st.markdown("---")
                                st.markdown("##### 📄 Comprobante PDF")
                                col_info, col_download = st.columns([2, 1])
                                with col_info:
                                    st.caption(f"`{pdf_path.name}`")
                                with col_download:
                                    with open(pdf_path, "rb") as f:
                                        st.download_button(
                                            "⬇️ Descargar",
                                            f.read(),
                                            file_name=pdf_path.name,
                                            mime="application/pdf",
                                            type="primary",
                                            use_container_width=True,
                                        )

                        elif status == "pending":
                            st.warning(f"⏳ **Pago Pendiente** - ID: {verification.get('payment_id')}")
                        else:
                            st.error(f"❌ **Estado: {status}** - ID: {verification.get('payment_id')}")
                    else:
                        st.info("ℹ️ No se encontraron pagos")
                else:
                    st.caption("Haz clic en 'Verificar Pago' para consultar el estado")

        # Traza de nodos
        if st.session_state.pharmacy_node_trace:
            st.divider()
            st.subheader("📊 Traza de Ejecucion")
            for trace in st.session_state.pharmacy_node_trace[-5:]:
                st.caption(f"`{trace.get('node', trace.get('step'))}` - {trace['message']}")

    def render_debug(self):
        """Renderizar tab de depuracion."""
        state = st.session_state.pharmacy_state

        # Mostrar errores
        if st.session_state.pharmacy_error:
            st.error(f"**Ultimo Error:** {st.session_state.pharmacy_error}")

        st.subheader("🔧 Estado Raw de Farmacia")

        if state:
            # Filtrar mensajes para vista mas limpia
            display_state = {k: v for k, v in state.items() if k != "messages"}
            st.json(display_state)

            with st.expander("📨 Historial de Mensajes"):
                messages = state.get("messages", [])
                if messages:
                    for i, msg in enumerate(messages):
                        msg_type = type(msg).__name__
                        content = msg.content if hasattr(msg, "content") else str(msg)
                        display_content = content[:200] + "..." if len(content) > 200 else content
                        st.text(f"[{i}] {msg_type}: {display_content}")
                else:
                    st.caption("Sin mensajes aun")
        else:
            st.info("Sin estado disponible. Inicia una conversacion primero.")

        st.divider()
        st.subheader("📋 Info de Sesion")
        st.caption(f"**ID Conversacion:** `{st.session_state.pharmacy_conversation_id}`")
        st.caption(f"**Telefono Cliente:** `{st.session_state.pharmacy_phone}`")
        st.caption(f"**Mensajes:** {len(st.session_state.pharmacy_conversation)}")
        st.caption(f"**Grafo Inicializado:** {st.session_state.pharmacy_graph_initialized}")

        # Organization Resolution Details
        st.divider()
        st.subheader("🏥 Resolucion de Organizacion")

        col1, col2 = st.columns(2)
        with col1:
            st.caption(f"**Farmacia Seleccionada:** `{st.session_state.get('selected_pharmacy_phone', 'Ninguna')}`")
        with col2:
            st.caption(f"**Cliente:** `{st.session_state.pharmacy_phone}`")

        if st.session_state.get("org_resolution_info"):
            st.json(st.session_state.org_resolution_info)
        else:
            st.caption("Sin informacion de resolucion aun. Envia un mensaje para ver.")

        # Info de traza de nodos
        st.divider()
        st.subheader("🔍 Traza de Nodos (Debug)")
        if st.session_state.pharmacy_node_trace:
            for i, trace in enumerate(st.session_state.pharmacy_node_trace):
                with st.expander(f"Paso {i+1}: {trace.get('node', 'unknown')}", expanded=False):
                    st.json(trace)
        else:
            st.caption("Sin traza de nodos aun")

    def render(self):
        """Metodo principal de renderizado."""
        st.title("🏥 Pruebas de Agente de Farmacia")
        st.markdown("Prueba el agente del dominio de farmacia con conversaciones simuladas de WhatsApp")

        self.render_sidebar()

        if not st.session_state.pharmacy_graph_initialized:
            st.warning("👈 Haz clic en **Inicializar Grafo** en el sidebar para comenzar")

            with st.expander("ℹ️ Como usar esta pagina"):
                st.markdown("""
                1. **Inicializar**: Haz clic en "Inicializar Grafo" en el sidebar
                2. **Configurar Telefono**: Ingresa un numero o usa los botones rapidos
                3. **Conversar**: Envia mensajes para interactuar con el agente
                4. **Monitorear**: Usa las pestanas de Grafo, Estado y Debug para inspeccionar

                **Telefonos de Prueba:**
                - `2645631000` - Cliente conocido (PEDROZO, tiene deuda)
                - `1234567890` - Cliente desconocido (activa flujo de registro)

                **Flujo de Prueba:**
                1. Envia "Hola" para identificar al cliente
                2. Envia "consultar deuda" para ver el saldo
                3. Envia "si" para confirmar la deuda
                4. Envia "generar recibo" para crear el comprobante
                """)
            return

        # Tabs
        tab1, tab2, tab3, tab4 = st.tabs([
            "💬 Conversacion",
            "📊 Grafo",
            "🔍 Inspector de Estado",
            "🐛 Depuracion"
        ])

        with tab1:
            self.render_chat()

        with tab2:
            self.render_graph_visualization()

        with tab3:
            self.render_state_inspector()

        with tab4:
            self.render_debug()


# Ejecutar pagina
if __name__ == "__main__":
    page = PharmacyTesterPage()
    page.render()
else:
    page = PharmacyTesterPage()
    page.render()
