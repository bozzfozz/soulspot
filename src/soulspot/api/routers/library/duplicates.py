"""Library duplicate detection and resolution endpoints.

Hey future me - this file handles TWO types of duplicates:

1. **File Duplicates** (/duplicates/files)
   - EXACT matches by file hash
   - Detected during library import
   - Same content = identical files on disk

2. **Track Candidates** (/duplicates/candidates)
   - SIMILAR matches by fuzzy comparison (title/artist/duration)
   - Detected by DuplicateDetectorWorker background job
   - Might be same song from different sources/releases

Both need review because automatic resolution can lose data.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session
from soulspot.application.use_cases.scan_library import GetDuplicatesUseCase

logger = logging.getLogger(__name__)

router = APIRouter(tags=["library-duplicates"])


# =============================================================================
# Response Models
# =============================================================================


class DuplicateCandidate(BaseModel):
    """A pair of tracks that might be duplicates (fuzzy match)."""

    id: str
    track_1_id: str
    track_1_title: str
    track_1_artist: str
    track_1_file_path: str | None
    track_2_id: str
    track_2_title: str
    track_2_artist: str
    track_2_file_path: str | None
    similarity_score: int  # 0-100
    match_type: str  # metadata, fingerprint
    status: str  # pending, confirmed, dismissed
    created_at: str


class DuplicateCandidatesResponse(BaseModel):
    """Response with list of duplicate candidates."""

    candidates: list[DuplicateCandidate]
    total: int
    pending_count: int
    confirmed_count: int
    dismissed_count: int


class ResolveDuplicateRequest(BaseModel):
    """Request to resolve a duplicate candidate."""

    action: str  # keep_first, keep_second, keep_both, dismiss


# =============================================================================
# FILE DUPLICATES (Hash-based, detected during import)
# =============================================================================


@router.get("/duplicates/files")
async def get_duplicate_files(
    resolved: bool | None = Query(None, description="Filter by resolved status"),
    limit: int = Query(100, ge=1, le=500, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get duplicate files (same hash = identical content).

    Hey future me - these are EXACT duplicates (identical file content).
    Detected during library import when file_hash matches.

    Different from /duplicates/candidates which finds SIMILAR tracks
    (fuzzy matching by title/artist/duration).

    Args:
        resolved: Filter by resolved status (None=all, True=resolved, False=unresolved)
        limit: Max duplicate groups to return (default 100, max 500)
        offset: Pagination offset
        session: Database session

    Returns:
        List of duplicate file groups with pagination info
    """
    use_case = GetDuplicatesUseCase(session)
    # Hey future me - GetDuplicatesUseCase doesn't support pagination yet!
    # We apply it after the query - not ideal but works for now.
    # TODO: Add pagination to GetDuplicatesUseCase for better performance.
    all_duplicates = await use_case.execute(resolved=resolved)

    # Apply pagination
    total = len(all_duplicates)
    duplicates = all_duplicates[offset:offset + limit]

    return {
        "duplicates": duplicates,
        "total_count": total,
        "returned_count": len(duplicates),
        "limit": limit,
        "offset": offset,
        "total_duplicate_files": sum(d["duplicate_count"] for d in all_duplicates),
        "total_wasted_bytes": sum(
            d["total_size_bytes"] - (d["total_size_bytes"] // d["duplicate_count"])
            for d in all_duplicates
        ),
    }


# =============================================================================
# TRACK CANDIDATES (Fuzzy match, detected by background worker)
# =============================================================================


@router.get("/duplicates/candidates")
async def list_duplicate_candidates(
    status: str | None = Query(
        None, description="Filter by status: pending, confirmed, dismissed"
    ),
    limit: int = Query(50, description="Max candidates to return"),
    offset: int = Query(0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_db_session),
) -> DuplicateCandidatesResponse:
    """List duplicate track candidates for review.

    Hey future me - these are SIMILAR tracks (fuzzy matching)!
    Created by DuplicateDetectorWorker based on title/artist/duration.

    Different from /duplicates/files which finds EXACT duplicates
    (same file hash = identical content).

    Args:
        status: Optional status filter (pending, confirmed, dismissed)
        limit: Maximum candidates to return
        offset: Pagination offset
        session: Database session

    Returns:
        List of duplicate candidates with statistics
    """
    from soulspot.application.services.duplicate_service import DuplicateService

    service = DuplicateService(session)
    result = await service.list_candidates(status, limit, offset)

    # Convert to response format
    candidates = [
        DuplicateCandidate(
            id=c["id"],
            track_1_id=c["track_1"]["id"],
            track_1_title=c["track_1"]["title"],
            track_1_artist=c["track_1"]["artist"],
            track_1_file_path=c["track_1"]["file_path"],
            track_2_id=c["track_2"]["id"],
            track_2_title=c["track_2"]["title"],
            track_2_artist=c["track_2"]["artist"],
            track_2_file_path=c["track_2"]["file_path"],
            similarity_score=c["similarity_score"],
            match_type=c["match_type"],
            status=c["status"],
            created_at=c["created_at"],
        )
        for c in result["candidates"]
    ]

    counts = result["counts"]
    return DuplicateCandidatesResponse(
        candidates=candidates,
        total=result["total"],
        pending_count=counts["pending"],
        confirmed_count=counts["confirmed"],
        dismissed_count=counts["dismissed"],
    )


@router.post("/duplicates/candidates/{candidate_id}/resolve")
async def resolve_duplicate(
    candidate_id: str,
    request: ResolveDuplicateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Resolve a duplicate candidate.

    Hey future me – Actions:
    - keep_first: Keep Track 1, delete Track 2
    - keep_second: Keep Track 2, delete Track 1
    - keep_both: Mark as "not duplicate" (both stay)
    - dismiss: Ignore this candidate (no action)

    Args:
        candidate_id: Candidate ID
        request: Resolution action
        session: Database session

    Returns:
        Resolution result with deleted track ID (if any)
    """
    from soulspot.application.services.duplicate_service import DuplicateService
    from soulspot.domain.exceptions import EntityNotFoundError, InvalidOperationError

    service = DuplicateService(session)

    try:
        result = await service.resolve_candidate(candidate_id, request.action)
        return {
            "candidate_id": candidate_id,
            "action": request.action,
            "message": f"Duplicate resolved with action: {request.action}",
            "deleted_track_id": result.get("deleted_track_id"),
        }
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InvalidOperationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/duplicates/candidates/scan")
async def trigger_duplicate_scan(
    request: Request,
) -> dict[str, Any]:
    """Trigger a manual duplicate candidates scan.

    Hey future me - this scans for SIMILAR tracks using fuzzy matching
    (title, artist, duration). Different from import-time hash detection.

    Uses the DuplicateDetectorWorker background job.

    Returns:
        Scan job information with job_id
    """
    if not hasattr(request.app.state, "duplicate_detector_worker"):
        raise HTTPException(
            status_code=503,
            detail="Duplicate detector worker not available",
        )

    worker = request.app.state.duplicate_detector_worker
    job_id = await worker.trigger_scan_now()

    return {
        "message": "Duplicate candidates scan started",
        "job_id": job_id,
    }
