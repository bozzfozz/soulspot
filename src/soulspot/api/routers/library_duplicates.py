"""Duplicate detection & merge API endpoints.

Hey future me - this file exists only to keep `library.py` from becoming an unreadable mega-router.
These endpoints are still mounted under `/api/library/*` because `library.py` includes this router.

Updated 2025-01: Migrated from LibraryMergeService to DeduplicationHousekeepingService.
The new service is part of the consolidated deduplication architecture:
- DeduplicationChecker: Fast import-time matching (<50ms)
- DeduplicationHousekeepingService: Async scheduled cleanup (this router)
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session
from soulspot.application.services.deduplication_housekeeping import (
    DeduplicationHousekeepingService,
)
from soulspot.infrastructure.persistence.repositories import (
    AlbumRepository,
    ArtistRepository,
    TrackRepository,
)

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
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Find potential duplicate artists by normalized name matching.

    Returns groups of artists that might be duplicates (same normalized name).
    Each group includes a suggested primary (the one with Spotify URI or most tracks).

    Use POST /duplicates/artists/merge to combine duplicates.
    """
    # Hey future me - DeduplicationHousekeepingService needs all repos for FK transfers
    artist_repo = ArtistRepository(session)
    album_repo = AlbumRepository(session)
    track_repo = TrackRepository(session)

    service = DeduplicationHousekeepingService(
        session=session,
        artist_repository=artist_repo,
        album_repository=album_repo,
        track_repository=track_repo,
    )

    duplicate_groups = await service.find_duplicate_artists()

    # Convert to API response format
    response_groups = []
    for group in duplicate_groups:
        artists = [group.canonical, *group.duplicates]
        response_groups.append({
            "artists": [
                {
                    "id": str(a.id),
                    "name": a.name,
                    "spotify_uri": a.spotify_uri,
                    "deezer_id": a.deezer_id,
                    "musicbrainz_id": a.musicbrainz_id,
                }
                for a in artists
            ],
            "match_reason": group.match_reason,
            "suggested_keep_id": str(group.canonical.id),
        })

    return {
        "duplicate_groups": response_groups,
        "total_groups": len(duplicate_groups),
        "total_duplicates": sum(len(g.duplicates) for g in duplicate_groups),
    }


@router.post(
    "/duplicates/artists/merge",
    summary="Merge duplicate artists",
)
async def merge_duplicate_artists(
    request: MergeRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Merge multiple artists into one.

    All tracks and albums from merge_ids artists will be transferred to keep_id artist.
    The merge_ids artists will be deleted after transfer.

    Args:
        keep_id: ID of artist to keep
        merge_ids: List of artist IDs to merge into keep artist
    """
    artist_repo = ArtistRepository(session)
    album_repo = AlbumRepository(session)
    track_repo = TrackRepository(session)

    service = DeduplicationHousekeepingService(
        session=session,
        artist_repository=artist_repo,
        album_repository=album_repo,
        track_repository=track_repo,
    )

    try:
        # Fetch the canonical artist
        canonical = await artist_repo.get_by_id(int(request.keep_id))
        if not canonical:
            raise ValueError(f"Artist {request.keep_id} not found")

        # Fetch duplicates
        duplicates = []
        for merge_id in request.merge_ids:
            dup = await artist_repo.get_by_id(int(merge_id))
            if dup:
                duplicates.append(dup)

        if not duplicates:
            raise ValueError("No valid merge_ids provided")

        # Create group and merge
        from soulspot.application.services.deduplication_housekeeping import (
            DuplicateGroup,
        )

        group = DuplicateGroup(
            entity_type="artist",
            canonical=canonical,
            duplicates=duplicates,
            match_reason="manual merge",
        )

        result = await service.merge_artist_group(group)

        if not result.success:
            raise ValueError(result.error or "Merge failed")

        return {
            "success": True,
            "kept_id": str(result.kept_id),
            "merged_ids": [str(mid) for mid in result.merged_ids],
            "albums_transferred": len(result.merged_ids),  # Approximate
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/duplicates/albums",
    summary="Find duplicate albums",
)
async def find_duplicate_albums(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Find potential duplicate albums by normalized name + artist matching.

    Returns groups of albums that might be duplicates.
    """
    artist_repo = ArtistRepository(session)
    album_repo = AlbumRepository(session)
    track_repo = TrackRepository(session)

    service = DeduplicationHousekeepingService(
        session=session,
        artist_repository=artist_repo,
        album_repository=album_repo,
        track_repository=track_repo,
    )

    duplicate_groups = await service.find_duplicate_albums()

    # Convert to API response format
    response_groups = []
    for group in duplicate_groups:
        albums = [group.canonical, *group.duplicates]
        response_groups.append({
            "albums": [
                {
                    "id": str(a.id),
                    "title": a.title,
                    "artist_id": str(a.artist_id) if a.artist_id else None,
                    "spotify_uri": a.spotify_uri,
                    "deezer_id": a.deezer_id,
                    "musicbrainz_id": a.musicbrainz_id,
                }
                for a in albums
            ],
            "match_reason": group.match_reason,
            "suggested_keep_id": str(group.canonical.id),
        })

    return {
        "duplicate_groups": response_groups,
        "total_groups": len(duplicate_groups),
        "total_duplicates": sum(len(g.duplicates) for g in duplicate_groups),
    }


@router.post(
    "/duplicates/albums/merge",
    summary="Merge duplicate albums",
)
async def merge_duplicate_albums(
    request: MergeRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Merge multiple albums into one.

    All tracks from merge_ids albums will be transferred to keep_id album.
    The merge_ids albums will be deleted after transfer.
    """
    artist_repo = ArtistRepository(session)
    album_repo = AlbumRepository(session)
    track_repo = TrackRepository(session)

    service = DeduplicationHousekeepingService(
        session=session,
        artist_repository=artist_repo,
        album_repository=album_repo,
        track_repository=track_repo,
    )

    try:
        # Fetch the canonical album
        canonical = await album_repo.get_by_id(int(request.keep_id))
        if not canonical:
            raise ValueError(f"Album {request.keep_id} not found")

        # Fetch duplicates
        duplicates = []
        for merge_id in request.merge_ids:
            dup = await album_repo.get_by_id(int(merge_id))
            if dup:
                duplicates.append(dup)

        if not duplicates:
            raise ValueError("No valid merge_ids provided")

        # Create group and merge
        from soulspot.application.services.deduplication_housekeeping import (
            DuplicateGroup,
        )

        group = DuplicateGroup(
            entity_type="album",
            canonical=canonical,
            duplicates=duplicates,
            match_reason="manual merge",
        )

        result = await service.merge_album_group(group)

        if not result.success:
            raise ValueError(result.error or "Merge failed")

        return {
            "success": True,
            "kept_id": str(result.kept_id),
            "merged_ids": [str(mid) for mid in result.merged_ids],
            "tracks_transferred": len(result.merged_ids),  # Approximate
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
