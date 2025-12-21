"""Dependency injection for API endpoints."""

import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, cast

from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.services.credentials_service import CredentialsService
from soulspot.application.services.session_store import (
    DatabaseSessionStore,
)
from soulspot.application.services.token_manager import TokenManager
from soulspot.domain.exceptions import TokenRefreshException

if TYPE_CHECKING:
    from soulspot.application.services.deezer_auth_service import (
        DeezerAuthService,
    )
    from soulspot.application.services.images import ImageService
    from soulspot.application.services.spotify_auth_service import (
        SpotifyAuthService,
    )
    from soulspot.application.services.token_manager import DatabaseTokenManager
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin
from soulspot.application.use_cases.enrich_metadata import EnrichMetadataUseCase
from soulspot.application.use_cases.import_spotify_playlist import (
    ImportSpotifyPlaylistUseCase,
)
from soulspot.application.use_cases.queue_playlist_downloads import (
    QueuePlaylistDownloadsUseCase,
)
from soulspot.application.use_cases.search_and_download import (
    SearchAndDownloadTrackUseCase,
)
from soulspot.application.workers.download_worker import DownloadWorker
from soulspot.application.workers.job_queue import JobQueue
from soulspot.config import Settings, get_settings
from soulspot.infrastructure.integrations.deezer_client import DeezerClient
from soulspot.infrastructure.integrations.lastfm_client import LastfmClient
from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient
from soulspot.infrastructure.integrations.slskd_client import SlskdClient
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
from soulspot.infrastructure.persistence.database import Database
from soulspot.infrastructure.persistence.repositories import (
    AlbumRepository,
    ArtistRepository,
    DownloadRepository,
    PlaylistRepository,
    SpotifyBrowseRepository,
    TrackRepository,
)

logger = logging.getLogger(__name__)


# Hey future me, NOW WE GET SESSION STORE FROM APP STATE! The DatabaseSessionStore is initialized
# during app startup (see main.py lifespan()) and attached to app.state.session_store. This gives
# us database-backed sessions that persist across restarts. If session_store isn't in app.state,
# something went wrong during startup - return 503 to indicate server not ready. The DB session
# factory is already available via get_db_session, which the store uses for persistence!
def get_session_store(request: Request) -> DatabaseSessionStore:
    """Get database-backed session store from app state.

    Returns:
        DatabaseSessionStore instance with database persistence

    Raises:
        HTTPException: 503 if session store not initialized
    """
    if not hasattr(request.app.state, "session_store"):
        raise HTTPException(
            status_code=503,
            detail="Session store not initialized",
        )
    return cast(DatabaseSessionStore, request.app.state.session_store)


# Hey future me - this is a FastAPI dependency that yields a DB session to endpoints.
# We use the session_scope() context manager instead of the get_session() async generator
# because the context manager pattern properly handles connection cleanup.
#
# The old "async for session in db.get_session()" pattern caused "GC cleaning up non-checked-in
# connection" warnings because:
# 1. FastAPI calls the generator, gets one session, then breaks out
# 2. The break triggers GeneratorExit during SQLAlchemy operations
# 3. Connection cleanup fails, leaving it for GC to clean up
#
# The session_scope() context manager is cleaner and avoids these race conditions.
# Use this in endpoint params like: "session: AsyncSession = Depends(get_db_session)"
async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Get database session from app state.

    Uses session_scope() context manager for proper connection lifecycle management.
    FastAPI automatically handles cleanup when the request completes.
    """
    db: Database = request.app.state.db
    async with db.session_scope() as session:
        yield session


# Hey future me - CredentialsService is the NEW way to get service credentials!
# It uses database-first approach with .env fallback for migration period.
# After migration complete, .env fallback will be removed.
# All credentials (Spotify, slskd, Deezer) should be accessed through this service.
# Use this in endpoint params like: "credentials: CredentialsService = Depends(get_credentials_service)"
#
# CRITICAL (Jan 2025 fix): We MUST pass fallback_settings to enable ENV var fallback!
# Without it, DB-only mode is used, and users with .env configs get "missing client_id" errors.
# The fallback kicks in when DB values are empty/default.
async def get_credentials_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> CredentialsService:
    """Get CredentialsService for database-first credential access.

    The service checks database (app_settings) first, falls back to .env if not set.
    This enables smooth migration from .env-based to database-based credentials.

    Args:
        session: Database session for app_settings access
        settings: Application settings for .env fallback

    Returns:
        CredentialsService instance ready for credential lookups
    """
    return CredentialsService(session, fallback_settings=settings)


# Hey future me - ImageService for disk usage stats and image caching!
# Uses cache_base_path from settings.storage.image_path (Docker: /config/images).
# This is a simple factory - no session needed for disk operations.
def get_image_service(settings: Settings = Depends(get_settings)) -> "ImageService":
    """Get ImageService instance configured with storage paths.

    Args:
        settings: Application settings for image_path configuration

    Returns:
        ImageService instance ready for disk operations
    """
    from soulspot.application.services.images import ImageService

    return ImageService(
        cache_base_path=str(settings.storage.image_path),
        local_serve_prefix="/images/local",
    )


# Yo, creates NEW SpotifyClient on EVERY request! Not cached/singleton. This is fine because
# SpotifyClient is stateless (httpx client inside is pooled). If SpotifyClient becomes expensive
# to construct, add @lru_cache but watch out - settings changes won't take effect until restart!
# UPDATE: Now gets credentials from DB-first via CredentialsService (with .env fallback)!
async def get_spotify_client(
    credentials_service: CredentialsService = Depends(get_credentials_service),
) -> SpotifyClient:
    """Get Spotify client instance with DB-first credentials.

    Credentials are loaded from database via CredentialsService with .env fallback.
    This enables runtime credential updates without app restart.
    """
    from soulspot.config.settings import SpotifySettings

    spotify_creds = await credentials_service.get_spotify_credentials()

    # Create SpotifySettings from DB credentials
    spotify_settings = SpotifySettings(
        client_id=spotify_creds.client_id,
        client_secret=spotify_creds.client_secret,
        redirect_uri=spotify_creds.redirect_uri,
    )
    return SpotifyClient(spotify_settings)


# Hey future me - SpotifyAuthService wraps all OAuth operations cleanly!
# Use this instead of creating SpotifyClient in routers for auth operations.
# The service handles: auth URL generation, code exchange, token refresh.
# It's stateless - doesn't store tokens, that's the caller's job.
# UPDATE: Now gets credentials from DB-first via CredentialsService (with .env fallback)!
async def get_spotify_auth_service(
    credentials_service: CredentialsService = Depends(get_credentials_service),
) -> "SpotifyAuthService":
    """Get SpotifyAuthService for OAuth operations.

    Creates a SpotifyAuthService that handles all OAuth complexity:
    - Auth URL generation with PKCE
    - Authorization code exchange
    - Token refresh

    Credentials are loaded from database via CredentialsService with .env fallback.

    Returns:
        SpotifyAuthService instance
    """
    from soulspot.application.services.spotify_auth_service import SpotifyAuthService
    from soulspot.config.settings import SpotifySettings

    spotify_creds = await credentials_service.get_spotify_credentials()

    # Create SpotifySettings from DB credentials
    spotify_settings = SpotifySettings(
        client_id=spotify_creds.client_id,
        client_secret=spotify_creds.client_secret,
        redirect_uri=spotify_creds.redirect_uri,
    )
    return SpotifyAuthService(spotify_settings)


# Hey future me - DeezerAuthService wraps all Deezer OAuth operations!
# Unlike Spotify:
# - NO PKCE (simpler OAuth 2.0 flow)
# - NO refresh_token (Deezer tokens are long-lived ~90 days)
# - Public API doesn't need auth at all (charts, releases)
# Only needed for user-specific operations (favorites, playlists)
async def get_deezer_auth_service(
    credentials_service: CredentialsService = Depends(get_credentials_service),
) -> "DeezerAuthService":
    """Get DeezerAuthService for OAuth operations.

    Creates a DeezerAuthService that handles Deezer OAuth:
    - Auth URL generation (simple OAuth 2.0, no PKCE)
    - Authorization code exchange
    - NO token refresh (Deezer tokens are long-lived)

    Credentials are loaded from database via CredentialsService with .env fallback.

    Returns:
        DeezerAuthService instance
    """
    from soulspot.application.services.deezer_auth_service import DeezerAuthService
    from soulspot.infrastructure.integrations.deezer_client import DeezerOAuthConfig

    deezer_creds = await credentials_service.get_deezer_credentials()

    oauth_config = DeezerOAuthConfig(
        app_id=deezer_creds.app_id,
        secret=deezer_creds.secret,
        redirect_uri=deezer_creds.redirect_uri,
    )

    return DeezerAuthService(oauth_config)


# Hey future me - SpotifyPlugin dependency! The plugin wraps SpotifyClient and handles token
# management internally. This is the NEW way to interact with Spotify API. All services should
# use SpotifyPlugin instead of raw SpotifyClient. The plugin handles:
# 1. Token management (auto-refresh when needed)
# 2. Converting raw JSON responses to DTOs (ArtistDTO, AlbumDTO, TrackDTO, etc.)
# 3. Pagination handling for list endpoints
# Use this in endpoint params like: "spotify_plugin: SpotifyPlugin = Depends(get_spotify_plugin)"
# UPDATE: Now gets credentials from DB-first via CredentialsService (with .env fallback)!
async def get_spotify_plugin(
    request: Request,
    credentials_service: CredentialsService = Depends(get_credentials_service),
) -> "SpotifyPlugin":
    """Get SpotifyPlugin instance with token management.

    Creates a SpotifyPlugin that wraps SpotifyClient and handles token management
    internally. The plugin fetches tokens from DatabaseTokenManager.

    Credentials are loaded from database via CredentialsService with .env fallback.

    Args:
        request: FastAPI request for app state access
        credentials_service: Service for DB-first credential access

    Returns:
        SpotifyPlugin instance ready for API calls

    Raises:
        HTTPException: 503 if plugin cannot be created
    """
    from soulspot.config.settings import SpotifySettings
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

    try:
        # Get credentials from DB (with .env fallback)
        spotify_creds = await credentials_service.get_spotify_credentials()
        spotify_settings = SpotifySettings(
            client_id=spotify_creds.client_id,
            client_secret=spotify_creds.client_secret,
            redirect_uri=spotify_creds.redirect_uri,
        )
        spotify_client = SpotifyClient(spotify_settings)
        db_token_manager: DatabaseTokenManager = request.app.state.db_token_manager

        # Get access token from token manager
        access_token = await db_token_manager.get_token_for_background()
        if not access_token:
            raise HTTPException(
                status_code=401,
                detail="Not authenticated with Spotify. Please connect your account first.",
            )

        return SpotifyPlugin(
            client=spotify_client,
            access_token=access_token,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create SpotifyPlugin: {e}")
        raise HTTPException(
            status_code=503,
            detail="Spotify plugin not available",
        ) from e


# Hey future me - MULTI-SERVICE PATTERN: Optional Spotify Plugin!
# Use this instead of get_spotify_plugin when you want FALLBACK to other services.
# Returns None if user is not logged in to Spotify, instead of raising HTTPException.
# Routes should check if spotify_plugin is None and use Deezer fallback!
async def get_spotify_plugin_optional(
    request: Request,
    credentials_service: CredentialsService = Depends(get_credentials_service),
) -> "SpotifyPlugin | None":
    """Get SpotifyPlugin instance, or None if not authenticated.

    MULTI-SERVICE PATTERN: This dependency returns None instead of raising HTTPException
    when the user is not authenticated with Spotify. Use this for routes that should
    work with Deezer fallback when Spotify is unavailable.

    Args:
        request: FastAPI request for app state access
        credentials_service: Service for DB-first credential access

    Returns:
        SpotifyPlugin instance if authenticated, None otherwise
    """
    from soulspot.config.settings import SpotifySettings
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

    try:
        spotify_creds = await credentials_service.get_spotify_credentials()
        spotify_settings = SpotifySettings(
            client_id=spotify_creds.client_id,
            client_secret=spotify_creds.client_secret,
            redirect_uri=spotify_creds.redirect_uri,
        )
        spotify_client = SpotifyClient(spotify_settings)
        db_token_manager: DatabaseTokenManager = request.app.state.db_token_manager

        access_token = await db_token_manager.get_token_for_background()
        if not access_token:
            # MULTI-SERVICE: No exception, just return None
            logger.debug("No Spotify token available - returning None for optional plugin")
            return None

        return SpotifyPlugin(
            client=spotify_client,
            access_token=access_token,
        )
    except Exception as e:
        logger.debug(f"Spotify plugin unavailable (optional): {e}")
        return None


# Hey future me, this is a helper to parse Bearer tokens consistently! We extract this logic
# because it's used by get_session_id dependency (for every auth'd request). The logic is: if string
# starts with "bearer " (case-insensitive), strip it and return the rest. Otherwise return the whole
# string. If you change how Bearer tokens are parsed, change it HERE!
def parse_bearer_token(authorization: str) -> str:
    """Parse Authorization header to extract session ID.

    Handles both "Bearer {token}" and raw token formats.
    Bearer prefix is case-insensitive.

    Args:
        authorization: Authorization header value

    Returns:
        Session ID with Bearer prefix removed (if present)
    """
    # Remove "Bearer " prefix if present (case-insensitive)
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    # If no "Bearer " prefix, treat entire value as session ID (lenient)
    return authorization.strip()


# Hey future me, NOW SUPPORTS BOTH COOKIE AND BEARER TOKEN AUTH! This is for multi-device access -
# users can either use the default session cookie (browser) OR pass session_id via Authorization header
# (API clients, curl, another browser). We check Authorization first (explicit > implicit), then fall
# back to cookie. The parse_bearer_token() helper handles the "Bearer " prefix extraction consistently.
# IMPORTANT: We check for empty/whitespace-only headers to avoid processing blank Authorization headers
# as valid - if someone sends "Authorization: " with no value, we should fall back to cookie!
# This makes session IDs PORTABLE across devices but also more vulnerable to theft - MUST use HTTPS!
async def get_session_id(
    authorization: str | None = Header(None),
    session_id_cookie: str | None = Cookie(None, alias="session_id"),
) -> str | None:
    """Extract session ID from either Authorization header or cookie.

    Supports multi-device authentication by allowing session ID in bearer token format.
    Header takes precedence over cookie for explicit auth.

    Args:
        authorization: Authorization header (format: "Bearer {session_id}")
        session_id_cookie: Session ID from cookie

    Returns:
        Session ID or None if not found in either source
    """
    # Check Authorization header first (explicit auth)
    # Empty/whitespace-only headers should fall back to cookie
    if authorization and authorization.strip():
        return parse_bearer_token(authorization)

    # Fall back to cookie (default browser auth)
    return session_id_cookie


# Hey future me, this is THE CORE AUTH DEPENDENCY for all Spotify API endpoints! It does FOUR things now:
# 1) Checks session ID from EITHER cookie OR Authorization header (multi-device support!),
# 2) Validates session exists and is not expired, 3) Extracts access token from session,
# 4) AUTO-REFRESHES expired tokens using the refresh_token. This is super convenient - endpoints just
# inject this and get a VALID token without thinking about expiration! The new get_session_id() dependency
# allows users to access from multiple devices by sharing their session_id via API clients. BUT session IDs
# are now MORE SENSITIVE - they can be copied/stolen! Require HTTPS in production!
async def get_spotify_token_from_session(
    session_store: DatabaseSessionStore = Depends(get_session_store),
    spotify_client: SpotifyClient = Depends(get_spotify_client),
    session_id: str | None = Depends(get_session_id),
) -> str:
    """Get valid Spotify access token from session with automatic refresh.

    This dependency automatically retrieves the Spotify access token from the
    user's session. If the token is expired, it will automatically refresh it
    using the refresh token.

    Supports multi-device access via both cookie and Authorization header.

    Args:
        session_id: Session ID from cookie or Authorization header
        session_store: Session store instance
        spotify_client: Spotify client for token refresh

    Returns:
        Valid Spotify access token

    Raises:
        HTTPException: 401 if no session or token found, or if refresh fails
    """
    # Check if session exists
    if not session_id:
        raise HTTPException(
            status_code=401,
            detail="No session found. Please authenticate with Spotify first.",
        )

    session = await session_store.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session. Please authenticate with Spotify again.",
        )

    # Check if we have a token
    if not session.access_token:
        raise HTTPException(
            status_code=401,
            detail="No Spotify token in session. Please authenticate with Spotify.",
        )

    # Check if token is expired and refresh if needed
    if session.is_token_expired():
        if not session.refresh_token:
            raise HTTPException(
                status_code=401,
                detail="Token expired and no refresh token available. Please re-authenticate with Spotify.",
            )

        try:
            # Refresh the token using the stored refresh token
            # Hey future me - this is the KEY part of token renewal!
            # spotify_client.refresh_token() will:
            # 1. Send refresh_token to Spotify's token endpoint
            # 2. Return new access_token (and possibly new refresh_token)
            # 3. Raise TokenRefreshException if refresh token is invalid/revoked
            token_data = await spotify_client.refresh_token(session.refresh_token)

            # Update session with new tokens
            # Hey - Spotify MAY return a new refresh_token or might not!
            # If they don't return one, we keep using the old one.
            # If they DO return a new one, we MUST store it (old one might be invalidated).
            session.set_tokens(
                access_token=token_data["access_token"],
                refresh_token=token_data.get(
                    "refresh_token", session.refresh_token
                ),  # Use old refresh token if not provided
                expires_in=token_data.get("expires_in", 3600),
            )

            # Persist session changes to database for future requests
            await session_store.update_session(
                session.session_id,
                access_token=session.access_token,
                refresh_token=session.refresh_token,
                token_expires_at=session.token_expires_at,
            )

            return cast(str, token_data["access_token"])

        except TokenRefreshException as e:
            # Hey future me - this is the INVALID REFRESH TOKEN case!
            # The refresh token is dead (user revoked access, token expired, etc.)
            # User MUST re-authenticate manually - no way to auto-recover from this.
            raise HTTPException(
                status_code=401,
                detail=f"Refresh token invalid. {e.message}",
            ) from e

        except Exception as e:
            # Other errors (network, unexpected) - also require re-auth to be safe
            raise HTTPException(
                status_code=401,
                detail=f"Failed to refresh token. Please re-authenticate with Spotify: {str(e)}",
            ) from e

    # At this point we know session.access_token is not None (checked above)
    assert session.access_token is not None  # nosec B101
    return session.access_token


# Hey future me - this is THE NEW SHARED TOKEN dependency for all Spotify API endpoints!
# Instead of per-browser session tokens, this uses the SINGLE SHARED token from DatabaseTokenManager.
# This solves the "can't use SoulSpot from other PCs on the network" issue because:
# 1) User authenticates ONCE on any device
# 2) Token is stored server-side in the database (spotify_tokens table)
# 3) ALL devices/browsers share the same token - no session cookie needed!
# 4) Background workers (WatchlistWorker, etc.) also use this same token
#
# The tradeoff: This is SINGLE-USER architecture. Only one person can be logged into Spotify.
# If someone else authenticates, they'll overwrite the previous token. For home server use, this is
# usually what you want! For multi-user scenarios, stick with get_spotify_token_from_session.
async def get_spotify_token_shared(request: Request) -> str:
    """Get valid Spotify access token from shared DatabaseTokenManager.

    This dependency retrieves the Spotify access token from the server-side
    database, making it accessible from ANY device on the network without
    requiring per-browser sessions.

    Single-user architecture: One token shared by all devices and background workers.

    Args:
        request: FastAPI request (for app.state access)

    Returns:
        Valid Spotify access token

    Raises:
        HTTPException: 401 if no token found or token is invalid
    """
    # Check if DatabaseTokenManager is available
    if not hasattr(request.app.state, "db_token_manager"):
        raise HTTPException(
            status_code=503,
            detail="Token manager not initialized. Server may still be starting.",
        )

    db_token_manager: DatabaseTokenManager = request.app.state.db_token_manager
    access_token = await db_token_manager.get_token_for_background()

    if not access_token:
        # Token doesn't exist or is invalid - user needs to authenticate
        raise HTTPException(
            status_code=401,
            detail="No Spotify connection. Please authenticate with Spotify first.",
        )

    return access_token


# Yo, creates NEW SlskdClient on every request - not cached! Slskd is your Soulseek downloader, this
# client talks to its API. Like SpotifyClient, it's stateless so creating new instances is fine (httpx
# pools connections internally). If slskd server is down, this won't fail until you actually USE the
# client in an endpoint.
# UPDATE: Now gets credentials from DB-first via CredentialsService (with .env fallback)!
async def get_slskd_client(
    credentials_service: CredentialsService = Depends(get_credentials_service),
) -> SlskdClient:
    """Get slskd client instance with DB-first credentials.

    Credentials are loaded from database via CredentialsService with .env fallback.
    This enables runtime credential updates without app restart.
    """
    from soulspot.config.settings import SlskdSettings

    slskd_creds = await credentials_service.get_slskd_credentials()

    # Create SlskdSettings from DB credentials
    slskd_settings = SlskdSettings(
        url=slskd_creds.url,
        username=slskd_creds.username,
        password=slskd_creds.password,
        api_key=slskd_creds.api_key,
    )
    return SlskdClient(slskd_settings)


# Hey future me - this checks if slskd is currently available for downloads!
# Returns True if slskd is running and accepting connections, False otherwise.
# Used by download endpoints to decide whether to put downloads in WAITING or PENDING status.
# This is a QUICK check (10s timeout) - don't use for heavy operations!
async def check_slskd_available(
    slskd_client: SlskdClient = Depends(get_slskd_client),
) -> bool:
    """Check if slskd download manager is available.

    Returns:
        True if slskd is healthy and accepting downloads, False otherwise
    """
    try:
        result = await slskd_client.test_connection()
        return result.get("success", False)
    except Exception as e:
        logger.warning(f"slskd connection check failed: {e}")
        return False


# Hey, MusicBrainz is the metadata enrichment source - gets artist/album/track info from their public
# database. Not cached, new client per request. MusicBrainz has RATE LIMITS (1 req/sec for anonymous,
# higher if you set contact info in settings.musicbrainz.contact). If you hammer it too fast, you'll
# get 503 errors! The client should handle rate limiting internally but watch out for that.
def get_musicbrainz_client(
    settings: Settings = Depends(get_settings),
) -> MusicBrainzClient:
    """Get MusicBrainz client instance."""
    return MusicBrainzClient(settings.musicbrainz)


# Listen up, Last.fm is OPTIONAL! Returns None if API key isn't configured. This is different from other
# clients - endpoints MUST check for None before using! Last.fm provides scrobble data, play counts, tags
# etc for metadata enrichment. If you call methods on None you'll get AttributeError. The is_configured()
# check probably verifies API key exists - check LastfmSettings if you're debugging why this returns None.
def get_lastfm_client(
    settings: Settings = Depends(get_settings),
) -> LastfmClient | None:
    """Get Last.fm client instance if configured, None otherwise."""
    if not settings.lastfm.is_configured():
        return None
    return LastfmClient(settings.lastfm)


# Yo, TokenManager handles OAuth token operations - exchange, refresh, validation. It wraps SpotifyClient
# for token-specific logic. Created new per request. I think this might be redundant with the token
# management already in get_spotify_token_from_session? Check if this is actually used - might be legacy.
def get_token_manager(
    spotify_client: SpotifyClient = Depends(get_spotify_client),
) -> TokenManager:
    """Get token manager instance."""
    return TokenManager(spotify_client)


# Hey future me, this is the Repository Pattern in action! ArtistRepository abstracts all artist DB access.
# Created new per request with the DB session injected. The session is tied to the request lifecycle (auto
# cleanup/rollback). Use this dependency in endpoints that need to read/write artists. DON'T bypass the
# repository and query artists directly - that breaks the abstraction and makes code harder to test!
def get_artist_repository(
    session: AsyncSession = Depends(get_db_session),
) -> ArtistRepository:
    """Get artist repository instance."""
    return ArtistRepository(session)


# Yo, album data access layer. Same pattern as ArtistRepository - wraps all album DB queries. New instance
# per request with request-scoped session. Albums have complex relationships (artists, tracks, metadata)
# so the repository handles all that JOIN complexity. Use this instead of raw SQLAlchemy queries!
def get_album_repository(
    session: AsyncSession = Depends(get_db_session),
) -> AlbumRepository:
    """Get album repository instance."""
    return AlbumRepository(session)


# Hey, manages playlist storage and retrieval. Playlists link to tracks through a many-to-many relationship
# (playlist_tracks join table probably). Repository handles adding/removing tracks from playlists, ordering,
# etc. Standard repository pattern - use this for all playlist DB operations!
def get_playlist_repository(
    session: AsyncSession = Depends(get_db_session),
) -> PlaylistRepository:
    """Get playlist repository instance."""
    return PlaylistRepository(session)


# Listen, THE most important repository - tracks are the core domain entity! Handles track metadata, file
# paths, download status, relationships to artists/albums. Queries here can be SLOW if you have thousands
# of tracks - consider adding indexes if track listing endpoints lag. Repository pattern as usual.
def get_track_repository(
    session: AsyncSession = Depends(get_db_session),
) -> TrackRepository:
    """Get track repository instance."""
    return TrackRepository(session)


# Yo, tracks download operations and their state (queued, in-progress, completed, failed). This is separate
# from TrackRepository because downloads are transient operations, not permanent track data. Repository
# queries are used by download workers to find pending downloads. High-traffic table!
def get_download_repository(
    session: AsyncSession = Depends(get_db_session),
) -> DownloadRepository:
    """Get download repository instance."""
    return DownloadRepository(session)


# Hey future me - SpotifyBrowseRepository handles synced Spotify data (followed artists, albums, tracks).
# This is SEPARATE from the local library! Use this for dashboard stats that show Spotify data.
def get_spotify_browse_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SpotifyBrowseRepository:
    """Get Spotify browse repository instance for Spotify synced data."""
    return SpotifyBrowseRepository(session)


# Hey future me, this is a USE CASE - application layer orchestration! It coordinates SpotifyPlugin
# (NOT SpotifyClient anymore!) and multiple repositories to import a playlist from Spotify into our DB.
# Use cases encapsulate business logic that spans multiple repositories/services. Created fresh per
# request with all dependencies injected. SpotifyPlugin handles token management internally - no more
# passing access_token around! This is Clean Architecture - endpoint just calls use_case.execute()!
def get_import_playlist_use_case(
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
    track_repository: TrackRepository = Depends(get_track_repository),
    artist_repository: ArtistRepository = Depends(get_artist_repository),
    album_repository: AlbumRepository = Depends(get_album_repository),
) -> ImportSpotifyPlaylistUseCase:
    """Get import playlist use case instance."""
    return ImportSpotifyPlaylistUseCase(
        spotify_plugin=spotify_plugin,
        playlist_repository=playlist_repository,
        track_repository=track_repository,
        artist_repository=artist_repository,
        album_repository=album_repository,
    )


# Listen, this use case searches Soulseek for a track and initiates download! It's the bridge between
# "I want this track" and "download is queued in slskd". Coordinates SlskdClient (Soulseek API) with
# track/download repositories. Complex logic around search result ranking, file quality selection, etc
# lives in this use case. Standard dependency injection pattern.
def get_search_and_download_use_case(
    slskd_client: SlskdClient = Depends(get_slskd_client),
    track_repository: TrackRepository = Depends(get_track_repository),
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> SearchAndDownloadTrackUseCase:
    """Get search and download use case instance."""
    return SearchAndDownloadTrackUseCase(
        slskd_client=slskd_client,
        track_repository=track_repository,
        download_repository=download_repository,
    )


# Yo, fetches rich metadata from MusicBrainz and stores it in our DB! Gets album art, genres, release
# dates, artist bios, etc. This is separate from the multi-source enrichment use case (which merges
# Spotify/Last.fm/MusicBrainz). Probably legacy - check if this is still used or if multi-source version
# replaced it. MusicBrainz-only enrichment is simpler but less comprehensive.
def get_enrich_metadata_use_case(
    musicbrainz_client: MusicBrainzClient = Depends(get_musicbrainz_client),
    track_repository: TrackRepository = Depends(get_track_repository),
    artist_repository: ArtistRepository = Depends(get_artist_repository),
    album_repository: AlbumRepository = Depends(get_album_repository),
) -> EnrichMetadataUseCase:
    """Get enrich metadata use case instance."""
    return EnrichMetadataUseCase(
        musicbrainz_client=musicbrainz_client,
        track_repository=track_repository,
        artist_repository=artist_repository,
        album_repository=album_repository,
    )


# Hey future me, JobQueue is a SINGLETON stored in app.state! It's created at startup (check main.py or
# app initialization) and lives for the app lifetime. This is different from repositories which are
# request-scoped. If job_queue isn't in app.state, app didn't start properly - probably a startup error.
# 503 Service Unavailable is correct HTTP code for "app not ready yet". The cast() is needed because
# app.state is untyped (can hold anything). JobQueue manages background work queue for downloads/imports.
def get_job_queue(request: Request) -> JobQueue:
    """Get job queue instance from app state.

    Args:
        request: FastAPI request

    Returns:
        JobQueue instance

    Raises:
        HTTPException: If job queue not initialized
    """
    if not hasattr(request.app.state, "job_queue"):
        raise HTTPException(
            status_code=503,
            detail="Job queue not initialized",
        )
    return cast(JobQueue, request.app.state.job_queue)


# Listen up, DownloadWorker is also a singleton in app.state! It's the background worker that processes
# download jobs from the queue. Probably runs in a separate asyncio task continuously polling for work.
# Like JobQueue, this lives for the whole app lifetime and is shared across all requests. If this fails,
# downloads won't process! 503 is appropriate - app is partially broken. Check startup logs if this error
# appears. The worker coordinates with slskd to actually download files.
def get_download_worker(request: Request) -> DownloadWorker:
    """Get download worker instance from app state.

    Args:
        request: FastAPI request

    Returns:
        DownloadWorker instance

    Raises:
        HTTPException: If download worker not initialized
    """
    if not hasattr(request.app.state, "download_worker"):
        raise HTTPException(
            status_code=503,
            detail="Download worker not initialized",
        )
    return cast(DownloadWorker, request.app.state.download_worker)


def get_queue_playlist_downloads_use_case(
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
    track_repository: TrackRepository = Depends(get_track_repository),
    job_queue: JobQueue = Depends(get_job_queue),
) -> QueuePlaylistDownloadsUseCase:
    """Get queue playlist downloads use case.

    Args:
        playlist_repository: Playlist repository
        track_repository: Track repository
        job_queue: Job queue

    Returns:
        QueuePlaylistDownloadsUseCase instance
    """
    return QueuePlaylistDownloadsUseCase(
        playlist_repository=playlist_repository,
        track_repository=track_repository,
        job_queue=job_queue,
    )


# Hey future me - this creates SpotifySyncService for auto-syncing Spotify data!
# REFACTORED to use SpotifyPlugin (Dec 2025)!
# Used by the /spotify/* UI routes to auto-sync on page load and fetch data from DB.
# Requires both DB session and SpotifyPlugin for API calls + persistence.
# ImageService wird mitgegeben für Bilder-Downloads!
async def get_spotify_sync_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator:
    """Get Spotify sync service for auto-sync and browse.

    Hey future me - refactored to use SpotifyPlugin (Dec 2025)!
    No more raw SpotifyClient - plugin handles auth and returns DTOs.
    
    ImageService wird IMMER mitgegeben für Bilder-Downloads!
    Die download_*_image() Methoden brauchen keine Session -
    sie geben nur den Pfad zurück, der Caller aktualisiert die DB.

    Args:
        request: FastAPI request for app state access
        session: Database session
        settings: Application settings

    Yields:
        SpotifySyncService instance with ImageService
    """
    from soulspot.application.services.images import ImageService
    from soulspot.application.services.spotify_sync_service import SpotifySyncService
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

    # Create SpotifyPlugin for the sync service
    spotify_client = SpotifyClient(settings.spotify)
    db_token_manager: DatabaseTokenManager = request.app.state.db_token_manager

    # Get access token from token manager
    access_token = await db_token_manager.get_token_for_background()
    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with Spotify. Please connect your account first.",
        )

    spotify_plugin = SpotifyPlugin(
        client=spotify_client,
        access_token=access_token,
    )

    # Hey future me - ImageService OHNE Session für Sync-Services!
    # download_*_image() macht nur: HTTP → WebP → Datei → Pfad zurück
    # Der Sync-Service aktualisiert selbst die DB mit dem Pfad.
    # image_path: Docker: /config/images, Local: ./images
    image_service = ImageService(
        cache_base_path=str(settings.storage.image_path),
        local_serve_prefix="/images/local",
    )

    yield SpotifySyncService(
        session=session,
        spotify_plugin=spotify_plugin,
        image_service=image_service,
    )


# Hey future me - this creates LibraryScannerService for scanning local music files!
# Used by /api/library/scan endpoints to start/check scans.
# The service itself handles file discovery, metadata extraction, fuzzy matching.
async def get_library_scanner_service(
    _request: Request,  # noqa: ARG001
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator:
    """Get library scanner service for local file imports.

    Args:
        request: FastAPI request (for settings access)
        session: Database session

    Yields:
        LibraryScannerService instance
    """
    from soulspot.application.services.library_scanner_service import (
        LibraryScannerService,
    )

    settings = get_settings()
    yield LibraryScannerService(session=session, settings=settings)


# Hey future me - LibraryViewService liefert ViewModels für Templates!
# Das ist der NEUE Service nach Clean Architecture (Phase 1 Refactoring).
# Routes rufen diesen Service auf und bekommen fertige ViewModels zurück.
# Die Route muss NICHTS über Models wissen (z.B. ob es "title" oder "name" heißt)!
#
# Optionaler SpotifySyncService für Sync-on-demand:
# - Wenn spotify_sync vorhanden: Auto-sync tracks on page load
# - Wenn nicht vorhanden: Zeigt nur cached Daten (graceful degradation)
async def get_library_view_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator:
    """Get Library View Service for template ViewModels.
    
    Hey future me - das ist Phase 1 des Service Separation Plans!
    ViewModels wurden aus SpotifySyncService extrahiert.
    
    Dieser Service:
    1. Holt Daten aus DB via Repositories
    2. Triggert Sync-on-demand (optional, wenn SpotifyPlugin auth hat)
    3. Konvertiert Models zu ViewModels
    4. Gibt ViewModels an Routes zurück
    
    Routes wissen NICHTS über Models - nur ViewModels!

    Args:
        request: FastAPI request for app state access
        session: Database session
        settings: Application settings

    Yields:
        LibraryViewService instance
    """
    from soulspot.application.services.images import ImageService
    from soulspot.application.services.library_view_service import LibraryViewService
    from soulspot.application.services.spotify_sync_service import SpotifySyncService
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin
    
    # Try to create SpotifySyncService for sync-on-demand (optional)
    spotify_sync: SpotifySyncService | None = None
    
    try:
        # Get token for SpotifyPlugin (may not be authenticated)
        db_token_manager: DatabaseTokenManager = request.app.state.db_token_manager
        access_token = await db_token_manager.get_token_for_background()
        
        if access_token:
            # User is authenticated - create sync service for sync-on-demand
            spotify_client = SpotifyClient(settings.spotify)
            spotify_plugin = SpotifyPlugin(
                client=spotify_client,
                access_token=access_token,
            )
            
            # Hey future me - ImageService OHNE Session für Sync-Services!
            # image_path: Docker: /config/images, Local: ./images
            image_service = ImageService(
                cache_base_path=str(settings.storage.image_path),
                local_serve_prefix="/images/local",
            )
            
            spotify_sync = SpotifySyncService(
                session=session,
                spotify_plugin=spotify_plugin,
                image_service=image_service,
            )
    except Exception as e:
        # No auth or error - graceful degradation (show cached data)
        logger.debug(f"No Spotify auth for LibraryViewService: {e}")
    
    yield LibraryViewService(
        session=session,
        spotify_sync=spotify_sync,
    )


# Hey future me - DeezerClient is stateless and doesn't need OAuth!
# Perfect for browse/discovery features when user isn't logged into Spotify.
# Creates a new client per request (cheap - just httpx setup).
def get_deezer_client() -> DeezerClient:
    """Get Deezer client instance for no-auth music discovery.

    Deezer API is perfect for:
    - New releases (get_browse_new_releases, get_editorial_releases)
    - Charts (get_chart_albums, get_chart_tracks)
    - Genre browsing (get_genres, get_genre_artists)

    No authentication required - works for all users!

    Returns:
        DeezerClient instance
    """
    return DeezerClient()


# Hey future me - DeezerPlugin wraps DeezerClient and converts to DTOs!
# Like SpotifyPlugin but simpler - no OAuth needed for most operations.
# Use this for browse/discovery features without auth requirements.
def get_deezer_plugin() -> "DeezerPlugin":
    """Get Deezer plugin instance for no-auth music discovery.

    The plugin wraps DeezerClient and provides:
    - get_browse_new_releases() - Combined editorial + charts
    - get_editorial_releases() - Curated picks
    - get_chart_albums() - Top charting albums
    - get_genres() - All genre categories

    All methods work without authentication!

    Returns:
        DeezerPlugin instance
    """
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

    return DeezerPlugin()


# Hey future me - DeezerSyncService synct Deezer-Daten zur DB!
# Das ist Phase 2 des Service Separation Plans.
# KEINE OAuth nötig für Charts, New Releases, Artist Albums!
async def get_deezer_sync_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator:
    """Get Deezer sync service for syncing Deezer data to database.
    
    Hey future me - das ist der DEEZER Sync Service nach Clean Architecture!
    Braucht KEINE OAuth für die meisten Operationen!
    
    Features:
    - sync_charts() - Top Tracks/Albums/Artists zu DB
    - sync_new_releases() - Neuerscheinungen zu DB
    - sync_artist_albums() - Artist Discographie (Fallback für Spotify!)
    
    ImageService wird IMMER mitgegeben für Bilder-Downloads!
    Die download_*_image() Methoden brauchen keine Session -
    sie geben nur den Pfad zurück, der Caller aktualisiert die DB.
    
    Args:
        session: Database session
        settings: App settings for ImageService

    Yields:
        DeezerSyncService instance with ImageService
    """
    from soulspot.application.services.deezer_sync_service import DeezerSyncService
    from soulspot.application.services.images import ImageService
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
    
    deezer_plugin = DeezerPlugin()
    
    # Hey future me - ImageService OHNE Session für Sync-Services!
    # download_*_image() macht nur: HTTP → WebP → Datei → Pfad zurück
    # Der Sync-Service aktualisiert selbst die DB mit dem Pfad.
    # image_path: Docker: /config/images, Local: ./images
    image_service = ImageService(
        cache_base_path=str(settings.storage.image_path),
        local_serve_prefix="/images/local",
    )
    
    yield DeezerSyncService(
        session=session,
        deezer_plugin=deezer_plugin,
        image_service=image_service,
    )


# Hey future me - ImageService ist der ZENTRALE Bild-Service!
# Handles: URL resolution, download, WebP conversion, cache management.
# Sync methods für Templates, async methods für Services.
# KEINE Provider-Logik - Plugins liefern die URLs, ImageService verarbeitet sie.
def get_image_service(
    settings: Settings = Depends(get_settings),
) -> "ImageService":
    """Get ImageService for all image operations.
    
    Hey future me - ZENTRALER Image Service nach Clean Architecture!
    
    Features:
    - get_display_url() - SYNC für Templates (local > CDN > placeholder)
    - get_best_image() - SYNC Multi-Provider beste verfügbare
    - download_and_cache() - ASYNC Download + WebP + Cache
    - validate_image() - ASYNC HEAD-Request CDN-Validität
    - optimize_cache() - ASYNC Cache-Cleanup
    
    WICHTIG: Für async Methoden (download, get_image) session separat übergeben!
    Sync methods (get_display_url, get_placeholder) brauchen keine Session.
    
    Returns:
        ImageService instance
    
    Example:
        # In Template (sync method):
        image_service.get_display_url(source_url, local_path, "artist")
        
        # In Route (async method):
        await image_service.download_and_cache(url, "album", entity_id)
    """
    from soulspot.application.services.images import ImageService
    
    # Hey future me - image_path ist der konfigurierte Bild-Cache-Pfad!
    # Docker: /config/images (via STORAGE__IMAGE_PATH)
    # Local dev: ./images
    return ImageService(
        cache_base_path=str(settings.storage.image_path),
        local_serve_prefix="/images/local",
    )


# Hey future me - ImageService MIT Session für async Methoden!
# Nutze diese Dependency wenn du get_image() oder download_and_cache() brauchst.
# Für reine URL-Resolution (get_display_url) reicht get_image_service().
async def get_image_service_with_session(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> "ImageService":
    """Get ImageService WITH database session for async operations.
    
    Hey future me - nutze diese Dependency für async Methoden!
    
    Async methods that need session:
    - get_image() - Loads entity from DB
    - download_and_cache() - Updates entity image_path in DB
    - _update_entity_image_path() - Internal DB update
    
    Args:
        session: Database session for entity operations
        settings: App settings for cache path
        
    Returns:
        ImageService instance with session
    """
    from soulspot.application.services.images import ImageService
    
    # Hey future me - image_path ist der konfigurierte Bild-Cache-Pfad!
    # Docker: /config/images (via STORAGE__IMAGE_PATH)
    # Local dev: ./images
    return ImageService(
        session=session,
        cache_base_path=str(settings.storage.image_path),
        local_serve_prefix="/images/local",
    )


# Hey future me - ProviderSyncOrchestrator ist der MULTI-PROVIDER Service!
# Das ist Phase 3 des Service Separation Plans.
# Zentralisiert Provider-Fallback-Logik (Spotify → Deezer).
async def get_provider_sync_orchestrator(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator:
    """Get provider sync orchestrator for multi-provider operations.
    
    Hey future me - das ist der ORCHESTRATOR für Multi-Provider Sync!
    
    Features:
    - sync_artist_albums() - Spotify first, Deezer fallback
    - sync_new_releases() - Deezer first (NO AUTH!), then Spotify
    - sync_artist_top_tracks() - Spotify first, Deezer fallback
    - sync_related_artists() - Discovery feature
    - sync_charts() - Deezer only (Spotify has no public charts API)
    
    ImageService wird für BEIDE Sync-Services mitgegeben!
    
    Args:
        request: FastAPI request (for token access)
        session: Database session

    Yields:
        ProviderSyncOrchestrator instance
    """
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.application.services.deezer_sync_service import DeezerSyncService
    from soulspot.application.services.images import ImageService
    from soulspot.application.services.provider_sync_orchestrator import (
        ProviderSyncOrchestrator,
    )
    from soulspot.application.services.spotify_sync_service import SpotifySyncService
    from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

    settings = get_settings()
    
    # Hey future me - ImageService OHNE Session für Sync-Services!
    # image_path: Docker: /config/images, Local: ./images
    image_service = ImageService(
        cache_base_path=str(settings.storage.image_path),
        local_serve_prefix="/images/local",
    )
    
    # Deezer is ALWAYS available (NO AUTH NEEDED!)
    deezer_plugin = DeezerPlugin()
    deezer_sync = DeezerSyncService(
        session=session,
        deezer_plugin=deezer_plugin,
        image_service=image_service,
    )
    
    # Spotify is OPTIONAL (needs OAuth)
    spotify_sync: SpotifySyncService | None = None
    try:
        db_token_manager: DatabaseTokenManager = request.app.state.db_token_manager
        access_token = await db_token_manager.get_token_for_background()
        
        if access_token:
            spotify_client = SpotifyClient(settings.spotify)
            spotify_plugin = SpotifyPlugin(
                client=spotify_client,
                access_token=access_token,
            )
            spotify_sync = SpotifySyncService(
                session=session,
                spotify_plugin=spotify_plugin,
                image_service=image_service,
            )
    except Exception as e:
        logger.debug(f"No Spotify auth for ProviderSyncOrchestrator: {e}")
    
    settings_service = AppSettingsService(session)
    
    yield ProviderSyncOrchestrator(
        session=session,
        spotify_sync=spotify_sync,
        deezer_sync=deezer_sync,
        settings_service=settings_service,
    )
