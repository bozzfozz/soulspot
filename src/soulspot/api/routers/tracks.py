"""Track management endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

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
    try:
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
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid track ID: {str(e)}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start download: {str(e)}"
        ) from e


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


@router.get("/{track_id}")
async def get_track(
    track_id: str,
    track_repository: TrackRepository = Depends(get_track_repository),
) -> dict[str, Any]:
    """Get track details.

    Args:
        track_id: Track ID
        track_repository: Track repository

    Returns:
        Track details
    """
    try:
        track_id_obj = TrackId.from_string(track_id)
        track = await track_repository.get_by_id(track_id_obj)

        if not track:
            raise HTTPException(status_code=404, detail="Track not found")

        return {
            "id": str(track.id.value),
            "title": track.title,
            "artist": track.artist,
            "album": track.album,
            "album_artist": track.album_artist,
            "genre": track.genre,
            "year": track.year,
            "artist_id": str(track.artist_id.value),
            "album_id": str(track.album_id.value) if track.album_id else None,
            "duration_ms": track.duration_ms,
            "track_number": track.track_number,
            "disc_number": track.disc_number,
            "spotify_uri": str(track.spotify_uri) if track.spotify_uri else None,
            "musicbrainz_id": track.musicbrainz_id,
            "isrc": track.isrc,
            "file_path": str(track.file_path) if track.file_path else None,
            "created_at": track.created_at.isoformat(),
            "updated_at": track.updated_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid track ID: {str(e)}"
        ) from e


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
                from mutagen.mp3 import MP3
                from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TCON, TDRC, TRCK, TPOS

                audio = MP3(str(track.file_path), ID3=ID3)
                
                # Add ID3 tag if it doesn't exist
                if audio.tags is None:
                    audio.add_tags()

                # Update tags
                if "title" in metadata:
                    audio.tags.add(TIT2(encoding=3, text=metadata["title"]))
                if "artist" in metadata:
                    audio.tags.add(TPE1(encoding=3, text=metadata["artist"]))
                if "album" in metadata:
                    audio.tags.add(TALB(encoding=3, text=metadata["album"]))
                if "album_artist" in metadata:
                    audio.tags.add(TPE2(encoding=3, text=metadata["album_artist"]))
                if "genre" in metadata:
                    audio.tags.add(TCON(encoding=3, text=metadata["genre"]))
                if "year" in metadata:
                    audio.tags.add(TDRC(encoding=3, text=str(metadata["year"])))
                if "track_number" in metadata:
                    audio.tags.add(TRCK(encoding=3, text=str(metadata["track_number"])))
                if "disc_number" in metadata:
                    audio.tags.add(TPOS(encoding=3, text=str(metadata["disc_number"])))

                audio.save()
            except Exception as e:
                # Log error but don't fail the request
                print(f"Warning: Failed to update file tags: {e}")

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
