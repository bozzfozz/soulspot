"""Widget content endpoints for dashboard widgets."""

# Yo future me, these endpoints power the HTMX-driven widget refresh system! Each widget type has a /content
# endpoint that returns HTML fragment. Widgets auto-poll these endpoints (hx-get + hx-trigger="every 5s") to
# stay up-to-date. This is a hybrid approach: SSE for instant updates, polling as fallback. The templates
# in partials/widgets/ define how each widget renders. Keep these endpoints FAST - widgets poll frequently!
# Use repository pagination and limits to avoid huge queries. The templates variable is Jinja2 template engine
# configured with src/soulspot/templates directory. All responses are HTMLResponse not JSON!

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from soulspot.api.dependencies import (
    get_download_repository,
    get_playlist_repository,
    get_track_repository,
)
from soulspot.infrastructure.persistence.repositories import (
    DownloadRepository,
    PlaylistRepository,
    TrackRepository,
)

templates = Jinja2Templates(directory="src/soulspot/templates")

router = APIRouter(prefix="/ui/widgets", tags=["widget-content"])


# Hey future me, this powers the Active Jobs widget! Gets active downloads (queued, in progress) and
# limits to 10 most recent. The TODO comments say we should get actual track/artist info instead of
# just using IDs - currently shows "Track <uuid>" and "Unknown Artist" which is poor UX. Should join
# with track table to get real names. downloads[:10] slice is arbitrary - widget config should control
# this. List comprehension builds template-friendly dicts. Progress percent defaults to 0 if None which
# is sensible. The jobs_count includes ALL active downloads even though we only show 10 - misleading!
# Should clarify "Showing 10 of 50 jobs" or paginate. This endpoint is called frequently by polling.
@router.get("/active-jobs/content", response_class=HTMLResponse)
async def active_jobs_content(
    request: Request,
    download_repository: DownloadRepository = Depends(get_download_repository),
) -> Any:
    """Get active jobs widget content."""
    # Get active downloads
    downloads = await download_repository.list_active()

    # Convert to template-friendly format
    jobs = [
        {
            "id": str(download.id.value),
            "title": f"Track {download.track_id.value}",  # TODO: Get actual track info
            "artist": "Unknown Artist",  # TODO: Get actual artist info
            "status": download.status.value,
            "progress_percent": download.progress_percent or 0,
        }
        for download in downloads[:10]  # Limit to 10 most recent
    ]

    return templates.TemplateResponse(
        "partials/widgets/active_jobs.html",
        {
            "request": request,
            "jobs": jobs,
            "jobs_count": len(downloads),
        },
    )


# Hey future me, Spotify search widget endpoint! Gets search results and renders them as HTML using the
# widget template. Creates SpotifyClient fresh each time which is inefficient - should use dependency injection!
# More critically, access_token="" with nosec B106 means NO AUTHENTICATION - search will FAIL! The # nosec
# suppresses security warning but this is a real bug. Should get token from session or skip this widget if
# no auth. query_string length check (>= 2 chars) prevents single-letter spam searches. Returns empty results
# array if search fails rather than showing error - UI should indicate failure!
@router.get("/spotify-search/content", response_class=HTMLResponse)
async def spotify_search_content(
    request: Request,
) -> Any:
    """Get Spotify search widget content."""
    return templates.TemplateResponse(
        "partials/widgets/spotify_search.html",
        {
            "request": request,
            "results": [],
        },
    )


# WARNING: Spotify search in widget context! The query string needs at least 2 chars before searching
# which prevents single-character spam. Creates SpotifyClient fresh every time - inefficient, should
# cache or inject. More importantly, access_token="" with nosec comment means NO AUTHENTICATION! The
# B106 bandit warning is suppressed but this is actually a real security issue. Search will fail without
# valid token. TODO says "needs to be refactored to use session-based auth" - this is broken currently!
# The search_results dict structure is nested (tracks.items) which matches Spotify API format. List
# comp extracts relevant fields. Empty results on exception is silent failure - users won't know why
# search didn't work. Logger warning is good but UI shows nothing. search_type param not actually used!
@router.get("/spotify-search/results", response_class=HTMLResponse)
async def spotify_search_results(
    request: Request,
    query: str = "",
    search_type: str = "track",
    limit: int = 10,
) -> Any:
    """Get Spotify search results for widget."""
    from soulspot.config import get_settings
    from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

    results = []

    if query and len(query) >= 2:
        try:
            settings = get_settings()
            spotify_client = SpotifyClient(settings.spotify)

            if search_type == "track":
                # Note: search_track requires access_token but we don't have it in widget context
                # This needs to be refactored to use session-based auth
                search_results = await spotify_client.search_track(
                    query,
                    access_token="",
                    limit=limit,  # nosec B106
                )
                # search_results is a dict with structure: {"tracks": {"items": [...]}}
                track_items = search_results.get("tracks", {}).get("items", [])
                results = [
                    {
                        "name": track.get("name", ""),
                        "artists": ", ".join(
                            a.get("name", "") for a in track.get("artists", [])
                        ),
                        "album": track.get("album", {}).get("name", ""),
                        "uri": track.get("uri", ""),
                        "duration_ms": track.get("duration_ms", 0),
                    }
                    for track in track_items
                ]
        except Exception as e:
            # Log error but don't crash - return empty results
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Spotify search failed: {e}")

    return templates.TemplateResponse(
        "partials/spotify_search_results.html",
        {
            "request": request,
            "results": results,
            "query": query,
        },
    )


# Listen, this widget shows tracks that haven't been downloaded! Gets all playlists then iterates to
# find missing tracks - very N+1 query pattern. Limited to first 10 playlists which is arbitrary.
# For each playlist, loops through ALL track IDs doing separate lookups - SUPER slow for big playlists!
# Should batch fetch tracks. The is_broken check has type: ignore because it's on ORM model not entity.
# Only includes playlists that have missing tracks which is smart filtering. Total_missing sums across
# playlists to show overall count. Downloaded_count tracks successfully downloaded files. The missing_tracks
# list includes track details but could be huge - no limit per playlist! Widget could show 100s of tracks.
@router.get("/missing-tracks/content", response_class=HTMLResponse)
async def missing_tracks_content(
    request: Request,
    playlist_repository: PlaylistRepository = Depends(get_playlist_repository),
    track_repository: TrackRepository = Depends(get_track_repository),
) -> Any:
    """Get missing tracks widget content."""
    # Get all playlists
    playlists = await playlist_repository.list_all()

    # Build playlists with missing tracks info
    playlists_data = []
    total_missing = 0

    for playlist in playlists[:10]:  # Limit to first 10 playlists for widget
        missing_tracks = []
        downloaded_count = 0

        for track_id in playlist.track_ids:
            track = await track_repository.get_by_id(track_id)
            if track:
                # Note: is_broken is on TrackModel (ORM), not Track entity
                if track.file_path and not track.is_broken:  # type: ignore[attr-defined]
                    downloaded_count += 1
                else:
                    missing_tracks.append(
                        {
                            "id": str(track.id.value),
                            "title": track.title,
                            "artist": track.artist,  # type: ignore[attr-defined]
                        }
                    )

        if missing_tracks:  # Only include playlists with missing tracks
            playlists_data.append(
                {
                    "id": str(playlist.id.value),
                    "name": playlist.name,
                    "track_count": len(playlist.track_ids),
                    "downloaded_count": downloaded_count,
                    "missing_count": len(missing_tracks),
                    "missing_tracks": missing_tracks,
                }
            )
            total_missing += len(missing_tracks)

    return templates.TemplateResponse(
        "partials/widgets/missing_tracks.html",
        {
            "request": request,
            "playlists": playlists_data,
            "missing_count": total_missing,
        },
    )


@router.get("/quick-actions/content", response_class=HTMLResponse)
async def quick_actions_content(
    request: Request,
) -> Any:
    """Get quick actions widget content."""
    return templates.TemplateResponse(
        "partials/widgets/quick_actions.html",
        {
            "request": request,
        },
    )


# Yo metadata manager widget - detects issues in your tracks! Limited to first 100 tracks to prevent
# timeout but that means you only see SOME of your issues, not all. Should paginate or sample randomly.
# Detects missing title/artist/album, broken files, missing files. Each issue has severity (high/medium)
# and can_auto_fix flag (true if track has spotify_uri for enrichment). The filter param ("all"/"missing"/
# "incorrect") filters what's shown but the logic is hacky - string matching on issue_type! The "missing"
# filter checks if "missing" is in issue_type which works but is fragile. Limited to 20 issues for display
# which is reasonable for widget but issues_count shows total found. Type ignores all over because Track
# entity uses ORM relationships. This does full table scan of 100 tracks on every widget load - expensive!
@router.get("/metadata-manager/content", response_class=HTMLResponse)
async def metadata_manager_content(
    request: Request,
    filter: str = "all",
    track_repository: TrackRepository = Depends(get_track_repository),
) -> Any:
    """Get metadata manager widget content."""
    # Get all tracks
    tracks = await track_repository.list_all()

    # Detect metadata issues
    issues = []
    for track in tracks[:100]:  # Limit to first 100 for widget performance
        track_issues = []

        # Check for missing metadata
        if not track.title or track.title.strip() == "":
            track_issues.append(
                {
                    "issue_type": "missing_title",
                    "description": "Missing track title",
                    "severity": "high",
                    "can_auto_fix": False,
                }
            )

        # Note: artist and album are ORM relationships, not domain entity attributes
        if not track.artist or track.artist.strip() == "":  # type: ignore[attr-defined]
            track_issues.append(
                {
                    "issue_type": "missing_artist",
                    "description": "Missing artist name",
                    "severity": "high",
                    "can_auto_fix": False,
                }
            )

        if not track.album or track.album.strip() == "":  # type: ignore[attr-defined]
            track_issues.append(
                {
                    "issue_type": "missing_album",
                    "description": "Missing album name",
                    "severity": "medium",
                    "can_auto_fix": track.spotify_uri is not None,
                }
            )

        # Check for broken files
        # Note: is_broken is on TrackModel (ORM), not Track entity
        if track.is_broken:  # type: ignore[attr-defined]
            track_issues.append(
                {
                    "issue_type": "broken_file",
                    "description": "File is broken or corrupt",
                    "severity": "high",
                    "can_auto_fix": track.spotify_uri is not None,
                }
            )

        # Check for missing file
        if not track.file_path:
            track_issues.append(
                {
                    "issue_type": "missing_file",
                    "description": "File not downloaded",
                    "severity": "medium",
                    "can_auto_fix": track.spotify_uri is not None,
                }
            )

        # Add issues to list
        for issue in track_issues:
            # Apply filter
            if filter == "missing" and "missing" not in issue["issue_type"]:  # type: ignore[operator]
                continue
            if filter == "incorrect" and issue["issue_type"] not in ["broken_file"]:
                continue

            issues.append(
                {
                    "track_id": str(track.id.value),
                    "track_title": track.title or "Unknown",
                    "track_artist": track.artist or "Unknown",  # type: ignore[attr-defined]
                    **issue,
                }
            )

    return templates.TemplateResponse(
        "partials/widgets/metadata_manager.html",
        {
            "request": request,
            "issues": issues[:20],  # Limit to 20 for display
            "issues_count": len(issues),
            "filter": filter,
        },
    )
