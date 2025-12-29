# Hey future me - dieser Router ist für den Worker-Status-Indicator in der Sidebar!
#
# Er gibt den Status aller Background-Worker zurück (Token Refresh, Spotify Sync).
# Das Frontend pollt /api/workers/status/html alle 10 Sekunden via HTMX und zeigt
# animierte Icons im Sidebar-Footer an:
# - Idle: Icon pulsiert sanft (grün)
# - Active: Icon dreht sich
# - Error: Icon ist rot
#
# Hover zeigt einen kombinierten Tooltip mit Details zu allen Workern.
# Klick auf ein Icon navigiert zu den entsprechenden Settings.
#
# Wenn du neue Worker hinzufügst, füge sie hier in get_all_workers_status() ein.
# Das System ist bewusst simpel gehalten - kein ABC/Registry Pattern,
# einfach direkt die Worker vom app.state holen.
"""Background worker status API endpoints."""

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

router = APIRouter()


class WorkerStatusInfo(BaseModel):
    """Status information for a single worker."""

    name: str = Field(description="Display name of the worker")
    icon: str = Field(description="Font Awesome icon class")
    settings_url: str = Field(description="URL to settings page for this worker")
    running: bool = Field(description="Whether the worker is currently running")
    status: str = Field(description="Current status: idle, active, error, or stopped")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Worker-specific details"
    )


class AllWorkersStatus(BaseModel):
    """Status of all background workers."""

    workers: dict[str, WorkerStatusInfo] = Field(
        description="Status information for each worker"
    )


def _format_time_ago(dt: datetime | None) -> str:
    """Format a datetime as a relative time string (e.g., 'vor 5 min').

    Hey future me - diese Funktion macht aus einem Timestamp einen lesbaren String.
    Wird für "Letzter Sync: vor 3 min" im Tooltip verwendet.
    WICHTIG: Handles both naive und aware datetimes (von unterschiedlichen Workern)!
    """
    if dt is None:
        return "noch nie"

    # Get current time in UTC (aware)
    now = datetime.now(UTC)

    # If dt is naive (no timezone), assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)

    diff = now - dt
    seconds = int(diff.total_seconds())

    if seconds < 60:
        return "gerade eben"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"vor {minutes} min"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"vor {hours} h"
    else:
        days = seconds // 86400
        return f"vor {days} d"


def _format_time_until(minutes: int) -> str:
    """Format minutes until next action as readable string."""
    if minutes <= 0:
        return "jetzt"
    elif minutes < 60:
        return f"in {minutes} min"
    else:
        hours = minutes // 60
        return f"in {hours} h"


def _get_token_worker_status(request: Request) -> WorkerStatusInfo:
    """Get status for the Token Refresh Worker.

    Hey future me - holt den Status vom TokenRefreshWorker.
    Der Worker ist auf app.state.token_refresh_worker gespeichert (siehe lifecycle.py).
    """
    worker = getattr(request.app.state, "token_refresh_worker", None)

    if worker is None:
        return WorkerStatusInfo(
            name="Token Refresh",
            icon="bi bi-key",
            settings_url="/settings?tab=spotify",
            running=False,
            status="stopped",
            details={"error": "Worker not initialized"},
        )

    raw_status = worker.get_status()

    # Determine status based on token availability
    # We can't async check token here, so we just show worker status
    status = "idle" if raw_status.get("running") else "stopped"

    return WorkerStatusInfo(
        name="Token Refresh",
        icon="bi bi-key",
        settings_url="/settings?tab=spotify",
        running=raw_status.get("running", False),
        status=status,
        details={
            "check_interval_seconds": raw_status.get("check_interval_seconds", 300),
            "refresh_threshold_minutes": raw_status.get(
                "refresh_threshold_minutes", 10
            ),
        },
    )


def _get_spotify_sync_worker_status(request: Request) -> WorkerStatusInfo:
    """Get status for the Spotify Sync Worker.

    Hey future me - holt den Status vom SpotifySyncWorker.
    Der Worker ist auf app.state.spotify_sync_worker gespeichert.
    """
    worker = getattr(request.app.state, "spotify_sync_worker", None)

    if worker is None:
        return WorkerStatusInfo(
            name="Spotify Sync",
            icon="bi bi-spotify",
            settings_url="/settings?tab=spotify",
            running=False,
            status="stopped",
            details={"error": "Worker not initialized"},
        )

    raw_status = worker.get_status()

    # Format last sync times
    last_syncs = raw_status.get("last_sync", {})
    formatted_last_syncs = {}
    for sync_type, iso_time in last_syncs.items():
        if iso_time:
            dt = datetime.fromisoformat(iso_time)
            formatted_last_syncs[sync_type] = _format_time_ago(dt)
        else:
            formatted_last_syncs[sync_type] = "noch nie"

    # Check for errors in stats
    stats = raw_status.get("stats", {})
    has_errors = any(
        s.get("last_error") is not None for s in stats.values() if isinstance(s, dict)
    )

    # Determine status
    if not raw_status.get("running"):
        status = "stopped"
    elif has_errors:
        status = "error"
    else:
        status = "idle"

    return WorkerStatusInfo(
        name="Spotify Sync",
        icon="bi bi-spotify",
        settings_url="/settings?tab=spotify",
        running=raw_status.get("running", False),
        status=status,
        details={
            "last_syncs": formatted_last_syncs,
            "check_interval_seconds": raw_status.get("check_interval_seconds", 60),
            "stats": stats,
            "has_errors": has_errors,
        },
    )


def _get_download_monitor_worker_status(request: Request) -> WorkerStatusInfo:
    """Get status for the Download Monitor Worker.

    Hey future me - holt den Status vom DownloadMonitorWorker.
    Der Worker überwacht slskd Downloads und updated Job Progress.
    """
    worker = getattr(request.app.state, "download_monitor_worker", None)

    if worker is None:
        return WorkerStatusInfo(
            name="Download Monitor",
            icon="bi bi-download",
            settings_url="/settings?tab=downloads",
            running=False,
            status="stopped",
            details={"error": "Worker not initialized"},
        )

    raw_status = worker.get_status()
    stats = raw_status.get("stats", {})

    # Format last poll time
    last_poll_at = stats.get("last_poll_at")
    if last_poll_at:
        dt = datetime.fromisoformat(last_poll_at)
        last_poll_formatted = _format_time_ago(dt)
    else:
        last_poll_formatted = "noch nie"

    # Determine status
    if not raw_status.get("running"):
        status = "stopped"
    elif stats.get("last_error"):
        status = "error"
    else:
        status = "idle"

    return WorkerStatusInfo(
        name="Download Monitor",
        icon="bi bi-download",
        settings_url="/settings?tab=downloads",
        running=raw_status.get("running", False),
        status=status,
        details={
            "poll_interval_seconds": raw_status.get("poll_interval_seconds", 10),
            "last_poll": last_poll_formatted,
            "downloads_completed": stats.get("downloads_completed", 0),
            "downloads_failed": stats.get("downloads_failed", 0),
            "last_error": stats.get("last_error"),
        },
    )


def _get_automation_workers_status(request: Request) -> WorkerStatusInfo:
    """Get combined status for Automation Workers.

    Hey future me - kombiniert den Status aller 3 Automation Workers:
    - WatchlistWorker: Neue Releases finden
    - DiscographyWorker: Fehlende Alben finden
    - QualityUpgradeWorker: Upgrade-Kandidaten finden

    Alle 3 sind optional und default disabled via AppSettingsService.
    """
    manager = getattr(request.app.state, "automation_manager", None)

    if manager is None:
        return WorkerStatusInfo(
            name="Automation",
            icon="bi bi-robot",
            settings_url="/settings?tab=automation",
            running=False,
            status="stopped",
            details={"error": "Worker not initialized"},
        )

    raw_status = manager.get_status()

    # Check if all workers are running
    all_running = all(raw_status.values())
    any_running = any(raw_status.values())

    if all_running:
        status = "idle"
    elif any_running:
        status = "idle"  # Some running, some stopped
    else:
        status = "stopped"

    return WorkerStatusInfo(
        name="Automation",
        icon="bi bi-robot",
        settings_url="/settings?tab=automation",
        running=any_running,
        status=status,
        details={
            "watchlist_running": raw_status.get("watchlist", False),
            "discography_running": raw_status.get("discography", False),
            "quality_upgrade_running": raw_status.get("quality_upgrade", False),
        },
    )


def _get_cleanup_worker_status(request: Request) -> WorkerStatusInfo:
    """Get status for the Cleanup Worker.

    Hey future me - holt den Status vom CleanupWorker.
    Dieser Worker löscht alte Temp-Dateien und verwaiste Downloads.
    ACHTUNG: Ist per Default DISABLED weil destruktiv!
    """
    worker = getattr(request.app.state, "cleanup_worker", None)

    if worker is None:
        return WorkerStatusInfo(
            name="Cleanup",
            icon="bi bi-trash3",
            settings_url="/settings?tab=automation",
            running=False,
            status="stopped",
            details={"error": "Worker not initialized"},
        )

    raw_status = worker.get_status()
    stats = raw_status.get("stats", {})

    # Format last run time
    last_run_at = stats.get("last_run_at")
    if last_run_at:
        dt = datetime.fromisoformat(last_run_at)
        last_run_formatted = _format_time_ago(dt)
    else:
        last_run_formatted = "noch nie"

    # Determine status
    if not raw_status.get("running"):
        status = "stopped"
    elif stats.get("last_error"):
        status = "error"
    else:
        status = "idle"

    return WorkerStatusInfo(
        name="Cleanup",
        icon="bi bi-trash3",
        settings_url="/settings?tab=automation",
        running=raw_status.get("running", False),
        status=status,
        details={
            "dry_run": raw_status.get("dry_run", False),
            "last_run": last_run_formatted,
            "files_deleted": stats.get("files_deleted", 0),
            "bytes_freed": stats.get("bytes_freed", 0),
            "last_error": stats.get("last_error"),
        },
    )


def _get_duplicate_detector_worker_status(request: Request) -> WorkerStatusInfo:
    """Get status for the Duplicate Detector Worker.

    Hey future me - holt den Status vom DuplicateDetectorWorker.
    Dieser Worker findet Duplikate via Metadata-Hash.
    Per Default DISABLED, läuft nur 1x pro Woche wenn enabled.
    """
    worker = getattr(request.app.state, "duplicate_detector_worker", None)

    if worker is None:
        return WorkerStatusInfo(
            name="Duplicate Detector",
            icon="bi bi-copy",
            settings_url="/settings?tab=automation",
            running=False,
            status="stopped",
            details={"error": "Worker not initialized"},
        )

    raw_status = worker.get_status()
    stats = raw_status.get("stats", {})

    # Format last scan time
    last_scan_at = stats.get("last_scan_at")
    if last_scan_at:
        dt = datetime.fromisoformat(last_scan_at)
        last_scan_formatted = _format_time_ago(dt)
    else:
        last_scan_formatted = "noch nie"

    # Determine status
    if not raw_status.get("running"):
        status = "stopped"
    elif stats.get("last_error"):
        status = "error"
    else:
        status = "idle"

    return WorkerStatusInfo(
        name="Duplicate Detector",
        icon="bi bi-copy",
        settings_url="/settings?tab=automation",
        running=raw_status.get("running", False),
        status=status,
        details={
            "detection_method": raw_status.get("detection_method", "metadata-hash"),
            "last_scan": last_scan_formatted,
            "duplicates_found": stats.get("duplicates_found", 0),
            "tracks_scanned": stats.get("tracks_scanned", 0),
            "last_error": stats.get("last_error"),
        },
    )


def _get_retry_scheduler_worker_status(request: Request) -> WorkerStatusInfo:
    """Get status for the Retry Scheduler Worker.

    Hey future me - holt den Status vom RetrySchedulerWorker.
    Dieser Worker plant automatische Retries für fehlgeschlagene Downloads.
    Uses exponential backoff (1, 5, 15 minutes).
    """
    worker = getattr(request.app.state, "retry_scheduler_worker", None)

    if worker is None:
        return WorkerStatusInfo(
            name="Retry Scheduler",
            icon="bi bi-arrow-repeat",
            settings_url="/settings?tab=downloads",
            running=False,
            status="stopped",
            details={"error": "Worker not initialized"},
        )

    raw_status = worker.get_stats()
    stats = raw_status.get("stats", {})

    # Format last check time
    last_check_at = stats.get("last_check_at")
    if last_check_at:
        dt = datetime.fromisoformat(last_check_at)
        last_check_formatted = _format_time_ago(dt)
    else:
        last_check_formatted = "noch nie"

    # Determine status
    if not raw_status.get("running"):
        status = "stopped"
    elif stats.get("last_error"):
        status = "error"
    else:
        status = "idle"

    return WorkerStatusInfo(
        name="Retry Scheduler",
        icon="bi bi-arrow-repeat",
        settings_url="/settings?tab=downloads",
        running=raw_status.get("running", False),
        status=status,
        details={
            "check_interval_seconds": raw_status.get("check_interval_seconds", 60),
            "last_check": last_check_formatted,
            "retries_scheduled": stats.get("retries_scheduled", 0),
            "retries_successful": stats.get("retries_successful", 0),
            "max_retries": raw_status.get("max_retries", 3),
            "last_error": stats.get("last_error"),
        },
    )


def _get_post_processing_worker_status(request: Request) -> WorkerStatusInfo:
    """Get status for the Post-Processing Worker.

    Hey future me - holt den Status vom PostProcessingWorker.
    Dieser Worker tagged und organisiert Downloads nach Fertigstellung.
    """
    worker = getattr(request.app.state, "post_processing_worker", None)

    if worker is None:
        return WorkerStatusInfo(
            name="Post-Processing",
            icon="bi bi-file-earmark-music",
            settings_url="/settings?tab=downloads",
            running=False,
            status="stopped",
            details={"error": "Worker not initialized"},
        )

    raw_status = worker.get_status()
    stats = raw_status.get("stats", {})

    # Format last process time
    last_process_at = stats.get("last_process_at")
    if last_process_at:
        dt = datetime.fromisoformat(last_process_at)
        last_process_formatted = _format_time_ago(dt)
    else:
        last_process_formatted = "noch nie"

    # Determine status
    if not raw_status.get("running"):
        status = "stopped"
    elif stats.get("last_error"):
        status = "error"
    else:
        status = "idle"

    return WorkerStatusInfo(
        name="Post-Processing",
        icon="bi bi-file-earmark-music",
        settings_url="/settings?tab=downloads",
        running=raw_status.get("running", False),
        status=status,
        details={
            "check_interval_seconds": raw_status.get("check_interval_seconds", 30),
            "last_process": last_process_formatted,
            "files_tagged": stats.get("files_tagged", 0),
            "files_moved": stats.get("files_moved", 0),
            "last_error": stats.get("last_error"),
        },
    )


def _get_queue_dispatcher_worker_status(request: Request) -> WorkerStatusInfo:
    """Get status for the Queue Dispatcher Worker.

    Hey future me - holt den Status vom QueueDispatcherWorker.
    Dieser Worker dispatched Jobs aus der PersistentJobQueue an slskd.
    """
    worker = getattr(request.app.state, "queue_dispatcher_worker", None)

    if worker is None:
        return WorkerStatusInfo(
            name="Queue Dispatcher",
            icon="bi bi-send",
            settings_url="/settings?tab=downloads",
            running=False,
            status="stopped",
            details={"error": "Worker not initialized"},
        )

    raw_status = worker.get_status()
    stats = raw_status.get("stats", {})

    # Format last dispatch time
    last_dispatch_at = stats.get("last_dispatch_at")
    if last_dispatch_at:
        dt = datetime.fromisoformat(last_dispatch_at)
        last_dispatch_formatted = _format_time_ago(dt)
    else:
        last_dispatch_formatted = "noch nie"

    # Determine status
    if not raw_status.get("running"):
        status = "stopped"
    elif stats.get("last_error"):
        status = "error"
    else:
        status = "idle"

    return WorkerStatusInfo(
        name="Queue Dispatcher",
        icon="bi bi-send",
        settings_url="/settings?tab=downloads",
        running=raw_status.get("running", False),
        status=status,
        details={
            "dispatch_interval_seconds": raw_status.get("dispatch_interval_seconds", 5),
            "last_dispatch": last_dispatch_formatted,
            "jobs_dispatched": stats.get("jobs_dispatched", 0),
            "concurrent_limit": raw_status.get("concurrent_limit", 3),
            "last_error": stats.get("last_error"),
        },
    )


def _get_service_status(request: Request) -> dict[str, Any]:
    """Get connectivity status for all external services.

    Hey future me - kontrolliert ob die Verbindungen zu externen Services aktiv sind:
    - Spotify: OAuth Token gültig?
    - slskd: Kann der Worker verbinden?
    - MusicBrainz/CoverArtArchive: APIs erreichbar?

    Returns dict mit service_name → is_connected für das Tooltip.
    """
    service_status = {}

    # Check Spotify connection via Token Worker status
    # Can't do async in sync function, so trust the Token Worker
    spotify_worker = getattr(request.app.state, "token_refresh_worker", None)
    service_status["spotify"] = (
        spotify_worker is not None and spotify_worker.get_status().get("running", False)
    )

    # Check if slskd connection is available
    # This is checked by the DownloadMonitorWorker
    download_worker = getattr(request.app.state, "download_monitor_worker", None)
    service_status["slskd"] = (
        download_worker is not None
        and download_worker.get_status().get("running", False)
    )

    # External APIs (MusicBrainz, CoverArtArchive) are generally available
    # but we could add health checks if needed
    service_status["musicbrainz"] = True
    service_status["coverart"] = True

    return service_status


# Hey future me – dieser Endpoint gibt JSON mit allen Worker-Statuses zurück.
# Nützlich für Debugging und falls jemand die API direkt nutzen will.
@router.get("/status")
async def get_all_workers_status(request: Request) -> AllWorkersStatus:
    """Get status of all background workers.

    Returns status information for:
    - Token Refresh Worker: Keeps Spotify OAuth tokens fresh
    - Spotify Sync Worker: Automatically syncs Spotify data
    - Download Monitor Worker: Tracks slskd download progress
    - Retry Scheduler Worker: Schedules automatic retries for failed downloads
    - Post-Processing Worker: Tags and organizes completed downloads
    - Queue Dispatcher Worker: Dispatches jobs from queue to slskd
    - Automation Workers: Watchlist, Discography, Quality Upgrade
    - Cleanup Worker: Removes orphaned files (disabled by default)
    - Duplicate Detector Worker: Finds duplicate tracks (disabled by default)

    Each worker includes:
    - name: Display name
    - icon: Font Awesome icon class
    - settings_url: Link to relevant settings page
    - running: Whether the worker is running
    - status: Current state (idle, active, error, stopped)
    - details: Worker-specific information
    """
    workers = {
        "token_refresh": _get_token_worker_status(request),
        "spotify_sync": _get_spotify_sync_worker_status(request),
        "download_monitor": _get_download_monitor_worker_status(request),
        "retry_scheduler": _get_retry_scheduler_worker_status(request),
        "post_processing": _get_post_processing_worker_status(request),
        "queue_dispatcher": _get_queue_dispatcher_worker_status(request),
        "automation": _get_automation_workers_status(request),
        "cleanup": _get_cleanup_worker_status(request),
        "duplicate_detector": _get_duplicate_detector_worker_status(request),
    }

    return AllWorkersStatus(workers=workers)


# Hey future me – dieser Endpoint rendert das HTML-Partial für HTMX!
# Wird alle 10 Sekunden vom Sidebar-Footer gepollt.
# Zeigt alle Worker und deren Status mit Service-Verbindungsinformationen an.
@router.get("/status/html", response_class=HTMLResponse)
async def get_workers_status_html(request: Request) -> HTMLResponse:
    """Get HTML partial for worker status indicator.

    Returns an HTML fragment for HTMX polling that shows:
    - Worker icons with status-based animations
    - Comprehensive tooltip with ALL workers + service status
    - Service connectivity indicators (Spotify, slskd, etc.)

    Used by the sidebar footer to display real-time worker status.
    """
    # Get status for all workers
    all_workers_status = await get_all_workers_status(request)
    service_status = _get_service_status(request)

    # Build worker rows for tooltip
    worker_rows = ""
    worker_order = [
        "token_refresh",
        "spotify_sync",
        "download_monitor",
        "retry_scheduler",
        "post_processing",
        "queue_dispatcher",
        "automation",
        "cleanup",
        "duplicate_detector",
    ]

    for worker_key in worker_order:
        if worker_key not in all_workers_status.workers:
            continue

        worker = all_workers_status.workers[worker_key]
        status_icon = {
            "idle": "●",
            "active": "⟳",
            "error": "✕",
            "stopped": "○",
        }.get(worker.status, "●")

        status_color = {
            "idle": "#4ade80",  # green
            "active": "#3b82f6",  # blue
            "error": "#ef4444",  # red
            "stopped": "#9ca3af",  # gray
        }.get(worker.status, "#9ca3af")

        # Build worker details
        details_html = ""
        if worker.details:
            # Show key details based on worker type
            if worker_key == "token_refresh":
                interval = worker.details.get("check_interval_seconds", 300) // 60
                next_check = worker.details.get("next_check_in", "unknown")
                details_html = f'<div class="tooltip-detail">Check alle {interval} min • Nächste: {next_check}</div>'

            elif worker_key == "spotify_sync":
                last_syncs = worker.details.get("last_syncs", {})
                if last_syncs:
                    sync_rows = ""
                    sync_icons = {
                        "artists": "🎤",
                        "playlists": "📋",
                        "liked_songs": "❤️",
                        "saved_albums": "💿",
                    }
                    for sync_type, icon in sync_icons.items():
                        if sync_type in last_syncs:
                            last_time = last_syncs[sync_type]
                            sync_rows += f'<span class="tooltip-sync-tag">{icon} {last_time}</span>'
                    if sync_rows:
                        details_html = f'<div class="tooltip-detail tooltip-syncs">{sync_rows}</div>'

            elif worker_key == "download_monitor":
                poll_interval = worker.details.get("poll_interval_seconds", 10)
                completed = worker.details.get("downloads_completed", 0)
                failed = worker.details.get("downloads_failed", 0)
                details_html = f'<div class="tooltip-detail">↻ alle {poll_interval}s • ✓ {completed} • ✕ {failed}</div>'

            elif worker_key == "retry_scheduler":
                retries = worker.details.get("retries_scheduled", 0)
                successful = worker.details.get("retries_successful", 0)
                max_retries = worker.details.get("max_retries", 3)
                details_html = f'<div class="tooltip-detail">Scheduled: {retries} • Success: {successful} • Max: {max_retries}</div>'

            elif worker_key == "post_processing":
                tagged = worker.details.get("files_tagged", 0)
                moved = worker.details.get("files_moved", 0)
                details_html = f'<div class="tooltip-detail">Tagged: {tagged} • Moved: {moved}</div>'

            elif worker_key == "queue_dispatcher":
                dispatched = worker.details.get("jobs_dispatched", 0)
                concurrent = worker.details.get("concurrent_limit", 3)
                details_html = f'<div class="tooltip-detail">Dispatched: {dispatched} • Parallel: {concurrent}</div>'

            elif worker_key == "automation":
                watchlist = worker.details.get("watchlist_running", False)
                discography = worker.details.get("discography_running", False)
                quality = worker.details.get("quality_upgrade_running", False)
                running = sum([watchlist, discography, quality])
                details_html = (
                    f'<div class="tooltip-detail">{running} von 3 Workern aktiv</div>'
                )

            elif worker_key == "cleanup":
                dry_run = worker.details.get("dry_run", False)
                last_run = worker.details.get("last_run", "noch nie")
                details_html = f'<div class="tooltip-detail">{"(Dry Run) " if dry_run else ""}Zuletzt: {last_run}</div>'

            elif worker_key == "duplicate_detector":
                method = worker.details.get("detection_method", "metadata-hash")
                found = worker.details.get("duplicates_found", 0)
                details_html = f'<div class="tooltip-detail">Methode: {method} • Gefunden: {found}</div>'

        worker_rows += f"""
        <div class="tooltip-worker-row">
            <div class="tooltip-worker-name">
                <span style="color: {status_color}; font-weight: bold;">{status_icon}</span>
                <i class="{worker.icon}"></i>
                <span>{worker.name}</span>
            </div>
            {details_html}
        </div>
        """

    # Build service status section
    service_rows = ""
    service_display = {
        "spotify": ("🎵 Spotify", "#1DB954"),
        "slskd": ("⬇️ Soulseek (slskd)", "#FF6B6B"),
        "musicbrainz": ("🎼 MusicBrainz", "#EB743B"),
        "coverart": ("🖼️ CoverArt", "#5F6FD3"),
    }

    for service_key, (service_label, _color) in service_display.items():
        is_connected = service_status.get(service_key, False)
        status_symbol = "✓" if is_connected else "✕"
        status_style = f"color: {'#4ade80' if is_connected else '#ef4444'};"
        service_rows += f"""
        <div class="tooltip-service-row">
            <span style="{status_style}; font-weight: bold;">{status_symbol}</span>
            <span>{service_label}</span>
        </div>
        """

    # Determine overall status
    all_statuses = [w.status for w in all_workers_status.workers.values()]
    if "error" in all_statuses:
        overall_status = "error"
    elif "active" in all_statuses:
        overall_status = "active"
    elif all(s == "stopped" for s in all_statuses):
        overall_status = "stopped"
    else:
        overall_status = "idle"

    status_text = {
        "idle": "Aktiv",
        "active": "Syncing",
        "error": "Fehler",
        "stopped": "Gestoppt",
    }

    html = f"""
<div class="worker-indicator-single" tabindex="0">
    <a href="/settings?tab=spotify"
       class="worker-icon"
       data-status="{overall_status}"
       aria-label="Background Workers: {status_text.get(overall_status, overall_status)}"
       title="">
        <i class="bi bi-disc"></i>
    </a>

    <div class="worker-tooltip" role="tooltip">
        <div class="tooltip-header">
            <span>🔄 Background Workers</span>
            <span class="tooltip-badge tooltip-badge-{overall_status}">{status_text.get(overall_status, overall_status)}</span>
        </div>

        <div class="tooltip-workers-section">
            {worker_rows}
        </div>

        <div class="tooltip-divider"></div>

        <div class="tooltip-services-section">
            <div class="tooltip-services-title">📡 Service Status</div>
            <div class="tooltip-services-grid">
                {service_rows}
            </div>
        </div>
    </div>
</div>
"""

    return HTMLResponse(content=html)


# =============================================================================
# ORCHESTRATOR STATUS ENDPOINT (NEW Dec 2025)
# =============================================================================
# Hey future me - dieser Endpoint gibt den Status vom Worker Orchestrator zurück!
# Der Orchestrator trackt alle Worker zentral und bietet:
# - Übersicht aller registrierten Worker
# - Status pro Worker (running, stopped, failed)
# - Kategorisierung (critical, sync, download, maintenance, enrichment)
# - Health-Check (alle required Workers laufen?)
#
# Endpoint: GET /api/workers/orchestrator
# Response: JSON mit orchestrator metadata + workers dict


@router.get("/orchestrator")
async def get_orchestrator_status(request: Request) -> dict[str, Any]:
    """Get comprehensive status from the Worker Orchestrator.

    Returns detailed status of all workers tracked by the orchestrator,
    including:
    - Total worker count
    - Workers grouped by state (running, stopped, failed)
    - Per-worker details (name, category, priority, started_at, etc.)
    - Overall health status

    This is the preferred endpoint for monitoring and debugging worker status.
    Use /api/workers/status for the UI-friendly format with icons and tooltips.
    """
    orchestrator = getattr(request.app.state, "orchestrator", None)

    if orchestrator is None:
        return {
            "error": "Orchestrator not initialized",
            "total_workers": 0,
            "healthy": False,
            "workers": {},
        }

    status = orchestrator.get_status()
    status["healthy"] = orchestrator.is_healthy()

    return status


# =============================================================================
# WORKER CONTROL ENDPOINTS (NEW Dec 2025)
# =============================================================================
# Hey future me - diese Endpoints erlauben Worker-Kontrolle via API!
# Nützlich für:
# - Debugging (Worker manuell stoppen/starten)
# - Maintenance (Worker während Updates pausieren)
# - Testing (einzelne Worker isoliert testen)
#
# ACHTUNG: Diese Endpoints sind mächtig! Nur für Admin-Zugriff gedacht.
# In Production sollte man Rate-Limiting oder Auth hinzufügen.


@router.post("/orchestrator/{worker_name}/stop")
async def stop_worker(request: Request, worker_name: str) -> dict[str, Any]:
    """Stop a specific worker by name.

    Args:
        worker_name: Name of the worker to stop (e.g., "token_refresh", "spotify_sync")

    Returns:
        Status of the operation including success/error message.

    Warning: Stopping critical workers may affect app functionality!
    """
    orchestrator = getattr(request.app.state, "orchestrator", None)

    if orchestrator is None:
        return {"success": False, "error": "Orchestrator not initialized"}

    worker_info = orchestrator._workers.get(worker_name)
    if worker_info is None:
        return {"success": False, "error": f"Worker '{worker_name}' not found"}

    try:
        # Stop the worker
        stop_result = worker_info.worker.stop()
        if asyncio.iscoroutine(stop_result):
            await stop_result

        # Update state
        from soulspot.application.workers.orchestrator import WorkerState

        worker_info.state = WorkerState.STOPPED

        return {
            "success": True,
            "worker": worker_name,
            "state": "stopped",
            "message": f"Worker '{worker_name}' stopped successfully",
        }
    except Exception as e:
        return {
            "success": False,
            "worker": worker_name,
            "error": str(e),
        }


@router.post("/orchestrator/{worker_name}/start")
async def start_worker(request: Request, worker_name: str) -> dict[str, Any]:
    """Start a specific worker by name.

    Args:
        worker_name: Name of the worker to start (e.g., "token_refresh", "spotify_sync")

    Returns:
        Status of the operation including success/error message.
    """
    orchestrator = getattr(request.app.state, "orchestrator", None)

    if orchestrator is None:
        return {"success": False, "error": "Orchestrator not initialized"}

    worker_info = orchestrator._workers.get(worker_name)
    if worker_info is None:
        return {"success": False, "error": f"Worker '{worker_name}' not found"}

    try:
        # Check if already running
        from soulspot.application.workers.orchestrator import WorkerState

        if worker_info.state == WorkerState.RUNNING:
            return {
                "success": True,
                "worker": worker_name,
                "state": "running",
                "message": f"Worker '{worker_name}' is already running",
            }

        # Start the worker
        await worker_info.worker.start()
        worker_info.state = WorkerState.RUNNING

        return {
            "success": True,
            "worker": worker_name,
            "state": "running",
            "message": f"Worker '{worker_name}' started successfully",
        }
    except Exception as e:
        worker_info.state = WorkerState.FAILED
        worker_info.error = str(e)
        return {
            "success": False,
            "worker": worker_name,
            "error": str(e),
        }


@router.get("/orchestrator/{worker_name}")
async def get_worker_status(request: Request, worker_name: str) -> dict[str, Any]:
    """Get detailed status of a specific worker.

    Args:
        worker_name: Name of the worker to query

    Returns:
        Detailed worker status including state, category, start time, errors, etc.
    """
    orchestrator = getattr(request.app.state, "orchestrator", None)

    if orchestrator is None:
        return {"error": "Orchestrator not initialized"}

    worker_info = orchestrator._workers.get(worker_name)
    if worker_info is None:
        return {"error": f"Worker '{worker_name}' not found"}

    # Get worker's own status
    try:
        worker_status = worker_info.worker.get_status()
    except Exception:
        worker_status = {}

    return {
        "name": worker_name,
        "state": worker_info.state.value,
        "category": worker_info.category,
        "priority": worker_info.priority,
        "required": worker_info.required,
        "started_at": worker_info.started_at.isoformat()
        if worker_info.started_at
        else None,
        "stopped_at": worker_info.stopped_at.isoformat()
        if worker_info.stopped_at
        else None,
        "error": worker_info.error,
        "depends_on": worker_info.depends_on,
        "worker_details": worker_status,
    }
