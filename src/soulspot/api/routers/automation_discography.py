"""Automation: discography endpoints.

Mounted under `/automation` by `automation.py`.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session
from soulspot.application.services.artist_service import ArtistService
from soulspot.domain.value_objects import ArtistId

router = APIRouter()


# Hey, super simple request - just an artist ID to check their complete discography!
class DiscographyCheckRequest(BaseModel):
    """Request to check discography."""

    artist_id: str


# Listen, this endpoint checks "do we have ALL albums for this artist?" Uses pre-synced spotify_albums
# data from background sync, NO live API call needed!
@router.post("/discography/check")
async def check_discography(
    request: DiscographyCheckRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Check discography completeness for an artist."""
    try:
        artist_id = ArtistId.from_string(request.artist_id)
        service = ArtistService(session)
        info = await service.check_discography(artist_id, "")
        return info.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to check discography: {e}"
        ) from e


# Hey future me, this is the "collector's dream" endpoint - show me ALL missing albums across ALL artists!
@router.get("/discography/missing")
async def get_missing_albums(
    limit: int = 10,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get missing albums for all artists."""
    try:
        service = ArtistService(session)
        infos = await service.get_missing_albums_for_all_artists("", limit)
        return {
            "artists_with_missing_albums": [info.to_dict() for info in infos],
            "count": len(infos),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get missing albums: {e}"
        ) from e
