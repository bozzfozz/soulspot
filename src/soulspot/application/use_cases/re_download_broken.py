"""Use case for re-downloading broken/corrupted files."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.entities import DownloadStatus
from soulspot.infrastructure.persistence.models import DownloadModel, TrackModel

logger = logging.getLogger(__name__)


class ReDownloadBrokenFilesUseCase:
    """Use case for re-downloading broken/corrupted files."""

    # Hey future me, this use case is straightforward - just store the DB session. No fancy setup needed.
    # The session is passed in (dependency injection) so we can test this without a real DB. Don't create
    # the session here or you'll have lifetime management headaches!
    def __init__(self, session: AsyncSession) -> None:
        """Initialize use case.

        Args:
            session: Database session
        """
        self.session = session

    # Yo future me, this is the MEAT of the use case - find all tracks marked is_broken=True and queue
    # them for re-download. The priority param (0-2) lets urgent files jump the queue. max_files limits
    # how many to queue at once - IMPORTANT to prevent queuing 10,000 files and overwhelming the system!
    # We check EACH track for existing downloads - if already queued/in-progress, skip it! If download
    # failed before, we REUSE the row and reset status to QUEUED (preserves history). The commit happens
    # AFTER the loop - if anything fails mid-loop, whole thing rolls back (all-or-nothing). This can be
    # SLOW for hundreds of tracks - consider pagination or background job for large batches!
    async def execute(
        self, priority: int = 0, max_files: int | None = None
    ) -> dict[str, Any]:
        """Queue re-download of broken files.

        Args:
            priority: Priority for re-downloads (0=highest, 1=medium, 2=low)
            max_files: Maximum number of files to queue (None = all)

        Returns:
            Summary of queued downloads
        """
        logger.info(
            "Starting broken files re-download",
            extra={"priority": priority, "max_files": max_files},
        )

        # Find all broken files
        stmt = select(TrackModel).where(
            TrackModel.is_broken == True  # noqa: E712
        )

        if max_files:
            stmt = stmt.limit(max_files)

        result = await self.session.execute(stmt)
        broken_tracks = result.scalars().all()

        if not broken_tracks:
            logger.info("No broken files found")
            return {
                "queued_count": 0,
                "already_downloading": 0,
                "failed_to_queue": 0,
                "tracks": [],
            }

        queued_count = 0
        already_downloading = 0
        failed_to_queue = 0
        queued_tracks = []

        for track in broken_tracks:
            try:
                # Check if there's already a download entry for this track
                existing_download_stmt = select(DownloadModel).where(
                    DownloadModel.track_id == track.id
                )
                existing_result = await self.session.execute(existing_download_stmt)
                existing_download = existing_result.scalar_one_or_none()

                if existing_download:
                    # Check if it's already being downloaded
                    if existing_download.status in (
                        DownloadStatus.PENDING.value,
                        DownloadStatus.QUEUED.value,
                        DownloadStatus.DOWNLOADING.value,
                    ):
                        logger.info(
                            f"Track {track.title} already in download queue",
                            extra={
                                "track_id": track.id,
                                "status": existing_download.status,
                            },
                        )
                        already_downloading += 1
                        continue

                    # Update existing failed/cancelled download
                    existing_download.status = DownloadStatus.QUEUED.value
                    existing_download.priority = priority
                    existing_download.error_message = None
                    existing_download.progress_percent = 0.0

                    logger.info(
                        f"Updated download for broken track: {track.title}",
                        extra={"track_id": track.id, "priority": priority},
                    )
                else:
                    # Create new download entry
                    new_download = DownloadModel(
                        track_id=track.id,
                        status=DownloadStatus.QUEUED.value,
                        priority=priority,
                    )
                    self.session.add(new_download)

                    logger.info(
                        f"Created download for broken track: {track.title}",
                        extra={"track_id": track.id, "priority": priority},
                    )

                queued_count += 1
                queued_tracks.append(
                    {
                        "track_id": track.id,
                        "title": track.title,
                        "file_path": track.file_path,
                        "priority": priority,
                    }
                )

            except Exception as e:
                logger.error(
                    f"Failed to queue download for track {track.title}: {e}",
                    extra={
                        "track_id": track.id,
                        "title": track.title,
                        "error": str(e),
                    },
                )
                failed_to_queue += 1
                continue

        # Commit the changes
        await self.session.commit()

        logger.info(
            f"Re-download queued: {queued_count} tracks",
            extra={
                "queued_count": queued_count,
                "already_downloading": already_downloading,
                "failed_to_queue": failed_to_queue,
            },
        )

        return {
            "queued_count": queued_count,
            "already_downloading": already_downloading,
            "failed_to_queue": failed_to_queue,
            "tracks": queued_tracks,
        }

    # Hey future me, optimized summary with JOIN instead of O(n) queries! Uses LEFT OUTER JOIN
    # because not all broken tracks have downloads yet. The WHERE filter on download status happens
    # in SQL (efficient) instead of Python loop. COUNT with CASE gives us queued count in one query.
    # Result is FAST even with thousands of broken tracks - single DB round trip!
    async def get_broken_files_summary(self) -> dict[str, Any]:
        """Get summary of broken files.

        Optimized with JOIN to avoid N+1 queries.

        Returns:
            Summary of broken files
        """
        from sqlalchemy import and_, case, func

        # Single query with LEFT JOIN to get all broken tracks + their download status
        # COUNT with CASE filters active downloads in SQL instead of Python loop
        stmt = (
            select(
                func.count(TrackModel.id).label("total_broken"),
                func.count(
                    case(
                        (
                            DownloadModel.status.in_(
                                [
                                    DownloadStatus.PENDING.value,
                                    DownloadStatus.QUEUED.value,
                                    DownloadStatus.DOWNLOADING.value,
                                ]
                            ),
                            1,
                        ),
                        else_=None,
                    )
                ).label("already_queued"),
            )
            .select_from(TrackModel)
            .outerjoin(DownloadModel, TrackModel.id == DownloadModel.track_id)
            .where(TrackModel.is_broken == True)  # noqa: E712
        )

        result = await self.session.execute(stmt)
        row = result.one()

        total_broken = row.total_broken
        already_queued = row.already_queued

        return {
            "total_broken": total_broken,
            "already_queued": already_queued,
            "available_to_queue": total_broken - already_queued,
        }
