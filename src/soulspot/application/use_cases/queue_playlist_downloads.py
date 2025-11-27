"""Use case for queueing playlist tracks for download."""

from dataclasses import dataclass

from soulspot.application.use_cases import UseCase
from soulspot.application.workers.job_queue import JobQueue, JobType
from soulspot.domain.value_objects import PlaylistId
from soulspot.infrastructure.persistence.repositories import (
    PlaylistRepository,
    TrackRepository,
)


@dataclass
class QueuePlaylistDownloadsRequest:
    """Request to queue playlist tracks for download."""

    playlist_id: str
    quality_filter: str | None = None  # "flac", "320", "any"
    auto_start: bool = True


@dataclass
class QueuePlaylistDownloadsResponse:
    """Response from queueing playlist downloads."""

    queued_count: int
    already_downloaded: int
    skipped_count: int
    failed_count: int
    job_ids: list[str]
    errors: list[str]


class QueuePlaylistDownloadsUseCase(UseCase):
    """Queue all missing tracks from a playlist for download.

    Hey future me - this is the SMART DOWNLOAD QUEUE feature! When user imports a playlist,
    they can auto-queue all missing tracks (tracks without file_path) for download. The
    quality_filter lets them choose: "flac" (lossless only), "320" (320kbps MP3+), or "any"
    (download whatever is available). This integrates with the existing JobQueue system that
    handles Soulseek downloads. The use case is idempotent - tracks already downloaded are
    skipped. Returns job IDs so UI can track download progress!
    """

    def __init__(
        self,
        playlist_repository: PlaylistRepository,
        track_repository: TrackRepository,
        job_queue: JobQueue,
    ) -> None:
        """Initialize the use case.

        Args:
            playlist_repository: Repository for playlist operations
            track_repository: Repository for track operations
            job_queue: Job queue for download operations
        """
        self._playlist_repository = playlist_repository
        self._track_repository = track_repository
        self._job_queue = job_queue

    # Hey future me, this checks if track meets quality requirements! The quality_filter
    # param determines what we're willing to download. "flac" = lossless only (FLAC/ALAC),
    # "320" = high quality (320kbps MP3 or better), "any" = download anything available.
    # For now, we accept all tracks (quality checking happens in Soulseek search), but
    # this is where you'd add logic to skip tracks based on existing metadata if needed.
    @staticmethod
    def _meets_quality_filter(_quality_filter: str | None) -> bool:  # noqa: ARG004
        """Check if track meets quality filter requirements.

        Args:
            _quality_filter: Quality filter ("flac", "320", "any", or None)

        Returns:
            True if track should be queued, False otherwise
        """
        # For now, accept all tracks - quality filtering happens in Soulseek search
        # Future: Could check track.bitrate or track.format if we store that metadata
        return True

    async def execute(
        self, request: QueuePlaylistDownloadsRequest
    ) -> QueuePlaylistDownloadsResponse:
        """Execute the queue playlist downloads use case.

        Args:
            request: Request containing playlist ID and quality filter

        Returns:
            Response with queue statistics and job IDs
        """
        errors: list[str] = []
        queued_count = 0
        already_downloaded = 0
        skipped_count = 0
        failed_count = 0
        job_ids: list[str] = []

        # 1. Get playlist
        try:
            playlist_id = PlaylistId.from_string(request.playlist_id)
            playlist = await self._playlist_repository.get_by_id(playlist_id)

            if not playlist:
                errors.append(f"Playlist not found: {request.playlist_id}")
                return QueuePlaylistDownloadsResponse(
                    queued_count=0,
                    already_downloaded=0,
                    skipped_count=0,
                    failed_count=1,
                    job_ids=[],
                    errors=errors,
                )
        except Exception as e:
            errors.append(f"Failed to get playlist: {e}")
            return QueuePlaylistDownloadsResponse(
                queued_count=0,
                already_downloaded=0,
                skipped_count=0,
                failed_count=1,
                job_ids=[],
                errors=errors,
            )

        # 2. Get all tracks in playlist
        if not playlist.track_ids:
            return QueuePlaylistDownloadsResponse(
                queued_count=0,
                already_downloaded=0,
                skipped_count=0,
                failed_count=0,
                job_ids=[],
                errors=["Playlist has no tracks"],
            )

        # 3. Process each track
        for track_id in playlist.track_ids:
            try:
                track = await self._track_repository.get_by_id(track_id)

                if not track:
                    skipped_count += 1
                    errors.append(f"Track not found: {track_id}")
                    continue

                # Skip if already downloaded
                if track.file_path:
                    already_downloaded += 1
                    continue

                # Check quality filter
                if not self._meets_quality_filter(request.quality_filter):
                    skipped_count += 1
                    continue

                # Queue download job
                job_id = await self._job_queue.enqueue(
                    job_type=JobType.DOWNLOAD,
                    payload={
                        "track_id": str(track.id.value),
                        "quality_preference": request.quality_filter or "any",
                    },
                    priority=10,  # Higher priority for user-initiated downloads
                )

                job_ids.append(job_id)
                queued_count += 1

            except Exception as e:
                failed_count += 1
                errors.append(f"Failed to queue track {track_id}: {e}")

        return QueuePlaylistDownloadsResponse(
            queued_count=queued_count,
            already_downloaded=already_downloaded,
            skipped_count=skipped_count,
            failed_count=failed_count,
            job_ids=job_ids,
            errors=errors,
        )
