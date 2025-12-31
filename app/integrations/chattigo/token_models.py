# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Models for Chattigo token storage in Redis.
# ============================================================================
"""
Chattigo Token Models for Redis Storage.

Pydantic models for serializing/deserializing Chattigo JWT tokens in Redis.
Used by ChattigoTokenCache for persistent token storage with tolerance logic.
"""

import time

from pydantic import BaseModel, Field


class ChattigoTokenData(BaseModel):
    """
    Token data stored in Redis for Chattigo JWT tokens.

    Stores the token along with timing information needed for
    the refresh tolerance calculation based on token_refresh_hours.

    Attributes:
        token: The JWT token string from Chattigo ISV
        obtained_at: Unix timestamp when token was obtained
        expiry: Unix timestamp when token expires (obtained_at + TOKEN_TTL_HOURS)
    """

    token: str = Field(..., description="JWT token string from Chattigo ISV")
    obtained_at: float = Field(
        ..., description="Unix timestamp when token was obtained"
    )
    expiry: float = Field(..., description="Unix timestamp when token expires")

    def should_refresh(self, token_refresh_hours: int) -> bool:
        """
        Check if token needs refresh based on tolerance setting.

        The token should be refreshed when:
        current_time >= obtained_at + (token_refresh_hours * 3600)

        This allows the token to be refreshed proactively before expiration,
        based on the token_refresh_hours setting from the database.

        Args:
            token_refresh_hours: Hours before token should be refreshed
                                 (from chattigo_credentials.token_refresh_hours)

        Returns:
            True if token needs refresh, False if still valid
        """
        refresh_at = self.obtained_at + (token_refresh_hours * 3600)
        return time.time() >= refresh_at

    def time_until_refresh(self, token_refresh_hours: int) -> float:
        """
        Calculate seconds until token needs refresh.

        Args:
            token_refresh_hours: Hours before token should be refreshed

        Returns:
            Seconds until refresh needed (negative if already needs refresh)
        """
        refresh_at = self.obtained_at + (token_refresh_hours * 3600)
        return refresh_at - time.time()
