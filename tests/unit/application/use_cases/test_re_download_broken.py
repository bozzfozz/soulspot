"""Unit tests for re-download broken files use case."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.use_cases.re_download_broken import (
    ReDownloadBrokenFilesUseCase,
)
from soulspot.domain.entities import DownloadStatus
from soulspot.infrastructure.persistence.models import DownloadModel, TrackModel


@pytest.mark.asyncio
class TestReDownloadBrokenFilesUseCase:
    """Test ReDownloadBrokenFilesUseCase."""

    async def test_init(self, db_session: AsyncSession) -> None:
        """Test initialization."""
        use_case = ReDownloadBrokenFilesUseCase(db_session)

        assert use_case.session == db_session

    async def test_execute_no_broken_files(self, db_session: AsyncSession) -> None:
        """Test execute with no broken files."""
        use_case = ReDownloadBrokenFilesUseCase(db_session)

        result = await use_case.execute()

        assert result["queued_count"] == 0
        assert result["already_downloading"] == 0
        assert result["failed_to_queue"] == 0
        assert result["tracks"] == []

    async def test_get_broken_files_summary_no_broken(
        self, db_session: AsyncSession
    ) -> None:
        """Test get summary with no broken files."""
        use_case = ReDownloadBrokenFilesUseCase(db_session)

        summary = await use_case.get_broken_files_summary()

        assert summary["total_broken"] == 0
        assert summary["already_queued"] == 0
        assert summary["available_to_queue"] == 0

    async def test_execute_queues_broken_files(self, db_session: AsyncSession) -> None:
        """Test execute queues broken files for download."""
        # Create broken track
        track = TrackModel(
            title="Broken Track",
            artist_id="artist-1",
            is_broken=True,
            file_path="/path/to/broken.mp3",
        )
        db_session.add(track)
        await db_session.commit()
        await db_session.refresh(track)

        use_case = ReDownloadBrokenFilesUseCase(db_session)

        result = await use_case.execute(priority=1)

        assert result["queued_count"] == 1
        assert result["already_downloading"] == 0
        assert result["failed_to_queue"] == 0
        assert len(result["tracks"]) == 1
        assert result["tracks"][0]["track_id"] == track.id
        assert result["tracks"][0]["title"] == "Broken Track"
        assert result["tracks"][0]["priority"] == 1

        # Verify download was created
        download_stmt = select(DownloadModel).where(DownloadModel.track_id == track.id)
        download_result = await db_session.execute(download_stmt)
        download = download_result.scalar_one()

        assert download is not None
        assert download.status == DownloadStatus.QUEUED.value
        assert download.priority == 1

    async def test_execute_skips_already_downloading(
        self, db_session: AsyncSession
    ) -> None:
        """Test execute skips tracks already in download queue."""
        # Create broken track with existing download
        track = TrackModel(
            title="Broken Track",
            artist_id="artist-1",
            is_broken=True,
        )
        db_session.add(track)
        await db_session.flush()

        download = DownloadModel(
            track_id=track.id,
            status=DownloadStatus.DOWNLOADING.value,
        )
        db_session.add(download)
        await db_session.commit()

        use_case = ReDownloadBrokenFilesUseCase(db_session)

        result = await use_case.execute()

        assert result["queued_count"] == 0
        assert result["already_downloading"] == 1
        assert result["failed_to_queue"] == 0
        assert result["tracks"] == []

    async def test_execute_updates_failed_downloads(
        self, db_session: AsyncSession
    ) -> None:
        """Test execute updates existing failed downloads."""
        # Create broken track with failed download
        track = TrackModel(
            title="Failed Track",
            artist_id="artist-1",
            is_broken=True,
        )
        db_session.add(track)
        await db_session.flush()

        download = DownloadModel(
            track_id=track.id,
            status=DownloadStatus.FAILED.value,
            error_message="Previous error",
        )
        db_session.add(download)
        await db_session.commit()
        await db_session.refresh(download)

        use_case = ReDownloadBrokenFilesUseCase(db_session)

        result = await use_case.execute(priority=0)

        assert result["queued_count"] == 1
        assert result["already_downloading"] == 0

        # Verify download was updated
        await db_session.refresh(download)
        assert download.status == DownloadStatus.QUEUED.value
        assert download.priority == 0
        assert download.error_message is None
        assert download.progress_percent == 0.0

    async def test_execute_respects_max_files(self, db_session: AsyncSession) -> None:
        """Test execute respects max_files limit."""
        # Create multiple broken tracks
        for i in range(5):
            track = TrackModel(
                title=f"Broken Track {i}",
                artist_id="artist-1",
                is_broken=True,
            )
            db_session.add(track)

        await db_session.commit()

        use_case = ReDownloadBrokenFilesUseCase(db_session)

        result = await use_case.execute(max_files=3)

        assert result["queued_count"] == 3
        assert len(result["tracks"]) == 3

    async def test_get_broken_files_summary_with_broken(
        self, db_session: AsyncSession
    ) -> None:
        """Test get summary with broken files."""
        # Create broken tracks
        track1 = TrackModel(title="Broken 1", artist_id="artist-1", is_broken=True)
        track2 = TrackModel(title="Broken 2", artist_id="artist-1", is_broken=True)
        db_session.add_all([track1, track2])
        await db_session.flush()

        # One is already queued
        download = DownloadModel(
            track_id=track1.id,
            status=DownloadStatus.QUEUED.value,
        )
        db_session.add(download)
        await db_session.commit()

        use_case = ReDownloadBrokenFilesUseCase(db_session)

        summary = await use_case.get_broken_files_summary()

        assert summary["total_broken"] == 2
        assert summary["already_queued"] == 1
        assert summary["available_to_queue"] == 1

    async def test_execute_with_priority_levels(self, db_session: AsyncSession) -> None:
        """Test execute with different priority levels."""
        track = TrackModel(
            title="Broken Track",
            artist_id="artist-1",
            is_broken=True,
        )
        db_session.add(track)
        await db_session.commit()
        await db_session.refresh(track)

        use_case = ReDownloadBrokenFilesUseCase(db_session)

        # Test with high priority (0)
        result = await use_case.execute(priority=0)

        assert result["queued_count"] == 1

        # Verify download was created with correct priority
        download_stmt = select(DownloadModel).where(DownloadModel.track_id == track.id)
        download_result = await db_session.execute(download_stmt)
        download = download_result.scalar_one()

        assert download.priority == 0
