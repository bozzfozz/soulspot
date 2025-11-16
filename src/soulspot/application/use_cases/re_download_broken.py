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

    def __init__(self, session: AsyncSession) -> None:
        """Initialize use case.

        Args:
            session: Database session
        """
        self.session = session

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

    async def get_broken_files_summary(self) -> dict[str, Any]:
        """Get summary of broken files.

        Returns:
            Summary of broken files
        """
        # Count total broken files
        stmt = select(TrackModel).where(TrackModel.is_broken == True)  # noqa: E712
        result = await self.session.execute(stmt)
        broken_tracks = result.scalars().all()

        total_broken = len(broken_tracks)

        # Check how many are already in download queue
        queued_count = 0
        for track in broken_tracks:
            download_stmt = select(DownloadModel).where(
                DownloadModel.track_id == track.id
            )
            download_result = await self.session.execute(download_stmt)
            download = download_result.scalar_one_or_none()

            if download and download.status in (
                DownloadStatus.PENDING.value,
                DownloadStatus.QUEUED.value,
                DownloadStatus.DOWNLOADING.value,
            ):
                queued_count += 1

        return {
            "total_broken": total_broken,
            "already_queued": queued_count,
            "available_to_queue": total_broken - queued_count,
        }
