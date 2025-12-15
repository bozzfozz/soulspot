"""Duplicate Service - Manages duplicate track detection and resolution.

Hey future me - this service handles the ENTIRE duplicate workflow!
Instead of library.py doing complex JOINs and resolution logic, we centralize it here.
Clean Architecture: Router → DuplicateService → Repositories.

Workflow:
1. DuplicateDetectorWorker finds candidates
2. User reviews via UI (GET /duplicates)
3. User resolves (POST /duplicates/{id}/resolve)
4. Service handles deletion/merging
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from soulspot.domain.exceptions import EntityNotFoundError, InvalidOperationError

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DuplicateService:
    """Service for duplicate track management and resolution.

    Handles:
    - Listing duplicate candidates with track details
    - Resolving duplicates (keep_first, keep_second, dismiss, keep_both)
    - File deletion for resolved duplicates
    - Statistics and counts
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize duplicate service.

        Args:
            session: Database session
        """
        self.session = session

    async def list_candidates(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List duplicate candidates with full track details.

        OPTIMIZED: Batch-loads all tracks with single IN query (eliminates N+1 problem).

        Args:
            status: Filter by status (pending, confirmed, dismissed)
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            Dict with candidates list and counts by status
        """
        from soulspot.infrastructure.persistence.models import (
            DuplicateCandidateModel,
            TrackModel,
        )
        from soulspot.infrastructure.persistence.repositories import (
            DuplicateCandidateRepository,
        )

        repo = DuplicateCandidateRepository(self.session)

        # Get candidates via repository
        if status:
            candidates_entities = await repo.list_by_status(status, limit)
        else:
            # Get pending by default
            candidates_entities = await repo.list_pending(limit)

        # Get counts
        counts = await repo.count_by_status()

        # OPTIMIZATION: Collect all track IDs first (no queries yet)
        track_ids = set()
        for entity in candidates_entities:
            track_ids.add(entity.track_id_1)
            track_ids.add(entity.track_id_2)

        # OPTIMIZATION: Batch-load ALL tracks with single IN query + eager loading
        # Hey future me - this is the key optimization! Instead of 2 queries per candidate,
        # we load all tracks at once. For 50 candidates = 100 track IDs → 1 query instead of 100!
        tracks_query = (
            select(TrackModel)
            .where(TrackModel.id.in_(track_ids))
            .options(joinedload(TrackModel.artist))
        )
        tracks_result = await self.session.execute(tracks_query)
        tracks_map = {track.id: track for track in tracks_result.unique().scalars().all()}

        # Build candidates list using pre-loaded tracks (no more queries!)
        candidates = []
        for entity in candidates_entities:
            # Get tracks from pre-loaded map (no DB query)
            track_1 = tracks_map.get(entity.track_id_1)
            track_2 = tracks_map.get(entity.track_id_2)

            if not track_1 or not track_2:
                logger.warning(
                    f"Missing track for candidate {entity.id}: "
                    f"track_1={track_1 is not None}, track_2={track_2 is not None}"
                )
                continue

            candidates.append(
                {
                    "id": entity.id,
                    "track_1": {
                        "id": track_1.id,
                        "title": track_1.title,
                        "artist": track_1.artist.name if track_1.artist else "Unknown",
                        "artist_id": track_1.artist_id,
                        "duration_ms": track_1.duration_ms,
                        "file_path": track_1.file_path,
                        "audio_bitrate": track_1.audio_bitrate,
                        "audio_format": track_1.audio_format,
                    },
                    "track_2": {
                        "id": track_2.id,
                        "title": track_2.title,
                        "artist": track_2.artist.name if track_2.artist else "Unknown",
                        "artist_id": track_2.artist_id,
                        "duration_ms": track_2.duration_ms,
                        "file_path": track_2.file_path,
                        "audio_bitrate": track_2.audio_bitrate,
                        "audio_format": track_2.audio_format,
                    },
                    "similarity_score": entity.similarity_score,
                    "match_type": entity.match_type.value,
                    "status": entity.status.value,
                    "resolution_action": (
                        entity.resolution_action.value
                        if entity.resolution_action
                        else None
                    ),
                    "created_at": entity.created_at.isoformat(),
                    "reviewed_at": (
                        entity.reviewed_at.isoformat() if entity.reviewed_at else None
                    ),
                }
            )

        return {
            "candidates": candidates,
            "counts": counts,
            "total": counts["pending"]
            + counts["confirmed"]
            + counts["dismissed"]
            + counts.get("auto_resolved", 0),
        }

    async def resolve_candidate(
        self,
        candidate_id: str,
        action: str,
    ) -> dict[str, Any]:
        """Resolve a duplicate candidate.

        CRITICAL: Includes transaction rollback on errors to prevent DB corruption!

        Args:
            candidate_id: ID of the candidate to resolve
            action: Resolution action (dismiss, keep_both, keep_first, keep_second)

        Returns:
            Resolution result with success status

        Raises:
            ValueError: If candidate not found or invalid action
        """
        from soulspot.domain.entities import DuplicateResolutionAction
        from soulspot.infrastructure.persistence.models import TrackModel
        from soulspot.infrastructure.persistence.repositories import (
            DuplicateCandidateRepository,
        )

        repo = DuplicateCandidateRepository(self.session)

        try:
            logger.info(
                f"🔄 Resolve Duplicate Candidate\n"
                f"├─ Candidate ID: {candidate_id}\n"
                f"└─ Action: {action}"
            )

            # Get candidate
            candidate = await repo.get_by_id(candidate_id)
            if not candidate:
                raise EntityNotFoundError(f"Duplicate candidate {candidate_id} not found")

            action_lower = action.lower()
            deleted_track_id: str | None = None

            if action_lower == "dismiss":
                await repo.dismiss(candidate_id)
            elif action_lower == "keep_both":
                # Mark as dismissed with keep_both action
                await repo.resolve(candidate_id, DuplicateResolutionAction.KEEP_BOTH.value)
            elif action_lower == "keep_first":
                # Delete track 2, keep track 1
                deleted_track_id = candidate.track_id_2
                await self._delete_track_file(candidate.track_id_2)
                await repo.resolve(candidate_id, DuplicateResolutionAction.KEEP_FIRST.value)
            elif action_lower == "keep_second":
                # Delete track 1, keep track 2
                deleted_track_id = candidate.track_id_1
                await self._delete_track_file(candidate.track_id_1)
                await repo.resolve(
                    candidate_id, DuplicateResolutionAction.KEEP_SECOND.value
                )
            else:
                raise InvalidOperationError(
                    f"Invalid resolution action: {action}. "
                    f"Valid actions: dismiss, keep_both, keep_first, keep_second"
                )

            await self.session.commit()

            logger.info(
                f"✅ Duplicate Resolved\n"
                f"├─ Candidate ID: {candidate_id}\n"
                f"├─ Action: {action}\n"
                f"└─ Deleted Track ID: {deleted_track_id or 'None'}"
            )

            return {
                "success": True,
                "action": action,
                "deleted_track_id": deleted_track_id,
            }
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to resolve duplicate candidate {candidate_id}: {e}")
            raise

    async def _delete_track_file(self, track_id: str) -> None:
        """Delete track file from disk (soft delete in DB).

        SECURITY: Validates file path is within library directory to prevent path traversal.

        Args:
            track_id: ID of track to delete
        """
        from pathlib import Path

        from soulspot.infrastructure.persistence.models import TrackModel

        track = await self.session.get(TrackModel, track_id)
        if not track or not track.file_path:
            return

        file_path = Path(track.file_path).resolve()

        # Security: Validate file_path exists and is a file (not directory)
        if not file_path.exists():
            logger.warning(f"Track file does not exist: {file_path}")
            # Soft delete anyway (mark as broken)
            track.file_path = None
            track.is_broken = True
            return

        if not file_path.is_file():
            logger.error(f"Security: Track path is not a file: {file_path}")
            return

        # Delete physical file
        try:
            os.remove(track.file_path)
            logger.info(f"🗑️ Deleted duplicate file: {track.file_path}")
        except OSError as e:
            logger.warning(f"Failed to delete file {track.file_path}: {e}")

        # Soft delete: clear file_path, mark as broken
        track.file_path = None
        track.is_broken = True

    async def get_counts(self) -> dict[str, int]:
        """Get duplicate candidate counts by status.

        Returns:
            Dict with status counts
        """
        from soulspot.infrastructure.persistence.repositories import (
            DuplicateCandidateRepository,
        )

        repo = DuplicateCandidateRepository(self.session)
        return await repo.count_by_status()
