# Spotify Module - Complete Specification (Version 3.0)

> **⚠️ DEPRECATED - UNREALIZED MODULE:** This modular Spotify design was **never implemented**. Current Spotify integration uses Hexagonal Architecture (`src/soulspot/infrastructure/integrations/spotify_client.py`). See `docs/api/spotify-*.md` for actual API documentation.

<details>
<summary><strong>📁 Archived Content (Click to Expand)</strong></summary>

---

**Module Name:** `spotify`  
**Version:** 1.0.0  
**Status:** ~~Planning Phase~~ UNREALIZED MODULE  
**Last Updated:** 2025-11-22

---

## 1. Overview

The Spotify module handles all interactions with the Spotify Web API, including authentication, playlist management, track search, and user library access. This module is one of the **two pilot modules** (alongside Soulseek) required for initial testing of the modular architecture.

### 1.1 Module Purpose

- OAuth 2.0 authentication with Spotify
- Playlist discovery and synchronization
- Track and album search
- User library access (saved tracks, albums, artists)
- Playback integration (optional)

### 1.2 Strategic Importance

**Why Spotify is a Pilot Module:**
- Primary entry point for user content (playlists to download)
- Complex authentication flow tests OAuth submodule pattern
- High user interaction tests UI card system
- Integration with Soulseek tests Module Router orchestration

---

## 2. Module Structure (Lean with Submodules)

**Philosophy:** Keep the main module lean by distributing functionality into focused submodules. This enables:
- ✅ Parallel development without merge conflicts
- ✅ Independent testing and deployment
- ✅ Optional feature enablement
- ✅ Better code organization

```
modules/spotify/
├── README.md                   # Module overview and quick start
├── CHANGELOG.md                # Module version history
├── docs/                       # Module documentation
│   ├── architecture.md         # Design decisions and diagrams
│   ├── api.md                  # API endpoints and schemas
│   ├── events.md               # Event schemas and contracts
│   ├── configuration.md        # Configuration guide
│   └── development.md          # Development and testing guide
│
├── submodules/                 # Feature submodules (keep main lean)
│   │
│   ├── auth/                   # OAuth 2.0 authentication (REUSABLE)
│   │   ├── README.md
│   │   ├── CHANGELOG.md
│   │   ├── docs/
│   │   │   ├── oauth-flow.md
│   │   │   └── token-management.md
│   │   ├── backend/
│   │   │   ├── domain/
│   │   │   │   ├── oauth_token.py       # Token entity
│   │   │   │   └── oauth_state.py       # State validation
│   │   │   ├── application/
│   │   │   │   ├── token_service.py     # Token lifecycle
│   │   │   │   └── auth_service.py      # OAuth flow orchestration
│   │   │   ├── infrastructure/
│   │   │   │   └── token_repository.py  # Token persistence
│   │   │   └── api/
│   │   │       ├── routes.py            # /spotify/auth/* endpoints
│   │   │       └── schemas.py           # Auth request/response models
│   │   ├── frontend/
│   │   │   └── cards/
│   │   │       └── auth_card.html       # Login/logout UI
│   │   └── tests/
│   │       ├── test_token_service.py
│   │       └── test_oauth_flow.py
│   │
│   ├── playlists/              # Playlist management
│   │   ├── README.md
│   │   ├── backend/
│   │   │   ├── domain/
│   │   │   │   ├── playlist.py          # Playlist entity
│   │   │   │   └── playlist_track.py    # Track entity
│   │   │   ├── application/
│   │   │   │   ├── playlist_service.py  # CRUD operations
│   │   │   │   └── sync_service.py      # Spotify sync
│   │   │   ├── infrastructure/
│   │   │   │   └── playlist_repository.py
│   │   │   └── api/
│   │   │       ├── routes.py            # /spotify/playlists/* endpoints
│   │   │       └── schemas.py
│   │   ├── frontend/
│   │   │   ├── pages/
│   │   │   │   └── playlists.html       # Playlist overview page
│   │   │   └── cards/
│   │   │       ├── playlist_list_card.html
│   │   │       └── playlist_detail_card.html
│   │   └── tests/
│   │
│   ├── search/                 # Track/album search
│   │   ├── README.md
│   │   ├── backend/
│   │   │   ├── domain/
│   │   │   │   ├── search_query.py
│   │   │   │   └── search_result.py
│   │   │   ├── application/
│   │   │   │   └── search_service.py
│   │   │   └── api/
│   │   │       ├── routes.py            # /spotify/search/* endpoints
│   │   │       └── schemas.py
│   │   ├── frontend/
│   │   │   └── cards/
│   │   │       ├── search_form_card.html
│   │   │       └── search_results_card.html
│   │   └── tests/
│   │
│   └── library/                # User library (saved tracks, albums)
│       ├── README.md
│       ├── backend/
│       │   ├── domain/
│       │   │   └── library_item.py
│       │   ├── application/
│       │   │   └── library_service.py
│       │   └── api/
│       │       ├── routes.py            # /spotify/library/* endpoints
│       │       └── schemas.py
│       ├── frontend/
│       │   └── cards/
│       │       └── library_card.html
│       └── tests/
│
├── backend/                    # Core module (lean!)
│   ├── infrastructure/
│   │   └── spotify_client_base.py  # Base API client (used by submodules)
│   ├── application/
│   │   └── health_service.py       # Connection health checks
│   └── config/
│       └── settings.py             # Module configuration
│
├── frontend/                   # Core UI only
│   ├── pages/
│   │   └── index.html          # Module dashboard
│   └── cards/
│       └── status_card.html    # Connection status
│
└── tests/                      # Integration tests (cross-submodule)
    ├── test_integration.py     # Full flow tests
    └── test_router_integration.py  # Tests with Module Router
```

### 2.1 Why This Structure?

**Main Module (~200 LOC):**
- Only connection management and health checks
- Provides base Spotify API client
- Coordinates submodules

**Auth Submodule (~800 LOC):**
- **Reusable** across any OAuth 2.0 service (Last.fm, etc.)
- Independent token lifecycle
- Can be developed/tested in isolation
- Different team can work on auth while another works on playlists

**Playlists Submodule (~1,200 LOC):**
- All playlist logic isolated
- Heavy feature, deserves own space
- Can be disabled if user only wants search

**Search Submodule (~600 LOC):**
- Stateless search functionality
- Simple and focused
- Fast to develop and test

**Library Submodule (~500 LOC):**
- Optional feature
- Can be added later without touching other code

**Benefits:**
- ✅ **No merge conflicts**: 4 developers can work on 4 submodules in parallel
- ✅ **Lean modules**: Main module stays under 500 LOC total
- ✅ **Clear ownership**: Each submodule has single responsibility
- ✅ **Easy testing**: Test each submodule independently

---

## 3. Module Capabilities

### 3.1 Capability Registration

```python
# modules/spotify/__init__.py

from .backend.application.health_service import SpotifyHealthService
from .submodules.auth.backend.application.auth_service import AuthService
from .submodules.playlists.backend.application.playlist_service import PlaylistService
from .submodules.search.backend.application.search_service import SearchService

class Module:
    """Spotify module interface."""
    
    name = "spotify"
    version = "1.0.0"
    description = "Spotify integration with OAuth, playlists, and search"
    
    # Register capabilities with Module Router
    capabilities = [
        {
            "operation": "auth.spotify",
            "handler": "spotify.auth.authorize",
            "priority": 10,
            "required_config": ["client_id", "client_secret"],
        },
        {
            "operation": "search.track",
            "handler": "spotify.search.search_tracks",
            "priority": 10,
            "required_modules": ["spotify.auth"],  # Depends on auth submodule
        },
        {
            "operation": "playlists.list",
            "handler": "spotify.playlists.list_playlists",
            "priority": 10,
            "required_modules": ["spotify.auth"],
        },
        {
            "operation": "playlists.sync",
            "handler": "spotify.playlists.sync_playlist",
            "priority": 10,
            "required_modules": ["spotify.auth"],
        },
    ]
    
    # Module dependencies
    depends_on = ["core"]
    optional_deps = ["soulseek"]  # For download integration
```

### 3.2 Integration with Soulseek

**Complete Flow (Pilot Module Integration Test):**

```python
# User searches for track
search_results = await module_router.route_request(
    operation="search.track",
    params={"query": "Beatles - Let It Be"}
)
# Router → Spotify.Search submodule

# User clicks download on a track
download_request = await module_router.route_request(
    operation="download.track",
    params={
        "track_id": search_results[0]["id"],
        "artist": search_results[0]["artist"],
        "title": search_results[0]["title"],
    }
)
# Router → Soulseek module

# Soulseek reports download complete
# Router → Spotify: notify track is downloaded
await event_bus.publish("download.completed", {
    "track_id": search_results[0]["id"],
    "file_path": "/music/beatles_let_it_be.mp3",
})

# Spotify submodule can update playlist with download status
```

---

## 4. Submodule Details

### 4.1 Auth Submodule (Reusable OAuth)

**Purpose:** Handle OAuth 2.0 flow for Spotify (and potentially other services).

**Domain Model:**

```python
# modules/spotify/submodules/auth/backend/domain/oauth_token.py

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

@dataclass
class OAuthToken:
    """
    OAuth 2.0 token entity.
    
    Hey future me – Spotify tokens expire after 1 hour. We store both
    access and refresh tokens. The refresh token never expires but can
    be revoked by user. Always check is_expired() before using.
    
    Domain invariants:
    - access_token is required
    - refresh_token is required (for Spotify)
    - expires_at must be in the future when created
    """
    
    access_token: str
    refresh_token: str
    expires_at: datetime
    scope: str
    token_type: str = "Bearer"
    
    def is_expired(self) -> bool:
        """
        Check if token is expired.
        
        Returns:
            bool: True if expired or expires in <5 minutes (buffer)
            
        Notes:
            We use 5-minute buffer to avoid race conditions where token
            expires between check and use.
        """
        buffer = timedelta(minutes=5)
        return datetime.utcnow() >= (self.expires_at - buffer)
    
    def time_until_expiry(self) -> timedelta:
        """Get time until token expires."""
        return self.expires_at - datetime.utcnow()
```

**Application Service:**

```python
# modules/spotify/submodules/auth/backend/application/auth_service.py

class AuthService:
    """
    OAuth 2.0 authentication service.
    
    Handles complete OAuth flow:
    1. Generate authorization URL
    2. Handle callback with authorization code
    3. Exchange code for tokens
    4. Refresh expired tokens
    5. Revoke tokens on logout
    """
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        token_repository: TokenRepository,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token_repo = token_repository
        self.logger = logging.getLogger(__name__)
    
    async def get_authorization_url(self, state: str) -> str:
        """
        Generate Spotify authorization URL.
        
        Args:
            state: CSRF protection token (random string)
            
        Returns:
            URL to redirect user to Spotify login
            
        Example:
            >>> url = await auth_service.get_authorization_url("random123")
            >>> print(url)
            https://accounts.spotify.com/authorize?client_id=...
        """
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "state": state,
            "scope": "playlist-read-private user-library-read",
        }
        return f"https://accounts.spotify.com/authorize?{urlencode(params)}"
    
    async def handle_callback(
        self, 
        code: str, 
        state: str
    ) -> OAuthToken:
        """
        Handle OAuth callback and exchange code for tokens.
        
        Args:
            code: Authorization code from Spotify
            state: State parameter for CSRF validation
            
        Returns:
            OAuthToken with access and refresh tokens
            
        Raises:
            AuthenticationError: If code exchange fails
            StateValidationError: If state doesn't match
            
        Notes:
            The authorization code is single-use and expires after 10 minutes.
            We must exchange it immediately.
        """
        # Validate state (CSRF protection)
        if not await self._validate_state(state):
            raise StateValidationError(
                code="SPOTIFY_AUTH_INVALID_STATE",
                message="State parameter validation failed",
                resolution="Please try logging in again",
                context={"state": state},
            )
        
        # Exchange code for tokens
        try:
            response = await self._exchange_code_for_tokens(code)
            token = self._parse_token_response(response)
            
            # Store token
            await self.token_repo.save(token)
            
            self.logger.info(
                "OAuth authentication successful",
                extra={
                    "module": "spotify.auth",
                    "expires_in": token.time_until_expiry().total_seconds(),
                }
            )
            
            return token
            
        except httpx.HTTPStatusError as e:
            raise AuthenticationError(
                code="SPOTIFY_AUTH_CODE_EXCHANGE_FAILED",
                message=f"Failed to exchange authorization code: {e.response.status_code}",
                resolution="Check client_id and client_secret in configuration",
                context={
                    "status_code": e.response.status_code,
                    "response": e.response.text,
                },
                docs_url="https://docs.soulspot.app/troubleshooting/spotify-auth"
            )
```

**Error Examples (Auth Submodule):**

```python
# Example 1: Missing configuration
❌ Spotify Configuration Missing

Code: SPOTIFY_AUTH_CONFIG_MISSING
Message: Spotify client_id or client_secret not configured
What to do:
  1. Go to Settings → Spotify
  2. Enter your Spotify app credentials
  3. Get credentials from: https://developer.spotify.com/dashboard
  4. Test connection before saving
Context:
  Module: spotify.auth
  Missing: client_id, client_secret
Docs: https://docs.soulspot.app/setup/spotify

# Example 2: Token expired
⚠️  Spotify Session Expired

Code: SPOTIFY_AUTH_TOKEN_EXPIRED
Message: Your Spotify session has expired
What to do: Click "Re-authenticate with Spotify" to refresh
Context:
  Module: spotify.auth
  Expired at: 2025-11-22 10:30:15
  Last refresh: 2025-11-22 09:30:15
Auto-fix: Attempting automatic refresh...

# Example 3: Token refresh failed
❌ Spotify Re-authentication Required

Code: SPOTIFY_AUTH_REFRESH_FAILED
Message: Could not automatically refresh Spotify token
What to do:
  1. Click "Re-authenticate with Spotify"
  2. Log in again with your Spotify account
  3. If problem persists, revoke app access in Spotify settings and re-add
Context:
  Module: spotify.auth
  Error: invalid_grant (refresh token revoked)
Docs: https://docs.soulspot.app/troubleshooting/spotify-reauth
```

### 4.2 Playlists Submodule

**Purpose:** Discover, synchronize, and manage Spotify playlists.

**Domain Model:**

```python
# modules/spotify/submodules/playlists/backend/domain/playlist.py

from dataclasses import dataclass
from datetime import datetime
from typing import List

@dataclass
class Playlist:
    """
    Spotify playlist entity.
    
    Represents a user's Spotify playlist with tracks. We store a local copy
    to enable offline viewing and track synchronization status.
    """
    
    id: str                         # Spotify playlist ID
    name: str
    owner: str                      # Spotify username
    description: str
    public: bool
    collaborative: bool
    tracks_total: int               # Total tracks in playlist
    tracks_synced: int = 0          # How many tracks are downloaded
    snapshot_id: str = ""           # Spotify's version identifier
    last_synced: datetime | None = None
    created_at: datetime = None
    
    def sync_progress(self) -> float:
        """
        Calculate sync progress percentage.
        
        Returns:
            Percentage (0-100) of tracks downloaded
            
        Example:
            >>> playlist = Playlist(tracks_total=100, tracks_synced=75)
            >>> playlist.sync_progress()
            75.0
        """
        if self.tracks_total == 0:
            return 100.0
        return (self.tracks_synced / self.tracks_total) * 100
    
    def needs_sync(self) -> bool:
        """
        Check if playlist needs synchronization.
        
        Returns:
            True if never synced or Spotify version changed
            
        Notes:
            Spotify's snapshot_id changes whenever playlist is modified
            (tracks added/removed/reordered).
        """
        if self.last_synced is None:
            return True
        
        # Check if snapshot_id changed (playlist modified on Spotify)
        # This will be checked against Spotify API
        return True  # Simplified for spec
```

**Application Service:**

```python
# modules/spotify/submodules/playlists/backend/application/playlist_service.py

class PlaylistService:
    """
    Playlist management service.
    
    Handles:
    - Fetching playlists from Spotify API
    - Syncing playlist metadata and tracks
    - Triggering downloads via Module Router
    """
    
    async def sync_playlist(
        self, 
        playlist_id: str,
        download: bool = False
    ) -> Playlist:
        """
        Synchronize playlist from Spotify.
        
        Args:
            playlist_id: Spotify playlist ID
            download: If True, trigger downloads for all tracks
            
        Returns:
            Updated Playlist entity
            
        Raises:
            PlaylistNotFoundError: If playlist doesn't exist
            AuthenticationError: If token is invalid
            
        Notes:
            This is a long-running operation for large playlists.
            We fetch tracks in batches of 50 (Spotify API limit).
        """
        self.logger.info(
            f"Starting playlist sync",
            extra={
                "playlist_id": playlist_id,
                "download": download,
            }
        )
        
        # Step 1: Fetch playlist metadata
        try:
            spotify_data = await self.spotify_client.get_playlist(playlist_id)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise PlaylistNotFoundError(
                    code="SPOTIFY_PLAYLIST_NOT_FOUND",
                    message=f"Playlist {playlist_id} not found",
                    resolution="Check playlist ID or URL",
                    context={"playlist_id": playlist_id},
                )
            raise
        
        # Step 2: Update local playlist record
        playlist = await self._update_playlist_metadata(spotify_data)
        
        # Step 3: Sync tracks
        tracks = await self._fetch_all_tracks(playlist_id)
        await self._update_tracks(playlist_id, tracks)
        
        # Step 4: Trigger downloads if requested
        if download:
            await self._trigger_downloads(playlist, tracks)
        
        self.logger.info(
            f"Playlist sync complete",
            extra={
                "playlist_id": playlist_id,
                "tracks_count": len(tracks),
                "download_triggered": download,
            }
        )
        
        return playlist
    
    async def _trigger_downloads(
        self,
        playlist: Playlist,
        tracks: List[PlaylistTrack]
    ) -> None:
        """
        Trigger downloads for all tracks via Module Router.
        
        This is where Spotify module integrates with Soulseek module.
        
        Hey future me – We use Module Router here instead of calling
        Soulseek directly. This allows the system to work even if
        Soulseek module is disabled. Router will show warning if
        downloader not available.
        """
        for track in tracks:
            try:
                # Use Module Router to find downloader
                await module_router.route_request(
                    operation="download.track",
                    params={
                        "source_id": track.spotify_id,
                        "source": "spotify",
                        "artist": track.artist,
                        "title": track.title,
                        "album": track.album,
                        "playlist_id": playlist.id,
                    }
                )
                
                self.logger.debug(
                    f"Download triggered for track",
                    extra={
                        "track_id": track.spotify_id,
                        "artist": track.artist,
                        "title": track.title,
                    }
                )
                
            except ModuleNotAvailableError as e:
                # Downloader module not available
                self.logger.warning(
                    f"Cannot download track: {e.code}",
                    extra={
                        "track_id": track.spotify_id,
                        "error": str(e),
                    }
                )
                # Don't raise – continue with other tracks
```

**API Endpoints:**

```python
# modules/spotify/submodules/playlists/backend/api/routes.py

router = APIRouter(prefix="/spotify/playlists", tags=["spotify-playlists"])

@router.get("/")
async def list_playlists(
    auth: OAuthToken = Depends(get_current_token),
) -> List[PlaylistSchema]:
    """
    List all user playlists.
    
    Returns local database records with sync status.
    """
    service = get_playlist_service()
    playlists = await service.list_playlists()
    return [PlaylistSchema.from_entity(p) for p in playlists]


@router.post("/{playlist_id}/sync")
async def sync_playlist(
    playlist_id: str,
    download: bool = False,
    auth: OAuthToken = Depends(get_current_token),
) -> PlaylistSchema:
    """
    Synchronize playlist from Spotify.
    
    Args:
        playlist_id: Spotify playlist ID or URL
        download: Whether to trigger downloads for tracks
        
    Returns:
        Updated playlist with sync status
        
    Example:
        POST /spotify/playlists/37i9dQZF1DXcBWIGoYBM5M/sync?download=true
        
        Response:
        {
            "id": "37i9dQZF1DXcBWIGoYBM5M",
            "name": "Today's Top Hits",
            "tracks_total": 50,
            "tracks_synced": 12,
            "sync_progress": 24.0,
            "last_synced": "2025-11-22T10:30:00Z"
        }
    """
    service = get_playlist_service()
    
    try:
        playlist = await service.sync_playlist(playlist_id, download=download)
        return PlaylistSchema.from_entity(playlist)
        
    except PlaylistNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "code": e.code,
                "message": e.message,
                "resolution": e.resolution,
            }
        )
```

### 4.3 Search Submodule

**Purpose:** Search for tracks, albums, and artists on Spotify.

**Domain Model:**

```python
# modules/spotify/submodules/search/backend/domain/search_result.py

@dataclass
class SearchResult:
    """
    Spotify search result.
    
    Represents a track/album/artist returned from search.
    """
    
    id: str              # Spotify ID
    type: str            # track, album, artist
    name: str
    artist: str
    album: str | None
    duration_ms: int | None
    spotify_url: str
    preview_url: str | None
    album_art_url: str | None
    
    # Download integration
    is_downloaded: bool = False
    download_status: str | None = None  # pending, completed, failed
    
    def can_download(self) -> bool:
        """Check if result can be downloaded."""
        return self.type == "track" and not self.is_downloaded
```

**Application Service:**

```python
# modules/spotify/submodules/search/backend/application/search_service.py

class SearchService:
    """
    Spotify search service.
    
    Handles track/album/artist search with caching.
    """
    
    async def search_tracks(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[SearchResult]:
        """
        Search for tracks on Spotify.
        
        Args:
            query: Search query (artist, title, album, etc.)
            limit: Maximum results (1-50)
            offset: Pagination offset
            
        Returns:
            List of search results
            
        Raises:
            InvalidQueryError: If query is empty or invalid
            RateLimitError: If Spotify rate limit hit
            
        Example:
            >>> results = await search_service.search_tracks("Beatles Let It Be")
            >>> for r in results:
            ...     print(f"{r.artist} - {r.name}")
            The Beatles - Let It Be - Remastered 2009
            The Beatles - Let It Be - Original Mix
        """
        # Validate query
        if not query or not query.strip():
            raise InvalidQueryError(
                code="SPOTIFY_SEARCH_EMPTY_QUERY",
                message="Search query cannot be empty",
                resolution="Enter at least 1 character to search",
                context={"query": query},
            )
        
        if len(query) > 500:
            raise InvalidQueryError(
                code="SPOTIFY_SEARCH_QUERY_TOO_LONG",
                message=f"Search query too long ({len(query)} characters)",
                resolution="Limit query to 500 characters",
                context={"query_length": len(query)},
            )
        
        self.logger.info(
            f"Searching Spotify",
            extra={
                "query": query,
                "limit": limit,
                "offset": offset,
            }
        )
        
        try:
            # Search Spotify API
            response = await self.spotify_client.search(
                q=query,
                type="track",
                limit=limit,
                offset=offset,
            )
            
            # Parse results
            results = [
                self._parse_track_result(item)
                for item in response.get("tracks", {}).get("items", [])
            ]
            
            # Check download status (cross-module query)
            await self._enrich_with_download_status(results)
            
            self.logger.info(
                f"Search complete",
                extra={
                    "results_count": len(results),
                    "query": query,
                }
            )
            
            return results
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError(
                    code="SPOTIFY_SEARCH_RATE_LIMIT",
                    message="Spotify rate limit exceeded",
                    resolution="Wait 60 seconds before searching again",
                    context={
                        "retry_after": e.response.headers.get("Retry-After", "60"),
                    },
                )
            raise
    
    async def _enrich_with_download_status(
        self,
        results: List[SearchResult]
    ) -> None:
        """
        Check if tracks are already downloaded.
        
        This queries the Library module via Module Router.
        
        Hey future me – This is optional enrichment. If Library module
        is not available, we just skip this and results show as not downloaded.
        """
        try:
            spotify_ids = [r.id for r in results]
            
            # Query library module
            downloaded = await module_router.route_request(
                operation="library.check_downloaded",
                params={"spotify_ids": spotify_ids}
            )
            
            # Update results
            downloaded_set = set(downloaded.get("ids", []))
            for result in results:
                result.is_downloaded = result.id in downloaded_set
                
        except ModuleNotAvailableError:
            # Library module not available, skip enrichment
            self.logger.debug("Library module not available, skipping download status")
```

---

## 5. Frontend Cards

### 5.1 Status Card

```html
<!-- modules/spotify/frontend/cards/status_card.html -->

<div class="card card--status" data-module="spotify">
  <div class="card__header">
    <h3 class="card__title">Spotify Connection</h3>
    <span class="card__badge card__badge--{{ status }}">
      {{ status }}
    </span>
  </div>
  
  <div class="card__body">
    {% if connected %}
      <div class="status__item">
        <span class="status__label">Account:</span>
        <span class="status__value">{{ user.display_name }}</span>
      </div>
      
      <div class="status__item">
        <span class="status__label">Playlists:</span>
        <span class="status__value">{{ playlists_count }} synced</span>
      </div>
      
      <div class="status__item">
        <span class="status__label">Token expires:</span>
        <span class="status__value">{{ token_expiry }}</span>
      </div>
    {% else %}
      <div class="status__message status__message--warning">
        <p>Not connected to Spotify</p>
        <a href="/spotify/auth/login" class="btn btn--primary">
          Connect Spotify Account
        </a>
      </div>
    {% endif %}
  </div>
  
  <div class="card__footer">
    <button 
      hx-post="/spotify/health/check"
      hx-target="closest .card"
      hx-swap="outerHTML"
      class="btn btn--secondary"
    >
      Refresh Status
    </button>
  </div>
</div>
```

### 5.2 Playlist List Card

```html
<!-- modules/spotify/submodules/playlists/frontend/cards/playlist_list_card.html -->

<div class="card card--list" data-module="spotify-playlists">
  <div class="card__header">
    <h3 class="card__title">Your Playlists</h3>
    <button 
      hx-post="/spotify/playlists/refresh"
      hx-target="closest .card .card__body"
      hx-swap="innerHTML"
      class="btn btn--sm btn--secondary"
    >
      Refresh from Spotify
    </button>
  </div>
  
  <div class="card__body">
    <div class="list">
      {% for playlist in playlists %}
        <div class="list__item" data-playlist-id="{{ playlist.id }}">
          <div class="list__item-content">
            <h4 class="list__item-title">{{ playlist.name }}</h4>
            <p class="list__item-subtitle">
              {{ playlist.tracks_total }} tracks
              {% if playlist.tracks_synced > 0 %}
                · {{ playlist.sync_progress|round(0) }}% downloaded
              {% endif %}
            </p>
          </div>
          
          <div class="list__item-actions">
            <button 
              hx-post="/spotify/playlists/{{ playlist.id }}/sync"
              hx-target="closest .list__item"
              hx-swap="outerHTML"
              class="btn btn--sm btn--secondary"
            >
              Sync
            </button>
            
            <button 
              hx-post="/spotify/playlists/{{ playlist.id }}/sync?download=true"
              hx-target="closest .list__item"
              hx-swap="outerHTML"
              hx-confirm="Download all {{ playlist.tracks_total }} tracks?"
              class="btn btn--sm btn--primary"
            >
              Sync & Download
            </button>
          </div>
          
          {% if playlist.sync_progress > 0 and playlist.sync_progress < 100 %}
            <div class="list__item-progress">
              <div class="progress-bar">
                <div 
                  class="progress-bar__fill" 
                  style="width: {{ playlist.sync_progress }}%"
                ></div>
              </div>
            </div>
          {% endif %}
        </div>
      {% endfor %}
    </div>
  </div>
</div>
```

### 5.3 Search Card

```html
<!-- modules/spotify/submodules/search/frontend/cards/search_form_card.html -->

<div class="card card--action" data-module="spotify-search">
  <div class="card__header">
    <h3 class="card__title">Search Spotify</h3>
  </div>
  
  <div class="card__body">
    <form 
      hx-post="/spotify/search"
      hx-target="#search-results"
      hx-swap="innerHTML"
      hx-indicator="#search-spinner"
    >
      <div class="form-group">
        <label for="search-query">Track, Artist, or Album</label>
        <input 
          type="text" 
          id="search-query"
          name="query"
          placeholder="Enter search query..."
          required
          minlength="1"
          class="form-control"
        />
      </div>
      
      <button type="submit" class="btn btn--primary">
        Search
        <span id="search-spinner" class="spinner htmx-indicator"></span>
      </button>
    </form>
  </div>
</div>

<!-- Results displayed below -->
<div id="search-results"></div>
```

---

## 6. Error Messages

### 6.1 Authentication Errors

```python
# Example 1: Not authenticated
⚠️  Spotify Authentication Required

Code: SPOTIFY_AUTH_REQUIRED
Message: You need to connect your Spotify account
What to do: Click "Connect Spotify Account" in the Spotify status card
Context:
  Module: spotify
  Operation: playlists.list
  User authenticated: false
Docs: https://docs.soulspot.app/setup/spotify

# Example 2: Token refresh failed
❌ Spotify Re-authentication Required

Code: SPOTIFY_AUTH_REFRESH_FAILED
Message: Could not refresh Spotify token
What to do:
  1. Go to Spotify settings
  2. Click "Disconnect and reconnect"
  3. Log in again with Spotify
Reason: Your Spotify refresh token has been revoked
Context:
  Module: spotify.auth
  Last successful auth: 2025-11-22 09:00:00
  Error from Spotify: invalid_grant
Docs: https://docs.soulspot.app/troubleshooting/spotify-reauth
```

### 6.2 Playlist Errors

```python
# Example 1: Playlist not found
❌ Playlist Not Found

Code: SPOTIFY_PLAYLIST_NOT_FOUND
Message: Playlist '37i9dQZF1DXcBWIGoYBM5M' not found
What to do:
  1. Check the playlist ID or URL
  2. Ensure you have access to the playlist
  3. If private playlist, make sure you're the owner or collaborator
Context:
  Module: spotify.playlists
  Playlist ID: 37i9dQZF1DXcBWIGoYBM5M
  User: john_doe
Docs: https://docs.soulspot.app/spotify/playlists#troubleshooting

# Example 2: Rate limit hit
⚠️  Spotify Rate Limit

Code: SPOTIFY_PLAYLISTS_RATE_LIMIT
Message: Too many requests to Spotify API
What to do: Wait 60 seconds before syncing more playlists
Context:
  Module: spotify.playlists
  Retry after: 60 seconds
  Requests made: 100 (limit: 100/hour)
Auto-retry: Will automatically retry in 60 seconds
```

### 6.3 Search Errors

```python
# Example 1: Empty query
❌ Empty Search Query

Code: SPOTIFY_SEARCH_EMPTY_QUERY
Message: Search query cannot be empty
What to do: Enter at least 1 character to search for tracks
Context:
  Module: spotify.search
  Query length: 0

# Example 2: No results
ℹ️  No Results Found

Code: SPOTIFY_SEARCH_NO_RESULTS
Message: No tracks found for "zxcvbnmasdfghjklqwertyuiop"
What to do:
  1. Check spelling
  2. Try different keywords
  3. Use artist and song name (e.g., "Beatles Let It Be")
Context:
  Module: spotify.search
  Query: zxcvbnmasdfghjklqwertyuiop
  Results: 0
```

---

## 7. Testing Strategy

### 7.1 Unit Tests (Submodule-Level)

```python
# modules/spotify/submodules/auth/tests/test_token_service.py

import pytest
from datetime import datetime, timedelta
from spotify.submodules.auth.backend.domain.oauth_token import OAuthToken
from spotify.submodules.auth.backend.application.token_service import TokenService

@pytest.fixture
def valid_token():
    """Create a valid non-expired token."""
    return OAuthToken(
        access_token="access_123",
        refresh_token="refresh_456",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        scope="playlist-read-private",
    )

@pytest.fixture
def expired_token():
    """Create an expired token."""
    return OAuthToken(
        access_token="access_789",
        refresh_token="refresh_012",
        expires_at=datetime.utcnow() - timedelta(minutes=10),
        scope="playlist-read-private",
    )

def test_token_is_not_expired_when_valid(valid_token):
    """Valid token should not be expired."""
    assert not valid_token.is_expired()

def test_token_is_expired_when_past_expiry(expired_token):
    """Expired token should be detected."""
    assert expired_token.is_expired()

def test_token_is_expired_within_buffer():
    """
    Token expiring in <5 minutes should be considered expired.
    
    Why: This prevents race conditions where token expires between
    check and use. Buffer gives us time to refresh.
    """
    almost_expired = OAuthToken(
        access_token="access_buffer",
        refresh_token="refresh_buffer",
        expires_at=datetime.utcnow() + timedelta(minutes=3),
        scope="playlist-read-private",
    )
    
    assert almost_expired.is_expired()  # Should be expired due to 5min buffer

@pytest.mark.asyncio
async def test_token_refresh_success(token_service, expired_token):
    """Expired token should be refreshed successfully."""
    # Mock Spotify API response
    mock_response = {
        "access_token": "new_access_token",
        "token_type": "Bearer",
        "expires_in": 3600,
    }
    
    with patch_spotify_api_call(mock_response):
        new_token = await token_service.refresh_token(expired_token)
        
        assert new_token.access_token == "new_access_token"
        assert not new_token.is_expired()
```

### 7.2 Integration Tests (Cross-Submodule)

```python
# modules/spotify/tests/test_integration.py

@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_spotify_flow():
    """
    Test complete flow: Auth → Search → Playlist Sync.
    
    This tests integration between all Spotify submodules.
    """
    # Step 1: Authenticate
    auth_service = get_auth_service()
    token = await auth_service.handle_callback(
        code="auth_code_123",
        state="state_456",
    )
    assert token is not None
    
    # Step 2: Search for tracks
    search_service = get_search_service()
    results = await search_service.search_tracks("Beatles Let It Be")
    assert len(results) > 0
    
    # Step 3: Get playlists
    playlist_service = get_playlist_service()
    playlists = await playlist_service.list_playlists()
    assert len(playlists) > 0
    
    # Step 4: Sync a playlist
    playlist = await playlist_service.sync_playlist(
        playlist_id=playlists[0].id,
        download=False,  # Don't trigger downloads in test
    )
    assert playlist.last_synced is not None
```

### 7.3 Router Integration Tests (Spotify ↔ Soulseek)

```python
# modules/spotify/tests/test_router_integration.py

@pytest.mark.integration
@pytest.mark.asyncio
async def test_spotify_to_soulseek_download():
    """
    Test Module Router orchestration: Spotify → Soulseek.
    
    This is the critical integration test for pilot modules.
    """
    # Step 1: Search on Spotify
    search_results = await module_router.route_request(
        operation="search.track",
        params={"query": "Beatles Let It Be"}
    )
    assert len(search_results) > 0
    
    # Step 2: Trigger download via Router
    track = search_results[0]
    download_request = await module_router.route_request(
        operation="download.track",
        params={
            "source_id": track["id"],
            "source": "spotify",
            "artist": track["artist"],
            "title": track["name"],
        }
    )
    
    # Router should have routed to Soulseek module
    assert download_request["module"] == "soulseek"
    assert download_request["status"] == "pending"
    
    # Step 3: Wait for download completion event
    event = await wait_for_event("download.completed", timeout=30)
    assert event.data["source_id"] == track["id"]
    
    # Step 4: Verify Spotify was notified
    # (Spotify should update track status to downloaded)
    updated_results = await module_router.route_request(
        operation="search.track",
        params={"query": "Beatles Let It Be"}
    )
    
    downloaded_track = next(
        (r for r in updated_results if r["id"] == track["id"]),
        None
    )
    assert downloaded_track is not None
    assert downloaded_track["is_downloaded"] is True
```

---

## 8. Configuration

### 8.1 Module Settings

```python
# modules/spotify/backend/config/settings.py

from pydantic import BaseSettings, Field

class SpotifySettings(BaseSettings):
    """
    Spotify module configuration.
    
    All settings loaded from database (post-onboarding).
    Secrets are encrypted at rest.
    """
    
    # OAuth credentials (REQUIRED)
    client_id: str = Field(
        ...,
        description="Spotify app client ID",
        docs="Get from https://developer.spotify.com/dashboard",
    )
    
    client_secret: str = Field(
        ...,
        description="Spotify app client secret (encrypted)",
        sensitive=True,  # Marks for encryption
    )
    
    redirect_uri: str = Field(
        default="http://localhost:8765/spotify/auth/callback",
        description="OAuth redirect URI (must match Spotify app settings)",
    )
    
    # API settings
    api_base_url: str = Field(
        default="https://api.spotify.com/v1",
        description="Spotify API base URL",
    )
    
    timeout: int = Field(
        default=30,
        description="API request timeout (seconds)",
        ge=5,
        le=120,
    )
    
    # Feature flags
    enable_playlists: bool = Field(
        default=True,
        description="Enable playlist sync feature",
    )
    
    enable_search: bool = Field(
        default=True,
        description="Enable track search feature",
    )
    
    enable_library: bool = Field(
        default=False,
        description="Enable user library access (optional)",
    )
    
    # Rate limiting
    max_requests_per_second: int = Field(
        default=10,
        description="Max API requests per second",
        ge=1,
        le=100,
    )
    
    class Config:
        env_prefix = "SPOTIFY_"
        case_sensitive = False
```

### 8.2 Onboarding Configuration

```python
# During onboarding, user provides:

# Step 1: Spotify Credentials
{
  "client_id": "abc123def456",
  "client_secret": "secret789xyz012",  # Will be encrypted
  "redirect_uri": "http://localhost:8765/spotify/auth/callback"
}

# Step 2: Test connection
# - Attempt OAuth flow
# - Verify credentials work
# - Show success: "✅ Connected! Found 42 playlists"

# Step 3: Save to database (encrypted)
await config_service.save_config(
    module_name="spotify",
    config={
        "client_id": "abc123def456",
        "client_secret": encrypt("secret789xyz012"),
    },
    sensitive_keys=["client_secret"],
)
```

---

## 9. Parallel Development

### 9.1 No Merge Conflicts

**How It Works:**

```bash
# Developer A: Works on auth submodule
cd modules/spotify/submodules/auth/
git checkout -b feature/improve-token-refresh
# Edits: backend/application/token_service.py
git commit -m "Add automatic token refresh retry"

# Developer B: Works on playlists submodule (SAME TIME)
cd modules/spotify/submodules/playlists/
git checkout -b feature/add-playlist-folders
# Edits: backend/domain/playlist.py, backend/application/playlist_service.py
git commit -m "Add playlist folder support"

# Developer C: Works on search submodule (SAME TIME)
cd modules/spotify/submodules/search/
git checkout -b feature/album-search
# Edits: backend/application/search_service.py
git commit -m "Add album search support"

# RESULT: No conflicts!
# All three developers work in completely separate directory trees
```

**Benefits:**
- ✅ **No waiting**: Developers work independently
- ✅ **Clean PRs**: Each PR touches only one submodule
- ✅ **Easy reviews**: Reviewers only review one focused area
- ✅ **Safe merging**: No conflicts between unrelated features

### 9.2 Independent Testing

```bash
# Test only auth submodule
pytest modules/spotify/submodules/auth/tests/

# Test only playlists submodule
pytest modules/spotify/submodules/playlists/tests/

# Test only search submodule
pytest modules/spotify/submodules/search/tests/

# Test full integration
pytest modules/spotify/tests/test_integration.py
```

---

## 10. Summary

### 10.1 Module Characteristics

**Spotify Module:**
- **Size**: ~3,000 LOC total (main: 200, submodules: 2,800)
- **Submodules**: 4 (Auth, Playlists, Search, Library)
- **Purpose**: Spotify integration with OAuth, playlists, and search
- **Pilot Module**: Yes (required for testing with Soulseek)

**Key Benefits:**
- ✅ **Lean main module**: Only connection management
- ✅ **Reusable auth**: OAuth submodule can be used by other services
- ✅ **Parallel development**: 4 teams can work simultaneously
- ✅ **No merge conflicts**: Clear submodule boundaries
- ✅ **Comprehensive errors**: 50+ error messages with actionable resolutions
- ✅ **Well-documented**: Docstrings, inline comments, ADRs
- ✅ **Card-based UI**: No widget proliferation

### 10.2 Integration Points

**With Soulseek Module:**
- Search → Download: Spotify search triggers Soulseek download
- Download Complete: Soulseek notifies Spotify when file ready
- Status Sync: Spotify shows download status for tracks

**With Library Module:**
- Track Status: Check if Spotify tracks are downloaded
- Metadata Enrichment: Library enriches Spotify metadata

**With Metadata Module:**
- Cover Art: Fetch high-res album art
- Track Info: Enrich with MusicBrainz data

---

## 11. Next Steps

1. **Implement Auth Submodule** (Week 1-2)
   - OAuth 2.0 flow
   - Token management
   - Encryption integration
   
2. **Implement Search Submodule** (Week 2-3)
   - Track search
   - Result parsing
   - UI search card
   
3. **Implement Playlists Submodule** (Week 3-4)
   - Playlist sync
   - Download trigger integration
   - Progress tracking
   
4. **Integration Testing** (Week 4)
   - Spotify ↔ Soulseek flow
   - Error messaging validation
   - UI card validation
   
5. **Documentation** (Ongoing)
   - Submodule READMEs
   - API documentation
   - Event schemas

---

**End of Spotify Module Specification**
