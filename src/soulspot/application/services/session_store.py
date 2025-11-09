"""Session management service for storing user sessions and tokens."""

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass
class Session:
    """User session with OAuth tokens and state."""

    session_id: str
    access_token: str | None = None
    refresh_token: str | None = None
    token_expires_at: datetime | None = None
    oauth_state: str | None = None
    code_verifier: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_accessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_expired(self, session_timeout_seconds: int = 3600) -> bool:
        """Check if session is expired.

        Args:
            session_timeout_seconds: Session timeout in seconds (default 1 hour)

        Returns:
            True if session is expired
        """
        expiry_time = self.last_accessed_at + timedelta(seconds=session_timeout_seconds)
        return datetime.now(UTC) >= expiry_time

    def refresh_access(self) -> None:
        """Update last access time."""
        self.last_accessed_at = datetime.now(UTC)

    def is_token_expired(self) -> bool:
        """Check if OAuth token is expired.

        Returns:
            True if token is expired or not set
        """
        if not self.token_expires_at:
            return True
        return datetime.now(UTC) >= self.token_expires_at

    def set_tokens(self, access_token: str, refresh_token: str, expires_in: int) -> None:
        """Set OAuth tokens.

        Args:
            access_token: Access token
            refresh_token: Refresh token
            expires_in: Token expiration time in seconds
        """
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
        self.refresh_access()


class SessionStore:
    """In-memory session store.

    In production, this should be replaced with Redis or a database-backed store.
    """

    def __init__(self, session_timeout_seconds: int = 3600) -> None:
        """Initialize session store.

        Args:
            session_timeout_seconds: Session timeout in seconds (default 1 hour)
        """
        self.session_timeout_seconds = session_timeout_seconds
        self._sessions: dict[str, Session] = {}

    def create_session(self, oauth_state: str | None = None, code_verifier: str | None = None) -> Session:
        """Create a new session.

        Args:
            oauth_state: OAuth state for CSRF protection
            code_verifier: PKCE code verifier

        Returns:
            New session
        """
        session_id = secrets.token_urlsafe(32)
        session = Session(
            session_id=session_id,
            oauth_state=oauth_state,
            code_verifier=code_verifier,
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session if found and not expired, None otherwise
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        if session.is_expired(self.session_timeout_seconds):
            # Clean up expired session
            del self._sessions[session_id]
            return None

        session.refresh_access()
        return session

    def get_session_by_state(self, state: str) -> Session | None:
        """Get session by OAuth state.

        Args:
            state: OAuth state

        Returns:
            Session if found and not expired, None otherwise
        """
        for session in self._sessions.values():
            if session.oauth_state == state and not session.is_expired(self.session_timeout_seconds):
                session.refresh_access()
                return session
        return None

    def update_session(self, session_id: str, **kwargs: Any) -> Session | None:
        """Update session data.

        Args:
            session_id: Session ID
            **kwargs: Fields to update

        Returns:
            Updated session or None if not found
        """
        session = self.get_session(session_id)
        if not session:
            return None

        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)

        session.refresh_access()
        return session

    def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session ID

        Returns:
            True if session was deleted, False if not found
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def cleanup_expired_sessions(self) -> int:
        """Remove all expired sessions.

        Returns:
            Number of sessions removed
        """
        expired_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if session.is_expired(self.session_timeout_seconds)
        ]

        for session_id in expired_ids:
            del self._sessions[session_id]

        return len(expired_ids)

    def count_sessions(self) -> int:
        """Get number of active sessions.

        Returns:
            Number of sessions
        """
        return len(self._sessions)
