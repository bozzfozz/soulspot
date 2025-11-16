"""Automation API endpoints for watchlists, discography, and quality upgrades."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session, get_spotify_token_from_session
from soulspot.application.services.discography_service import DiscographyService
from soulspot.application.services.quality_upgrade_service import QualityUpgradeService
from soulspot.application.services.watchlist_service import WatchlistService
from soulspot.config import Settings, get_settings
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
    access_token: str = Depends(get_spotify_token_from_session),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Check for new releases for a watchlist.

    Args:
        watchlist_id: Watchlist ID
        access_token: Spotify access token
        session: Database session
        settings: Application settings

    Returns:
        New releases found
    """
    try:
        wid = WatchlistId.from_string(watchlist_id)
        spotify_client = SpotifyClient(settings.spotify)
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
    access_token: str = Depends(get_spotify_token_from_session),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Check discography completeness for an artist.

    Args:
        request: Discography check request
        access_token: Spotify access token
        session: Database session
        settings: Application settings

    Returns:
        Discography information
    """
    try:
        artist_id = ArtistId.from_string(request.artist_id)
        spotify_client = SpotifyClient(settings.spotify)
        service = DiscographyService(session, spotify_client)
        info = await service.check_discography(artist_id, access_token)

        return info.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check discography: {e}")


@router.get("/discography/missing")
async def get_missing_albums(
    limit: int = 10,
    access_token: str = Depends(get_spotify_token_from_session),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Get missing albums for all artists.

    Args:
        limit: Maximum number of artists to check
        access_token: Spotify access token
        session: Database session
        settings: Application settings

    Returns:
        List of artists with missing albums
    """
    try:
        spotify_client = SpotifyClient(settings.spotify)
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
        raise HTTPException(status_code=500, detail=f"Failed to identify upgrades: {e}")


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


# Filter management endpoints
class CreateFilterRequest(BaseModel):
    """Request to create a filter rule."""

    name: str
    filter_type: str  # "whitelist" or "blacklist"
    target: str  # "keyword", "user", "format", "bitrate"
    pattern: str
    is_regex: bool = False
    priority: int = 0
    description: str | None = None


class UpdateFilterRequest(BaseModel):
    """Request to update a filter rule."""

    pattern: str
    is_regex: bool = False


@router.post("/filters")
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
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create filter: {e}")


@router.get("/filters")
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
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list filters: {e}")


@router.get("/filters/{filter_id}")
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
        raise HTTPException(status_code=500, detail=f"Failed to get filter: {e}")


@router.post("/filters/{filter_id}/enable")
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
        raise HTTPException(status_code=500, detail=f"Failed to enable filter: {e}")


@router.post("/filters/{filter_id}/disable")
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
        raise HTTPException(status_code=500, detail=f"Failed to disable filter: {e}")


@router.patch("/filters/{filter_id}")
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
        )


@router.delete("/filters/{filter_id}")
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
        raise HTTPException(status_code=500, detail=f"Failed to delete filter: {e}")


# Automation rule management endpoints
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


@router.post("/rules")
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
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create automation rule: {e}"
        )


@router.get("/rules")
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
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list automation rules: {e}"
        )


@router.get("/rules/{rule_id}")
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
        )


@router.post("/rules/{rule_id}/enable")
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
        )


@router.post("/rules/{rule_id}/disable")
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
        )


@router.delete("/rules/{rule_id}")
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
        )
