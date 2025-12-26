# ============================================================================
# SCOPE: MULTI-TENANT
# Description: API de admin para farmacias - listar, testing de agente.
# Tenant-Aware: Yes - lista farmacias de pharmacy_merchant_configs.
# ============================================================================
"""
Pharmacy Admin API - Endpoints for pharmacy testing and management.

Provides endpoints for the Vue.js pharmacy testing interface.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from threading import Lock
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenancy.pharmacy_config_service import PharmacyConfigService
from app.database.async_db import get_async_db
from app.domains.pharmacy.agents.graph import PharmacyGraph
from app.repositories.async_redis_repository import AsyncRedisRepository

logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS
# ============================================================

SESSION_TTL = 86400  # 24 hours in seconds
SESSION_PREFIX = "pharmacy_test"


# ============================================================
# SESSION STATE MODELS
# ============================================================


class SerializedMessage(BaseModel):
    """Serializable representation of LangChain messages."""

    role: str  # "human" or "ai"
    content: str
    timestamp: str | None = None


class PharmacySessionState(BaseModel):
    """Pydantic model for Redis session storage."""

    session_id: str
    organization_id: str
    customer_id: str  # WhatsApp phone number
    messages: list[SerializedMessage] = Field(default_factory=list)

    # Core state fields (from PharmacyState)
    customer_identified: bool = False
    plex_customer_id: int | None = None
    plex_customer: dict[str, Any] | None = None
    has_debt: bool = False
    total_debt: float | None = None
    debt_data: dict[str, Any] | None = None
    debt_status: str | None = None
    awaiting_confirmation: bool = False
    confirmation_received: bool = False
    workflow_step: str | None = None
    is_complete: bool = False
    error_count: int = 0

    # Payment state
    mp_preference_id: str | None = None
    mp_init_point: str | None = None
    mp_payment_status: str | None = None
    mp_external_reference: str | None = None
    awaiting_payment: bool = False
    payment_amount: float | None = None
    is_partial_payment: bool = False

    # Registration state
    awaiting_registration_data: bool = False
    registration_step: str | None = None

    # Metadata
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    model_config = {"extra": "allow"}


# ============================================================
# MESSAGE SERIALIZATION HELPERS
# ============================================================


def serialize_messages(messages: list[BaseMessage]) -> list[SerializedMessage]:
    """Convert LangChain messages to serializable format."""
    result = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            result.append(
                SerializedMessage(
                    role="human",
                    content=str(msg.content),
                    timestamp=datetime.now().isoformat(),
                )
            )
        elif isinstance(msg, AIMessage):
            result.append(
                SerializedMessage(
                    role="ai",
                    content=str(msg.content),
                    timestamp=datetime.now().isoformat(),
                )
            )
    return result


def deserialize_messages(messages: list[SerializedMessage]) -> list[BaseMessage]:
    """Convert serialized messages back to LangChain format."""
    result: list[BaseMessage] = []
    for msg in messages:
        if msg.role == "human":
            result.append(HumanMessage(content=msg.content))
        elif msg.role == "ai":
            result.append(AIMessage(content=msg.content))
    return result


def extract_bot_response(result: dict[str, Any]) -> str:
    """Extract the last AIMessage content from graph result."""
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return str(msg.content)
    return "[Sin respuesta generada]"


# ============================================================
# GRAPH MANAGER (SINGLETON)
# ============================================================


class PharmacyGraphManager:
    """Singleton manager for PharmacyGraph instance."""

    _instance: PharmacyGraphManager | None = None
    _lock = Lock()

    def __init__(self) -> None:
        self._graph: PharmacyGraph | None = None
        self._initialized = False

    @classmethod
    def get_instance(cls) -> PharmacyGraphManager:
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_graph(self) -> PharmacyGraph:
        """Get or initialize the PharmacyGraph singleton."""
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._graph = PharmacyGraph()
                    self._graph.initialize()
                    self._initialized = True
                    logger.info("PharmacyGraph singleton initialized")
        if self._graph is None:
            raise RuntimeError("PharmacyGraph failed to initialize")
        return self._graph

    def reset(self) -> None:
        """Reset the graph (for testing/debugging)."""
        with self._lock:
            self._graph = None
            self._initialized = False


# Global singleton
_graph_manager = PharmacyGraphManager.get_instance()


# ============================================================
# SESSION REPOSITORY
# ============================================================


class PharmacySessionRepository:
    """Repository for pharmacy test session management."""

    def __init__(self) -> None:
        self._repo: AsyncRedisRepository[PharmacySessionState] | None = None
        self._connected = False

    async def _ensure_connected(self) -> None:
        """Ensure Redis connection is established."""
        if self._repo is None:
            self._repo = AsyncRedisRepository[PharmacySessionState](
                model_class=PharmacySessionState,
                prefix=SESSION_PREFIX,
            )
        if not self._connected:
            await self._repo.connect()
            self._connected = True

    async def get(self, session_id: str) -> PharmacySessionState | None:
        """Get session state by ID."""
        await self._ensure_connected()
        if self._repo is None:
            return None
        return await self._repo.get(session_id)

    async def save(self, session: PharmacySessionState) -> bool:
        """Save session state with TTL."""
        await self._ensure_connected()
        if self._repo is None:
            return False
        session.updated_at = datetime.now().isoformat()
        return await self._repo.set(session.session_id, session, expiration=SESSION_TTL)

    async def delete(self, session_id: str) -> bool:
        """Delete session state."""
        await self._ensure_connected()
        if self._repo is None:
            return False
        return await self._repo.delete(session_id)

    async def exists(self, session_id: str) -> bool:
        """Check if session exists."""
        await self._ensure_connected()
        if self._repo is None:
            return False
        return await self._repo.exists(session_id)


# Global repository instance
_session_repo = PharmacySessionRepository()


router = APIRouter(prefix="/admin/pharmacy", tags=["Pharmacy Admin"])


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================


class PharmacyResponse(BaseModel):
    """Schema for pharmacy list response."""

    id: str = Field(..., description="Organization ID")
    name: str = Field(..., description="Pharmacy name")
    code: str = Field(..., description="WhatsApp phone number")
    address: str | None = Field(None, description="Pharmacy address")
    phone: str | None = Field(None, description="Pharmacy phone")
    active: bool = Field(True, description="Whether pharmacy is active")


class PharmacyTestRequest(BaseModel):
    """Schema for pharmacy test message request."""

    pharmacy_id: str = Field(..., description="Pharmacy organization ID")
    message: str = Field(..., description="Test message to send")
    session_id: str | None = Field(None, description="Existing session ID")
    phone_number: str | None = Field(None, description="Simulated customer phone")


class PharmacyTestResponse(BaseModel):
    """Schema for pharmacy test message response."""

    session_id: str = Field(..., description="Session ID")
    response: str = Field(..., description="Agent response")
    execution_steps: list[Any] | None = Field(None, description="Execution trace")
    graph_state: dict[str, Any] | None = Field(None, description="Current graph state")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")


# ============================================================
# ENDPOINTS
# ============================================================


@router.get("/list", response_model=list[PharmacyResponse])
async def list_pharmacies(
    db: AsyncSession = Depends(get_async_db),
) -> list[PharmacyResponse]:
    """
    List all available pharmacies for testing.

    Returns pharmacy configurations from the database.
    """
    try:
        service = PharmacyConfigService(db)
        pharmacies = await service.list_all_pharmacies()

        return [
            PharmacyResponse(
                id=p["organization_id"],
                name=p["pharmacy_name"],
                code=p["whatsapp_phone_number"] or "",
                address=None,  # Not exposed in list_all_pharmacies
                phone=None,
                active=p["mp_enabled"],
            )
            for p in pharmacies
        ]
    except Exception as e:
        logger.error(f"Error listing pharmacies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading pharmacies: {e}",
        ) from e


@router.post("/test", response_model=PharmacyTestResponse)
async def send_test_message(
    request: PharmacyTestRequest,
    db: AsyncSession = Depends(get_async_db),
) -> PharmacyTestResponse:
    """
    Send a test message to the pharmacy agent.

    This endpoint simulates a WhatsApp conversation for testing purposes.
    Supports multi-turn conversations via session_id.
    """
    try:
        # 1. Resolve organization_id from pharmacy_id
        service = PharmacyConfigService(db)
        try:
            org_id = UUID(request.pharmacy_id)
            config = await service.get_config(org_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid pharmacy_id format: {e}",
            ) from e
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pharmacy not found: {e}",
            ) from e

        # 2. Get or create session
        session_id = request.session_id or str(uuid.uuid4())
        existing_session = await _session_repo.get(session_id)

        if existing_session:
            session = existing_session
            previous_messages = deserialize_messages(session.messages)
        else:
            session = PharmacySessionState(
                session_id=session_id,
                organization_id=str(org_id),
                customer_id=request.phone_number or "5491122334455",
            )
            previous_messages = []

        # 3. Get graph and build state
        graph = _graph_manager.get_graph()

        new_message = HumanMessage(content=request.message)
        all_messages = list(previous_messages) + [new_message]

        graph_state: dict[str, Any] = {
            "messages": all_messages,
            "customer_id": session.customer_id,
            "organization_id": str(org_id),
            "is_bypass_route": True,
            "is_complete": False,
            "error_count": session.error_count,
            "has_debt": session.has_debt,
            "awaiting_confirmation": session.awaiting_confirmation,
            "customer_identified": session.customer_identified,
            # Restore state for multi-turn
            "plex_customer_id": session.plex_customer_id,
            "plex_customer": session.plex_customer,
            "total_debt": session.total_debt,
            "debt_data": session.debt_data,
            "debt_status": session.debt_status,
            "confirmation_received": session.confirmation_received,
            "workflow_step": session.workflow_step,
            "mp_preference_id": session.mp_preference_id,
            "mp_init_point": session.mp_init_point,
            "mp_payment_status": session.mp_payment_status,
            "mp_external_reference": session.mp_external_reference,
            "awaiting_payment": session.awaiting_payment,
            "payment_amount": session.payment_amount,
            "is_partial_payment": session.is_partial_payment,
            "awaiting_registration_data": session.awaiting_registration_data,
            "registration_step": session.registration_step,
        }

        # 4. Invoke graph
        invoke_config = {"recursion_limit": 50}
        result = await graph.app.ainvoke(graph_state, invoke_config)

        # 5. Extract response
        response_text = extract_bot_response(result)

        # 6. Update session state from result
        session.messages = serialize_messages(result.get("messages", []))
        session.customer_identified = result.get("customer_identified", False)
        session.plex_customer_id = result.get("plex_customer_id")
        session.plex_customer = result.get("plex_customer")
        session.has_debt = result.get("has_debt", False)
        session.total_debt = result.get("total_debt")
        session.debt_data = result.get("debt_data")
        session.debt_status = result.get("debt_status")
        session.awaiting_confirmation = result.get("awaiting_confirmation", False)
        session.confirmation_received = result.get("confirmation_received", False)
        session.workflow_step = result.get("workflow_step")
        session.is_complete = result.get("is_complete", False)
        session.error_count = result.get("error_count", 0)
        session.mp_preference_id = result.get("mp_preference_id")
        session.mp_init_point = result.get("mp_init_point")
        session.mp_payment_status = result.get("mp_payment_status")
        session.mp_external_reference = result.get("mp_external_reference")
        session.awaiting_payment = result.get("awaiting_payment", False)
        session.payment_amount = result.get("payment_amount")
        session.is_partial_payment = result.get("is_partial_payment", False)
        session.awaiting_registration_data = result.get("awaiting_registration_data", False)
        session.registration_step = result.get("registration_step")

        # 7. Save session
        await _session_repo.save(session)

        # 8. Build response
        return PharmacyTestResponse(
            session_id=session_id,
            response=response_text,
            execution_steps=[
                {
                    "workflow_step": result.get("workflow_step"),
                    "next_agent": result.get("next_agent"),
                    "customer_identified": result.get("customer_identified", False),
                }
            ],
            graph_state={
                "customer_identified": result.get("customer_identified", False),
                "has_debt": result.get("has_debt", False),
                "total_debt": result.get("total_debt"),
                "debt_status": result.get("debt_status"),
                "workflow_step": result.get("workflow_step"),
                "awaiting_confirmation": result.get("awaiting_confirmation", False),
                "is_complete": result.get("is_complete", False),
                "awaiting_payment": result.get("awaiting_payment", False),
                "mp_init_point": result.get("mp_init_point"),
            },
            metadata={
                "pharmacy_id": request.pharmacy_id,
                "pharmacy_name": config.pharmacy_name,
                "message_count": len(session.messages),
                "is_new_session": request.session_id is None,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in pharmacy test: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing test message: {e}",
        ) from e


@router.get("/session/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    """
    Get test session history.

    Returns the conversation history and state for a given session.
    """
    session = await _session_repo.get(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    return {
        "session_id": session.session_id,
        "messages": [
            {"role": m.role, "content": m.content, "timestamp": m.timestamp}
            for m in session.messages
        ],
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "execution_steps": [],
        "graph_state": {
            "customer_identified": session.customer_identified,
            "has_debt": session.has_debt,
            "total_debt": session.total_debt,
            "debt_status": session.debt_status,
            "workflow_step": session.workflow_step,
            "awaiting_confirmation": session.awaiting_confirmation,
            "is_complete": session.is_complete,
            "awaiting_payment": session.awaiting_payment,
            "mp_init_point": session.mp_init_point,
        },
    }


@router.delete("/session/{session_id}")
async def clear_session(
    session_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, bool]:
    """
    Clear a test session.

    Removes session data from Redis cache.
    """
    exists = await _session_repo.exists(session_id)
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    success = await _session_repo.delete(session_id)
    return {"success": success}


@router.get("/graph/{session_id}")
async def get_graph_data(
    session_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    """
    Get pharmacy graph visualization data.

    Returns data for visualizing the agent graph execution.
    """
    session = await _session_repo.get(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    # Define node structure for the pharmacy graph
    nodes = [
        {"id": "customer_identification_node", "label": "Identificacion", "type": "entry"},
        {"id": "customer_registration_node", "label": "Registro", "type": "registration"},
        {"id": "pharmacy_router", "label": "Router", "type": "router"},
        {"id": "debt_check_node", "label": "Consulta Deuda", "type": "operation"},
        {"id": "confirmation_node", "label": "Confirmacion", "type": "operation"},
        {"id": "invoice_generation_node", "label": "Recibo", "type": "operation"},
        {"id": "payment_link_node", "label": "Link de Pago", "type": "operation"},
    ]

    edges = [
        {"from": "customer_identification_node", "to": "pharmacy_router"},
        {"from": "customer_identification_node", "to": "customer_registration_node"},
        {"from": "customer_registration_node", "to": "pharmacy_router"},
        {"from": "pharmacy_router", "to": "debt_check_node"},
        {"from": "pharmacy_router", "to": "confirmation_node"},
        {"from": "pharmacy_router", "to": "invoice_generation_node"},
        {"from": "pharmacy_router", "to": "payment_link_node"},
        {"from": "debt_check_node", "to": "pharmacy_router"},
        {"from": "confirmation_node", "to": "pharmacy_router"},
        {"from": "confirmation_node", "to": "payment_link_node"},
    ]

    return {
        "session_id": session_id,
        "nodes": nodes,
        "edges": edges,
        "current_node": session.workflow_step,
        "visited_nodes": [],  # Could track this in session if needed
    }
