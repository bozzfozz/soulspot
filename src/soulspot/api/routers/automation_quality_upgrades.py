"""Automation: quality upgrade endpoints.

Mounted under `/automation` by `automation.py`.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session
from soulspot.application.services.quality_upgrade_service import QualityUpgradeService

router = APIRouter()


# Listen, this finds tracks that could be upgraded to better quality files!
class QualityUpgradeRequest(BaseModel):
    """Request to identify quality upgrade candidates."""

    quality_profile: str = "high"
    min_improvement_score: float = 0.3
    limit: int = 100


@router.post("/quality-upgrades/identify")
async def identify_quality_upgrades(
    request: QualityUpgradeRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Identify tracks that could be upgraded to better quality."""
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


@router.get("/quality-upgrades/unprocessed")
async def get_unprocessed_upgrades(
    limit: int = 100,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get unprocessed quality upgrade candidates."""
    try:
        service = QualityUpgradeService(session)
        candidates = await service.get_unprocessed_candidates(limit)
        return {"candidates": candidates, "count": len(candidates)}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get unprocessed upgrades: {e}"
        ) from e
