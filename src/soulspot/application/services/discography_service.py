"""Discography service for detecting missing albums.

Hey future me - Nach Table Consolidation (Nov 2025):
- KEINE spotify_albums Tabelle mehr! Alles in soulspot_albums
- "owned" = Alben mit file_path (downloaded) ODER source='local'
- "known from spotify" = Alben mit source='spotify'
- Vergleich basiert auf spotify_uri Matching
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.value_objects import ArtistId
from soulspot.infrastructure.observability.log_messages import LogMessages
from soulspot.infrastructure.persistence.models import AlbumModel, ArtistModel

# Hey future me – SpotifyClient Import entfernt!
# Service nutzt bereits lokale SpotifyBrowseRepository-Daten für Discography-Checks.
# Kein direkter Spotify API Call mehr nötig hier.

logger = logging.getLogger(__name__)


class DiscographyInfo:
    """Information about artist discography completeness."""

    def __init__(
        self,
        artist_id: str,
        artist_name: str,
        total_albums: int,
        owned_albums: int,
        missing_albums: list[dict[str, Any]],
    ):
        """Initialize discography info."""
        self.artist_id = artist_id
        self.artist_name = artist_name
        self.total_albums = total_albums
        self.owned_albums = owned_albums
        self.missing_albums = missing_albums
        self.completeness_percent = (
            (owned_albums / total_albums * 100) if total_albums > 0 else 0.0
        )

    # Hey future me, simple dataclass helper - checks if we have ALL albums or missing some
    # Used for UI indicators (green checkmark vs yellow warning)
    def is_complete(self) -> bool:
        """Check if discography is complete."""
        return self.owned_albums >= self.total_albums

    # Yo serialization helper - converts to JSON-friendly dict for API responses
    # WHY round completeness? 66.66666667% looks ugly, 66.67% is cleaner
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "artist_id": self.artist_id,
            "artist_name": self.artist_name,
            "total_albums": self.total_albums,
            "owned_albums": self.owned_albums,
            "missing_albums_count": len(self.missing_albums),
            "missing_albums": self.missing_albums,
            "completeness_percent": round(self.completeness_percent, 2),
            "is_complete": self.is_complete(),
        }


class DiscographyService:
    """Service for checking artist discography completeness."""

    # Hey future me – SpotifyClient Parameter entfernt!
    # Service nutzt lokale Daten aus SpotifyBrowseRepository für Discography-Checks.
    # Background Sync hält spotify_albums aktuell, kein live API Call nötig.
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        """Initialize discography service.

        Args:
            session: Database session
        """
        self._session = session

    # Hey future me: Discography completeness check - finds which albums are missing from an artist's catalog
    # WHY check this? User downloads 3 Pink Floyd albums, but they have 15 studio albums - which 12 are missing?
    # GOTCHA: Spotify returns compilations, live albums, singles - you might not WANT them all
    # Consider adding filter for album_type (album vs single vs compilation)
    #
    # NACH TABLE CONSOLIDATION (Nov 2025):
    # - Nutzt unified soulspot_albums Tabelle
    # - "owned" = file_path IS NOT NULL oder source='local'
    # - "known" = source='spotify' (alle bekannten Spotify-Alben)
    # - Vergleich über spotify_uri matching
    async def check_discography(
        self,
        artist_id: ArtistId,
        access_token: str,  # noqa: ARG002
    ) -> DiscographyInfo:
        """Check discography completeness for an artist.

        Uses unified soulspot_albums table after table consolidation.
        Compares owned albums (downloaded) with known albums from Spotify.

        Args:
            artist_id: Artist ID (local soulspot_artists.id)
            access_token: Spotify access token (kept for API compatibility, rarely used now)

        Returns:
            Discography information
        """
        # Get artist from database
        stmt = select(ArtistModel).where(ArtistModel.id == str(artist_id.value))
        result = await self._session.execute(stmt)
        artist = result.scalar_one_or_none()

        if not artist:
            logger.warning(
                LogMessages.file_operation_failed(
                    operation="artist_lookup",
                    path=str(artist_id.value),
                    reason="Artist not found in database",
                    hint="Artist must be synced from Spotify or imported first"
                ).format()
            )
            return DiscographyInfo(
                artist_id=str(artist_id.value),
                artist_name="Unknown",
                total_albums=0,
                owned_albums=0,
                missing_albums=[],
            )

        # Get owned albums (downloaded/local files) - these have file_path set
        stmt_owned = select(AlbumModel).where(
            AlbumModel.artist_id == str(artist_id.value),
            # Album is "owned" if it has local files or was imported from local library
            AlbumModel.source.in_(["local", "hybrid"]),
        )
        result = await self._session.execute(stmt_owned)
        owned_albums = result.scalars().all()
        owned_spotify_uris = {
            album.spotify_uri for album in owned_albums if album.spotify_uri
        }

        # Get Spotify artist ID from URI
        spotify_artist_id = (
            artist.spotify_uri.split(":")[-1] if artist.spotify_uri else None
        )
        if not spotify_artist_id:
            logger.warning(
                LogMessages.sync_failed(
                    sync_type="discography_check",
                    reason=f"Artist {artist.name} has no Spotify URI",
                    hint="Artist must be synced from Spotify to check discography"
                ).format()
            )
            return DiscographyInfo(
                artist_id=str(artist_id.value),
                artist_name=artist.name,
                total_albums=len(owned_albums),
                owned_albums=len(owned_albums),
                missing_albums=[],
            )

        # Check if albums are synced for this artist (albums_synced_at field)
        if not artist.albums_synced_at:
            # Albums not synced yet - can't determine missing albums
            # The Background Sync will eventually sync them
            logger.info(
                f"Albums not yet synced for {artist.name}, waiting for background sync"
            )
            return DiscographyInfo(
                artist_id=str(artist_id.value),
                artist_name=artist.name,
                total_albums=len(owned_albums),  # Best guess
                owned_albums=len(owned_albums),
                missing_albums=[],  # Can't determine yet
            )

        # Get all known albums from Spotify (source='spotify') for this artist
        # Hey future me - nach Consolidation sind ALLE Alben in soulspot_albums!
        stmt_spotify = select(AlbumModel).where(
            AlbumModel.artist_id == str(artist_id.value),
            AlbumModel.source == "spotify",  # Only Spotify-synced albums
        )
        result = await self._session.execute(stmt_spotify)
        all_spotify_albums = list(result.scalars().all())

        # Find missing albums (in spotify-synced but not in owned/local)
        missing_albums = []
        for album in all_spotify_albums:
            if album.spotify_uri not in owned_spotify_uris:
                # Extract spotify_id from URI: "spotify:album:xxx" -> "xxx"
                spotify_id = album.spotify_uri.split(":")[-1] if album.spotify_uri else album.id
                missing_albums.append(
                    {
                        "name": album.title,
                        "spotify_uri": album.spotify_uri,
                        "spotify_id": spotify_id,
                        "release_date": album.release_date or "",
                        "total_tracks": album.total_tracks or 0,
                        "album_type": album.primary_type,
                        "image_url": album.cover_url,
                    }
                )

        logger.info(
            f"Discography check for {artist.name}: "
            f"{len(owned_albums)}/{len(all_spotify_albums)} albums (from unified library)"
        )

        return DiscographyInfo(
            artist_id=str(artist_id.value),
            artist_name=artist.name,
            total_albums=len(all_spotify_albums),
            owned_albums=len(owned_albums),
            missing_albums=missing_albums,
        )

    # Listen - batch discography check for multiple artists
    # WHY limit param? Checking 1000 artists = 1000 Spotify API calls = rate limit hell
    # Default limit=10 is conservative - increase if you have good rate limit headroom
    # GOTCHA: This is SLOW - each artist requires separate Spotify API call
    # Consider adding batch parallelization with asyncio.gather() but watch rate limits!
    async def get_missing_albums_for_all_artists(
        self, access_token: str, limit: int = 10
    ) -> list[DiscographyInfo]:
        """Get missing albums for all artists in the library.

        Args:
            access_token: Spotify access token
            limit: Maximum number of artists to check

        Returns:
            List of discography information for artists with missing albums
        """
        # Get all artists from database
        stmt = select(ArtistModel).limit(limit)
        result = await self._session.execute(stmt)
        artists = result.scalars().all()

        discography_infos = []
        for artist in artists:
            try:
                artist_id = ArtistId.from_string(artist.id)
                info = await self.check_discography(artist_id, access_token)
                if not info.is_complete():
                    discography_infos.append(info)
            except Exception as e:
                logger.error(
                    LogMessages.sync_failed(
                        sync_type="discography_check",
                        reason=f"Failed to check discography for artist {artist.id}",
                        hint="Check artist data validity and Spotify sync status"
                    ).format(),
                    exc_info=e
                )
                continue

        return discography_infos
