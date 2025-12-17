"""Repository implementations for domain entities."""

from __future__ import annotations

import contextlib
import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, TypeVar, cast

if TYPE_CHECKING:
    from soulspot.application.services.session_store import Session

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soulspot.domain.entities import (
    Album,
    Artist,
    Download,
    DownloadStatus,
    Playlist,
    PlaylistSource,
    Track,
)
from soulspot.domain.exceptions import EntityNotFoundException, ValidationException
from soulspot.domain.ports import (
    IAlbumRepository,
    IArtistRepository,
    IArtistWatchlistRepository,
    IAutomationRuleRepository,
    IDownloadRepository,
    IFilterRuleRepository,
    IPlaylistRepository,
    IQualityUpgradeCandidateRepository,
    ISessionRepository,
    ITrackRepository,
)
from soulspot.domain.value_objects import (
    AlbumId,
    ArtistId,
    DownloadId,
    FilePath,
    PlaylistId,
    SpotifyUri,
    TrackId,
)

from .models import (
    AlbumModel,
    ArtistModel,
    DeezerSessionModel,
    DownloadModel,
    PlaylistModel,
    PlaylistTrackModel,
    SpotifySessionModel,
    SpotifyTokenModel,
    TrackModel,
    ensure_utc_aware,
)

# Type variable for generic repository
T = TypeVar("T")


class ArtistRepository(IArtistRepository):
    """SQLAlchemy implementation of Artist repository."""

    # Hey future me, this is the Repository pattern! Each repo gets its own AsyncSession injected
    # from the DB dependency. The session is NOT committed here - that happens in the route/use case!
    # Repo only stages changes (session.add, model updates). If you call add() then the request
    # fails before commit, the DB stays unchanged (transaction rollback). Don't create your own
    # session inside repos - always use the injected one or you'll get isolation/deadlock issues!
    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    # Yo, add() converts domain entity (Artist) to ORM model (ArtistModel) and stages it. Note we
    # convert IDs and URIs to strings for DB storage (UUIDs/URIs as varchar). The session.add()
    # does NOT hit the database yet - it just marks model for INSERT. Actual DB write happens on
    # session.commit() (handled by dependency). If artist.id already exists in DB, you'll get
    # IntegrityError on commit - this method doesn't check! Use get_by_id first if you care.
    # Hey - genres/tags are serialized as JSON strings for SQLite compatibility!
    # Hey - image_url is stored directly as string (Spotify CDN URL)!
    # Hey - disambiguation is text disambiguation from folder (e.g., "English rock band")!
    # Hey - source tracks LOCAL/SPOTIFY/HYBRID for unified Music Manager view!
    # Hey - deezer_id/tidal_id are multi-service IDs for cross-service deduplication!
    async def add(self, artist: Artist) -> None:
        """Add a new artist."""
        model = ArtistModel(
            id=str(artist.id.value),
            name=artist.name,
            source=artist.source.value,  # Store as string: 'local', 'spotify', 'hybrid'
            spotify_uri=str(artist.spotify_uri) if artist.spotify_uri else None,
            musicbrainz_id=artist.musicbrainz_id,
            artwork_url=artist.artwork_url,
            deezer_id=artist.deezer_id,
            tidal_id=artist.tidal_id,
            disambiguation=artist.disambiguation,
            genres=json.dumps(artist.genres) if artist.genres else None,
            tags=json.dumps(artist.tags) if artist.tags else None,
            created_at=artist.created_at,
            updated_at=artist.updated_at,
        )
        self.session.add(model)

    async def update(self, artist: Artist) -> None:
        """Update an existing artist."""
        stmt = select(ArtistModel).where(ArtistModel.id == str(artist.id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException("Artist", artist.id.value)

        model.name = artist.name
        model.source = artist.source.value  # Update source (local/spotify/hybrid)
        model.spotify_uri = str(artist.spotify_uri) if artist.spotify_uri else None
        model.musicbrainz_id = artist.musicbrainz_id
        model.image_url = artist.image_url
        model.deezer_id = artist.deezer_id
        model.tidal_id = artist.tidal_id
        model.disambiguation = artist.disambiguation
        model.genres = json.dumps(artist.genres) if artist.genres else None
        model.tags = json.dumps(artist.tags) if artist.tags else None
        model.updated_at = artist.updated_at

    async def delete(self, artist_id: ArtistId) -> None:
        """Delete an artist."""
        stmt = delete(ArtistModel).where(ArtistModel.id == str(artist_id.value))
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]  # type: ignore[attr-defined]
            raise EntityNotFoundException("Artist", artist_id.value)

    # Hey future me, this get() is a convenience wrapper that accepts a raw string ID and converts
    # it to ArtistId value object before calling get_by_id(). This is needed because some services
    # (like FollowedArtistsService.sync_artist_albums) work with string IDs directly. Without this,
    # you'd get AttributeError: 'ArtistRepository' has no attribute 'get' - super confusing!
    # The pattern: Service has string → get() wraps to ArtistId → get_by_id() does actual DB lookup.
    async def get(self, artist_id: str) -> Artist | None:
        """Get an artist by string ID (convenience wrapper for get_by_id)."""
        return await self.get_by_id(ArtistId.from_string(artist_id))

    # Listen up, get_by_id fetches from DB and converts ORM model back to domain entity. Returns None
    # if not found (not an error!). The scalar_one_or_none() is important - it returns ONE row or None,
    # raising if multiple rows match (shouldn't happen with unique ID but defensive). We reconstruct
    # the domain Artist object with all its value objects (ArtistId, SpotifyUri). The if/else on
    # spotify_uri handles nullable field - can't call SpotifyUri.from_string(None)!
    # Hey - genres/tags are deserialized from JSON strings!
    # Hey - image_url is stored directly as string (no conversion needed)!
    # Hey - disambiguation is text from folder (e.g., "English rock band")!
    async def get_by_id(self, artist_id: ArtistId) -> Artist | None:
        """Get an artist by ID."""
        stmt = select(ArtistModel).where(ArtistModel.id == str(artist_id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        from soulspot.domain.entities import ArtistSource
        return Artist(
            id=ArtistId.from_string(model.id),
            name=model.name,
            source=ArtistSource(model.source),  # Reconstruct from DB string
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            artwork_url=model.artwork_url,
            disambiguation=model.disambiguation,
            genres=json.loads(model.genres) if model.genres else [],
            tags=json.loads(model.tags) if model.tags else [],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_name(self, name: str) -> Artist | None:
        """Get an artist by name."""
        stmt = select(ArtistModel).where(ArtistModel.name == name)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        from soulspot.domain.entities import ArtistSource
        return Artist(
            id=ArtistId.from_string(model.id),
            name=model.name,
            source=ArtistSource(model.source),
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            artwork_url=model.artwork_url,
            disambiguation=model.disambiguation,
            genres=json.loads(model.genres) if model.genres else [],
            tags=json.loads(model.tags) if model.tags else [],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_musicbrainz_id(self, musicbrainz_id: str) -> Artist | None:
        """Get an artist by MusicBrainz ID."""
        stmt = select(ArtistModel).where(ArtistModel.musicbrainz_id == musicbrainz_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        from soulspot.domain.entities import ArtistSource
        return Artist(
            id=ArtistId.from_string(model.id),
            name=model.name,
            source=ArtistSource(model.source),
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            artwork_url=model.artwork_url,
            disambiguation=model.disambiguation,
            genres=json.loads(model.genres) if model.genres else [],
            tags=json.loads(model.tags) if model.tags else [],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    # Hey future me, this gets artist by Spotify URI (spotify:artist:xxxxx). Used when syncing
    # followed artists from Spotify - we check if artist already exists before creating. The URI
    # is stored as string in DB but we convert to/from SpotifyUri value object. Returns None if
    # not found. This is similar to get_by_musicbrainz_id but for Spotify identifiers.
    async def get_by_spotify_uri(self, spotify_uri: SpotifyUri) -> Artist | None:
        """Get an artist by Spotify URI.

        Args:
            spotify_uri: Spotify URI (e.g., spotify:artist:4RbUYWWjEBb4umwqakOEd3)

        Returns:
            Artist entity if found, None otherwise
        """
        stmt = select(ArtistModel).where(ArtistModel.spotify_uri == str(spotify_uri))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        from soulspot.domain.entities import ArtistSource
        return Artist(
            id=ArtistId.from_string(model.id),
            name=model.name,
            source=ArtistSource(model.source),
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            artwork_url=model.artwork_url,
            disambiguation=model.disambiguation,
            genres=json.loads(model.genres) if model.genres else [],
            tags=json.loads(model.tags) if model.tags else [],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Artist]:
        """List all artists with pagination."""
        stmt = (
            select(ArtistModel).order_by(ArtistModel.name).limit(limit).offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        from soulspot.domain.entities import ArtistSource
        return [
            Artist(
                id=ArtistId.from_string(model.id),
                name=model.name,
                source=ArtistSource(model.source),
                spotify_uri=SpotifyUri.from_string(model.spotify_uri)
                if model.spotify_uri
                else None,
                musicbrainz_id=model.musicbrainz_id,
                artwork_url=model.artwork_url,
                disambiguation=model.disambiguation,
                genres=json.loads(model.genres) if model.genres else [],
                tags=json.loads(model.tags) if model.tags else [],
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    # Hey future me - this counts ALL artists in the DB using SQL COUNT (efficient!).
    # Used for pagination total_count and stats. Returns 0 if no artists exist (not None).
    async def count_all(self) -> int:
        """Count total number of artists in the database.

        Returns:
            Total count of artists
        """
        stmt = select(func.count(ArtistModel.id))
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # =========================================================================
    # ENRICHMENT METHODS
    # =========================================================================
    # Hey future me - these methods are for Spotify enrichment of local library!
    # They find artists that have a local file (file_path in tracks) but no Spotify data yet.
    # This allows enriching local library with Spotify metadata (artwork, genres, etc.)
    # =========================================================================

    async def get_unenriched(self, limit: int = 50) -> list[Artist]:
        """Get artists that have local files but no Spotify enrichment yet.

        Returns artists where:
        - spotify_uri is NULL (not linked to Spotify yet)
        - Artist has at least one track with file_path (local file exists)
        - Artist name is NOT "Various Artists" etc (those can't be enriched)

        Args:
            limit: Maximum number of artists to return (default 50 for batch processing)

        Returns:
            List of Artist entities needing enrichment
        """
        from soulspot.domain.value_objects.album_types import VARIOUS_ARTISTS_PATTERNS

        # Hey - we use EXISTS subquery to only get artists with local files
        # This avoids enriching artists that only exist from Spotify imports
        has_local_tracks = (
            select(TrackModel.id)
            .where(TrackModel.artist_id == ArtistModel.id)
            .where(TrackModel.file_path.isnot(None))
            .exists()
        )

        stmt = (
            select(ArtistModel)
            .where(ArtistModel.spotify_uri.is_(None))  # Not enriched yet
            .where(has_local_tracks)  # Has local files
            .order_by(ArtistModel.name)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        from soulspot.domain.entities import ArtistSource
        # Filter out Various Artists patterns in Python (more flexible than SQL LIKE)
        enrichable = []
        for model in models:
            name_lower = model.name.lower()
            # Skip if name matches Various Artists patterns
            if any(pattern in name_lower for pattern in VARIOUS_ARTISTS_PATTERNS):
                continue
            enrichable.append(
                Artist(
                    id=ArtistId.from_string(model.id),
                    name=model.name,
                    source=ArtistSource(model.source),  # Include source field
                    spotify_uri=None,
                    musicbrainz_id=model.musicbrainz_id,
                    artwork_url=model.artwork_url,
                    disambiguation=model.disambiguation,
                    genres=json.loads(model.genres) if model.genres else [],
                    tags=json.loads(model.tags) if model.tags else [],
                    created_at=model.created_at,
                    updated_at=model.updated_at,
                )
            )

        return enrichable

    async def count_unenriched(self) -> int:
        """Count artists that need enrichment.

        Returns count of artists with local files but no Spotify URI.
        """
        has_local_tracks = (
            select(TrackModel.id)
            .where(TrackModel.artist_id == ArtistModel.id)
            .where(TrackModel.file_path.isnot(None))
            .exists()
        )

        stmt = (
            select(func.count(ArtistModel.id))
            .where(ArtistModel.spotify_uri.is_(None))
            .where(has_local_tracks)
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # Hey future me - this counts artists SYNCED FROM SPOTIFY (have spotify_uri).
    # Used for the Spotify Database Stats in Settings UI to show how many entities
    # were imported from Spotify. Different from count_unenriched which counts local files!
    async def count_with_spotify_uri(self) -> int:
        """Count artists that have a Spotify URI (synced from Spotify).

        Returns:
            Count of artists with spotify_uri IS NOT NULL
        """
        stmt = select(func.count(ArtistModel.id)).where(
            ArtistModel.spotify_uri.isnot(None)
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # =======================================================================
    # UNIFIED MUSIC MANAGER VIEW (LOCAL + SPOTIFY)
    # =======================================================================
    # Hey future me - this is THE CORE of the unified Music Manager!
    # It merges LOCAL library artists (from file scans) with SPOTIFY followed artists.
    # The source field tracks origin: LOCAL, SPOTIFY, or HYBRID (both).
    #
    # Why this matters:
    # - Users want to see ALL their artists in one place
    # - Local files provide actual music ownership
    # - Spotify provides metadata (artwork, genres, popularity)
    # - HYBRID artists get best of both worlds
    #
    # Match criteria (in order of priority):
    # 1. spotify_uri exact match (most reliable)
    # 2. name case-insensitive match (fallback for manual imports)
    #
    # Source determination:
    # - LOCAL only: Artist has files but not in Spotify followed
    # - SPOTIFY only: Followed artist but no local files yet
    # - HYBRID: Artist exists in BOTH local library and Spotify
    # =======================================================================

    async def get_all_artists_unified(
        self, limit: int = 100, offset: int = 0, source_filter: str | None = None
    ) -> list[Artist]:
        """Get unified view of LOCAL + SPOTIFY artists.

        Hey future me - this powers the Music Manager unified artist list!
        Returns artists from soulspot_artists table with source field correctly set.
        Artists with source='spotify' are followed on Spotify but have no local files yet.
        Artists with source='hybrid' exist in both local library and Spotify followed.
        Artists with source='local' are only in local file scans (not followed on Spotify).

        Args:
            limit: Max artists to return (pagination)
            offset: Skip N artists (pagination)
            source_filter: Filter by source ('local', 'spotify', 'hybrid', None=all)

        Returns:
            List of Artist entities with correct source field
        """
        from soulspot.domain.entities import ArtistSource

        stmt = select(ArtistModel).order_by(ArtistModel.name)

        # Apply source filter if provided
        if source_filter:
            stmt = stmt.where(ArtistModel.source == source_filter)

        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            Artist(
                id=ArtistId.from_string(model.id),
                name=model.name,
                source=ArtistSource(model.source),
                spotify_uri=SpotifyUri.from_string(model.spotify_uri)
                if model.spotify_uri
                else None,
                musicbrainz_id=model.musicbrainz_id,
                artwork_url=model.artwork_url,
                disambiguation=model.disambiguation,
                genres=json.loads(model.genres) if model.genres else [],
                tags=json.loads(model.tags) if model.tags else [],
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def count_by_source(self, source: str | None = None) -> int:
        """Count artists by source type.

        Args:
            source: Filter by source ('local', 'spotify', 'hybrid', None=all)

        Returns:
            Count of artists matching source filter
        """
        stmt = select(func.count(ArtistModel.id))
        if source:
            stmt = stmt.where(ArtistModel.source == source)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_missing_artwork(self, limit: int = 50) -> list[Artist]:
        """Get artists that have Spotify URI but missing artwork.

        Hey future me - this is for RE-ENRICHING artists whose artwork download failed!
        Sometimes the initial enrichment links to Spotify but artwork download fails
        (network issues, rate limits, etc.). This method finds those artists so we
        can try downloading their artwork again.

        Returns artists where:
        - spotify_uri is NOT NULL (already enriched)
        - image_url is NULL (artwork missing)

        Args:
            limit: Maximum number of artists to return

        Returns:
            List of Artist entities with missing artwork
        """
        stmt = (
            select(ArtistModel)
            .where(ArtistModel.spotify_uri.isnot(None))  # Has Spotify link
            .where(ArtistModel.artwork_url.is_(None))  # But no artwork
            .order_by(ArtistModel.name)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        from soulspot.domain.entities import ArtistSource
        return [
            Artist(
                id=ArtistId.from_string(model.id),
                name=model.name,
                source=ArtistSource(model.source),  # Include source field
                spotify_uri=SpotifyUri(model.spotify_uri) if model.spotify_uri else None,
                musicbrainz_id=model.musicbrainz_id,
                artwork_url=model.artwork_url,
                disambiguation=model.disambiguation,
                genres=json.loads(model.genres) if model.genres else [],
                tags=json.loads(model.tags) if model.tags else [],
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    # =========================================================================
    # MULTI-SERVICE LOOKUP METHODS
    # =========================================================================
    # Hey future me - these are THE KEY for multi-service deduplication!
    # When syncing from Deezer/Tidal, check if artist already exists via these IDs
    # before creating a new one. Pattern identical to get_by_spotify_uri.
    # =========================================================================

    async def get_by_deezer_id(self, deezer_id: str) -> Artist | None:
        """Get an artist by Deezer ID.

        Used when syncing from Deezer to check if artist already exists.

        Args:
            deezer_id: Deezer artist ID (e.g., '27')

        Returns:
            Artist entity if found, None otherwise
        """
        stmt = select(ArtistModel).where(ArtistModel.deezer_id == deezer_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        from soulspot.domain.entities import ArtistSource
        return Artist(
            id=ArtistId.from_string(model.id),
            name=model.name,
            source=ArtistSource(model.source),
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            artwork_url=model.artwork_url,
            deezer_id=model.deezer_id,
            tidal_id=model.tidal_id,
            disambiguation=model.disambiguation,
            genres=json.loads(model.genres) if model.genres else [],
            tags=json.loads(model.tags) if model.tags else [],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_tidal_id(self, tidal_id: str) -> Artist | None:
        """Get an artist by Tidal ID.

        Used when syncing from Tidal to check if artist already exists.

        Args:
            tidal_id: Tidal artist ID (e.g., '3566')

        Returns:
            Artist entity if found, None otherwise
        """
        stmt = select(ArtistModel).where(ArtistModel.tidal_id == tidal_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        from soulspot.domain.entities import ArtistSource
        return Artist(
            id=ArtistId.from_string(model.id),
            name=model.name,
            source=ArtistSource(model.source),
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            artwork_url=model.artwork_url,
            deezer_id=model.deezer_id,
            tidal_id=model.tidal_id,
            disambiguation=model.disambiguation,
            genres=json.loads(model.genres) if model.genres else [],
            tags=json.loads(model.tags) if model.tags else [],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class AlbumRepository(IAlbumRepository):
    """SQLAlchemy implementation of Album repository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    def _model_to_entity(self, model: AlbumModel) -> Album:
        """Convert AlbumModel to Album entity with ALL fields.
        
        Hey future me - this is the ONE place that maps DB → Entity!
        When you add fields to Album entity, UPDATE THIS FUNCTION!
        """
        return Album(
            id=AlbumId.from_string(model.id),
            title=model.title,
            artist_id=ArtistId.from_string(model.artist_id),
            source=model.source,
            release_year=model.release_year,
            release_date=model.release_date,
            release_date_precision=model.release_date_precision,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            deezer_id=model.deezer_id,
            tidal_id=model.tidal_id,
            artwork_path=FilePath.from_string(model.artwork_path)
            if model.artwork_path
            else None,
            artwork_url=model.artwork_url,
            primary_type=model.primary_type,
            secondary_types=model.secondary_types or [],
            disambiguation=model.disambiguation,
            total_tracks=model.total_tracks,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def add(self, album: Album) -> None:
        """Add a new album."""
        model = AlbumModel(
            id=str(album.id.value),
            title=album.title,
            artist_id=str(album.artist_id.value),
            source=album.source,
            release_year=album.release_year,
            release_date=album.release_date,
            release_date_precision=album.release_date_precision,
            spotify_uri=str(album.spotify_uri.value) if album.spotify_uri else None,
            musicbrainz_id=album.musicbrainz_id,
            deezer_id=album.deezer_id,
            tidal_id=album.tidal_id,
            artwork_path=str(album.artwork_path.value) if album.artwork_path else None,
            artwork_url=album.artwork_url,
            primary_type=album.primary_type,
            secondary_types=album.secondary_types,
            disambiguation=album.disambiguation,
            total_tracks=album.total_tracks,
            created_at=album.created_at,
            updated_at=album.updated_at,
        )
        self.session.add(model)

    async def update(self, album: Album) -> None:
        """Update an existing album."""
        stmt = select(AlbumModel).where(AlbumModel.id == str(album.id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one()

        model.title = album.title
        model.artist_id = str(album.artist_id.value)
        model.source = album.source
        model.release_year = album.release_year
        model.release_date = album.release_date
        model.release_date_precision = album.release_date_precision
        model.spotify_uri = str(album.spotify_uri.value) if album.spotify_uri else None
        model.musicbrainz_id = album.musicbrainz_id
        model.deezer_id = album.deezer_id
        model.tidal_id = album.tidal_id
        model.artwork_path = (
            str(album.artwork_path.value) if album.artwork_path else None
        )
        model.artwork_url = album.artwork_url
        model.primary_type = album.primary_type
        model.secondary_types = album.secondary_types
        model.disambiguation = album.disambiguation
        model.total_tracks = album.total_tracks
        model.updated_at = album.updated_at

        self.session.add(model)

    async def delete(self, album_id: AlbumId) -> None:
        """Delete an album."""
        stmt = delete(AlbumModel).where(AlbumModel.id == str(album_id.value))
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]  # type: ignore[attr-defined]
            raise EntityNotFoundException("Album", album_id.value)

    async def get_by_id(self, album_id: AlbumId) -> Album | None:
        """Get an album by ID."""
        stmt = select(AlbumModel).where(AlbumModel.id == str(album_id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return self._model_to_entity(model)

    async def get_by_artist(self, artist_id: ArtistId) -> list[Album]:
        """Get all albums by an artist."""
        stmt = (
            select(AlbumModel)
            .where(AlbumModel.artist_id == str(artist_id.value))
            .order_by(AlbumModel.release_year)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self._model_to_entity(model) for model in models]

    async def get_by_musicbrainz_id(self, musicbrainz_id: str) -> Album | None:
        """Get an album by MusicBrainz ID."""
        stmt = select(AlbumModel).where(AlbumModel.musicbrainz_id == musicbrainz_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return self._model_to_entity(model)

    # Hey future me, this gets album by Spotify URI! Essential for playlist import to avoid
    # creating duplicate albums. Spotify track data includes album info with URI, so we can
    # check if album already exists before creating. This is the same pattern as artist
    # get_by_spotify_uri - deduplicate by URI, not by name (multiple albums can share names!).
    async def get_by_spotify_uri(self, spotify_uri: SpotifyUri) -> Album | None:
        """Get an album by Spotify URI.

        Args:
            spotify_uri: Spotify URI (e.g., spotify:album:4aawyAB9vmqN3uQ7FjRGTy)

        Returns:
            Album entity if found, None otherwise
        """
        stmt = select(AlbumModel).where(
            AlbumModel.spotify_uri == str(spotify_uri.value)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return self._model_to_entity(model)

    async def get_by_title_and_artist(
        self, title: str, artist_id: ArtistId
    ) -> Album | None:
        """Get an album by title and artist ID.

        Hey future me - CROSS-SERVICE DEDUPLICATION!
        This finds albums by their title+artist combination, regardless of
        which service they came from (Spotify, Deezer, local).
        
        Used to prevent duplicates when same album is found from different
        providers (e.g., Spotify returns "Dark Side of the Moon" and later
        Deezer also returns "Dark Side of the Moon" for same artist).
        
        NOTE: Uses case-insensitive matching via func.lower() to catch
        slight variations like "The Dark Side Of The Moon" vs 
        "The Dark Side of the Moon".

        Args:
            title: Album title (case-insensitive)
            artist_id: Artist ID

        Returns:
            Album entity if found, None otherwise
        """
        from sqlalchemy import func
        
        stmt = select(AlbumModel).where(
            func.lower(AlbumModel.title) == title.lower(),
            AlbumModel.artist_id == str(artist_id.value),
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return self._model_to_entity(model)

    # =========================================================================
    # ENRICHMENT METHODS
    # =========================================================================
    # Hey future me - these methods are for Spotify enrichment of local library!
    # They find albums that have local tracks but no Spotify data yet.
    # =========================================================================

    async def get_unenriched(
        self,
        limit: int = 50,
        include_compilations: bool = True,
    ) -> list[Album]:
        """Get albums that have local files but no Spotify enrichment yet.

        Returns albums where:
        - spotify_uri is NULL (not linked to Spotify yet)
        - Album has at least one track with file_path (local file exists)

        Args:
            limit: Maximum number of albums to return (default 50 for batch processing)
            include_compilations: If False, exclude compilation albums

        Returns:
            List of Album entities needing enrichment
        """
        # Hey - we use EXISTS subquery to only get albums with local files
        has_local_tracks = (
            select(TrackModel.id)
            .where(TrackModel.album_id == AlbumModel.id)
            .where(TrackModel.file_path.isnot(None))
            .exists()
        )

        stmt = (
            select(AlbumModel)
            .where(AlbumModel.spotify_uri.is_(None))  # Not enriched yet
            .where(has_local_tracks)  # Has local files
            .order_by(AlbumModel.title)
            .limit(limit)
        )

        # Filter out compilations if requested
        if not include_compilations:
            # Hey - secondary_types is JSON array, we check if 'compilation' is NOT in it
            # SQLite JSON functions: json_each() to unnest, or check string contains
            # Simpler approach: exclude where secondary_types contains "compilation"
            stmt = stmt.where(~AlbumModel.secondary_types.contains('"compilation"'))

        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [self._model_to_entity(model) for model in models]

    async def count_unenriched(self, include_compilations: bool = True) -> int:
        """Count albums that need enrichment.

        Returns count of albums with local files but no Spotify URI.
        """
        has_local_tracks = (
            select(TrackModel.id)
            .where(TrackModel.album_id == AlbumModel.id)
            .where(TrackModel.file_path.isnot(None))
            .exists()
        )

        stmt = (
            select(func.count(AlbumModel.id))
            .where(AlbumModel.spotify_uri.is_(None))
            .where(has_local_tracks)
        )

        if not include_compilations:
            stmt = stmt.where(~AlbumModel.secondary_types.contains('"compilation"'))

        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # Hey future me - this counts albums SYNCED FROM SPOTIFY (have spotify_uri).
    # Used for the Spotify Database Stats in Settings UI.
    async def count_with_spotify_uri(self) -> int:
        """Count albums that have a Spotify URI (synced from Spotify).

        Returns:
            Count of albums with spotify_uri IS NOT NULL
        """
        stmt = select(func.count(AlbumModel.id)).where(
            AlbumModel.spotify_uri.isnot(None)
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # =========================================================================
    # MULTI-SERVICE LOOKUP METHODS
    # =========================================================================

    async def get_by_deezer_id(self, deezer_id: str) -> Album | None:
        """Get an album by Deezer ID.

        Args:
            deezer_id: Deezer album ID

        Returns:
            Album entity if found, None otherwise
        """
        stmt = select(AlbumModel).where(AlbumModel.deezer_id == deezer_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return self._model_to_entity(model)

    async def get_by_tidal_id(self, tidal_id: str) -> Album | None:
        """Get an album by Tidal ID.

        Args:
            tidal_id: Tidal album ID

        Returns:
            Album entity if found, None otherwise
        """
        stmt = select(AlbumModel).where(AlbumModel.tidal_id == tidal_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return self._model_to_entity(model)


class TrackRepository(ITrackRepository):
    """SQLAlchemy implementation of Track repository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    async def add(self, track: Track) -> None:
        """Add a new track."""
        # Hey - extract primary genre from genres list for DB storage!
        # Takes first genre if available, else None. DB stores single genre for filtering.
        # Check both that list exists AND is not empty before accessing [0]
        primary_genre = (
            track.genres[0] if (track.genres and len(track.genres) > 0) else None
        )

        model = TrackModel(
            id=str(track.id.value),
            title=track.title,
            artist_id=str(track.artist_id.value),
            album_id=str(track.album_id.value) if track.album_id else None,
            duration_ms=track.duration_ms,
            track_number=track.track_number,
            disc_number=track.disc_number,
            spotify_uri=str(track.spotify_uri) if track.spotify_uri else None,
            musicbrainz_id=track.musicbrainz_id,
            isrc=track.isrc,
            file_path=str(track.file_path) if track.file_path else None,
            genre=primary_genre,
            created_at=track.created_at,
            updated_at=track.updated_at,
        )
        self.session.add(model)

    async def update(self, track: Track) -> None:
        """Update an existing track."""
        stmt = select(TrackModel).where(TrackModel.id == str(track.id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException("Track", track.id.value)

        # Hey - update genre from entity's genres list (primary genre only)
        # Check both that list exists AND is not empty before accessing [0]
        primary_genre = (
            track.genres[0] if (track.genres and len(track.genres) > 0) else None
        )

        model.title = track.title
        model.artist_id = str(track.artist_id.value)
        model.album_id = str(track.album_id.value) if track.album_id else None
        model.duration_ms = track.duration_ms
        model.track_number = track.track_number
        model.disc_number = track.disc_number
        model.spotify_uri = str(track.spotify_uri) if track.spotify_uri else None
        model.musicbrainz_id = track.musicbrainz_id
        model.isrc = track.isrc
        model.file_path = str(track.file_path) if track.file_path else None
        model.genre = primary_genre
        model.updated_at = track.updated_at

    async def delete(self, track_id: TrackId) -> None:
        """Delete a track."""
        stmt = delete(TrackModel).where(TrackModel.id == str(track_id.value))
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]  # type: ignore[attr-defined]
            raise EntityNotFoundException("Track", track_id.value)

    async def get_by_id(self, track_id: TrackId) -> Track | None:
        """Get a track by ID."""
        stmt = select(TrackModel).where(TrackModel.id == str(track_id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return Track(
            id=TrackId.from_string(model.id),
            title=model.title,
            artist_id=ArtistId.from_string(model.artist_id),
            album_id=AlbumId.from_string(model.album_id) if model.album_id else None,
            duration_ms=model.duration_ms,
            track_number=model.track_number,
            disc_number=model.disc_number,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            isrc=model.isrc,
            file_path=FilePath.from_string(model.file_path)
            if model.file_path
            else None,
            genres=[model.genre]
            if model.genre
            else [],  # Hey - convert single genre back to list!
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_spotify_uri(self, spotify_uri: SpotifyUri) -> Track | None:
        """Get a track by Spotify URI."""
        stmt = select(TrackModel).where(TrackModel.spotify_uri == str(spotify_uri))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return Track(
            id=TrackId.from_string(model.id),
            title=model.title,
            artist_id=ArtistId.from_string(model.artist_id),
            album_id=AlbumId.from_string(model.album_id) if model.album_id else None,
            duration_ms=model.duration_ms,
            track_number=model.track_number,
            disc_number=model.disc_number,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            isrc=model.isrc,
            file_path=FilePath.from_string(model.file_path)
            if model.file_path
            else None,
            genres=[model.genre] if model.genre else [],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_album(self, album_id: AlbumId) -> list[Track]:
        """Get all tracks in an album."""
        stmt = (
            select(TrackModel)
            .where(TrackModel.album_id == str(album_id.value))
            .order_by(TrackModel.disc_number, TrackModel.track_number)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            Track(
                id=TrackId.from_string(model.id),
                title=model.title,
                artist_id=ArtistId.from_string(model.artist_id),
                album_id=AlbumId.from_string(model.album_id)
                if model.album_id
                else None,
                duration_ms=model.duration_ms,
                track_number=model.track_number,
                disc_number=model.disc_number,
                spotify_uri=SpotifyUri.from_string(model.spotify_uri)
                if model.spotify_uri
                else None,
                musicbrainz_id=model.musicbrainz_id,
                isrc=model.isrc,
                file_path=FilePath.from_string(model.file_path)
                if model.file_path
                else None,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def get_by_artist(self, artist_id: ArtistId) -> list[Track]:
        """Get all tracks by an artist."""
        stmt = (
            select(TrackModel)
            .where(TrackModel.artist_id == str(artist_id.value))
            .order_by(TrackModel.title)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            Track(
                id=TrackId.from_string(model.id),
                title=model.title,
                artist_id=ArtistId.from_string(model.artist_id),
                album_id=AlbumId.from_string(model.album_id)
                if model.album_id
                else None,
                duration_ms=model.duration_ms,
                track_number=model.track_number,
                disc_number=model.disc_number,
                spotify_uri=SpotifyUri.from_string(model.spotify_uri)
                if model.spotify_uri
                else None,
                musicbrainz_id=model.musicbrainz_id,
                isrc=model.isrc,
                file_path=FilePath.from_string(model.file_path)
                if model.file_path
                else None,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    # Hey future me - this gets tracks that have NO album association (singles)!
    # Used for displaying "loose" tracks from an artist that aren't part of any album.
    # Perfect for the "artist songs" feature where we sync top tracks/singles from Spotify.
    # The WHERE clause filters for album_id IS NULL to exclude album tracks.
    async def get_singles_by_artist(self, artist_id: ArtistId) -> list[Track]:
        """Get tracks by an artist that are NOT associated with any album (singles).

        Args:
            artist_id: Artist ID to get singles for

        Returns:
            List of Track entities without album association
        """
        stmt = (
            select(TrackModel)
            .where(
                TrackModel.artist_id == str(artist_id.value),
                TrackModel.album_id.is_(None),
            )
            .order_by(TrackModel.title)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            Track(
                id=TrackId.from_string(model.id),
                title=model.title,
                artist_id=ArtistId.from_string(model.artist_id),
                album_id=None,  # Guaranteed to be None from query
                duration_ms=model.duration_ms,
                track_number=model.track_number,
                disc_number=model.disc_number,
                spotify_uri=SpotifyUri.from_string(model.spotify_uri)
                if model.spotify_uri
                else None,
                musicbrainz_id=model.musicbrainz_id,
                isrc=model.isrc,
                file_path=FilePath.from_string(model.file_path)
                if model.file_path
                else None,
                genres=[model.genre] if model.genre else [],
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    # Hey future me - count singles for an artist for pagination/stats.
    async def count_singles_by_artist(self, artist_id: ArtistId) -> int:
        """Count tracks by an artist that are NOT associated with any album.

        Args:
            artist_id: Artist ID to count singles for

        Returns:
            Number of singles (tracks without album)
        """
        stmt = select(func.count(TrackModel.id)).where(
            TrackModel.artist_id == str(artist_id.value),
            TrackModel.album_id.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Track]:
        """List all tracks with pagination and eager loading of relationships."""
        stmt = (
            select(TrackModel)
            .options(
                selectinload(TrackModel.artist),
                selectinload(TrackModel.album),
            )
            .order_by(TrackModel.title)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            Track(
                id=TrackId.from_string(model.id),
                title=model.title,
                artist_id=ArtistId.from_string(model.artist_id),
                album_id=AlbumId.from_string(model.album_id)
                if model.album_id
                else None,
                duration_ms=model.duration_ms,
                track_number=model.track_number,
                disc_number=model.disc_number,
                spotify_uri=SpotifyUri.from_string(model.spotify_uri)
                if model.spotify_uri
                else None,
                musicbrainz_id=model.musicbrainz_id,
                isrc=model.isrc,
                file_path=FilePath.from_string(model.file_path)
                if model.file_path
                else None,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def count_all(self) -> int:
        """Count total number of tracks."""
        stmt = select(func.count(TrackModel.id))
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # Hey future me - this counts tracks SYNCED FROM SPOTIFY (have spotify_uri).
    # Used for the Spotify Database Stats in Settings UI.
    async def count_with_spotify_uri(self) -> int:
        """Count tracks that have a Spotify URI (synced from Spotify).

        Returns:
            Count of tracks with spotify_uri IS NOT NULL
        """
        stmt = select(func.count(TrackModel.id)).where(
            TrackModel.spotify_uri.isnot(None)
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def add_batch(self, tracks: list[Track]) -> None:
        """Add multiple tracks in a single batch operation.

        This is more efficient than calling add() multiple times as it reduces
        the number of round trips to the database.

        Args:
            tracks: List of Track entities to add
        """
        models = [
            TrackModel(
                id=str(track.id.value),
                title=track.title,
                artist_id=str(track.artist_id.value),
                album_id=str(track.album_id.value) if track.album_id else None,
                duration_ms=track.duration_ms,
                track_number=track.track_number,
                disc_number=track.disc_number,
                spotify_uri=str(track.spotify_uri) if track.spotify_uri else None,
                musicbrainz_id=track.musicbrainz_id,
                isrc=track.isrc,
                file_path=str(track.file_path) if track.file_path else None,
                created_at=track.created_at,
                updated_at=track.updated_at,
            )
            for track in tracks
        ]
        self.session.add_all(models)

    async def update_batch(self, tracks: list[Track]) -> None:
        """Update multiple tracks in a single batch operation.

        This is more efficient than calling update() multiple times.
        Note: This loads all tracks into memory first, then updates them.

        Args:
            tracks: List of Track entities to update
        """
        track_ids = [str(track.id.value) for track in tracks]
        stmt = select(TrackModel).where(TrackModel.id.in_(track_ids))
        result = await self.session.execute(stmt)
        models = {model.id: model for model in result.scalars().all()}

        for track in tracks:
            model = models.get(str(track.id.value))
            if model:
                model.title = track.title
                model.artist_id = str(track.artist_id.value)
                model.album_id = str(track.album_id.value) if track.album_id else None
                model.duration_ms = track.duration_ms
                model.track_number = track.track_number
                model.disc_number = track.disc_number
                model.spotify_uri = (
                    str(track.spotify_uri) if track.spotify_uri else None
                )
                model.musicbrainz_id = track.musicbrainz_id
                model.isrc = track.isrc
                model.file_path = str(track.file_path) if track.file_path else None
                model.updated_at = track.updated_at

    # Hey future me - ISRC lookup for auto-import track matching!
    # ISRC (International Standard Recording Code) is a globally unique identifier
    # for recordings. If we have ISRC in ID3 tags, this is the BEST way to match
    # a downloaded file to a track in our DB. Much more reliable than title/artist matching!
    async def get_by_isrc(self, isrc: str) -> Track | None:
        """Get a track by ISRC (International Standard Recording Code).

        ISRC is a globally unique identifier for recordings, making this
        the most reliable way to match downloaded files to tracks.

        Args:
            isrc: ISRC code (e.g., 'USRC11900012')

        Returns:
            Track entity or None if not found
        """
        stmt = select(TrackModel).where(TrackModel.isrc == isrc)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return Track(
            id=TrackId.from_string(model.id),
            title=model.title,
            artist_id=ArtistId.from_string(model.artist_id),
            album_id=AlbumId.from_string(model.album_id) if model.album_id else None,
            duration_ms=model.duration_ms,
            track_number=model.track_number,
            disc_number=model.disc_number,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            isrc=model.isrc,
            file_path=FilePath.from_string(model.file_path)
            if model.file_path
            else None,
            genres=[model.genre] if model.genre else [],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    # Hey future me - CROSS-PROVIDER DEDUPLICATION for top tracks!
    # When we get tracks from Deezer but might already have them from Spotify,
    # this method finds existing tracks by title+artist (case-insensitive).
    # Returns single track (first match) for dedup purposes.
    async def get_by_title_and_artist(
        self, title: str, artist_name: str
    ) -> Track | None:
        """Find a track by title and artist name (case-insensitive).

        Used for cross-provider deduplication when ISRC is not available.
        Returns the first match or None.

        Args:
            title: Track title to search for
            artist_name: Artist name to filter by

        Returns:
            Track entity or None if not found
        """
        stmt = (
            select(TrackModel)
            .join(ArtistModel, TrackModel.artist_id == ArtistModel.id)
            .where(
                func.lower(TrackModel.title) == func.lower(title),
                func.lower(ArtistModel.name) == func.lower(artist_name),
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return Track(
            id=TrackId.from_string(model.id),
            title=model.title,
            artist_id=ArtistId.from_string(model.artist_id),
            album_id=AlbumId.from_string(model.album_id) if model.album_id else None,
            duration_ms=model.duration_ms,
            track_number=model.track_number,
            disc_number=model.disc_number,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            isrc=model.isrc,
            file_path=FilePath.from_string(model.file_path)
            if model.file_path
            else None,
            genres=[model.genre] if model.genre else [],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    # Hey future me - fuzzy title/artist search for fallback matching!
    # When ISRC is not available, we try to match by title and artist name.
    # Uses LIKE queries with case-insensitive matching. Not perfect but better than nothing!
    # Returns list because multiple tracks might match (same song from different albums).
    async def search_by_title_artist(
        self, title: str, artist_name: str | None = None, limit: int = 5
    ) -> list[Track]:
        """Search for tracks by title and optionally artist name.

        Used as fallback when ISRC is not available. Uses case-insensitive
        LIKE matching for fuzzy search.

        Args:
            title: Track title to search for
            artist_name: Optional artist name to filter by
            limit: Maximum results to return

        Returns:
            List of matching Track entities, sorted by relevance
        """
        # Base query with title filter (case-insensitive)
        stmt = select(TrackModel).where(
            func.lower(TrackModel.title) == func.lower(title)
        )

        # If artist name provided, join with artist table and filter
        if artist_name:
            stmt = stmt.join(ArtistModel, TrackModel.artist_id == ArtistModel.id).where(
                func.lower(ArtistModel.name) == func.lower(artist_name)
            )

        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            Track(
                id=TrackId.from_string(model.id),
                title=model.title,
                artist_id=ArtistId.from_string(model.artist_id),
                album_id=AlbumId.from_string(model.album_id)
                if model.album_id
                else None,
                duration_ms=model.duration_ms,
                track_number=model.track_number,
                disc_number=model.disc_number,
                spotify_uri=SpotifyUri.from_string(model.spotify_uri)
                if model.spotify_uri
                else None,
                musicbrainz_id=model.musicbrainz_id,
                isrc=model.isrc,
                file_path=FilePath.from_string(model.file_path)
                if model.file_path
                else None,
                genres=[model.genre] if model.genre else [],
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def get_unenriched_with_isrc(self, limit: int = 50) -> list[Track]:
        """Get tracks that have ISRC but no Spotify URI (unenriched).

        Hey future me - this is the GOLD MINE for enrichment! Tracks with ISRC
        can be matched 100% reliably via Deezer/Spotify ISRC lookup.
        Much better than fuzzy title/artist matching!

        Args:
            limit: Maximum number of tracks to return

        Returns:
            List of Track entities with ISRC but no spotify_uri
        """
        stmt = (
            select(TrackModel)
            .where(
                TrackModel.isrc.isnot(None),  # Has ISRC
                TrackModel.isrc != "",  # ISRC is not empty string
                TrackModel.spotify_uri.is_(None),  # But no Spotify URI yet
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            Track(
                id=TrackId.from_string(model.id),
                title=model.title,
                artist_id=ArtistId.from_string(model.artist_id),
                album_id=AlbumId.from_string(model.album_id)
                if model.album_id
                else None,
                duration_ms=model.duration_ms,
                track_number=model.track_number,
                disc_number=model.disc_number,
                spotify_uri=SpotifyUri.from_string(model.spotify_uri)
                if model.spotify_uri
                else None,
                musicbrainz_id=model.musicbrainz_id,
                isrc=model.isrc,
                file_path=FilePath.from_string(model.file_path)
                if model.file_path
                else None,
                genres=[model.genre] if model.genre else [],
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    # =========================================================================
    # MULTI-SERVICE LOOKUP METHODS
    # =========================================================================
    # Hey future me - these are for multi-service deduplication!
    # Pattern: Check ISRC first (universal), then service ID, then name match.
    # =========================================================================

    async def get_by_deezer_id(self, deezer_id: str) -> Track | None:
        """Get a track by Deezer ID.

        Args:
            deezer_id: Deezer track ID

        Returns:
            Track entity if found, None otherwise
        """
        stmt = select(TrackModel).where(TrackModel.deezer_id == deezer_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return Track(
            id=TrackId.from_string(model.id),
            title=model.title,
            artist_id=ArtistId.from_string(model.artist_id),
            album_id=AlbumId.from_string(model.album_id)
            if model.album_id
            else None,
            duration_ms=model.duration_ms,
            track_number=model.track_number,
            disc_number=model.disc_number,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            isrc=model.isrc,
            deezer_id=model.deezer_id,
            tidal_id=model.tidal_id,
            file_path=FilePath.from_string(model.file_path)
            if model.file_path
            else None,
            genres=[model.genre] if model.genre else [],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_tidal_id(self, tidal_id: str) -> Track | None:
        """Get a track by Tidal ID.

        Args:
            tidal_id: Tidal track ID

        Returns:
            Track entity if found, None otherwise
        """
        stmt = select(TrackModel).where(TrackModel.tidal_id == tidal_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return Track(
            id=TrackId.from_string(model.id),
            title=model.title,
            artist_id=ArtistId.from_string(model.artist_id),
            album_id=AlbumId.from_string(model.album_id)
            if model.album_id
            else None,
            duration_ms=model.duration_ms,
            track_number=model.track_number,
            disc_number=model.disc_number,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            musicbrainz_id=model.musicbrainz_id,
            isrc=model.isrc,
            deezer_id=model.deezer_id,
            tidal_id=model.tidal_id,
            file_path=FilePath.from_string(model.file_path)
            if model.file_path
            else None,
            genres=[model.genre] if model.genre else [],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class PlaylistRepository(IPlaylistRepository):
    """SQLAlchemy implementation of Playlist repository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    async def add(self, playlist: Playlist) -> None:
        """Add a new playlist."""
        model = PlaylistModel(
            id=str(playlist.id.value),
            name=playlist.name,
            description=playlist.description,
            source=playlist.source.value,
            spotify_uri=str(playlist.spotify_uri) if playlist.spotify_uri else None,
            artwork_url=playlist.artwork_url,
            created_at=playlist.created_at,
            updated_at=playlist.updated_at,
        )
        self.session.add(model)

        # Add playlist tracks
        for position, track_id in enumerate(playlist.track_ids):
            playlist_track = PlaylistTrackModel(
                playlist_id=str(playlist.id.value),
                track_id=str(track_id.value),
                position=position,
            )
            self.session.add(playlist_track)

    async def update(self, playlist: Playlist) -> None:
        """Update an existing playlist."""
        stmt = select(PlaylistModel).where(PlaylistModel.id == str(playlist.id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException("Playlist", playlist.id.value)

        model.name = playlist.name
        model.description = playlist.description
        model.source = playlist.source.value
        model.spotify_uri = str(playlist.spotify_uri) if playlist.spotify_uri else None
        model.artwork_url = playlist.artwork_url
        model.updated_at = playlist.updated_at

        # Update playlist tracks - delete old and add new
        delete_stmt = delete(PlaylistTrackModel).where(
            PlaylistTrackModel.playlist_id == str(playlist.id.value)
        )
        await self.session.execute(delete_stmt)

        for position, track_id in enumerate(playlist.track_ids):
            playlist_track = PlaylistTrackModel(
                playlist_id=str(playlist.id.value),
                track_id=str(track_id.value),
                position=position,
            )
            self.session.add(playlist_track)

    async def delete(self, playlist_id: PlaylistId) -> None:
        """Delete a playlist."""
        stmt = delete(PlaylistModel).where(PlaylistModel.id == str(playlist_id.value))
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]  # type: ignore[attr-defined]
            raise EntityNotFoundException("Playlist", playlist_id.value)

    async def get_by_id(self, playlist_id: PlaylistId) -> Playlist | None:
        """Get a playlist by ID with eager loading of tracks."""
        stmt = (
            select(PlaylistModel)
            .where(PlaylistModel.id == str(playlist_id.value))
            .options(selectinload(PlaylistModel.playlist_tracks))
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Get playlist tracks in order
        track_ids = [TrackId.from_string(pt.track_id) for pt in model.playlist_tracks]

        # Convert source string to PlaylistSource enum (case-insensitive)
        # Hey future me - DB stores uppercase (SPOTIFY, MANUAL) but enum has lowercase values
        try:
            source = PlaylistSource(model.source.lower())
        except ValueError as e:
            raise ValidationException(
                f"Invalid playlist source '{model.source}' for playlist {model.id}"
            ) from e

        return Playlist(
            id=PlaylistId.from_string(model.id),
            name=model.name,
            description=model.description,
            source=source,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            artwork_url=model.artwork_url,  # Spotify playlist cover image
            track_ids=track_ids,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_spotify_uri(self, spotify_uri: SpotifyUri) -> Playlist | None:
        """Get a playlist by Spotify URI with eager loading of tracks."""
        stmt = (
            select(PlaylistModel)
            .where(PlaylistModel.spotify_uri == str(spotify_uri))
            .options(selectinload(PlaylistModel.playlist_tracks))
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Get playlist tracks in order
        track_ids = [TrackId.from_string(pt.track_id) for pt in model.playlist_tracks]

        # Convert source string to PlaylistSource enum (case-insensitive)
        # Hey future me - DB stores uppercase (SPOTIFY, MANUAL) but enum has lowercase values
        try:
            source = PlaylistSource(model.source.lower())
        except ValueError as e:
            raise ValidationException(
                f"Invalid playlist source '{model.source}' for playlist {model.id}"
            ) from e

        return Playlist(
            id=PlaylistId.from_string(model.id),
            name=model.name,
            description=model.description,
            source=source,
            spotify_uri=SpotifyUri.from_string(model.spotify_uri)
            if model.spotify_uri
            else None,
            artwork_url=model.artwork_url,  # Spotify playlist cover image
            track_ids=track_ids,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def add_track(self, playlist_id: PlaylistId, track_id: TrackId) -> None:
        """Add a track to a playlist (if not already present).

        Hey future me - this now checks for duplicates before adding!
        If the track is already in the playlist, we just skip it silently.
        This prevents UNIQUE constraint violations on re-imports.
        """
        # Check if track already exists in this playlist
        check_stmt = select(PlaylistTrackModel).where(
            PlaylistTrackModel.playlist_id == str(playlist_id.value),
            PlaylistTrackModel.track_id == str(track_id.value),
        )
        check_result = await self.session.execute(check_stmt)
        if check_result.scalar_one_or_none():
            # Track already in playlist, skip
            return

        # Get current max position
        stmt = select(PlaylistTrackModel).where(
            PlaylistTrackModel.playlist_id == str(playlist_id.value)
        )
        result = await self.session.execute(stmt)
        existing_tracks = result.scalars().all()

        max_position = max([pt.position for pt in existing_tracks], default=-1)

        # Add new track at end
        playlist_track = PlaylistTrackModel(
            playlist_id=str(playlist_id.value),
            track_id=str(track_id.value),
            position=max_position + 1,
        )
        self.session.add(playlist_track)

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Playlist]:
        """List all playlists with pagination and eager loading of tracks."""
        stmt = (
            select(PlaylistModel)
            .options(selectinload(PlaylistModel.playlist_tracks))
            .order_by(PlaylistModel.name)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        playlists = []
        for model in models:
            track_ids = [
                TrackId.from_string(pt.track_id) for pt in model.playlist_tracks
            ]
            # Convert source string to PlaylistSource enum (case-insensitive)
            # Hey future me - DB stores uppercase (SPOTIFY, MANUAL) but enum has lowercase values
            try:
                source = PlaylistSource(model.source.lower())
            except ValueError as e:
                raise ValidationException(
                    f"Invalid playlist source '{model.source}' for playlist {model.id}"
                ) from e

            playlists.append(
                Playlist(
                    id=PlaylistId.from_string(model.id),
                    name=model.name,
                    description=model.description,
                    source=source,
                    spotify_uri=SpotifyUri.from_string(model.spotify_uri)
                    if model.spotify_uri
                    else None,
                    artwork_url=model.artwork_url,
                    track_ids=track_ids,
                    created_at=model.created_at,
                    updated_at=model.updated_at,
                )
            )

        return playlists

    # Hey future me - this counts playlists by source type (spotify/manual).
    # Used for the Spotify Database Stats in Settings UI.
    # DB stores source as uppercase string, but we accept case-insensitive input.
    async def count_by_source(self, source: str) -> int:
        """Count playlists by source (e.g., 'spotify', 'manual').

        Args:
            source: Source to filter by (case-insensitive)

        Returns:
            Count of playlists with matching source
        """
        # DB stores uppercase, so we convert input to uppercase for matching
        stmt = select(func.count(PlaylistModel.id)).where(
            func.upper(PlaylistModel.source) == source.upper()
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0


class DownloadRepository(IDownloadRepository):
    """SQLAlchemy implementation of Download repository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    async def add(self, download: Download) -> None:
        """Add a new download."""
        model = DownloadModel(
            id=str(download.id.value),
            track_id=str(download.track_id.value),
            status=download.status.value,
            priority=download.priority,
            target_path=str(download.target_path) if download.target_path else None,
            source_url=download.source_url,
            progress_percent=download.progress_percent,
            error_message=download.error_message,
            started_at=download.started_at,
            completed_at=download.completed_at,
            created_at=download.created_at,
            updated_at=download.updated_at,
        )
        self.session.add(model)

    async def update(self, download: Download) -> None:
        """Update an existing download."""
        stmt = select(DownloadModel).where(DownloadModel.id == str(download.id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException("Download", download.id.value)

        model.track_id = str(download.track_id.value)
        model.status = download.status.value
        model.priority = download.priority
        model.target_path = str(download.target_path) if download.target_path else None
        model.source_url = download.source_url
        model.progress_percent = download.progress_percent
        model.error_message = download.error_message
        model.started_at = download.started_at
        model.completed_at = download.completed_at
        model.updated_at = download.updated_at

    async def delete(self, download_id: DownloadId) -> None:
        """Delete a download."""
        stmt = delete(DownloadModel).where(DownloadModel.id == str(download_id.value))
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise EntityNotFoundException("Download", download_id.value)

    async def get_by_id(self, download_id: DownloadId) -> Download | None:
        """Get a download by ID with eager loading of track."""
        stmt = (
            select(DownloadModel)
            .where(DownloadModel.id == str(download_id.value))
            .options(selectinload(DownloadModel.track))
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Convert status string to DownloadStatus enum
        try:
            status = DownloadStatus(model.status)
        except ValueError as e:
            raise ValidationException(
                f"Invalid download status '{model.status}' for download {model.id}"
            ) from e

        return Download(
            id=DownloadId.from_string(model.id),
            track_id=TrackId.from_string(model.track_id),
            status=status,
            priority=model.priority,
            target_path=FilePath.from_string(model.target_path)
            if model.target_path
            else None,
            source_url=model.source_url,
            progress_percent=model.progress_percent,
            error_message=model.error_message,
            started_at=model.started_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_track(self, track_id: TrackId) -> Download | None:
        """Get a download by track ID with eager loading."""
        stmt = (
            select(DownloadModel)
            .where(DownloadModel.track_id == str(track_id.value))
            .options(selectinload(DownloadModel.track))
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Convert status string to DownloadStatus enum
        try:
            status = DownloadStatus(model.status)
        except ValueError as e:
            raise ValidationException(
                f"Invalid download status '{model.status}' for download {model.id}"
            ) from e

        return Download(
            id=DownloadId.from_string(model.id),
            track_id=TrackId.from_string(model.track_id),
            status=status,
            priority=model.priority,
            target_path=FilePath.from_string(model.target_path)
            if model.target_path
            else None,
            source_url=model.source_url,
            progress_percent=model.progress_percent,
            error_message=model.error_message,
            started_at=model.started_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_by_status(
        self, status: str, limit: int = 100, offset: int = 0
    ) -> list[Download]:
        """List downloads with a specific status, with pagination and eager loading."""
        stmt = (
            select(DownloadModel)
            .options(selectinload(DownloadModel.track))
            .where(DownloadModel.status == status)
            .order_by(DownloadModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            Download(
                id=DownloadId.from_string(model.id),
                track_id=TrackId.from_string(model.track_id),
                status=DownloadStatus(model.status),
                priority=model.priority,
                target_path=FilePath.from_string(model.target_path)
                if model.target_path
                else None,
                source_url=model.source_url,
                progress_percent=model.progress_percent,
                error_message=model.error_message,
                started_at=model.started_at,
                completed_at=model.completed_at,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    # Hey future me - list_active now includes WAITING and PENDING! This means the download queue UI
    # will show ALL downloads that aren't finished (including those waiting for slskd). The order is
    # by priority DESC (higher priority first) then created_at DESC (oldest first within same priority).
    async def list_active(self, limit: int = 100, offset: int = 0) -> list[Download]:
        """List all active downloads (not finished), with pagination and eager loading."""
        stmt = (
            select(DownloadModel)
            .options(selectinload(DownloadModel.track))
            .where(
                DownloadModel.status.in_(
                    [
                        DownloadStatus.WAITING.value,
                        DownloadStatus.PENDING.value,
                        DownloadStatus.QUEUED.value,
                        DownloadStatus.DOWNLOADING.value,
                    ]
                )
            )
            .order_by(
                DownloadModel.priority.desc(),
                DownloadModel.created_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            Download(
                id=DownloadId.from_string(model.id),
                track_id=TrackId.from_string(model.track_id),
                status=DownloadStatus(model.status),
                priority=model.priority,
                target_path=FilePath.from_string(model.target_path)
                if model.target_path
                else None,
                source_url=model.source_url,
                progress_percent=model.progress_percent,
                error_message=model.error_message,
                started_at=model.started_at,
                completed_at=model.completed_at,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    # Hey future me - this gets downloads waiting for slskd to become available!
    # Ordered by priority DESC then created_at ASC (oldest first) so we process in FIFO within priority.
    # Used by QueueDispatcherWorker to find downloads to dispatch when slskd comes online.
    async def list_waiting(self, limit: int = 10) -> list[Download]:
        """List downloads waiting for download manager to become available.

        Returns downloads in WAITING status, ordered by priority (highest first)
        then by created_at (oldest first within same priority).
        """
        stmt = (
            select(DownloadModel)
            .options(selectinload(DownloadModel.track))
            .where(DownloadModel.status == DownloadStatus.WAITING.value)
            .order_by(
                DownloadModel.priority.desc(),
                DownloadModel.created_at.asc(),
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            Download(
                id=DownloadId.from_string(model.id),
                track_id=TrackId.from_string(model.track_id),
                status=DownloadStatus(model.status),
                priority=model.priority,
                target_path=FilePath.from_string(model.target_path)
                if model.target_path
                else None,
                source_url=model.source_url,
                progress_percent=model.progress_percent,
                error_message=model.error_message,
                started_at=model.started_at,
                completed_at=model.completed_at,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def count_by_status(self, status: str) -> int:
        """Count downloads by status."""
        stmt = select(func.count(DownloadModel.id)).where(
            DownloadModel.status == status
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def count_active(self) -> int:
        """Count active downloads (including waiting)."""
        stmt = select(func.count(DownloadModel.id)).where(
            DownloadModel.status.in_(
                [
                    DownloadStatus.WAITING.value,
                    DownloadStatus.PENDING.value,
                    DownloadStatus.QUEUED.value,
                    DownloadStatus.DOWNLOADING.value,
                ]
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def list_recent(self, limit: int = 5) -> list[Download]:
        """List recently completed or active downloads with track info.

        Hey future me - this is for the dashboard recent activity!
        Returns downloads ordered by completed_at (newest first), falling back to created_at.
        Eager-loads the track + artist + album relationships so we can show title/artist/artwork.
        """
        from sqlalchemy.orm import selectinload

        from soulspot.infrastructure.persistence.models import TrackModel

        stmt = (
            select(DownloadModel)
            .options(
                selectinload(DownloadModel.track).selectinload(TrackModel.artist),
                selectinload(DownloadModel.track).selectinload(TrackModel.album),
            )
            .order_by(
                DownloadModel.completed_at.desc().nullslast(),
                DownloadModel.created_at.desc(),
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        downloads = []
        for model in models:
            # Convert status string to DownloadStatus enum
            try:
                status = DownloadStatus(model.status)
            except ValueError:
                status = DownloadStatus.PENDING

            # Create download with track metadata if available
            download = Download(
                id=DownloadId.from_string(model.id),
                track_id=TrackId.from_string(model.track_id),
                status=status,
                priority=model.priority,
                target_path=FilePath.from_string(model.target_path)
                if model.target_path
                else None,
                source_url=model.source_url,
                progress_percent=model.progress_percent,
                error_message=model.error_message,
                started_at=model.started_at,
                completed_at=model.completed_at,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )

            # Attach track info as extra attributes for dashboard display
            # Hey future me - album_art comes from Track -> Album -> artwork_url!
            if model.track:
                download.track_title = model.track.title  # type: ignore[attr-defined]
                download.artist_name = (  # type: ignore[attr-defined]
                    model.track.artist.name if model.track.artist else None
                )
                download.album_art_url = (  # type: ignore[attr-defined]
                    model.track.album.artwork_url if model.track.album else None
                )
            else:
                download.track_title = None  # type: ignore[attr-defined]
                download.artist_name = None  # type: ignore[attr-defined]
                download.album_art_url = None  # type: ignore[attr-defined]

            downloads.append(download)

        return downloads

    async def get_completed_track_ids(self) -> set[str]:
        """Get set of track IDs for all completed downloads.
        
        Hey future me - this is for AutoImportService to filter which files to import!
        Only files with completed downloads should be imported to prevent importing
        random files that users didn't request. Returns raw string IDs for fast lookup.
        """
        stmt = select(DownloadModel.track_id).where(
            DownloadModel.status == DownloadStatus.COMPLETED.value
        )
        result = await self.session.execute(stmt)
        track_ids = result.scalars().all()
        return set(track_ids)


class ArtistWatchlistRepository(IArtistWatchlistRepository):
    """SQLAlchemy implementation of Artist Watchlist repository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    async def add(self, watchlist: Any) -> None:
        """Add a new watchlist."""

        from .models import ArtistWatchlistModel

        model = ArtistWatchlistModel(
            id=str(watchlist.id.value),
            artist_id=str(watchlist.artist_id.value),
            status=watchlist.status.value,
            check_frequency_hours=watchlist.check_frequency_hours,
            auto_download=watchlist.auto_download,
            quality_profile=watchlist.quality_profile,
            last_checked_at=watchlist.last_checked_at,
            last_release_date=watchlist.last_release_date,
            total_releases_found=watchlist.total_releases_found,
            total_downloads_triggered=watchlist.total_downloads_triggered,
            created_at=watchlist.created_at,
            updated_at=watchlist.updated_at,
        )
        self.session.add(model)

    async def get_by_id(self, watchlist_id: Any) -> Any:
        """Get a watchlist by ID."""
        from soulspot.domain.entities import ArtistWatchlist, WatchlistStatus
        from soulspot.domain.value_objects import WatchlistId

        from .models import ArtistWatchlistModel

        stmt = select(ArtistWatchlistModel).where(
            ArtistWatchlistModel.id == str(watchlist_id.value)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return ArtistWatchlist(
            id=WatchlistId.from_string(model.id),
            artist_id=ArtistId.from_string(model.artist_id),
            status=WatchlistStatus(model.status),
            check_frequency_hours=model.check_frequency_hours,
            auto_download=model.auto_download,
            quality_profile=model.quality_profile,
            last_checked_at=model.last_checked_at,
            last_release_date=model.last_release_date,
            total_releases_found=model.total_releases_found,
            total_downloads_triggered=model.total_downloads_triggered,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_artist_id(self, artist_id: ArtistId) -> Any:
        """Get watchlist for an artist."""
        from soulspot.domain.entities import ArtistWatchlist, WatchlistStatus
        from soulspot.domain.value_objects import WatchlistId

        from .models import ArtistWatchlistModel

        stmt = select(ArtistWatchlistModel).where(
            ArtistWatchlistModel.artist_id == str(artist_id.value)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return ArtistWatchlist(
            id=WatchlistId.from_string(model.id),
            artist_id=ArtistId.from_string(model.artist_id),
            status=WatchlistStatus(model.status),
            check_frequency_hours=model.check_frequency_hours,
            auto_download=model.auto_download,
            quality_profile=model.quality_profile,
            last_checked_at=model.last_checked_at,
            last_release_date=model.last_release_date,
            total_releases_found=model.total_releases_found,
            total_downloads_triggered=model.total_downloads_triggered,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Any]:
        """List all watchlists with pagination."""
        from soulspot.domain.entities import ArtistWatchlist, WatchlistStatus
        from soulspot.domain.value_objects import WatchlistId

        from .models import ArtistWatchlistModel

        stmt = select(ArtistWatchlistModel).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            ArtistWatchlist(
                id=WatchlistId.from_string(model.id),
                artist_id=ArtistId.from_string(model.artist_id),
                status=WatchlistStatus(model.status),
                check_frequency_hours=model.check_frequency_hours,
                auto_download=model.auto_download,
                quality_profile=model.quality_profile,
                last_checked_at=model.last_checked_at,
                last_release_date=model.last_release_date,
                total_releases_found=model.total_releases_found,
                total_downloads_triggered=model.total_downloads_triggered,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def list_active(self, limit: int = 100, offset: int = 0) -> list[Any]:
        """List active watchlists."""
        from soulspot.domain.entities import ArtistWatchlist, WatchlistStatus
        from soulspot.domain.value_objects import WatchlistId

        from .models import ArtistWatchlistModel

        stmt = (
            select(ArtistWatchlistModel)
            .where(ArtistWatchlistModel.status == "active")
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            ArtistWatchlist(
                id=WatchlistId.from_string(model.id),
                artist_id=ArtistId.from_string(model.artist_id),
                status=WatchlistStatus(model.status),
                check_frequency_hours=model.check_frequency_hours,
                auto_download=model.auto_download,
                quality_profile=model.quality_profile,
                last_checked_at=model.last_checked_at,
                last_release_date=model.last_release_date,
                total_releases_found=model.total_releases_found,
                total_downloads_triggered=model.total_downloads_triggered,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def list_due_for_check(self, limit: int = 100) -> list[Any]:
        """List watchlists that are due for checking."""

        from soulspot.domain.entities import ArtistWatchlist, WatchlistStatus
        from soulspot.domain.value_objects import WatchlistId

        from .models import ArtistWatchlistModel

        # Active watchlists that haven't been checked or are due for check
        stmt = (
            select(ArtistWatchlistModel)
            .where(ArtistWatchlistModel.status == "active")
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        # Filter in Python for simpler logic
        due_watchlists = []
        for model in models:
            watchlist = ArtistWatchlist(
                id=WatchlistId.from_string(model.id),
                artist_id=ArtistId.from_string(model.artist_id),
                status=WatchlistStatus(model.status),
                check_frequency_hours=model.check_frequency_hours,
                auto_download=model.auto_download,
                quality_profile=model.quality_profile,
                last_checked_at=model.last_checked_at,
                last_release_date=model.last_release_date,
                total_releases_found=model.total_releases_found,
                total_downloads_triggered=model.total_downloads_triggered,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            if watchlist.should_check():
                due_watchlists.append(watchlist)

        return due_watchlists[:limit]

    async def update(self, watchlist: Any) -> None:
        """Update an existing watchlist."""
        from .models import ArtistWatchlistModel

        stmt = select(ArtistWatchlistModel).where(
            ArtistWatchlistModel.id == str(watchlist.id.value)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException("ArtistWatchlist", watchlist.id.value)

        model.status = watchlist.status.value
        model.check_frequency_hours = watchlist.check_frequency_hours
        model.auto_download = watchlist.auto_download
        model.quality_profile = watchlist.quality_profile
        model.last_checked_at = watchlist.last_checked_at
        model.last_release_date = watchlist.last_release_date
        model.total_releases_found = watchlist.total_releases_found
        model.total_downloads_triggered = watchlist.total_downloads_triggered
        model.updated_at = watchlist.updated_at

    async def delete(self, watchlist_id: Any) -> None:
        """Delete a watchlist."""
        from .models import ArtistWatchlistModel

        stmt = delete(ArtistWatchlistModel).where(
            ArtistWatchlistModel.id == str(watchlist_id.value)
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise EntityNotFoundException("ArtistWatchlist", watchlist_id.value)


class FilterRuleRepository(IFilterRuleRepository):
    """SQLAlchemy implementation of Filter Rule repository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    async def add(self, filter_rule: Any) -> None:
        """Add a new filter rule."""
        from .models import FilterRuleModel

        model = FilterRuleModel(
            id=str(filter_rule.id.value),
            name=filter_rule.name,
            filter_type=filter_rule.filter_type.value,
            target=filter_rule.target.value,
            pattern=filter_rule.pattern,
            is_regex=filter_rule.is_regex,
            enabled=filter_rule.enabled,
            priority=filter_rule.priority,
            description=filter_rule.description,
            created_at=filter_rule.created_at,
            updated_at=filter_rule.updated_at,
        )
        self.session.add(model)

    async def get_by_id(self, rule_id: Any) -> Any:
        """Get a filter rule by ID."""
        from soulspot.domain.entities import FilterRule, FilterTarget, FilterType
        from soulspot.domain.value_objects import FilterRuleId

        from .models import FilterRuleModel

        stmt = select(FilterRuleModel).where(FilterRuleModel.id == str(rule_id.value))
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return FilterRule(
            id=FilterRuleId.from_string(model.id),
            name=model.name,
            filter_type=FilterType(model.filter_type),
            target=FilterTarget(model.target),
            pattern=model.pattern,
            is_regex=model.is_regex,
            enabled=model.enabled,
            priority=model.priority,
            description=model.description,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Any]:
        """List all filter rules with pagination."""
        from soulspot.domain.entities import FilterRule, FilterTarget, FilterType
        from soulspot.domain.value_objects import FilterRuleId

        from .models import FilterRuleModel

        stmt = (
            select(FilterRuleModel)
            .order_by(FilterRuleModel.priority.desc(), FilterRuleModel.created_at)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            FilterRule(
                id=FilterRuleId.from_string(model.id),
                name=model.name,
                filter_type=FilterType(model.filter_type),
                target=FilterTarget(model.target),
                pattern=model.pattern,
                is_regex=model.is_regex,
                enabled=model.enabled,
                priority=model.priority,
                description=model.description,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def list_by_type(self, filter_type: str) -> list[Any]:
        """List filter rules by type (whitelist/blacklist)."""
        from soulspot.domain.entities import FilterRule, FilterTarget, FilterType
        from soulspot.domain.value_objects import FilterRuleId

        from .models import FilterRuleModel

        stmt = (
            select(FilterRuleModel)
            .where(FilterRuleModel.filter_type == filter_type)
            .order_by(FilterRuleModel.priority.desc(), FilterRuleModel.created_at)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            FilterRule(
                id=FilterRuleId.from_string(model.id),
                name=model.name,
                filter_type=FilterType(model.filter_type),
                target=FilterTarget(model.target),
                pattern=model.pattern,
                is_regex=model.is_regex,
                enabled=model.enabled,
                priority=model.priority,
                description=model.description,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def list_enabled(self) -> list[Any]:
        """List all enabled filter rules."""
        from soulspot.domain.entities import FilterRule, FilterTarget, FilterType
        from soulspot.domain.value_objects import FilterRuleId

        from .models import FilterRuleModel

        stmt = (
            select(FilterRuleModel)
            .where(FilterRuleModel.enabled == True)  # noqa: E712
            .order_by(FilterRuleModel.priority.desc(), FilterRuleModel.created_at)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            FilterRule(
                id=FilterRuleId.from_string(model.id),
                name=model.name,
                filter_type=FilterType(model.filter_type),
                target=FilterTarget(model.target),
                pattern=model.pattern,
                is_regex=model.is_regex,
                enabled=model.enabled,
                priority=model.priority,
                description=model.description,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def update(self, filter_rule: Any) -> None:
        """Update an existing filter rule."""
        from .models import FilterRuleModel

        stmt = select(FilterRuleModel).where(
            FilterRuleModel.id == str(filter_rule.id.value)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException("FilterRule", filter_rule.id.value)

        model.name = filter_rule.name
        model.filter_type = filter_rule.filter_type.value
        model.target = filter_rule.target.value
        model.pattern = filter_rule.pattern
        model.is_regex = filter_rule.is_regex
        model.enabled = filter_rule.enabled
        model.priority = filter_rule.priority
        model.description = filter_rule.description
        model.updated_at = filter_rule.updated_at

    async def delete(self, rule_id: Any) -> None:
        """Delete a filter rule."""
        from .models import FilterRuleModel

        stmt = delete(FilterRuleModel).where(FilterRuleModel.id == str(rule_id.value))
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise EntityNotFoundException("FilterRule", rule_id.value)


class AutomationRuleRepository(IAutomationRuleRepository):
    """SQLAlchemy implementation of Automation Rule repository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    async def add(self, rule: Any) -> None:
        """Add a new automation rule."""
        from .models import AutomationRuleModel

        model = AutomationRuleModel(
            id=str(rule.id.value),
            name=rule.name,
            trigger=rule.trigger.value,
            action=rule.action.value,
            enabled=rule.enabled,
            priority=rule.priority,
            quality_profile=rule.quality_profile,
            apply_filters=rule.apply_filters,
            auto_process=rule.auto_process,
            description=rule.description,
            last_triggered_at=rule.last_triggered_at,
            total_executions=rule.total_executions,
            successful_executions=rule.successful_executions,
            failed_executions=rule.failed_executions,
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )
        self.session.add(model)

    async def get_by_id(self, rule_id: Any) -> Any:
        """Get an automation rule by ID."""
        from soulspot.domain.entities import (
            AutomationAction,
            AutomationRule,
            AutomationTrigger,
        )
        from soulspot.domain.value_objects import AutomationRuleId

        from .models import AutomationRuleModel

        stmt = select(AutomationRuleModel).where(
            AutomationRuleModel.id == str(rule_id.value)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return AutomationRule(
            id=AutomationRuleId.from_string(model.id),
            name=model.name,
            trigger=AutomationTrigger(model.trigger),
            action=AutomationAction(model.action),
            enabled=model.enabled,
            priority=model.priority,
            quality_profile=model.quality_profile,
            apply_filters=model.apply_filters,
            auto_process=model.auto_process,
            description=model.description,
            last_triggered_at=model.last_triggered_at,
            total_executions=model.total_executions,
            successful_executions=model.successful_executions,
            failed_executions=model.failed_executions,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Any]:
        """List all automation rules with pagination."""
        from soulspot.domain.entities import (
            AutomationAction,
            AutomationRule,
            AutomationTrigger,
        )
        from soulspot.domain.value_objects import AutomationRuleId

        from .models import AutomationRuleModel

        stmt = (
            select(AutomationRuleModel)
            .order_by(
                AutomationRuleModel.priority.desc(), AutomationRuleModel.created_at
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            AutomationRule(
                id=AutomationRuleId.from_string(model.id),
                name=model.name,
                trigger=AutomationTrigger(model.trigger),
                action=AutomationAction(model.action),
                enabled=model.enabled,
                priority=model.priority,
                quality_profile=model.quality_profile,
                apply_filters=model.apply_filters,
                auto_process=model.auto_process,
                description=model.description,
                last_triggered_at=model.last_triggered_at,
                total_executions=model.total_executions,
                successful_executions=model.successful_executions,
                failed_executions=model.failed_executions,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def list_by_trigger(self, trigger: str) -> list[Any]:
        """List automation rules by trigger type."""
        from soulspot.domain.entities import (
            AutomationAction,
            AutomationRule,
            AutomationTrigger,
        )
        from soulspot.domain.value_objects import AutomationRuleId

        from .models import AutomationRuleModel

        stmt = (
            select(AutomationRuleModel)
            .where(AutomationRuleModel.trigger == trigger)
            .order_by(
                AutomationRuleModel.priority.desc(), AutomationRuleModel.created_at
            )
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            AutomationRule(
                id=AutomationRuleId.from_string(model.id),
                name=model.name,
                trigger=AutomationTrigger(model.trigger),
                action=AutomationAction(model.action),
                enabled=model.enabled,
                priority=model.priority,
                quality_profile=model.quality_profile,
                apply_filters=model.apply_filters,
                auto_process=model.auto_process,
                description=model.description,
                last_triggered_at=model.last_triggered_at,
                total_executions=model.total_executions,
                successful_executions=model.successful_executions,
                failed_executions=model.failed_executions,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def list_enabled(self) -> list[Any]:
        """List all enabled automation rules."""
        from soulspot.domain.entities import (
            AutomationAction,
            AutomationRule,
            AutomationTrigger,
        )
        from soulspot.domain.value_objects import AutomationRuleId

        from .models import AutomationRuleModel

        stmt = (
            select(AutomationRuleModel)
            .where(AutomationRuleModel.enabled == True)  # noqa: E712
            .order_by(
                AutomationRuleModel.priority.desc(), AutomationRuleModel.created_at
            )
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            AutomationRule(
                id=AutomationRuleId.from_string(model.id),
                name=model.name,
                trigger=AutomationTrigger(model.trigger),
                action=AutomationAction(model.action),
                enabled=model.enabled,
                priority=model.priority,
                quality_profile=model.quality_profile,
                apply_filters=model.apply_filters,
                auto_process=model.auto_process,
                description=model.description,
                last_triggered_at=model.last_triggered_at,
                total_executions=model.total_executions,
                successful_executions=model.successful_executions,
                failed_executions=model.failed_executions,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def update(self, rule: Any) -> None:
        """Update an existing automation rule."""
        from .models import AutomationRuleModel

        stmt = select(AutomationRuleModel).where(
            AutomationRuleModel.id == str(rule.id.value)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException("AutomationRule", rule.id.value)

        model.name = rule.name
        model.trigger = rule.trigger.value
        model.action = rule.action.value
        model.enabled = rule.enabled
        model.priority = rule.priority
        model.quality_profile = rule.quality_profile
        model.apply_filters = rule.apply_filters
        model.auto_process = rule.auto_process
        model.description = rule.description
        model.last_triggered_at = rule.last_triggered_at
        model.total_executions = rule.total_executions
        model.successful_executions = rule.successful_executions
        model.failed_executions = rule.failed_executions
        model.updated_at = rule.updated_at

    async def delete(self, rule_id: Any) -> None:
        """Delete an automation rule."""
        from .models import AutomationRuleModel

        stmt = delete(AutomationRuleModel).where(
            AutomationRuleModel.id == str(rule_id.value)
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise EntityNotFoundException("AutomationRule", rule_id.value)


class QualityUpgradeCandidateRepository(IQualityUpgradeCandidateRepository):
    """SQLAlchemy implementation of Quality Upgrade Candidate repository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    async def add(self, candidate: Any) -> None:
        """Add a new quality upgrade candidate."""
        from .models import QualityUpgradeCandidateModel

        model = QualityUpgradeCandidateModel(
            id=candidate.id,
            track_id=str(candidate.track_id.value),
            current_bitrate=candidate.current_bitrate,
            current_format=candidate.current_format,
            target_bitrate=candidate.target_bitrate,
            target_format=candidate.target_format,
            improvement_score=candidate.improvement_score,
            detected_at=candidate.detected_at,
            processed=candidate.processed,
            download_id=str(candidate.download_id.value)
            if candidate.download_id
            else None,
            created_at=candidate.created_at,
            updated_at=candidate.updated_at,
        )
        self.session.add(model)

    async def get_by_id(self, candidate_id: str) -> Any:
        """Get a quality upgrade candidate by ID."""
        from soulspot.domain.entities import QualityUpgradeCandidate
        from soulspot.domain.value_objects import DownloadId, TrackId

        from .models import QualityUpgradeCandidateModel

        stmt = select(QualityUpgradeCandidateModel).where(
            QualityUpgradeCandidateModel.id == candidate_id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return QualityUpgradeCandidate(
            id=model.id,
            track_id=TrackId.from_string(model.track_id),
            current_bitrate=model.current_bitrate,
            current_format=model.current_format,
            target_bitrate=model.target_bitrate,
            target_format=model.target_format,
            improvement_score=model.improvement_score,
            detected_at=model.detected_at,
            processed=model.processed,
            download_id=DownloadId.from_string(model.download_id)
            if model.download_id
            else None,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_track_id(self, track_id: Any) -> Any:
        """Get quality upgrade candidate for a track."""
        from soulspot.domain.entities import QualityUpgradeCandidate
        from soulspot.domain.value_objects import DownloadId, TrackId

        from .models import QualityUpgradeCandidateModel

        stmt = select(QualityUpgradeCandidateModel).where(
            QualityUpgradeCandidateModel.track_id == str(track_id.value)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return QualityUpgradeCandidate(
            id=model.id,
            track_id=TrackId.from_string(model.track_id),
            current_bitrate=model.current_bitrate,
            current_format=model.current_format,
            target_bitrate=model.target_bitrate,
            target_format=model.target_format,
            improvement_score=model.improvement_score,
            detected_at=model.detected_at,
            processed=model.processed,
            download_id=DownloadId.from_string(model.download_id)
            if model.download_id
            else None,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Any]:
        """List all quality upgrade candidates with pagination."""
        from soulspot.domain.entities import QualityUpgradeCandidate
        from soulspot.domain.value_objects import DownloadId, TrackId

        from .models import QualityUpgradeCandidateModel

        stmt = (
            select(QualityUpgradeCandidateModel)
            .order_by(
                QualityUpgradeCandidateModel.improvement_score.desc(),
                QualityUpgradeCandidateModel.detected_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            QualityUpgradeCandidate(
                id=model.id,
                track_id=TrackId.from_string(model.track_id),
                current_bitrate=model.current_bitrate,
                current_format=model.current_format,
                target_bitrate=model.target_bitrate,
                target_format=model.target_format,
                improvement_score=model.improvement_score,
                detected_at=model.detected_at,
                processed=model.processed,
                download_id=DownloadId.from_string(model.download_id)
                if model.download_id
                else None,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def list_unprocessed(
        self, limit: int = 100, min_score: float = 0.0
    ) -> list[Any]:
        """List unprocessed quality upgrade candidates."""
        from soulspot.domain.entities import QualityUpgradeCandidate
        from soulspot.domain.value_objects import DownloadId, TrackId

        from .models import QualityUpgradeCandidateModel

        stmt = (
            select(QualityUpgradeCandidateModel)
            .where(
                QualityUpgradeCandidateModel.processed == False,  # noqa: E712
                QualityUpgradeCandidateModel.improvement_score >= min_score,
            )
            .order_by(
                QualityUpgradeCandidateModel.improvement_score.desc(),
                QualityUpgradeCandidateModel.detected_at.desc(),
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            QualityUpgradeCandidate(
                id=model.id,
                track_id=TrackId.from_string(model.track_id),
                current_bitrate=model.current_bitrate,
                current_format=model.current_format,
                target_bitrate=model.target_bitrate,
                target_format=model.target_format,
                improvement_score=model.improvement_score,
                detected_at=model.detected_at,
                processed=model.processed,
                download_id=DownloadId.from_string(model.download_id)
                if model.download_id
                else None,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]

    async def update(self, candidate: Any) -> None:
        """Update an existing quality upgrade candidate."""
        from .models import QualityUpgradeCandidateModel

        stmt = select(QualityUpgradeCandidateModel).where(
            QualityUpgradeCandidateModel.id == candidate.id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException("QualityUpgradeCandidate", candidate.id)

        model.processed = candidate.processed
        model.download_id = (
            str(candidate.download_id.value) if candidate.download_id else None
        )
        model.updated_at = candidate.updated_at

    async def delete(self, candidate_id: str) -> None:
        """Delete a quality upgrade candidate."""
        from .models import QualityUpgradeCandidateModel

        stmt = delete(QualityUpgradeCandidateModel).where(
            QualityUpgradeCandidateModel.id == candidate_id
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise EntityNotFoundException("QualityUpgradeCandidate", candidate_id)

    async def delete_processed(self) -> int:
        """Delete all processed candidates and return count."""
        from .models import QualityUpgradeCandidateModel

        stmt = delete(QualityUpgradeCandidateModel).where(
            QualityUpgradeCandidateModel.processed == True  # noqa: E712
        )
        result = await self.session.execute(stmt)
        return result.rowcount  # type: ignore[attr-defined, no-any-return]

    # Hey future me - this method returns candidates sorted by improvement_score DESC.
    # Use min_score to filter out low-priority upgrades (e.g., min_score=0.3 means 30%+ quality gain).
    # It's for the Quality Upgrade UI where users pick which tracks to upgrade first.
    # The improvement_score is calculated as (target_bitrate - current_bitrate) / target_bitrate.
    async def list_by_improvement_score(
        self, min_score: float, limit: int = 100
    ) -> list[Any]:
        """List candidates by minimum improvement score.

        Args:
            min_score: Minimum improvement score threshold (0.0 to 1.0)
            limit: Maximum number of results to return

        Returns:
            List of QualityUpgradeCandidate entities sorted by improvement_score DESC
        """
        from soulspot.domain.entities import QualityUpgradeCandidate
        from soulspot.domain.value_objects import DownloadId, TrackId

        from .models import QualityUpgradeCandidateModel

        stmt = (
            select(QualityUpgradeCandidateModel)
            .where(QualityUpgradeCandidateModel.improvement_score >= min_score)
            .order_by(
                QualityUpgradeCandidateModel.improvement_score.desc(),
                QualityUpgradeCandidateModel.detected_at.desc(),
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            QualityUpgradeCandidate(
                id=model.id,
                track_id=TrackId.from_string(model.track_id),
                current_bitrate=model.current_bitrate,
                current_format=model.current_format,
                target_bitrate=model.target_bitrate,
                target_format=model.target_format,
                improvement_score=model.improvement_score,
                detected_at=model.detected_at,
                processed=model.processed,
                download_id=DownloadId.from_string(model.download_id)
                if model.download_id
                else None,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]


# =============================================================================
# ENRICHMENT CANDIDATE REPOSITORY
# =============================================================================
# Hey future me - EnrichmentCandidateRepository stores potential Spotify matches!
# When enriching local artists/albums, we may find multiple Spotify matches.
# This repo stores all candidates for user review. User picks correct one via UI.
# =============================================================================


class EnrichmentCandidateRepository:
    """SQLAlchemy implementation of Enrichment Candidate repository.

    Manages potential Spotify matches for local library entities (artists/albums).
    Users review candidates in UI and select the correct match.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    async def add(self, candidate: Any) -> None:
        """Add a new enrichment candidate."""
        from soulspot.domain.entities import EnrichmentCandidate

        from .models import EnrichmentCandidateModel

        model = EnrichmentCandidateModel(
            id=candidate.id,
            entity_type=candidate.entity_type.value,
            entity_id=candidate.entity_id,
            spotify_uri=candidate.spotify_uri,
            spotify_name=candidate.spotify_name,
            spotify_image_url=candidate.spotify_image_url,
            confidence_score=candidate.confidence_score,
            is_selected=candidate.is_selected,
            is_rejected=candidate.is_rejected,
            extra_info=candidate.extra_info,
            created_at=candidate.created_at,
            updated_at=candidate.updated_at,
        )
        self.session.add(model)

    async def get_by_id(self, candidate_id: str) -> Any | None:
        """Get an enrichment candidate by ID."""
        from soulspot.domain.entities import EnrichmentCandidate, EnrichmentEntityType

        from .models import EnrichmentCandidateModel

        stmt = select(EnrichmentCandidateModel).where(
            EnrichmentCandidateModel.id == candidate_id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return EnrichmentCandidate(
            id=model.id,
            entity_type=EnrichmentEntityType(model.entity_type),
            entity_id=model.entity_id,
            spotify_uri=model.spotify_uri,
            spotify_name=model.spotify_name,
            spotify_image_url=model.spotify_image_url,
            confidence_score=model.confidence_score,
            is_selected=model.is_selected,
            is_rejected=model.is_rejected,
            extra_info=model.extra_info,
            created_at=ensure_utc_aware(model.created_at),
            updated_at=ensure_utc_aware(model.updated_at),
        )

    async def get_by_entity(self, entity_type: str, entity_id: str) -> list[Any]:
        """Get all candidates for a specific entity (artist/album)."""
        from soulspot.domain.entities import EnrichmentCandidate, EnrichmentEntityType

        from .models import EnrichmentCandidateModel

        stmt = (
            select(EnrichmentCandidateModel)
            .where(
                EnrichmentCandidateModel.entity_type == entity_type,
                EnrichmentCandidateModel.entity_id == entity_id,
            )
            .order_by(EnrichmentCandidateModel.confidence_score.desc())
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            EnrichmentCandidate(
                id=model.id,
                entity_type=EnrichmentEntityType(model.entity_type),
                entity_id=model.entity_id,
                spotify_uri=model.spotify_uri,
                spotify_name=model.spotify_name,
                spotify_image_url=model.spotify_image_url,
                confidence_score=model.confidence_score,
                is_selected=model.is_selected,
                is_rejected=model.is_rejected,
                extra_info=model.extra_info,
                created_at=ensure_utc_aware(model.created_at),
                updated_at=ensure_utc_aware(model.updated_at),
            )
            for model in models
        ]

    async def get_pending_for_entity(
        self, entity_type: str, entity_id: str
    ) -> list[Any]:
        """Get unreviewed candidates for an entity (not selected/rejected)."""
        from soulspot.domain.entities import EnrichmentCandidate, EnrichmentEntityType

        from .models import EnrichmentCandidateModel

        stmt = (
            select(EnrichmentCandidateModel)
            .where(
                EnrichmentCandidateModel.entity_type == entity_type,
                EnrichmentCandidateModel.entity_id == entity_id,
                EnrichmentCandidateModel.is_selected == False,  # noqa: E712
                EnrichmentCandidateModel.is_rejected == False,  # noqa: E712
            )
            .order_by(EnrichmentCandidateModel.confidence_score.desc())
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            EnrichmentCandidate(
                id=model.id,
                entity_type=EnrichmentEntityType(model.entity_type),
                entity_id=model.entity_id,
                spotify_uri=model.spotify_uri,
                spotify_name=model.spotify_name,
                spotify_image_url=model.spotify_image_url,
                confidence_score=model.confidence_score,
                is_selected=model.is_selected,
                is_rejected=model.is_rejected,
                extra_info=model.extra_info,
                created_at=ensure_utc_aware(model.created_at),
                updated_at=ensure_utc_aware(model.updated_at),
            )
            for model in models
        ]

    async def get_pending_count(self) -> int:
        """Get count of candidates awaiting review."""
        from .models import EnrichmentCandidateModel

        stmt = select(func.count(EnrichmentCandidateModel.id)).where(
            EnrichmentCandidateModel.is_selected == False,  # noqa: E712
            EnrichmentCandidateModel.is_rejected == False,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def count_pending(self, entity_type: str | None = None) -> int:
        """Count pending candidates (optionally filtered by entity type).

        Hey future me - this is used by enrichment status endpoint.
        Counts candidates that haven't been selected or rejected yet.

        Args:
            entity_type: Optional filter by 'artist' or 'album'

        Returns:
            Count of pending candidates
        """
        from .models import EnrichmentCandidateModel

        stmt = select(func.count(EnrichmentCandidateModel.id)).where(
            EnrichmentCandidateModel.is_selected == False,  # noqa: E712
            EnrichmentCandidateModel.is_rejected == False,  # noqa: E712
        )

        if entity_type:
            stmt = stmt.where(EnrichmentCandidateModel.entity_type == entity_type)

        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def list_pending(
        self,
        entity_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Any]:
        """List pending candidates with pagination.

        Hey future me - returns candidates awaiting user review.
        Sorted by confidence score (highest first).

        Args:
            entity_type: Optional filter by 'artist' or 'album'
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of EnrichmentCandidate domain entities
        """
        from soulspot.domain.entities import EnrichmentCandidate, EnrichmentEntityType

        from .models import EnrichmentCandidateModel

        stmt = (
            select(EnrichmentCandidateModel)
            .where(
                EnrichmentCandidateModel.is_selected == False,  # noqa: E712
                EnrichmentCandidateModel.is_rejected == False,  # noqa: E712
            )
            .order_by(EnrichmentCandidateModel.confidence_score.desc())
            .limit(limit)
            .offset(offset)
        )

        if entity_type:
            stmt = stmt.where(EnrichmentCandidateModel.entity_type == entity_type)

        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            EnrichmentCandidate(
                id=model.id,
                entity_type=EnrichmentEntityType(model.entity_type),
                entity_id=model.entity_id,
                spotify_uri=model.spotify_uri,
                spotify_name=model.spotify_name,
                spotify_image_url=model.spotify_image_url,
                confidence_score=model.confidence_score,
                is_selected=model.is_selected,
                is_rejected=model.is_rejected,
                extra_info=model.extra_info,
                created_at=ensure_utc_aware(model.created_at),
                updated_at=ensure_utc_aware(model.updated_at),
            )
            for model in models
        ]

    async def update(self, candidate: Any) -> None:
        """Update an existing candidate."""
        from .models import EnrichmentCandidateModel

        stmt = select(EnrichmentCandidateModel).where(
            EnrichmentCandidateModel.id == candidate.id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException("EnrichmentCandidate", candidate.id)

        model.is_selected = candidate.is_selected
        model.is_rejected = candidate.is_rejected
        model.confidence_score = candidate.confidence_score
        model.extra_info = candidate.extra_info
        model.updated_at = candidate.updated_at

    async def delete(self, candidate_id: str) -> None:
        """Delete a candidate by ID."""
        from .models import EnrichmentCandidateModel

        stmt = delete(EnrichmentCandidateModel).where(
            EnrichmentCandidateModel.id == candidate_id
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise EntityNotFoundException("EnrichmentCandidate", candidate_id)

    async def delete_for_entity(self, entity_type: str, entity_id: str) -> int:
        """Delete all candidates for an entity. Returns count deleted."""
        from .models import EnrichmentCandidateModel

        stmt = delete(EnrichmentCandidateModel).where(
            EnrichmentCandidateModel.entity_type == entity_type,
            EnrichmentCandidateModel.entity_id == entity_id,
        )
        result = await self.session.execute(stmt)
        return result.rowcount  # type: ignore[attr-defined, no-any-return]

    async def mark_selected(self, candidate_id: str) -> Any:
        """Mark a candidate as selected (and reject others for same entity).
        
        Hey future me - this does TWO things atomically:
        1. Marks the chosen candidate as selected
        2. Rejects all other candidates for the same entity
        
        Returns:
            The selected EnrichmentCandidate domain entity
        """
        from soulspot.domain.entities import EnrichmentCandidate, EnrichmentEntityType

        from .models import EnrichmentCandidateModel

        # First, get the candidate to find entity info
        stmt = select(EnrichmentCandidateModel).where(
            EnrichmentCandidateModel.id == candidate_id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException("EnrichmentCandidate", candidate_id)

        # Reject all other candidates for same entity
        reject_stmt = (
            update(EnrichmentCandidateModel)
            .where(
                EnrichmentCandidateModel.entity_type == model.entity_type,
                EnrichmentCandidateModel.entity_id == model.entity_id,
                EnrichmentCandidateModel.id != candidate_id,
            )
            .values(is_rejected=True, updated_at=datetime.now(UTC))
        )
        await self.session.execute(reject_stmt)

        # Mark this candidate as selected
        model.is_selected = True
        model.is_rejected = False
        model.updated_at = datetime.now(UTC)

        # Return domain entity
        return EnrichmentCandidate(
            id=model.id,
            entity_type=EnrichmentEntityType(model.entity_type),
            entity_id=model.entity_id,
            spotify_uri=model.spotify_uri,
            spotify_name=model.spotify_name,
            spotify_image_url=model.spotify_image_url,
            confidence_score=model.confidence_score,
            is_selected=model.is_selected,
            is_rejected=model.is_rejected,
            extra_info=model.extra_info,
            created_at=ensure_utc_aware(model.created_at),
            updated_at=ensure_utc_aware(model.updated_at),
        )

    async def mark_rejected(self, candidate_id: str) -> Any:
        """Mark a candidate as rejected.
        
        Hey future me - marks candidate as rejected (user dismissed this match).
        
        Returns:
            The rejected EnrichmentCandidate domain entity
        """
        from soulspot.domain.entities import EnrichmentCandidate, EnrichmentEntityType

        from .models import EnrichmentCandidateModel

        # Get the candidate first
        stmt = select(EnrichmentCandidateModel).where(
            EnrichmentCandidateModel.id == candidate_id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException("EnrichmentCandidate", candidate_id)

        # Mark as rejected
        model.is_rejected = True
        model.updated_at = datetime.now(UTC)

        # Return domain entity
        return EnrichmentCandidate(
            id=model.id,
            entity_type=EnrichmentEntityType(model.entity_type),
            entity_id=model.entity_id,
            spotify_uri=model.spotify_uri,
            spotify_name=model.spotify_name,
            spotify_image_url=model.spotify_image_url,
            confidence_score=model.confidence_score,
            is_selected=model.is_selected,
            is_rejected=model.is_rejected,
            extra_info=model.extra_info,
            created_at=ensure_utc_aware(model.created_at),
            updated_at=ensure_utc_aware(model.updated_at),
        )


# =============================================================================
# DUPLICATE CANDIDATE REPOSITORY
# =============================================================================
# Hey future me - DuplicateCandidateRepository stores potential duplicate track pairs!
# DuplicateDetectorWorker finds tracks that might be duplicates and stores them here.
# User reviews in UI and decides: keep one, keep both, or merge metadata.
# =============================================================================


class DuplicateCandidateRepository:
    """SQLAlchemy implementation of Duplicate Candidate repository.

    Manages potential duplicate track pairs found by DuplicateDetectorWorker.
    Users review candidates in UI and decide resolution action.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    async def add(self, candidate: Any) -> None:
        """Add a new duplicate candidate."""
        from soulspot.domain.entities import DuplicateCandidate

        from .models import DuplicateCandidateModel

        model = DuplicateCandidateModel(
            id=candidate.id,
            track_id_1=candidate.track_id_1,
            track_id_2=candidate.track_id_2,
            similarity_score=candidate.similarity_score,
            match_type=candidate.match_type.value,
            status=candidate.status.value,
            match_details=candidate.match_details,
            resolution_action=(
                candidate.resolution_action.value
                if candidate.resolution_action
                else None
            ),
            created_at=candidate.created_at,
            reviewed_at=candidate.reviewed_at,
        )
        self.session.add(model)

    async def get_by_id(self, candidate_id: str) -> Any | None:
        """Get a duplicate candidate by ID."""
        from soulspot.domain.entities import (
            DuplicateCandidate,
            DuplicateCandidateStatus,
            DuplicateMatchType,
            DuplicateResolutionAction,
        )

        from .models import DuplicateCandidateModel

        stmt = select(DuplicateCandidateModel).where(
            DuplicateCandidateModel.id == candidate_id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return DuplicateCandidate(
            id=model.id,
            track_id_1=model.track_id_1,
            track_id_2=model.track_id_2,
            similarity_score=model.similarity_score,
            match_type=DuplicateMatchType(model.match_type),
            status=DuplicateCandidateStatus(model.status),
            match_details=model.match_details,
            resolution_action=(
                DuplicateResolutionAction(model.resolution_action)
                if model.resolution_action
                else None
            ),
            created_at=ensure_utc_aware(model.created_at),
            reviewed_at=(
                ensure_utc_aware(model.reviewed_at) if model.reviewed_at else None
            ),
        )

    async def exists(self, track_id_1: str, track_id_2: str) -> bool:
        """Check if a duplicate pair already exists (in either order)."""
        from .models import DuplicateCandidateModel

        # Ensure track_id_1 < track_id_2 for consistent lookups
        id1, id2 = (track_id_1, track_id_2) if track_id_1 < track_id_2 else (track_id_2, track_id_1)

        stmt = select(func.count(DuplicateCandidateModel.id)).where(
            DuplicateCandidateModel.track_id_1 == id1,
            DuplicateCandidateModel.track_id_2 == id2,
        )
        result = await self.session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def list_pending(self, limit: int = 100) -> list[Any]:
        """List pending duplicate candidates for review."""
        return await self.list_by_status("pending", limit)

    async def list_by_status(self, status: str, limit: int = 100) -> list[Any]:
        """List candidates by status."""
        from soulspot.domain.entities import (
            DuplicateCandidate,
            DuplicateCandidateStatus,
            DuplicateMatchType,
            DuplicateResolutionAction,
        )

        from .models import DuplicateCandidateModel

        stmt = (
            select(DuplicateCandidateModel)
            .where(DuplicateCandidateModel.status == status)
            .order_by(DuplicateCandidateModel.similarity_score.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            DuplicateCandidate(
                id=model.id,
                track_id_1=model.track_id_1,
                track_id_2=model.track_id_2,
                similarity_score=model.similarity_score,
                match_type=DuplicateMatchType(model.match_type),
                status=DuplicateCandidateStatus(model.status),
                match_details=model.match_details,
                resolution_action=(
                    DuplicateResolutionAction(model.resolution_action)
                    if model.resolution_action
                    else None
                ),
                created_at=ensure_utc_aware(model.created_at),
                reviewed_at=(
                    ensure_utc_aware(model.reviewed_at) if model.reviewed_at else None
                ),
            )
            for model in models
        ]

    async def count_by_status(self) -> dict[str, int]:
        """Get count of candidates per status."""
        from .models import DuplicateCandidateModel

        stmt = select(
            DuplicateCandidateModel.status,
            func.count(DuplicateCandidateModel.id),
        ).group_by(DuplicateCandidateModel.status)
        result = await self.session.execute(stmt)
        rows = result.all()

        counts = {"pending": 0, "confirmed": 0, "dismissed": 0, "auto_resolved": 0}
        for status, count in rows:
            counts[status] = count
        return counts

    async def update(self, candidate: Any) -> None:
        """Update an existing candidate."""
        from .models import DuplicateCandidateModel

        stmt = select(DuplicateCandidateModel).where(
            DuplicateCandidateModel.id == candidate.id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise EntityNotFoundException("DuplicateCandidate", candidate.id)

        model.status = candidate.status.value
        model.resolution_action = (
            candidate.resolution_action.value if candidate.resolution_action else None
        )
        model.reviewed_at = candidate.reviewed_at

    async def delete(self, candidate_id: str) -> None:
        """Delete a candidate by ID."""
        from .models import DuplicateCandidateModel

        stmt = delete(DuplicateCandidateModel).where(
            DuplicateCandidateModel.id == candidate_id
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise EntityNotFoundException("DuplicateCandidate", candidate_id)

    async def confirm(self, candidate_id: str) -> None:
        """Mark candidate as confirmed duplicate."""
        from .models import DuplicateCandidateModel

        stmt = (
            update(DuplicateCandidateModel)
            .where(DuplicateCandidateModel.id == candidate_id)
            .values(status="confirmed", reviewed_at=datetime.now(UTC))
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise EntityNotFoundException("DuplicateCandidate", candidate_id)

    async def dismiss(self, candidate_id: str) -> None:
        """Mark candidate as dismissed (not a duplicate)."""
        from .models import DuplicateCandidateModel

        stmt = (
            update(DuplicateCandidateModel)
            .where(DuplicateCandidateModel.id == candidate_id)
            .values(status="dismissed", reviewed_at=datetime.now(UTC))
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise EntityNotFoundException("DuplicateCandidate", candidate_id)

    async def resolve(self, candidate_id: str, action: str) -> None:
        """Resolve a duplicate with specific action (keep_first, keep_second, etc.)."""
        from .models import DuplicateCandidateModel

        stmt = (
            update(DuplicateCandidateModel)
            .where(DuplicateCandidateModel.id == candidate_id)
            .values(
                status="confirmed",
                resolution_action=action,
                reviewed_at=datetime.now(UTC),
            )
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise EntityNotFoundException("DuplicateCandidate", candidate_id)


# Hey future me, SessionRepository is THE fix for the Docker restart auth bug! It persists
# sessions to SQLite instead of keeping them in-memory. Each method maps Session dataclass
# (application layer) to SpotifySessionModel (ORM). The get() method refreshes last_accessed_at on
# EVERY read to implement sliding session expiration - sessions stay alive while used!
# The cleanup_expired() is CRITICAL for housekeeping - run it periodically (e.g., every 5 min)
# or the sessions table grows forever. Returns count of deleted sessions for monitoring.
class SessionRepository(ISessionRepository):
    """Repository for session persistence.

    Handles database operations for user sessions, enabling persistence
    across application restarts. Sessions are automatically refreshed on access.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    # Yo, create() inserts a new session into DB. We use the session_id from the Session dataclass
    # as the primary key. The commit happens in the calling code (usually the auth endpoint), not here!
    # This is staged INSERT - if something fails before commit, the DB rolls back and session is lost.
    # That's GOOD - we don't want orphaned sessions from failed requests cluttering the DB.
    async def create(self, session_data: Session) -> None:
        """Create a new session in database.

        Args:
            session_data: Session dataclass to persist
        """

        model = SpotifySessionModel(
            session_id=session_data.session_id,
            access_token=session_data.access_token,
            refresh_token=session_data.refresh_token,
            token_expires_at=session_data.token_expires_at,
            oauth_state=session_data.oauth_state,
            code_verifier=session_data.code_verifier,
            created_at=session_data.created_at,
            last_accessed_at=session_data.last_accessed_at,
        )
        self.session.add(model)

    # Listen up, get() fetches session AND updates last_accessed_at in ONE transaction! This implements
    # "sliding expiration" - sessions stay alive as long as they're used. The NOW() is server-side SQL
    # function (not Python datetime) to avoid clock skew issues. If session_id doesn't exist, returns None.
    # scalar_one_or_none() is safe - returns exactly one row or None, never raises if missing.
    async def get(self, session_id: str) -> Session | None:
        """Get session by ID and update last accessed time.

        Args:
            session_id: Session identifier

        Returns:
            Session dataclass or None if not found
        """

        # Get the session
        stmt = select(SpotifySessionModel).where(SpotifySessionModel.session_id == session_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Update last_accessed_at (sliding expiration)

        model.last_accessed_at = datetime.now(UTC)

        # Convert to dataclass
        return Session(
            session_id=model.session_id,
            access_token=model.access_token,
            refresh_token=model.refresh_token,
            token_expires_at=model.token_expires_at,
            oauth_state=model.oauth_state,
            code_verifier=model.code_verifier,
            created_at=model.created_at,
            last_accessed_at=model.last_accessed_at,
        )

    # Hey, update() modifies an existing session. We don't pass the whole Session object, just the fields
    # to change via **kwargs. This is flexible but RISKY - no validation that field names are correct!
    # If you typo "access_tokenn", it silently does nothing (hasattr check fails). The refresh of
    # last_accessed_at keeps session alive. If session_id doesn't exist, returns None (not an error).
    async def update(self, session_id: str, **kwargs: Any) -> Session | None:
        """Update session fields.

        Args:
            session_id: Session identifier
            **kwargs: Fields to update

        Returns:
            Updated session or None if not found
        """

        stmt = select(SpotifySessionModel).where(SpotifySessionModel.session_id == session_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Update fields
        for key, value in kwargs.items():
            if hasattr(model, key):
                setattr(model, key, value)

        # Update last_accessed_at

        model.last_accessed_at = datetime.now(UTC)

        # Convert to dataclass
        return Session(
            session_id=model.session_id,
            access_token=model.access_token,
            refresh_token=model.refresh_token,
            token_expires_at=model.token_expires_at,
            oauth_state=model.oauth_state,
            code_verifier=model.code_verifier,
            created_at=model.created_at,
            last_accessed_at=model.last_accessed_at,
        )

    # Yo, delete() removes session from DB. Returns True if found+deleted, False if not found. This is
    # idempotent - safe to call multiple times. The rowcount check tells us if DELETE actually removed
    # a row or not. No exception if session doesn't exist - that's intentional (logout should succeed
    # even if session is already gone). The commit happens in calling code!
    async def delete(self, session_id: str) -> bool:
        """Delete session from database.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        stmt = delete(SpotifySessionModel).where(SpotifySessionModel.session_id == session_id)
        result = await self.session.execute(stmt)
        rowcount = cast(int, result.rowcount)  # type: ignore[attr-defined]
        return bool(rowcount > 0)

    # Listen future me, cleanup_expired() is ESSENTIAL maintenance! It deletes sessions older than
    # timeout_seconds (default 3600 = 1 hour). The WHERE clause compares last_accessed_at + timeout
    # to NOW() - pure SQL, no Python loops! This scales to millions of sessions. Returns count for
    # monitoring (if count is huge, timeout might be too short or cleanup isn't running often enough).
    # Run this in a background task every 5-10 minutes to prevent table bloat. If you forget to run
    # cleanup, sessions table grows forever = disk full = app crash! Set up alerts if cleanup fails.
    async def cleanup_expired(self, timeout_seconds: int = 3600) -> int:
        """Delete expired sessions from database.

        Args:
            timeout_seconds: Session timeout in seconds

        Returns:
            Number of sessions deleted
        """
        cutoff_time = datetime.now(UTC) - timedelta(seconds=timeout_seconds)
        stmt = delete(SpotifySessionModel).where(SpotifySessionModel.last_accessed_at < cutoff_time)
        result = await self.session.execute(stmt)
        rowcount = cast(int, result.rowcount)  # type: ignore[attr-defined]
        return int(rowcount or 0)

    # Hey, get_by_oauth_state() is for OAuth callback verification. We need to find which session
    # corresponds to the state parameter Spotify sends back. This is a LINEAR SEARCH (SELECT with WHERE)
    # but it's fine because state is unique per session and we only do this once per auth flow. If you
    # have millions of sessions and this gets slow, add an index on oauth_state column. Returns None
    # if no session has that state (probably a replay attack or expired state - reject it!).
    async def get_by_oauth_state(self, state: str) -> Session | None:
        """Get session by OAuth state parameter.

        Args:
            state: OAuth state value

        Returns:
            Session dataclass or None if not found
        """

        stmt = select(SpotifySessionModel).where(SpotifySessionModel.oauth_state == state)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Update last_accessed_at

        model.last_accessed_at = datetime.now(UTC)

        # Convert to dataclass
        return Session(
            session_id=model.session_id,
            access_token=model.access_token,
            refresh_token=model.refresh_token,
            token_expires_at=model.token_expires_at,
            oauth_state=model.oauth_state,
            code_verifier=model.code_verifier,
            created_at=model.created_at,
            last_accessed_at=model.last_accessed_at,
        )


# Hey future me - DeezerSessionRepository ist das Pendant zu SessionRepository für Deezer!
# Hauptunterschiede:
# - Kein refresh_token (Deezer Tokens sind langlebig ~90 Tage)
# - Kein code_verifier (Deezer nutzt kein PKCE)
# - Hat deezer_user_id/deezer_username für User-Info
# Die Session-ID ist DIESELBE wie bei Spotify (aus dem Browser Cookie)!
class DeezerSessionRepository:
    """Repository for Deezer session persistence.

    Similar to SessionRepository (Spotify) but:
    - No refresh_token (Deezer tokens are long-lived)
    - No code_verifier (Deezer doesn't use PKCE)
    - Has Deezer-specific user info (user_id, username)
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def create(self, session_id: str, access_token: str | None = None,
                     deezer_user_id: str | None = None, 
                     deezer_username: str | None = None,
                     oauth_state: str | None = None) -> DeezerSessionModel:
        """Create a new Deezer session.

        Args:
            session_id: Browser session ID (same as Spotify session_id)
            access_token: Deezer access token (if authenticated)
            deezer_user_id: Deezer user ID
            deezer_username: Deezer username
            oauth_state: OAuth state for CSRF protection

        Returns:
            Created DeezerSessionModel
        """
        model = DeezerSessionModel(
            session_id=session_id,
            access_token=access_token,
            deezer_user_id=deezer_user_id,
            deezer_username=deezer_username,
            oauth_state=oauth_state,
            created_at=datetime.now(UTC),
            last_accessed_at=datetime.now(UTC),
        )
        self.session.add(model)
        return model

    async def get(self, session_id: str) -> DeezerSessionModel | None:
        """Get Deezer session by ID and update last accessed time.

        Args:
            session_id: Session identifier

        Returns:
            DeezerSessionModel or None if not found
        """
        stmt = select(DeezerSessionModel).where(
            DeezerSessionModel.session_id == session_id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Update last_accessed_at (sliding expiration)
        model.last_accessed_at = datetime.now(UTC)
        return model

    async def get_all_active(self) -> list[DeezerSessionModel]:
        """Get all Deezer sessions with valid access tokens.

        Hey future me - this is for background workers that need to sync
        user data across all authenticated users. Returns only sessions
        that have an access_token set.

        Returns:
            List of DeezerSessionModel with tokens
        """
        stmt = select(DeezerSessionModel).where(
            DeezerSessionModel.access_token.isnot(None)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, session_id: str, **kwargs: Any) -> DeezerSessionModel | None:
        """Update Deezer session fields.

        Args:
            session_id: Session identifier
            **kwargs: Fields to update (access_token, deezer_user_id, etc.)

        Returns:
            Updated model or None if not found
        """
        stmt = select(DeezerSessionModel).where(
            DeezerSessionModel.session_id == session_id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        for key, value in kwargs.items():
            if hasattr(model, key):
                setattr(model, key, value)

        model.last_accessed_at = datetime.now(UTC)
        return model

    async def delete(self, session_id: str) -> bool:
        """Delete Deezer session from database.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        stmt = delete(DeezerSessionModel).where(
            DeezerSessionModel.session_id == session_id
        )
        result = await self.session.execute(stmt)
        rowcount = cast(int, result.rowcount)
        return bool(rowcount > 0)

    async def cleanup_expired(self, timeout_days: int = 90) -> int:
        """Delete expired Deezer sessions.

        Hey future me - Deezer tokens are LONG-LIVED (~90 days), so we use
        days instead of seconds for timeout. Default: 90 days.

        Args:
            timeout_days: Session timeout in days

        Returns:
            Number of sessions deleted
        """
        cutoff_time = datetime.now(UTC) - timedelta(days=timeout_days)
        stmt = delete(DeezerSessionModel).where(
            DeezerSessionModel.last_accessed_at < cutoff_time
        )
        result = await self.session.execute(stmt)
        rowcount = cast(int, result.rowcount)
        return int(rowcount or 0)

    async def get_by_oauth_state(self, state: str) -> DeezerSessionModel | None:
        """Get Deezer session by OAuth state parameter.

        Used during OAuth callback to find the session that initiated auth.

        Args:
            state: OAuth state value

        Returns:
            DeezerSessionModel or None if not found
        """
        stmt = select(DeezerSessionModel).where(
            DeezerSessionModel.oauth_state == state
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            model.last_accessed_at = datetime.now(UTC)
        return model


# =============================================================================
# PROVIDER BROWSE REPOSITORY
# =============================================================================
# Hey future me - this repository handles synced provider data (artists, albums, 
# tracks from Spotify, Deezer, Tidal, etc.).
# The sync flow: Provider API → ProviderBrowseRepository → DB. The browse flow:
# DB → ProviderBrowseRepository → UI. Auto-sync with diff logic on page load.
# =============================================================================


class ProviderBrowseRepository:
    """Repository for provider browse data (followed artists, albums, tracks).

    Hey future me - Nach Table Consolidation (Nov 2025):
    - Nutzt die unified Models: ArtistModel, AlbumModel, TrackModel
    - KEINE separaten provider_* Tabellen mehr!
    - Filter nach source='spotify'/'deezer'/'tidal' für provider-spezifische Daten
    - spotify_uri/deezer_uri enthält die Provider-IDs (z.B. "spotify:artist:xxx")
    
    Renamed from SpotifyBrowseRepository → ProviderBrowseRepository (Nov 2025)
    Alias SpotifyBrowseRepository = ProviderBrowseRepository für Rückwärtskompatibilität
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with session."""
        self.session = session

    # =========================================================================
    # ARTISTS (unified ArtistModel with source='spotify')
    # =========================================================================

    async def get_all_artist_ids(self) -> set[str]:
        """Get all Spotify artist IDs in the database.

        Used for diff-sync: compare with Spotify API result to find
        new follows and unfollows.
        
        Returns Spotify IDs extracted from spotify_uri.
        """
        from .models import ArtistModel

        stmt = select(ArtistModel.spotify_uri).where(
            ArtistModel.source == "spotify",
            ArtistModel.spotify_uri.isnot(None),
        )
        result = await self.session.execute(stmt)
        # Extract Spotify ID from URI: "spotify:artist:xxx" -> "xxx"
        return {row[0].split(":")[-1] for row in result.all() if row[0]}

    async def get_artist_by_id(self, spotify_id: str) -> Any | None:
        """Get a Spotify artist by ID."""
        from .models import ArtistModel

        spotify_uri = f"spotify:artist:{spotify_id}"
        stmt = select(ArtistModel).where(
            ArtistModel.spotify_uri == spotify_uri
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_artists(self, limit: int = 100, offset: int = 0) -> list[Any]:
        """Get all followed artists with pagination."""
        from .models import ArtistModel

        stmt = (
            select(ArtistModel)
            .where(ArtistModel.source == "spotify")
            .order_by(ArtistModel.name)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_artists(self) -> int:
        """Count total followed artists from Spotify."""
        from .models import ArtistModel

        stmt = select(func.count(ArtistModel.id)).where(
            ArtistModel.source == "spotify"
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_artists_pending_album_sync(self, limit: int = 5) -> list[Any]:
        """Get artists whose albums haven't been synced yet.

        Hey future me - this is for gradual background album sync!
        We find artists where albums_synced_at IS NULL (never synced).
        The limit parameter controls how many artists to sync per cycle
        to avoid API rate limits. Default 5 = ~5 API calls per cycle.

        Args:
            limit: Maximum number of artists to return (default 5)

        Returns:
            List of ArtistModel objects without synced albums
        """
        from .models import ArtistModel

        stmt = (
            select(ArtistModel)
            .where(
                ArtistModel.source == "spotify",
                ArtistModel.albums_synced_at.is_(None),
            )
            .order_by(ArtistModel.name)  # Alphabetical for predictability
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_artists_pending_album_sync(self) -> int:
        """Count artists whose albums haven't been synced yet.

        Useful for progress tracking in UI.

        Returns:
            Number of artists still needing album sync
        """
        from .models import ArtistModel

        stmt = select(func.count(ArtistModel.id)).where(
            ArtistModel.source == "spotify",
            ArtistModel.albums_synced_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_artists_due_for_resync(
        self, max_age_hours: int = 24, limit: int = 5
    ) -> list[Any]:
        """Get artists whose albums haven't been synced in a while.

        Hey future me - this is for the periodic resync feature!
        We find artists where albums_synced_at is NOT NULL but older than
        max_age_hours. This ensures we periodically refresh album data
        to catch new releases without requiring users to visit artist pages.

        Priority: Oldest synced first (so we cycle through all artists evenly).

        Args:
            max_age_hours: How many hours before resync is needed (default 24)
            limit: Maximum number of artists to return (default 5)

        Returns:
            List of ArtistModel objects needing album resync
        """
        from datetime import timedelta

        from .models import ArtistModel

        cutoff_time = datetime.now(UTC) - timedelta(hours=max_age_hours)

        stmt = (
            select(ArtistModel)
            .where(
                ArtistModel.source == "spotify",
                ArtistModel.albums_synced_at.isnot(None),
                ArtistModel.albums_synced_at < cutoff_time,
            )
            .order_by(ArtistModel.albums_synced_at.asc())  # Oldest first
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_artists_due_for_resync(self, max_age_hours: int = 24) -> int:
        """Count artists whose albums are due for resync.

        Args:
            max_age_hours: How many hours before resync is needed

        Returns:
            Number of artists needing album resync
        """
        from datetime import timedelta

        from .models import ArtistModel

        cutoff_time = datetime.now(UTC) - timedelta(hours=max_age_hours)

        stmt = select(func.count(ArtistModel.id)).where(
            ArtistModel.source == "spotify",
            ArtistModel.albums_synced_at.isnot(None),
            ArtistModel.albums_synced_at < cutoff_time,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def upsert_artist(
        self,
        spotify_id: str,
        name: str,
        image_url: str | None = None,
        image_path: str | None = None,
        genres: list[str] | None = None,
        popularity: int | None = None,
        follower_count: int | None = None,
    ) -> None:
        """Insert or update a Spotify artist in unified library.
        
        CRITICAL FIX (Dec 2025): Prevents duplicate artists by checking name first!
        - First checks for existing artist by spotify_uri
        - Then checks for existing artist by NAME (prevents Spotify/Deezer duplicates)
        - Only creates NEW artist if neither exists
        - Updates source to "hybrid" if artist exists from other provider
        """
        from .models import ArtistModel

        spotify_uri = f"spotify:artist:{spotify_id}"
        
        # STEP 1: Check if exists by spotify_uri
        stmt = select(ArtistModel).where(
            ArtistModel.spotify_uri == spotify_uri
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        # STEP 2: If not found by spotify_uri, check by NAME (prevent duplicates!)
        # CRITICAL FIX: Case-insensitive + whitespace normalization!
        if not model:
            normalized_name = name.strip().lower()
            stmt = select(ArtistModel).where(func.lower(func.trim(ArtistModel.name)) == normalized_name)
            result = await self.session.execute(stmt)
            # Use first() instead of scalar_one_or_none() to handle existing duplicates gracefully
            model = result.scalars().first()

        now = datetime.now(UTC)
        # Genres stored as JSON in unified model
        genres_json = json.dumps(genres) if genres else None

        if model:
            # Update existing artist - add spotify_uri if missing
            if not model.spotify_uri:
                model.spotify_uri = spotify_uri
            
            # Update source to "hybrid" if it was only from one provider before
            if model.source == "deezer":
                model.source = "hybrid"
            elif model.source == "local":
                model.source = "hybrid"
            # If already "spotify" or "hybrid", keep as is
            
            model.name = name
            model.artwork_url = image_url
            if image_path is not None:
                model.image_path = image_path
            model.genres = genres_json
            model.popularity = popularity
            model.follower_count = follower_count
            model.last_synced_at = now
            model.updated_at = now
        else:
            # Insert new with source='spotify'
            model = ArtistModel(
                name=name,
                spotify_uri=spotify_uri,
                image_url=image_url,
                image_path=image_path,
                genres=genres_json,
                popularity=popularity,
                follower_count=follower_count,
                source="spotify",
                last_synced_at=now,
            )
            self.session.add(model)

    async def delete_artists(self, spotify_ids: set[str]) -> int:
        """Delete artists by Spotify IDs (CASCADE deletes albums and tracks)."""
        from .models import ArtistModel

        if not spotify_ids:
            return 0

        # Convert IDs to URIs for matching
        spotify_uris = {f"spotify:artist:{sid}" for sid in spotify_ids}

        stmt = delete(ArtistModel).where(
            ArtistModel.spotify_uri.in_(spotify_uris)
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0  # type: ignore[attr-defined]

    # =========================================================================
    # ALBUMS (unified AlbumModel with source='spotify')
    # =========================================================================

    async def get_albums_by_artist(
        self, artist_id: str, limit: int = 100, offset: int = 0
    ) -> list[Any]:
        """Get albums for a Spotify artist.
        
        Hey future me - artist_id here is SPOTIFY ID (from API), not UUID!
        We need to look up the artist by spotify_uri first.
        """
        from .models import AlbumModel, ArtistModel

        # Find artist by Spotify ID to get internal ID
        spotify_uri = f"spotify:artist:{artist_id}"
        artist_stmt = select(ArtistModel.id).where(ArtistModel.spotify_uri == spotify_uri)
        artist_result = await self.session.execute(artist_stmt)
        internal_artist_id = artist_result.scalar_one_or_none()
        
        if not internal_artist_id:
            return []

        stmt = (
            select(AlbumModel)
            .where(
                AlbumModel.artist_id == internal_artist_id,
                AlbumModel.source == "spotify",
            )
            .order_by(AlbumModel.release_date.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_album_by_id(self, spotify_id: str) -> Any | None:
        """Get a Spotify album by ID."""
        from .models import AlbumModel

        spotify_uri = f"spotify:album:{spotify_id}"
        stmt = select(AlbumModel).where(
            AlbumModel.spotify_uri == spotify_uri
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_albums(self) -> int:
        """Count total saved albums from Spotify."""
        from .models import AlbumModel

        stmt = select(func.count(AlbumModel.id)).where(
            AlbumModel.source == "spotify"
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_latest_releases(
        self,
        limit: int = 20,
        album_types: list[str] | None = None,
    ) -> list[Any]:
        """Get the latest releases from followed artists sorted by release_date.

        Hey future me - this is for the Dashboard "New Releases" feature!
        Returns albums/singles sorted by release_date (newest first), mixed together.
        The join with ArtistModel gives us artist names without N+1 queries.

        release_date format can be:
        - "2024" (year only, release_date_precision="year")
        - "2024-05" (month, release_date_precision="month")
        - "2024-05-15" (full date, release_date_precision="day")

        SQLite sorts these strings correctly because ISO format is lexicographically
        sortable! "2024-05-15" > "2024-01-01" works as expected.

        Args:
            limit: Maximum number of releases to return (default 20)
            album_types: Filter by album type (default None = all types)
                         Options: "album", "single", "compilation"

        Returns:
            List of tuples: (AlbumModel, artist_name: str)
        """
        from .models import AlbumModel, ArtistModel

        stmt = (
            select(AlbumModel, ArtistModel.name)
            .join(
                ArtistModel,
                AlbumModel.artist_id == ArtistModel.id,
            )
            .where(
                AlbumModel.source == "spotify",
                AlbumModel.release_date.isnot(None),
            )
            .order_by(AlbumModel.release_date.desc())
            .limit(limit)
        )

        # Optionally filter by album type
        if album_types:
            stmt = stmt.where(AlbumModel.album_type.in_(album_types))

        result = await self.session.execute(stmt)
        return list(result.all())

    async def count_albums_by_artist(self, artist_id: str) -> int:
        """Count albums for an artist (by Spotify ID)."""
        from .models import AlbumModel, ArtistModel

        # Find artist by Spotify ID
        spotify_uri = f"spotify:artist:{artist_id}"
        artist_stmt = select(ArtistModel.id).where(ArtistModel.spotify_uri == spotify_uri)
        artist_result = await self.session.execute(artist_stmt)
        internal_artist_id = artist_result.scalar_one_or_none()
        
        if not internal_artist_id:
            return 0

        stmt = select(func.count(AlbumModel.id)).where(
            AlbumModel.artist_id == internal_artist_id,
            AlbumModel.source == "spotify",
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_new_albums_since(
        self, artist_id: str, since_date: datetime | None
    ) -> list[Any]:
        """Get albums for an artist released after a specific date.

        Hey future me - this is for the Watchlist/New Release feature!
        Instead of hitting Spotify API every time, we use the unified
        albums table. The Background Album Sync keeps this data fresh,
        so we just query locally.

        If since_date is None, returns all albums (first check scenario).

        Args:
            artist_id: Spotify artist ID (NOT internal UUID)
            since_date: Only return albums with created_at > since_date

        Returns:
            List of AlbumModel objects
        """
        from .models import AlbumModel, ArtistModel

        # Find artist by Spotify ID
        spotify_uri = f"spotify:artist:{artist_id}"
        artist_stmt = select(ArtistModel.id).where(ArtistModel.spotify_uri == spotify_uri)
        artist_result = await self.session.execute(artist_stmt)
        internal_artist_id = artist_result.scalar_one_or_none()
        
        if not internal_artist_id:
            return []

        if since_date is None:
            # First check - return all albums
            stmt = (
                select(AlbumModel)
                .where(
                    AlbumModel.artist_id == internal_artist_id,
                    AlbumModel.source == "spotify",
                )
                .order_by(AlbumModel.release_date.desc())
            )
        else:
            # Return only albums added to DB after since_date
            # Hey - we use created_at, not release_date, because:
            # 1. Album might have been released before we started tracking
            # 2. We want "new to us" not "new release date"
            stmt = (
                select(AlbumModel)
                .where(
                    AlbumModel.artist_id == internal_artist_id,
                    AlbumModel.source == "spotify",
                    AlbumModel.created_at > since_date,
                )
                .order_by(AlbumModel.release_date.desc())
            )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_artist_albums_sync_status(self, artist_id: str) -> dict[str, Any]:
        """Get sync status for an artist's albums.

        Returns info about whether albums are synced and how fresh the data is.
        Used by Watchlist/Discography workers to decide if they need fresh data.

        Args:
            artist_id: Spotify artist ID (NOT internal UUID)

        Returns:
            Dict with sync status info
        """
        from .models import ArtistModel

        spotify_uri = f"spotify:artist:{artist_id}"
        stmt = select(ArtistModel).where(
            ArtistModel.spotify_uri == spotify_uri
        )
        result = await self.session.execute(stmt)
        artist = result.scalar_one_or_none()

        if not artist:
            return {
                "artist_exists": False,
                "albums_synced": False,
                "albums_synced_at": None,
                "album_count": 0,
            }

        album_count = await self.count_albums_by_artist(artist_id)

        return {
            "artist_exists": True,
            "albums_synced": artist.albums_synced_at is not None,
            "albums_synced_at": artist.albums_synced_at,
            "album_count": album_count,
        }

    async def upsert_album(
        self,
        spotify_id: str,
        artist_id: str,
        name: str,
        image_url: str | None = None,
        image_path: str | None = None,
        release_date: str | None = None,
        release_date_precision: str | None = None,
        album_type: str = "album",
        total_tracks: int = 0,
        is_saved: bool = False,
    ) -> None:
        """Insert or update a Spotify album in unified library.
        
        Hey future me - artist_id here is SPOTIFY ID, not internal UUID!
        We need to look up the artist first.
        album_type param maps to primary_type field in AlbumModel!
        """
        from .models import AlbumModel, ArtistModel

        spotify_uri = f"spotify:album:{spotify_id}"
        artist_spotify_uri = f"spotify:artist:{artist_id}"
        
        # Find internal artist ID
        artist_stmt = select(ArtistModel.id).where(ArtistModel.spotify_uri == artist_spotify_uri)
        artist_result = await self.session.execute(artist_stmt)
        internal_artist_id = artist_result.scalar_one_or_none()
        
        if not internal_artist_id:
            # Artist doesn't exist - skip this album
            return

        # Check if album exists
        stmt = select(AlbumModel).where(
            AlbumModel.spotify_uri == spotify_uri
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        now = datetime.now(UTC)

        if model:
            model.title = name
            model.artwork_url = image_url
            if image_path is not None:
                model.image_path = image_path
            model.release_date = release_date
            model.release_date_precision = release_date_precision
            model.primary_type = album_type  # album_type → primary_type
            model.total_tracks = total_tracks
            # Only set is_saved to True, never back to False via this method
            if is_saved:
                model.is_saved = True
            model.updated_at = now
        else:
            model = AlbumModel(
                title=name,
                artist_id=internal_artist_id,
                spotify_uri=spotify_uri,
                artwork_url=image_url,
                image_path=image_path,
                release_date=release_date,
                release_date_precision=release_date_precision,
                primary_type=album_type,  # album_type → primary_type
                total_tracks=total_tracks,
                is_saved=is_saved,
                source="spotify",
            )
            self.session.add(model)

    async def set_albums_synced(self, artist_id: str) -> None:
        """Mark albums as synced for an artist (by Spotify ID)."""
        from .models import ArtistModel

        spotify_uri = f"spotify:artist:{artist_id}"
        stmt = select(ArtistModel).where(
            ArtistModel.spotify_uri == spotify_uri
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            model.albums_synced_at = datetime.now(UTC)

    # =========================================================================
    # TRACKS (unified TrackModel with source='spotify')
    # =========================================================================

    async def get_tracks_by_album(
        self, album_id: str, limit: int = 100, offset: int = 0
    ) -> list[Any]:
        """Get tracks for a Spotify album (by Spotify album ID)."""
        from .models import AlbumModel, TrackModel

        # Find album by Spotify ID
        spotify_uri = f"spotify:album:{album_id}"
        album_stmt = select(AlbumModel.id).where(AlbumModel.spotify_uri == spotify_uri)
        album_result = await self.session.execute(album_stmt)
        internal_album_id = album_result.scalar_one_or_none()
        
        if not internal_album_id:
            return []

        stmt = (
            select(TrackModel)
            .where(
                TrackModel.album_id == internal_album_id,
                TrackModel.source == "spotify",
            )
            .order_by(TrackModel.disc_number, TrackModel.track_number)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_track_by_id(self, spotify_id: str) -> Any | None:
        """Get a Spotify track by ID."""
        from .models import TrackModel

        spotify_uri = f"spotify:track:{spotify_id}"
        stmt = select(TrackModel).where(
            TrackModel.spotify_uri == spotify_uri
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_tracks(self) -> int:
        """Count total tracks from Spotify (all albums)."""
        from .models import TrackModel

        stmt = select(func.count(TrackModel.id)).where(
            TrackModel.source == "spotify"
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def count_tracks_by_album(self, album_id: str) -> int:
        """Count tracks in an album (by Spotify album ID)."""
        from .models import AlbumModel, TrackModel

        # Find album by Spotify ID
        spotify_uri = f"spotify:album:{album_id}"
        album_stmt = select(AlbumModel.id).where(AlbumModel.spotify_uri == spotify_uri)
        album_result = await self.session.execute(album_stmt)
        internal_album_id = album_result.scalar_one_or_none()
        
        if not internal_album_id:
            return 0

        stmt = select(func.count(TrackModel.id)).where(
            TrackModel.album_id == internal_album_id,
            TrackModel.source == "spotify",
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def upsert_track(
        self,
        spotify_id: str,
        album_id: str,
        name: str,
        track_number: int = 1,
        disc_number: int = 1,
        duration_ms: int = 0,
        explicit: bool = False,
        preview_url: str | None = None,
        isrc: str | None = None,
    ) -> None:
        """Insert or update a Spotify track in unified library.
        
        Hey future me - album_id here is SPOTIFY ID, not internal UUID!
        """
        from .models import AlbumModel, TrackModel

        spotify_uri = f"spotify:track:{spotify_id}"
        album_spotify_uri = f"spotify:album:{album_id}"
        
        # Find internal album ID and artist_id
        album_stmt = select(AlbumModel.id, AlbumModel.artist_id).where(
            AlbumModel.spotify_uri == album_spotify_uri
        )
        album_result = await self.session.execute(album_stmt)
        album_row = album_result.one_or_none()
        
        if not album_row:
            # Album doesn't exist - skip this track
            return
        
        internal_album_id, artist_id = album_row

        # Check if track exists
        stmt = select(TrackModel).where(
            TrackModel.spotify_uri == spotify_uri
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        now = datetime.now(UTC)

        if model:
            model.title = name
            model.track_number = track_number
            model.disc_number = disc_number
            model.duration_ms = duration_ms
            model.explicit = explicit
            model.preview_url = preview_url
            model.isrc = isrc
            model.updated_at = now
        else:
            model = TrackModel(
                title=name,
                artist_id=artist_id,
                album_id=internal_album_id,
                spotify_uri=spotify_uri,
                track_number=track_number,
                disc_number=disc_number,
                duration_ms=duration_ms,
                explicit=explicit,
                preview_url=preview_url,
                isrc=isrc,
                source="spotify",
            )
            self.session.add(model)

    async def set_tracks_synced(self, album_id: str) -> None:
        """Mark tracks as synced for an album (by Spotify album ID)."""
        from .models import AlbumModel

        spotify_uri = f"spotify:album:{album_id}"
        stmt = select(AlbumModel).where(AlbumModel.spotify_uri == spotify_uri)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            model.tracks_synced_at = datetime.now(UTC)

    async def link_track_to_local(
        self, spotify_track_id: str, local_track_id: str
    ) -> None:
        """Link a Spotify track to a local library track after download.
        
        Hey future me - nach Table Consolidation sind Spotify tracks und local tracks
        in derselben Tabelle! Diese Methode ist jetzt deprecated.
        Stattdessen: Track mit source='spotify' zu source='hybrid' ändern.
        """
        from .models import TrackModel

        spotify_uri = f"spotify:track:{spotify_track_id}"
        stmt = select(TrackModel).where(
            TrackModel.spotify_uri == spotify_uri
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            # Mark as hybrid (both streaming and local)
            model.source = "hybrid"
            model.updated_at = datetime.now(UTC)

    # =========================================================================
    # SYNC STATUS
    # =========================================================================

    async def get_sync_status(self, sync_type: str) -> Any | None:
        """Get sync status for a type."""
        from .models import SpotifySyncStatusModel

        stmt = select(SpotifySyncStatusModel).where(
            SpotifySyncStatusModel.sync_type == sync_type
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_sync_status(
        self,
        sync_type: str,
        status: str = "idle",
        items_synced: int = 0,
        items_added: int = 0,
        items_removed: int = 0,
        error_message: str | None = None,
        cooldown_minutes: int = 5,
    ) -> None:
        """Update or create sync status."""
        import uuid

        from .models import SpotifySyncStatusModel

        stmt = select(SpotifySyncStatusModel).where(
            SpotifySyncStatusModel.sync_type == sync_type
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        now = datetime.now(UTC)
        next_sync = now + timedelta(minutes=cooldown_minutes)

        if model:
            model.status = status
            model.last_sync_at = now
            model.next_sync_at = next_sync
            model.items_synced = items_synced
            model.items_added = items_added
            model.items_removed = items_removed
            model.error_message = error_message
            model.updated_at = now
        else:
            model = SpotifySyncStatusModel(
                id=str(uuid.uuid4()),
                sync_type=sync_type,
                status=status,
                last_sync_at=now,
                next_sync_at=next_sync,
                items_synced=items_synced,
                items_added=items_added,
                items_removed=items_removed,
                error_message=error_message,
            )
            self.session.add(model)

    async def should_sync(self, sync_type: str) -> bool:
        """Check if sync is due based on cooldown.

        Hey future me - use ensure_utc_aware() because SQLite returns naive datetimes!
        """
        status = await self.get_sync_status(sync_type)
        if not status:
            return True  # Never synced
        if status.status == "running":
            return False  # Already running
        if not status.next_sync_at:
            return True
        return bool(datetime.now(UTC) >= ensure_utc_aware(status.next_sync_at))

    # =========================================================================
    # PLAYLISTS (SPOTIFY-SYNCED)
    # =========================================================================
    # Hey future me - playlists are in the playlists table (not spotify_* prefix)!
    # We identify Spotify playlists by source='SPOTIFY' and spotify_uri NOT NULL.
    # =========================================================================

    async def get_spotify_playlist_uris(self) -> set[str]:
        """Get all Spotify playlist URIs in the database.

        Used for diff-sync: compare with Spotify API result.
        """
        from .models import PlaylistModel

        stmt = select(PlaylistModel.spotify_uri).where(
            PlaylistModel.source == "SPOTIFY",
            PlaylistModel.spotify_uri.isnot(None),
            PlaylistModel.is_liked_songs == False,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        return {row[0] for row in result.all() if row[0]}

    async def get_playlist_by_uri(self, spotify_uri: str) -> Any | None:
        """Get a playlist by Spotify URI."""
        from .models import PlaylistModel

        stmt = select(PlaylistModel).where(PlaylistModel.spotify_uri == spotify_uri)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_spotify_playlists(self) -> int:
        """Count Spotify-synced playlists (excluding Liked Songs)."""
        from .models import PlaylistModel

        stmt = select(func.count(PlaylistModel.id)).where(
            PlaylistModel.source == "SPOTIFY",
            PlaylistModel.is_liked_songs == False,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def upsert_playlist(
        self,
        spotify_uri: str,
        name: str,
        description: str | None = None,
        cover_url: str | None = None,
        cover_path: str | None = None,
        source: str = "SPOTIFY",
    ) -> None:
        """Insert or update a Spotify playlist."""
        import uuid

        from .models import PlaylistModel

        stmt = select(PlaylistModel).where(PlaylistModel.spotify_uri == spotify_uri)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        now = datetime.now(UTC)

        if model:
            model.name = name
            model.description = description
            model.artwork_url = cover_url
            if cover_path is not None:
                model.cover_path = cover_path
            model.updated_at = now
        else:
            model = PlaylistModel(
                id=str(uuid.uuid4()),
                name=name,
                description=description,
                source=source,
                spotify_uri=spotify_uri,
                cover_url=cover_url,
                cover_path=cover_path,
                is_liked_songs=False,
                created_at=now,
                updated_at=now,
            )
            self.session.add(model)

    async def delete_playlists_by_uris(self, spotify_uris: set[str]) -> int:
        """Delete playlists by Spotify URIs."""
        from .models import PlaylistModel

        if not spotify_uris:
            return 0

        stmt = delete(PlaylistModel).where(PlaylistModel.spotify_uri.in_(spotify_uris))
        result = await self.session.execute(stmt)
        return result.rowcount or 0  # type: ignore[attr-defined]

    # =========================================================================
    # LIKED SONGS (SPECIAL PLAYLIST)
    # =========================================================================

    async def get_or_create_liked_songs_playlist(self) -> Any:
        """Get or create the Liked Songs special playlist."""
        import uuid

        from .models import PlaylistModel

        stmt = select(PlaylistModel).where(PlaylistModel.is_liked_songs == True)  # noqa: E712
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            return model

        # Create Liked Songs playlist
        now = datetime.now(UTC)
        model = PlaylistModel(
            id=str(uuid.uuid4()),
            name="Liked Songs",
            description="Your Spotify Liked Songs",
            source="SPOTIFY",
            spotify_uri=None,  # No URI for Liked Songs
            is_liked_songs=True,
            created_at=now,
            updated_at=now,
        )
        self.session.add(model)
        await self.session.flush()  # Get ID immediately
        return model

    async def count_liked_songs_tracks(self) -> int:
        """Count tracks in Liked Songs playlist."""
        from .models import PlaylistModel, PlaylistTrackModel

        # Get Liked Songs playlist
        stmt = select(PlaylistModel.id).where(PlaylistModel.is_liked_songs == True)  # noqa: E712
        result = await self.session.execute(stmt)
        playlist_id = result.scalar_one_or_none()

        if not playlist_id:
            return 0

        # Count tracks
        count_stmt = select(func.count(PlaylistTrackModel.track_id)).where(
            PlaylistTrackModel.playlist_id == playlist_id
        )
        count_result = await self.session.execute(count_stmt)
        count = count_result.scalar()
        return count if count is not None else 0

    async def sync_liked_songs_tracks(
        self,
        playlist_id: str,
        tracks: list[dict[str, Any]],
    ) -> int:
        """Sync tracks to Liked Songs playlist.

        Replaces all existing tracks with new set from Spotify.
        Creates TrackModel entries if they don't exist.

        Args:
            playlist_id: ID of the Liked Songs playlist
            tracks: List of track data from Spotify API

        Returns:
            Number of tracks added
        """
        from .models import PlaylistTrackModel

        # Delete existing playlist tracks
        delete_stmt = delete(PlaylistTrackModel).where(
            PlaylistTrackModel.playlist_id == playlist_id
        )
        await self.session.execute(delete_stmt)

        added_count = 0
        now = datetime.now(UTC)

        for position, track_data in enumerate(tracks):
            if not track_data.get("id"):
                continue

            # Ensure track exists and get its UUID (NOT Spotify ID!)
            track_uuid = await self._ensure_track_exists(track_data)
            # Flush to DB so FK constraint works for playlist_tracks
            await self.session.flush()

            # Add to playlist - use UUID, not Spotify ID!
            playlist_track = PlaylistTrackModel(
                playlist_id=playlist_id,
                track_id=track_uuid,  # This is the soulspot_tracks.id (UUID)
                position=position,
                added_at=now,
            )
            self.session.add(playlist_track)
            added_count += 1

        return added_count

    async def _get_or_create_artist(self, artist_data: dict[str, Any]) -> str:
        """Get or create an artist entry and return its ID.

        Hey future me - this creates a minimal artist in soulspot_artists for
        Liked Songs sync. We need a real artist_id for the TrackModel FK.
        The artist is identified by spotify_uri to prevent duplicates.

        Args:
            artist_data: Artist dict from Spotify API with 'id' and 'name'

        Returns:
            The artist ID (UUID string) for use as FK in TrackModel
        """
        from .models import ArtistModel

        spotify_id = artist_data.get("id", "")
        artist_name = artist_data.get("name", "Unknown Artist")
        spotify_uri = f"spotify:artist:{spotify_id}" if spotify_id else None

        # Try to find existing artist by spotify_uri first
        if spotify_uri:
            stmt = select(ArtistModel).where(ArtistModel.spotify_uri == spotify_uri)
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                return existing.id

        # Try to find by name as fallback (for artists without Spotify ID)
        stmt = select(ArtistModel).where(ArtistModel.name == artist_name)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return existing.id

        # Create new artist with minimal data
        new_artist = ArtistModel(
            name=artist_name,
            spotify_uri=spotify_uri,
        )
        self.session.add(new_artist)
        await self.session.flush()  # Get the generated ID
        return new_artist.id

    async def _get_or_create_album(
        self, album_data: dict[str, Any], artist_id: str
    ) -> str | None:
        """Get or create an album entry and return its ID.

        Hey future me - albums need an artist_id FK, so call _get_or_create_artist
        BEFORE this method. Returns None if album_data is empty/invalid.

        Args:
            album_data: Album dict from Spotify API with 'id', 'name', etc.
            artist_id: The artist ID (from _get_or_create_artist) for the FK

        Returns:
            The album ID (UUID string) for use as FK in TrackModel, or None
        """
        from .models import AlbumModel

        if not album_data or not album_data.get("name"):
            return None

        spotify_id = album_data.get("id", "")
        album_name = album_data.get("name", "Unknown Album")
        spotify_uri = f"spotify:album:{spotify_id}" if spotify_id else None

        # Convert release_date string (e.g. "2020-01-15" or "2020") to release_year int
        release_date_str = album_data.get("release_date", "")
        release_year: int | None = None
        if release_date_str:
            with contextlib.suppress(ValueError, IndexError):
                release_year = int(release_date_str[:4])  # Extract year from YYYY-MM-DD

        # Extract artwork URL from images array
        images = album_data.get("images", [])
        artwork_url = images[0].get("url") if images else None

        # Try to find existing album by spotify_uri
        if spotify_uri:
            stmt = select(AlbumModel).where(AlbumModel.spotify_uri == spotify_uri)
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                return existing.id

        # Create new album with minimal data
        new_album = AlbumModel(
            title=album_name,
            artist_id=artist_id,
            release_year=release_year,
            spotify_uri=spotify_uri,
            artwork_url=artwork_url,
        )
        self.session.add(new_album)
        await self.session.flush()  # Get the generated ID
        return new_album.id

    async def _ensure_track_exists(self, track_data: dict[str, Any]) -> str:
        """Ensure a track exists in the soulspot_tracks table.

        Hey future me - this is for Liked Songs sync. We create real TrackModel
        entries with proper FK relations to Artist and Album. The old code was
        broken because it tried to use 'artist' and 'album' as string fields,
        but TrackModel needs artist_id (FK) not a string. That caused the
        '_sa_instance_state' error.

        Flow: Get/Create Artist → Get/Create Album → Create Track with FKs
        
        Returns:
            Track UUID (NOT Spotify ID!) - this is the soulspot_tracks.id
        """
        from .models import TrackModel

        spotify_id = track_data.get("id")
        if not spotify_id:
            raise ValidationException("Track data missing 'id' field")

        # Check if track exists (by spotify_uri)
        spotify_uri = f"spotify:track:{spotify_id}"
        stmt = select(TrackModel).where(TrackModel.spotify_uri == spotify_uri)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return existing.id  # Return UUID, not Spotify ID!

        # Extract track metadata
        name = track_data.get("name", "Unknown")
        duration_ms = track_data.get("duration_ms", 0)

        # Get artist - MUST exist for FK constraint
        artists = track_data.get("artists", [])
        if artists:
            artist_id = await self._get_or_create_artist(artists[0])
        else:
            # Create placeholder artist if none provided
            artist_id = await self._get_or_create_artist({"name": "Unknown Artist"})

        # Get album (optional, nullable FK)
        album_data = track_data.get("album", {})
        album_id = await self._get_or_create_album(album_data, artist_id)

        # ISRC if available
        external_ids = track_data.get("external_ids", {})
        isrc = external_ids.get("isrc")

        # Create track with proper FK references
        model = TrackModel(
            title=name,
            artist_id=artist_id,  # Correct FK field
            album_id=album_id,  # Correct FK field (nullable)
            duration_ms=duration_ms,
            isrc=isrc,
            spotify_uri=spotify_uri,
        )
        self.session.add(model)
        # CRITICAL: Return the UUID (model.id), NOT the Spotify ID!
        return model.id

    # =========================================================================
    # SAVED ALBUMS (unified AlbumModel with is_saved=True)
    # =========================================================================

    async def get_saved_album_ids(self) -> set[str]:
        """Get all Spotify album IDs marked as saved.
        
        Returns Spotify IDs extracted from spotify_uri.
        """
        from .models import AlbumModel

        stmt = select(AlbumModel.spotify_uri).where(
            AlbumModel.source == "spotify",
            AlbumModel.is_saved == True,  # noqa: E712
            AlbumModel.spotify_uri.isnot(None),
        )
        result = await self.session.execute(stmt)
        # Extract Spotify ID from URI: "spotify:album:xxx" -> "xxx"
        return {row[0].split(":")[-1] for row in result.all() if row[0]}

    async def count_saved_albums(self) -> int:
        """Count albums marked as saved."""
        from .models import AlbumModel

        stmt = select(func.count(AlbumModel.id)).where(
            AlbumModel.source == "spotify",
            AlbumModel.is_saved == True,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def unmark_albums_as_saved(self, spotify_ids: set[str]) -> int:
        """Remove is_saved flag from albums (user removed from saved).

        Note: This doesn't delete the album - it might still exist from
        followed artist sync. Just removes the "saved" status.
        """
        from .models import AlbumModel

        if not spotify_ids:
            return 0

        # Convert IDs to URIs for matching
        spotify_uris = {f"spotify:album:{sid}" for sid in spotify_ids}

        stmt = (
            update(AlbumModel)
            .where(AlbumModel.spotify_uri.in_(spotify_uris))
            .values(is_saved=False, updated_at=datetime.now(UTC))
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0  # type: ignore[attr-defined]


# Backwards compatibility alias (renamed Nov 2025)
# Hey future me - remove this alias when all callers are updated to use ProviderBrowseRepository
SpotifyBrowseRepository = ProviderBrowseRepository


# =============================================================================
# SPOTIFY TOKEN REPOSITORY (Background Worker OAuth Tokens)
# =============================================================================
# Hey future me - this repository handles the SINGLE token for background workers!
# Single-user architecture: we always use id='default'. UPSERT pattern ensures
# exactly one row. Background workers call get_active_token() to get the token.
#
# The is_valid flag is CRITICAL:
# - True: Token works, workers operate normally
# - False: Refresh failed → UI shows warning → workers skip work → no crash loop
#
# The repository does NOT refresh tokens - that's TokenManager's job. Repository
# is pure data access (CRUD), business logic lives in services/managers.
# =============================================================================


class SpotifyTokenRepository:
    """Repository for background worker Spotify OAuth tokens.

    Single-user: manages exactly one token row (id='default'). Background workers
    call get_active_token() for API access. Separate from user sessions.

    Key methods:
    - get_active_token(): Get valid token for background work (None if invalid/missing)
    - upsert_token(): Store new token after OAuth callback
    - mark_invalid(): Flag token as invalid (triggers UI warning)
    - get_expiring_soon(): Find tokens needing proactive refresh
    """

    # Single-user token ID (could be spotify_user_id for multi-user later)
    # This is a database identifier, not a password - B105 is a false positive
    DEFAULT_TOKEN_ID = "default"  # nosec B105

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    # Hey future me - this is THE method background workers call! Returns the token
    # if it exists AND is valid. Returns None if: no token, or is_valid=False.
    # Workers should check for None and gracefully skip work (no crash!).
    async def get_active_token(self) -> SpotifyTokenModel | None:
        """Get the active valid token for background workers.

        Returns None if:
        - No token exists (user never authenticated)
        - Token is marked invalid (refresh failed, user revoked)

        Background workers should check for None and skip work gracefully.

        Returns:
            SpotifyTokenModel if valid token exists, None otherwise
        """
        from .models import SpotifyTokenModel

        stmt = select(SpotifyTokenModel).where(
            SpotifyTokenModel.id == self.DEFAULT_TOKEN_ID,
            SpotifyTokenModel.is_valid == True,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # Yo - use this to get token status for UI display (even if invalid)
    async def get_token_status(self) -> SpotifyTokenModel | None:
        """Get token regardless of validity (for status display).

        Unlike get_active_token(), this returns the token even if is_valid=False.
        Used for UI status display and the /api/auth/token-status endpoint.

        Returns:
            SpotifyTokenModel if exists, None if never authenticated
        """
        from .models import SpotifyTokenModel

        stmt = select(SpotifyTokenModel).where(
            SpotifyTokenModel.id == self.DEFAULT_TOKEN_ID
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # Listen up - OAuth callback calls this after successful auth! UPSERT pattern:
    # if token exists → update, else → create. Sets is_valid=True and clears errors.
    async def upsert_token(
        self,
        access_token: str,
        refresh_token: str,
        token_expires_at: datetime,
        scopes: str | None = None,
    ) -> SpotifyTokenModel:
        """Store or update the OAuth token after successful authentication.

        Uses UPSERT pattern: creates new row if none exists, updates if exists.
        Sets is_valid=True and clears any previous errors.

        Args:
            access_token: New access token from Spotify
            refresh_token: New refresh token from Spotify
            token_expires_at: When the access token expires
            scopes: Space-separated scopes granted (optional)

        Returns:
            The created or updated SpotifyTokenModel
        """
        from .models import SpotifyTokenModel

        stmt = select(SpotifyTokenModel).where(
            SpotifyTokenModel.id == self.DEFAULT_TOKEN_ID
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        now = datetime.now(UTC)

        if model:
            # Update existing token
            model.access_token = access_token
            model.refresh_token = refresh_token
            model.token_expires_at = token_expires_at
            model.scopes = scopes
            model.is_valid = True  # Reset validity on new auth
            model.last_error = None  # Clear previous errors
            model.last_error_at = None
            model.updated_at = now
            model.last_refreshed_at = now
        else:
            # Create new token
            model = SpotifyTokenModel(
                id=self.DEFAULT_TOKEN_ID,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=token_expires_at,
                scopes=scopes,
                is_valid=True,
                created_at=now,
                updated_at=now,
                last_refreshed_at=now,
            )
            self.session.add(model)

        return model

    # Hey - TokenRefreshWorker calls this after successful refresh!
    # Updates access_token, expiry, and last_refreshed_at timestamp.
    async def update_after_refresh(
        self,
        access_token: str,
        token_expires_at: datetime,
        refresh_token: str | None = None,
    ) -> bool:
        """Update token after successful refresh.

        Called by TokenRefreshWorker after Spotify returns new tokens.
        Optionally updates refresh_token if Spotify returned a new one.

        Args:
            access_token: New access token
            token_expires_at: New expiration time
            refresh_token: New refresh token (optional, Spotify sometimes rotates)

        Returns:
            True if token was updated, False if no token exists
        """
        from .models import SpotifyTokenModel

        stmt = select(SpotifyTokenModel).where(
            SpotifyTokenModel.id == self.DEFAULT_TOKEN_ID
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return False

        now = datetime.now(UTC)
        model.access_token = access_token
        model.token_expires_at = token_expires_at
        model.updated_at = now
        model.last_refreshed_at = now
        model.is_valid = True  # Successful refresh confirms validity
        model.last_error = None  # Clear any previous errors
        model.last_error_at = None

        # Spotify sometimes rotates refresh tokens
        if refresh_token:
            model.refresh_token = refresh_token

        return True

    # Yo - call this when refresh FAILS (401, 403, network error, etc.)
    # Sets is_valid=False which triggers UI warning and pauses workers.
    async def mark_invalid(self, error_message: str) -> bool:
        """Mark token as invalid after refresh failure.

        This triggers:
        1. UI warning banner telling user to re-authenticate
        2. Background workers skip their work (no crash loop)

        Args:
            error_message: Description of what went wrong (for debugging)

        Returns:
            True if token was marked invalid, False if no token exists
        """
        from .models import SpotifyTokenModel

        stmt = select(SpotifyTokenModel).where(
            SpotifyTokenModel.id == self.DEFAULT_TOKEN_ID
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return False

        now = datetime.now(UTC)
        model.is_valid = False
        model.last_error = error_message
        model.last_error_at = now
        model.updated_at = now

        return True

    # Listen - TokenRefreshWorker calls this to find tokens needing refresh!
    # Default: refresh tokens expiring within 10 minutes (proactive refresh).
    async def get_expiring_soon(self, minutes: int = 10) -> SpotifyTokenModel | None:
        """Get token if it expires within given minutes.

        Used by TokenRefreshWorker for proactive refresh before expiration.
        Only returns valid tokens (is_valid=True).

        Args:
            minutes: Threshold in minutes (default 10)

        Returns:
            SpotifyTokenModel if expiring soon and valid, None otherwise
        """
        from .models import SpotifyTokenModel

        threshold = datetime.now(UTC) + timedelta(minutes=minutes)

        stmt = select(SpotifyTokenModel).where(
            SpotifyTokenModel.id == self.DEFAULT_TOKEN_ID,
            SpotifyTokenModel.is_valid == True,  # noqa: E712
            SpotifyTokenModel.token_expires_at <= threshold,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # Hey - cleanup method, probably not needed for single-user but good to have
    async def delete_token(self) -> bool:
        """Delete the token (logout/revoke).

        Returns:
            True if token was deleted, False if none existed
        """
        from .models import SpotifyTokenModel

        stmt = select(SpotifyTokenModel).where(
            SpotifyTokenModel.id == self.DEFAULT_TOKEN_ID
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return False

        await self.session.delete(model)
        return True
