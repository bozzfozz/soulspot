# AI-Model: Copilot
"""Artist management API endpoints.

Hey future me - this router handles syncing followed artists from Spotify to our DB.
The flow is: User clicks "sync" → we fetch all followed artists from Spotify → create/update
them in our artists table → return the list. Artists can also be deleted individually.
This is separate from watchlists (which track NEW releases) - this is just the artist catalog!
"""

import logging

# Hey future me - we use TYPE_CHECKING for SpotifyPlugin to avoid circular imports!
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import (
    get_db_session,
    get_spotify_plugin,
    get_spotify_plugin_optional,
)
from soulspot.application.services.followed_artists_service import (
    FollowedArtistsService,
)
from soulspot.domain.value_objects import ArtistId
from soulspot.infrastructure.persistence.repositories import ArtistRepository

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/artists", tags=["Artists"])


# Hey future me - these are the response DTOs for the artists API. ArtistResponse maps
# the domain Artist entity to what the frontend needs. Keep it flat (no nested objects)
# for easy JSON serialization. genres is list[str] from the DB JSON field.
# Hey - source field shows where artist comes from! 'local' = file scan, 'spotify' = followed,
# 'hybrid' = both. UI uses this for badges (🎵 Local | 🎧 Spotify | 🌟 Both).
class ArtistResponse(BaseModel):
    """Response model for an artist."""

    id: str = Field(..., description="Artist UUID")
    name: str = Field(..., description="Artist name")
    source: str = Field(..., description="Artist source: local, spotify, or hybrid")
    spotify_uri: str | None = Field(
        None, description="Spotify URI (e.g., spotify:artist:xxxx)"
    )
    musicbrainz_id: str | None = Field(None, description="MusicBrainz ID")
    image_url: str | None = Field(None, description="Artist profile image URL")
    genres: list[str] = Field(default_factory=list, description="Artist genres")
    created_at: str = Field(..., description="ISO 8601 timestamp")
    updated_at: str = Field(..., description="ISO 8601 timestamp")


class SyncArtistsResponse(BaseModel):
    """Response model for sync operation."""

    artists: list[ArtistResponse] = Field(..., description="List of synced artists")
    stats: dict[str, int] = Field(..., description="Sync statistics")
    message: str = Field(..., description="Status message")


class ArtistListResponse(BaseModel):
    """Response model for listing artists."""

    artists: list[ArtistResponse] = Field(..., description="List of artists")
    total_count: int = Field(..., description="Total number of artists in DB")
    limit: int = Field(..., description="Pagination limit used")
    offset: int = Field(..., description="Pagination offset used")


# Hey future me - this converts a domain Artist entity to an ArtistResponse DTO.
# The datetime formatting is done here to keep the domain clean. Spotify URI is
# converted to string if present. This is called for each artist in lists.
# The source field is converted from enum to string for JSON serialization.
def _artist_to_response(artist: Any) -> ArtistResponse:
    """Convert domain Artist to ArtistResponse DTO.

    Args:
        artist: Domain Artist entity

    Returns:
        ArtistResponse DTO for API response
    """
    return ArtistResponse(
        id=str(artist.id.value),
        name=artist.name,
        source=artist.source.value,  # Convert enum to string: 'local', 'spotify', 'hybrid'
        spotify_uri=str(artist.spotify_uri) if artist.spotify_uri else None,
        musicbrainz_id=artist.musicbrainz_id,
        image_url=artist.image.url,  # ImageRef.url for CDN/cached image URL
        genres=artist.genres or [],
        created_at=artist.created_at.isoformat(),
        updated_at=artist.updated_at.isoformat(),
    )


# Hey future me - DEBUG endpoint to check what artists are in DB by name.
# Useful for debugging "already in library" issues.
# Usage: GET /api/artists/debug/search?name=Nosferatu
@router.get("/debug/search")
async def debug_search_artists(
    name: str = Query(..., description="Artist name to search for"),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Debug endpoint: Search artists by name in DB.
    
    Returns all matching artists with their source info.
    Case-insensitive partial match.
    """
    from sqlalchemy import select, func
    from soulspot.infrastructure.persistence.models import ArtistModel
    
    stmt = select(ArtistModel).where(
        func.lower(ArtistModel.name).contains(name.lower())
    )
    result = await session.execute(stmt)
    artists = result.scalars().all()
    
    return {
        "query": name,
        "count": len(artists),
        "artists": [
            {
                "id": str(a.id),
                "name": a.name,
                "source": a.source,
                "spotify_uri": a.spotify_uri,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in artists
        ]
    }


# Yo, this is the MAIN sync endpoint! It fetches ALL followed artists from Spotify (paginated
# internally) and creates/updates them in our DB. Uses shared server-side token so any device
# can trigger sync. Returns the full list of synced artists plus stats (created/updated counts).
# This is idempotent - safe to call multiple times. Duplicate prevention is by spotify_uri.
# POST because it modifies DB state.
@router.post("/sync", response_model=SyncArtistsResponse)
async def sync_followed_artists(
    session: AsyncSession = Depends(get_db_session),
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
) -> SyncArtistsResponse:
    """Sync followed artists from Spotify to the database.

    Hey future me - refactored to use SpotifyPlugin!
    No more access_token - plugin handles auth internally.
    Fetches all artists the user follows on Spotify and creates/updates them
    in the local database. Uses spotify_uri as unique key to prevent duplicates.

    Also respects is_provider_enabled("spotify") - if Spotify is disabled in settings,
    returns early with a message instead of making API calls.

    Args:
        session: Database session
        spotify_plugin: SpotifyPlugin for Spotify API calls

    Returns:
        List of synced artists and sync statistics

    Raises:
        HTTPException: If Spotify API fails or authentication issues
    """
    # Check if Spotify provider is enabled + auth using can_use()
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.domain.ports.plugin import PluginCapability

    app_settings = AppSettingsService(session)
    if not await app_settings.is_provider_enabled("spotify"):
        raise HTTPException(
            status_code=503,
            detail="Spotify provider is disabled in settings. Enable it to sync artists.",
        )

    # can_use() checks capability + auth in one call
    if not spotify_plugin.can_use(PluginCapability.USER_FOLLOWED_ARTISTS):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with Spotify. Please connect your account first.",
        )

    try:
        # Create DeezerPlugin for fallback (NO AUTH NEEDED!)
        from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

        deezer_plugin = DeezerPlugin()

        service = FollowedArtistsService(
            session=session,
            spotify_plugin=spotify_plugin,
            deezer_plugin=deezer_plugin,
        )

        artists, stats = await service.sync_followed_artists()

        # Commit the transaction to persist changes
        await session.commit()

        logger.info(
            f"Synced {len(artists)} followed artists from Spotify: "
            f"{stats['created']} created, {stats['updated']} updated"
        )

        return SyncArtistsResponse(
            artists=[_artist_to_response(a) for a in artists],
            stats=stats,
            message=(
                f"Successfully synced {len(artists)} artists. "
                f"Created: {stats['created']}, Updated: {stats['updated']}, "
                f"Errors: {stats['errors']}"
            ),
        )
    except Exception as e:
        await session.rollback()
        from soulspot.infrastructure.observability.log_messages import LogMessages

        logger.error(
            LogMessages.sync_failed(
                entity="Followed Artists",
                source="Spotify",
                error=str(e),
                hint="Check Spotify authentication in Settings → Providers → Spotify",
            ),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync followed artists: {str(e)}",
        ) from e


# Hey future me - MULTI-PROVIDER Sync!
# This endpoint syncs followed artists from ALL enabled providers (Spotify + Deezer).
# Each provider needs its own OAuth authentication. Artists are deduplicated across providers.
@router.post("/sync/all-providers", response_model=dict)
async def sync_followed_artists_all_providers(
    session: AsyncSession = Depends(get_db_session),
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
) -> dict:
    """Sync followed artists from ALL providers to unified library.

    Hey future me - this is the MULTI-PROVIDER sync endpoint!
    Aggregates followed artists from Spotify AND Deezer (both require OAuth).
    Each artist is deduplicated across providers.

    Returns:
        Dict with aggregated stats per provider and total counts
    """
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

    try:
        # Create DeezerPlugin with potential OAuth token
        deezer_plugin = DeezerPlugin()

        service = FollowedArtistsService(
            session=session,
            spotify_plugin=spotify_plugin,
            deezer_plugin=deezer_plugin,
        )

        artists, stats = await service.sync_followed_artists_all_providers()

        await session.commit()

        logger.info(
            f"Multi-provider sync complete: {stats['total_fetched']} total, "
            f"Spotify: {stats.get('providers', {}).get('spotify', {}).get('total_fetched', 0)}, "
            f"Deezer: {stats.get('providers', {}).get('deezer', {}).get('total_fetched', 0)}"
        )

        return {
            "success": True,
            "total_artists": len(artists),
            "stats": stats,
            "message": (
                f"Synced {stats['total_fetched']} artists from all providers. "
                f"Created: {stats['total_created']}, Updated: {stats['total_updated']}"
            ),
        }
    except Exception as e:
        await session.rollback()
        logger.error(f"Multi-provider sync failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync followed artists from all providers: {str(e)}",
        ) from e


# Hey future me - this lists artists from unified Music Manager view (LOCAL + SPOTIFY)!
# Uses get_all_artists_unified() which returns artists with correct source field.
# Supports filtering by source: ?source=local (only local files), ?source=spotify (followed),
# ?source=hybrid (both), or no filter (all artists). Sorted alphabetically by name.
# Pagination via limit/offset. Returns total count for UI pagination controls.
@router.get("", response_model=ArtistListResponse)
async def list_artists(
    limit: int = Query(
        100, ge=1, le=500, description="Maximum number of artists to return"
    ),
    offset: int = Query(0, ge=0, description="Number of artists to skip"),
    source: str | None = Query(
        None,
        description="Filter by source: 'local', 'spotify', 'hybrid', or None for all",
    ),
    session: AsyncSession = Depends(get_db_session),
) -> ArtistListResponse:
    """List all artists from unified Music Manager view (LOCAL + SPOTIFY).

    Returns paginated list of artists with source field indicating origin:
    - 'local': Artist from local file scan only
    - 'spotify': Followed artist on Spotify only
    - 'hybrid': Artist exists in both local library and Spotify

    Artists are sorted alphabetically by name.

    Args:
        limit: Maximum number of artists to return (1-500)
        offset: Number of artists to skip for pagination
        source: Optional filter by source type ('local', 'spotify', 'hybrid')
        session: Database session

    Returns:
        Paginated list of artists with total count
    """
    repo = ArtistRepository(session)

    # Use unified view that includes source field
    artists = await repo.get_all_artists_unified(
        limit=limit, offset=offset, source_filter=source
    )
    total_count = await repo.count_by_source(source=source)

    return ArtistListResponse(
        artists=[_artist_to_response(a) for a in artists],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


@router.get("/count", response_model=dict[str, int])
async def count_artists(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, int]:
    """Get total count of artists in the database.

    Args:
        session: Database session

    Returns:
        Dictionary with total_count key
    """
    repo = ArtistRepository(session)
    total = await repo.count_all()

    return {"total_count": total}


# Hey future me - this is the "Add to Library" endpoint from Discovery page!
# It creates an artist in the local DB from discovered/related artist data.
# Deduplication: If artist with same spotify_id or deezer_id exists, returns existing.
# If artist with same name exists (fuzzy match), returns existing to avoid duplicates.
# Source is set to 'local' since user is explicitly adding to their library.
class AddArtistRequest(BaseModel):
    """Request model for adding an artist to the library."""

    name: str = Field(..., description="Artist name")
    spotify_id: str | None = Field(None, description="Spotify artist ID (not full URI)")
    deezer_id: str | None = Field(None, description="Deezer artist ID")
    image_url: str | None = Field(None, description="Artist image URL")


class AddArtistResponse(BaseModel):
    """Response model for add artist operation."""

    artist: ArtistResponse
    created: bool = Field(..., description="True if new artist created, False if existing returned")
    message: str


@router.post("", response_model=AddArtistResponse, status_code=201)
async def add_artist_to_library(
    request: AddArtistRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AddArtistResponse:
    """Add an artist to the local library from Discovery/Similar Artists.

    Hey future me - this endpoint is called when user clicks "Add to Library" on
    Discovery page. It creates a LOCAL artist entry (not synced from streaming service).
    
    Deduplication logic:
    1. If spotify_id provided, check for existing artist with that spotify_uri
    2. If deezer_id provided, check for existing artist with that deezer_id
    3. Otherwise, check by normalized name (case-insensitive)
    
    If duplicate found, returns existing artist with created=False.
    If new, creates artist with source='local' and returns with created=True.

    Args:
        request: Artist data from discovery
        session: Database session

    Returns:
        Created or existing artist with status indicator
    """
    # Hey future me - DEBUG LOGGING to catch wrong artist issues!
    # If all Add clicks show same artist name (e.g. "Nosferatu"), check these values!
    logger.debug(
        "ADD ARTIST REQUEST: name=%r, spotify_id=%r, deezer_id=%r",
        request.name,
        request.spotify_id,
        request.deezer_id,
    )
    
    from soulspot.domain.entities import Artist, ArtistSource
    from soulspot.domain.value_objects import ImageRef, SpotifyUri

    repo = ArtistRepository(session)

    # Hey future me - ONLY check if artist exists as LOCAL or HYBRID source!
    # Spotify-only synced artists (source='spotify') should NOT block adding!
    # User wants to add artist to their LOCAL library, not check streaming follows.
    
    # Check for existing LOCAL/HYBRID artist by spotify_uri
    if request.spotify_id:
        spotify_uri = SpotifyUri.from_string(f"spotify:artist:{request.spotify_id}")
        existing = await repo.get_by_spotify_uri(spotify_uri)
        if existing and existing.source in (ArtistSource.LOCAL, ArtistSource.HYBRID):
            logger.info(f"Artist already exists locally (spotify_uri): {existing.name}")
            return AddArtistResponse(
                artist=_artist_to_response(existing),
                created=False,
                message=f"Artist '{existing.name}' already in library",
            )
        elif existing:
            # Artist exists but only from Spotify sync - upgrade to HYBRID
            logger.info(f"Upgrading artist from spotify to hybrid: {existing.name}")
            existing.source = ArtistSource.HYBRID
            await repo.update(existing)
            await session.commit()
            return AddArtistResponse(
                artist=_artist_to_response(existing),
                created=False,
                message=f"Artist '{existing.name}' upgraded to local library",
            )

    # Check for existing LOCAL/HYBRID artist by deezer_id
    if request.deezer_id:
        existing = await repo.get_by_deezer_id(request.deezer_id)
        if existing and existing.source in (ArtistSource.LOCAL, ArtistSource.HYBRID):
            logger.info(f"Artist already exists locally (deezer_id): {existing.name}")
            return AddArtistResponse(
                artist=_artist_to_response(existing),
                created=False,
                message=f"Artist '{existing.name}' already in library",
            )
        elif existing:
            # Artist exists but only from Deezer sync - upgrade to HYBRID
            logger.info(f"Upgrading artist from deezer to hybrid: {existing.name}")
            existing.source = ArtistSource.HYBRID
            await repo.update(existing)
            await session.commit()
            return AddArtistResponse(
                artist=_artist_to_response(existing),
                created=False,
                message=f"Artist '{existing.name}' upgraded to local library",
            )

    # Check for existing LOCAL/HYBRID artist by name (normalized)
    existing = await repo.get_by_name(request.name)
    if existing and existing.source in (ArtistSource.LOCAL, ArtistSource.HYBRID):
        logger.info(f"Artist already exists locally (name): {existing.name}")
        return AddArtistResponse(
            artist=_artist_to_response(existing),
            created=False,
            message=f"Artist '{existing.name}' already in library",
        )
    elif existing:
        # Artist exists but only from streaming sync - upgrade to HYBRID
        logger.info(f"Upgrading artist from streaming to hybrid: {existing.name}")
        existing.source = ArtistSource.HYBRID
        # Also update spotify_id/deezer_id if provided
        if request.spotify_id and not existing.spotify_uri:
            existing.spotify_uri = SpotifyUri.from_string(f"spotify:artist:{request.spotify_id}")
        if request.deezer_id and not existing.deezer_id:
            existing.deezer_id = request.deezer_id
        await repo.update(existing)
        await session.commit()
        return AddArtistResponse(
            artist=_artist_to_response(existing),
            created=False,
            message=f"Artist '{existing.name}' upgraded to local library",
        )

    # Create new artist
    artist = Artist(
        id=ArtistId.generate(),
        name=request.name,
        source=ArtistSource.LOCAL,  # User is adding to LOCAL library
        spotify_uri=SpotifyUri.from_string(f"spotify:artist:{request.spotify_id}") if request.spotify_id else None,
        deezer_id=request.deezer_id,
        image=ImageRef(url=request.image_url) if request.image_url else ImageRef(),
    )

    await repo.add(artist)
    await session.commit()

    logger.info(f"Added artist to library: {artist.name} (id={artist.id})")

    return AddArtistResponse(
        artist=_artist_to_response(artist),
        created=True,
        message=f"Artist '{artist.name}' added to library",
    )


@router.get("/{artist_id}", response_model=ArtistResponse)
async def get_artist(
    artist_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> ArtistResponse:
    """Get a specific artist by ID.

    Args:
        artist_id: Artist UUID
        session: Database session

    Returns:
        Artist details

    Raises:
        HTTPException: 404 if artist not found
    """
    repo = ArtistRepository(session)

    try:
        artist_id_obj = ArtistId.from_string(artist_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid artist ID format: {e}"
        ) from e

    artist = await repo.get_by_id(artist_id_obj)

    if not artist:
        raise HTTPException(status_code=404, detail=f"Artist not found: {artist_id}")

    return _artist_to_response(artist)


@router.delete("/{artist_id}", status_code=204)
async def delete_artist(
    artist_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete an artist from the database.

    Removes the artist and cascades to delete their albums and tracks.
    This is a destructive operation - use with caution!

    Args:
        artist_id: Artist UUID to delete
        session: Database session

    Raises:
        HTTPException: 404 if artist not found, 400 if invalid ID format
    """
    repo = ArtistRepository(session)

    try:
        artist_id_obj = ArtistId.from_string(artist_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid artist ID format: {e}"
        ) from e

    # Check if artist exists first (repository.delete raises exception if not found)
    artist = await repo.get_by_id(artist_id_obj)
    if not artist:
        raise HTTPException(status_code=404, detail=f"Artist not found: {artist_id}")

    await repo.delete(artist_id_obj)
    await session.commit()

    logger.info(f"Deleted artist: {artist.name} (id: {artist_id})")


# =========================================================================
# SPOTIFY FOLLOW/UNFOLLOW ENDPOINTS
# =========================================================================
# Hey future me - these endpoints let users follow/unfollow artists on Spotify directly!
# This is for the Search Page "Add to Followed Artists" feature.
# - POST /artists/spotify/{spotify_id}/follow → Follow artist on Spotify
# - DELETE /artists/spotify/{spotify_id}/follow → Unfollow artist on Spotify
# - GET /artists/spotify/following-status → Check if following multiple artists
# All use the shared token since we have single-user architecture.
# =========================================================================


class FollowArtistResponse(BaseModel):
    """Response model for follow/unfollow operations."""

    success: bool = Field(..., description="Whether the operation succeeded")
    spotify_id: str = Field(..., description="Spotify artist ID")
    message: str = Field(..., description="Status message")


class FollowingStatusRequest(BaseModel):
    """Request model for checking following status."""

    artist_ids: list[str] = Field(
        ..., description="List of Spotify artist IDs to check", max_length=50
    )


class FollowingStatusResponse(BaseModel):
    """Response model for following status check."""

    statuses: dict[str, bool] = Field(
        ..., description="Map of artist_id → is_following"
    )


@router.post(
    "/spotify/{spotify_id}/follow",
    response_model=FollowArtistResponse,
    summary="Follow an artist on Spotify",
)
async def follow_artist_on_spotify(
    spotify_id: str,
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> FollowArtistResponse:
    """Follow an artist on Spotify.

    Adds the artist to the user's followed artists on Spotify. After following,
    the artist will appear in the user's Spotify library and in sync_followed_artists().

    Args:
        spotify_id: Spotify artist ID (e.g., "3WrFJ7ztbogyGnTHbHJFl2")
        spotify_plugin: SpotifyPlugin handles token management internally
        session: Database session

    Returns:
        Success status and message

    Raises:
        HTTPException: 400 if invalid artist ID, 500 if Spotify API fails
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
    if not spotify_plugin.can_use(PluginCapability.FOLLOW_ARTIST):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with Spotify. Please connect your account first.",
        )

    try:
        await spotify_plugin.follow_artists([spotify_id])

        logger.info(f"Followed artist on Spotify: {spotify_id}")

        return FollowArtistResponse(
            success=True,
            spotify_id=spotify_id,
            message="Successfully followed artist on Spotify",
        )
    except Exception as e:
        logger.error(f"Failed to follow artist {spotify_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to follow artist: {str(e)}",
        ) from e


@router.delete(
    "/spotify/{spotify_id}/follow",
    response_model=FollowArtistResponse,
    summary="Unfollow an artist on Spotify",
)
async def unfollow_artist_on_spotify(
    spotify_id: str,
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> FollowArtistResponse:
    """Unfollow an artist on Spotify.

    Removes the artist from the user's followed artists on Spotify. After unfollowing,
    the artist will no longer appear in sync_followed_artists().

    Args:
        spotify_id: Spotify artist ID (e.g., "3WrFJ7ztbogyGnTHbHJFl2")
        spotify_plugin: SpotifyPlugin handles token management internally
        session: Database session

    Returns:
        Success status and message

    Raises:
        HTTPException: 400 if invalid artist ID, 500 if Spotify API fails
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
    if not spotify_plugin.can_use(PluginCapability.UNFOLLOW_ARTIST):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with Spotify. Please connect your account first.",
        )

    try:
        await spotify_plugin.unfollow_artists([spotify_id])

        logger.info(f"Unfollowed artist on Spotify: {spotify_id}")

        return FollowArtistResponse(
            success=True,
            spotify_id=spotify_id,
            message="Successfully unfollowed artist on Spotify",
        )
    except Exception as e:
        logger.error(f"Failed to unfollow artist {spotify_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to unfollow artist: {str(e)}",
        ) from e


@router.post(
    "/spotify/following-status",
    response_model=FollowingStatusResponse,
    summary="Check if user follows multiple artists",
)
async def check_following_status(
    request: FollowingStatusRequest,
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> FollowingStatusResponse:
    """Check if user follows one or more artists on Spotify.

    Use this to display "Following" vs "Follow" button states in the search results.
    Returns a map of artist_id → is_following for efficient batch checking.

    Args:
        request: List of Spotify artist IDs to check (max 50)
        spotify_plugin: SpotifyPlugin handles token management internally
        session: Database session

    Returns:
        Map of artist_id → is_following status

    Raises:
        HTTPException: 400 if too many IDs, 500 if Spotify API fails
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
    # USER_FOLLOWED_ARTISTS capability is needed to check following status
    if not spotify_plugin.can_use(PluginCapability.USER_FOLLOWED_ARTISTS):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with Spotify. Please connect your account first.",
        )

    if len(request.artist_ids) > 50:
        raise HTTPException(
            status_code=400,
            detail="Maximum 50 artist IDs per request",
        )

    try:
        # SpotifyPlugin.check_following_artists returns dict[str, bool] directly!
        statuses = await spotify_plugin.check_following_artists(request.artist_ids)

        return FollowingStatusResponse(statuses=statuses)
    except Exception as e:
        logger.error(f"Failed to check following status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check following status: {str(e)}",
        ) from e


# =============================================================================
# RELATED ARTISTS (Similar Artists / Fans Also Like)
# Hey future me - this fetches artists that Spotify thinks are SIMILAR to a given artist!
# Uses Spotify's recommendation engine based on listener overlap, genres, etc. Returns up
# to 20 artists. Perfect for "Fans Also Like" sections in artist detail pages. The response
# includes following status for each artist so UI can show correct button states.
# =============================================================================


class RelatedArtistResponse(BaseModel):
    """Response model for a related/similar artist."""

    spotify_id: str = Field(..., description="Spotify artist ID")
    name: str = Field(..., description="Artist name")
    image_url: str | None = Field(None, description="Artist profile image URL")
    genres: list[str] = Field(default_factory=list, description="Artist genres")
    popularity: int = Field(..., description="Spotify popularity score 0-100")
    is_following: bool = Field(..., description="Whether user follows this artist")
    is_in_library: bool = Field(
        False, description="Whether artist is in local library (LOCAL or HYBRID source)"
    )


class RelatedArtistsResponse(BaseModel):
    """Response model for related artists list."""

    artist_id: str = Field(..., description="Source artist Spotify ID")
    artist_name: str = Field(..., description="Source artist name")
    related_artists: list[RelatedArtistResponse] = Field(
        ..., description="List of similar artists"
    )
    total: int = Field(..., description="Number of related artists returned")


# Hey future me - Helper function to check which artists are in LOCAL library!
# Returns a dict of spotify_id -> bool (True if LOCAL or HYBRID source).
# This is used for "is_in_library" badges on Similar Artists / Discovery pages.
async def _check_artists_in_library(
    session: AsyncSession,
    spotify_ids: list[str],
    deezer_ids: list[str] | None = None,
) -> dict[str, bool]:
    """Check which artists are in local library (LOCAL or HYBRID source).
    
    Args:
        session: Database session
        spotify_ids: List of Spotify artist IDs to check
        deezer_ids: Optional list of Deezer artist IDs to check
        
    Returns:
        Dict mapping spotify_id/deezer_id -> True if in library
    """
    from sqlalchemy import select, or_
    from soulspot.infrastructure.persistence.models import ArtistModel
    
    result: dict[str, bool] = {}
    
    if not spotify_ids and not deezer_ids:
        return result
    
    # Build query conditions
    conditions = []
    
    # Check by spotify_uri (format: "spotify:artist:ID")
    if spotify_ids:
        spotify_uris = [f"spotify:artist:{sid}" for sid in spotify_ids]
        conditions.append(ArtistModel.spotify_uri.in_(spotify_uris))
    
    # Check by deezer_id
    if deezer_ids:
        conditions.append(ArtistModel.deezer_id.in_(deezer_ids))
    
    # Query artists with LOCAL or HYBRID source
    stmt = select(ArtistModel.spotify_uri, ArtistModel.deezer_id).where(
        or_(*conditions),
        ArtistModel.source.in_(["local", "hybrid"]),
    )
    
    db_result = await session.execute(stmt)
    rows = db_result.all()
    
    # Build result dict
    for row in rows:
        # Extract spotify_id from URI if present
        if row.spotify_uri:
            # spotify_uri is "spotify:artist:ID" → extract ID
            parts = row.spotify_uri.split(":")
            if len(parts) == 3:
                result[parts[2]] = True
        if row.deezer_id:
            result[row.deezer_id] = True
    
    return result


@router.get(
    "/spotify/{spotify_id}/related",
    response_model=RelatedArtistsResponse,
    summary="Get artists similar to a given artist",
)
async def get_related_artists(
    spotify_id: str,
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> RelatedArtistsResponse:
    """Get up to 20 artists similar to the given artist.

    Spotify's recommendation engine determines similarity based on listener overlap,
    genre tags, and other factors. Perfect for "Fans Also Like" sections.

    Also checks if user follows each related artist to display correct button states.

    Args:
        spotify_id: Spotify artist ID (e.g., "3WrFJ7ztbogyGnTHbHJFl2")
        spotify_plugin: SpotifyPlugin handles token management internally
        session: Database session

    Returns:
        List of similar artists with following status

    Raises:
        HTTPException: 404 if artist not found, 500 if Spotify API fails
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
    if not spotify_plugin.can_use(PluginCapability.GET_RELATED_ARTISTS):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with Spotify. Please connect your account first.",
        )

    try:
        # Get the source artist details first (for name in response)
        source_artist = await spotify_plugin.get_artist(spotify_id)

        # Get related artists (returns list[ArtistDTO])
        related_dtos = await spotify_plugin.get_related_artists(spotify_id)

        if not related_dtos:
            return RelatedArtistsResponse(
                artist_id=spotify_id,
                artist_name=source_artist.name,
                related_artists=[],
                total=0,
            )

        # Batch check following status for all related artists
        related_ids: list[str] = [a.spotify_id for a in related_dtos if a.spotify_id]
        following_statuses: dict[str, bool] = {}
        if related_ids:
            following_statuses = await spotify_plugin.check_following_artists(
                related_ids
            )

        # Hey future me - Batch check which related artists are in LOCAL library!
        # This shows "Already in Library" badges on Similar Artists pages.
        library_statuses: dict[str, bool] = {}
        if related_ids:
            library_statuses = await _check_artists_in_library(session, related_ids)

        # Build response with following status AND library status
        related_artists: list[RelatedArtistResponse] = []
        for artist_dto in related_dtos:
            artist_spotify_id = artist_dto.spotify_id or ""
            related_artists.append(
                RelatedArtistResponse(
                    spotify_id=artist_spotify_id,
                    name=artist_dto.name,
                    image_url=artist_dto.image.url,  # ArtistDTO.image is ImageRef
                    genres=artist_dto.genres[:3] if artist_dto.genres else [],
                    popularity=artist_dto.popularity or 0,
                    is_following=following_statuses.get(artist_spotify_id, False),
                    is_in_library=library_statuses.get(artist_spotify_id, False),
                )
            )

        return RelatedArtistsResponse(
            artist_id=spotify_id,
            artist_name=source_artist.name,
            related_artists=related_artists,
            total=len(related_artists),
        )

    except Exception as e:
        logger.error(
            f"Failed to get related artists for {spotify_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get related artists: {str(e)}",
        ) from e


# =============================================================================
# MULTI-PROVIDER RELATED ARTISTS (Similar Artists from ALL sources)
# Hey future me - this is the NEW endpoint that aggregates from Spotify AND Deezer!
# Unlike /spotify/{id}/related (Spotify-only), this endpoint:
# 1. Queries BOTH Spotify and Deezer for related artists
# 2. Works even without Spotify auth (Deezer public API is auth-free!)
# 3. Deduplicates results from multiple sources
# 4. Returns source info so UI knows where each suggestion came from
# =============================================================================


class MultiProviderRelatedArtistResponse(BaseModel):
    """Response model for a related artist from multiple providers."""

    name: str = Field(..., description="Artist name")
    spotify_id: str | None = Field(None, description="Spotify artist ID (if known)")
    deezer_id: str | None = Field(None, description="Deezer artist ID (if known)")
    image_url: str | None = Field(None, description="Artist profile image URL")
    genres: list[str] = Field(default_factory=list, description="Artist genres")
    popularity: int = Field(0, description="Popularity score (0-100)")
    source: str = Field(..., description="Source service: spotify, deezer, or merged")
    based_on: str | None = Field(None, description="Which artist this was discovered from")
    is_in_library: bool = Field(
        False, description="Whether artist is in local library (LOCAL or HYBRID source)"
    )


class MultiProviderRelatedArtistsResponse(BaseModel):
    """Response model for multi-provider related artists list."""

    artist_name: str = Field(..., description="Source artist name")
    spotify_id: str | None = Field(None, description="Source artist Spotify ID")
    deezer_id: str | None = Field(None, description="Source artist Deezer ID")
    related_artists: list[MultiProviderRelatedArtistResponse] = Field(
        default_factory=list, description="List of similar artists from all providers"
    )
    total: int = Field(0, description="Number of related artists returned")
    source_counts: dict[str, int] = Field(
        default_factory=dict, description="How many from each provider"
    )
    errors: dict[str, str] = Field(
        default_factory=dict, description="Errors from providers that failed"
    )


@router.get(
    "/related/{artist_name}",
    response_model=MultiProviderRelatedArtistsResponse,
    summary="Get similar artists from all providers (Spotify + Deezer)",
)
async def get_multi_provider_related_artists(
    artist_name: str,
    spotify_id: str | None = Query(None, description="Spotify artist ID (optional)"),
    deezer_id: str | None = Query(None, description="Deezer artist ID (optional)"),
    limit: int = Query(20, ge=1, le=50, description="Maximum artists to return"),
    session: AsyncSession = Depends(get_db_session),
) -> MultiProviderRelatedArtistsResponse:
    """Get artists similar to the given artist from ALL available providers.

    Hey future me - this is the "Works without Spotify" version of related artists!

    Features:
    - Aggregates from Spotify + Deezer
    - Works with Deezer ONLY if Spotify is not authenticated
    - Deduplicates artists that appear on multiple services
    - Returns source info for UI badges

    Strategy:
    1. If spotify_id provided AND Spotify authenticated → Query Spotify
    2. If deezer_id provided OR can search by name → Query Deezer
    3. Merge and deduplicate results
    4. Return with source metadata

    Args:
        artist_name: Artist name (used for display and Deezer search fallback)
        spotify_id: Optional Spotify artist ID
        deezer_id: Optional Deezer artist ID
        limit: Max artists to return (default 20)
        session: Database session

    Returns:
        Related artists from all available providers

    Note:
        Unlike /spotify/{id}/related, this endpoint NEVER fails if one provider
        is unavailable. It gracefully returns results from whichever providers work.
    """
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.application.services.discover_service import (
        DiscoverResult,
        DiscoverService,
    )
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

    # Initialize plugins
    app_settings = AppSettingsService(session)
    spotify_plugin = None
    deezer_plugin = None
    enabled_providers: list[str] = []

    # Check which providers are available
    # Spotify - only if authenticated
    try:
        from soulspot.api.dependencies import get_spotify_plugin_optional

        spotify_plugin = await get_spotify_plugin_optional(session)
        if (
            spotify_plugin
            and spotify_plugin.is_authenticated
            and await app_settings.is_provider_enabled("spotify")
        ):
            enabled_providers.append("spotify")
    except Exception as e:
        logger.debug(f"Spotify not available for related artists: {e}")

    # Deezer - always available (public API, no auth needed)
    try:
        if await app_settings.is_provider_enabled("deezer"):
            # Hey future me - DeezerPlugin is initialized via dependency but also works standalone!
            from soulspot.config.settings import get_settings

            settings = get_settings()
            deezer_plugin = DeezerPlugin(settings.deezer)
            enabled_providers.append("deezer")
    except Exception as e:
        logger.debug(f"Deezer not available for related artists: {e}")

    if not enabled_providers:
        raise HTTPException(
            status_code=503,
            detail="No providers available. Enable Spotify or Deezer in settings.",
        )

    # Use DiscoverService for multi-provider aggregation
    discover_service = DiscoverService(
        spotify_plugin=spotify_plugin,
        deezer_plugin=deezer_plugin,
    )

    try:
        result: DiscoverResult = await discover_service.get_related_artists(
            spotify_id=spotify_id,
            deezer_id=deezer_id,
            artist_name=artist_name,
            limit=limit,
            enabled_providers=enabled_providers,
        )

        # Hey future me - Batch check which related artists are in LOCAL library!
        # Collect all spotify_ids and deezer_ids for library lookup
        all_spotify_ids: list[str] = [a.spotify_id for a in result.artists if a.spotify_id]
        all_deezer_ids: list[str] = [a.deezer_id for a in result.artists if a.deezer_id]
        library_statuses = await _check_artists_in_library(
            session, all_spotify_ids, all_deezer_ids
        )

        # Convert to response format
        related_artists: list[MultiProviderRelatedArtistResponse] = []
        for artist in result.artists:
            # Check if in library by spotify_id OR deezer_id
            is_in_lib = (
                library_statuses.get(artist.spotify_id or "", False)
                or library_statuses.get(artist.deezer_id or "", False)
            )
            related_artists.append(
                MultiProviderRelatedArtistResponse(
                    name=artist.name,
                    spotify_id=artist.spotify_id,
                    deezer_id=artist.deezer_id,
                    image_url=artist.image_url,
                    genres=artist.genres[:3] if artist.genres else [],
                    popularity=artist.popularity,
                    source=artist.source_service,
                    based_on=artist.based_on,
                    is_in_library=is_in_lib,
                )
            )

        return MultiProviderRelatedArtistsResponse(
            artist_name=artist_name,
            spotify_id=spotify_id,
            deezer_id=deezer_id,
            related_artists=related_artists,
            total=len(related_artists),
            source_counts=result.source_counts,
            errors=result.errors,
        )

    except Exception as e:
        logger.error(
            f"Failed to get multi-provider related artists for {artist_name}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get related artists: {str(e)}",
        ) from e


async def get_spotify_plugin_optional(
    session: AsyncSession,
) -> "SpotifyPlugin | None":
    """Get Spotify plugin if available, or None.

    Hey future me - this is a helper that doesn't throw if Spotify is not configured!
    Use this when Spotify is OPTIONAL (like multi-provider endpoints).
    """
    try:
        from soulspot.api.dependencies import get_spotify_plugin

        return await get_spotify_plugin(session)
    except HTTPException:
        return None
    except Exception:
        return None


# =============================================================================
# COMPLETE DISCOGRAPHY SYNC ENDPOINT
# =============================================================================


class DiscographySyncResponse(BaseModel):
    """Response model for complete discography sync."""

    albums_total: int = Field(..., description="Total albums fetched from provider")
    albums_added: int = Field(..., description="New albums added to DB")
    albums_skipped: int = Field(..., description="Albums already in DB (skipped)")
    tracks_total: int = Field(..., description="Total tracks fetched from provider")
    tracks_added: int = Field(..., description="New tracks added to DB")
    tracks_skipped: int = Field(..., description="Tracks already in DB (skipped)")
    source: str = Field(..., description="Provider source: spotify, deezer, or none")
    message: str = Field(..., description="Status message")


# Hey future me - THIS IS THE COMPLETE DISCOGRAPHY SYNC ENDPOINT!
# Syncs ALL albums AND ALL tracks for a single artist from providers to DB.
# After this, the UI can load everything from DB without API calls!
#
# MULTI-PROVIDER (Dec 2025):
# 1. Try Spotify first (if authenticated)
# 2. Fall back to Deezer (NO AUTH NEEDED!)
#
# Flow:
# POST /artists/{artist_id}/sync-discography
#   → FollowedArtistsService.sync_artist_discography_complete()
#   → For each album: fetch tracks from provider
#   → Store in soulspot_albums + soulspot_tracks
@router.post(
    "/{artist_id}/sync-discography",
    response_model=DiscographySyncResponse,
    summary="Sync complete discography (albums + tracks) for an artist",
)
async def sync_artist_discography_complete(
    artist_id: str,
    include_tracks: bool = Query(True, description="Also sync tracks for each album"),
    session: AsyncSession = Depends(get_db_session),
    spotify_plugin: "SpotifyPlugin | None" = Depends(get_spotify_plugin_optional),
) -> DiscographySyncResponse:
    """Sync complete discography (albums AND tracks) for an artist.

    Hey future me - this syncs EVERYTHING from providers to DB!
    After this call, the artist detail page can show all albums + tracks
    without making any more API calls. Everything is in soulspot_albums
    and soulspot_tracks tables.

    Multi-provider: Tries Spotify first, falls back to Deezer (no auth needed!).

    Args:
        artist_id: Our internal artist UUID
        include_tracks: Whether to also fetch tracks for each album (default: True)
        session: Database session
        spotify_plugin: Spotify plugin (optional, from Depends)

    Returns:
        Sync statistics (albums/tracks added/skipped)
    """
    from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

    try:
        # Hey future me - spotify_plugin is now properly injected via Depends!
        # It's None if user is not authenticated with Spotify.
        # DeezerPlugin doesn't need auth for album/track lookup.
        deezer_plugin = DeezerPlugin()

        service = FollowedArtistsService(
            session=session,
            spotify_plugin=spotify_plugin,
            deezer_plugin=deezer_plugin,
        )

        stats = await service.sync_artist_discography_complete(
            artist_id=artist_id,
            include_tracks=include_tracks,
        )

        # Commit the transaction
        await session.commit()

        source_msg = {
            "spotify": "Spotify (full album + track metadata)",
            "deezer": "Deezer (fallback, no auth needed)",
            "none": "No provider data available",
        }

        return DiscographySyncResponse(
            albums_total=stats["albums_total"],
            albums_added=stats["albums_added"],
            albums_skipped=stats["albums_skipped"],
            tracks_total=stats["tracks_total"],
            tracks_added=stats["tracks_added"],
            tracks_skipped=stats["tracks_skipped"],
            source=stats["source"],
            message=(
                f"Synced discography from {source_msg.get(stats['source'], stats['source'])}. "
                f"Albums: {stats['albums_added']} added / {stats['albums_skipped']} skipped. "
                f"Tracks: {stats['tracks_added']} added / {stats['tracks_skipped']} skipped."
            ),
        )

    except Exception as e:
        await session.rollback()
        logger.error(
            f"Failed to sync complete discography for artist {artist_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync discography: {str(e)}",
        ) from e