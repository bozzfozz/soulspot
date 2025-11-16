"""Discography service for detecting missing albums."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.value_objects import ArtistId
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
from soulspot.infrastructure.persistence.models import AlbumModel, ArtistModel

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

    def is_complete(self) -> bool:
        """Check if discography is complete."""
        return self.owned_albums >= self.total_albums

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

    def __init__(
        self,
        session: AsyncSession,
        spotify_client: SpotifyClient | None = None,
    ) -> None:
        """Initialize discography service.

        Args:
            session: Database session
            spotify_client: Spotify client for fetching discography
        """
        self.session = session
        self.spotify_client = spotify_client

    async def check_discography(
        self, artist_id: ArtistId, access_token: str
    ) -> DiscographyInfo:
        """Check discography completeness for an artist.

        Args:
            artist_id: Artist ID
            access_token: Spotify access token

        Returns:
            Discography information
        """
        # Get artist from database
        stmt = select(ArtistModel).where(ArtistModel.id == str(artist_id.value))
        result = await self.session.execute(stmt)
        artist = result.scalar_one_or_none()

        if not artist:
            logger.warning(f"Artist {artist_id} not found in database")
            return DiscographyInfo(
                artist_id=str(artist_id.value),
                artist_name="Unknown",
                total_albums=0,
                owned_albums=0,
                missing_albums=[],
            )

        # Get owned albums from database
        stmt = select(AlbumModel).where(AlbumModel.artist_id == str(artist_id.value))
        result = await self.session.execute(stmt)
        owned_albums = result.scalars().all()
        owned_spotify_uris = {album.spotify_uri for album in owned_albums if album.spotify_uri}

        # Get all albums from Spotify
        if not self.spotify_client:
            logger.warning("Spotify client not available for discography check")
            return DiscographyInfo(
                artist_id=str(artist_id.value),
                artist_name=artist.name,
                total_albums=len(owned_albums),
                owned_albums=len(owned_albums),
                missing_albums=[],
            )

        try:
            # Get artist's albums from Spotify
            spotify_artist_id = artist.spotify_uri.split(":")[-1] if artist.spotify_uri else None
            if not spotify_artist_id:
                logger.warning(f"Artist {artist_id} has no Spotify URI")
                return DiscographyInfo(
                    artist_id=str(artist_id.value),
                    artist_name=artist.name,
                    total_albums=len(owned_albums),
                    owned_albums=len(owned_albums),
                    missing_albums=[],
                )

            all_albums = await self.spotify_client.get_artist_albums(
                spotify_artist_id, access_token, include_groups="album"
            )

            # Find missing albums
            missing_albums = []
            for album in all_albums:
                album_uri = album.get("uri", "")
                if album_uri not in owned_spotify_uris:
                    missing_albums.append({
                        "name": album.get("name", ""),
                        "spotify_uri": album_uri,
                        "release_date": album.get("release_date", ""),
                        "total_tracks": album.get("total_tracks", 0),
                        "album_type": album.get("album_type", ""),
                    })

            logger.info(
                f"Discography check for {artist.name}: {len(owned_albums)}/{len(all_albums)} albums"
            )

            return DiscographyInfo(
                artist_id=str(artist_id.value),
                artist_name=artist.name,
                total_albums=len(all_albums),
                owned_albums=len(owned_albums),
                missing_albums=missing_albums,
            )

        except Exception as e:
            logger.error(f"Failed to check discography: {e}")
            return DiscographyInfo(
                artist_id=str(artist_id.value),
                artist_name=artist.name,
                total_albums=len(owned_albums),
                owned_albums=len(owned_albums),
                missing_albums=[],
            )

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
        result = await self.session.execute(stmt)
        artists = result.scalars().all()

        discography_infos = []
        for artist in artists:
            try:
                artist_id = ArtistId.from_string(artist.id)
                info = await self.check_discography(artist_id, access_token)
                if not info.is_complete():
                    discography_infos.append(info)
            except Exception as e:
                logger.error(f"Failed to check discography for artist {artist.id}: {e}")
                continue

        return discography_infos
