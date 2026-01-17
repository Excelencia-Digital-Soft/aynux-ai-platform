# ============================================================================
# SCOPE: MULTI-TENANT WORKFLOW
# Description: Admin API for reminder schedules and message templates.
# Tenant-Aware: Yes - via institution_config_id.
# ============================================================================
"""
Reminder Schedules and Message Templates Admin API.

Provides endpoints for:
- CRUD operations on reminder schedules
- CRUD operations on message templates
- Template preview and formatting

API Prefix: /api/v1/admin/reminder-schedules
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas.workflows import (
    MessageTemplateCreate,
    MessageTemplateListResponse,
    MessageTemplateResponse,
    MessageTemplateUpdate,
    ReminderScheduleCreate,
    ReminderScheduleListResponse,
    ReminderScheduleResponse,
    ReminderScheduleUpdate,
)
from app.database.async_db import get_async_db
from app.models.db.workflow import MessageTemplate, ReminderSchedule

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Reminder Schedules"])


# ============================================================================
# HELPERS
# ============================================================================


def _parse_uuid(value: str, field_name: str = "UUID") -> UUID:
    """Parse string to UUID with proper error handling."""
    try:
        return UUID(value)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format: {e}",
        ) from e


def _schedule_to_response(schedule: ReminderSchedule) -> ReminderScheduleResponse:
    """Convert ReminderSchedule to response schema."""
    return ReminderScheduleResponse(
        id=str(schedule.id),
        institution_config_id=str(schedule.institution_config_id),
        schedule_key=schedule.schedule_key,
        display_name=schedule.display_name,
        description=schedule.description,
        trigger_type=schedule.trigger_type,
        trigger_value=schedule.trigger_value,
        execution_hour=schedule.execution_hour,
        timezone=schedule.timezone,
        message_template_id=str(schedule.message_template_id) if schedule.message_template_id else None,
        fallback_message=schedule.fallback_message,
        buttons=schedule.buttons,
        is_active=schedule.is_active,
        created_at=schedule.created_at.isoformat() if schedule.created_at else None,
        updated_at=schedule.updated_at.isoformat() if schedule.updated_at else None,
    )


def _template_to_response(template: MessageTemplate) -> MessageTemplateResponse:
    """Convert MessageTemplate to response schema."""
    return MessageTemplateResponse(
        id=str(template.id),
        institution_config_id=str(template.institution_config_id) if template.institution_config_id else None,
        template_key=template.template_key,
        template_type=template.template_type,
        display_name=template.display_name,
        description=template.description,
        content=template.content,
        content_html=template.content_html,
        buttons=template.buttons,
        placeholders=template.placeholders,
        language=template.language,
        is_active=template.is_active,
        is_global=template.institution_config_id is None,
        created_at=template.created_at.isoformat() if template.created_at else None,
        updated_at=template.updated_at.isoformat() if template.updated_at else None,
    )


# ============================================================================
# REMINDER SCHEDULE ENDPOINTS
# ============================================================================


@router.get("", response_model=ReminderScheduleListResponse)
async def list_reminder_schedules(
    institution_config_id: str = Query(..., description="Institution config UUID"),
    trigger_type: str | None = Query(None, description="Filter by trigger type"),
    active_only: bool = Query(False, description="Only active schedules"),
    db: AsyncSession = Depends(get_async_db),
):
    """List reminder schedules for an institution."""
    inst_uuid = _parse_uuid(institution_config_id, "institution_config_id")

    stmt = (
        select(ReminderSchedule)
        .options(selectinload(ReminderSchedule.message_template))
        .where(ReminderSchedule.institution_config_id == inst_uuid)
    )

    if trigger_type:
        stmt = stmt.where(ReminderSchedule.trigger_type == trigger_type)
    if active_only:
        stmt = stmt.where(ReminderSchedule.is_active == True)  # noqa: E712

    stmt = stmt.order_by(ReminderSchedule.trigger_value.desc())

    result = await db.execute(stmt)
    schedules = result.scalars().all()

    return ReminderScheduleListResponse(
        schedules=[_schedule_to_response(s) for s in schedules],
        total=len(schedules),
    )


@router.post("", response_model=ReminderScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_reminder_schedule(
    data: ReminderScheduleCreate,
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new reminder schedule."""
    inst_uuid = _parse_uuid(data.institution_config_id, "institution_config_id")

    template_uuid = None
    if data.message_template_id:
        template_uuid = _parse_uuid(data.message_template_id, "message_template_id")

    schedule = ReminderSchedule(
        institution_config_id=inst_uuid,
        schedule_key=data.schedule_key,
        display_name=data.display_name,
        description=data.description,
        trigger_type=data.trigger_type,
        trigger_value=data.trigger_value,
        execution_hour=data.execution_hour,
        timezone=data.timezone,
        message_template_id=template_uuid,
        fallback_message=data.fallback_message,
        buttons=data.buttons,
        is_active=data.is_active,
    )

    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)

    logger.info(f"Created reminder schedule '{data.schedule_key}' for institution {inst_uuid}")
    return _schedule_to_response(schedule)


@router.get("/{schedule_id}", response_model=ReminderScheduleResponse)
async def get_reminder_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Get a reminder schedule by ID."""
    schedule_uuid = _parse_uuid(schedule_id, "schedule_id")

    stmt = (
        select(ReminderSchedule)
        .options(selectinload(ReminderSchedule.message_template))
        .where(ReminderSchedule.id == schedule_uuid)
    )
    result = await db.execute(stmt)
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reminder schedule not found: {schedule_id}",
        )

    return _schedule_to_response(schedule)


@router.put("/{schedule_id}", response_model=ReminderScheduleResponse)
async def update_reminder_schedule(
    schedule_id: str,
    data: ReminderScheduleUpdate,
    db: AsyncSession = Depends(get_async_db),
):
    """Update a reminder schedule."""
    schedule_uuid = _parse_uuid(schedule_id, "schedule_id")

    stmt = select(ReminderSchedule).where(ReminderSchedule.id == schedule_uuid)
    result = await db.execute(stmt)
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reminder schedule not found: {schedule_id}",
        )

    update_data = data.model_dump(exclude_unset=True)

    # Handle message_template_id separately
    if "message_template_id" in update_data:
        if update_data["message_template_id"]:
            update_data["message_template_id"] = _parse_uuid(
                update_data["message_template_id"], "message_template_id"
            )

    for key, value in update_data.items():
        setattr(schedule, key, value)

    await db.commit()
    await db.refresh(schedule)

    logger.info(f"Updated reminder schedule {schedule_id}")
    return _schedule_to_response(schedule)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reminder_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a reminder schedule."""
    schedule_uuid = _parse_uuid(schedule_id, "schedule_id")

    stmt = select(ReminderSchedule).where(ReminderSchedule.id == schedule_uuid)
    result = await db.execute(stmt)
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reminder schedule not found: {schedule_id}",
        )

    await db.delete(schedule)
    await db.commit()

    logger.info(f"Deleted reminder schedule {schedule_id}")


# ============================================================================
# MESSAGE TEMPLATE ENDPOINTS
# ============================================================================


templates_router = APIRouter(tags=["Message Templates"])


@templates_router.get("", response_model=MessageTemplateListResponse)
async def list_message_templates(
    institution_config_id: str | None = Query(None, description="Institution UUID (null for global)"),
    template_type: str | None = Query(None, description="Filter by type"),
    include_global: bool = Query(True, description="Include global templates"),
    active_only: bool = Query(False, description="Only active templates"),
    db: AsyncSession = Depends(get_async_db),
):
    """List message templates."""
    conditions = []

    if institution_config_id:
        inst_uuid = _parse_uuid(institution_config_id, "institution_config_id")
        if include_global:
            conditions.append(
                or_(
                    MessageTemplate.institution_config_id == inst_uuid,
                    MessageTemplate.institution_config_id.is_(None),
                )
            )
        else:
            conditions.append(MessageTemplate.institution_config_id == inst_uuid)
    elif not include_global:
        # Specific institution required but not provided
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="institution_config_id required when include_global=false",
        )
    # else: show all (global + all institutions)

    stmt = select(MessageTemplate)

    if conditions:
        stmt = stmt.where(*conditions)
    if template_type:
        stmt = stmt.where(MessageTemplate.template_type == template_type)
    if active_only:
        stmt = stmt.where(MessageTemplate.is_active == True)  # noqa: E712

    stmt = stmt.order_by(
        MessageTemplate.institution_config_id.desc().nullslast(),
        MessageTemplate.template_key,
    )

    result = await db.execute(stmt)
    templates = result.scalars().all()

    return MessageTemplateListResponse(
        templates=[_template_to_response(t) for t in templates],
        total=len(templates),
    )


@templates_router.post("", response_model=MessageTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_message_template(
    data: MessageTemplateCreate,
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new message template."""
    inst_uuid = None
    if data.institution_config_id:
        inst_uuid = _parse_uuid(data.institution_config_id, "institution_config_id")

    # Check for duplicate key (global or institution-specific)
    if inst_uuid is None:
        # Global template - check global uniqueness
        stmt = select(MessageTemplate).where(
            MessageTemplate.template_key == data.template_key,
            MessageTemplate.institution_config_id.is_(None),
        )
    else:
        # Institution-specific - check within institution
        stmt = select(MessageTemplate).where(
            MessageTemplate.template_key == data.template_key,
            MessageTemplate.institution_config_id == inst_uuid,
        )

    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        scope = "global" if inst_uuid is None else f"institution {inst_uuid}"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template '{data.template_key}' already exists ({scope})",
        )

    template = MessageTemplate(
        institution_config_id=inst_uuid,
        template_key=data.template_key,
        template_type=data.template_type,
        display_name=data.display_name,
        description=data.description,
        content=data.content,
        content_html=data.content_html,
        buttons=data.buttons,
        placeholders=data.placeholders,
        language=data.language,
        is_active=data.is_active,
    )

    db.add(template)
    await db.commit()
    await db.refresh(template)

    logger.info(f"Created message template '{data.template_key}'")
    return _template_to_response(template)


@templates_router.get("/{template_id}", response_model=MessageTemplateResponse)
async def get_message_template(
    template_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Get a message template by ID."""
    template_uuid = _parse_uuid(template_id, "template_id")

    stmt = select(MessageTemplate).where(MessageTemplate.id == template_uuid)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message template not found: {template_id}",
        )

    return _template_to_response(template)


@templates_router.get("/by-key/{template_key}", response_model=MessageTemplateResponse)
async def get_message_template_by_key(
    template_key: str,
    institution_config_id: str | None = Query(None, description="Institution UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Get a message template by key (institution-specific or global fallback)."""
    inst_uuid = None
    if institution_config_id:
        inst_uuid = _parse_uuid(institution_config_id, "institution_config_id")

    # Try institution-specific first, then global
    if inst_uuid:
        stmt = select(MessageTemplate).where(
            MessageTemplate.template_key == template_key,
            or_(
                MessageTemplate.institution_config_id == inst_uuid,
                MessageTemplate.institution_config_id.is_(None),
            ),
        ).order_by(MessageTemplate.institution_config_id.desc().nullslast())
    else:
        # Global only
        stmt = select(MessageTemplate).where(
            MessageTemplate.template_key == template_key,
            MessageTemplate.institution_config_id.is_(None),
        )

    result = await db.execute(stmt)
    template = result.scalars().first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message template not found: {template_key}",
        )

    return _template_to_response(template)


@templates_router.put("/{template_id}", response_model=MessageTemplateResponse)
async def update_message_template(
    template_id: str,
    data: MessageTemplateUpdate,
    db: AsyncSession = Depends(get_async_db),
):
    """Update a message template."""
    template_uuid = _parse_uuid(template_id, "template_id")

    stmt = select(MessageTemplate).where(MessageTemplate.id == template_uuid)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message template not found: {template_id}",
        )

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(template, key, value)

    await db.commit()
    await db.refresh(template)

    logger.info(f"Updated message template {template_id}")
    return _template_to_response(template)


@templates_router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message_template(
    template_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a message template."""
    template_uuid = _parse_uuid(template_id, "template_id")

    stmt = select(MessageTemplate).where(MessageTemplate.id == template_uuid)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message template not found: {template_id}",
        )

    await db.delete(template)
    await db.commit()

    logger.info(f"Deleted message template {template_id}")
