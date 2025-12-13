"""Automation: followed artists endpoints.

Mounted under `/automation` by `automation.py`.

Hey future me - these endpoints are a little weird because they support HTMX partial responses.
Keep that behavior here so the main automation router stays readable.
"""

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import (
    get_db_session,
    get_spotify_plugin,
    get_spotify_token_shared,
)
from soulspot.application.services.watchlist_service import WatchlistService
from soulspot.config import Settings, get_settings
from soulspot.domain.value_objects import ArtistId
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

router = APIRouter()
logger = logging.getLogger(__name__)


class SyncFollowedArtistsResponse(BaseModel):
    """Response from syncing followed artists."""

    total_fetched: int
    created: int
    updated: int
    errors: int
    artists: list[dict[str, Any]]


class BulkCreateWatchlistsRequest(BaseModel):
    """Request to create watchlists for multiple artists."""

    artist_ids: list[str]
    check_frequency_hours: int = 24
    auto_download: bool = True
    quality_profile: str = "high"


# Yo, this is THE main endpoint for followed artists! It can return HTML (HTMX) or JSON.
@router.post("/followed-artists/sync")
async def sync_followed_artists(
    request: Request,
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Sync followed artists from Spotify to local database."""
    # Provider + Auth checks using can_use()
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.domain.ports.plugin import PluginCapability

    app_settings = AppSettingsService(session)
    if not await app_settings.is_provider_enabled("spotify"):
        raise HTTPException(
            status_code=503,
            detail="Spotify provider is disabled in settings.",
        )
    if not spotify_plugin.can_use(PluginCapability.USER_FOLLOWED_ARTISTS):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with Spotify. Please connect your account first.",
        )

    try:
        from pathlib import Path

        from fastapi.templating import Jinja2Templates

        from soulspot.application.services.followed_artists_service import (
            FollowedArtistsService,
        )

        _TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
        templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

        service = FollowedArtistsService(session, spotify_plugin)
        artists, stats = await service.sync_followed_artists()
        await session.commit()

        is_htmx = request.headers.get("HX-Request") == "true"

        artists_data = [
            {
                "id": str(artist.id.value),
                "name": artist.name,
                "spotify_uri": str(artist.spotify_uri) if artist.spotify_uri else None,
                "image_url": artist.image_url,
                "genres": artist.genres,
            }
            for artist in artists
        ]

        if is_htmx:
            return templates.TemplateResponse(
                request,
                "partials/followed_artists_list.html",
                context={
                    "artists": artists_data,
                    "total_fetched": stats["total_fetched"],
                    "created": stats["created"],
                    "updated": stats["updated"],
                    "errors": stats["errors"],
                },
                headers={"Content-Type": "text/html; charset=utf-8"},
            )

        return SyncFollowedArtistsResponse(
            total_fetched=stats["total_fetched"],
            created=stats["created"],
            updated=stats["updated"],
            errors=stats["errors"],
            artists=artists_data,
        )
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to sync followed artists: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to sync followed artists: {e}"
        ) from e


# Listen up, this is the "create watchlists for all these artists at once" endpoint!
@router.post("/followed-artists/watchlists/bulk")
async def bulk_create_watchlists(
    request: BulkCreateWatchlistsRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Create watchlists for multiple artists at once."""
    try:
        created_count = 0
        failed_count = 0
        failed_artists: list[str] = []

        for artist_id_str in request.artist_ids:
            try:
                artist_id = ArtistId.from_string(artist_id_str)
                service = WatchlistService(session)

                existing = await service.get_by_artist(artist_id)
                if existing:
                    logger.info(f"Watchlist already exists for artist {artist_id_str}")
                    continue

                await service.create_watchlist(
                    artist_id=artist_id,
                    check_frequency_hours=request.check_frequency_hours,
                    auto_download=request.auto_download,
                    quality_profile=request.quality_profile,
                )
                created_count += 1
            except Exception as e:
                logger.error(f"Failed to create watchlist for artist {artist_id_str}: {e}")
                failed_count += 1
                failed_artists.append(artist_id_str)

        await session.commit()

        return {
            "total_requested": len(request.artist_ids),
            "created": created_count,
            "failed": failed_count,
            "failed_artists": failed_artists,
        }
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to bulk create watchlists: {e}"
        ) from e


# Hey, lightweight preview endpoint - fetches first page of followed artists WITHOUT syncing to DB.
@router.get("/followed-artists/preview")
async def preview_followed_artists(
    limit: int = 50,
    access_token: str = Depends(get_spotify_token_shared),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Preview followed artists from Spotify without syncing to database."""
    try:
        spotify_client = SpotifyClient(settings.spotify)
        response = await spotify_client.get_followed_artists(
            access_token=access_token,
            limit=min(limit, 50),
        )

        return response
    except Exception as e:
        logger.error(f"Failed to preview followed artists: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to preview followed artists: {e}"
        ) from e
