"""Automation: filter rule endpoints.

Mounted under `/automation` by `automation.py`.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session

router = APIRouter()


# Yo future me, filter schemas for the automation filtering system!
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
    """Create a new filter rule."""
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


@router.get("/filters")
async def list_filters(
    filter_type: str | None = None,
    enabled_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List filter rules."""
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


@router.get("/filters/{filter_id}")
async def get_filter(
    filter_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get a specific filter rule."""
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


@router.post("/filters/{filter_id}/enable")
async def enable_filter(
    filter_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Enable a filter rule."""
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


@router.post("/filters/{filter_id}/disable")
async def disable_filter(
    filter_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Disable a filter rule."""
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


@router.patch("/filters/{filter_id}")
async def update_filter_pattern(
    filter_id: str,
    request: UpdateFilterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Update a filter rule's pattern."""
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


@router.delete("/filters/{filter_id}")
async def delete_filter(
    filter_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Delete a filter rule."""
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
