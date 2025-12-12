"""Duplicate detection & merge API endpoints.

Hey future me - this file exists only to keep `library.py` from becoming an unreadable mega-router.
These endpoints are still mounted under `/api/library/*` because `library.py` includes this router.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session
from soulspot.application.services.local_library_enrichment_service import (
    LocalLibraryEnrichmentService,
)
from soulspot.config import Settings, get_settings

router = APIRouter(tags=["duplicates"])


class MergeRequest(BaseModel):
    """Request to merge duplicate entities."""

    keep_id: str
    merge_ids: list[str]


@router.get(
    "/duplicates/artists",
    summary="Find duplicate artists",
)
async def find_duplicate_artists(
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Find potential duplicate artists by normalized name matching.

    Returns groups of artists that might be duplicates (same normalized name).
    Each group includes a suggested primary (the one with Spotify URI or most tracks).

    Use POST /duplicates/artists/merge to combine duplicates.
    """
    # Hey future me - spotify_plugin=None weil wir nur lokale DB-Operationen machen!
    service = LocalLibraryEnrichmentService(
        session=db,
        spotify_plugin=None,
        settings=settings,
    )

    duplicate_groups = await service.find_duplicate_artists()

    return {
        "duplicate_groups": duplicate_groups,
        "total_groups": len(duplicate_groups),
        "total_duplicates": sum(len(g["artists"]) - 1 for g in duplicate_groups),
    }


@router.post(
    "/duplicates/artists/merge",
    summary="Merge duplicate artists",
)
async def merge_duplicate_artists(
    request: MergeRequest,
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Merge multiple artists into one.

    All tracks and albums from merge_ids artists will be transferred to keep_id artist.
    The merge_ids artists will be deleted after transfer.

    Args:
        keep_id: ID of artist to keep
        merge_ids: List of artist IDs to merge into keep artist
    """
    service = LocalLibraryEnrichmentService(
        session=db,
        spotify_plugin=None,
        settings=settings,
    )

    try:
        result = await service.merge_artists(request.keep_id, request.merge_ids)
        return {
            "success": True,
            **result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/duplicates/albums",
    summary="Find duplicate albums",
)
async def find_duplicate_albums(
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Find potential duplicate albums by normalized name + artist matching.

    Returns groups of albums that might be duplicates.
    """
    service = LocalLibraryEnrichmentService(
        session=db,
        spotify_plugin=None,
        settings=settings,
    )

    duplicate_groups = await service.find_duplicate_albums()

    return {
        "duplicate_groups": duplicate_groups,
        "total_groups": len(duplicate_groups),
        "total_duplicates": sum(len(g["albums"]) - 1 for g in duplicate_groups),
    }


@router.post(
    "/duplicates/albums/merge",
    summary="Merge duplicate albums",
)
async def merge_duplicate_albums(
    request: MergeRequest,
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Merge multiple albums into one.

    All tracks from merge_ids albums will be transferred to keep_id album.
    The merge_ids albums will be deleted after transfer.
    """
    service = LocalLibraryEnrichmentService(
        session=db,
        spotify_plugin=None,
        settings=settings,
    )

    try:
        result = await service.merge_albums(request.keep_id, request.merge_ids)
        return {
            "success": True,
            **result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
