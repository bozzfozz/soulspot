"""Dependency injection for API endpoints."""

from collections.abc import AsyncGenerator
from typing import cast

from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.services.session_store import (
    DatabaseSessionStore,
)
from soulspot.application.services.token_manager import TokenManager
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
    TrackRepository,
)


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


# Hey, this is a FastAPI dependency - extracts DB from app.state and yields a session. The "async
# for" syntax is weird but REQUIRED because db.get_session() is an async generator. FastAPI handles
# cleanup automatically (session.close(), rollback on error). Use this in endpoint params like:
# "session: AsyncSession = Depends(get_db_session)". Don't call this directly outside FastAPI!
async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Get database session from app state."""
    db: Database = request.app.state.db
    async for session in db.get_session():
        yield session


# Yo, creates NEW SpotifyClient on EVERY request! Not cached/singleton. This is fine because
# SpotifyClient is stateless (httpx client inside is pooled). If SpotifyClient becomes expensive
# to construct, add @lru_cache but watch out - settings changes won't take effect until restart!
def get_spotify_client(settings: Settings = Depends(get_settings)) -> SpotifyClient:
    """Get Spotify client instance."""
    return SpotifyClient(settings.spotify)


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
            # Refresh the token
            token_data = await spotify_client.refresh_token(session.refresh_token)

            # Update session with new token
            session.set_tokens(
                access_token=token_data["access_token"],
                refresh_token=token_data.get(
                    "refresh_token", session.refresh_token
                ),  # Use old refresh token if not provided
                expires_in=token_data.get("expires_in", 3600),
            )

            # Persist session changes to database
            await session_store.update_session(
                session.session_id,
                access_token=session.access_token,
                refresh_token=session.refresh_token,
                token_expires_at=session.token_expires_at,
            )

            return cast(str, token_data["access_token"])
        except Exception as e:
            raise HTTPException(
                status_code=401,
                detail=f"Failed to refresh token. Please re-authenticate with Spotify: {str(e)}",
            ) from e

    # At this point we know session.access_token is not None (checked above)
    assert session.access_token is not None  # nosec B101
    return session.access_token


# Yo, creates NEW SlskdClient on every request - not cached! Slskd is your Soulseek downloader, this
# client talks to its API. Like SpotifyClient, it's stateless so creating new instances is fine (httpx
# pools connections internally). If slskd server is down, this won't fail until you actually USE the
# client in an endpoint. Settings include API key, base URL - check config if requests fail!
def get_slskd_client(settings: Settings = Depends(get_settings)) -> SlskdClient:
    """Get slskd client instance."""
    return SlskdClient(settings.slskd)


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


# Hey future me, this is a USE CASE - application layer orchestration! It coordinates SpotifyClient and
# multiple repositories to import a playlist from Spotify into our DB. Use cases encapsulate business
# logic that spans multiple repositories/services. Created fresh per request with all dependencies injected.
# This is Clean Architecture - endpoint just calls use_case.execute(), the use case does the work!
def get_import_playlist_use_case(
    spotify_client: SpotifyClient = Depends(get_spotify_client),
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
    track_repository: TrackRepository = Depends(get_track_repository),
    artist_repository: ArtistRepository = Depends(get_artist_repository),
    album_repository: AlbumRepository = Depends(get_album_repository),
) -> ImportSpotifyPlaylistUseCase:
    """Get import playlist use case instance."""
    return ImportSpotifyPlaylistUseCase(
        spotify_client=spotify_client,
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
# Used by the /spotify/* UI routes to auto-sync on page load and fetch data from DB.
# Requires both DB session and Spotify client for API calls + persistence.
async def get_spotify_sync_service(
    session: AsyncSession = Depends(get_db_session),
    spotify_client: SpotifyClient = Depends(get_spotify_client),
) -> AsyncGenerator:
    """Get Spotify sync service for auto-sync and browse.

    Args:
        session: Database session
        spotify_client: Spotify client for API calls

    Yields:
        SpotifySyncService instance
    """
    from soulspot.application.services.spotify_sync_service import SpotifySyncService

    yield SpotifySyncService(session=session, spotify_client=spotify_client)


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
