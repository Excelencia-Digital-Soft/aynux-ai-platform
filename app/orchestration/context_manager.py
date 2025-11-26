"""
Context Manager

Manages conversation context across domains and sessions.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ConversationContext:
    """Stores context for a conversation."""

    conversation_id: str
    customer_id: int | None = None
    phone: str | None = None

    # Domain state
    current_domain: str | None = None
    domain_history: list[str] = field(default_factory=list)

    # Intent tracking
    intent_history: list[dict[str, Any]] = field(default_factory=list)
    last_intent: dict[str, Any] | None = None

    # Domain-specific context
    domains: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Shared context
    shared: dict[str, Any] = field(default_factory=dict)

    # Conversation metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    message_count: int = 0
    language: str = "es"

    def touch(self) -> None:
        """Update timestamp."""
        self.updated_at = datetime.now(UTC)

    def add_intent(self, intent: dict[str, Any]) -> None:
        """Add intent to history."""
        self.intent_history.append({
            **intent,
            "timestamp": datetime.now(UTC).isoformat(),
        })
        self.last_intent = intent
        self.touch()

    def switch_domain(self, domain: str) -> None:
        """Switch to a new domain."""
        if self.current_domain != domain:
            self.domain_history.append(domain)
            self.current_domain = domain
            self.touch()

    def get_domain_context(self, domain: str) -> dict[str, Any]:
        """Get context for a specific domain."""
        return self.domains.get(domain, {})

    def set_domain_context(self, domain: str, context: dict[str, Any]) -> None:
        """Set context for a specific domain."""
        self.domains[domain] = context
        self.touch()

    def update_domain_context(self, domain: str, updates: dict[str, Any]) -> None:
        """Update context for a specific domain."""
        if domain not in self.domains:
            self.domains[domain] = {}
        self.domains[domain].update(updates)
        self.touch()

    def get_summary(self) -> dict[str, Any]:
        """Get summary of conversation context."""
        return {
            "conversation_id": self.conversation_id,
            "customer_id": self.customer_id,
            "current_domain": self.current_domain,
            "domains_visited": self.domain_history,
            "message_count": self.message_count,
            "last_intent": self.last_intent,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class ContextManager:
    """
    Manages conversation contexts across the application.

    Provides context storage, retrieval, and cross-domain sharing.

    Example:
        ```python
        manager = ContextManager()

        # Get or create context
        context = manager.get_or_create(
            conversation_id="conv-123",
            customer_id=456,
        )

        # Update domain context
        context.set_domain_context("ecommerce", {
            "cart_items": ["product-1", "product-2"],
        })

        # Switch domains
        context.switch_domain("healthcare")
        ```
    """

    def __init__(
        self,
        ttl_hours: int = 24,
        max_contexts: int = 10000,
    ):
        """
        Initialize context manager.

        Args:
            ttl_hours: Time to live for contexts in hours
            max_contexts: Maximum number of contexts to store
        """
        self.ttl = timedelta(hours=ttl_hours)
        self.max_contexts = max_contexts
        self._contexts: dict[str, ConversationContext] = {}

        logger.info(f"ContextManager initialized (ttl={ttl_hours}h, max={max_contexts})")

    def get(self, conversation_id: str) -> ConversationContext | None:
        """
        Get context by conversation ID.

        Args:
            conversation_id: Conversation identifier

        Returns:
            ConversationContext or None if not found
        """
        context = self._contexts.get(conversation_id)

        if context:
            # Check if expired
            if datetime.now(UTC) - context.updated_at > self.ttl:
                del self._contexts[conversation_id]
                return None
            context.touch()

        return context

    def get_or_create(
        self,
        conversation_id: str,
        customer_id: int | None = None,
        phone: str | None = None,
        **kwargs,
    ) -> ConversationContext:
        """
        Get existing context or create new one.

        Args:
            conversation_id: Conversation identifier
            customer_id: Optional customer ID
            phone: Optional phone number
            **kwargs: Additional context attributes

        Returns:
            ConversationContext
        """
        context = self.get(conversation_id)

        if not context:
            context = ConversationContext(
                conversation_id=conversation_id,
                customer_id=customer_id,
                phone=phone,
                **kwargs,
            )
            self._store(context)

        return context

    def _store(self, context: ConversationContext) -> None:
        """Store context with cleanup if needed."""
        # Cleanup old contexts if at capacity
        if len(self._contexts) >= self.max_contexts:
            self._cleanup()

        self._contexts[context.conversation_id] = context

    def _cleanup(self) -> None:
        """Remove expired contexts."""
        now = datetime.now(UTC)
        expired = [
            cid
            for cid, ctx in self._contexts.items()
            if now - ctx.updated_at > self.ttl
        ]

        for cid in expired:
            del self._contexts[cid]

        # If still at capacity, remove oldest
        if len(self._contexts) >= self.max_contexts:
            sorted_contexts = sorted(
                self._contexts.items(),
                key=lambda x: x[1].updated_at,
            )
            # Remove oldest 10%
            to_remove = max(1, len(sorted_contexts) // 10)
            for cid, _ in sorted_contexts[:to_remove]:
                del self._contexts[cid]

    def delete(self, conversation_id: str) -> bool:
        """
        Delete context.

        Args:
            conversation_id: Conversation identifier

        Returns:
            True if deleted, False if not found
        """
        if conversation_id in self._contexts:
            del self._contexts[conversation_id]
            return True
        return False

    def get_by_customer(self, customer_id: int) -> list[ConversationContext]:
        """Get all contexts for a customer."""
        return [
            ctx for ctx in self._contexts.values()
            if ctx.customer_id == customer_id
        ]

    def get_by_phone(self, phone: str) -> list[ConversationContext]:
        """Get all contexts for a phone number."""
        return [
            ctx for ctx in self._contexts.values()
            if ctx.phone == phone
        ]

    def share_context(
        self,
        from_id: str,
        to_id: str,
        keys: list[str] | None = None,
    ) -> bool:
        """
        Share context between conversations.

        Args:
            from_id: Source conversation ID
            to_id: Target conversation ID
            keys: Specific keys to share (None = all shared context)

        Returns:
            True if successful
        """
        from_ctx = self.get(from_id)
        to_ctx = self.get(to_id)

        if not from_ctx or not to_ctx:
            return False

        if keys:
            for key in keys:
                if key in from_ctx.shared:
                    to_ctx.shared[key] = from_ctx.shared[key]
        else:
            to_ctx.shared.update(from_ctx.shared)

        to_ctx.touch()
        return True

    def get_stats(self) -> dict[str, Any]:
        """Get context manager statistics."""
        now = datetime.now(UTC)

        active_count = sum(
            1 for ctx in self._contexts.values()
            if now - ctx.updated_at < timedelta(minutes=30)
        )

        domains_distribution = {}
        for ctx in self._contexts.values():
            domain = ctx.current_domain or "unknown"
            domains_distribution[domain] = domains_distribution.get(domain, 0) + 1

        return {
            "total_contexts": len(self._contexts),
            "active_contexts": active_count,
            "domains_distribution": domains_distribution,
            "ttl_hours": self.ttl.total_seconds() / 3600,
            "max_contexts": self.max_contexts,
        }


# Global instance
_context_manager: ContextManager | None = None


def get_context_manager() -> ContextManager:
    """Get the global context manager instance."""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager


def reset_context_manager() -> None:
    """Reset the global context manager."""
    global _context_manager
    _context_manager = None
