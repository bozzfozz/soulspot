"""Stats and trends API endpoints for dashboard."""

# Hey future me - dieser Router liefert Dashboard-Stats und Trend-Daten!
# Die Trends zeigen Änderungen seit gestern/letzter Woche, z.B. "+12 heute ↑".
# Wird per HTMX vom Dashboard gepollt oder beim Page Load gefetcht.

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter()


class TrendData(BaseModel):
    """Trend information for a single metric."""

    current: int = Field(description="Current value")
    previous: int = Field(description="Value from comparison period")
    change: int = Field(description="Absolute change (current - previous)")
    change_percent: float = Field(description="Percentage change")
    direction: str = Field(description="'up', 'down', or 'stable'")
    period: str = Field(description="Comparison period (e.g., 'today', 'week')")


class StatsWithTrends(BaseModel):
    """Dashboard stats with trend indicators."""

    # Current counts
    playlists: int = Field(description="Total playlists")
    tracks: int = Field(description="Total tracks in playlists")
    tracks_downloaded: int = Field(description="Tracks with local files")
    downloads_completed: int = Field(description="Total completed downloads")
    downloads_failed: int = Field(description="Failed downloads needing attention")
    queue_size: int = Field(description="Pending/queued downloads")
    active_downloads: int = Field(description="Currently downloading")

    # Spotify stats
    spotify_artists: int = Field(description="Synced Spotify artists")
    spotify_albums: int = Field(description="Synced Spotify albums")
    spotify_tracks: int = Field(description="Synced Spotify tracks")

    # Trends (optional - only if we have historical data)
    trends: dict[str, TrendData] | None = Field(
        default=None, description="Trend data for key metrics"
    )

    # Timestamps
    last_updated: str = Field(description="ISO timestamp of stats snapshot")


# Hey future me - dieser Endpoint ist der HAUPT-Stats-Endpoint für das Dashboard!
# Er kombiniert aktuelle Counts mit Trend-Berechnung. Trends basieren auf der
# Differenz zwischen heute und gestern (für Downloads) oder dieser Woche vs.
# letzter Woche (für Playlists/Tracks). Die Trend-Berechnung ist optional -
# wenn keine historischen Daten vorhanden sind, werden trends=None zurückgegeben.
@router.get("/trends")
async def get_stats_with_trends(
    session: AsyncSession = Depends(get_db_session),
) -> StatsWithTrends:
    """Get dashboard statistics with trend indicators.

    Returns current counts for all major metrics plus trend data showing
    changes since yesterday/last week. Used by dashboard for stat cards
    with trend arrows (↑/↓).

    Returns:
        Current stats and optional trend data
    """
    # Hey future me - NOW fully uses StatsService! Clean Architecture.
    from soulspot.application.services.stats_service import StatsService
    from soulspot.infrastructure.persistence.models import DownloadModel, PlaylistModel
    from soulspot.infrastructure.persistence.repositories import SpotifyBrowseRepository

    stats_service = StatsService(session)

    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    # === Current Counts via StatsService ===
    playlist_count = await stats_service.get_total_playlists()
    total_tracks = await stats_service.get_distinct_playlist_tracks_count()
    tracks_downloaded = await stats_service.get_tracks_with_files()
    completed_downloads = await stats_service.get_completed_downloads_count()
    failed_downloads = await stats_service.get_failed_downloads_count()
    queue_size = await stats_service.get_queue_size()
    active_downloads = await stats_service.get_active_downloads_count()

    # Spotify stats
    spotify_repo = SpotifyBrowseRepository(session)
    spotify_artists = await spotify_repo.count_artists()
    spotify_albums = await spotify_repo.count_albums()
    spotify_tracks = await spotify_repo.count_tracks()

    # === Trend Calculations ===
    # Hey future me - Trends sind basierend auf created_at/completed_at timestamps.
    # Für Downloads zählen wir "heute hinzugefügt" vs "gestern hinzugefügt".
    # Das gibt dem User ein Gefühl für die Download-Aktivität.

    trends: dict[str, TrendData] = {}

    # Downloads completed today vs yesterday
    completed_today_stmt = select(func.count(DownloadModel.id)).where(
        DownloadModel.status == "completed",
        DownloadModel.completed_at >= today_start,
    )
    completed_today_result = await session.execute(completed_today_stmt)
    completed_today = completed_today_result.scalar() or 0

    completed_yesterday_stmt = select(func.count(DownloadModel.id)).where(
        DownloadModel.status == "completed",
        DownloadModel.completed_at >= yesterday_start,
        DownloadModel.completed_at < today_start,
    )
    completed_yesterday_result = await session.execute(completed_yesterday_stmt)
    completed_yesterday = completed_yesterday_result.scalar() or 0

    trends["downloads_today"] = _calculate_trend(
        completed_today, completed_yesterday, "today"
    )

    # Downloads in last 7 days vs previous 7 days
    two_weeks_ago = week_ago - timedelta(days=7)

    completed_this_week_stmt = select(func.count(DownloadModel.id)).where(
        DownloadModel.status == "completed",
        DownloadModel.completed_at >= week_ago,
    )
    this_week_result = await session.execute(completed_this_week_stmt)
    completed_this_week = this_week_result.scalar() or 0

    completed_last_week_stmt = select(func.count(DownloadModel.id)).where(
        DownloadModel.status == "completed",
        DownloadModel.completed_at >= two_weeks_ago,
        DownloadModel.completed_at < week_ago,
    )
    last_week_result = await session.execute(completed_last_week_stmt)
    completed_last_week = last_week_result.scalar() or 0

    trends["downloads_week"] = _calculate_trend(
        completed_this_week, completed_last_week, "week"
    )

    # New playlists this week
    new_playlists_stmt = select(func.count(PlaylistModel.id)).where(
        PlaylistModel.created_at >= week_ago
    )
    new_playlists_result = await session.execute(new_playlists_stmt)
    new_playlists = new_playlists_result.scalar() or 0

    # We don't have "last week" playlist count easily, so just show new this week
    trends["playlists_new"] = TrendData(
        current=new_playlists,
        previous=0,  # We don't track historical
        change=new_playlists,
        change_percent=100.0 if new_playlists > 0 else 0.0,
        direction="up" if new_playlists > 0 else "stable",
        period="week",
    )

    # Failed downloads trend (we want this to go DOWN)
    # Show as "up" if MORE failures (bad), "down" if FEWER (good)
    trends["failed"] = TrendData(
        current=failed_downloads,
        previous=0,  # No historical comparison for now
        change=failed_downloads,
        change_percent=0.0,
        direction="up" if failed_downloads > 0 else "stable",
        period="total",
    )

    return StatsWithTrends(
        playlists=playlist_count,
        tracks=total_tracks,
        tracks_downloaded=tracks_downloaded,
        downloads_completed=completed_downloads,
        downloads_failed=failed_downloads,
        queue_size=queue_size,
        active_downloads=active_downloads,
        spotify_artists=spotify_artists,
        spotify_albums=spotify_albums,
        spotify_tracks=spotify_tracks,
        trends=trends,
        last_updated=now.isoformat(),
    )


def _calculate_trend(current: int, previous: int, period: str) -> TrendData:
    """Calculate trend data from current and previous values.

    Hey future me - diese Helper-Funktion macht die Mathe für Trends.
    - direction: "up" wenn current > previous, "down" wenn kleiner, sonst "stable"
    - change_percent: Prozentuale Änderung, 0 wenn previous=0

    Args:
        current: Current period value
        previous: Previous period value
        period: Period label ("today", "week", etc.)

    Returns:
        TrendData with calculated values
    """
    change = current - previous

    if previous > 0:
        change_percent = round((change / previous) * 100, 1)
    elif current > 0:
        change_percent = 100.0  # Went from 0 to something
    else:
        change_percent = 0.0

    if change > 0:
        direction = "up"
    elif change < 0:
        direction = "down"
    else:
        direction = "stable"

    return TrendData(
        current=current,
        previous=previous,
        change=change,
        change_percent=change_percent,
        direction=direction,
        period=period,
    )


class QuickStats(BaseModel):
    """Minimal stats for quick refresh (HTMX polling)."""

    downloads_completed: int
    downloads_failed: int
    queue_size: int
    active_downloads: int
    last_updated: str


# Hey future me - dieser Endpoint ist für schnelles Polling gedacht!
# Das Dashboard kann alle 30s diesen Endpoint aufrufen um die Download-Zahlen
# zu aktualisieren ohne die ganze Seite neu zu laden. Nur die wichtigsten
# Zahlen, keine Trends (die ändern sich nicht so schnell).
@router.get("/quick")
async def get_quick_stats(
    session: AsyncSession = Depends(get_db_session),
) -> QuickStats:
    """Get minimal stats for quick polling.

    Lighter endpoint for HTMX polling - only download-related counts
    that change frequently.

    Returns:
        Current download stats
    """
    # Hey future me - NOW uses StatsService! Clean Architecture.
    from soulspot.application.services.stats_service import StatsService

    stats_service = StatsService(session)
    now = datetime.now(UTC)

    completed = await stats_service.get_completed_downloads_count()
    failed = await stats_service.get_failed_downloads_count()
    queue_size = await stats_service.get_queue_size()
    active = await stats_service.get_active_downloads_count()

    return QuickStats(
        downloads_completed=completed,
        downloads_failed=failed,
        queue_size=queue_size,
        active_downloads=active,
        last_updated=now.isoformat(),
    )
