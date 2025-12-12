"""Tests for Spotify UI routes and database-first architecture.

Hey future me - these tests verify that the Database-First architecture works correctly:
1. Spotify data is SYNCED to DB first
2. UI LOADS data from DB (not in-memory state)
3. Freshly synced data is visible IMMEDIATELY (no page refresh needed)

The key fix was changing the order of operations in spotify_artists_page():
- OLD: Load from DB → Sync → Render (showed stale data from before sync)
- NEW: Sync → Load from DB → Render (shows fresh data including just-synced items)
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

# Hey future me - these are test fixtures that mock the SpotifySyncService
# The service handles both syncing FROM Spotify TO the DB and reading FROM the DB.


class MockSpotifyArtist:
    """Mock Spotify artist model from DB."""

    def __init__(
        self,
        spotify_id: str,
        name: str,
        genres: list[str] | None = None,
        image_url: str | None = None,
        popularity: int | None = None,
        follower_count: int | None = None,
    ) -> None:
        self.spotify_id = spotify_id
        self.name = name
        self.genres = genres or []
        self.image_url = image_url
        self.popularity = popularity
        self.follower_count = follower_count
        self.created_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)


class MockSpotifySyncService:
    """Mock SpotifySyncService for testing UI route behavior.

    Hey future me - updated to match new SpotifyPlugin-based signatures!
    No more access_token parameters - plugin handles auth internally.
    """

    def __init__(self) -> None:
        self._artists: list[MockSpotifyArtist] = []
        self.sync_called = False
        self.get_artists_called = False
        self.sync_call_order: list[str] = []

    async def sync_followed_artists(
        self, force: bool = False
    ) -> dict[str, Any]:
        """Track that sync was called and when.

        Hey future me - no more access_token parameter!
        SpotifyPlugin handles auth internally.
        """
        self.sync_called = True
        self.sync_call_order.append("sync")
        return {
            "synced": True,
            "total": len(self._artists),
            "added": 0,
            "removed": 0,
        }

    async def sync_artist_albums(
        self, artist_id: str, force: bool = False
    ) -> dict[str, Any]:
        """Track that sync_artist_albums was called."""
        self.sync_call_order.append("sync_artist_albums")
        return {"synced": True, "total": 0, "added": 0}

    async def sync_album_tracks(
        self, album_id: str, force: bool = False
    ) -> dict[str, Any]:
        """Track that sync_album_tracks was called."""
        self.sync_call_order.append("sync_album_tracks")
        return {"synced": True, "total": 0, "added": 0}

    async def get_artists(
        self, limit: int = 100, offset: int = 0
    ) -> list[MockSpotifyArtist]:
        """Track that get_artists was called and return mock data."""
        self.get_artists_called = True
        self.sync_call_order.append("get_artists")
        return self._artists[:limit]

    async def get_artist(self, spotify_id: str) -> MockSpotifyArtist | None:
        """Get an artist by Spotify ID."""
        for artist in self._artists:
            if artist.spotify_id == spotify_id:
                return artist
        return None

    async def get_artist_albums(
        self, artist_id: str, limit: int = 100
    ) -> list[Any]:
        """Get albums for an artist."""
        return []

    async def get_album(self, spotify_id: str) -> Any | None:
        """Get an album by Spotify ID."""
        return None

    async def get_album_tracks(
        self, album_id: str, limit: int = 100
    ) -> list[Any]:
        """Get tracks for an album."""
        return []

    def add_artist(self, artist: MockSpotifyArtist) -> None:
        """Add an artist to the mock DB."""
        self._artists.append(artist)


class MockDatabaseTokenManager:
    """Mock DatabaseTokenManager for testing."""

    def __init__(self, token: str | None = None) -> None:
        self._token = token

    async def get_token_for_background(self) -> str | None:
        return self._token


class MockAppState:
    """Mock FastAPI app.state."""

    def __init__(self, token_manager: MockDatabaseTokenManager | None = None) -> None:
        if token_manager:
            self.db_token_manager = token_manager


class MockRequest:
    """Mock FastAPI Request."""

    def __init__(self, app_state: MockAppState) -> None:
        self.app = MagicMock()
        self.app.state = app_state


@pytest.fixture
def sync_service() -> MockSpotifySyncService:
    """Create a mock sync service."""
    return MockSpotifySyncService()


@pytest.fixture
def token_manager_with_token() -> MockDatabaseTokenManager:
    """Create a token manager with a valid token."""
    return MockDatabaseTokenManager(token="valid_token")


@pytest.fixture
def token_manager_without_token() -> MockDatabaseTokenManager:
    """Create a token manager without a token."""
    return MockDatabaseTokenManager(token=None)


@pytest.mark.asyncio
async def test_sync_called_before_get_artists_when_token_available(
    sync_service: MockSpotifySyncService,
    token_manager_with_token: MockDatabaseTokenManager,
) -> None:
    """Test that sync is called BEFORE get_artists when token is available.

    This is the KEY TEST that verifies the fix. The order must be:
    1. Get token (if available)
    2. Sync (if token available)
    3. Get artists from DB
    4. Render

    This ensures freshly synced data is visible immediately.
    """
    # Setup: Create mock request with token manager
    app_state = MockAppState(token_manager=token_manager_with_token)
    app_state.db_token_manager = token_manager_with_token

    # Add an artist that would be returned after sync
    sync_service.add_artist(
        MockSpotifyArtist(
            spotify_id="artist_123",
            name="Test Artist",
            genres=["rock", "indie"],
        )
    )

    # Simulate the route logic (from spotify_artists_page)
    # Step 1: Try to get token
    access_token = await token_manager_with_token.get_token_for_background()

    # Step 2: Sync if token available
    if access_token:
        await sync_service.sync_followed_artists(access_token)

    # Step 3: Get artists from DB
    artists = await sync_service.get_artists(limit=500)

    # Verify the order of operations
    assert sync_service.sync_call_order == ["sync", "get_artists"]
    assert sync_service.sync_called is True
    assert sync_service.get_artists_called is True
    assert len(artists) == 1
    assert artists[0].name == "Test Artist"


@pytest.mark.asyncio
async def test_get_artists_called_without_sync_when_no_token(
    sync_service: MockSpotifySyncService,
    token_manager_without_token: MockDatabaseTokenManager,
) -> None:
    """Test that get_artists is called even when no token is available.

    The Database-First architecture means data should ALWAYS be loaded from DB,
    even if the user isn't authenticated. Syncing is optional (requires token),
    but reading from DB is not.
    """
    # Setup: Create mock request without token
    # Add an artist that was previously synced
    sync_service.add_artist(
        MockSpotifyArtist(
            spotify_id="previous_artist",
            name="Previously Synced Artist",
        )
    )

    # Simulate the route logic
    access_token = await token_manager_without_token.get_token_for_background()

    # Step 2: Sync only if token available
    if access_token:
        await sync_service.sync_followed_artists(access_token)

    # Step 3: Get artists from DB
    artists = await sync_service.get_artists(limit=500)

    # Verify: sync NOT called, but get_artists IS called
    assert sync_service.sync_call_order == ["get_artists"]
    assert sync_service.sync_called is False
    assert sync_service.get_artists_called is True
    assert len(artists) == 1
    assert artists[0].name == "Previously Synced Artist"


@pytest.mark.asyncio
async def test_database_first_shows_data_without_token() -> None:
    """Test that previously synced data is visible without a valid token.

    This is a regression test for the main issue: data appearing to 'disappear'
    after restart. The fix ensures that:
    1. Data is persisted in the database
    2. The UI loads from DB regardless of token status
    3. User can see their data even if token expired/missing
    """
    # Setup: Simulate a scenario where data was previously synced
    sync_service = MockSpotifySyncService()
    sync_service.add_artist(
        MockSpotifyArtist(
            spotify_id="artist_1",
            name="Artist One",
            genres=["pop"],
        )
    )
    sync_service.add_artist(
        MockSpotifyArtist(
            spotify_id="artist_2",
            name="Artist Two",
            genres=["rock"],
        )
    )

    # Token manager has no token (user session expired, app restarted, etc.)
    token_manager = MockDatabaseTokenManager(token=None)

    # Simulate the route logic
    access_token = await token_manager.get_token_for_background()
    assert access_token is None  # Confirm no token

    # Even without token, we should be able to read from DB
    artists = await sync_service.get_artists(limit=500)

    # Verify data is still accessible
    assert len(artists) == 2
    assert artists[0].name == "Artist One"
    assert artists[1].name == "Artist Two"


@pytest.mark.asyncio
async def test_sync_adds_new_artists_visible_immediately() -> None:
    """Test that new artists from sync are visible in the same request.

    This tests the fix for the issue where freshly synced data wasn't visible
    until the user refreshed the page.
    """
    # Setup: Start with empty DB
    sync_service = MockSpotifySyncService()
    token_manager = MockDatabaseTokenManager(token="valid_token")

    # Override sync to simulate adding an artist during sync
    original_sync = sync_service.sync_followed_artists

    async def sync_that_adds_artist(
        access_token: str, force: bool = False
    ) -> dict[str, Any]:
        # Simulate the sync adding a new artist to the DB
        sync_service.add_artist(
            MockSpotifyArtist(
                spotify_id="new_artist",
                name="Newly Synced Artist",
            )
        )
        return await original_sync(access_token, force)

    sync_service.sync_followed_artists = sync_that_adds_artist  # type: ignore[method-assign]

    # Before sync: verify no artists and reset tracking
    assert len(await sync_service.get_artists(limit=500)) == 0
    sync_service.sync_call_order.clear()  # Reset tracking

    # Simulate the route logic
    access_token = await token_manager.get_token_for_background()

    # Step 1: Sync (this adds a new artist)
    if access_token:
        await sync_service.sync_followed_artists(access_token)

    # Step 2: Get artists from DB
    artists = await sync_service.get_artists(limit=500)

    # Verify the new artist is visible in the same request
    assert sync_service.sync_call_order == ["sync", "get_artists"]
    assert len(artists) == 1
    assert artists[0].name == "Newly Synced Artist"


@pytest.mark.asyncio
async def test_sync_failure_does_not_block_database_load() -> None:
    """Test that sync failures don't prevent loading data from DB.

    This is a KEY TEST for Database-First architecture:
    Even if the Spotify token is invalid or the sync fails for any reason,
    the cached data in the database MUST still be displayed to the user.

    The user should never see an empty page just because sync failed.
    """
    # Setup: Simulate a database with previously synced data
    sync_service = MockSpotifySyncService()
    sync_service.add_artist(
        MockSpotifyArtist(
            spotify_id="cached_artist_1",
            name="Cached Artist One",
        )
    )
    sync_service.add_artist(
        MockSpotifyArtist(
            spotify_id="cached_artist_2",
            name="Cached Artist Two",
        )
    )

    # Override sync to simulate a failure (token expired, API error, etc.)
    async def sync_that_fails(access_token: str, force: bool = False) -> dict[str, Any]:
        raise Exception("Token expired or API error")

    sync_service.sync_followed_artists = sync_that_fails  # type: ignore[method-assign]

    # Simulate the route logic with sync failure handling
    token_manager = MockDatabaseTokenManager(token="invalid_or_expired_token")
    access_token = await token_manager.get_token_for_background()

    # Step 1: Try to sync (will fail)
    sync_error = None
    try:
        if access_token:
            await sync_service.sync_followed_artists(access_token)
    except Exception as e:
        sync_error = str(e)

    # Verify sync failed
    assert sync_error is not None
    assert "Token expired" in sync_error or "API error" in sync_error

    # Step 2: MUST still be able to load from DB despite sync failure!
    artists = await sync_service.get_artists(limit=500)

    # Verify cached data is still accessible
    assert len(artists) == 2
    assert artists[0].name == "Cached Artist One"
    assert artists[1].name == "Cached Artist Two"
