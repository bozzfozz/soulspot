"""Dependency injection for API endpoints."""

from collections.abc import AsyncGenerator

from fastapi import Depends, Request
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
from soulspot.config import Settings, get_settings
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

# Global session store instance
# In production, this should be stored in app.state or use Redis
_session_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    """Get or create session store singleton.

    Returns:
        Session store instance
    """
    global _session_store
    if _session_store is None:
        _session_store = SessionStore(session_timeout_seconds=3600)  # 1 hour timeout
    return _session_store


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Get database session from app state."""
    db: Database = request.app.state.db
    async for session in db.get_session():
        yield session


def get_spotify_client(settings: Settings = Depends(get_settings)) -> SpotifyClient:
    """Get Spotify client instance."""
    return SpotifyClient(settings.spotify)


def get_slskd_client(settings: Settings = Depends(get_settings)) -> SlskdClient:
    """Get slskd client instance."""
    return SlskdClient(settings.slskd)


def get_musicbrainz_client(
    settings: Settings = Depends(get_settings),
) -> MusicBrainzClient:
    """Get MusicBrainz client instance."""
    return MusicBrainzClient(settings.musicbrainz)


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
