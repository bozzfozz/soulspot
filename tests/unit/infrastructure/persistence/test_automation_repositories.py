"""Unit tests for automation-related repositories."""

import pytest
from datetime import UTC, datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from soulspot.domain.entities import (
    ArtistWatchlist,
    FilterRule,
    AutomationRule,
    QualityUpgradeCandidate,
    WatchlistStatus,
    FilterType,
    FilterTarget,
    AutomationTrigger,
    AutomationAction,
)
from soulspot.domain.value_objects import (
    WatchlistId,
    ArtistId,
    FilterRuleId,
    AutomationRuleId,
    TrackId,
    DownloadId,
)
from soulspot.infrastructure.persistence.repositories import (
    ArtistWatchlistRepository,
    FilterRuleRepository,
    AutomationRuleRepository,
    QualityUpgradeCandidateRepository,
)
from soulspot.infrastructure.persistence.models import Base


@pytest.fixture(scope="function")
async def async_session():
    """Create an async test database session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    # Create tables with checkfirst to avoid duplicate index errors
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, checkfirst=True))
    
    # Create session
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()
        await session.close()
    
    await engine.dispose()


class TestArtistWatchlistRepository:
    """Test ArtistWatchlistRepository."""

    @pytest.mark.asyncio
    async def test_add_and_get_watchlist(self, async_session: AsyncSession) -> None:
        """Test adding and retrieving a watchlist."""
        repo = ArtistWatchlistRepository(async_session)
        
        watchlist = ArtistWatchlist(
            id=WatchlistId.generate(),
            artist_id=ArtistId.generate(),
            status=WatchlistStatus.ACTIVE,
            check_frequency_hours=24,
            auto_download=True,
            quality_profile="high",
            last_checked_at=None,
            last_release_date=None,
            total_releases_found=0,
            total_downloads_triggered=0,
        )
        
        await repo.add(watchlist)
        await async_session.commit()
        
        retrieved = await repo.get_by_id(watchlist.id)
        assert retrieved is not None
        assert retrieved.id == watchlist.id
        assert retrieved.artist_id == watchlist.artist_id
        assert retrieved.status == WatchlistStatus.ACTIVE
        assert retrieved.check_frequency_hours == 24
        assert retrieved.auto_download is True
        assert retrieved.quality_profile == "high"

    @pytest.mark.asyncio
    async def test_get_by_artist_id(self, async_session: AsyncSession) -> None:
        """Test retrieving watchlist by artist ID."""
        repo = ArtistWatchlistRepository(async_session)
        artist_id = ArtistId.generate()
        
        watchlist = ArtistWatchlist(
            id=WatchlistId.generate(),
            artist_id=artist_id,
            status=WatchlistStatus.ACTIVE,
            check_frequency_hours=24,
            auto_download=True,
            quality_profile="high",
            last_checked_at=None,
            last_release_date=None,
            total_releases_found=0,
            total_downloads_triggered=0,
        )
        
        await repo.add(watchlist)
        await async_session.commit()
        
        retrieved = await repo.get_by_artist_id(artist_id)
        assert retrieved is not None
        assert retrieved.artist_id == artist_id

    @pytest.mark.asyncio
    async def test_update_watchlist(self, async_session: AsyncSession) -> None:
        """Test updating a watchlist."""
        repo = ArtistWatchlistRepository(async_session)
        
        watchlist = ArtistWatchlist(
            id=WatchlistId.generate(),
            artist_id=ArtistId.generate(),
            status=WatchlistStatus.ACTIVE,
            check_frequency_hours=24,
            auto_download=True,
            quality_profile="high",
            last_checked_at=None,
            last_release_date=None,
            total_releases_found=0,
            total_downloads_triggered=0,
        )
        
        await repo.add(watchlist)
        await async_session.commit()
        
        # Update the watchlist
        watchlist.update_check(releases_found=5, downloads_triggered=3)
        await repo.update(watchlist)
        await async_session.commit()
        
        retrieved = await repo.get_by_id(watchlist.id)
        assert retrieved is not None
        assert retrieved.total_releases_found == 5
        assert retrieved.total_downloads_triggered == 3
        assert retrieved.last_checked_at is not None

    @pytest.mark.asyncio
    async def test_delete_watchlist(self, async_session: AsyncSession) -> None:
        """Test deleting a watchlist."""
        repo = ArtistWatchlistRepository(async_session)
        
        watchlist = ArtistWatchlist(
            id=WatchlistId.generate(),
            artist_id=ArtistId.generate(),
            status=WatchlistStatus.ACTIVE,
            check_frequency_hours=24,
            auto_download=True,
            quality_profile="high",
            last_checked_at=None,
            last_release_date=None,
            total_releases_found=0,
            total_downloads_triggered=0,
        )
        
        await repo.add(watchlist)
        await async_session.commit()
        
        await repo.delete(watchlist.id)
        await async_session.commit()
        
        retrieved = await repo.get_by_id(watchlist.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_list_all_watchlists(self, async_session: AsyncSession) -> None:
        """Test listing all watchlists."""
        repo = ArtistWatchlistRepository(async_session)
        
        # Create multiple watchlists
        for i in range(3):
            watchlist = ArtistWatchlist(
                id=WatchlistId.generate(),
                artist_id=ArtistId.generate(),
                status=WatchlistStatus.ACTIVE,
                check_frequency_hours=24,
                auto_download=True,
                quality_profile="high",
                last_checked_at=None,
                last_release_date=None,
                total_releases_found=0,
                total_downloads_triggered=0,
            )
            await repo.add(watchlist)
        
        await async_session.commit()
        
        watchlists = await repo.list_all(limit=10, offset=0)
        assert len(watchlists) == 3


class TestFilterRuleRepository:
    """Test FilterRuleRepository."""

    @pytest.mark.asyncio
    async def test_add_and_get_filter_rule(self, async_session: AsyncSession) -> None:
        """Test adding and retrieving a filter rule."""
        repo = FilterRuleRepository(async_session)
        
        filter_rule = FilterRule(
            id=FilterRuleId.generate(),
            name="Test Filter",
            filter_type=FilterType.WHITELIST,
            target=FilterTarget.KEYWORD,
            pattern="test*",
            is_regex=True,
            enabled=True,
            priority=1,
            description="Test filter rule",
        )
        
        await repo.add(filter_rule)
        await async_session.commit()
        
        retrieved = await repo.get_by_id(filter_rule.id)
        assert retrieved is not None
        assert retrieved.id == filter_rule.id
        assert retrieved.name == "Test Filter"
        assert retrieved.filter_type == FilterType.WHITELIST
        assert retrieved.target == FilterTarget.KEYWORD
        assert retrieved.pattern == "test*"
        assert retrieved.is_regex is True

    @pytest.mark.asyncio
    async def test_list_by_type(self, async_session: AsyncSession) -> None:
        """Test listing filter rules by type."""
        repo = FilterRuleRepository(async_session)
        
        # Create whitelist and blacklist filters
        whitelist = FilterRule(
            id=FilterRuleId.generate(),
            name="Whitelist Filter",
            filter_type=FilterType.WHITELIST,
            target=FilterTarget.KEYWORD,
            pattern="good*",
            is_regex=True,
            enabled=True,
            priority=1,
        )
        
        blacklist = FilterRule(
            id=FilterRuleId.generate(),
            name="Blacklist Filter",
            filter_type=FilterType.BLACKLIST,
            target=FilterTarget.USER,
            pattern="bad*",
            is_regex=True,
            enabled=True,
            priority=1,
        )
        
        await repo.add(whitelist)
        await repo.add(blacklist)
        await async_session.commit()
        
        whitelists = await repo.list_by_type(FilterType.WHITELIST.value)
        assert len(whitelists) == 1
        assert whitelists[0].filter_type == FilterType.WHITELIST
        
        blacklists = await repo.list_by_type(FilterType.BLACKLIST.value)
        assert len(blacklists) == 1
        assert blacklists[0].filter_type == FilterType.BLACKLIST

    @pytest.mark.asyncio
    async def test_list_enabled(self, async_session: AsyncSession) -> None:
        """Test listing enabled filter rules."""
        repo = FilterRuleRepository(async_session)
        
        # Create enabled and disabled filters
        enabled = FilterRule(
            id=FilterRuleId.generate(),
            name="Enabled Filter",
            filter_type=FilterType.WHITELIST,
            target=FilterTarget.KEYWORD,
            pattern="test*",
            is_regex=True,
            enabled=True,
            priority=1,
        )
        
        disabled = FilterRule(
            id=FilterRuleId.generate(),
            name="Disabled Filter",
            filter_type=FilterType.BLACKLIST,
            target=FilterTarget.USER,
            pattern="bad*",
            is_regex=True,
            enabled=False,
            priority=1,
        )
        
        await repo.add(enabled)
        await repo.add(disabled)
        await async_session.commit()
        
        enabled_rules = await repo.list_enabled()
        assert len(enabled_rules) == 1
        assert enabled_rules[0].enabled is True


class TestAutomationRuleRepository:
    """Test AutomationRuleRepository."""

    @pytest.mark.asyncio
    async def test_add_and_get_automation_rule(
        self, async_session: AsyncSession
    ) -> None:
        """Test adding and retrieving an automation rule."""
        repo = AutomationRuleRepository(async_session)
        
        rule = AutomationRule(
            id=AutomationRuleId.generate(),
            name="Test Automation",
            trigger=AutomationTrigger.NEW_RELEASE,
            action=AutomationAction.SEARCH_AND_DOWNLOAD,
            enabled=True,
            priority=1,
            quality_profile="high",
            apply_filters=True,
            auto_process=True,
            description="Test automation rule",
            last_triggered_at=None,
            total_executions=0,
            successful_executions=0,
            failed_executions=0,
        )
        
        await repo.add(rule)
        await async_session.commit()
        
        retrieved = await repo.get_by_id(rule.id)
        assert retrieved is not None
        assert retrieved.id == rule.id
        assert retrieved.name == "Test Automation"
        assert retrieved.trigger == AutomationTrigger.NEW_RELEASE
        assert retrieved.action == AutomationAction.SEARCH_AND_DOWNLOAD

    @pytest.mark.asyncio
    async def test_list_by_trigger(self, async_session: AsyncSession) -> None:
        """Test listing automation rules by trigger."""
        repo = AutomationRuleRepository(async_session)
        
        # Create rules with different triggers
        new_release_rule = AutomationRule(
            id=AutomationRuleId.generate(),
            name="New Release Rule",
            trigger=AutomationTrigger.NEW_RELEASE,
            action=AutomationAction.SEARCH_AND_DOWNLOAD,
            enabled=True,
            priority=1,
            quality_profile="high",
            apply_filters=True,
            auto_process=True,
            last_triggered_at=None,
            total_executions=0,
            successful_executions=0,
            failed_executions=0,
        )
        
        quality_rule = AutomationRule(
            id=AutomationRuleId.generate(),
            name="Quality Upgrade Rule",
            trigger=AutomationTrigger.QUALITY_UPGRADE,
            action=AutomationAction.NOTIFY_ONLY,
            enabled=True,
            priority=1,
            quality_profile="lossless",
            apply_filters=True,
            auto_process=True,
            last_triggered_at=None,
            total_executions=0,
            successful_executions=0,
            failed_executions=0,
        )
        
        await repo.add(new_release_rule)
        await repo.add(quality_rule)
        await async_session.commit()
        
        new_release_rules = await repo.list_by_trigger(AutomationTrigger.NEW_RELEASE.value)
        assert len(new_release_rules) == 1
        assert new_release_rules[0].trigger == AutomationTrigger.NEW_RELEASE

    @pytest.mark.asyncio
    async def test_update_execution_stats(self, async_session: AsyncSession) -> None:
        """Test updating execution statistics."""
        repo = AutomationRuleRepository(async_session)
        
        rule = AutomationRule(
            id=AutomationRuleId.generate(),
            name="Test Rule",
            trigger=AutomationTrigger.NEW_RELEASE,
            action=AutomationAction.SEARCH_AND_DOWNLOAD,
            enabled=True,
            priority=1,
            quality_profile="high",
            apply_filters=True,
            auto_process=True,
            last_triggered_at=None,
            total_executions=0,
            successful_executions=0,
            failed_executions=0,
        )
        
        await repo.add(rule)
        await async_session.commit()
        
        # Record executions
        rule.record_execution(success=True)
        rule.record_execution(success=True)
        rule.record_execution(success=False)
        
        await repo.update(rule)
        await async_session.commit()
        
        retrieved = await repo.get_by_id(rule.id)
        assert retrieved is not None
        assert retrieved.total_executions == 3
        assert retrieved.successful_executions == 2
        assert retrieved.failed_executions == 1


class TestQualityUpgradeCandidateRepository:
    """Test QualityUpgradeCandidateRepository."""

    @pytest.mark.asyncio
    async def test_add_and_get_candidate(self, async_session: AsyncSession) -> None:
        """Test adding and retrieving a quality upgrade candidate."""
        repo = QualityUpgradeCandidateRepository(async_session)
        
        candidate = QualityUpgradeCandidate(
            id="test-candidate-1",
            track_id=TrackId.generate(),
            current_bitrate=192,
            current_format="mp3",
            target_bitrate=320,
            target_format="mp3",
            improvement_score=0.5,
            detected_at=datetime.now(UTC),
            processed=False,
            download_id=None,
        )
        
        await repo.add(candidate)
        await async_session.commit()
        
        retrieved = await repo.get_by_id(candidate.id)
        assert retrieved is not None
        assert retrieved.id == candidate.id
        assert retrieved.current_bitrate == 192
        assert retrieved.target_bitrate == 320
        assert retrieved.improvement_score == 0.5

    @pytest.mark.asyncio
    async def test_list_unprocessed(self, async_session: AsyncSession) -> None:
        """Test listing unprocessed candidates."""
        repo = QualityUpgradeCandidateRepository(async_session)
        
        # Create processed and unprocessed candidates
        unprocessed = QualityUpgradeCandidate(
            id="unprocessed-1",
            track_id=TrackId.generate(),
            current_bitrate=128,
            current_format="mp3",
            target_bitrate=320,
            target_format="flac",
            improvement_score=0.8,
            detected_at=datetime.now(UTC),
            processed=False,
            download_id=None,
        )
        
        processed = QualityUpgradeCandidate(
            id="processed-1",
            track_id=TrackId.generate(),
            current_bitrate=192,
            current_format="mp3",
            target_bitrate=320,
            target_format="mp3",
            improvement_score=0.3,
            detected_at=datetime.now(UTC),
            processed=True,
            download_id=DownloadId.generate(),
        )
        
        await repo.add(unprocessed)
        await repo.add(processed)
        await async_session.commit()
        
        candidates = await repo.list_unprocessed(limit=10)
        assert len(candidates) == 1
        assert candidates[0].processed is False

    @pytest.mark.asyncio
    async def test_mark_as_processed(self, async_session: AsyncSession) -> None:
        """Test marking a candidate as processed."""
        repo = QualityUpgradeCandidateRepository(async_session)
        
        candidate = QualityUpgradeCandidate(
            id="test-candidate-2",
            track_id=TrackId.generate(),
            current_bitrate=192,
            current_format="mp3",
            target_bitrate=320,
            target_format="flac",
            improvement_score=0.6,
            detected_at=datetime.now(UTC),
            processed=False,
            download_id=None,
        )
        
        await repo.add(candidate)
        await async_session.commit()
        
        download_id = DownloadId.generate()
        candidate.mark_processed(download_id)
        
        await repo.update(candidate)
        await async_session.commit()
        
        retrieved = await repo.get_by_id(candidate.id)
        assert retrieved is not None
        assert retrieved.processed is True
        assert retrieved.download_id == download_id
