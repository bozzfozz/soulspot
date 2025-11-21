"""Track management endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from soulspot.api.dependencies import (
    get_enrich_metadata_use_case,
    get_search_and_download_use_case,
    get_spotify_client,
    get_track_repository,
)
from soulspot.application.use_cases.enrich_metadata import (
    EnrichMetadataRequest,
    EnrichMetadataUseCase,
)
from soulspot.application.use_cases.search_and_download import (
    SearchAndDownloadTrackRequest,
    SearchAndDownloadTrackUseCase,
)
from soulspot.domain.value_objects import TrackId
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
from soulspot.infrastructure.persistence.repositories import TrackRepository

router = APIRouter()
logger = logging.getLogger(__name__)


# Hey future me, this endpoint kicks off a track download! It uses the SearchAndDownloadTrackUseCase which
# searches Soulseek, picks best result based on quality preference ("best"=highest bitrate, "any"=first match),
# and queues the download. If search finds nothing or download fails to start, we return 400 error. The response
# includes download_id for tracking and search_results_count so you know if search was good (10 results) or
# weak (1 result = might be wrong file!). This is ASYNC - download happens in background, don't wait for completion!
@router.post("/{track_id}/download")
async def download_track(
    track_id: str,
    quality: str = Query("best", description="Quality preference: best, good, any"),
    use_case: SearchAndDownloadTrackUseCase = Depends(get_search_and_download_use_case),
) -> dict[str, Any]:
    """Download a track.

    Args:
        track_id: Track ID to download
        quality: Quality preference
        use_case: Search and download use case

    Returns:
        Download status
    """
    track_id_obj = TrackId.from_string(track_id)
    request = SearchAndDownloadTrackRequest(
        track_id=track_id_obj,
        quality_preference=quality,
    )
    response = await use_case.execute(request)

    if response.status.value == "failed":
        raise HTTPException(
            status_code=400, detail=response.error_message or "Download failed"
        )

    return {
        "message": "Download started",
        "track_id": track_id,
        "download_id": str(response.download.id.value),
        "quality": quality,
        "status": response.status.value,
        "search_results_count": response.search_results_count,
    }


# Yo, this enriches ONE track with metadata from MusicBrainz (genres, release dates, artwork URLs, etc).
# The force_refresh flag bypasses cache - only use if metadata is wrong! MusicBrainz has STRICT rate limits
# (1 req/sec), so this can take 1-3 seconds. If track not found in MB, we return enriched=false but 200 OK
# (not 404 - track exists in our DB, just no MB data). The enriched_fields list tells you what changed. This
# updates our DB but doesn't write to file tags - use the PATCH endpoint for that!
@router.post("/{track_id}/enrich")
async def enrich_track(
    track_id: str,
    force_refresh: bool = Query(False, description="Force refresh metadata"),
    use_case: EnrichMetadataUseCase = Depends(get_enrich_metadata_use_case),
) -> dict[str, Any]:
    """Enrich track metadata from MusicBrainz.

    Args:
        track_id: Track ID to enrich
        force_refresh: Force refresh even if already enriched
        use_case: Enrich metadata use case

    Returns:
        Enrichment status
    """
    try:
        track_id_obj = TrackId.from_string(track_id)
        request = EnrichMetadataRequest(
            track_id=track_id_obj,
            force_refresh=force_refresh,
        )
        response = await use_case.execute(request)

        return {
            "message": "Track enriched successfully"
            if response.enriched_fields
            else "Track not found in MusicBrainz",
            "track_id": track_id,
            "enriched": bool(response.enriched_fields),
            "enriched_fields": response.enriched_fields,
            "musicbrainz_id": response.track.musicbrainz_id if response.track else None,
            "errors": response.errors,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid track ID: {str(e)}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to enrich metadata: {str(e)}"
        ) from e


# Listen up, this searches Spotify for tracks matching query! Requires access_token because we hit Spotify API
# directly (not using our DB). The limit param caps results (max 100). We return simplified track objects (id,
# name, artists, album, duration) - not full Spotify track schema. This is for "search then download" flow or
# "add to playlist" features. If access_token is expired, Spotify returns 401 and we bubble it up as 500 (should
# be 401!). The query can be anything: track name, artist, album, or even ISRC code (Spotify is smart!).
@router.get("/search")
async def search_tracks(
    query: str = Query(..., description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Number of results"),
    access_token: str = Query(..., description="Spotify access token"),
    spotify_client: SpotifyClient = Depends(get_spotify_client),
) -> dict[str, Any]:
    """Search for tracks.

    Args:
        query: Search query
        limit: Number of results to return
        access_token: Spotify access token
        spotify_client: Spotify client

    Returns:
        Search results
    """
    try:
        results = await spotify_client.search_track(query, access_token, limit=limit)

        tracks = []
        for item in results.get("tracks", {}).get("items", []):
            tracks.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "artists": [
                        {"name": artist["name"]} for artist in item.get("artists", [])
                    ],
                    "album": {"name": item.get("album", {}).get("name")},
                    "duration_ms": item.get("duration_ms"),
                    "uri": item.get("uri"),
                }
            )

        return {
            "tracks": tracks,
            "total": len(tracks),
            "query": query,
            "limit": limit,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}") from e


# Yo future me, this gets ONE track's full details with artist/album names! Uses anext() to grab
# DB session from generator - bit sketchy (should use Depends). joinedload() eagerly loads relationships
# to avoid N+1 queries. The hasattr checks on album are because Album model might not have "artist" or
# "year" fields depending on how it's set up. genre is hardcoded None (TODO) - should add to Track model.
# Returns flat dict which is easy for frontend to consume. The unique() call prevents duplicate results
# when joins create multiple rows. scalar_one_or_none() returns Track or None - perfect for 404 check.
@router.get("/{track_id}")
async def get_track(
    request: Request,
    track_id: str,
    _track_repository: TrackRepository = Depends(get_track_repository),
) -> dict[str, Any]:
    """Get track details.

    Args:
        track_id: Track ID
        track_repository: Track repository

    Returns:
        Track details
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import joinedload

    from soulspot.api.dependencies import get_db_session
    from soulspot.infrastructure.persistence.models import TrackModel

    try:
        # Get session for direct DB query to include artist/album names
        session: AsyncSession = await anext(get_db_session(request))

        stmt = (
            select(TrackModel)
            .where(TrackModel.id == track_id)
            .options(joinedload(TrackModel.artist), joinedload(TrackModel.album))
        )
        result = await session.execute(stmt)
        track_model = result.unique().scalar_one_or_none()

        if not track_model:
            raise HTTPException(status_code=404, detail="Track not found")

        return {
            "id": track_model.id,
            "title": track_model.title,
            "artist": track_model.artist.name if track_model.artist else None,
            "album": track_model.album.title if track_model.album else None,
            "album_artist": track_model.album.artist
            if track_model.album and hasattr(track_model.album, "artist")
            else None,
            "genre": None,  # TODO: Add genre field to track model
            "year": track_model.album.year
            if track_model.album and hasattr(track_model.album, "year")
            else None,
            "artist_id": track_model.artist_id,
            "album_id": track_model.album_id,
            "duration_ms": track_model.duration_ms,
            "track_number": track_model.track_number,
            "disc_number": track_model.disc_number,
            "spotify_uri": track_model.spotify_uri,
            "musicbrainz_id": track_model.musicbrainz_id,
            "isrc": track_model.isrc,
            "file_path": track_model.file_path,
            "created_at": track_model.created_at.isoformat(),
            "updated_at": track_model.updated_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid track ID: {str(e)}"
        ) from e


# Yo future me, this is the MANUAL metadata editor - update track info by hand! We have an allowed_fields list
# to prevent users from modifying internal fields (spotify_id, created_at, etc). After updating our DB, we ALSO
# write to file's ID3 tags using mutagen! This is CRITICAL - if you only update DB, the file still has old tags
# and re-scans will overwrite your changes! The mutagen code uses add() not set() because we want to REPLACE
# tags, not append. If file doesn't exist or tag writing fails, we LOG warning but DON'T fail the request (DB
# update succeeded, that's what matters!). Encoding=3 means UTF-8 for international characters.
@router.patch("/{track_id}/metadata")
async def update_track_metadata(
    track_id: str,
    metadata: dict[str, Any],
    track_repository: TrackRepository = Depends(get_track_repository),
) -> dict[str, Any]:
    """Update track metadata.

    Args:
        track_id: Track ID
        metadata: Dictionary of metadata fields to update
        track_repository: Track repository

    Returns:
        Updated track details
    """
    try:
        track_id_obj = TrackId.from_string(track_id)
        track = await track_repository.get_by_id(track_id_obj)

        if not track:
            raise HTTPException(status_code=404, detail="Track not found")

        # Update allowed metadata fields
        allowed_fields = [
            "title",
            "artist",
            "album",
            "album_artist",
            "genre",
            "year",
            "track_number",
            "disc_number",
        ]

        for field in allowed_fields:
            if field in metadata:
                setattr(track, field, metadata[field])

        # Save updated track
        await track_repository.update(track)

        # If file exists, update file metadata tags
        if track.file_path and track.file_path.exists():
            try:
                # Import here to avoid circular dependencies
                from mutagen.id3 import (  # type: ignore[attr-defined]
                    ID3,
                    TALB,
                    TCON,
                    TDRC,
                    TIT2,
                    TPE1,
                    TPE2,
                    TPOS,
                    TRCK,
                )
                from mutagen.mp3 import MP3

                audio = MP3(str(track.file_path), ID3=ID3)

                # Add ID3 tag if it doesn't exist
                if audio.tags is None:
                    audio.add_tags()  # type: ignore[no-untyped-call]

                # Update tags
                if "title" in metadata:
                    audio.tags.add(TIT2(encoding=3, text=metadata["title"]))  # type: ignore[no-untyped-call]
                if "artist" in metadata:
                    audio.tags.add(TPE1(encoding=3, text=metadata["artist"]))  # type: ignore[no-untyped-call]
                if "album" in metadata:
                    audio.tags.add(TALB(encoding=3, text=metadata["album"]))  # type: ignore[no-untyped-call]
                if "album_artist" in metadata:
                    audio.tags.add(TPE2(encoding=3, text=metadata["album_artist"]))  # type: ignore[no-untyped-call]
                if "genre" in metadata:
                    audio.tags.add(TCON(encoding=3, text=metadata["genre"]))  # type: ignore[no-untyped-call]
                if "year" in metadata:
                    audio.tags.add(TDRC(encoding=3, text=str(metadata["year"])))  # type: ignore[no-untyped-call]
                if "track_number" in metadata:
                    audio.tags.add(TRCK(encoding=3, text=str(metadata["track_number"])))  # type: ignore[no-untyped-call]
                if "disc_number" in metadata:
                    audio.tags.add(TPOS(encoding=3, text=str(metadata["disc_number"])))  # type: ignore[no-untyped-call]

                audio.save()
            except Exception as e:
                # Log error but don't fail the request
                logger.warning("Failed to update file tags for track %s: %s", track_id, e, exc_info=True)

        return {
            "message": "Metadata updated successfully",
            "track_id": track_id,
            "updated_fields": list(metadata.keys()),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid track ID: {str(e)}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update metadata: {str(e)}"
        ) from e
