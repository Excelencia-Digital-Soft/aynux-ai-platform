"""
TenantPromptManager - Multi-tenant prompt resolution with scope hierarchy.

Implements the prompt resolution hierarchy:
1. USER: User-level overrides within organization (highest priority)
2. ORG: Organization-level customizations
3. GLOBAL: System-wide defaults (in prompts table)
4. SYSTEM: Code-level YAML files (lowest priority)

Usage:
    manager = TenantPromptManager(organization_id=org_id, user_id=user_id)
    prompt = await manager.get_prompt("product.search.intent")
    rendered = await manager.render_prompt("greeting.welcome", name="John")
"""

from __future__ import annotations

import logging
import uuid
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.async_db import get_async_db_context
from app.models.db.prompts import Prompt
from app.models.db.tenancy import TenantPrompt

from .context import get_tenant_context

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class PromptScope(str, Enum):
    """Prompt resolution scope hierarchy."""

    USER = "user"  # User-level overrides (highest priority)
    ORG = "org"  # Organization-level customizations
    GLOBAL = "global"  # System-wide defaults (prompts table)
    SYSTEM = "system"  # Code-level YAML files (lowest priority)


class PromptNotFoundError(Exception):
    """Raised when a prompt cannot be found in any scope."""

    pass


class TenantPromptManager:
    """
    Multi-tenant prompt manager with scope hierarchy.

    Resolves prompts in order of priority:
    1. User-level overrides (TenantPrompt with scope='user')
    2. Organization-level overrides (TenantPrompt with scope='org')
    3. Global defaults (Prompt table)
    4. System YAML files (via PromptRegistry)

    Supports:
    - Variable substitution with {variable} placeholders
    - Prompt versioning and metadata
    - Caching for performance
    - Scope-aware prompt management

    Example:
        >>> manager = TenantPromptManager(organization_id=org_id)
        >>> prompt = await manager.get_prompt("product.search.intent")
        >>> rendered = await manager.render_prompt(
        ...     "greeting.welcome",
        ...     name="John",
        ...     company="Acme"
        ... )
    """

    # Cache for prompt lookups (per-request, cleared on context change)
    _cache: dict[str, tuple[str, PromptScope]] = {}

    def __init__(
        self,
        organization_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        db_session: AsyncSession | None = None,
        enable_cache: bool = True,
    ):
        """
        Initialize tenant prompt manager.

        Args:
            organization_id: Organization UUID (uses TenantContext if None).
            user_id: User UUID for user-scope resolution.
            db_session: AsyncSession for database operations.
            enable_cache: Whether to enable prompt caching.
        """
        self._organization_id = organization_id
        self._user_id = user_id
        self._db_session = db_session
        self._enable_cache = enable_cache
        self._local_cache: dict[str, tuple[str, PromptScope, dict]] = {}

    @property
    def organization_id(self) -> uuid.UUID | None:
        """Get organization ID from context or explicit setting."""
        if self._organization_id:
            return self._organization_id

        ctx = get_tenant_context()
        if ctx:
            return ctx.organization_id

        return None

    @property
    def user_id(self) -> uuid.UUID | None:
        """Get user ID from context or explicit setting."""
        if self._user_id:
            return self._user_id

        ctx = get_tenant_context()
        if ctx:
            return ctx.user_id

        return None

    def _get_cache_key(self, prompt_key: str) -> str:
        """Generate cache key including tenant context."""
        org_id = self.organization_id or "system"
        user_id = self.user_id or "none"
        return f"{org_id}:{user_id}:{prompt_key}"

    async def get_prompt(
        self,
        prompt_key: str,
        *,
        max_scope: PromptScope | None = None,
        include_metadata: bool = False,
    ) -> str | tuple[str, dict]:
        """
        Get prompt template by key, resolving through scope hierarchy.

        Args:
            prompt_key: Prompt identifier (e.g., "product.search.intent").
            max_scope: Maximum scope to check (limits resolution depth).
            include_metadata: If True, return (template, metadata) tuple.

        Returns:
            Prompt template string, or (template, metadata) if include_metadata.

        Raises:
            PromptNotFoundError: If prompt not found in any scope.

        Example:
            >>> template = await manager.get_prompt("greeting.welcome")
            >>> template, meta = await manager.get_prompt(
            ...     "greeting.welcome",
            ...     include_metadata=True
            ... )
        """
        cache_key = self._get_cache_key(prompt_key)

        # Check cache
        if self._enable_cache and cache_key in self._local_cache:
            template, scope, metadata = self._local_cache[cache_key]
            return (template, metadata) if include_metadata else template

        # Resolve through hierarchy
        template, scope, metadata = await self._resolve_prompt(prompt_key, max_scope)

        if template is None:
            raise PromptNotFoundError(
                f"Prompt '{prompt_key}' not found in any scope. "
                f"Checked: USER → ORG → GLOBAL → SYSTEM"
            )

        # Cache result
        if self._enable_cache:
            self._local_cache[cache_key] = (template, scope, metadata)

        logger.debug(f"Resolved prompt '{prompt_key}' from scope: {scope.value}")

        return (template, metadata) if include_metadata else template

    async def render_prompt(
        self,
        prompt_key: str,
        **variables: Any,
    ) -> str:
        """
        Get and render prompt with variable substitution.

        Args:
            prompt_key: Prompt identifier.
            **variables: Variables to substitute in template.

        Returns:
            Rendered prompt string.

        Example:
            >>> rendered = await manager.render_prompt(
            ...     "greeting.welcome",
            ...     name="John",
            ...     company="Acme Corp"
            ... )
        """
        result = await self.get_prompt(prompt_key)
        # get_prompt without include_metadata always returns str
        template = str(result) if not isinstance(result, str) else result

        try:
            return template.format(**variables)
        except KeyError as e:
            logger.warning(
                f"Missing variable in prompt '{prompt_key}': {e}. "
                f"Available variables: {list(variables.keys())}"
            )
            # Return template with missing variables as-is
            return template.format_map(SafeDict(variables))

    async def _resolve_prompt(
        self,
        prompt_key: str,
        max_scope: PromptScope | None = None,
    ) -> tuple[str | None, PromptScope, dict]:
        """
        Resolve prompt through scope hierarchy.

        Args:
            prompt_key: Prompt identifier.
            max_scope: Maximum scope to check.

        Returns:
            Tuple of (template, scope, metadata) or (None, SYSTEM, {}).
        """
        org_id = self.organization_id
        user_id = self.user_id

        # Define resolution order
        scopes_to_check = [
            PromptScope.USER,
            PromptScope.ORG,
            PromptScope.GLOBAL,
            PromptScope.SYSTEM,
        ]

        # Filter by max_scope if specified
        if max_scope:
            try:
                max_idx = scopes_to_check.index(max_scope)
                scopes_to_check = scopes_to_check[: max_idx + 1]
            except ValueError:
                pass

        async with get_async_db_context() as db:
            for scope in scopes_to_check:
                result = await self._check_scope(db, prompt_key, scope, org_id, user_id)
                if result:
                    return result

        return None, PromptScope.SYSTEM, {}

    async def _check_scope(
        self,
        db: AsyncSession,
        prompt_key: str,
        scope: PromptScope,
        org_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
    ) -> tuple[str, PromptScope, dict] | None:
        """
        Check a specific scope for the prompt.

        Args:
            db: Database session.
            prompt_key: Prompt identifier.
            scope: Scope to check.
            org_id: Organization UUID.
            user_id: User UUID.

        Returns:
            Tuple of (template, scope, metadata) or None.
        """
        if scope == PromptScope.USER:
            if not org_id or not user_id:
                return None

            stmt = select(TenantPrompt).where(
                TenantPrompt.organization_id == org_id,
                TenantPrompt.prompt_key == prompt_key,
                TenantPrompt.scope == "user",
                TenantPrompt.user_id == user_id,
                TenantPrompt.is_active == True,  # noqa: E712
            )
            result = await db.execute(stmt)
            tenant_prompt = result.scalar_one_or_none()

            if tenant_prompt:
                return (
                    str(tenant_prompt.template),
                    PromptScope.USER,
                    dict(tenant_prompt.meta_data) if tenant_prompt.meta_data else {},
                )

        elif scope == PromptScope.ORG:
            if not org_id:
                return None

            stmt = select(TenantPrompt).where(
                TenantPrompt.organization_id == org_id,
                TenantPrompt.prompt_key == prompt_key,
                TenantPrompt.scope == "org",
                TenantPrompt.is_active == True,  # noqa: E712
            )
            result = await db.execute(stmt)
            tenant_prompt = result.scalar_one_or_none()

            if tenant_prompt:
                return (
                    str(tenant_prompt.template),
                    PromptScope.ORG,
                    dict(tenant_prompt.meta_data) if tenant_prompt.meta_data else {},
                )

        elif scope == PromptScope.GLOBAL:
            stmt = select(Prompt).where(
                Prompt.key == prompt_key,
                Prompt.is_active == True,  # noqa: E712
            )
            result = await db.execute(stmt)
            prompt = result.scalar_one_or_none()

            if prompt:
                return (
                    str(prompt.template),
                    PromptScope.GLOBAL,
                    dict(prompt.meta_data) if prompt.meta_data else {},
                )

        elif scope == PromptScope.SYSTEM:
            # Try to validate key exists in PromptRegistry
            # Note: PromptRegistry only contains key constants, not actual templates
            # System-level prompts would come from YAML files loaded separately
            from app.prompts.registry import PromptRegistry

            try:
                if PromptRegistry.validate_key(prompt_key):
                    # Key exists in registry, but template loading would require
                    # a separate YAML loader implementation
                    logger.debug(f"Key '{prompt_key}' exists in PromptRegistry but template loading not implemented")
            except Exception as e:
                logger.debug(f"System prompt lookup failed for '{prompt_key}': {e}")

        return None

    async def set_prompt(
        self,
        prompt_key: str,
        template: str,
        scope: PromptScope = PromptScope.ORG,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> bool:
        """
        Create or update a prompt override.

        Args:
            prompt_key: Prompt identifier.
            template: Prompt template text.
            scope: Override scope (USER or ORG).
            description: Description of the prompt.
            metadata: Additional metadata.

        Returns:
            True if successful.

        Raises:
            ValueError: If trying to set GLOBAL or SYSTEM scope.
        """
        if scope in (PromptScope.GLOBAL, PromptScope.SYSTEM):
            raise ValueError(
                f"Cannot set prompt at scope {scope}. "
                "Use ORG or USER scope for tenant overrides."
            )

        org_id = self.organization_id
        if not org_id:
            raise ValueError("Organization ID required to set prompt override")

        user_id = self.user_id if scope == PromptScope.USER else None
        if scope == PromptScope.USER and not user_id:
            raise ValueError("User ID required for USER scope prompt")

        try:
            async with get_async_db_context() as db:
                # Check for existing prompt
                stmt = select(TenantPrompt).where(
                    TenantPrompt.organization_id == org_id,
                    TenantPrompt.prompt_key == prompt_key,
                    TenantPrompt.scope == scope.value,
                )
                # Add user_id filter for USER scope
                if scope == PromptScope.USER:
                    stmt = stmt.where(TenantPrompt.user_id == user_id)

                result = await db.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    # Update existing
                    existing.template = template
                    if description:
                        existing.description = description
                    if metadata:
                        existing.meta_data = metadata
                else:
                    # Create new
                    if scope == PromptScope.USER and user_id is not None:
                        new_prompt = TenantPrompt.create_user_override(
                            organization_id=org_id,
                            user_id=user_id,
                            prompt_key=prompt_key,
                            template=template,
                            description=description,
                            meta_data=metadata,
                        )
                    else:
                        new_prompt = TenantPrompt.create_org_override(
                            organization_id=org_id,
                            prompt_key=prompt_key,
                            template=template,
                            description=description,
                            meta_data=metadata,
                        )
                    db.add(new_prompt)

                await db.commit()

                # Invalidate cache
                cache_key = self._get_cache_key(prompt_key)
                self._local_cache.pop(cache_key, None)

                logger.info(f"Set prompt '{prompt_key}' at scope {scope.value}")
                return True

        except Exception as e:
            logger.error(f"Error setting prompt '{prompt_key}': {e}")
            return False

    async def delete_prompt(
        self,
        prompt_key: str,
        scope: PromptScope = PromptScope.ORG,
    ) -> bool:
        """
        Delete a prompt override (reverts to lower scope).

        Args:
            prompt_key: Prompt identifier.
            scope: Scope of override to delete.

        Returns:
            True if deleted, False if not found.
        """
        org_id = self.organization_id
        if not org_id:
            return False

        user_id = self.user_id if scope == PromptScope.USER else None

        try:
            async with get_async_db_context() as db:
                stmt = select(TenantPrompt).where(
                    TenantPrompt.organization_id == org_id,
                    TenantPrompt.prompt_key == prompt_key,
                    TenantPrompt.scope == scope.value,
                )
                if scope == PromptScope.USER:
                    stmt = stmt.where(TenantPrompt.user_id == user_id)

                result = await db.execute(stmt)
                prompt = result.scalar_one_or_none()

                if prompt:
                    await db.delete(prompt)
                    await db.commit()

                    # Invalidate cache
                    cache_key = self._get_cache_key(prompt_key)
                    self._local_cache.pop(cache_key, None)

                    logger.info(f"Deleted prompt '{prompt_key}' from scope {scope.value}")
                    return True

                return False

        except Exception as e:
            logger.error(f"Error deleting prompt '{prompt_key}': {e}")
            return False

    async def list_prompts(
        self,
        scope: PromptScope | None = None,
    ) -> list[dict]:
        """
        List all prompts available to this tenant.

        Args:
            scope: Filter by scope (None for all scopes).

        Returns:
            List of prompt dictionaries with key, template, scope, etc.
        """
        org_id = self.organization_id
        user_id = self.user_id
        prompts = []

        async with get_async_db_context() as db:
            # User-level prompts
            if scope in (None, PromptScope.USER) and org_id and user_id:
                stmt = select(TenantPrompt).where(
                    TenantPrompt.organization_id == org_id,
                    TenantPrompt.scope == "user",
                    TenantPrompt.user_id == user_id,
                    TenantPrompt.is_active == True,  # noqa: E712
                )
                result = await db.execute(stmt)
                for p in result.scalars():
                    prompts.append({
                        "key": p.prompt_key,
                        "scope": PromptScope.USER.value,
                        "template": p.template,
                        "description": p.description,
                        "version": p.version,
                        "metadata": p.meta_data,
                    })

            # Org-level prompts
            if scope in (None, PromptScope.ORG) and org_id:
                stmt = select(TenantPrompt).where(
                    TenantPrompt.organization_id == org_id,
                    TenantPrompt.scope == "org",
                    TenantPrompt.is_active == True,  # noqa: E712
                )
                result = await db.execute(stmt)
                for p in result.scalars():
                    prompts.append({
                        "key": p.prompt_key,
                        "scope": PromptScope.ORG.value,
                        "template": p.template,
                        "description": p.description,
                        "version": p.version,
                        "metadata": p.meta_data,
                    })

            # Global prompts
            if scope in (None, PromptScope.GLOBAL):
                stmt = select(Prompt).where(Prompt.is_active == True)  # noqa: E712
                result = await db.execute(stmt)
                for p in result.scalars():
                    prompts.append({
                        "key": p.key,
                        "scope": PromptScope.GLOBAL.value,
                        "template": p.template,
                        "description": p.description,
                        "version": p.version,
                        "metadata": p.meta_data,
                    })

        return prompts

    def clear_cache(self) -> None:
        """Clear the local prompt cache."""
        self._local_cache.clear()
        logger.debug("Prompt cache cleared")


class SafeDict(dict):
    """Dict that returns {key} for missing keys during format_map."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"
