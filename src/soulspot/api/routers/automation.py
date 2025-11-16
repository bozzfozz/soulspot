"""Automation API endpoints for watchlists, discography, and quality upgrades."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session, get_spotify_access_token
from soulspot.application.services.discography_service import DiscographyService
from soulspot.application.services.quality_upgrade_service import QualityUpgradeService
from soulspot.application.services.watchlist_service import WatchlistService
from soulspot.domain.value_objects import ArtistId, WatchlistId
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

router = APIRouter(prefix="/automation", tags=["automation"])


# Pydantic models for API
class CreateWatchlistRequest(BaseModel):
    """Request to create an artist watchlist."""

    artist_id: str
    check_frequency_hours: int = 24
    auto_download: bool = True
    quality_profile: str = "high"


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


class DiscographyCheckRequest(BaseModel):
    """Request to check discography."""

    artist_id: str


class QualityUpgradeRequest(BaseModel):
    """Request to identify quality upgrade candidates."""

    quality_profile: str = "high"
    min_improvement_score: float = 0.3
    limit: int = 100


# Watchlist endpoints
@router.post("/watchlist")
async def create_watchlist(
    request: CreateWatchlistRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Create a new artist watchlist.

    Args:
        request: Watchlist creation request
        session: Database session

    Returns:
        Created watchlist information
    """
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
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create watchlist: {e}")


@router.get("/watchlist")
async def list_watchlists(
    limit: int = 100,
    offset: int = 0,
    active_only: bool = False,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List artist watchlists.

    Args:
        limit: Maximum number of results
        offset: Offset for pagination
        active_only: Only return active watchlists
        session: Database session

    Returns:
        List of watchlists
    """
    try:
        service = WatchlistService(session)
        if active_only:
            watchlists = await service.list_active(limit, offset)
        else:
            watchlists = await service.list_all(limit, offset)

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
        raise HTTPException(status_code=500, detail=f"Failed to list watchlists: {e}")


@router.get("/watchlist/{watchlist_id}")
async def get_watchlist(
    watchlist_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get a specific watchlist.

    Args:
        watchlist_id: Watchlist ID
        session: Database session

    Returns:
        Watchlist information
    """
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
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get watchlist: {e}")


@router.post("/watchlist/{watchlist_id}/check")
async def check_watchlist_releases(
    watchlist_id: str,
    access_token: str = Depends(get_spotify_access_token),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Check for new releases for a watchlist.

    Args:
        watchlist_id: Watchlist ID
        access_token: Spotify access token
        session: Database session

    Returns:
        New releases found
    """
    try:
        wid = WatchlistId.from_string(watchlist_id)
        spotify_client = SpotifyClient()
        service = WatchlistService(session, spotify_client)
        watchlist = await service.get_watchlist(wid)

        if not watchlist:
            raise HTTPException(status_code=404, detail="Watchlist not found")

        releases = await service.check_for_new_releases(watchlist, access_token)
        await session.commit()

        return {
            "watchlist_id": watchlist_id,
            "releases_found": len(releases),
            "releases": releases,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to check for releases: {e}"
        )


@router.delete("/watchlist/{watchlist_id}")
async def delete_watchlist(
    watchlist_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Delete a watchlist.

    Args:
        watchlist_id: Watchlist ID
        session: Database session

    Returns:
        Success message
    """
    try:
        wid = WatchlistId.from_string(watchlist_id)
        service = WatchlistService(session)
        await service.delete_watchlist(wid)
        await session.commit()

        return {"message": f"Watchlist {watchlist_id} deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete watchlist: {e}")


# Discography endpoints
@router.post("/discography/check")
async def check_discography(
    request: DiscographyCheckRequest,
    access_token: str = Depends(get_spotify_access_token),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Check discography completeness for an artist.

    Args:
        request: Discography check request
        access_token: Spotify access token
        session: Database session

    Returns:
        Discography information
    """
    try:
        artist_id = ArtistId.from_string(request.artist_id)
        spotify_client = SpotifyClient()
        service = DiscographyService(session, spotify_client)
        info = await service.check_discography(artist_id, access_token)

        return info.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to check discography: {e}"
        )


@router.get("/discography/missing")
async def get_missing_albums(
    limit: int = 10,
    access_token: str = Depends(get_spotify_access_token),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get missing albums for all artists.

    Args:
        limit: Maximum number of artists to check
        access_token: Spotify access token
        session: Database session

    Returns:
        List of artists with missing albums
    """
    try:
        spotify_client = SpotifyClient()
        service = DiscographyService(session, spotify_client)
        infos = await service.get_missing_albums_for_all_artists(access_token, limit)

        return {
            "artists_with_missing_albums": [info.to_dict() for info in infos],
            "count": len(infos),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get missing albums: {e}"
        )


# Quality upgrade endpoints
@router.post("/quality-upgrades/identify")
async def identify_quality_upgrades(
    request: QualityUpgradeRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Identify tracks that could be upgraded to better quality.

    Args:
        request: Quality upgrade request
        session: Database session

    Returns:
        List of upgrade candidates
    """
    try:
        service = QualityUpgradeService(session)
        candidates = await service.identify_upgrade_candidates(
            quality_profile=request.quality_profile,
            min_improvement_score=request.min_improvement_score,
            limit=request.limit,
        )

        return {
            "candidates": candidates,
            "count": len(candidates),
            "quality_profile": request.quality_profile,
            "min_improvement_score": request.min_improvement_score,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to identify upgrades: {e}"
        )


@router.get("/quality-upgrades/unprocessed")
async def get_unprocessed_upgrades(
    limit: int = 100,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get unprocessed quality upgrade candidates.

    Args:
        limit: Maximum number of results
        session: Database session

    Returns:
        List of unprocessed candidates
    """
    try:
        service = QualityUpgradeService(session)
        candidates = await service.get_unprocessed_candidates(limit)

        return {"candidates": candidates, "count": len(candidates)}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get unprocessed upgrades: {e}"
        )
