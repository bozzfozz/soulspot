"""Track management endpoints."""

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import (
    get_db_session,
    get_enrich_metadata_use_case,
    get_search_and_download_use_case,
    get_spotify_plugin,
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
from soulspot.infrastructure.persistence.repositories import TrackRepository

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

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


# Listen up, this searches Spotify for tracks matching query! Uses SpotifyPlugin which handles token
# management internally. The limit param caps results (max 100). We return simplified track objects (id,
# name, artists, album, duration) - not full Spotify track schema. This is for "search then download" flow or
# "add to playlist" features. The query can be anything: track name, artist, album, or even ISRC code!
@router.get("/search")
async def search_tracks(
    query: str = Query(..., description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Number of results"),
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Search for tracks.

    Args:
        query: Search query
        limit: Number of results to return
        spotify_plugin: SpotifyPlugin handles token management internally
        session: Database session

    Returns:
        Search results
    """
    # Provider + Auth checks using can_use()
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.domain.ports.plugin import PluginCapability

    app_settings = AppSettingsService(session)
    if not await app_settings.is_provider_enabled("spotify"):
        raise HTTPException(
            status_code=503,
            detail="Spotify provider is disabled in settings.",
        )
    if not spotify_plugin.can_use(PluginCapability.SEARCH_TRACKS):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with Spotify. Please connect your account first.",
        )

    try:
        # search_track returns PaginatedResponse[TrackDTO]
        result = await spotify_plugin.search_track(query, limit=limit)

        tracks = []
        for track_dto in result.items:
            # Build artists list from DTO - primary artist + additional artists
            artists_list = [{"name": track_dto.artist_name}]
            if track_dto.additional_artists:
                artists_list.extend([{"name": a.name} for a in track_dto.additional_artists])

            tracks.append(
                {
                    "id": track_dto.spotify_id,
                    "name": track_dto.title,
                    "artists": artists_list,
                    "album": {"name": track_dto.album_name},
                    "duration_ms": track_dto.duration_ms,
                    "uri": f"spotify:track:{track_dto.spotify_id}" if track_dto.spotify_id else None,
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


# Yo future me, this gets ONE track's full details with artist/album names! Uses Depends(get_db_session)
# to properly manage DB session lifecycle. joinedload() eagerly loads relationships to avoid N+1 queries.
# The hasattr checks on album are because Album model might not have "artist" or "year" fields depending
# on how it's set up. genre field now comes from TrackModel.genre (populated by library scanner from
# audio file tags). Returns flat dict which is easy for frontend to consume. The unique() call prevents
# duplicate results when joins create multiple rows. scalar_one_or_none() returns Track or None - perfect for 404 check.
@router.get("/{track_id}")
async def get_track(
    track_id: str,
    _track_repository: TrackRepository = Depends(get_track_repository),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get track details.

    Args:
        track_id: Track ID
        track_repository: Track repository
        session: Database session

    Returns:
        Track details
    """
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from soulspot.infrastructure.persistence.models import TrackModel

    try:
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
            "genre": track_model.genre,  # Hey - now returns actual genre from DB!
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
                logger.warning(
                    "Failed to update file tags for track %s: %s",
                    track_id,
                    e,
                    exc_info=True,
                )

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
