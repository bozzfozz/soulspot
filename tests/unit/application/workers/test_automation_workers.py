"""Unit tests for automation workers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.workers.automation_workers import (
    DiscographyWorker,
    QualityUpgradeWorker,
    WatchlistWorker,
)
from soulspot.domain.entities import AutomationTrigger


class TestWatchlistWorker:
    """Test WatchlistWorker class."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock(spec=AsyncSession)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.fixture
    def mock_spotify_client(self):
        """Create mock Spotify client."""
        return MagicMock()

    @pytest.fixture
    def worker(self, mock_session, mock_spotify_client):
        """Create WatchlistWorker instance."""
        return WatchlistWorker(
            session=mock_session,
            spotify_client=mock_spotify_client,
            check_interval_seconds=1,  # Short interval for testing
        )

    def test_init(self, worker, mock_session, mock_spotify_client):
        """Test WatchlistWorker initialization."""
        assert worker.session == mock_session
        assert worker.spotify_client == mock_spotify_client
        assert worker.check_interval_seconds == 1
        assert worker._running is False
        assert worker._task is None

    @pytest.mark.asyncio
    async def test_start(self, worker):
        """Test starting the worker."""
        await worker.start()

        assert worker._running is True
        assert worker._task is not None

        # Stop worker
        await worker.stop()

    @pytest.mark.asyncio
    async def test_start_already_running(self, worker):
        """Test starting worker when already running."""
        await worker.start()
        initial_task = worker._task

        # Try to start again
        await worker.start()

        # Should keep the same task
        assert worker._task == initial_task

        await worker.stop()

    @pytest.mark.asyncio
    async def test_stop(self, worker):
        """Test stopping the worker."""
        await worker.start()
        assert worker._running is True

        await worker.stop()

        assert worker._running is False
        # Task should be cancelled

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, worker):
        """Test stopping worker when not running."""
        # Should not raise error
        await worker.stop()
        assert worker._running is False

    @pytest.mark.asyncio
    async def test_check_watchlists_no_watchlists(self, worker):
        """Test checking watchlists when none are due."""
        # Mock token manager to return a valid token
        mock_token_manager = MagicMock()
        mock_token_manager.get_token_for_background = AsyncMock(
            return_value="valid-token"
        )
        worker._token_manager = mock_token_manager

        with patch.object(
            worker.watchlist_service, "list_due_for_check", new_callable=AsyncMock
        ) as mock_list:
            mock_list.return_value = []

            await worker._check_watchlists()

            mock_list.assert_called_once_with(limit=100)

    @pytest.mark.asyncio
    async def test_check_watchlists_with_watchlists_no_spotify(
        self, worker, mock_session
    ):
        """Test checking watchlists where artist has no Spotify URI.

        Hey future me - the code path is:
        1. Get watchlists due for check
        2. Get local artist via ArtistRepository
        3. If artist has no spotify_uri, log warning and continue (skip watchlist)
        So when artist has no spotify_uri, watchlist is NOT updated (skipped).
        """
        # Mock token manager to return a valid token
        mock_token_manager = MagicMock()
        mock_token_manager.get_token_for_background = AsyncMock(
            return_value="valid-token"
        )
        worker._token_manager = mock_token_manager

        # Create mock watchlist
        mock_watchlist = MagicMock()
        mock_watchlist.artist_id = MagicMock()
        mock_watchlist.artist_id.value = "artist-123"
        mock_watchlist.id = MagicMock()
        mock_watchlist.id.value = "watchlist-123"
        mock_watchlist.update_check = MagicMock()

        # Create mock artist WITHOUT spotify_uri (the "no spotify" case)
        mock_artist = MagicMock()
        mock_artist.id = "artist-123"
        mock_artist.name = "Test Artist"
        mock_artist.spotify_uri = None  # No Spotify URI

        # Mock the ArtistRepository class - patch at the source module
        mock_artist_repo = MagicMock()
        mock_artist_repo.get_by_id = AsyncMock(return_value=mock_artist)

        with (
            patch.object(
                worker.watchlist_service, "list_due_for_check", new_callable=AsyncMock
            ) as mock_list,
            patch(
                "soulspot.infrastructure.persistence.repositories.ArtistRepository",
                return_value=mock_artist_repo,
            ),
            patch(
                "soulspot.infrastructure.persistence.repositories.SpotifyBrowseRepository"
            ),
        ):
            mock_list.return_value = [mock_watchlist]

            await worker._check_watchlists()

            # Artist has no spotify_uri, so watchlist is SKIPPED (not updated)
            # The code does 'continue' when spotify_uri is None
            mock_watchlist.update_check.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_watchlists_with_auto_download(
        self, worker, mock_session, mock_spotify_client
    ):
        """Test checking watchlists with auto_download enabled.

        Hey future me - the code path is:
        1. Get watchlists due for check
        2. Get local artist via ArtistRepository (must have spotify_uri!)
        3. Check sync status via SpotifyBrowseRepository
        4. Get new albums from SpotifyBrowseRepository
        5. Trigger workflow for each new release if auto_download enabled
        """
        # Mock token manager to return a valid token
        mock_token_manager = MagicMock()
        mock_token_manager.get_token_for_background = AsyncMock(
            return_value="valid-token"
        )
        worker._token_manager = mock_token_manager

        # Create mock watchlist with auto_download enabled
        mock_watchlist = MagicMock()
        mock_watchlist.artist_id = MagicMock()
        mock_watchlist.artist_id.value = "artist-123"
        mock_watchlist.id = MagicMock()
        mock_watchlist.id.value = "watchlist-123"
        mock_watchlist.auto_download = True
        mock_watchlist.quality_profile = "high"
        mock_watchlist.update_check = MagicMock()
        mock_watchlist.last_checked_at = None  # No previous check

        # Create mock artist WITH spotify_uri (required for the happy path)
        mock_artist = MagicMock()
        mock_artist.id = "artist-123"
        mock_artist.name = "Test Artist"
        mock_artist.spotify_uri = "spotify:artist:abc123"

        # Mock the ArtistRepository class - patch at the source module
        mock_artist_repo = MagicMock()
        mock_artist_repo.get_by_id = AsyncMock(return_value=mock_artist)

        # Create mock album returned by SpotifyBrowseRepository
        mock_album = MagicMock()
        mock_album.spotify_id = "album-123"
        mock_album.name = "New Album"
        mock_album.album_type = "album"
        mock_album.release_date = "2025-11-01"
        mock_album.total_tracks = 10
        mock_album.image_url = "https://example.com/image.jpg"

        # Mock the SpotifyBrowseRepository class - patch at the source module
        mock_spotify_repo = MagicMock()
        mock_spotify_repo.get_artist_albums_sync_status = AsyncMock(
            return_value={"albums_synced": True, "album_count": 5}
        )
        mock_spotify_repo.get_new_albums_since = AsyncMock(return_value=[mock_album])

        with (
            patch.object(
                worker.watchlist_service, "list_due_for_check", new_callable=AsyncMock
            ) as mock_list,
            patch.object(
                worker.workflow_service, "trigger_workflow", new_callable=AsyncMock
            ) as mock_trigger,
            patch.object(
                worker.watchlist_service.repository, "update", new_callable=AsyncMock
            ),
            patch(
                "soulspot.infrastructure.persistence.repositories.ArtistRepository",
                return_value=mock_artist_repo,
            ),
            patch(
                "soulspot.infrastructure.persistence.repositories.SpotifyBrowseRepository",
                return_value=mock_spotify_repo,
            ),
        ):
            mock_list.return_value = [mock_watchlist]
            await worker._check_watchlists()

            # Should trigger workflow
            mock_trigger.assert_called_once()
            call_args = mock_trigger.call_args
            assert call_args[1]["trigger"] == AutomationTrigger.NEW_RELEASE
            assert "artist_id" in call_args[1]["context"]

    @pytest.mark.asyncio
    async def test_check_watchlists_error_handling(self, worker):
        """Test error handling in watchlist checking."""
        with patch.object(
            worker.watchlist_service, "list_due_for_check", new_callable=AsyncMock
        ) as mock_list:
            mock_list.side_effect = Exception("Test error")

            # Should not raise exception
            await worker._check_watchlists()

    @pytest.mark.asyncio
    async def test_trigger_automation(self, worker):
        """Test triggering automation for new releases."""
        mock_watchlist = MagicMock()
        mock_watchlist.artist_id = MagicMock()
        mock_watchlist.artist_id.value = "artist-123"
        mock_watchlist.id = MagicMock()
        mock_watchlist.id.value = "watchlist-123"
        mock_watchlist.quality_profile = "high"

        new_releases = [
            {"id": "release-1", "name": "Album 1"},
            {"id": "release-2", "name": "Album 2"},
        ]

        with patch.object(
            worker.workflow_service, "trigger_workflow", new_callable=AsyncMock
        ) as mock_trigger:
            await worker._trigger_automation(mock_watchlist, new_releases)

            # Should trigger workflow for each release
            assert mock_trigger.call_count == 2


class TestDiscographyWorker:
    """Test DiscographyWorker class."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock(spec=AsyncSession)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.fixture
    def mock_spotify_client(self):
        """Create mock Spotify client."""
        return MagicMock()

    @pytest.fixture
    def worker(self, mock_session, mock_spotify_client):
        """Create DiscographyWorker instance."""
        return DiscographyWorker(
            session=mock_session,
            spotify_client=mock_spotify_client,
            check_interval_seconds=1,
        )

    def test_init(self, worker, mock_session, mock_spotify_client):
        """Test DiscographyWorker initialization."""
        assert worker.session == mock_session
        assert worker.spotify_client == mock_spotify_client
        assert worker.check_interval_seconds == 1
        assert worker._running is False
        assert worker._task is None

    @pytest.mark.asyncio
    async def test_start(self, worker):
        """Test starting the worker."""
        await worker.start()

        assert worker._running is True
        assert worker._task is not None

        await worker.stop()

    @pytest.mark.asyncio
    async def test_start_already_running(self, worker):
        """Test starting when already running."""
        await worker.start()
        initial_task = worker._task

        await worker.start()

        assert worker._task == initial_task

        await worker.stop()

    @pytest.mark.asyncio
    async def test_stop(self, worker):
        """Test stopping the worker."""
        await worker.start()

        await worker.stop()

        assert worker._running is False

    @pytest.mark.asyncio
    async def test_check_discographies_error_handling(self, worker):
        """Test error handling in discography checking."""
        with patch(
            "soulspot.infrastructure.persistence.repositories.ArtistWatchlistRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.list_active = AsyncMock(side_effect=Exception("Test error"))

            # Should not raise exception
            await worker._check_discographies()


class TestQualityUpgradeWorker:
    """Test QualityUpgradeWorker class."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock(spec=AsyncSession)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.fixture
    def worker(self, mock_session):
        """Create QualityUpgradeWorker instance."""
        return QualityUpgradeWorker(
            session=mock_session,
            check_interval_seconds=1,
        )

    def test_init(self, worker, mock_session):
        """Test QualityUpgradeWorker initialization."""
        assert worker.session == mock_session
        assert worker.check_interval_seconds == 1
        assert worker._running is False
        assert worker._task is None

    @pytest.mark.asyncio
    async def test_start(self, worker):
        """Test starting the worker."""
        await worker.start()

        assert worker._running is True
        assert worker._task is not None

        await worker.stop()

    @pytest.mark.asyncio
    async def test_start_already_running(self, worker):
        """Test starting when already running."""
        await worker.start()
        initial_task = worker._task

        await worker.start()

        assert worker._task == initial_task

        await worker.stop()

    @pytest.mark.asyncio
    async def test_stop(self, worker):
        """Test stopping the worker."""
        await worker.start()

        await worker.stop()

        assert worker._running is False

    @pytest.mark.asyncio
    async def test_identify_upgrades_no_tracks(self, worker):
        """Test identifying upgrades when no tracks exist."""
        with patch(
            "soulspot.infrastructure.persistence.repositories.TrackRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.list_all = AsyncMock(return_value=[])

            # Should handle empty list gracefully
            await worker._identify_upgrades()

    @pytest.mark.asyncio
    async def test_identify_upgrades_error_handling(self, worker):
        """Test error handling in upgrade identification."""
        with patch(
            "soulspot.infrastructure.persistence.repositories.TrackRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.list_all = AsyncMock(side_effect=Exception("Test error"))

            # Should not raise exception
            await worker._identify_upgrades()

    @pytest.mark.asyncio
    async def test_run_loop_stops_on_flag(self, worker):
        """Test that run loop stops when _running is False."""
        # Start the worker
        worker._running = True

        # Mock check method to set _running to False after first call
        call_count = 0

        async def mock_check():
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                worker._running = False

        with patch.object(worker, "_identify_upgrades", side_effect=mock_check):
            await worker._run_loop()

        # Should have called check at least once
        assert call_count >= 1
