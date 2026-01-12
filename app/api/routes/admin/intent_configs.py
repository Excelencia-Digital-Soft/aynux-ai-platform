# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Admin API for managing intent routing configurations. Replaces
#              hardcoded values in intent_validator.py with database-driven config.
# Tenant-Aware: Yes - each organization has isolated configurations.
# ============================================================================
"""
Intent Configs Admin API - Manage intent routing configurations.

Replaces hardcoded values in intent_validator.py:
- AGENT_TO_INTENT_MAPPING -> Intent Agent Mappings endpoints
- FLOW_AGENTS -> Flow Agent Configs endpoints
- KEYWORD_TO_AGENT -> Keyword Agent Mappings endpoints

Also provides:
- Test endpoint to simulate intent detection
- Visualization endpoint for Vue Flow diagram
- Seed endpoint to import from hardcoded defaults
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.intent_configs import (
    AllConfigsResponse,
    CacheInvalidateResponse,
    CacheStatsResponse,
    FlowAgentConfigCreate,
    FlowAgentConfigListResponse,
    FlowAgentConfigResponse,
    FlowAgentConfigUpdate,
    FlowEdge,
    FlowNode,
    FlowVisualizationResponse,
    IntentAgentMappingCreate,
    IntentAgentMappingListResponse,
    IntentAgentMappingResponse,
    IntentAgentMappingUpdate,
    IntentTestRequest,
    IntentTestResponse,
    IntentTestResult,
    KeywordAgentMappingBulkCreate,
    KeywordAgentMappingCreate,
    KeywordAgentMappingListResponse,
    KeywordAgentMappingResponse,
    SeedRequest,
    SeedResponse,
)
from app.core.cache.intent_config_cache import intent_config_cache
from app.database.async_db import get_async_db
from app.models.db.intent_configs import (
    FlowAgentConfig,
    IntentAgentMapping,
    KeywordAgentMapping,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Intent Configs"])


# ============================================================
# HELPERS
# ============================================================


def _parse_org_id(organization_id: str) -> UUID:
    """Parse and validate organization_id string to UUID."""
    try:
        return UUID(organization_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid organization_id format: {e}",
        ) from e


def _parse_uuid(value: str, name: str = "id") -> UUID:
    """Parse and validate UUID string."""
    try:
        return UUID(value)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {name} format: {e}",
        ) from e


def _mapping_to_response(mapping: IntentAgentMapping) -> IntentAgentMappingResponse:
    """Convert IntentAgentMapping to response schema."""
    return IntentAgentMappingResponse(
        id=str(mapping.id),
        organization_id=str(mapping.organization_id),
        domain_key=mapping.domain_key,
        intent_key=mapping.intent_key,
        intent_name=mapping.intent_name,
        intent_description=mapping.intent_description,
        agent_key=mapping.agent_key,
        confidence_threshold=float(mapping.confidence_threshold),
        requires_handoff=mapping.requires_handoff,
        priority=mapping.priority,
        is_enabled=mapping.is_enabled,
        examples=mapping.examples or [],
        created_at=mapping.created_at.isoformat() if mapping.created_at else None,
        updated_at=mapping.updated_at.isoformat() if mapping.updated_at else None,
    )


def _flow_config_to_response(config: FlowAgentConfig) -> FlowAgentConfigResponse:
    """Convert FlowAgentConfig to response schema."""
    return FlowAgentConfigResponse(
        id=str(config.id),
        organization_id=str(config.organization_id),
        agent_key=config.agent_key,
        is_flow_agent=config.is_flow_agent,
        flow_description=config.flow_description,
        max_turns=config.max_turns,
        timeout_seconds=config.timeout_seconds,
        is_enabled=config.is_enabled,
        created_at=config.created_at.isoformat() if config.created_at else None,
        updated_at=config.updated_at.isoformat() if config.updated_at else None,
    )


def _keyword_to_response(keyword: KeywordAgentMapping) -> KeywordAgentMappingResponse:
    """Convert KeywordAgentMapping to response schema."""
    return KeywordAgentMappingResponse(
        id=str(keyword.id),
        organization_id=str(keyword.organization_id),
        agent_key=keyword.agent_key,
        keyword=keyword.keyword,
        match_type=keyword.match_type,
        case_sensitive=keyword.case_sensitive,
        priority=keyword.priority,
        is_enabled=keyword.is_enabled,
        created_at=keyword.created_at.isoformat() if keyword.created_at else None,
    )


# ============================================================
# INTENT AGENT MAPPINGS ENDPOINTS
# ============================================================


@router.get("/mappings", response_model=IntentAgentMappingListResponse)
async def list_intent_mappings(
    organization_id: str = Query(..., description="Organization UUID"),
    domain_key: str | None = Query(None, description="Filter by domain"),
    enabled_only: bool = Query(False, description="Only return enabled mappings"),
    db: AsyncSession = Depends(get_async_db),
):
    """List all intent-to-agent mappings for an organization."""
    org_uuid = _parse_org_id(organization_id)

    stmt = select(IntentAgentMapping).where(
        IntentAgentMapping.organization_id == org_uuid
    )

    if domain_key:
        stmt = stmt.where(IntentAgentMapping.domain_key == domain_key)

    if enabled_only:
        stmt = stmt.where(IntentAgentMapping.is_enabled == True)  # noqa: E712

    stmt = stmt.order_by(IntentAgentMapping.priority.desc())

    result = await db.execute(stmt)
    mappings = result.scalars().all()

    return IntentAgentMappingListResponse(
        mappings=[_mapping_to_response(m) for m in mappings],
        total=len(mappings),
        organization_id=organization_id,
    )


@router.post("/mappings", response_model=IntentAgentMappingResponse, status_code=status.HTTP_201_CREATED)
async def create_intent_mapping(
    data: IntentAgentMappingCreate,
    organization_id: str = Query(..., description="Organization UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new intent-to-agent mapping."""
    org_uuid = _parse_org_id(organization_id)

    # Check for duplicate
    stmt = select(IntentAgentMapping).where(
        IntentAgentMapping.organization_id == org_uuid,
        IntentAgentMapping.domain_key == data.domain_key,
        IntentAgentMapping.intent_key == data.intent_key,
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mapping for intent '{data.intent_key}' already exists",
        )

    mapping = IntentAgentMapping(
        organization_id=org_uuid,
        domain_key=data.domain_key,
        intent_key=data.intent_key,
        intent_name=data.intent_name,
        intent_description=data.intent_description,
        agent_key=data.agent_key,
        confidence_threshold=data.confidence_threshold,
        requires_handoff=data.requires_handoff,
        priority=data.priority,
        is_enabled=data.is_enabled,
        examples=data.examples,
    )

    db.add(mapping)
    await db.commit()
    await db.refresh(mapping)

    # Invalidate cache
    await intent_config_cache.invalidate(org_uuid)

    logger.info(f"Created intent mapping: {data.intent_key} -> {data.agent_key}")
    return _mapping_to_response(mapping)


@router.get("/mappings/{mapping_id}", response_model=IntentAgentMappingResponse)
async def get_intent_mapping(
    mapping_id: str = Path(..., description="Mapping UUID"),
    organization_id: str = Query(..., description="Organization UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Get a specific intent-to-agent mapping."""
    org_uuid = _parse_org_id(organization_id)
    id_uuid = _parse_uuid(mapping_id, "mapping_id")

    stmt = select(IntentAgentMapping).where(
        IntentAgentMapping.id == id_uuid,
        IntentAgentMapping.organization_id == org_uuid,
    )
    result = await db.execute(stmt)
    mapping = result.scalar_one_or_none()

    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping {mapping_id} not found",
        )

    return _mapping_to_response(mapping)


@router.put("/mappings/{mapping_id}", response_model=IntentAgentMappingResponse)
async def update_intent_mapping(
    data: IntentAgentMappingUpdate,
    mapping_id: str = Path(..., description="Mapping UUID"),
    organization_id: str = Query(..., description="Organization UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Update an intent-to-agent mapping."""
    org_uuid = _parse_org_id(organization_id)
    id_uuid = _parse_uuid(mapping_id, "mapping_id")

    stmt = select(IntentAgentMapping).where(
        IntentAgentMapping.id == id_uuid,
        IntentAgentMapping.organization_id == org_uuid,
    )
    result = await db.execute(stmt)
    mapping = result.scalar_one_or_none()

    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping {mapping_id} not found",
        )

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(mapping, field, value)

    await db.commit()
    await db.refresh(mapping)

    # Invalidate cache
    await intent_config_cache.invalidate(org_uuid)

    logger.info(f"Updated intent mapping: {mapping.intent_key}")
    return _mapping_to_response(mapping)


@router.delete("/mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_intent_mapping(
    mapping_id: str = Path(..., description="Mapping UUID"),
    organization_id: str = Query(..., description="Organization UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete an intent-to-agent mapping."""
    org_uuid = _parse_org_id(organization_id)
    id_uuid = _parse_uuid(mapping_id, "mapping_id")

    stmt = delete(IntentAgentMapping).where(
        IntentAgentMapping.id == id_uuid,
        IntentAgentMapping.organization_id == org_uuid,
    )
    result = await db.execute(stmt)
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping {mapping_id} not found",
        )

    # Invalidate cache
    await intent_config_cache.invalidate(org_uuid)

    logger.info(f"Deleted intent mapping: {mapping_id}")


# ============================================================
# FLOW AGENT CONFIGS ENDPOINTS
# ============================================================


@router.get("/flow-agents", response_model=FlowAgentConfigListResponse)
async def list_flow_agents(
    organization_id: str = Query(..., description="Organization UUID"),
    enabled_only: bool = Query(False, description="Only return enabled configs"),
    db: AsyncSession = Depends(get_async_db),
):
    """List all flow agent configurations for an organization."""
    org_uuid = _parse_org_id(organization_id)

    stmt = select(FlowAgentConfig).where(
        FlowAgentConfig.organization_id == org_uuid
    )

    if enabled_only:
        stmt = stmt.where(FlowAgentConfig.is_enabled == True)  # noqa: E712

    result = await db.execute(stmt)
    configs = result.scalars().all()

    return FlowAgentConfigListResponse(
        configs=[_flow_config_to_response(c) for c in configs],
        total=len(configs),
        organization_id=organization_id,
    )


@router.post("/flow-agents", response_model=FlowAgentConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_flow_agent(
    data: FlowAgentConfigCreate,
    organization_id: str = Query(..., description="Organization UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new flow agent configuration."""
    org_uuid = _parse_org_id(organization_id)

    # Check for duplicate
    stmt = select(FlowAgentConfig).where(
        FlowAgentConfig.organization_id == org_uuid,
        FlowAgentConfig.agent_key == data.agent_key,
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Flow config for agent '{data.agent_key}' already exists",
        )

    config = FlowAgentConfig(
        organization_id=org_uuid,
        agent_key=data.agent_key,
        is_flow_agent=data.is_flow_agent,
        flow_description=data.flow_description,
        max_turns=data.max_turns,
        timeout_seconds=data.timeout_seconds,
        is_enabled=data.is_enabled,
    )

    db.add(config)
    await db.commit()
    await db.refresh(config)

    # Invalidate cache
    await intent_config_cache.invalidate(org_uuid)

    logger.info(f"Created flow agent config: {data.agent_key}")
    return _flow_config_to_response(config)


@router.put("/flow-agents/{agent_key}", response_model=FlowAgentConfigResponse)
async def update_flow_agent(
    data: FlowAgentConfigUpdate,
    agent_key: str = Path(..., description="Agent key"),
    organization_id: str = Query(..., description="Organization UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Update a flow agent configuration."""
    org_uuid = _parse_org_id(organization_id)

    stmt = select(FlowAgentConfig).where(
        FlowAgentConfig.organization_id == org_uuid,
        FlowAgentConfig.agent_key == agent_key,
    )
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flow config for agent '{agent_key}' not found",
        )

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)

    await db.commit()
    await db.refresh(config)

    # Invalidate cache
    await intent_config_cache.invalidate(org_uuid)

    logger.info(f"Updated flow agent config: {agent_key}")
    return _flow_config_to_response(config)


@router.delete("/flow-agents/{agent_key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow_agent(
    agent_key: str = Path(..., description="Agent key"),
    organization_id: str = Query(..., description="Organization UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a flow agent configuration."""
    org_uuid = _parse_org_id(organization_id)

    stmt = delete(FlowAgentConfig).where(
        FlowAgentConfig.organization_id == org_uuid,
        FlowAgentConfig.agent_key == agent_key,
    )
    result = await db.execute(stmt)
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flow config for agent '{agent_key}' not found",
        )

    # Invalidate cache
    await intent_config_cache.invalidate(org_uuid)

    logger.info(f"Deleted flow agent config: {agent_key}")


# ============================================================
# KEYWORD AGENT MAPPINGS ENDPOINTS
# ============================================================


@router.get("/keywords", response_model=KeywordAgentMappingListResponse)
async def list_keywords(
    organization_id: str = Query(..., description="Organization UUID"),
    agent_key: str | None = Query(None, description="Filter by agent"),
    enabled_only: bool = Query(False, description="Only return enabled keywords"),
    db: AsyncSession = Depends(get_async_db),
):
    """List all keyword-to-agent mappings for an organization."""
    org_uuid = _parse_org_id(organization_id)

    stmt = select(KeywordAgentMapping).where(
        KeywordAgentMapping.organization_id == org_uuid
    )

    if agent_key:
        stmt = stmt.where(KeywordAgentMapping.agent_key == agent_key)

    if enabled_only:
        stmt = stmt.where(KeywordAgentMapping.is_enabled == True)  # noqa: E712

    stmt = stmt.order_by(KeywordAgentMapping.priority.desc())

    result = await db.execute(stmt)
    keywords = result.scalars().all()

    return KeywordAgentMappingListResponse(
        mappings=[_keyword_to_response(k) for k in keywords],
        total=len(keywords),
        organization_id=organization_id,
    )


@router.post("/keywords", response_model=KeywordAgentMappingResponse, status_code=status.HTTP_201_CREATED)
async def create_keyword(
    data: KeywordAgentMappingCreate,
    organization_id: str = Query(..., description="Organization UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new keyword-to-agent mapping."""
    org_uuid = _parse_org_id(organization_id)

    # Check for duplicate
    stmt = select(KeywordAgentMapping).where(
        KeywordAgentMapping.organization_id == org_uuid,
        KeywordAgentMapping.agent_key == data.agent_key,
        KeywordAgentMapping.keyword == data.keyword,
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Keyword '{data.keyword}' already exists for agent '{data.agent_key}'",
        )

    keyword = KeywordAgentMapping(
        organization_id=org_uuid,
        agent_key=data.agent_key,
        keyword=data.keyword,
        match_type=data.match_type.value,
        case_sensitive=data.case_sensitive,
        priority=data.priority,
        is_enabled=data.is_enabled,
    )

    db.add(keyword)
    await db.commit()
    await db.refresh(keyword)

    # Invalidate cache
    await intent_config_cache.invalidate(org_uuid)

    logger.info(f"Created keyword mapping: {data.keyword} -> {data.agent_key}")
    return _keyword_to_response(keyword)


@router.post("/keywords/bulk", response_model=KeywordAgentMappingListResponse, status_code=status.HTTP_201_CREATED)
async def create_keywords_bulk(
    data: KeywordAgentMappingBulkCreate,
    organization_id: str = Query(..., description="Organization UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Bulk create keyword-to-agent mappings."""
    org_uuid = _parse_org_id(organization_id)

    created = []
    for kw in data.keywords:
        # Skip duplicates
        stmt = select(KeywordAgentMapping).where(
            KeywordAgentMapping.organization_id == org_uuid,
            KeywordAgentMapping.agent_key == data.agent_key,
            KeywordAgentMapping.keyword == kw,
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            continue

        keyword = KeywordAgentMapping(
            organization_id=org_uuid,
            agent_key=data.agent_key,
            keyword=kw,
            match_type=data.match_type.value,
            case_sensitive=data.case_sensitive,
            priority=data.priority,
            is_enabled=True,
        )
        db.add(keyword)
        created.append(keyword)

    await db.commit()

    # Refresh all created keywords
    for kw in created:
        await db.refresh(kw)

    # Invalidate cache
    await intent_config_cache.invalidate(org_uuid)

    logger.info(f"Bulk created {len(created)} keywords for {data.agent_key}")
    return KeywordAgentMappingListResponse(
        mappings=[_keyword_to_response(k) for k in created],
        total=len(created),
        organization_id=organization_id,
    )


@router.delete("/keywords/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_keyword(
    keyword_id: str = Path(..., description="Keyword UUID"),
    organization_id: str = Query(..., description="Organization UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a keyword-to-agent mapping."""
    org_uuid = _parse_org_id(organization_id)
    id_uuid = _parse_uuid(keyword_id, "keyword_id")

    stmt = delete(KeywordAgentMapping).where(
        KeywordAgentMapping.id == id_uuid,
        KeywordAgentMapping.organization_id == org_uuid,
    )
    result = await db.execute(stmt)
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keyword {keyword_id} not found",
        )

    # Invalidate cache
    await intent_config_cache.invalidate(org_uuid)

    logger.info(f"Deleted keyword: {keyword_id}")


# ============================================================
# TEST ENDPOINT
# ============================================================


@router.post("/test", response_model=IntentTestResponse)
async def test_intent_detection(
    data: IntentTestRequest,
    organization_id: str = Query(..., description="Organization UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Test intent detection for a message."""
    org_uuid = _parse_org_id(organization_id)

    # Get configs from cache
    mappings = await intent_config_cache.get_intent_mappings(db, org_uuid, data.domain_key)
    flow_agents = await intent_config_cache.get_flow_agents(db, org_uuid)
    keywords = await intent_config_cache.get_keyword_mappings(db, org_uuid)

    message_lower = data.message.lower()
    matched_keywords = []
    detected_intent = "fallback"
    target_agent = "fallback_agent"
    method = "none"
    reasoning = "No match found"

    # Try keyword matching first
    for agent_key, agent_keywords in keywords.items():
        for kw in agent_keywords:
            if kw.lower() in message_lower:
                matched_keywords.append(kw)
                if detected_intent == "fallback":
                    detected_intent = "keyword_match"
                    target_agent = agent_key
                    method = "keyword"
                    reasoning = f"Matched keyword '{kw}'"

    # Try intent mapping (reverse lookup from agent)
    # Filter out domain metadata keys
    clean_mappings = {k: v for k, v in mappings.items() if not k.startswith("_")}
    for intent_key, agent_key in clean_mappings.items():
        if intent_key.lower() in message_lower or any(
            word in message_lower for word in intent_key.lower().split("_")
        ):
            detected_intent = intent_key
            target_agent = agent_key
            method = "mapping"
            reasoning = f"Matched intent pattern '{intent_key}'"
            break

    is_flow_agent = target_agent in flow_agents

    return IntentTestResponse(
        result=IntentTestResult(
            detected_intent=detected_intent,
            confidence=0.8 if method != "none" else 0.3,
            target_agent=target_agent,
            method=method,
            reasoning=reasoning,
            matched_keywords=matched_keywords,
            is_flow_agent=is_flow_agent,
        ),
        organization_id=organization_id,
    )


# ============================================================
# VISUALIZATION ENDPOINT
# ============================================================


@router.get("/visualization", response_model=FlowVisualizationResponse)
async def get_flow_visualization(
    organization_id: str = Query(..., description="Organization UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Get flow visualization data for Vue Flow diagram."""
    org_uuid = _parse_org_id(organization_id)

    # Get all configs
    stmt = select(IntentAgentMapping).where(
        IntentAgentMapping.organization_id == org_uuid,
        IntentAgentMapping.is_enabled == True,  # noqa: E712
    )
    result = await db.execute(stmt)
    mappings = result.scalars().all()

    stmt = select(FlowAgentConfig).where(
        FlowAgentConfig.organization_id == org_uuid,
        FlowAgentConfig.is_enabled == True,  # noqa: E712
    )
    result = await db.execute(stmt)
    flow_configs = result.scalars().all()
    flow_agents = {c.agent_key for c in flow_configs if c.is_flow_agent}

    stmt = select(KeywordAgentMapping).where(
        KeywordAgentMapping.organization_id == org_uuid,
        KeywordAgentMapping.is_enabled == True,  # noqa: E712
    )
    result = await db.execute(stmt)
    keywords = result.scalars().all()

    # Count keywords per agent
    keyword_counts: dict[str, int] = {}
    for kw in keywords:
        keyword_counts[kw.agent_key] = keyword_counts.get(kw.agent_key, 0) + 1

    nodes: list[FlowNode] = []
    edges: list[FlowEdge] = []

    # Create intent nodes
    for mapping in mappings:
        nodes.append(FlowNode(
            id=f"intent_{mapping.intent_key}",
            type="intent",
            label=mapping.intent_name,
            data={
                "intent_key": mapping.intent_key,
                "priority": mapping.priority,
                "confidence_threshold": float(mapping.confidence_threshold),
                "domain_key": mapping.domain_key,
            },
        ))

    # Create agent nodes
    unique_agents = {m.agent_key for m in mappings}
    for agent_key in unique_agents:
        nodes.append(FlowNode(
            id=f"agent_{agent_key}",
            type="agent",
            label=agent_key.replace("_", " ").title(),
            data={
                "agent_key": agent_key,
                "is_flow_agent": agent_key in flow_agents,
                "keyword_count": keyword_counts.get(agent_key, 0),
            },
        ))

    # Create edges
    for mapping in mappings:
        edges.append(FlowEdge(
            id=f"edge_{mapping.intent_key}_{mapping.agent_key}",
            source=f"intent_{mapping.intent_key}",
            target=f"agent_{mapping.agent_key}",
            label=f"{mapping.priority}",
        ))

    return FlowVisualizationResponse(
        nodes=nodes,
        edges=edges,
        organization_id=organization_id,
    )


# ============================================================
# SEED ENDPOINT
# ============================================================


@router.post("/seed", response_model=SeedResponse)
async def seed_from_defaults(
    data: SeedRequest,
    organization_id: str = Query(..., description="Organization UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Seed intent configurations from hardcoded defaults in intent_validator.py.

    This imports:
    - AGENT_TO_INTENT_MAPPING -> intent_agent_mappings
    - FLOW_AGENTS -> flow_agent_configs
    - KEYWORD_TO_AGENT -> keyword_agent_mappings
    """
    org_uuid = _parse_org_id(organization_id)

    # Hardcoded defaults from intent_validator.py
    agent_to_intent_mapping = {
        "excelencia_agent": "excelencia",
        "excelencia_support_agent": "excelencia_soporte",
        "excelencia_invoice_agent": "excelencia_facturacion",
        "excelencia_promotions_agent": "excelencia_promociones",
        "support_agent": "soporte",
        "greeting_agent": "saludo",
        "fallback_agent": "fallback",
        "farewell_agent": "despedida",
        "product_agent": "producto",
        "ecommerce_agent": "ecommerce",
        "data_insights_agent": "datos",
        "pharmacy_operations_agent": "pharmacy",
    }

    flow_agents = {
        "excelencia_support_agent",
        "excelencia_invoice_agent",
        "pharmacy_operations_agent",
    }

    keyword_to_agent = {
        "pharmacy_operations_agent": [
            "receta", "medicamento", "farmacia", "medicamentos", "pedido farmacia",
            "deuda farmacia", "urgente receta", "envié receta", "mandé receta",
        ],
        "excelencia_support_agent": [
            "problema", "error", "falla", "no funciona", "ayuda", "soporte",
            "incidente", "bug", "ticket",
        ],
        "excelencia_invoice_agent": [
            "factura", "facturación", "cobro", "pago", "cuenta", "deuda",
        ],
        "greeting_agent": [
            "hola", "buenos días", "buenas tardes", "buenas noches", "hi", "hello",
        ],
        "farewell_agent": [
            "adiós", "chao", "bye", "hasta luego", "gracias", "nos vemos",
        ],
    }

    mappings_created = 0
    flow_agents_created = 0
    keywords_created = 0

    # Seed intent-agent mappings
    for agent_key, intent_key in agent_to_intent_mapping.items():
        stmt = select(IntentAgentMapping).where(
            IntentAgentMapping.organization_id == org_uuid,
            IntentAgentMapping.intent_key == intent_key,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing and not data.overwrite:
            continue

        if existing:
            await db.delete(existing)

        mapping = IntentAgentMapping(
            organization_id=org_uuid,
            intent_key=intent_key,
            intent_name=intent_key.replace("_", " ").title(),
            agent_key=agent_key,
            priority=50,
            is_enabled=True,
        )
        db.add(mapping)
        mappings_created += 1

    # Seed flow agent configs
    for agent_key in flow_agents:
        stmt = select(FlowAgentConfig).where(
            FlowAgentConfig.organization_id == org_uuid,
            FlowAgentConfig.agent_key == agent_key,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing and not data.overwrite:
            continue

        if existing:
            await db.delete(existing)

        config = FlowAgentConfig(
            organization_id=org_uuid,
            agent_key=agent_key,
            is_flow_agent=True,
            flow_description=f"Multi-turn flow for {agent_key}",
            max_turns=10,
            timeout_seconds=300,
            is_enabled=True,
        )
        db.add(config)
        flow_agents_created += 1

    # Seed keyword mappings
    for agent_key, agent_keywords in keyword_to_agent.items():
        for kw in agent_keywords:
            stmt = select(KeywordAgentMapping).where(
                KeywordAgentMapping.organization_id == org_uuid,
                KeywordAgentMapping.agent_key == agent_key,
                KeywordAgentMapping.keyword == kw,
            )
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing and not data.overwrite:
                continue

            if existing:
                await db.delete(existing)

            keyword = KeywordAgentMapping(
                organization_id=org_uuid,
                agent_key=agent_key,
                keyword=kw,
                match_type="contains",
                case_sensitive=False,
                priority=50,
                is_enabled=True,
            )
            db.add(keyword)
            keywords_created += 1

    await db.commit()

    # Invalidate cache
    await intent_config_cache.invalidate(org_uuid)

    logger.info(
        f"Seeded intent configs for org {org_uuid}: "
        f"{mappings_created} mappings, {flow_agents_created} flow agents, "
        f"{keywords_created} keywords"
    )

    return SeedResponse(
        mappings_created=mappings_created,
        flow_agents_created=flow_agents_created,
        keywords_created=keywords_created,
        organization_id=organization_id,
    )


# ============================================================
# CACHE ENDPOINTS
# ============================================================


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats():
    """Get cache statistics."""
    stats = intent_config_cache.get_stats()
    return CacheStatsResponse(**stats)


@router.post("/cache/invalidate", response_model=CacheInvalidateResponse)
async def invalidate_cache(
    organization_id: str = Query(..., description="Organization UUID"),
):
    """Invalidate cache for an organization."""
    org_uuid = _parse_org_id(organization_id)
    await intent_config_cache.invalidate(org_uuid)

    return CacheInvalidateResponse(
        success=True,
        organization_id=organization_id,
        message="Cache invalidated successfully",
    )


# ============================================================
# COMBINED ENDPOINTS
# ============================================================


@router.get("/all", response_model=AllConfigsResponse)
async def get_all_configs(
    organization_id: str = Query(..., description="Organization UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Get all intent configurations for an organization."""
    org_uuid = _parse_org_id(organization_id)

    # Get all configs
    stmt = select(IntentAgentMapping).where(
        IntentAgentMapping.organization_id == org_uuid
    ).order_by(IntentAgentMapping.priority.desc())
    result = await db.execute(stmt)
    mappings = result.scalars().all()

    stmt = select(FlowAgentConfig).where(
        FlowAgentConfig.organization_id == org_uuid
    )
    result = await db.execute(stmt)
    flow_configs = result.scalars().all()

    stmt = select(KeywordAgentMapping).where(
        KeywordAgentMapping.organization_id == org_uuid
    ).order_by(KeywordAgentMapping.priority.desc())
    result = await db.execute(stmt)
    keywords = result.scalars().all()

    return AllConfigsResponse(
        intent_mappings=[_mapping_to_response(m) for m in mappings],
        flow_agents=[_flow_config_to_response(c) for c in flow_configs],
        keyword_mappings=[_keyword_to_response(k) for k in keywords],
        organization_id=organization_id,
    )
