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

    async def clear_local_library(self, batch_size: int = 1000) -> dict[str, Any]:
        """Clear all local library data (tracks with file_path + orphaned entities).

        Hey future me - MANUAL DEVELOPMENT RESET! Use when:
        1. Testing local file imports - want clean slate
        2. Corrupted file_path assignments need cleanup
        3. Development: reset local files without re-syncing streaming data

        ⚠️ IMPORTANT: This is for MANUAL use only (no automatic workers)!

        Deletes:
        1. All tracks with file_path (downloaded/imported local files)
        2. Albums with NO tracks (local OR streaming) - true orphans only
        3. Artists with NO tracks AND NO albums - true orphans only

        KEEPS:
        ✅ Streaming tracks (file_path = NULL from Spotify/Deezer sync)
        ✅ Albums with streaming tracks (even if no local files)
        ✅ Artists with streaming albums

        CRITICAL: Includes transaction rollback on errors to prevent partial deletes!
        OPTIMIZED: Batch deletion prevents memory issues for massive (10k+) libraries.

        Args:
            batch_size: Number of entities to delete per batch (default 1000)

        Returns:
            Statistics about deleted entities
        """
        stats = {
            "deleted_tracks": 0,
            "deleted_albums": 0,
            "deleted_artists": 0,
        }

        logger.info(
            "Library Clear Started (Manual Reset)\n"
            "├─ Operation: Clear local files only\n"
            f"├─ Batch size: {batch_size}\n"
            "├─ Deletes: Tracks with file_path (local files)\n"
            "├─ Keeps: Streaming tracks (file_path=NULL)\n"
            "└─ Orphans: Only TRUE orphans (no local AND no streaming data)"
        )

        try:
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
                    "Local Tracks Deleted: %d (streaming tracks kept)",
                    stats["deleted_tracks"],
                )

            # Step 2: OPTIMIZED - Delete orphaned albums in batches (prevents memory overload)
            # Hey future me - loading 10k+ album IDs into memory is bad! We batch delete instead.
            while True:
                orphan_albums_stmt = (
                    select(AlbumModel.id)
                    .outerjoin(TrackModel, AlbumModel.id == TrackModel.album_id)
                    .group_by(AlbumModel.id)
                    .having(func.count(TrackModel.id) == 0)
                    .limit(batch_size)
                )
                orphan_albums_result = await self._session.execute(orphan_albums_stmt)
                orphan_album_ids = [row[0] for row in orphan_albums_result.all()]

                if not orphan_album_ids:
                    break  # No more orphaned albums

                batch_count = len(orphan_album_ids)
                stats["deleted_albums"] += batch_count

                delete_albums_stmt = delete(AlbumModel).where(
                    AlbumModel.id.in_(orphan_album_ids)
                )
                await self._session.execute(delete_albums_stmt)

                logger.debug(
                    "Orphaned Albums Batch: %d (no tracks at all)", batch_count
                )

                if batch_count < batch_size:
                    break  # Last batch processed

            if stats["deleted_albums"] > 0:
                logger.info(
                    "Orphaned Albums Deleted: %d (true orphans only)",
                    stats["deleted_albums"],
                )

            # Step 3: OPTIMIZED - Delete orphaned artists in batches (prevents memory overload)
            while True:
                orphan_artists_stmt = (
                    select(ArtistModel.id)
                    .outerjoin(TrackModel, ArtistModel.id == TrackModel.artist_id)
                    .outerjoin(AlbumModel, ArtistModel.id == AlbumModel.artist_id)
                    .group_by(ArtistModel.id)
                    .having(
                        (func.count(TrackModel.id) == 0)
                        & (func.count(AlbumModel.id) == 0)
                    )
                    .limit(batch_size)
                )
                orphan_artists_result = await self._session.execute(orphan_artists_stmt)
                orphan_artist_ids = [row[0] for row in orphan_artists_result.all()]

                if not orphan_artist_ids:
                    break  # No more orphaned artists

                batch_count = len(orphan_artist_ids)
                stats["deleted_artists"] += batch_count

                delete_artists_stmt = delete(ArtistModel).where(
                    ArtistModel.id.in_(orphan_artist_ids)
                )
                await self._session.execute(delete_artists_stmt)

                logger.debug(
                    "Orphaned Artists Batch: %d (no albums/tracks)", batch_count
                )

                if batch_count < batch_size:
                    break  # Last batch processed

            if stats["deleted_artists"] > 0:
                logger.info(
                    "Orphaned Artists Deleted: %d (true orphans only)",
                    stats["deleted_artists"],
                )

            await self._session.commit()

            logger.info(
                "Library Clear Complete: %d tracks, %d albums, %d artists (streaming data kept)",
                stats["deleted_tracks"],
                stats["deleted_albums"],
                stats["deleted_artists"],
            )

            return stats
        except Exception as e:
            await self._session.rollback()
            logger.error(f"Failed to clear local library: {e}")
            raise
