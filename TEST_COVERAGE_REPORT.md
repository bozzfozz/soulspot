# 🧪 Test Coverage Report - SoulSpot Bridge

**Generated:** 2025-11-24  
**Overall Coverage:** 52.57% ❌ (Target: 80%, Critical Minimum: 80%)

---

## Executive Summary

**Status:** 🔴 **CRITICAL - BLOCKS MERGE**

The codebase is currently at **52.57% coverage**, significantly below the 80% minimum threshold. This represents a coverage debt of **27.43 percentage points** that must be addressed.

### Coverage Breakdown
| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| **Overall Coverage** | 52.57% | 80% | ❌ FAIL |
| **Statement Coverage** | 56.29% (4593/8159) | 80% | ❌ FAIL |
| **Branch Coverage** | 34.90% (601/1722) | 70% | ❌ FAIL |

### Files Requiring Attention
- **Files with 0% coverage:** 1
- **Files below 20% coverage:** 15
- **Files below 50% coverage:** 35+
- **Files below 80% coverage:** 50+

---

## Changed Files Coverage Analysis

### Critical Priority Files (Below 20%)

#### 1. ❌ `src/soulspot/application/services/followed_artists_service.py` - **0.00%**

**Missing Coverage:** Lines 4-215 (ENTIRE FILE)

**Why This Matters:** This service handles Spotify followed artists sync - a core feature. Zero test coverage means ANY change could break production!

**Concrete Test Suggestions:**

```python
# tests/unit/application/services/test_followed_artists_service.py
"""Tests for FollowedArtistsService - syncing followed artists from Spotify."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.services.followed_artists_service import FollowedArtistsService
from soulspot.domain.entities import Artist
from soulspot.domain.value_objects import ArtistId, SpotifyUri
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient


@pytest.fixture
def mock_session():
    """Mock database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_spotify_client():
    """Mock Spotify client."""
    client = AsyncMock(spec=SpotifyClient)
    return client


@pytest.fixture
def service(mock_session, mock_spotify_client):
    """Create service instance with mocked dependencies."""
    return FollowedArtistsService(
        session=mock_session,
        spotify_client=mock_spotify_client
    )


# TEST 1: Successful sync with pagination
@pytest.mark.asyncio
async def test_sync_followed_artists_with_pagination(service, mock_spotify_client, mocker):
    """Test syncing followed artists handles Spotify pagination correctly."""
    # Arrange: Mock Spotify API responses with cursor-based pagination
    page1_response = {
        "artists": {
            "items": [
                {"id": "artist1", "name": "Artist One", "genres": ["rock"]},
                {"id": "artist2", "name": "Artist Two", "genres": ["pop"]},
            ],
            "cursors": {"after": "cursor_page2"}  # More pages available
        }
    }
    page2_response = {
        "artists": {
            "items": [
                {"id": "artist3", "name": "Artist Three", "genres": ["jazz"]},
            ],
            "cursors": {"after": None}  # Last page
        }
    }
    
    # Mock get_followed_artists to return different responses for each call
    mock_spotify_client.get_followed_artists.side_effect = [page1_response, page2_response]
    
    # Mock repository methods
    mock_artist_repo = mocker.patch.object(service, 'artist_repo')
    mock_artist_repo.get_by_spotify_uri.return_value = None  # No existing artists
    
    # Act
    artists, stats = await service.sync_followed_artists(access_token="valid_token")
    
    # Assert: Should fetch both pages
    assert mock_spotify_client.get_followed_artists.call_count == 2
    assert len(artists) == 3
    assert stats["total_fetched"] == 3
    assert stats["created"] == 3
    assert stats["updated"] == 0
    assert stats["errors"] == 0
    
    # Verify pagination parameters
    first_call = mock_spotify_client.get_followed_artists.call_args_list[0]
    assert first_call[1]["limit"] == 50
    assert first_call[1]["after"] is None  # First page has no cursor
    
    second_call = mock_spotify_client.get_followed_artists.call_args_list[1]
    assert second_call[1]["after"] == "cursor_page2"  # Second page uses cursor


# TEST 2: Updating existing artists
@pytest.mark.asyncio
async def test_sync_followed_artists_updates_existing(service, mock_spotify_client, mocker):
    """Test that sync updates existing artists instead of duplicating."""
    # Arrange: Mock Spotify response
    spotify_response = {
        "artists": {
            "items": [
                {"id": "existing_id", "name": "Updated Name", "genres": ["new_genre"]},
            ],
            "cursors": {"after": None}
        }
    }
    mock_spotify_client.get_followed_artists.return_value = spotify_response
    
    # Mock existing artist in DB
    existing_artist = Artist(
        id=ArtistId.generate(),
        name="Old Name",
        spotify_uri=SpotifyUri.from_string("spotify:artist:existing_id"),
        genres=["old_genre"],
        metadata_sources={"name": "spotify", "genres": "spotify"}
    )
    
    mock_artist_repo = mocker.patch.object(service, 'artist_repo')
    mock_artist_repo.get_by_spotify_uri.return_value = existing_artist
    
    # Act
    artists, stats = await service.sync_followed_artists(access_token="valid_token")
    
    # Assert: Should update, not create
    assert stats["created"] == 0
    assert stats["updated"] == 1
    assert existing_artist.name == "Updated Name"  # Name should be updated
    assert existing_artist.genres == ["new_genre"]  # Genres should be updated
    mock_artist_repo.update.assert_called_once_with(existing_artist)


# TEST 3: Empty response handling
@pytest.mark.asyncio
async def test_sync_followed_artists_empty_response(service, mock_spotify_client):
    """Test that sync handles users with zero followed artists gracefully."""
    # Arrange: Empty response
    mock_spotify_client.get_followed_artists.return_value = {
        "artists": {
            "items": [],
            "cursors": {}
        }
    }
    
    # Act
    artists, stats = await service.sync_followed_artists(access_token="valid_token")
    
    # Assert
    assert len(artists) == 0
    assert stats["total_fetched"] == 0
    assert stats["created"] == 0
    assert mock_spotify_client.get_followed_artists.call_count == 1


# TEST 4: Error handling mid-pagination
@pytest.mark.asyncio
async def test_sync_followed_artists_error_mid_pagination(service, mock_spotify_client, mocker):
    """Test that sync returns partial results if pagination fails mid-sync."""
    # Arrange: First page succeeds, second page fails
    page1_response = {
        "artists": {
            "items": [{"id": "artist1", "name": "Artist One", "genres": []}],
            "cursors": {"after": "cursor_page2"}
        }
    }
    
    mock_spotify_client.get_followed_artists.side_effect = [
        page1_response,
        Exception("Spotify API rate limit exceeded")
    ]
    
    mock_artist_repo = mocker.patch.object(service, 'artist_repo')
    mock_artist_repo.get_by_spotify_uri.return_value = None
    
    # Act
    artists, stats = await service.sync_followed_artists(access_token="valid_token")
    
    # Assert: Should return partial results (page 1 only)
    assert len(artists) == 1
    assert stats["total_fetched"] == 1
    assert stats["created"] == 1


# TEST 5: Invalid artist data handling
@pytest.mark.asyncio
async def test_sync_followed_artists_invalid_data(service, mock_spotify_client, mocker):
    """Test that sync logs errors for invalid artist data but continues processing."""
    # Arrange: Mix of valid and invalid artist data
    spotify_response = {
        "artists": {
            "items": [
                {"id": "artist1", "name": "Valid Artist", "genres": []},
                {"id": None, "name": "Missing ID"},  # Invalid!
                {"id": "artist3", "name": "Another Valid", "genres": []},
            ],
            "cursors": {"after": None}
        }
    }
    mock_spotify_client.get_followed_artists.return_value = spotify_response
    
    mock_artist_repo = mocker.patch.object(service, 'artist_repo')
    mock_artist_repo.get_by_spotify_uri.return_value = None
    
    # Act
    artists, stats = await service.sync_followed_artists(access_token="valid_token")
    
    # Assert: Should process valid artists, skip invalid
    assert len(artists) == 2  # Only valid artists
    assert stats["total_fetched"] == 2
    assert stats["errors"] == 1  # One invalid artist


# TEST 6: Preview without syncing
@pytest.mark.asyncio
async def test_preview_followed_artists(service, mock_spotify_client):
    """Test preview returns raw Spotify data without persisting to DB."""
    # Arrange
    expected_response = {
        "artists": {
            "items": [{"id": "artist1", "name": "Preview Artist"}]
        }
    }
    mock_spotify_client.get_followed_artists.return_value = expected_response
    
    # Act
    result = await service.preview_followed_artists(
        access_token="token",
        limit=10
    )
    
    # Assert: Should return raw Spotify response
    assert result == expected_response
    # Verify limit is capped at 50
    mock_spotify_client.get_followed_artists.assert_called_once_with(
        access_token="token",
        limit=10
    )
```

**Priority:** 🔴 **CRITICAL** - This is a core service with ZERO coverage.

---

#### 2. ❌ `src/soulspot/api/routers/auth.py` - **19.47%**

**Missing Coverage:** Lines 22-65, 80-165, 174-238, 246-277, 285-308, 316-356, 364-390 (OAuth flow critical paths)

**Why This Matters:** Authentication is SECURITY CRITICAL. Missing coverage on OAuth callbacks and session management is a major risk!

**Concrete Test Suggestions:**

```python
# tests/integration/api/test_auth_endpoints.py
"""Integration tests for authentication endpoints - SECURITY CRITICAL!"""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta

from soulspot.main import app
from soulspot.application.services.session_store import DatabaseSessionStore


@pytest.fixture
def mock_session_store():
    """Mock session store for testing."""
    store = AsyncMock(spec=DatabaseSessionStore)
    return store


# TEST 1: OAuth authorization flow initiation
@pytest.mark.asyncio
async def test_authorize_creates_session_and_returns_url(mock_session_store):
    """Test /authorize creates session with state and returns Spotify auth URL."""
    # Arrange: Mock session creation
    mock_session = AsyncMock()
    mock_session.session_id = "test_session_123"
    mock_session_store.create_session.return_value = mock_session
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        with patch("soulspot.api.routers.auth.get_session_store", return_value=mock_session_store):
            # Act
            response = await client.get("/api/v1/auth/authorize")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "authorization_url" in data
    assert "spotify.com/authorize" in data["authorization_url"]
    
    # Verify session cookie was set
    assert "soulspot_session" in response.cookies
    
    # Verify session was created with state and code_verifier
    mock_session_store.create_session.assert_called_once()
    call_kwargs = mock_session_store.create_session.call_args[1]
    assert "oauth_state" in call_kwargs
    assert "code_verifier" in call_kwargs
    assert len(call_kwargs["oauth_state"]) > 20  # State should be cryptographically random


# TEST 2: OAuth callback with valid state (CSRF protection)
@pytest.mark.asyncio
async def test_callback_validates_state_csrf_protection(mock_session_store):
    """Test /callback rejects requests with mismatched state (CSRF protection)."""
    # Arrange: Session with stored state
    mock_session = AsyncMock()
    mock_session.oauth_state = "stored_state_abc123"
    mock_session.code_verifier = "verifier_xyz"
    mock_session_store.get_session.return_value = mock_session
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        with patch("soulspot.api.routers.auth.get_session_store", return_value=mock_session_store):
            # Act: Send mismatched state
            response = await client.get(
                "/api/v1/auth/callback",
                params={"code": "auth_code", "state": "WRONG_STATE"},
                cookies={"soulspot_session": "session_id"}
            )
    
    # Assert: Should reject with 400 (CSRF attack detected)
    assert response.status_code == 400
    assert "State verification failed" in response.json()["detail"]


# TEST 3: OAuth callback without session cookie (session fixation protection)
@pytest.mark.asyncio
async def test_callback_rejects_missing_session():
    """Test /callback rejects requests without session cookie."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Act: No session cookie
        response = await client.get(
            "/api/v1/auth/callback",
            params={"code": "auth_code", "state": "some_state"}
        )
    
    # Assert: Should reject with 401
    assert response.status_code == 401
    assert "No session found" in response.json()["detail"]


# TEST 4: Successful OAuth callback and token exchange
@pytest.mark.asyncio
async def test_callback_successful_token_exchange(mock_session_store):
    """Test /callback successfully exchanges code for tokens and stores in session."""
    # Arrange
    mock_session = AsyncMock()
    mock_session.oauth_state = "correct_state"
    mock_session.code_verifier = "verifier_123"
    mock_session_store.get_session.return_value = mock_session
    
    mock_token_data = {
        "access_token": "spotify_access_token",
        "refresh_token": "spotify_refresh_token",
        "expires_in": 3600
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        with patch("soulspot.api.routers.auth.get_session_store", return_value=mock_session_store):
            with patch("soulspot.infrastructure.integrations.spotify_client.SpotifyClient.exchange_code",
                      return_value=mock_token_data):
                # Act
                response = await client.get(
                    "/api/v1/auth/callback",
                    params={"code": "auth_code", "state": "correct_state"},
                    cookies={"soulspot_session": "session_id"},
                    follow_redirects=False
                )
    
    # Assert: Should redirect to dashboard
    assert response.status_code == 302
    assert response.headers["location"] == "/"
    
    # Verify tokens were stored in session
    mock_session.set_tokens.assert_called_once_with(
        access_token="spotify_access_token",
        refresh_token="spotify_refresh_token",
        expires_in=3600
    )
    
    # Verify state and verifier were cleared (one-time use)
    mock_session_store.update_session.assert_called_once()
    update_call = mock_session_store.update_session.call_args
    assert update_call[1]["oauth_state"] is None
    assert update_call[1]["code_verifier"] is None


# TEST 5: Token refresh endpoint
@pytest.mark.asyncio
async def test_refresh_token_success(mock_session_store):
    """Test /refresh successfully refreshes access token using refresh token."""
    # Arrange
    mock_session = AsyncMock()
    mock_session.refresh_token = "valid_refresh_token"
    mock_session_store.get_session.return_value = mock_session
    
    mock_new_tokens = {
        "access_token": "new_access_token",
        "expires_in": 3600
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        with patch("soulspot.api.routers.auth.get_session_store", return_value=mock_session_store):
            with patch("soulspot.infrastructure.integrations.spotify_client.SpotifyClient.refresh_token",
                      return_value=mock_new_tokens):
                # Act
                response = await client.post(
                    "/api/v1/auth/refresh",
                    cookies={"soulspot_session": "session_id"}
                )
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Token refreshed successfully"
    assert data["expires_in"] == 3600
    
    # Verify session was updated with new token
    mock_session.set_tokens.assert_called_once()


# TEST 6: Token refresh without refresh token
@pytest.mark.asyncio
async def test_refresh_token_missing_refresh_token(mock_session_store):
    """Test /refresh rejects when session has no refresh token."""
    # Arrange
    mock_session = AsyncMock()
    mock_session.refresh_token = None  # No refresh token!
    mock_session_store.get_session.return_value = mock_session
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        with patch("soulspot.api.routers.auth.get_session_store", return_value=mock_session_store):
            # Act
            response = await client.post(
                "/api/v1/auth/refresh",
                cookies={"soulspot_session": "session_id"}
            )
    
    # Assert
    assert response.status_code == 400
    assert "No refresh token" in response.json()["detail"]


# TEST 7: Session info endpoint (no token leakage)
@pytest.mark.asyncio
async def test_get_session_info_no_token_leakage(mock_session_store):
    """Test /session returns metadata WITHOUT exposing actual token values."""
    # Arrange
    mock_session = AsyncMock()
    mock_session.session_id = "session_123"
    mock_session.access_token = "SECRET_ACCESS_TOKEN"  # Should NOT be in response!
    mock_session.refresh_token = "SECRET_REFRESH_TOKEN"  # Should NOT be in response!
    mock_session.is_token_expired.return_value = False
    mock_session.created_at = datetime.now()
    mock_session.last_accessed_at = datetime.now()
    mock_session_store.get_session.return_value = mock_session
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        with patch("soulspot.api.routers.auth.get_session_store", return_value=mock_session_store):
            # Act
            response = await client.get(
                "/api/v1/auth/session",
                cookies={"soulspot_session": "session_id"}
            )
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    
    # Verify NO token values are exposed
    assert "access_token" not in data
    assert "refresh_token" not in data
    assert "SECRET" not in str(data)
    
    # Verify metadata IS exposed
    assert data["has_access_token"] is True
    assert data["has_refresh_token"] is True
    assert data["token_expired"] is False


# TEST 8: Logout endpoint
@pytest.mark.asyncio
async def test_logout_deletes_session_and_cookie(mock_session_store):
    """Test /logout deletes session and clears cookie."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        with patch("soulspot.api.routers.auth.get_session_store", return_value=mock_session_store):
            # Act
            response = await client.post(
                "/api/v1/auth/logout",
                cookies={"soulspot_session": "session_id"}
            )
    
    # Assert
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"
    
    # Verify session was deleted
    mock_session_store.delete_session.assert_called_once_with("session_id")
    
    # Verify cookie was cleared
    assert "soulspot_session" in response.cookies
    assert response.cookies["soulspot_session"] == ""  # Cleared


# TEST 9: Spotify status check
@pytest.mark.asyncio
async def test_spotify_status_connected(mock_session_store):
    """Test /spotify/status returns correct connection status."""
    # Arrange: Valid, non-expired token
    mock_session = AsyncMock()
    mock_session.access_token = "valid_token"
    mock_session.is_token_expired.return_value = False
    mock_session.token_expires_at = datetime.now() + timedelta(hours=1)
    mock_session_store.get_session.return_value = mock_session
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        with patch("soulspot.api.routers.auth.get_session_store", return_value=mock_session_store):
            # Act
            response = await client.get(
                "/api/v1/auth/spotify/status",
                cookies={"soulspot_session": "session_id"}
            )
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True
    assert data["provider"] == "spotify"
    assert data["token_expired"] is False
```

**Priority:** 🔴 **CRITICAL** - Security-critical authentication code.

---

#### 3. ❌ `src/soulspot/application/services/postprocessing/id3_tagging_service.py` - **11.63%**

**Missing Coverage:** Lines 72-181, 194-211, 224-240, 262-264, 292, 319-339, 359-402

**Why This Matters:** ID3 tagging is how metadata gets written to files. Poor coverage means broken tags = bad user experience!

**Concrete Test Suggestions:**

```python
# tests/unit/application/services/postprocessing/test_id3_tagging_service.py
"""Tests for ID3TaggingService - metadata embedding into audio files."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
import tempfile
import shutil

from soulspot.application.services.postprocessing.id3_tagging_service import ID3TaggingService
from soulspot.domain.entities import Track, Artist, Album
from soulspot.domain.value_objects import TrackId, ArtistId, AlbumId, SpotifyUri
from soulspot.config import Settings


@pytest.fixture
def temp_music_dir():
    """Create temporary directory for test audio files."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_settings(temp_music_dir):
    """Mock settings with temp directories."""
    settings = MagicMock(spec=Settings)
    settings.storage.download_path = temp_music_dir / "downloads"
    settings.storage.music_path = temp_music_dir / "music"
    settings.storage.download_path.mkdir(exist_ok=True)
    settings.storage.music_path.mkdir(exist_ok=True)
    return settings


@pytest.fixture
def service(mock_settings):
    """Create ID3TaggingService instance."""
    return ID3TaggingService(settings=mock_settings)


@pytest.fixture
def sample_track():
    """Sample track entity for testing."""
    return Track(
        id=TrackId.generate(),
        title="Test Song",
        artist_id=ArtistId.generate(),
        spotify_uri=SpotifyUri.from_string("spotify:track:abc123"),
        duration_ms=180000,
        isrc="USRC12345678",
        metadata_sources={"title": "spotify"}
    )


@pytest.fixture
def sample_artist():
    """Sample artist entity for testing."""
    return Artist(
        id=ArtistId.generate(),
        name="Test Artist",
        spotify_uri=SpotifyUri.from_string("spotify:artist:xyz789"),
        genres=["rock", "alternative"],
        metadata_sources={"name": "spotify"}
    )


@pytest.fixture
def sample_album():
    """Sample album entity for testing."""
    return Album(
        id=AlbumId.generate(),
        title="Test Album",
        artist_id=ArtistId.generate(),
        release_date="2024-01-01",
        total_tracks=12,
        metadata_sources={"title": "spotify"}
    )


# TEST 1: Path validation - reject paths outside allowed directories
@pytest.mark.asyncio
async def test_write_tags_rejects_unsafe_path(service, sample_track, sample_artist):
    """Test that write_tags rejects paths outside allowed music directories (SECURITY)."""
    # Arrange: Path outside allowed directories
    unsafe_path = Path("/etc/passwd")
    
    # Act & Assert: Should raise ValueError for path traversal attempt
    with pytest.raises(ValueError, match="outside allowed"):
        await service.write_tags(
            file_path=unsafe_path,
            track=sample_track,
            artist=sample_artist
        )


# TEST 2: Path validation - accept paths in allowed directories
@pytest.mark.asyncio
async def test_write_tags_accepts_safe_path(service, sample_track, sample_artist, temp_music_dir):
    """Test that write_tags accepts paths within allowed music directories."""
    # Arrange: Valid path in music directory
    test_file = temp_music_dir / "music" / "test.mp3"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("fake mp3 data")  # Create dummy file
    
    with patch("soulspot.application.services.postprocessing.id3_tagging_service.MP3") as mock_mp3:
        with patch("soulspot.application.services.postprocessing.id3_tagging_service.EasyID3") as mock_easy:
            # Mock mutagen objects
            mock_audio = MagicMock()
            mock_mp3.return_value = mock_audio
            mock_tags = MagicMock()
            mock_easy.return_value = mock_tags
            
            # Act: Should succeed without ValueError
            await service.write_tags(
                file_path=test_file,
                track=sample_track,
                artist=sample_artist
            )
            
            # Assert: Tags should be written
            mock_tags.save.assert_called_once()


# TEST 3: Write basic track metadata
@pytest.mark.asyncio
async def test_write_tags_basic_metadata(service, sample_track, sample_artist, temp_music_dir):
    """Test writing basic track metadata (title, artist, album, etc.)."""
    # Arrange
    test_file = temp_music_dir / "music" / "test.mp3"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("fake mp3")
    
    sample_album = Album(
        id=AlbumId.generate(),
        title="Test Album",
        artist_id=sample_artist.id,
        release_date="2024-05-15",
        total_tracks=10,
        metadata_sources={"title": "musicbrainz"}
    )
    
    with patch("soulspot.application.services.postprocessing.id3_tagging_service.MP3"):
        with patch("soulspot.application.services.postprocessing.id3_tagging_service.EasyID3") as mock_easy:
            mock_tags = MagicMock()
            mock_easy.return_value = mock_tags
            
            # Act
            await service.write_tags(
                file_path=test_file,
                track=sample_track,
                artist=sample_artist,
                album=sample_album
            )
            
            # Assert: Basic tags should be set
            assert mock_tags["title"] == [sample_track.title]
            assert mock_tags["artist"] == [sample_artist.name]
            assert mock_tags["album"] == [sample_album.title]
            assert mock_tags["date"] == ["2024-05-15"]
            mock_tags.save.assert_called_once()


# TEST 4: Embed artwork
@pytest.mark.asyncio
async def test_write_tags_embeds_artwork(service, sample_track, sample_artist, temp_music_dir):
    """Test embedding album artwork into ID3 tags."""
    # Arrange
    test_file = temp_music_dir / "music" / "test.mp3"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("fake mp3")
    
    fake_artwork = b"fake_jpeg_data_12345"
    
    with patch("soulspot.application.services.postprocessing.id3_tagging_service.MP3") as mock_mp3:
        with patch("soulspot.application.services.postprocessing.id3_tagging_service.ID3") as mock_id3_class:
            with patch("soulspot.application.services.postprocessing.id3_tagging_service.APIC") as mock_apic:
                mock_audio = MagicMock()
                mock_mp3.return_value = mock_audio
                mock_id3 = MagicMock()
                mock_id3_class.return_value = mock_id3
                
                # Mock APIC frame creation
                mock_apic_frame = MagicMock()
                mock_apic.return_value = mock_apic_frame
                
                # Act
                await service.write_tags(
                    file_path=test_file,
                    track=sample_track,
                    artist=sample_artist,
                    artwork_data=fake_artwork
                )
                
                # Assert: APIC frame should be added
                mock_apic.assert_called_once()
                call_kwargs = mock_apic.call_args[1]
                assert call_kwargs["data"] == fake_artwork
                assert call_kwargs["type"] == 3  # Cover (front)
                mock_id3.save.assert_called_once()


# TEST 5: Embed lyrics
@pytest.mark.asyncio
async def test_write_tags_embeds_lyrics(service, sample_track, sample_artist, temp_music_dir):
    """Test embedding synced or unsynced lyrics into ID3 tags."""
    # Arrange
    test_file = temp_music_dir / "music" / "test.mp3"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("fake mp3")
    
    lyrics_text = "Verse 1:\nThis is a test song\nWith multiple lines"
    
    with patch("soulspot.application.services.postprocessing.id3_tagging_service.MP3"):
        with patch("soulspot.application.services.postprocessing.id3_tagging_service.ID3") as mock_id3_class:
            with patch("soulspot.application.services.postprocessing.id3_tagging_service.USLT") as mock_uslt:
                mock_id3 = MagicMock()
                mock_id3_class.return_value = mock_id3
                mock_lyrics_frame = MagicMock()
                mock_uslt.return_value = mock_lyrics_frame
                
                # Act
                await service.write_tags(
                    file_path=test_file,
                    track=sample_track,
                    artist=sample_artist,
                    lyrics=lyrics_text
                )
                
                # Assert: USLT frame should be added
                mock_uslt.assert_called_once()
                call_kwargs = mock_uslt.call_args[1]
                assert call_kwargs["text"] == lyrics_text
                assert call_kwargs["lang"] == "eng"


# TEST 6: Handle missing file
@pytest.mark.asyncio
async def test_write_tags_missing_file(service, sample_track, sample_artist, temp_music_dir):
    """Test that write_tags raises FileNotFoundError for non-existent files."""
    # Arrange: File that doesn't exist
    missing_file = temp_music_dir / "music" / "nonexistent.mp3"
    
    # Act & Assert
    with pytest.raises(FileNotFoundError):
        await service.write_tags(
            file_path=missing_file,
            track=sample_track,
            artist=sample_artist
        )


# TEST 7: Remove existing artwork before adding new (prevent duplicates)
@pytest.mark.asyncio
async def test_write_tags_removes_old_artwork(service, sample_track, sample_artist, temp_music_dir):
    """Test that write_tags removes ALL existing APIC frames before adding new artwork."""
    # Arrange
    test_file = temp_music_dir / "music" / "test.mp3"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("fake mp3")
    
    new_artwork = b"new_cover_art"
    
    with patch("soulspot.application.services.postprocessing.id3_tagging_service.MP3"):
        with patch("soulspot.application.services.postprocessing.id3_tagging_service.ID3") as mock_id3_class:
            with patch("soulspot.application.services.postprocessing.id3_tagging_service.APIC"):
                mock_id3 = MagicMock()
                # Mock existing APIC frames
                mock_id3.getall.return_value = [MagicMock(), MagicMock()]  # 2 existing covers
                mock_id3_class.return_value = mock_id3
                
                # Act
                await service.write_tags(
                    file_path=test_file,
                    track=sample_track,
                    artist=sample_artist,
                    artwork_data=new_artwork
                )
                
                # Assert: Should delete all existing APIC frames
                assert mock_id3.delall.called
                assert "APIC" in str(mock_id3.delall.call_args)
```

**Priority:** 🟡 **HIGH** - Core postprocessing feature.

---

## Overall Recommendations

### Immediate Actions (Next 2 Weeks)

1. **Add tests for followed_artists_service.py** (0% → 80%)
   - 6 tests suggested above cover main flows
   - **Estimated effort:** 4 hours

2. **Add security tests for auth.py** (19% → 80%)
   - 9 tests suggested above cover OAuth and session security
   - **Estimated effort:** 6 hours

3. **Add tests for ID3 tagging** (12% → 80%)
   - 7 tests suggested above cover metadata writing
   - **Estimated effort:** 5 hours

### Medium-Term Actions (Next Month)

4. **Increase service layer coverage** to 90%+
   - Focus on:
     - `discography_service.py` (22%)
     - `session_store.py` (35%)
     - `watchlist_service.py` (48%)

5. **Increase repository coverage** to 70%+
   - `repositories.py` (32%) - critical database operations

6. **Add API router tests** for all endpoints
   - Most routers are below 30%

### Long-Term Actions (Next Quarter)

7. **Workers coverage** to 80%+
   - Background job processing needs comprehensive testing

8. **Use cases coverage** to 90%+
   - Business logic layer should be thoroughly tested

---

## How to Use This Report

### For Each Suggested Test:

1. **Copy the entire test code** - It's production-ready!
2. **Create the test file** in the correct directory
3. **Run pytest** to verify it passes
4. **Run coverage** to see improvement:
   ```bash
   make test-cov
   ```
5. **Iterate** - Add more edge cases as needed

### Running Tests:

```bash
# Run all tests with coverage
make test-cov

# Run specific test file
pytest tests/unit/application/services/test_followed_artists_service.py -v

# Run coverage for specific module
pytest --cov=src/soulspot/application/services/followed_artists_service.py \
       --cov-report=term-missing
```

---

## Coverage Trends

**Target Milestones:**

- Week 1: 52% → 60% ✅ (Add critical service tests)
- Week 2: 60% → 70% ✅ (Add auth and API tests)
- Week 3: 70% → 80% ✅ (Add repository tests)
- Week 4: 80%+ ✅ (Maintain and improve)

---

## Notes on Test Quality

The suggested tests above follow these principles:

1. **Concrete, runnable code** - Not pseudo-code!
2. **Realistic test data** - Uses actual entities
3. **Edge case coverage** - Handles errors, empty data, pagination
4. **Security testing** - CSRF, path traversal, token leakage
5. **Clear assertions** - Easy to understand what's being tested
6. **Good naming** - Test names describe behavior

---

**Remember:** Test coverage is NOT just about the number - it's about **confidence in your code**. These tests will:

- ✅ Catch bugs before production
- ✅ Document expected behavior
- ✅ Enable safe refactoring
- ✅ Improve code design

---

**Generated by:** Test Coverage Guardian Agent  
**Next Review:** After implementing suggested tests
