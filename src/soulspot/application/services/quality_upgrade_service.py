"""Quality upgrade service for identifying lower quality tracks."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.domain.entities import QualityUpgradeCandidate
from soulspot.domain.exceptions import ValidationError
from soulspot.domain.value_objects import (
    DownloadId,
    QualityProfile,
    QUALITY_PROFILES_DICT,
    TrackId,
)
from soulspot.infrastructure.persistence.models import (
    QualityUpgradeCandidateModel,
    TrackModel,
)

logger = logging.getLogger(__name__)


class QualityUpgradeService:
    """Service for identifying and managing quality upgrade opportunities."""

    # Hey future me - QUALITY_PROFILES is now imported from domain/value_objects!
    # Use QualityProfile enum for type safety, QUALITY_PROFILES_DICT for legacy dict access.
    # Single source of truth: soulspot.domain.value_objects.quality_profile
    QUALITY_PROFILES = QUALITY_PROFILES_DICT

    def __init__(self, session: AsyncSession) -> None:
        """Initialize quality upgrade service.

        Args:
            session: Database session
        """
        self._session = session

    # Hey future me: Improvement score calculation - quantifies how much better the new file would be
    # Scoring: 40% bitrate improvement + 60% format improvement
    # WHY weight format more? FLAC->MP3 is huge downgrade even if bitrates similar
    # Example: 128kbps MP3 -> 320kbps FLAC = 0.4*(320/128-1)*0.4 + (1.0-0.6)*0.6 = ~0.54 improvement
    # GOTCHA: Score maxes at 1.0 - going from 128kbps to 5000kbps doesn't give bonus points
    def calculate_improvement_score(
        self,
        current_bitrate: int,
        current_format: str,
        target_bitrate: int,
        target_format: str,
    ) -> float:
        """Calculate improvement score for a quality upgrade.

        Args:
            current_bitrate: Current bitrate in kbps
            current_format: Current audio format
            target_bitrate: Target bitrate in kbps
            target_format: Target audio format

        Returns:
            Improvement score (0.0 to 1.0)
        """
        # Bitrate improvement (40% weight)
        bitrate_ratio = (
            min(target_bitrate / current_bitrate, 2.0) if current_bitrate > 0 else 1.0
        )
        bitrate_score = (bitrate_ratio - 1.0) * 0.4

        # Format improvement (60% weight)
        format_quality = {
            "flac": 1.0,
            "alac": 1.0,
            "wav": 0.9,
            "mp3": 0.6,
            "m4a": 0.6,
            "ogg": 0.5,
        }
        current_format_quality = format_quality.get(current_format.lower(), 0.5)
        target_format_quality = format_quality.get(target_format.lower(), 0.5)
        format_score = max(target_format_quality - current_format_quality, 0.0) * 0.6

        # Total score
        total_score = min(bitrate_score + format_score, 1.0)
        return round(total_score, 3)

    # Hey future me: Quality upgrade candidate identification - finds tracks that could be upgraded
    # WHY quality profiles? Not everyone wants lossless - some people are fine with 320kbps MP3
    # Profile hierarchy: low (128kbps) < medium (192kbps) < high (320kbps) < lossless (FLAC)
    # GOTCHA: This queries ALL tracks then filters - could be slow on huge libraries (100k+ tracks)
    # Consider adding index on audio_bitrate and audio_format columns
    async def identify_upgrade_candidates(
        self,
        quality_profile: str = "high",
        min_improvement_score: float = 0.3,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Identify tracks that could be upgraded to better quality.

        Args:
            quality_profile: Target quality profile (low, medium, high, lossless)
            min_improvement_score: Minimum improvement score to consider
            limit: Maximum number of candidates to return

        Returns:
            List of upgrade candidates
        """
        if quality_profile not in self.QUALITY_PROFILES:
            raise ValidationError(f"Invalid quality profile: {quality_profile}")

        target_profile = self.QUALITY_PROFILES[quality_profile]
        target_bitrate: int = target_profile["min_bitrate"]  # type: ignore[assignment]
        target_formats: list[str] = target_profile["formats"]  # type: ignore[assignment]

        # Find tracks below target quality
        stmt = (
            select(TrackModel)
            .where(TrackModel.file_path.isnot(None))
            .where(TrackModel.is_broken == False)  # noqa: E712
            .where(
                (TrackModel.audio_bitrate < target_bitrate)
                | (TrackModel.audio_format.notin_(target_formats))
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        tracks = result.scalars().all()

        candidates = []
        for track in tracks:
            # Calculate improvement score
            current_bitrate = track.audio_bitrate or 128
            current_format = track.audio_format or "mp3"
            target_format = "flac" if quality_profile == "lossless" else "mp3"

            improvement_score = self.calculate_improvement_score(
                current_bitrate, current_format, target_bitrate, target_format
            )

            if improvement_score >= min_improvement_score:
                candidates.append(
                    {
                        "track_id": track.id,
                        "title": track.title,
                        "current_bitrate": current_bitrate,
                        "current_format": current_format,
                        "target_bitrate": target_bitrate,
                        "target_format": target_format,
                        "improvement_score": improvement_score,
                    }
                )

        logger.info(f"Found {len(candidates)} quality upgrade candidates")
        return candidates

    # Hey future me: Quality upgrade candidate creation - stores potential upgrades in DB
    # WHY store candidates? Don't want to recalculate improvement scores every time
    # generates new ID for candidate - separate from track ID (one track can have multiple candidates over time)
    # Creates both domain entity AND persistence model - standard repository pattern
    async def create_upgrade_candidate(
        self,
        track_id: TrackId,
        current_bitrate: int,
        current_format: str,
        target_bitrate: int,
        target_format: str,
    ) -> QualityUpgradeCandidate:
        """Create a quality upgrade candidate.

        Args:
            track_id: Track ID
            current_bitrate: Current bitrate
            current_format: Current format
            target_bitrate: Target bitrate
            target_format: Target format

        Returns:
            Created candidate
        """
        improvement_score = self.calculate_improvement_score(
            current_bitrate, current_format, target_bitrate, target_format
        )

        candidate = QualityUpgradeCandidate(
            id=str(TrackId.generate().value),
            track_id=track_id,
            current_bitrate=current_bitrate,
            current_format=current_format,
            target_bitrate=target_bitrate,
            target_format=target_format,
            improvement_score=improvement_score,
        )

        model = QualityUpgradeCandidateModel(
            id=candidate.id,
            track_id=str(candidate.track_id.value),
            current_bitrate=candidate.current_bitrate,
            current_format=candidate.current_format,
            target_bitrate=candidate.target_bitrate,
            target_format=candidate.target_format,
            improvement_score=candidate.improvement_score,
            detected_at=candidate.detected_at,
            processed=candidate.processed,
            download_id=str(candidate.download_id.value)
            if candidate.download_id
            else None,
            created_at=candidate.created_at,
            updated_at=candidate.updated_at,
        )
        self._session.add(model)

        logger.info(f"Created quality upgrade candidate for track {track_id}")
        return candidate

    # Listen, unprocessed candidates query - sorted by improvement score DESC
    # WHY DESC? Show best upgrades first (FLAC > 320kbps > 192kbps)
    # processed=False means we haven't downloaded the upgrade yet
    # Returns dict not entity for API responses
    async def get_unprocessed_candidates(
        self, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get unprocessed quality upgrade candidates.

        Args:
            limit: Maximum number of candidates to return

        Returns:
            List of unprocessed candidates
        """
        stmt = (
            select(QualityUpgradeCandidateModel)
            .where(QualityUpgradeCandidateModel.processed == False)  # noqa: E712
            .order_by(QualityUpgradeCandidateModel.improvement_score.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [
            {
                "id": model.id,
                "track_id": model.track_id,
                "current_bitrate": model.current_bitrate,
                "current_format": model.current_format,
                "target_bitrate": model.target_bitrate,
                "target_format": model.target_format,
                "improvement_score": model.improvement_score,
                "detected_at": model.detected_at.isoformat(),
            }
            for model in models
        ]

    # Hey, mark candidate as done - sets processed=True and optionally links download_id
    # download_id tracks which download job handled this upgrade (audit trail)
    # No validation that candidate_id exists - will silently do nothing if not found
    async def mark_candidate_processed(
        self, candidate_id: str, download_id: DownloadId | None = None
    ) -> None:
        """Mark a candidate as processed.

        Args:
            candidate_id: Candidate ID
            download_id: Optional download ID
        """
        stmt = select(QualityUpgradeCandidateModel).where(
            QualityUpgradeCandidateModel.id == candidate_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            model.processed = True
            model.download_id = str(download_id.value) if download_id else None
            logger.info(f"Marked quality upgrade candidate {candidate_id} as processed")

    # Hey future me - diese Methode wird vom QualityUpgradeWorker aufgerufen!
    # Anders als identify_upgrade_candidates() arbeitet sie mit einer EINZELNEN Track-ID.
    # Das ist nötig, weil der Worker jeden Track einzeln durchgeht.
    #
    # GOTCHA: Diese Methode nutzt die gleiche Logik wie identify_upgrade_candidates,
    # aber für einen einzelnen Track. In Zukunft könnte man das refactoren.
    async def identify_upgrade_opportunities(
        self,
        track_id: TrackId,
        quality_profile: str = "high",
        min_improvement_score: float = 0.2,
    ) -> list[QualityUpgradeCandidate]:
        """Identify upgrade opportunities for a specific track.

        Called by QualityUpgradeWorker for per-track scanning.

        Args:
            track_id: Track ID to check
            quality_profile: Target quality profile (low, medium, high, lossless)
            min_improvement_score: Minimum improvement score to consider

        Returns:
            List of upgrade candidates for this track
        """
        if quality_profile not in self.QUALITY_PROFILES:
            quality_profile = "high"

        target_profile = self.QUALITY_PROFILES[quality_profile]
        target_bitrate: int = target_profile["min_bitrate"]  # type: ignore[assignment]
        target_formats: list[str] = target_profile["formats"]  # type: ignore[assignment]

        # Get the specific track
        stmt = select(TrackModel).where(TrackModel.id == str(track_id.value))
        result = await self._session.execute(stmt)
        track = result.scalar_one_or_none()

        if not track:
            return []

        # Skip if already at target quality
        current_bitrate = track.audio_bitrate or 128
        current_format = (track.audio_format or "mp3").lower()

        # Check if upgrade would be beneficial
        if current_bitrate >= target_bitrate and current_format in target_formats:
            return []

        # Calculate improvement score
        target_format = "flac" if quality_profile == "lossless" else "mp3"
        improvement_score = self.calculate_improvement_score(
            current_bitrate, current_format, target_bitrate, target_format
        )

        if improvement_score < min_improvement_score:
            return []

        # Create candidate entity (not persisted yet)
        candidate = QualityUpgradeCandidate(
            id=str(TrackId.generate().value),
            track_id=track_id,
            current_bitrate=current_bitrate,
            current_format=current_format,
            target_bitrate=target_bitrate,
            target_format=target_format,
            improvement_score=improvement_score,
        )

        logger.debug(
            f"Found upgrade opportunity for track {track_id}: "
            f"{current_format}@{current_bitrate}kbps -> {target_format}@{target_bitrate}kbps "
            f"(score: {improvement_score})"
        )

        return [candidate]
