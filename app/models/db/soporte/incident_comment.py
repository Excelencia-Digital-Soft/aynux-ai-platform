"""
Incident Comment model for tracking comments on incidents.

Comments can be from users, agents, or system-generated.
Includes Jira comment ID for synchronization.
"""

import uuid

from sqlalchemy import Boolean, Column, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import relationship

from ..base import Base, TimestampMixin
from ..schemas import SOPORTE_SCHEMA

# Comment author types
COMMENT_AUTHOR_TYPES = ["user", "agent", "system"]


class IncidentComment(Base, TimestampMixin):
    """
    Comments on incidents.

    Attributes:
        id: Unique identifier (UUID)
        incident_id: FK to incident
        author_type: Type of author (user, agent, system)
        author_name: Name of the author
        content: Comment content
        is_internal: Whether comment is internal-only (not visible to user)
        jira_comment_id: Jira comment ID for sync
    """

    __tablename__ = "incident_comments"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Incident reference
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{SOPORTE_SCHEMA}.incidents.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK to incident",
    )

    # Author info
    author_type = Column(
        ENUM(*COMMENT_AUTHOR_TYPES, name="soporte_comment_author_type_enum", schema=SOPORTE_SCHEMA),
        nullable=False,
        default="user",
        comment="Type of author: user, agent, system",
    )
    author_name = Column(
        String(200),
        nullable=True,
        comment="Name of the author",
    )

    # Content
    content = Column(
        Text,
        nullable=False,
        comment="Comment content",
    )

    # Visibility
    is_internal = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether comment is internal-only (not visible to user)",
    )

    # Jira sync
    jira_comment_id = Column(
        String(50),
        nullable=True,
        comment="Jira comment ID for synchronization",
    )

    # Relationships
    incident = relationship("Incident", backref="comments")

    def __repr__(self) -> str:
        """String representation."""
        preview = self.content[:50] if self.content else ""
        return f"<IncidentComment(id={self.id}, author={self.author_name}, preview='{preview}...')>"

    # Table configuration
    __table_args__ = (
        Index("idx_incident_comments_incident_id", incident_id),
        Index("idx_incident_comments_author_type", author_type),
        Index("idx_incident_comments_created_at", "created_at"),
        {"schema": SOPORTE_SCHEMA},
    )
