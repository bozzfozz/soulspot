"""Stats Service - Centralized statistics and counts.

Hey future me - this service centralizes all count/stats queries!
Instead of routers doing `session.execute(select(func.count(...)))` directly,
they call this service. Clean Architecture: Router → Service → Repository.

Why centralized stats?
1. Reusable across routers (ui.py, stats.py, library.py)
2. Cacheable (future: add caching decorator)
3. Testable (mock service instead of DB)
4. Consistent naming and calculation logic
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    pass


class StatsService:
    """Service for library statistics and counts.

    Provides centralized access to counts and statistics across the library.
    All count queries should go through this service for consistency.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize stats service.

        Args:
            session: Database session
        """
        self._session = session

    # =========================================================================
    # BASIC COUNTS
    # =========================================================================

    async def get_total_tracks(self) -> int:
        """Get total number of tracks in library."""
        from soulspot.infrastructure.persistence.models import TrackModel

        stmt = select(func.count(TrackModel.id))
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def get_total_artists(self) -> int:
        """Get total number of artists in library."""
        from soulspot.infrastructure.persistence.models import ArtistModel

        stmt = select(func.count(ArtistModel.id))
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def get_total_albums(self) -> int:
        """Get total number of albums in library."""
        from soulspot.infrastructure.persistence.models import AlbumModel

        stmt = select(func.count(AlbumModel.id))
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def get_total_playlists(self) -> int:
        """Get total number of playlists."""
        from soulspot.infrastructure.persistence.models import PlaylistModel

        stmt = select(func.count(PlaylistModel.id))
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    # =========================================================================
    # DOWNLOAD STATS
    # =========================================================================

    async def get_download_counts_by_status(self) -> dict[str, int]:
        """Get download counts grouped by status.

        Returns:
            Dict with status as key and count as value
            Example: {"completed": 42, "pending": 5, "failed": 2}
        """
        from soulspot.infrastructure.persistence.models import DownloadModel

        stmt = select(
            DownloadModel.status,
            func.count(DownloadModel.id),
        ).group_by(DownloadModel.status)

        result = await self._session.execute(stmt)
        rows = result.all()

        counts = {
            "pending": 0,
            "downloading": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        }
        for status, count in rows:
            counts[status] = count

        return counts

    async def get_total_downloads(self) -> int:
        """Get total number of downloads (all statuses)."""
        from soulspot.infrastructure.persistence.models import DownloadModel

        stmt = select(func.count(DownloadModel.id))
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def get_completed_downloads_count(self) -> int:
        """Get number of completed downloads."""
        from soulspot.infrastructure.persistence.models import DownloadModel

        stmt = select(func.count(DownloadModel.id)).where(
            DownloadModel.status == "completed"
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def get_pending_downloads_count(self) -> int:
        """Get number of pending downloads (not started yet)."""
        from soulspot.infrastructure.persistence.models import DownloadModel

        stmt = select(func.count(DownloadModel.id)).where(
            DownloadModel.status == "pending"
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def get_failed_downloads_count(self) -> int:
        """Get number of failed downloads."""
        from soulspot.infrastructure.persistence.models import DownloadModel

        stmt = select(func.count(DownloadModel.id)).where(
            DownloadModel.status == "failed"
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    # =========================================================================
    # ENRICHMENT STATS
    # =========================================================================

    async def get_unenriched_artists_count(self) -> int:
        """Get number of artists without Spotify URI."""
        from soulspot.infrastructure.persistence.models import ArtistModel

        stmt = select(func.count(ArtistModel.id)).where(
            ArtistModel.spotify_uri.is_(None)
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def get_unenriched_albums_count(self) -> int:
        """Get number of albums without Spotify URI."""
        from soulspot.infrastructure.persistence.models import AlbumModel

        stmt = select(func.count(AlbumModel.id)).where(AlbumModel.spotify_uri.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def get_pending_enrichment_candidates_count(self) -> int:
        """Get number of enrichment candidates awaiting review."""
        from soulspot.infrastructure.persistence.repositories import (
            EnrichmentCandidateRepository,
        )

        repo = EnrichmentCandidateRepository(self._session)
        return await repo.get_pending_count()

    # =========================================================================
    # DUPLICATE STATS
    # =========================================================================

    async def get_duplicate_counts_by_status(self) -> dict[str, int]:
        """Get duplicate candidate counts grouped by status.

        Returns:
            Dict with status counts
            Example: {"pending": 12, "confirmed": 3, "dismissed": 5}
        """
        from soulspot.infrastructure.persistence.repositories import (
            DuplicateCandidateRepository,
        )

        repo = DuplicateCandidateRepository(self._session)
        return await repo.count_by_status()

    async def get_unresolved_duplicates_count(self) -> int:
        """Get number of unresolved duplicate groups.

        Hey future me - counts FileDuplicateModel where resolved=False.
        This is for legacy duplicate detection (file-based).
        """
        from soulspot.infrastructure.persistence.models import FileDuplicateModel

        stmt = select(func.count(FileDuplicateModel.id)).where(
            FileDuplicateModel.resolved == False  # noqa: E712
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    # =========================================================================
    # FILE STATS
    # =========================================================================

    async def get_tracks_with_files(self) -> int:
        """Get number of tracks with file_path set."""
        from soulspot.infrastructure.persistence.models import TrackModel

        stmt = select(func.count(TrackModel.id)).where(TrackModel.file_path.isnot(None))
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def get_broken_files_count(self) -> int:
        """Get number of broken files (is_broken=True)."""
        from soulspot.infrastructure.persistence.models import TrackModel

        stmt = select(func.count(TrackModel.id)).where(
            TrackModel.is_broken == True  # noqa: E712
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def get_total_file_size(self) -> int:
        """Get total file size in bytes (sum of all track file_size)."""
        from soulspot.infrastructure.persistence.models import TrackModel

        stmt = select(func.sum(TrackModel.file_size)).where(
            TrackModel.file_size.isnot(None)
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def get_distinct_playlist_tracks_count(self) -> int:
        """Get count of distinct tracks across all playlists."""
        from soulspot.infrastructure.persistence.models import PlaylistTrackModel

        stmt = select(func.count(func.distinct(PlaylistTrackModel.track_id)))
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def get_queue_size(self) -> int:
        """Get number of downloads in queue (pending/queued/downloading)."""
        from soulspot.infrastructure.persistence.models import DownloadModel

        stmt = select(func.count(DownloadModel.id)).where(
            DownloadModel.status.in_(["pending", "queued", "downloading"])
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def get_active_downloads_count(self) -> int:
        """Get number of actively downloading items."""
        from soulspot.infrastructure.persistence.models import DownloadModel

        stmt = select(func.count(DownloadModel.id)).where(
            DownloadModel.status == "downloading"
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    # =========================================================================
    # AGGREGATE STATS (Multiple counts in one call)
    # =========================================================================

    async def get_library_overview(self) -> dict[str, Any]:
        """Get comprehensive library overview with all main counts.

        Returns:
            Dict with all library counts
        """
        return {
            "total_tracks": await self.get_total_tracks(),
            "total_artists": await self.get_total_artists(),
            "total_albums": await self.get_total_albums(),
            "total_playlists": await self.get_total_playlists(),
            "downloads": await self.get_download_counts_by_status(),
            "unenriched_artists": await self.get_unenriched_artists_count(),
            "unenriched_albums": await self.get_unenriched_albums_count(),
            "pending_enrichment_candidates": await self.get_pending_enrichment_candidates_count(),
            "duplicate_candidates": await self.get_duplicate_counts_by_status(),
        }
