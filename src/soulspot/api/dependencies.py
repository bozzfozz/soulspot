"""Dependency injection for API endpoints."""

from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import cast

from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.services.session_store import SessionStore
from soulspot.application.services.token_manager import TokenManager
from soulspot.application.use_cases.enrich_metadata import EnrichMetadataUseCase
from soulspot.application.use_cases.import_spotify_playlist import (
    ImportSpotifyPlaylistUseCase,
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


# Listen up future me, @lru_cache makes this a SINGLETON! First call creates SessionStore,
# subsequent calls return THE SAME INSTANCE. This is thread-safe but NOT multiprocess-safe
# (each gunicorn worker gets its own singleton). The 3600s timeout means sessions expire after
# 1 hour - adjust if users complain about getting logged out. If you restart the server, ALL
# sessions are lost because SessionStore is in-memory. For production, move to Redis!
@lru_cache
def get_session_store() -> SessionStore:
    """Get or create session store singleton (thread-safe).

    Returns:
        Session store instance
    """
    return SessionStore(session_timeout_seconds=3600)  # 1 hour timeout


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


async def get_spotify_token_from_session(
    session_id: str | None = Cookie(None),
    session_store: SessionStore = Depends(get_session_store),
    spotify_client: SpotifyClient = Depends(get_spotify_client),
) -> str:
    """Get valid Spotify access token from session with automatic refresh.

    This dependency automatically retrieves the Spotify access token from the
    user's session. If the token is expired, it will automatically refresh it
    using the refresh token.

    Args:
        session_id: Session ID from cookie
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

    session = session_store.get_session(session_id)
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

            return cast(str, token_data["access_token"])
        except Exception as e:
            raise HTTPException(
                status_code=401,
                detail=f"Failed to refresh token. Please re-authenticate with Spotify: {str(e)}",
            ) from e

    # At this point we know session.access_token is not None (checked above)
    assert session.access_token is not None  # nosec B101
    return session.access_token


def get_slskd_client(settings: Settings = Depends(get_settings)) -> SlskdClient:
    """Get slskd client instance."""
    return SlskdClient(settings.slskd)


def get_musicbrainz_client(
    settings: Settings = Depends(get_settings),
) -> MusicBrainzClient:
    """Get MusicBrainz client instance."""
    return MusicBrainzClient(settings.musicbrainz)


def get_lastfm_client(
    settings: Settings = Depends(get_settings),
) -> LastfmClient | None:
    """Get Last.fm client instance if configured, None otherwise."""
    if not settings.lastfm.is_configured():
        return None
    return LastfmClient(settings.lastfm)


def get_token_manager(
    spotify_client: SpotifyClient = Depends(get_spotify_client),
) -> TokenManager:
    """Get token manager instance."""
    return TokenManager(spotify_client)


def get_artist_repository(
    session: AsyncSession = Depends(get_db_session),
) -> ArtistRepository:
    """Get artist repository instance."""
    return ArtistRepository(session)


def get_album_repository(
    session: AsyncSession = Depends(get_db_session),
) -> AlbumRepository:
    """Get album repository instance."""
    return AlbumRepository(session)


def get_playlist_repository(
    session: AsyncSession = Depends(get_db_session),
) -> PlaylistRepository:
    """Get playlist repository instance."""
    return PlaylistRepository(session)


def get_track_repository(
    session: AsyncSession = Depends(get_db_session),
) -> TrackRepository:
    """Get track repository instance."""
    return TrackRepository(session)


def get_download_repository(
    session: AsyncSession = Depends(get_db_session),
) -> DownloadRepository:
    """Get download repository instance."""
    return DownloadRepository(session)


def get_import_playlist_use_case(
    spotify_client: SpotifyClient = Depends(get_spotify_client),
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
    track_repository: TrackRepository = Depends(get_track_repository),
    artist_repository: ArtistRepository = Depends(get_artist_repository),
) -> ImportSpotifyPlaylistUseCase:
    """Get import playlist use case instance."""
    return ImportSpotifyPlaylistUseCase(
        spotify_client=spotify_client,
        playlist_repository=playlist_repository,
        track_repository=track_repository,
        artist_repository=artist_repository,
    )


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
