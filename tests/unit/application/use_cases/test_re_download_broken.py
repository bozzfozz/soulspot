"""Unit tests for re-download broken files use case."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from soulspot.application.use_cases.re_download_broken import (
    ReDownloadBrokenFilesUseCase,
)


class TestReDownloadBrokenFilesUseCase:
    """Test ReDownloadBrokenFilesUseCase."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock database session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.add = MagicMock()
        
        # Setup mock result that returns empty list
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_result.scalar_one_or_none.return_value = None
        
        session.execute = AsyncMock(return_value=mock_result)
        
        return session

    def test_init(self, mock_session: AsyncMock) -> None:
        """Test initialization."""
        use_case = ReDownloadBrokenFilesUseCase(mock_session)

        assert use_case.session == mock_session

    @pytest.mark.asyncio
    async def test_execute_no_broken_files(self, mock_session: AsyncMock) -> None:
        """Test execute with no broken files."""
        use_case = ReDownloadBrokenFilesUseCase(mock_session)

        result = await use_case.execute()

        assert result["queued_count"] == 0
        assert result["already_downloading"] == 0
        assert result["failed_to_queue"] == 0
        assert result["tracks"] == []

    @pytest.mark.asyncio
    async def test_get_broken_files_summary_no_broken(
        self, mock_session: AsyncMock
    ) -> None:
        """Test get summary with no broken files."""
        use_case = ReDownloadBrokenFilesUseCase(mock_session)

        summary = await use_case.get_broken_files_summary()

        assert summary["total_broken"] == 0
        assert summary["already_queued"] == 0
        assert summary["available_to_queue"] == 0
