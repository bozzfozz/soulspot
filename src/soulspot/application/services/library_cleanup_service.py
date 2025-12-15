"""Library cleanup service for bulk operations.

Hey future me - this service handles DESTRUCTIVE bulk operations!
Use with caution - these operations delete data.
"""

import logging
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.infrastructure.persistence.models import (
    AlbumModel,
    ArtistModel,
    TrackModel,
)

logger = logging.getLogger(__name__)


class LibraryCleanupService:
    """Service for library cleanup operations.

    Hey future me - centralizes destructive operations that were in routes.
    These operations are pragmatic - they use Models directly for performance
    (bulk deletes, complex JOINs for orphan detection).
    """

    def __init__(self, session: AsyncSession):
        """Initialize cleanup service.

        Args:
            session: Database session
        """
        self._session = session

    async def clear_local_library(self) -> dict[str, Any]:
        """Clear all local library data (tracks with file_path + orphaned entities).

        Hey future me - NUCLEAR OPTION! Deletes:
        1. All tracks with file_path (local imports)
        2. Albums with no remaining tracks (orphaned)
        3. Artists with no tracks AND no albums (orphaned)

        Spotify-synced data (playlists, spotify_* tables) is NOT affected!

        Returns:
            Statistics about deleted entities
        """
        stats = {
            "deleted_tracks": 0,
            "deleted_albums": 0,
            "deleted_artists": 0,
        }

        logger.info(
            "🗑️ Library Clear Started\n"
            "├─ Operation: Clear local library\n"
            "└─ Target: All tracks with file_path + orphaned albums/artists"
        )

        # Step 1: Delete all tracks with file_path (local imports)
        count_stmt = select(func.count(TrackModel.id)).where(
            TrackModel.file_path.isnot(None)
        )
        count_result = await self._session.execute(count_stmt)
        stats["deleted_tracks"] = count_result.scalar() or 0

        if stats["deleted_tracks"] > 0:
            delete_tracks_stmt = delete(TrackModel).where(
                TrackModel.file_path.isnot(None)
            )
            await self._session.execute(delete_tracks_stmt)
            logger.info(
                f"🗑️ Local Tracks Deleted\n"
                f"└─ Count: {stats['deleted_tracks']} tracks"
            )

        # Step 2: Delete orphaned albums (albums with no remaining tracks)
        orphan_albums_stmt = (
            select(AlbumModel.id)
            .outerjoin(TrackModel, AlbumModel.id == TrackModel.album_id)
            .group_by(AlbumModel.id)
            .having(func.count(TrackModel.id) == 0)
        )
        orphan_albums_result = await self._session.execute(orphan_albums_stmt)
        orphan_album_ids = [row[0] for row in orphan_albums_result.all()]

        if orphan_album_ids:
            stats["deleted_albums"] = len(orphan_album_ids)
            delete_albums_stmt = delete(AlbumModel).where(
                AlbumModel.id.in_(orphan_album_ids)
            )
            await self._session.execute(delete_albums_stmt)
            logger.info(
                f"🗑️ Orphaned Albums Deleted\n"
                f"└─ Count: {stats['deleted_albums']} albums"
            )

        # Step 3: Delete orphaned artists (artists with no tracks AND no albums)
        orphan_artists_stmt = (
            select(ArtistModel.id)
            .outerjoin(TrackModel, ArtistModel.id == TrackModel.artist_id)
            .outerjoin(AlbumModel, ArtistModel.id == AlbumModel.artist_id)
            .group_by(ArtistModel.id)
            .having((func.count(TrackModel.id) == 0) & (func.count(AlbumModel.id) == 0))
        )
        orphan_artists_result = await self._session.execute(orphan_artists_stmt)
        orphan_artist_ids = [row[0] for row in orphan_artists_result.all()]

        if orphan_artist_ids:
            stats["deleted_artists"] = len(orphan_artist_ids)
            delete_artists_stmt = delete(ArtistModel).where(
                ArtistModel.id.in_(orphan_artist_ids)
            )
            await self._session.execute(delete_artists_stmt)
            logger.info(
                f"🗑️ Orphaned Artists Deleted\n"
                f"└─ Count: {stats['deleted_artists']} albums"
            )

        await self._session.commit()

        logger.info(
            "✅ Library Clear Complete\n"
            f"├─ Tracks: {stats['deleted_tracks']}\n"
            f"├─ Albums: {stats['deleted_albums']}\n"
            f"└─ Artists: {stats['deleted_artists']}"
        )

        return stats
