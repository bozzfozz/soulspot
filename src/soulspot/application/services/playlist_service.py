"""Playlist service for playlist operations.

Hey future me - this service handles playlist management operations
that were scattered in playlists.py routes. Includes missing track
detection, deletion, and blacklist management.
"""

from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from soulspot.infrastructure.persistence.models import (
    AppSettingsModel,
    PlaylistModel,
    TrackModel,
)


class PlaylistService:
    """Service for playlist management operations."""

    def __init__(self, session: AsyncSession):
        """Initialize playlist service.

        Args:
            session: Database session
        """
        self._session = session

    async def get_missing_tracks(self, playlist_id: str) -> dict[str, Any]:
        """Get tracks from playlist that don't have file_path (not downloaded).

        Hey future me - optimized version without N+1 queries.
        Uses single JOIN query instead of loop.

        Args:
            playlist_id: Playlist UUID

        Returns:
            Dict with missing_tracks list and counts

        Raises:
            ValueError: If playlist not found
        """
        # Get playlist
        playlist_stmt = select(PlaylistModel).where(PlaylistModel.id == playlist_id)
        playlist_result = await self._session.execute(playlist_stmt)
        playlist = playlist_result.scalar_one_or_none()

        if not playlist:
            raise ValueError("Playlist not found")

        # Get all tracks for playlist (optimized with JOIN)
        from soulspot.infrastructure.persistence.models import PlaylistTrackModel

        tracks_stmt = (
            select(TrackModel)
            .join(
                PlaylistTrackModel,
                TrackModel.id == PlaylistTrackModel.track_id,
            )
            .where(PlaylistTrackModel.playlist_id == playlist_id)
            .where(TrackModel.file_path.is_(None))
            .options(joinedload(TrackModel.artist), joinedload(TrackModel.album))
        )

        result = await self._session.execute(tracks_stmt)
        track_models = result.unique().scalars().all()

        missing_tracks = [
            {
                "id": track.id,
                "title": track.title,
                "artist": track.artist.name if track.artist else "Unknown Artist",
                "album": track.album.title if track.album else "Unknown Album",
                "duration_ms": track.duration_ms,
                "spotify_uri": track.spotify_uri,
            }
            for track in track_models
        ]

        # Get total track count
        total_stmt = select(PlaylistTrackModel.track_id).where(
            PlaylistTrackModel.playlist_id == playlist_id
        )
        total_result = await self._session.execute(total_stmt)
        total_tracks = len(total_result.all())

        return {
            "playlist_id": playlist_id,
            "playlist_name": playlist.name,
            "missing_tracks": missing_tracks,
            "missing_count": len(missing_tracks),
            "total_tracks": total_tracks,
        }

    async def delete_playlist(self, playlist_id: str) -> dict[str, Any]:
        """Delete playlist and all its associations.

        Hey future me - CASCADE deletes playlist_tracks automatically.
        Tracks themselves are NOT deleted.

        Args:
            playlist_id: Playlist UUID

        Returns:
            Dict with success message

        Raises:
            ValueError: If playlist not found
        """
        # Get playlist name before deletion
        stmt = select(PlaylistModel).where(PlaylistModel.id == playlist_id)
        result = await self._session.execute(stmt)
        playlist = result.scalar_one_or_none()

        if not playlist:
            raise ValueError("Playlist not found")

        playlist_name = playlist.name

        # Delete playlist
        delete_stmt = delete(PlaylistModel).where(PlaylistModel.id == playlist_id)
        await self._session.execute(delete_stmt)
        await self._session.commit()

        return {
            "message": f"Playlist '{playlist_name}' deleted",
            "playlist_id": playlist_id,
            "playlist_name": playlist_name,
        }

    async def set_blacklist_status(
        self, playlist_id: str, blacklisted: bool
    ) -> dict[str, Any]:
        """Set playlist blacklist status.

        Hey future me - blacklisted playlists are excluded from sync.

        Args:
            playlist_id: Playlist UUID
            blacklisted: True to blacklist, False to unblacklist

        Returns:
            Dict with success message

        Raises:
            ValueError: If playlist not found
        """
        # Get playlist
        stmt = select(PlaylistModel).where(PlaylistModel.id == playlist_id)
        result = await self._session.execute(stmt)
        playlist = result.scalar_one_or_none()

        if not playlist:
            raise ValueError("Playlist not found")

        # Update blacklist status
        update_stmt = (
            update(PlaylistModel)
            .where(PlaylistModel.id == playlist_id)
            .values(is_blacklisted=blacklisted)
        )
        await self._session.execute(update_stmt)
        await self._session.commit()

        action = "blacklisted" if blacklisted else "removed from blacklist"
        return {
            "message": f"Playlist '{playlist.name}' {action}",
            "playlist_id": playlist_id,
            "playlist_name": playlist.name,
            "is_blacklisted": blacklisted,
        }

    async def delete_and_blacklist(self, playlist_id: str) -> dict[str, Any]:
        """Delete playlist and add Spotify URI to blacklist.

        Hey future me - prevents re-import during sync.
        Stores Spotify URI in app_settings.

        Args:
            playlist_id: Playlist UUID

        Returns:
            Dict with success message

        Raises:
            ValueError: If playlist not found
        """
        # Get playlist info
        stmt = select(PlaylistModel).where(PlaylistModel.id == playlist_id)
        result = await self._session.execute(stmt)
        playlist = result.scalar_one_or_none()

        if not playlist:
            raise ValueError("Playlist not found")

        playlist_name = playlist.name
        spotify_uri = playlist.spotify_uri

        # Get current blacklist from app_settings
        settings_stmt = select(AppSettingsModel).where(
            AppSettingsModel.key == "playlist_blacklist"
        )
        settings_result = await self._session.execute(settings_stmt)
        settings = settings_result.scalar_one_or_none()

        if settings:
            # Add to existing blacklist
            blacklist = settings.value.get("uris", [])
            if spotify_uri and spotify_uri not in blacklist:
                blacklist.append(spotify_uri)
                settings.value = {"uris": blacklist}
        else:
            # Create new blacklist entry
            settings = AppSettingsModel(
                key="playlist_blacklist",
                value={"uris": [spotify_uri] if spotify_uri else []},
            )
            self._session.add(settings)

        # Delete playlist
        delete_stmt = delete(PlaylistModel).where(PlaylistModel.id == playlist_id)
        await self._session.execute(delete_stmt)
        await self._session.commit()

        return {
            "message": f"Playlist '{playlist_name}' deleted and blacklisted",
            "playlist_id": playlist_id,
            "playlist_name": playlist_name,
            "spotify_uri": spotify_uri,
        }
