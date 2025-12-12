"""Automation: watchlist endpoints.

Hey future me - this module exists to keep `automation.py` from becoming an unmaintainable mega-router.
`automation.py` mounts this router under the `/automation` prefix.
"""

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session, get_spotify_plugin
from soulspot.application.services.watchlist_service import WatchlistService
from soulspot.domain.value_objects import ArtistId, WatchlistId

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

router = APIRouter()


class CreateWatchlistRequest(BaseModel):
    """Request to create an artist watchlist."""

    artist_id: str
    check_frequency_hours: int = 24
    auto_download: bool = True
    quality_profile: str = "high"


# Yo, this is what GET /watchlist returns for each watchlist! Maps domain entity fields to API response
# format. last_checked_at is optional (None if never checked). The counts (total_releases_found,
# total_downloads_triggered) are cumulative stats - they increment but never reset. Useful for tracking
# automation effectiveness ("this watchlist triggered 50 downloads!"). status is enum converted to string.
class WatchlistResponse(BaseModel):
    """Response with watchlist information."""

    id: str
    artist_id: str
    status: str
    check_frequency_hours: int
    auto_download: bool
    quality_profile: str
    last_checked_at: str | None
    total_releases_found: int
    total_downloads_triggered: int


# Hey future me, creating a watchlist is idempotent-ish - if you try to create the same artist twice,
# the service layer should handle it. The quality_profile defaults to "high" but users can override
# for specific use cases (e.g., "low" for rare bootlegs where quality doesn't matter). We commit
# immediately after creation - no batch operations here. If this fails, the whole transaction rolls
# back. The artist_id parsing can throw ValueError if someone sends garbage - we catch and return 400.
@router.post("/watchlist")
async def create_watchlist(
    request: CreateWatchlistRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Create a new artist watchlist."""
    try:
        artist_id = ArtistId.from_string(request.artist_id)
        service = WatchlistService(session)
        watchlist = await service.create_watchlist(
            artist_id=artist_id,
            check_frequency_hours=request.check_frequency_hours,
            auto_download=request.auto_download,
            quality_profile=request.quality_profile,
        )
        await session.commit()

        return {
            "id": str(watchlist.id.value),
            "artist_id": str(watchlist.artist_id.value),
            "status": watchlist.status.value,
            "check_frequency_hours": watchlist.check_frequency_hours,
            "auto_download": watchlist.auto_download,
            "quality_profile": watchlist.quality_profile,
            "created_at": watchlist.created_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create watchlist: {e}") from e


# Yo future me, pagination here uses limit/offset - NOT cursor-based! For small datasets this is fine,
# but if watchlists grow huge (thousands of artists), you'll want cursor pagination to avoid missing
# rows when data changes between page fetches. The active_only flag is a performance optimization -
# most UI queries only care about active watchlists, why fetch disabled ones? Defaults to showing all.
@router.get("/watchlist")
async def list_watchlists(
    limit: int = 100,
    offset: int = 0,
    active_only: bool = False,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List artist watchlists."""
    try:
        service = WatchlistService(session)
        watchlists = (
            await service.list_active(limit, offset)
            if active_only
            else await service.list_all(limit, offset)
        )

        return {
            "watchlists": [
                {
                    "id": str(w.id.value),
                    "artist_id": str(w.artist_id.value),
                    "status": w.status.value,
                    "check_frequency_hours": w.check_frequency_hours,
                    "auto_download": w.auto_download,
                    "quality_profile": w.quality_profile,
                    "last_checked_at": w.last_checked_at.isoformat()
                    if w.last_checked_at
                    else None,
                    "total_releases_found": w.total_releases_found,
                    "total_downloads_triggered": w.total_downloads_triggered,
                }
                for w in watchlists
            ],
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list watchlists: {e}") from e


# Listen up, this is a simple GET by ID. The WatchlistId.from_string can throw ValueError if the ID
# is malformed (not a valid UUID format), hence the catch block. We return 404 if watchlist doesn't
# exist - standard REST semantics.
@router.get("/watchlist/{watchlist_id}")
async def get_watchlist(
    watchlist_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get a specific watchlist."""
    try:
        wid = WatchlistId.from_string(watchlist_id)
        service = WatchlistService(session)
        watchlist = await service.get_watchlist(wid)

        if not watchlist:
            raise HTTPException(status_code=404, detail="Watchlist not found")

        return {
            "id": str(watchlist.id.value),
            "artist_id": str(watchlist.artist_id.value),
            "status": watchlist.status.value,
            "check_frequency_hours": watchlist.check_frequency_hours,
            "auto_download": watchlist.auto_download,
            "quality_profile": watchlist.quality_profile,
            "last_checked_at": watchlist.last_checked_at.isoformat()
            if watchlist.last_checked_at
            else None,
            "total_releases_found": watchlist.total_releases_found,
            "total_downloads_triggered": watchlist.total_downloads_triggered,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get watchlist: {e}") from e


# Hey, this check endpoint is the MANUAL trigger for "check this artist for new releases RIGHT NOW".
# SpotifyPlugin handles token internally.
@router.post("/watchlist/{watchlist_id}/check")
async def check_watchlist_releases(
    watchlist_id: str,
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Check for new releases for a watchlist."""
    try:
        wid = WatchlistId.from_string(watchlist_id)
        service = WatchlistService(session, spotify_plugin)
        watchlist = await service.get_watchlist(wid)

        if not watchlist:
            raise HTTPException(status_code=404, detail="Watchlist not found")

        releases = await service.check_for_new_releases(watchlist)
        await session.commit()

        return {
            "watchlist_id": watchlist_id,
            "releases_found": len(releases),
            "releases": releases,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to check for releases: {e}") from e


# Yo, DELETE is destructive and PERMANENT - there's no soft delete here!
@router.delete("/watchlist/{watchlist_id}")
async def delete_watchlist(
    watchlist_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Delete a watchlist."""
    try:
        wid = WatchlistId.from_string(watchlist_id)
        service = WatchlistService(session)
        await service.delete_watchlist(wid)
        await session.commit()

        return {"message": f"Watchlist {watchlist_id} deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete watchlist: {e}") from e
