"""
Pydantic schemas for prompt management API.

Request/Response models for admin prompt endpoints.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

# ===== REQUEST MODELS =====


class PromptCreateRequest(BaseModel):
    """Request para crear un prompt."""

    key: str = Field(..., description="Clave única del prompt (ej: product.search.custom)")
    name: str = Field(..., description="Nombre descriptivo")
    template: str = Field(..., description="Template del prompt con {variables}")
    description: str | None = Field(None, description="Descripción opcional")
    metadata: dict[str, Any] | None = Field(default_factory=dict, description="Metadata adicional")


class PromptUpdateRequest(BaseModel):
    """Request para actualizar un prompt."""

    name: str | None = Field(None, description="Nuevo nombre")
    template: str | None = Field(None, description="Nuevo template")
    description: str | None = Field(None, description="Nueva descripción")
    metadata: dict[str, Any] | None = Field(None, description="Nueva metadata")


class RollbackRequest(BaseModel):
    """Request para hacer rollback."""

    version_id: str = Field(..., description="ID de la versión a restaurar")


# ===== RESPONSE MODELS =====


class PromptMetadataResponse(BaseModel):
    """Metadata structure for frontend compatibility."""

    temperature: float = 0.7
    max_tokens: int = 2048
    model: str = "default"
    tags: list[str] = []
    variables: dict[str, list[str]] = {"required": [], "optional": []}
    domain: str = ""


class PromptResponse(BaseModel):
    """Response con información de un prompt."""

    key: str
    name: str
    description: str = ""
    version: str
    template: str
    metadata: PromptMetadataResponse
    source: str = "file"  # "database" or "file"
    active: bool = True  # Frontend expects "active" not "is_active"
    status: Literal["active", "placeholder", "missing"] = "active"
    locked_by: str | None = None
    locked_at: str | None = None
    tenant_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @staticmethod
    def _extract_domain(key: str) -> str:
        """Extract domain from prompt key (first segment before dot)."""
        return key.split(".")[0] if key else ""

    @staticmethod
    def _normalize_variables(raw_variables: dict | list | None) -> dict[str, list[str]]:
        """Normalize variables to standard format with required/optional keys."""
        if isinstance(raw_variables, list):
            return {"required": raw_variables, "optional": []}
        if isinstance(raw_variables, dict):
            return {
                "required": raw_variables.get("required", []),
                "optional": raw_variables.get("optional", []),
            }
        return {"required": [], "optional": []}

    @staticmethod
    def _normalize_tags(tags: Any) -> list[str]:
        """Normalize tags to list format."""
        if isinstance(tags, list):
            return tags
        return [tags] if tags else []

    @staticmethod
    def _determine_status(template: str, tags: list[str]) -> Literal["active", "placeholder", "missing"]:
        """Determine prompt status based on template content and tags."""
        if not template:
            return "missing"
        # Check for placeholder indicators
        if "[PLACEHOLDER" in template or "placeholder" in tags:
            return "placeholder"
        return "active"

    @classmethod
    def from_prompt_dict(cls, prompt: dict[str, Any]) -> "PromptResponse":
        """Convert internal prompt dict to frontend-compatible response."""
        key = prompt.get("key", "")
        domain = cls._extract_domain(key)
        raw_metadata = prompt.get("metadata", {}) or {}
        template = prompt.get("template", "")
        tags = cls._normalize_tags(raw_metadata.get("tags", []))

        metadata = PromptMetadataResponse(
            temperature=float(raw_metadata.get("temperature", 0.7)),
            max_tokens=int(raw_metadata.get("max_tokens", 2048)),
            model=str(raw_metadata.get("model", "default")),
            tags=tags,
            variables=cls._normalize_variables(raw_metadata.get("variables")),
            domain=raw_metadata.get("domain", domain),
        )

        status = cls._determine_status(template, tags)

        return cls(
            key=key,
            name=prompt.get("name", key),
            description=prompt.get("description") or "",
            version=prompt.get("version", "1.0.0"),
            template=template,
            metadata=metadata,
            source=prompt.get("source", "file"),
            active=prompt.get("is_active", True),
            status=status,
            locked_by=None,
            locked_at=None,
            tenant_id=None,
            created_at=prompt.get("created_at"),
            updated_at=prompt.get("updated_at"),
        )


class PromptListResponse(BaseModel):
    """Response con lista de prompts paginada."""

    items: list[PromptResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PromptVersionResponse(BaseModel):
    """Response con información de una versión."""

    id: str
    prompt_id: str
    version: str
    template: str
    performance_metrics: dict[str, Any]
    is_active: bool
    created_at: str
    created_by: str | None
    notes: str | None


class LockStatusResponse(BaseModel):
    """Response for lock status."""

    locked: bool = False
    locked_by: str | None = None
    locked_at: str | None = None
    expires_at: str | None = None


class StatsResponse(BaseModel):
    """Response con estadísticas del sistema."""

    cache_stats: dict[str, Any]
    registry_info: dict[str, Any]
    system_info: dict[str, Any]


# ===== ANALYTICS MODELS =====


class TemplateUsage(BaseModel):
    """Usage data for a template."""

    prompt_key: str
    usage_count: int


class RecentChange(BaseModel):
    """Recent change entry."""

    prompt_key: str
    changed_at: str
    changed_by: str
    change_type: str  # 'created' | 'updated' | 'deleted'


class AnalyticsResponse(BaseModel):
    """Response with YAML prompt analytics."""

    total_prompts: int
    active_prompts: int
    domains_count: dict[str, int]
    most_used_templates: list[TemplateUsage]
    recent_changes: list[RecentChange]
