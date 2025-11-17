"""Widget content endpoints for dashboard widgets."""

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
                    query, access_token="", limit=limit
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
