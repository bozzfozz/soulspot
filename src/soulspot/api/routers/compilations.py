"""Compilation analyzer API endpoints.

Hey future me - this provides API access to the CompilationAnalyzerService!
Endpoints for:
- Analyze single album for compilation status
- Bulk analyze all albums
- Get compilation statistics
- Manual override (set/unset compilation)
- MusicBrainz verification (Phase 3)
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session, get_musicbrainz_client
from soulspot.application.services.compilation_analyzer_service import (
    AlbumAnalysisResult,
    CompilationAnalyzerService,
)
from soulspot.infrastructure.integrations.musicbrainz_client import MusicBrainzClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/library/compilations", tags=["library", "compilations"])


# =============================================================================
# Request/Response Models
# =============================================================================

class AnalyzeAlbumRequest(BaseModel):
    """Request to analyze a single album."""
    album_id: str = Field(..., description="UUID of the album to analyze")


class AnalyzeAllRequest(BaseModel):
    """Request to analyze all albums."""
    only_undetected: bool = Field(
        default=True,
        description="Only analyze albums not already marked as compilations"
    )
    min_tracks: int = Field(
        default=3,
        ge=2,
        description="Minimum track count for diversity analysis"
    )


class SetCompilationRequest(BaseModel):
    """Request to manually set compilation status."""
    album_id: str = Field(..., description="UUID of the album")
    is_compilation: bool = Field(..., description="True = mark as compilation")
    reason: str = Field(
        default="manual_override",
        description="Reason for the override (for audit trail)"
    )


class VerifyMusicBrainzRequest(BaseModel):
    """Request to verify via MusicBrainz."""
    album_id: str = Field(..., description="UUID of the album to verify")
    update_if_confirmed: bool = Field(
        default=True,
        description="Update DB if MusicBrainz gives confident answer"
    )


class AnalysisResultResponse(BaseModel):
    """Response for single album analysis."""
    album_id: str
    album_title: str
    previous_is_compilation: bool
    new_is_compilation: bool
    detection_reason: str
    confidence: float
    track_count: int
    unique_artists: int
    changed: bool
    musicbrainz_verified: bool = False
    musicbrainz_mbid: str | None = None


class BulkAnalysisResponse(BaseModel):
    """Response for bulk analysis."""
    analyzed_count: int
    changed_count: int
    results: list[dict[str, Any]]


class CompilationStatsResponse(BaseModel):
    """Response for compilation statistics."""
    total_albums: int
    compilation_albums: int
    various_artists_albums: int
    compilation_percent: float


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/analyze", response_model=AnalysisResultResponse)
async def analyze_album(
    request: AnalyzeAlbumRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Analyze a single album for compilation status.
    
    Uses Lidarr-style heuristics:
    1. Explicit compilation flags (TCMP/cpil)
    2. Album artist pattern matching (Various Artists, VA, etc.)
    3. Track artist diversity (≥75% unique or <25% dominant)
    
    Returns detection result with reason and confidence.
    """
    analyzer = CompilationAnalyzerService(session)
    result = await analyzer.analyze_album(request.album_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Album not found")
    
    return result.to_dict()


@router.post("/analyze-all", response_model=BulkAnalysisResponse)
async def analyze_all_albums(
    request: AnalyzeAllRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Analyze all albums for compilation status.
    
    Use after library scan or as periodic cleanup task.
    By default only analyzes albums not already marked as compilations.
    
    WARNING: Can be slow for large libraries. Consider running as background job.
    """
    analyzer = CompilationAnalyzerService(session)
    results = await analyzer.analyze_all_albums(
        only_undetected=request.only_undetected,
        min_tracks=request.min_tracks,
    )
    
    return {
        "analyzed_count": len(results),
        "changed_count": sum(1 for r in results if r.changed),
        "results": [r.to_dict() for r in results],
    }


@router.get("/stats", response_model=CompilationStatsResponse)
async def get_compilation_stats(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get statistics about compilations in the library.
    
    Returns counts and percentages of compilation albums.
    """
    analyzer = CompilationAnalyzerService(session)
    return await analyzer.get_compilation_stats()


@router.post("/set-status")
async def set_compilation_status(
    request: SetCompilationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Manually set compilation status for an album.
    
    Use when automatic detection is wrong and user wants to override.
    The reason is stored for audit trail.
    """
    analyzer = CompilationAnalyzerService(session)
    success = await analyzer.set_compilation_status(
        album_id=request.album_id,
        is_compilation=request.is_compilation,
        reason=request.reason,
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Album not found")
    
    return {
        "success": True,
        "album_id": request.album_id,
        "is_compilation": request.is_compilation,
        "reason": request.reason,
    }


@router.post("/verify-musicbrainz")
async def verify_with_musicbrainz(
    request: VerifyMusicBrainzRequest,
    session: AsyncSession = Depends(get_db_session),
    mb_client: MusicBrainzClient = Depends(get_musicbrainz_client),
) -> dict[str, Any]:
    """Verify compilation status via MusicBrainz API.
    
    Use for borderline cases where local heuristics are uncertain.
    MusicBrainz has authoritative data on album types.
    
    NOTE: MusicBrainz has strict rate limits (1 req/sec). Don't call this
    in rapid succession for many albums - use verify-borderline instead.
    """
    analyzer = CompilationAnalyzerService(session, musicbrainz_client=mb_client)
    result = await analyzer.verify_with_musicbrainz(
        album_id=request.album_id,
        update_if_confirmed=request.update_if_confirmed,
    )
    
    return result


@router.post("/verify-borderline")
async def verify_borderline_albums(
    limit: int = Query(default=20, ge=1, le=100, description="Max albums to verify"),
    session: AsyncSession = Depends(get_db_session),
    mb_client: MusicBrainzClient = Depends(get_musicbrainz_client),
) -> dict[str, Any]:
    """Verify borderline albums via MusicBrainz in bulk.
    
    Finds albums where local heuristics are uncertain (50-75% diversity)
    and queries MusicBrainz for authoritative answer.
    
    WARNING: This is SLOW due to MusicBrainz rate limits (1 req/sec).
    With limit=20, expect ~20 seconds minimum. Run as background task!
    """
    analyzer = CompilationAnalyzerService(session, musicbrainz_client=mb_client)
    results = await analyzer.verify_borderline_albums(limit=limit)
    
    return {
        "verified_count": sum(1 for r in results if r.get("verified")),
        "updated_count": sum(1 for r in results if r.get("updated")),
        "results": results,
    }


# =============================================================================
# Album Detail Enhancement (for UI)
# =============================================================================

@router.get("/{album_id}/detection-info")
async def get_detection_info(
    album_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get detailed compilation detection info for an album.
    
    Returns current status, detection reason, and track diversity metrics.
    Useful for UI to show WHY an album was/wasn't detected as compilation.
    """
    analyzer = CompilationAnalyzerService(session)
    result = await analyzer.analyze_album(album_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Album not found")
    
    # Return full details including explanation
    return {
        "album_id": result.album_id,
        "album_title": result.album_title,
        "is_compilation": result.new_is_compilation,
        "detection_reason": result.detection_reason,
        "confidence": result.confidence,
        "track_count": result.track_count,
        "unique_artists": result.unique_artists,
        "diversity_ratio": (
            result.unique_artists / result.track_count 
            if result.track_count > 0 else 0
        ),
        "explanation": _format_detection_explanation(result),
    }


def _format_detection_explanation(result: AlbumAnalysisResult) -> str:
    """Format human-readable explanation of detection result.
    
    Hey future me - this is what the UI shows to explain WHY an album
    was detected as compilation (or not).
    """
    reason = result.detection_reason
    confidence = result.confidence
    
    # Guard against ZeroDivisionError when track_count is 0
    diversity_percent = (
        round(result.unique_artists / result.track_count * 100)
        if result.track_count > 0 else 0
    )
    
    explanations = {
        "explicit_flag": (
            "Detected via explicit compilation flag (TCMP/cpil tag) in audio files. "
            "This is the most reliable indicator."
        ),
        "album_artist_pattern": (
            f"Album artist matches 'Various Artists' pattern. "
            f"Confidence: {confidence:.0%}"
        ),
        "track_diversity": (
            f"High track artist diversity detected: {result.unique_artists} unique artists "
            f"across {result.track_count} tracks "
            f"({diversity_percent}% diversity). "
            f"Threshold is 75%."
        ),
        "no_dominant_artist": (
            f"No single artist dominates the album. "
            f"{result.unique_artists} artists share {result.track_count} tracks evenly."
        ),
        "borderline_diversity": (
            f"Borderline diversity ({diversity_percent}%). "
            f"Local heuristics uncertain - consider MusicBrainz verification."
        ),
        "no_indicators": (
            f"No compilation indicators found. "
            f"Album has {result.unique_artists} unique artist(s) across {result.track_count} tracks."
        ),
        "mb_various_artists": (
            "Verified via MusicBrainz: Album credited to 'Various Artists' (official MBID)."
        ),
        "mb_compilation_type": (
            "Verified via MusicBrainz: Album has 'Compilation' secondary type."
        ),
        "mb_not_compilation": (
            "Verified via MusicBrainz: Album is NOT marked as compilation."
        ),
        "manual_override": (
            "Compilation status was manually set by user."
        ),
    }
    
    return explanations.get(reason, f"Detection reason: {reason}")
