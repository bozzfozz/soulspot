"""Session management service for storing user sessions and tokens."""

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


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

    # Hey future me, this checks if the SESSION is expired (inactive too long), NOT the OAuth token!
    # Sessions expire based on last_accessed_at, which gets updated on every request. Default is 1 hour
    # of inactivity. If a user closes their browser and comes back 2 hours later, session is GONE and
    # they need to re-auth. This is SEPARATE from token expiry - tokens expire in 1 hour regardless of
    # activity! Don't confuse these two timeouts!
    def is_expired(self, session_timeout_seconds: int = 3600) -> bool:
        """Check if session is expired.

        Args:
            session_timeout_seconds: Session timeout in seconds (default 1 hour)

        Returns:
            True if session is expired
        """
        expiry_time = self.last_accessed_at + timedelta(seconds=session_timeout_seconds)
        return datetime.now(UTC) >= expiry_time

    # Yo, this "refreshes" the session by updating last_accessed_at to NOW. We call this on EVERY
    # request that uses the session, so the session stays alive as long as user is active. This is
    # why you can keep using the app all day without re-auth - each API call resets the timeout!
    def refresh_access(self) -> None:
        """Update last access time."""
        self.last_accessed_at = datetime.now(UTC)

    # Listen up, this checks if the OAUTH TOKEN is expired, NOT the session! Spotify tokens expire
    # after 1 hour ALWAYS, even if you're actively using the app. If this returns True, you need to
    # call refresh_token endpoint to get a new access_token using the refresh_token. If token_expires_at
    # is None, we assume expired (safe default). Always check this before making Spotify API calls!
    def is_token_expired(self) -> bool:
        """Check if OAuth token is expired.

        Returns:
            True if token is expired or not set
        """
        if not self.token_expires_at:
            return True
        return datetime.now(UTC) >= self.token_expires_at

    # Hey, this updates the OAuth tokens AND refreshes session access time. The expires_in is in SECONDS
    # (usually 3600 = 1 hour). We calculate token_expires_at from NOW + expires_in. Important: Spotify
    # sometimes returns a NEW refresh_token, sometimes the SAME one - we store whatever they give us.
    # If access_token is None or empty, that's weird but we store it anyway - let calling code handle it.
    def set_tokens(
        self, access_token: str, refresh_token: str, expires_in: int
    ) -> None:
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

    # Yo future me, this is IN-MEMORY storage! If the server restarts, ALL SESSIONS ARE GONE and every
    # user has to re-auth. That's fine for dev/testing but SUCKS in production. The dict key is the
    # session_id (random 32-byte urlsafe string). In production, replace this with Redis (fast!) or
    # DB (persistent). If you have multiple app servers, in-memory won't work - sessions won't be shared!
    # The timeout default is 1 hour - probably should be configurable via Settings.
    def __init__(self, session_timeout_seconds: int = 3600) -> None:
        """Initialize session store.

        Args:
            session_timeout_seconds: Session timeout in seconds (default 1 hour)
        """
        self.session_timeout_seconds = session_timeout_seconds
        self._sessions: dict[str, Session] = {}

    # Hey, we generate a cryptographically random session_id using secrets (NOT random module - that's
    # not crypto-safe!). The session starts with oauth_state and code_verifier because we create the
    # session BEFORE redirecting to Spotify. We need to store these for CSRF verification later. The
    # session doesn't have tokens yet - those come after OAuth callback when we exchange the code.
    def create_session(
        self, oauth_state: str | None = None, code_verifier: str | None = None
    ) -> Session:
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

    # Listen up, this does THREE things: 1) Fetch session from dict, 2) Check if expired (auto-cleanup
    # if yes!), 3) Refresh access time if not expired. This means EVERY session lookup that succeeds
    # resets the timeout - sessions stay alive as long as they're used! The auto-cleanup on expiry is
    # nice but means expired sessions leak memory until accessed. Run cleanup_expired_sessions periodically!
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

    # Yo, this is for OAuth callback - Spotify returns the state parameter, we need to find which session
    # it belongs to. This is a LINEAR SEARCH through all sessions - O(n)! If you have thousands of concurrent
    # users, this will be SLOW. Consider using a second index (dict[state, session_id]) for O(1) lookup.
    # We also check expiry and refresh access here. Only returns if state MATCHES and not expired.
    def get_session_by_state(self, state: str) -> Session | None:
        """Get session by OAuth state.

        Args:
            state: OAuth state

        Returns:
            Session if found and not expired, None otherwise
        """
        for session in self._sessions.values():
            if session.oauth_state == state and not session.is_expired(
                self.session_timeout_seconds
            ):
                session.refresh_access()
                return session
        return None

    # Hey, this is a generic update method using **kwargs - updates any session fields dynamically. We
    # use hasattr check to prevent injecting random attributes. This refreshes access time too, so
    # updating a session keeps it alive. If session doesn't exist or is expired, returns None. Be careful
    # what you pass in kwargs - no validation here beyond "does the attribute exist"!
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

    # Yo, delete is simple - remove from dict. Returns True if found+deleted, False if not found. This
    # is idempotent - safe to call multiple times. We don't invalidate the session_id cookie here - that's
    # the API layer's job! If you delete a session but forget to delete cookie, the cookie will keep
    # getting sent but lookups will fail (user appears logged out).
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

    # Listen future me, this is your MEMORY LEAK PREVENTION! Expired sessions don't auto-delete except
    # when accessed via get_session. If sessions are created but never accessed again, they leak memory
    # FOREVER. Run this periodically (every 5 minutes?) in a background task. Returns count of sessions
    # deleted - if this number is huge, your timeout might be too short or you have lots of abandoned sessions.
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

    # Hey, this is for monitoring/debugging - how many active sessions do we have? Useful for capacity
    # planning (each session is ~1KB of memory) and debugging (sessions growing without bound = leak!).
    # This counts ALL sessions including expired ones that haven't been cleaned up yet!
    def count_sessions(self) -> int:
        """Get number of active sessions.

        Returns:
            Number of sessions
        """
        return len(self._sessions)


# Hey future me, DatabaseSessionStore is THE SOLUTION to the Docker restart bug! It persists
# sessions to SQLite instead of RAM. Each method is ASYNC and uses SessionRepository for DB ops.
# The in-memory dict (_sessions) acts as a WRITE-THROUGH CACHE - reads check memory first (fast!),
# writes go to BOTH memory and DB. When app restarts, we LOAD sessions from DB on first access.
# This is backward compatible with SessionStore - just swap dependencies to use this class instead!
class DatabaseSessionStore:
    """Database-backed session store with persistence across restarts.

    Uses SessionRepository to persist sessions to database, solving the
    "re-authenticate after Docker restart" problem. Provides async
    interface for all operations.
    """

    def __init__(
        self,
        session_timeout_seconds: int = 3600,
        get_db_session: Any | None = None,
    ) -> None:
        """Initialize database-backed session store.

        Args:
            session_timeout_seconds: Session timeout in seconds
            get_db_session: Async function that returns AsyncSession for DB ops
        """
        self.session_timeout_seconds = session_timeout_seconds
        self._get_db_session = get_db_session
        self._sessions: dict[str, Session] = {}  # In-memory cache
        self._db_loaded = False  # Track if we've loaded sessions from DB yet

    # Yo, this loads ALL non-expired sessions from DB into memory cache on first call! We do this
    # LAZY (not in __init__) because __init__ is sync but DB is async. After first load, _db_loaded
    # is True and we skip this. This means the FIRST request after restart might be slow (loads all
    # sessions) but subsequent requests are fast (memory cache). If you have 10k+ sessions, this could
    # be a problem - consider paginated loading or on-demand loading per session_id instead!
    async def _ensure_loaded(self) -> None:
        """Mark sessions as ready for on-demand loading.

        Sessions are loaded on-demand when accessed, not all at once.
        This flag prevents attempting to pre-load all sessions, which
        could be expensive with many sessions. Each session is fetched
        from the database individually when requested if not in cache.
        """
        if self._db_loaded or not self._get_db_session:
            return

        # Sessions are loaded on-demand in get_session() and get_session_by_state()
        # when not found in memory cache. This is more efficient than loading all
        # sessions upfront, especially after restart with many sessions.
        self._db_loaded = True

    # Hey, create() now writes to BOTH memory and DB! The in-memory write is sync (fast), the DB
    # write is async (slower but persistent). If DB write fails, session still exists in memory
    # until restart. We commit the DB session here - each create is its own transaction. If you're
    # creating many sessions rapidly, consider batching commits for performance!
    async def create_session(
        self, oauth_state: str | None = None, code_verifier: str | None = None
    ) -> Session:
        """Create a new session with database persistence.

        Args:
            oauth_state: OAuth state for CSRF protection
            code_verifier: PKCE code verifier

        Returns:
            New session
        """
        # Create session object
        session_id = secrets.token_urlsafe(32)
        session = Session(
            session_id=session_id,
            oauth_state=oauth_state,
            code_verifier=code_verifier,
        )

        # Store in memory cache
        self._sessions[session_id] = session

        # Persist to database (async, survives restarts)
        if self._get_db_session:
            from soulspot.infrastructure.persistence.repositories import (
                SessionRepository,
            )

            async for db_session in self._get_db_session():
                try:
                    repo = SessionRepository(db_session)
                    await repo.create(session)
                    await db_session.commit()
                except Exception:
                    # Don't fail the request if DB write fails - session still works in memory
                    await db_session.rollback()
                finally:
                    await db_session.close()
                break

        return session

    # Listen up, get() checks memory FIRST (fast!), then DB if not in memory (restart scenario).
    # If found in DB, we load it into memory cache for next time. This implements a WRITE-THROUGH
    # cache pattern - reads are fast after first access, writes always hit DB. The DB update of
    # last_accessed_at happens on EVERY get - this keeps sessions alive in DB! Commit happens here.
    async def get_session(self, session_id: str) -> Session | None:
        """Get session by ID from memory or database.

        Args:
            session_id: Session identifier

        Returns:
            Session if found and not expired, None otherwise
        """
        await self._ensure_loaded()

        # Check memory cache first
        session = self._sessions.get(session_id)
        if session:
            # Check if expired in memory
            if session.is_expired(self.session_timeout_seconds):
                # Clean up expired session from memory
                del self._sessions[session_id]
                session = None
            else:
                # Refresh access time
                session.refresh_access()

        if session:
            # Update in DB too (refresh last_accessed_at)
            if self._get_db_session:
                from soulspot.infrastructure.persistence.repositories import (
                    SessionRepository,
                )

                async for db_session in self._get_db_session():
                    try:
                        repo = SessionRepository(db_session)
                        await repo.get(session_id)  # This updates last_accessed_at
                        await db_session.commit()
                    except Exception:
                        await db_session.rollback()
                    finally:
                        await db_session.close()
                    break
            return session

        # Not in memory - check DB (restart scenario)
        if self._get_db_session:
            from soulspot.infrastructure.persistence.repositories import (
                SessionRepository,
            )

            async for db_session in self._get_db_session():
                try:
                    repo = SessionRepository(db_session)
                    session = await repo.get(session_id)
                    await db_session.commit()

                    if session and not session.is_expired(self.session_timeout_seconds):
                        # Load into memory cache for next time
                        self._sessions[session_id] = session
                        return session
                except Exception:
                    await db_session.rollback()
                finally:
                    await db_session.close()
                break

        return None

    # Yo, get_by_state() is for OAuth callback - find session by state param. We check memory first,
    # then DB. This is CRITICAL for the auth flow - if we can't find the session, auth fails! The
    # state is temporary (only used during OAuth flow), so it's usually in memory. But after restart,
    # we need to check DB. Linear search in both memory and DB - not ideal for scale but fine for
    # single-user app. If you have 1000s of concurrent auth flows, add index on oauth_state!
    async def get_session_by_state(self, state: str) -> Session | None:
        """Get session by OAuth state from memory or database.

        Args:
            state: OAuth state parameter

        Returns:
            Session if found and not expired, None otherwise
        """
        await self._ensure_loaded()

        # Check memory first (linear search through sessions)
        for session in self._sessions.values():
            if session.oauth_state == state and not session.is_expired(
                self.session_timeout_seconds
            ):
                session.refresh_access()
                return session

        # Not in memory - check DB
        if self._get_db_session:
            from soulspot.infrastructure.persistence.repositories import (
                SessionRepository,
            )

            async for db_session in self._get_db_session():
                try:
                    repo = SessionRepository(db_session)
                    db_session_result = await repo.get_by_oauth_state(state)
                    await db_session.commit()

                    if (
                        db_session_result
                        and not db_session_result.is_expired(self.session_timeout_seconds)
                    ):
                        # Load into memory cache
                        self._sessions[db_session_result.session_id] = db_session_result
                        return db_session_result
                except Exception:
                    await db_session.rollback()
                finally:
                    await db_session.close()
                break

        return None

    # Hey, update() modifies session in BOTH memory and DB! The memory update is fast, DB update
    # is persistent. We use **kwargs for flexibility - can update any session field. This also
    # refreshes last_accessed_at in DB. If session doesn't exist, returns None (not an error).
    # Commit happens here - each update is atomic!
    async def update_session(self, session_id: str, **kwargs: Any) -> Session | None:
        """Update session in memory and database.

        Args:
            session_id: Session identifier
            **kwargs: Fields to update

        Returns:
            Updated session or None if not found
        """
        # Update in memory - get session first
        session = self._sessions.get(session_id)
        if not session:
            return None

        if session.is_expired(self.session_timeout_seconds):
            # Clean up expired session
            del self._sessions[session_id]
            return None

        # Update fields
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)

        session.refresh_access()

        # Update in DB
        if self._get_db_session:
            from soulspot.infrastructure.persistence.repositories import (
                SessionRepository,
            )

            async for db_session in self._get_db_session():
                try:
                    repo = SessionRepository(db_session)
                    await repo.update(session_id, **kwargs)
                    await db_session.commit()
                except Exception:
                    await db_session.rollback()
                finally:
                    await db_session.close()
                break

        return session

    # Listen up, delete() removes from BOTH memory and DB! Memory delete is fast, DB delete is
    # permanent. This is idempotent - safe to call multiple times even if session doesn't exist.
    # Returns True if deleted from either location. Commit happens here - deletion is atomic!
    async def delete_session(self, session_id: str) -> bool:
        """Delete session from memory and database.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        # Delete from memory
        memory_deleted = False
        if session_id in self._sessions:
            del self._sessions[session_id]
            memory_deleted = True

        # Delete from DB
        db_deleted = False
        if self._get_db_session:
            from soulspot.infrastructure.persistence.repositories import (
                SessionRepository,
            )

            async for db_session in self._get_db_session():
                try:
                    repo = SessionRepository(db_session)
                    db_deleted = await repo.delete(session_id)
                    await db_session.commit()
                except Exception:
                    await db_session.rollback()
                finally:
                    await db_session.close()
                break

        return memory_deleted or db_deleted

    # Yo, cleanup() removes expired sessions from BOTH memory and DB! This is CRITICAL for preventing
    # table bloat. The DB cleanup is a single DELETE query (efficient!), memory cleanup is a loop.
    # Returns total count from both locations. Run this every 5-10 minutes in a background task!
    # If you forget, sessions table grows forever = disk full = bad times!
    async def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions from memory and database.

        Returns:
            Total number of sessions removed
        """
        # Cleanup memory
        expired_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if session.is_expired(self.session_timeout_seconds)
        ]

        for session_id in expired_ids:
            del self._sessions[session_id]

        memory_count = len(expired_ids)

        # Cleanup DB
        db_count = 0
        if self._get_db_session:
            from soulspot.infrastructure.persistence.repositories import (
                SessionRepository,
            )

            async for db_session in self._get_db_session():
                try:
                    repo = SessionRepository(db_session)
                    db_count = await repo.cleanup_expired(self.session_timeout_seconds)
                    await db_session.commit()
                except Exception:
                    await db_session.rollback()
                finally:
                    await db_session.close()
                break

        return memory_count + db_count
