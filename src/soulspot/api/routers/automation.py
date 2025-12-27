"""Automation API endpoints for watchlists, discography, and quality upgrades."""

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import (
    get_db_session,
    get_spotify_plugin,
)
from soulspot.api.routers.automation_discography import router as discography_router
from soulspot.api.routers.automation_filters import router as filters_router
from soulspot.api.routers.automation_followed_artists import (
    router as followed_artists_router,
)
from soulspot.api.routers.automation_quality_upgrades import (
    router as quality_upgrades_router,
)
from soulspot.api.routers.automation_rules import router as rules_router
from soulspot.api.routers.automation_watchlists import router as watchlists_router
from soulspot.application.services.discography_service import DiscographyService
from soulspot.application.services.quality_upgrade_service import QualityUpgradeService
from soulspot.application.services.watchlist_service import WatchlistService
from soulspot.domain.value_objects import ArtistId, WatchlistId
from soulspot.infrastructure.observability.log_messages import LogMessages

if TYPE_CHECKING:
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

router = APIRouter(prefix="/automation", tags=["automation"])
logger = logging.getLogger(__name__)

# Hey future me - router split: keep old endpoints on legacy_router so we can migrate
# incrementally without duplicate route registrations.
legacy_router = router

router = APIRouter(prefix="/automation", tags=["automation"])
router.include_router(watchlists_router)
router.include_router(discography_router)
router.include_router(quality_upgrades_router)
router.include_router(filters_router)
router.include_router(rules_router)
router.include_router(followed_artists_router)


# Pydantic models for API
# Hey future me, these are REQUEST/RESPONSE schemas - Pydantic validates incoming JSON and serializes
# outgoing data. They're DTOs (Data Transfer Objects) - different from domain entities! Don't confuse
# CreateWatchlistRequest with the Watchlist domain entity. Request schemas live here, domain models live
# in domain/entities. This keeps API concerns separate from business logic. Use Field() for validation
# and OpenAPI docs - those descriptions show up in Swagger UI!


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


# Hey, super simple request - just an artist ID to check their complete discography! This hits Spotify
# API to get ALL albums/singles/compilations/etc for the artist, then compares against our library to
# find gaps. No pagination here - if artist has 100 albums, you get all 100. Might be slow for prolific
# artists (check Classical music artists with hundreds of recordings!).
class DiscographyCheckRequest(BaseModel):
    """Request to check discography."""

    artist_id: str


# Listen, this finds tracks that could be upgraded to better quality files! quality_profile is target
# quality ("high" = FLAC/320kbps, "medium" = 256kbps, etc - check QualityProfile enum for values).
# min_improvement_score filters results - only show upgrades that are X% better quality. Score is 0.0-1.0
# where 0.3 means "30% improvement". Lower scores = more aggressive upgrades (might upgrade 320 to FLAC),
# higher = only major upgrades (128kbps to anything better). limit prevents huge response sets!
class QualityUpgradeRequest(BaseModel):
    """Request to identify quality upgrade candidates."""

    quality_profile: str = "high"
    min_improvement_score: float = 0.3
    limit: int = 100


# Watchlist endpoints
# Hey future me, creating a watchlist is idempotent-ish - if you try to create the same artist twice,
# the service layer should handle it. The quality_profile defaults to "high" but users can override
# for specific use cases (e.g., "low" for rare bootlegs where quality doesn't matter). We commit
# immediately after creation - no batch operations here. If this fails, the whole transaction rolls
# back. The artist_id parsing can throw ValueError if someone sends garbage - we catch and return 400.
@legacy_router.post("/watchlist")
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
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create watchlist: {e}"
        ) from e


# Yo future me, pagination here uses limit/offset - NOT cursor-based! For small datasets this is fine,
# but if watchlists grow huge (thousands of artists), you'll want cursor pagination to avoid missing
# rows when data changes between page fetches. The active_only flag is a performance optimization -
# most UI queries only care about active watchlists, why fetch disabled ones? Defaults to showing all.
@legacy_router.get("/watchlist")
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
        raise HTTPException(
            status_code=500, detail=f"Failed to list watchlists: {e}"
        ) from e


# Listen up, this is a simple GET by ID. The WatchlistId.from_string can throw ValueError if the ID
# is malformed (not a valid UUID format), hence the catch block. We return 404 if watchlist doesn't
# exist - standard REST semantics. Don't cache this response - watchlist stats (releases found, downloads
# triggered) change frequently when background workers run!
@legacy_router.get("/watchlist/{watchlist_id}")
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
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get watchlist: {e}"
        ) from e


# Hey, this check endpoint is the MANUAL trigger for "check this artist for new releases RIGHT NOW".
# Normally background workers do this on a schedule, but users want instant gratification! SpotifyPlugin
# handles token internally. If Spotify is down or rate-limits us, this will fail. The releases list in
# response might be EMPTY even for active artists - that's normal if nothing new since last check.
# We commit after check to update last_checked_at timestamp.
@legacy_router.post("/watchlist/{watchlist_id}/check")
async def check_watchlist_releases(
    watchlist_id: str,
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Check for new releases for a watchlist.

    Args:
        watchlist_id: Watchlist ID
        spotify_plugin: SpotifyPlugin handles token management internally
        session: Database session

    Returns:
        New releases found
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
    if not spotify_plugin.can_use(PluginCapability.GET_ARTIST_ALBUMS):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with Spotify. Please connect your account first.",
        )

    try:
        wid = WatchlistId.from_string(watchlist_id)
        service = WatchlistService(session, spotify_plugin)
        watchlist = await service.get_watchlist(wid)

        if not watchlist:
            raise HTTPException(status_code=404, detail="Watchlist not found")

        # No access_token needed - SpotifyPlugin handles token internally
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
        raise HTTPException(
            status_code=500, detail=f"Failed to check for releases: {e}"
        ) from e


# Yo, DELETE is destructive and PERMANENT - there's no soft delete here! Once you delete a watchlist,
# all its history (releases found, downloads triggered counts) is GONE. We should probably add a
# "are you sure?" in the UI. The service layer might cascade-delete related records - check the model
# relationships. This commits immediately, no undo. Returns 200 even if watchlist didn't exist (idempotent).
@legacy_router.delete("/watchlist/{watchlist_id}")
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
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to delete watchlist: {e}"
        ) from e


# Discography endpoints
# Listen, this endpoint checks "do we have ALL albums for this artist?" Uses pre-synced spotify_albums
# data from background sync, NO live API call needed! Compares known albums with owned albums locally.
# Fast and doesn't require Spotify auth. The to_dict() serialization might include large lists of
# missing albums - consider pagination if this response gets huge!
@legacy_router.post("/discography/check")
async def check_discography(
    request: DiscographyCheckRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Check discography completeness for an artist.

    Uses pre-synced spotify_albums data - no live API call needed.

    Args:
        request: Discography check request
        session: Database session

    Returns:
        Discography information
    """
    try:
        artist_id = ArtistId.from_string(request.artist_id)
        service = DiscographyService(session)
        # access_token parameter kept for backward compatibility but unused
        info = await service.check_discography(artist_id, "")

        return info.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to check discography: {e}"
        ) from e


# Hey future me, this is the "collector's dream" endpoint - show me ALL missing albums across ALL
# artists! Uses pre-synced spotify_albums data from background sync - NO live API calls needed!
# The limit param is still useful for performance (checking 1000 artists = lots of DB queries).
# Default 10 is conservative. Now FAST because it uses local data, not Spotify API!
@legacy_router.get("/discography/missing")
async def get_missing_albums(
    limit: int = 10,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get missing albums for all artists.

    Uses pre-synced spotify_albums data - no live API calls needed.

    Args:
        limit: Maximum number of artists to check
        session: Database session

    Returns:
        List of artists with missing albums
    """
    try:
        service = DiscographyService(session)
        # access_token parameter kept for backward compatibility but unused
        infos = await service.get_missing_albums_for_all_artists("", limit)

        return {
            "artists_with_missing_albums": [info.to_dict() for info in infos],
            "count": len(infos),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get missing albums: {e}"
        ) from e


# Quality upgrade endpoints
# Yo, this endpoint finds tracks where you have a crappy MP3 but better quality is available on
# Soulseek. The min_improvement_score is a threshold (0.0-1.0) - lower means more aggressive upgrades
# (might upgrade 320kbps to FLAC), higher means only upgrade really bad files (128kbps to anything).
# The algorithm is in QualityUpgradeService - it scores based on bitrate, format, source quality.
# Limit=100 prevents massive result sets, but this could still return lots of data!
@legacy_router.post("/quality-upgrades/identify")
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
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to identify upgrades: {e}"
        ) from e


# Hey, this gets tracks that were IDENTIFIED for upgrade but not yet processed (downloaded/replaced).
# This is basically a work queue - the automation workers pick from here. If this list is HUGE, your
# workers are falling behind! Might indicate Soulseek network issues or rate limiting. The limit
# prevents overwhelming the response, but you might need pagination if queue grows into thousands.
@legacy_router.get("/quality-upgrades/unprocessed")
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
        ) from e


# Filter management endpoints
# Yo future me, filter schemas for the automation filtering system! Filters control what downloads are
# allowed (whitelist) or blocked (blacklist). target specifies WHAT to filter (keywords in filename, username,
# file format, bitrate). pattern is the value to match (could be regex if is_regex=true!). priority determines
# filter evaluation order - higher priority runs first. This is powerful but complex - wrong filter can block
# everything or let junk through! Test carefully in dev before deploying filter changes!


class CreateFilterRequest(BaseModel):
    """Request to create a filter rule."""

    name: str
    filter_type: str  # "whitelist" or "blacklist"
    target: str  # "keyword", "user", "format", "bitrate"
    pattern: str
    is_regex: bool = False
    priority: int = 0
    description: str | None = None


# Hey, PATCH request to update existing filter's pattern! You can't change filter type or target with PATCH
# (that would be creating a new filter), just tweak the pattern and regex flag. This is useful when your
# regex was almost right but needs tweaking. Changing is_regex from false to true (or vice versa) completely
# changes match behavior - "test" as literal only matches "test", but "test" as regex matches "testing",
# "contest", etc! Be careful with that toggle!
class UpdateFilterRequest(BaseModel):
    """Request to update a filter rule."""

    pattern: str
    is_regex: bool = False


# Hey future me, this creates filter rules via the POST /filters endpoint! The lazy imports inside the
# endpoint are kind of ugly but avoid circular import issues. FilterType and FilterTarget are enums that
# validate the strings - will raise ValueError if you send invalid values like filter_type="maybe" (only
# whitelist/blacklist allowed). The filter is enabled by default (check FilterRule entity) so it takes
# effect IMMEDIATELY after commit! priority determines evaluation order when multiple filters match. Higher
# priority = runs first. Returns full filter object with generated ID and timestamps.
@legacy_router.post("/filters")
async def create_filter(
    request: CreateFilterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Create a new filter rule.

    Args:
        request: Filter creation request
        session: Database session

    Returns:
        Created filter information
    """
    try:
        from soulspot.application.services.filter_service import FilterService
        from soulspot.domain.entities import FilterTarget, FilterType

        service = FilterService(session)
        filter_rule = await service.create_filter(
            name=request.name,
            filter_type=FilterType(request.filter_type),
            target=FilterTarget(request.target),
            pattern=request.pattern,
            is_regex=request.is_regex,
            priority=request.priority,
            description=request.description,
        )
        await session.commit()

        return {
            "id": str(filter_rule.id.value),
            "name": filter_rule.name,
            "filter_type": filter_rule.filter_type.value,
            "target": filter_rule.target.value,
            "pattern": filter_rule.pattern,
            "is_regex": filter_rule.is_regex,
            "enabled": filter_rule.enabled,
            "priority": filter_rule.priority,
            "description": filter_rule.description,
            "created_at": filter_rule.created_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create filter: {e}"
        ) from e


# Yo, filter listing supports THREE modes: all filters, by type, or enabled only. The enabled_only
# is what download workers use - they only care about active filters. The type filter (whitelist/
# blacklist) is for UI organization. NO CACHING HERE - filter changes should take effect immediately!
# If you cache this, users will be confused why their new filter isn't working.
@legacy_router.get("/filters")
async def list_filters(
    filter_type: str | None = None,
    enabled_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List filter rules.

    Args:
        filter_type: Optional filter by type (whitelist/blacklist)
        enabled_only: Only return enabled filters
        limit: Maximum number of results
        offset: Offset for pagination
        session: Database session

    Returns:
        List of filters
    """
    try:
        from soulspot.application.services.filter_service import FilterService
        from soulspot.domain.entities import FilterType

        service = FilterService(session)

        if enabled_only:
            filters = await service.list_enabled()
        elif filter_type:
            filters = await service.list_by_type(FilterType(filter_type))
        else:
            filters = await service.list_all(limit, offset)

        return {
            "filters": [
                {
                    "id": str(f.id.value),
                    "name": f.name,
                    "filter_type": f.filter_type.value,
                    "target": f.target.value,
                    "pattern": f.pattern,
                    "is_regex": f.is_regex,
                    "enabled": f.enabled,
                    "priority": f.priority,
                    "description": f.description,
                }
                for f in filters
            ],
            "count": len(filters),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list filters: {e}"
        ) from e


# Listen up, this GET fetches individual filter details! Similar to other get-by-id endpoints - standard
# REST pattern. Returns full filter config including execution stats (if that's tracked - check FilterRule
# entity for hit_count or similar fields). The lazy import pattern again for FilterService and FilterRuleId.
# 404 if filter doesn't exist. Good for "edit filter" UI where you pre-populate form with existing values.
@legacy_router.get("/filters/{filter_id}")
async def get_filter(
    filter_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get a specific filter rule.

    Args:
        filter_id: Filter ID
        session: Database session

    Returns:
        Filter information
    """
    try:
        from soulspot.application.services.filter_service import FilterService
        from soulspot.domain.value_objects import FilterRuleId

        service = FilterService(session)
        filter_rule = await service.get_filter(FilterRuleId.from_string(filter_id))

        if not filter_rule:
            raise HTTPException(status_code=404, detail="Filter not found")

        return {
            "id": str(filter_rule.id.value),
            "name": filter_rule.name,
            "filter_type": filter_rule.filter_type.value,
            "target": filter_rule.target.value,
            "pattern": filter_rule.pattern,
            "is_regex": filter_rule.is_regex,
            "enabled": filter_rule.enabled,
            "priority": filter_rule.priority,
            "description": filter_rule.description,
            "created_at": filter_rule.created_at.isoformat(),
            "updated_at": filter_rule.updated_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get filter: {e}") from e


# Hey, enable/disable are separate from delete because filters are expensive to configure! Users want
# to temporarily disable a filter without losing it. This is instant - next download will respect the
# change. If you disable a whitelist that was blocking everything, downloads will suddenly start working.
# If you disable a blacklist, junk will start getting through. Think before you click!
@legacy_router.post("/filters/{filter_id}/enable")
async def enable_filter(
    filter_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Enable a filter rule.

    Args:
        filter_id: Filter ID
        session: Database session

    Returns:
        Success message
    """
    try:
        from soulspot.application.services.filter_service import FilterService
        from soulspot.domain.value_objects import FilterRuleId

        service = FilterService(session)
        await service.enable_filter(FilterRuleId.from_string(filter_id))
        await session.commit()

        return {"message": "Filter enabled successfully"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to enable filter: {e}"
        ) from e


# Yo, this is the opposite of enable - turns filter OFF without deleting it. Same immediate effect
# as enable - next download operation will skip this filter. Useful for debugging ("is this filter
# blocking my downloads?") - just temporarily disable it and try again!
@legacy_router.post("/filters/{filter_id}/disable")
async def disable_filter(
    filter_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Disable a filter rule.

    Args:
        filter_id: Filter ID
        session: Database session

    Returns:
        Success message
    """
    try:
        from soulspot.application.services.filter_service import FilterService
        from soulspot.domain.value_objects import FilterRuleId

        service = FilterService(session)
        await service.disable_filter(FilterRuleId.from_string(filter_id))
        await session.commit()

        return {"message": "Filter disabled successfully"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to disable filter: {e}"
        ) from e


# Yo, PATCH lets you update the pattern without recreating the whole filter. This is important because
# filters accumulate hit counts and stats - if you delete and recreate, you lose that history! The
# is_regex flag can be toggled here too - careful, changing a simple string pattern to regex or vice
# versa completely changes match behavior! Test the new pattern before applying.
@legacy_router.patch("/filters/{filter_id}")
async def update_filter_pattern(
    filter_id: str,
    request: UpdateFilterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Update a filter rule's pattern.

    Args:
        filter_id: Filter ID
        request: Update request
        session: Database session

    Returns:
        Success message
    """
    try:
        from soulspot.application.services.filter_service import FilterService
        from soulspot.domain.value_objects import FilterRuleId

        service = FilterService(session)
        await service.update_filter_pattern(
            FilterRuleId.from_string(filter_id), request.pattern, request.is_regex
        )
        await session.commit()

        return {"message": "Filter pattern updated successfully"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update filter pattern: {e}"
        ) from e


# Hey, DELETE is permanent - the filter configuration is GONE, including all historical stats and hit
# counts. Unlike disable, this can't be undone. Make sure users know this is destructive! Returns 200
# even if filter doesn't exist (idempotent). Commits immediately.
@legacy_router.delete("/filters/{filter_id}")
async def delete_filter(
    filter_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Delete a filter rule.

    Args:
        filter_id: Filter ID
        session: Database session

    Returns:
        Success message
    """
    try:
        from soulspot.application.services.filter_service import FilterService
        from soulspot.domain.value_objects import FilterRuleId

        service = FilterService(session)
        await service.delete_filter(FilterRuleId.from_string(filter_id))
        await session.commit()

        return {"message": "Filter deleted successfully"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to delete filter: {e}"
        ) from e


# Automation rule management endpoints
# Hey, automation rules are the WORKFLOW system - "when X happens, do Y"! trigger is the event (new_release,
# missing_album, quality_upgrade, manual), action is what to do (search_and_download, notify_only, add_to_queue).
# This is more complex than filters - rules can chain actions, apply filters, run on schedules. priority controls
# which rule fires when multiple match. apply_filters=true means run filter rules on download candidates before
# executing. auto_process=true means rule executes automatically without human approval. These defaults (priority=0,
# quality_profile="high", apply_filters=true, auto_process=true) create fully automated rules - might want
# manual approval for some use cases!


class CreateAutomationRuleRequest(BaseModel):
    """Request to create an automation rule."""

    name: str
    trigger: str  # "new_release", "missing_album", "quality_upgrade", "manual"
    action: str  # "search_and_download", "notify_only", "add_to_queue"
    priority: int = 0
    quality_profile: str = "high"
    apply_filters: bool = True
    auto_process: bool = True
    description: str | None = None


# Yo future me, creates automation rules via POST /rules! AutomationTrigger and AutomationAction enums
# validate the string values - ValueError if invalid. The lazy imports avoid circular deps. Rules are
# enabled by default so they start firing events IMMEDIATELY after commit! This could trigger downloads
# right away if there are pending events matching the trigger. The response includes execution stats
# (total/successful/failed counts) which are 0 for new rules. Check AutomationWorkflowService for the
# actual rule execution logic - this endpoint just stores configuration.
@legacy_router.post("/rules")
async def create_automation_rule(
    request: CreateAutomationRuleRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Create a new automation rule.

    Args:
        request: Rule creation request
        session: Database session

    Returns:
        Created rule information
    """
    try:
        from soulspot.application.services.automation_workflow_service import (
            AutomationWorkflowService,
        )
        from soulspot.domain.entities import AutomationAction, AutomationTrigger

        service = AutomationWorkflowService(session)
        rule = await service.create_rule(
            name=request.name,
            trigger=AutomationTrigger(request.trigger),
            action=AutomationAction(request.action),
            priority=request.priority,
            quality_profile=request.quality_profile,
            apply_filters=request.apply_filters,
            auto_process=request.auto_process,
            description=request.description,
        )
        await session.commit()

        return {
            "id": str(rule.id.value),
            "name": rule.name,
            "trigger": rule.trigger.value,
            "action": rule.action.value,
            "enabled": rule.enabled,
            "priority": rule.priority,
            "quality_profile": rule.quality_profile,
            "apply_filters": rule.apply_filters,
            "auto_process": rule.auto_process,
            "description": rule.description,
            "created_at": rule.created_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create automation rule: {e}"
        ) from e


# Hey, rule listing is like filter listing - supports multiple query modes. The enabled_only is what
# the automation workers query to find active rules. The trigger filter helps UI show "all rules for
# new releases" etc. The execution counts (total, successful, failed) are critical for debugging why
# automation isn't working - if failed_executions is high, check logs!
@legacy_router.get("/rules")
async def list_automation_rules(
    trigger: str | None = None,
    enabled_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List automation rules.

    Args:
        trigger: Optional filter by trigger type
        enabled_only: Only return enabled rules
        limit: Maximum number of results
        offset: Offset for pagination
        session: Database session

    Returns:
        List of automation rules
    """
    try:
        from soulspot.application.services.automation_workflow_service import (
            AutomationWorkflowService,
        )
        from soulspot.domain.entities import AutomationTrigger

        service = AutomationWorkflowService(session)

        if enabled_only:
            rules = await service.list_enabled()
        elif trigger:
            rules = await service.list_by_trigger(AutomationTrigger(trigger))
        else:
            rules = await service.list_all(limit, offset)

        return {
            "rules": [
                {
                    "id": str(r.id.value),
                    "name": r.name,
                    "trigger": r.trigger.value,
                    "action": r.action.value,
                    "enabled": r.enabled,
                    "priority": r.priority,
                    "quality_profile": r.quality_profile,
                    "apply_filters": r.apply_filters,
                    "auto_process": r.auto_process,
                    "total_executions": r.total_executions,
                    "successful_executions": r.successful_executions,
                    "failed_executions": r.failed_executions,
                }
                for r in rules
            ],
            "count": len(rules),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list automation rules: {e}"
        ) from e


# Listen up, this GET returns detailed rule info including execution stats. The last_triggered_at
# tells you when this rule last fired - if it's None or ancient, maybe the rule is misconfigured or
# the trigger never happens. The success/fail counts are your debugging friend - high failures mean
# check logs for what went wrong (Spotify API down? Soulseek timeout? Bug in action logic?).
@legacy_router.get("/rules/{rule_id}")
async def get_automation_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get a specific automation rule.

    Args:
        rule_id: Rule ID
        session: Database session

    Returns:
        Rule information
    """
    try:
        from soulspot.application.services.automation_workflow_service import (
            AutomationWorkflowService,
        )
        from soulspot.domain.value_objects import AutomationRuleId

        service = AutomationWorkflowService(session)
        rule = await service.get_rule(AutomationRuleId.from_string(rule_id))

        if not rule:
            raise HTTPException(status_code=404, detail="Automation rule not found")

        return {
            "id": str(rule.id.value),
            "name": rule.name,
            "trigger": rule.trigger.value,
            "action": rule.action.value,
            "enabled": rule.enabled,
            "priority": rule.priority,
            "quality_profile": rule.quality_profile,
            "apply_filters": rule.apply_filters,
            "auto_process": rule.auto_process,
            "description": rule.description,
            "last_triggered_at": (
                rule.last_triggered_at.isoformat() if rule.last_triggered_at else None
            ),
            "total_executions": rule.total_executions,
            "successful_executions": rule.successful_executions,
            "failed_executions": rule.failed_executions,
            "created_at": rule.created_at.isoformat(),
            "updated_at": rule.updated_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get automation rule: {e}"
        ) from e


# Yo, enabling a rule means it will start executing on matching events IMMEDIATELY. If this rule has
# auto_process=true, downloads might start RIGHT NOW if there are pending events! Be ready for sudden
# activity. This is instant - no polling delay. The automation workers check enabled rules continuously.
@legacy_router.post("/rules/{rule_id}/enable")
async def enable_automation_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Enable an automation rule.

    Args:
        rule_id: Rule ID
        session: Database session

    Returns:
        Success message
    """
    try:
        from soulspot.application.services.automation_workflow_service import (
            AutomationWorkflowService,
        )
        from soulspot.domain.value_objects import AutomationRuleId

        service = AutomationWorkflowService(session)
        await service.enable_rule(AutomationRuleId.from_string(rule_id))
        await session.commit()

        return {"message": "Automation rule enabled successfully"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to enable automation rule: {e}"
        ) from e


# Hey, disabling stops rule execution immediately - any pending actions WON'T complete! If a download
# was queued by this rule and you disable it mid-flight, the download might still finish (it's already
# in the download worker queue), but NEW matches won't trigger. Use this for testing rules without
# deleting them.
@legacy_router.post("/rules/{rule_id}/disable")
async def disable_automation_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Disable an automation rule.

    Args:
        rule_id: Rule ID
        session: Database session

    Returns:
        Success message
    """
    try:
        from soulspot.application.services.automation_workflow_service import (
            AutomationWorkflowService,
        )
        from soulspot.domain.value_objects import AutomationRuleId

        service = AutomationWorkflowService(session)
        await service.disable_rule(AutomationRuleId.from_string(rule_id))
        await session.commit()

        return {"message": "Automation rule disabled successfully"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to disable automation rule: {e}"
        ) from e


# Listen, DELETE is permanent and destroys all rule history (execution counts, last triggered, etc).
# Any pending actions from this rule might still complete (they're already queued), but no NEW events
# will match. This is for when you're truly done with a rule. Consider disabling instead if you might
# want it back later!
@legacy_router.delete("/rules/{rule_id}")
async def delete_automation_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Delete an automation rule.

    Args:
        rule_id: Rule ID
        session: Database session

    Returns:
        Success message
    """
    try:
        from soulspot.application.services.automation_workflow_service import (
            AutomationWorkflowService,
        )
        from soulspot.domain.value_objects import AutomationRuleId

        service = AutomationWorkflowService(session)
        await service.delete_rule(AutomationRuleId.from_string(rule_id))
        await session.commit()

        return {"message": "Automation rule deleted successfully"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to delete automation rule: {e}"
        ) from e


# Followed Artists endpoints
# Hey future me, these endpoints handle the "sync my Spotify followed artists" feature!
# Users go to Spotify and follow artists they like. We fetch that list and let them create
# watchlists in bulk. This is MUCH easier than manually adding 50+ artists one by one!
# GOTCHA: Requires user-follow-read OAuth scope - if user authed before we added that scope,
# they need to re-authorize! The sync endpoint can take a while (pagination) so consider
# making it async with progress updates via SSE in future.


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


# Yo, this is THE main endpoint for followed artists! It hits Spotify API to fetch all artists
# the user follows, creates/updates Artist entities in our DB, and returns them. This can take
# 10-30 seconds for users with 100+ followed artists due to pagination. Each Spotify API call
# fetches max 50 artists, so 200 followed artists = 4 API calls. Progress is logged server-side
# but user doesn't see it (future: add SSE progress updates). The response can be HTML (for HTMX)
# or JSON (for API clients) - we detect HX-Request header. SpotifyPlugin handles token management
# internally - no more manual token passing!
@legacy_router.post("/followed-artists/sync")
async def sync_followed_artists(
    request: Request,
    spotify_plugin: "SpotifyPlugin" = Depends(get_spotify_plugin),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Sync followed artists from Spotify to local database.

    Fetches all artists the current user follows on Spotify, creates or updates
    Artist entities in the database, and returns the complete list with sync statistics.

    Hey future me - SpotifyPlugin handles token management internally.
    No more manual token passing needed!

    Args:
        request: FastAPI request object (to check HX-Request header)
        spotify_plugin: SpotifyPlugin handles token management internally
        session: Database session

    Returns:
        HTML partial for HTMX requests, JSON for API requests

    Raises:
        HTTPException: 401 if token invalid/expired, 500 if sync fails
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
        from soulspot.infrastructure.plugins.deezer_plugin import DeezerPlugin

        # Get templates directory
        _TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
        templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

        # Use SpotifyPlugin directly with Deezer fallback - it handles token internally!
        deezer_plugin = DeezerPlugin()  # NO AUTH NEEDED for artist albums!
        service = FollowedArtistsService(
            session, spotify_plugin, deezer_plugin=deezer_plugin
        )

        # Hey future me - using the renamed Spotify-specific method!
        artists, stats = await service._sync_spotify_followed_artists()
        await session.commit()

        # Check if this is an HTMX request
        is_htmx = request.headers.get("HX-Request") == "true"

        if is_htmx:
            # Return HTML partial for HTMX
            artists_data = [
                {
                    "id": str(artist.id.value),
                    "name": artist.name,
                    "spotify_uri": str(artist.spotify_uri)
                    if artist.spotify_uri
                    else None,
                    "image_url": artist.image.url,  # ImageRef.url for CDN/cached image URL
                    "genres": artist.genres,
                }
                for artist in artists
            ]

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
        else:
            # Return JSON for API clients
            return SyncFollowedArtistsResponse(
                total_fetched=stats["total_fetched"],
                created=stats["created"],
                updated=stats["updated"],
                errors=stats["errors"],
                artists=[
                    {
                        "id": str(artist.id.value),
                        "name": artist.name,
                        "spotify_uri": str(artist.spotify_uri)
                        if artist.spotify_uri
                        else None,
                        "image_url": artist.image.url,  # ImageRef.url for CDN/cached image URL
                        "genres": artist.genres,
                    }
                    for artist in artists
                ],
            )
    except Exception as e:
        await session.rollback()
        logger.error(
            LogMessages.sync_failed(
                sync_type="followed_artists",
                reason="Failed to sync followed artists from Spotify",
                hint="Check Spotify token validity and API connectivity",
            ).format(),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to sync followed artists: {e}"
        ) from e


# Listen up, this is the "create watchlists for all these artists at once" endpoint! After user
# syncs followed artists and sees the list, they select which ones to watch (checkboxes in UI).
# Then POST artist_ids here to bulk-create watchlists. This is WAY faster than creating watchlists
# one-by-one via POST /watchlist! All watchlists get same config (check_frequency, auto_download,
# quality_profile) - if user wants different settings per artist, they have to create individually.
# The response includes counts of successful/failed creates. Partial success is OK - if 3 out of 10
# fail, we still create the 7 that succeeded and report stats. Transaction commits all or nothing!
@legacy_router.post("/followed-artists/watchlists/bulk")
async def bulk_create_watchlists(
    request: BulkCreateWatchlistsRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Create watchlists for multiple artists at once.

    Args:
        request: Bulk watchlist creation request with artist IDs
        session: Database session

    Returns:
        Statistics about created watchlists

    Raises:
        HTTPException: 400 if artist IDs invalid, 500 if creation fails
    """
    try:
        created_count = 0
        failed_count = 0
        failed_artists: list[str] = []

        for artist_id_str in request.artist_ids:
            try:
                artist_id = ArtistId.from_string(artist_id_str)
                service = WatchlistService(session)

                # Check if watchlist already exists for this artist
                existing = await service.get_by_artist(artist_id)
                if existing:
                    logger.info(
                        f"⏭️ Watchlist Skipped (Already Exists)\n"
                        f"└─ Artist ID: {artist_id_str}"
                    )
                    continue

                await service.create_watchlist(
                    artist_id=artist_id,
                    check_frequency_hours=request.check_frequency_hours,
                    auto_download=request.auto_download,
                    quality_profile=request.quality_profile,
                )
                created_count += 1
            except Exception:
                logger.error(
                    LogMessages.sync_failed(
                        sync_type="watchlist_creation",
                        reason=f"Failed to create watchlist for artist {artist_id_str}",
                        hint="Check database connection and artist ID validity",
                    ).format(),
                    exc_info=True,
                )
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
