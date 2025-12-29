# ============================================================================
# SCOPE: MULTI-TENANT
# Description: API para historial de conversaciones de farmacias.
#              Permite ver clientes, timeline de mensajes y conversaciones
#              por farmacia.
# Tenant-Aware: Yes - filtra por organization_id de la farmacia.
# ============================================================================
"""
Pharmacy Conversations API - Message history endpoints.

Provides endpoints for viewing pharmacy conversation history:
- Customers who contacted the pharmacy
- Global message timeline with filters
- Individual conversation threads
- Statistics
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user_db
from app.database.async_db import get_async_db
from app.models.db.conversation_history import ConversationContext, ConversationMessage
from app.models.db.tenancy import OrganizationUser
from app.models.db.tenancy.pharmacy_merchant_config import PharmacyMerchantConfig
from app.models.db.user import UserDB

router = APIRouter(tags=["Pharmacy Conversations"])


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================


class PharmacyCustomerResponse(BaseModel):
    """Customer who contacted the pharmacy."""

    user_phone: str
    conversation_id: str
    total_messages: int
    last_activity: str | None
    first_message: str | None
    rolling_summary: str | None


class PharmacyCustomerListResponse(BaseModel):
    """Paginated list of pharmacy customers."""

    customers: list[PharmacyCustomerResponse]
    total: int
    page: int
    page_size: int


class PharmacyMessageResponse(BaseModel):
    """Individual message in pharmacy history."""

    id: str
    conversation_id: str
    user_phone: str | None
    sender_type: str
    content: str
    agent_name: str | None
    created_at: str
    extra_data: dict


class PharmacyTimelineResponse(BaseModel):
    """Paginated message timeline."""

    messages: list[PharmacyMessageResponse]
    total: int
    page: int
    page_size: int


class PharmacyConversationResponse(BaseModel):
    """Full conversation thread with context."""

    conversation_id: str
    user_phone: str | None
    messages: list[PharmacyMessageResponse]
    total_messages: int
    context: dict


class PharmacyStatsResponse(BaseModel):
    """Pharmacy conversation statistics."""

    total_customers: int
    total_conversations: int
    total_messages: int
    messages_today: int
    messages_this_week: int
    avg_messages_per_conversation: float
    active_conversations_24h: int


# ============================================================
# HELPER FUNCTIONS
# ============================================================


async def get_pharmacy_with_auth(
    pharmacy_id: str,
    db: AsyncSession,
    user: UserDB,
) -> PharmacyMerchantConfig:
    """Get pharmacy config with authorization check."""
    try:
        pharmacy_uuid = uuid.UUID(pharmacy_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid pharmacy ID format"
        ) from e

    stmt = select(PharmacyMerchantConfig).where(PharmacyMerchantConfig.id == pharmacy_uuid)
    result = await db.execute(stmt)
    pharmacy = result.scalar_one_or_none()

    if not pharmacy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pharmacy not found"
        )

    # System admins can access any pharmacy
    is_system_admin = "admin" in (user.scopes or [])
    if is_system_admin:
        return pharmacy

    # Check user has access to this organization
    membership_stmt = select(OrganizationUser).where(
        OrganizationUser.user_id == user.id,
        OrganizationUser.organization_id == pharmacy.organization_id,
    )
    membership_result = await db.execute(membership_stmt)
    membership = membership_result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this pharmacy",
        )

    return pharmacy


# ============================================================
# ENDPOINTS
# ============================================================


@router.get("/{pharmacy_id}/customers", response_model=PharmacyCustomerListResponse)
async def get_pharmacy_customers(
    pharmacy_id: str,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=25, ge=1, le=100, description="Items per page"),
    search: str | None = Query(default=None, description="Search by phone"),
    user: UserDB = Depends(get_current_user_db),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get customers who contacted this pharmacy.

    Returns distinct customers with their conversation metadata.
    """
    pharmacy = await get_pharmacy_with_auth(pharmacy_id, db, user)

    # Query distinct customers for this organization
    stmt = (
        select(ConversationContext)
        .where(ConversationContext.organization_id == pharmacy.organization_id)
        .where(ConversationContext.user_phone.isnot(None))
    )

    if search:
        stmt = stmt.where(ConversationContext.user_phone.ilike(f"%{search}%"))

    # Get total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Apply pagination and ordering
    offset = (page - 1) * page_size
    stmt = stmt.order_by(desc(ConversationContext.last_activity_at)).offset(offset).limit(page_size)

    result = await db.execute(stmt)
    contexts = result.scalars().all()

    customers = [
        PharmacyCustomerResponse(
            user_phone=ctx.user_phone or "",
            conversation_id=ctx.conversation_id,
            total_messages=ctx.total_turns,
            last_activity=ctx.last_activity_at.isoformat() if ctx.last_activity_at else None,
            first_message=ctx.created_at.isoformat() if ctx.created_at else None,
            rolling_summary=ctx.rolling_summary,
        )
        for ctx in contexts
    ]

    return PharmacyCustomerListResponse(
        customers=customers, total=total, page=page, page_size=page_size
    )


@router.get("/{pharmacy_id}/timeline", response_model=PharmacyTimelineResponse)
async def get_pharmacy_timeline(
    pharmacy_id: str,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=100, description="Items per page"),
    start_date: str | None = Query(default=None, description="Start date (ISO format)"),
    end_date: str | None = Query(default=None, description="End date (ISO format)"),
    sender_type: str | None = Query(default=None, description="Filter by sender type"),
    user_phone: str | None = Query(default=None, description="Filter by customer phone"),
    search: str | None = Query(default=None, description="Search in message content"),
    user: UserDB = Depends(get_current_user_db),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get message timeline for this pharmacy.

    Returns paginated messages with optional filters.
    """
    pharmacy = await get_pharmacy_with_auth(pharmacy_id, db, user)

    # Get conversations for this organization
    conv_stmt = select(ConversationContext.conversation_id).where(
        ConversationContext.organization_id == pharmacy.organization_id
    )
    conv_result = await db.execute(conv_stmt)
    conversation_ids = [row[0] for row in conv_result.fetchall()]

    if not conversation_ids:
        return PharmacyTimelineResponse(
            messages=[], total=0, page=page, page_size=page_size
        )

    # Build message query
    stmt = (
        select(ConversationMessage, ConversationContext.user_phone)
        .join(
            ConversationContext,
            ConversationMessage.conversation_id == ConversationContext.conversation_id,
        )
        .where(ConversationMessage.conversation_id.in_(conversation_ids))
    )

    # Apply filters
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            stmt = stmt.where(ConversationMessage.created_at >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            stmt = stmt.where(ConversationMessage.created_at <= end_dt)
        except ValueError:
            pass

    if sender_type and sender_type != "all":
        stmt = stmt.where(ConversationMessage.sender_type == sender_type)

    if user_phone:
        stmt = stmt.where(ConversationContext.user_phone == user_phone)

    if search:
        stmt = stmt.where(ConversationMessage.content.ilike(f"%{search}%"))

    # Get total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Apply pagination and ordering
    offset = (page - 1) * page_size
    stmt = stmt.order_by(desc(ConversationMessage.created_at)).offset(offset).limit(page_size)

    result = await db.execute(stmt)
    rows = result.fetchall()

    messages = [
        PharmacyMessageResponse(
            id=str(msg.id),
            conversation_id=msg.conversation_id,
            user_phone=phone,
            sender_type=msg.sender_type.value if hasattr(msg.sender_type, "value") else msg.sender_type,
            content=msg.content,
            agent_name=msg.agent_name,
            created_at=msg.created_at.isoformat() if msg.created_at else "",
            extra_data=msg.extra_data or {},
        )
        for msg, phone in rows
    ]

    return PharmacyTimelineResponse(
        messages=messages, total=total, page=page, page_size=page_size
    )


@router.get(
    "/{pharmacy_id}/conversations/{conversation_id}",
    response_model=PharmacyConversationResponse,
)
async def get_pharmacy_conversation(
    pharmacy_id: str,
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=200, description="Max messages"),
    offset: int = Query(default=0, ge=0, description="Skip messages"),
    user: UserDB = Depends(get_current_user_db),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get full conversation thread for a specific customer.

    Returns messages with conversation context.
    """
    pharmacy = await get_pharmacy_with_auth(pharmacy_id, db, user)

    # Get conversation context
    ctx_stmt = (
        select(ConversationContext)
        .where(ConversationContext.conversation_id == conversation_id)
        .where(ConversationContext.organization_id == pharmacy.organization_id)
    )
    ctx_result = await db.execute(ctx_stmt)
    context = ctx_result.scalar_one_or_none()

    if not context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )

    # Get messages
    msg_stmt = (
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at)
        .offset(offset)
        .limit(limit)
    )
    msg_result = await db.execute(msg_stmt)
    messages = msg_result.scalars().all()

    return PharmacyConversationResponse(
        conversation_id=conversation_id,
        user_phone=context.user_phone,
        messages=[
            PharmacyMessageResponse(
                id=str(msg.id),
                conversation_id=msg.conversation_id,
                user_phone=context.user_phone,
                sender_type=msg.sender_type.value if hasattr(msg.sender_type, "value") else msg.sender_type,
                content=msg.content,
                agent_name=msg.agent_name,
                created_at=msg.created_at.isoformat() if msg.created_at else "",
                extra_data=msg.extra_data or {},
            )
            for msg in messages
        ],
        total_messages=context.total_turns,
        context={
            "rolling_summary": context.rolling_summary,
            "topic_history": context.topic_history or [],
            "last_activity": context.last_activity_at.isoformat() if context.last_activity_at else None,
        },
    )


@router.get("/{pharmacy_id}/stats", response_model=PharmacyStatsResponse)
async def get_pharmacy_stats(
    pharmacy_id: str,
    user: UserDB = Depends(get_current_user_db),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get conversation statistics for this pharmacy.

    Returns aggregated metrics about customer interactions.
    """
    pharmacy = await get_pharmacy_with_auth(pharmacy_id, db, user)

    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    day_ago = now - timedelta(hours=24)

    # Get all conversations for this org
    conv_stmt = select(ConversationContext).where(
        ConversationContext.organization_id == pharmacy.organization_id
    )
    conv_result = await db.execute(conv_stmt)
    conversations = conv_result.scalars().all()

    conversation_ids = [c.conversation_id for c in conversations]

    if not conversation_ids:
        return PharmacyStatsResponse(
            total_customers=0,
            total_conversations=0,
            total_messages=0,
            messages_today=0,
            messages_this_week=0,
            avg_messages_per_conversation=0.0,
            active_conversations_24h=0,
        )

    # Count total customers (distinct user_phones)
    total_customers = len({c.user_phone for c in conversations if c.user_phone})

    # Total conversations
    total_conversations = len(conversations)

    # Total messages
    total_messages = sum(c.total_turns for c in conversations)

    # Messages today
    today_stmt = (
        select(func.count())
        .select_from(ConversationMessage)
        .where(ConversationMessage.conversation_id.in_(conversation_ids))
        .where(ConversationMessage.created_at >= today_start)
    )
    today_result = await db.execute(today_stmt)
    messages_today = today_result.scalar() or 0

    # Messages this week
    week_stmt = (
        select(func.count())
        .select_from(ConversationMessage)
        .where(ConversationMessage.conversation_id.in_(conversation_ids))
        .where(ConversationMessage.created_at >= week_start)
    )
    week_result = await db.execute(week_stmt)
    messages_this_week = week_result.scalar() or 0

    # Average messages per conversation
    avg_messages = total_messages / total_conversations if total_conversations > 0 else 0.0

    # Active conversations in last 24h
    active_24h = len([c for c in conversations if c.last_activity_at and c.last_activity_at >= day_ago])

    return PharmacyStatsResponse(
        total_customers=total_customers,
        total_conversations=total_conversations,
        total_messages=total_messages,
        messages_today=messages_today,
        messages_this_week=messages_this_week,
        avg_messages_per_conversation=round(avg_messages, 1),
        active_conversations_24h=active_24h,
    )
