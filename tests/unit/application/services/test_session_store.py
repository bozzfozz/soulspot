"""Tests for Session Store service."""

from datetime import UTC, datetime, timedelta

from soulspot.application.services.session_store import Session, SessionStore


class TestSession:
    """Test Session dataclass."""

    def test_create_session(self) -> None:
        """Test session creation."""
        session = Session(session_id="test-session-id")
        assert session.session_id == "test-session-id"
        assert session.access_token is None
        assert session.refresh_token is None
        assert session.token_expires_at is None

    def test_session_not_expired_when_new(self) -> None:
        """Test newly created session is not expired."""
        session = Session(session_id="test-session-id")
        assert session.is_expired() is False

    def test_session_expired_after_timeout(self) -> None:
        """Test session expires after timeout."""
        session = Session(
            session_id="test-session-id",
            last_accessed_at=datetime.now(UTC) - timedelta(hours=2),
        )
        assert session.is_expired(session_timeout_seconds=3600) is True

    def test_refresh_access_updates_timestamp(self) -> None:
        """Test refresh_access updates last_accessed_at."""
        session = Session(session_id="test-session-id")
        old_time = session.last_accessed_at

        # Small delay to ensure timestamp difference
        import time

        time.sleep(0.01)

        session.refresh_access()
        assert session.last_accessed_at > old_time

    def test_is_token_expired_when_no_token(self) -> None:
        """Test is_token_expired returns True when no token set."""
        session = Session(session_id="test-session-id")
        assert session.is_token_expired() is True

    def test_is_token_expired_when_token_valid(self) -> None:
        """Test is_token_expired returns False when token valid."""
        session = Session(
            session_id="test-session-id",
            access_token="test-token",
            token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        assert session.is_token_expired() is False

    def test_is_token_expired_when_token_expired(self) -> None:
        """Test is_token_expired returns True when token expired."""
        session = Session(
            session_id="test-session-id",
            access_token="test-token",
            token_expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        assert session.is_token_expired() is True

    def test_set_tokens(self) -> None:
        """Test set_tokens updates token fields."""
        session = Session(session_id="test-session-id")
        session.set_tokens("access-token", "refresh-token", 3600)

        assert session.access_token == "access-token"
        assert session.refresh_token == "refresh-token"
        assert session.token_expires_at is not None
        assert session.token_expires_at > datetime.now(UTC)


class TestSessionStore:
    """Test SessionStore."""

    def test_create_store(self) -> None:
        """Test creating a session store."""
        store = SessionStore()
        assert store.count_sessions() == 0

    def test_create_session(self) -> None:
        """Test creating a session."""
        store = SessionStore()
        session = store.create_session(
            oauth_state="test-state", code_verifier="test-verifier"
        )

        assert session.session_id is not None
        assert session.oauth_state == "test-state"
        assert session.code_verifier == "test-verifier"
        assert store.count_sessions() == 1

    def test_get_session(self) -> None:
        """Test getting a session by ID."""
        store = SessionStore()
        session = store.create_session()

        retrieved = store.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    def test_get_session_not_found(self) -> None:
        """Test getting non-existent session returns None."""
        store = SessionStore()
        retrieved = store.get_session("non-existent")
        assert retrieved is None

    def test_get_session_expired(self) -> None:
        """Test getting expired session returns None and removes it."""
        store = SessionStore()
        session = store.create_session()

        # Make session expired
        session.last_accessed_at = datetime.now(UTC) - timedelta(hours=2)

        retrieved = store.get_session(session.session_id)
        assert retrieved is None
        assert store.count_sessions() == 0

    def test_get_session_by_state(self) -> None:
        """Test getting session by OAuth state."""
        store = SessionStore()
        session = store.create_session(oauth_state="test-state")

        retrieved = store.get_session_by_state("test-state")
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    def test_get_session_by_state_not_found(self) -> None:
        """Test getting session by non-existent state returns None."""
        store = SessionStore()
        store.create_session(oauth_state="test-state")

        retrieved = store.get_session_by_state("other-state")
        assert retrieved is None

    def test_update_session(self) -> None:
        """Test updating session data."""
        store = SessionStore()
        session = store.create_session()

        updated = store.update_session(session.session_id, access_token="new-token")
        assert updated is not None
        assert updated.access_token == "new-token"

    def test_update_session_not_found(self) -> None:
        """Test updating non-existent session returns None."""
        store = SessionStore()
        updated = store.update_session("non-existent", access_token="token")
        assert updated is None

    def test_delete_session(self) -> None:
        """Test deleting a session."""
        store = SessionStore()
        session = store.create_session()

        assert store.delete_session(session.session_id) is True
        assert store.count_sessions() == 0

    def test_delete_session_not_found(self) -> None:
        """Test deleting non-existent session returns False."""
        store = SessionStore()
        assert store.delete_session("non-existent") is False

    def test_cleanup_expired_sessions(self) -> None:
        """Test cleaning up expired sessions."""
        store = SessionStore()

        # Create some sessions
        session1 = store.create_session()
        session2 = store.create_session()
        session3 = store.create_session()

        # Make some expired
        session1.last_accessed_at = datetime.now(UTC) - timedelta(hours=2)
        session2.last_accessed_at = datetime.now(UTC) - timedelta(hours=3)

        removed_count = store.cleanup_expired_sessions()
        assert removed_count == 2
        assert store.count_sessions() == 1

        # Verify the right session remains
        retrieved = store.get_session(session3.session_id)
        assert retrieved is not None

    def test_session_refresh_on_access(self) -> None:
        """Test session last_accessed_at is updated on get."""
        store = SessionStore()
        session = store.create_session()

        old_time = session.last_accessed_at

        # Small delay
        import time

        time.sleep(0.01)

        retrieved = store.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.last_accessed_at > old_time
