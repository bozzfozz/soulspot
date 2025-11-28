# Hey future me - dieser Worker findet DUPLIKATE in deiner Musiksammlung!
#
# Problem: Du hast denselben Song 3x runtergeladen von verschiedenen Sources,
# oder leicht unterschiedliche Versionen (Remaster, Radio Edit, etc).
# Das frisst Disk-Space und macht Playlists chaotisch.
#
# Ansatz: METADATA-HASH (Phase 1)
# - Hash aus: artist_name + track_title (normalized)
# - Optional: + duration_ms (within tolerance)
# - Optional: + album_name
#
# NICHT implementiert (Phase 2): Audio-Fingerprinting
# - Chromaprint/AcoustID wäre genauer
# - Aber braucht externe Lib und ist CPU-intensiv
# - Für V1 reicht Metadata-Matching
#
# Stolperfallen:
# - "feat." vs "ft." vs "(feat. " - alles normalisieren!
# - "The Beatles" vs "Beatles, The"
# - Remaster-Suffixe: "(2023 Remaster)" usw.
# - Live-Versionen sind eigentlich KEINE Duplikate!
"""Duplicate detector worker for finding duplicate tracks in library."""

import asyncio
import contextlib
import hashlib
import logging
import re
import unicodedata
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from soulspot.application.services.app_settings_service import AppSettingsService
from soulspot.application.workers.job_queue import JobQueue, JobType

logger = logging.getLogger(__name__)


# Patterns to strip from titles for normalization
STRIP_PATTERNS = [
    r"\s*\(.*?remaster.*?\)\s*",  # (2023 Remaster), (Remastered) etc
    r"\s*\[.*?remaster.*?\]\s*",
    r"\s*-\s*remaster.*$",
    r"\s*\(.*?bonus.*?\)\s*",  # (Bonus Track)
    r"\s*\[.*?bonus.*?\]\s*",
    r"\s*\(.*?deluxe.*?\)\s*",  # (Deluxe Edition)
    r"\s*\(.*?anniversary.*?\)\s*",  # (25th Anniversary Edition)
]

# Feat patterns to normalize
FEAT_PATTERNS = [
    (r"\s*\(feat\.?\s+", " feat. "),
    (r"\s*\[feat\.?\s+", " feat. "),
    (r"\s*ft\.?\s+", " feat. "),
    (r"\s*featuring\s+", " feat. "),
]


class DuplicateDetectorWorker:
    """Background worker for detecting duplicate tracks in library.

    Uses metadata-based hashing to find potential duplicates:
    1. Normalizes artist + title (lowercase, strip special chars)
    2. Creates hash from normalized metadata
    3. Groups tracks by hash
    4. Reports groups with >1 track as duplicate candidates

    Results are stored in duplicate_candidates table for user review.
    The worker does NOT auto-delete - humans decide what's a real duplicate.
    """

    def __init__(
        self,
        job_queue: JobQueue,
        settings_service: AppSettingsService,
        session_factory: Any,  # Callable[[], AsyncSession]
    ) -> None:
        """Initialize duplicate detector worker.

        Args:
            job_queue: Job queue for creating scan jobs
            settings_service: Settings service for config
            session_factory: Async session factory for DB access
        """
        self._job_queue = job_queue
        self._settings = settings_service
        self._session_factory = session_factory

        self._running = False
        self._task: asyncio.Task[None] | None = None

        # Stats - values can be int, str, or None
        self._stats: dict[str, int | str | None] = {
            "scans_completed": 0,
            "duplicates_found": 0,
            "tracks_scanned": 0,
            "last_scan_at": None,
            "last_error": None,
        }

    async def start(self) -> None:
        """Start the duplicate detector worker."""
        if self._running:
            logger.warning("Duplicate detector worker is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Duplicate detector worker started")

    async def stop(self) -> None:
        """Stop the duplicate detector worker."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("Duplicate detector worker stopped")

    def get_status(self) -> dict[str, Any]:
        """Get worker status for monitoring/UI."""
        return {
            "name": "Duplicate Detector",
            "running": self._running,
            "status": "active" if self._running else "stopped",
            "detection_method": "metadata-hash",
            "stats": self._stats.copy(),
        }

    async def _run_loop(self) -> None:
        """Main worker loop.

        Hey future me - dieser Loop läuft selten! Default: 1x pro Woche.
        Duplicate Detection ist nicht zeitkritisch, aber CPU-intensiv
        wenn du viele Tracks hast. Deswegen nicht zu oft laufen lassen.
        """
        # Long initial delay - let other services stabilize
        await asyncio.sleep(60)

        logger.info("Duplicate detector worker entering main loop")

        while self._running:
            try:
                if await self._settings.is_duplicate_detection_enabled():
                    await self._run_scan()
                    scans = self._stats.get("scans_completed")
                    self._stats["scans_completed"] = (int(scans) if scans else 0) + 1
                    self._stats["last_scan_at"] = datetime.now(UTC).isoformat()
                else:
                    logger.debug("Duplicate detection is disabled, skipping scan")

            except Exception as e:
                logger.error(f"Error in duplicate detector loop: {e}", exc_info=True)
                self._stats["last_error"] = str(e)

            # Get interval from settings (default 168h = 1 week)
            try:
                interval_seconds = (
                    await self._settings.get_duplicate_detection_interval_seconds()
                )
            except Exception:
                interval_seconds = 168 * 3600  # 168 hours in seconds

            try:
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break

    async def _run_scan(self) -> None:
        """Execute one duplicate detection scan.

        Hey future me - das ist der Hauptalgorithmus:
        1. Lade alle Tracks aus DB
        2. Berechne Hash für jeden Track
        3. Gruppiere nach Hash
        4. Speichere Gruppen mit >1 Track als Candidates
        """
        logger.info("Starting duplicate detection scan")

        async with self._session_factory() as session:
            # Load all tracks (simplified - in production use batching)
            tracks = await self._load_tracks(session)
            self._stats["tracks_scanned"] = len(tracks)

            if not tracks:
                logger.info("No tracks to scan for duplicates")
                return

            # Group tracks by metadata hash
            hash_groups: dict[str, list[dict[str, Any]]] = {}
            for track in tracks:
                track_hash = self._compute_track_hash(track)
                if track_hash not in hash_groups:
                    hash_groups[track_hash] = []
                hash_groups[track_hash].append(track)

            # Find groups with duplicates
            duplicate_groups = {
                h: group for h, group in hash_groups.items() if len(group) > 1
            }

            logger.info(
                f"Found {len(duplicate_groups)} potential duplicate groups "
                f"from {len(tracks)} tracks"
            )

            # Store duplicate candidates
            candidates_added = 0
            for _hash_key, group in duplicate_groups.items():
                # Create pairwise candidates
                for i in range(len(group)):
                    for j in range(i + 1, len(group)):
                        track_1 = group[i]
                        track_2 = group[j]

                        # Calculate similarity score
                        score = self._calculate_similarity(track_1, track_2)

                        await self._store_candidate(
                            session,
                            track_1["id"],
                            track_2["id"],
                            score,
                            "metadata-hash",
                        )
                        candidates_added += 1

            await session.commit()
            dups = self._stats.get("duplicates_found")
            self._stats["duplicates_found"] = (int(dups) if dups else 0) + candidates_added

            logger.info(f"Stored {candidates_added} duplicate candidates")

    async def _load_tracks(self, session: Any) -> list[dict[str, Any]]:
        """Load all tracks from database.

        Args:
            session: DB session

        Returns:
            List of track dicts with id, title, artist_name, duration_ms
        """
        # Import here to avoid circular deps
        from sqlalchemy import select

        from soulspot.infrastructure.persistence.models import TrackModel

        result = await session.execute(
            select(TrackModel.id, TrackModel.title, TrackModel.artist_id, TrackModel.duration_ms)
        )
        rows = result.all()

        return [
            {
                "id": str(row.id),
                "title": row.title or "",
                # Note: artist_id instead of artist_name - for duplicate detection
                # we use artist_id as a proxy since actual name requires a join
                "artist_name": str(row.artist_id) if row.artist_id else "",
                "duration_ms": row.duration_ms or 0,
            }
            for row in rows
        ]

    def _compute_track_hash(self, track: dict[str, Any]) -> str:
        """Compute metadata hash for a track.

        Hey future me - NORMALISIERUNG ist der Schlüssel!
        Ohne sie matchst du "The Beatles" nicht mit "Beatles, The".

        Hash = MD5(normalized_artist + "|" + normalized_title)
        """
        artist = self._normalize_text(track["artist_name"])
        title = self._normalize_title(track["title"])

        # Combine and hash
        # Note: MD5 is used here only for grouping duplicates, not for security
        combined = f"{artist}|{title}"
        return hashlib.md5(  # nosec B324 - MD5 used for hash grouping, not security
            combined.encode("utf-8"), usedforsecurity=False
        ).hexdigest()

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison.

        Operations:
        - Lowercase
        - Unicode normalization (NFD -> ASCII)
        - Strip "The " prefix
        - Remove punctuation
        - Collapse whitespace
        """
        if not text:
            return ""

        # Lowercase
        text = text.lower()

        # Unicode normalization (é -> e, etc)
        text = unicodedata.normalize("NFD", text)
        text = text.encode("ascii", "ignore").decode("ascii")

        # Strip "The " prefix
        if text.startswith("the "):
            text = text[4:]

        # Remove punctuation except spaces
        text = re.sub(r"[^\w\s]", "", text)

        # Collapse whitespace
        text = " ".join(text.split())

        return text.strip()

    def _normalize_title(self, title: str) -> str:
        """Normalize track title with extra rules.

        Additional to base normalization:
        - Strip remaster/bonus/deluxe suffixes
        - Normalize feat. patterns
        """
        if not title:
            return ""

        # Apply strip patterns (remaster etc)
        for pattern in STRIP_PATTERNS:
            title = re.sub(pattern, "", title, flags=re.IGNORECASE)

        # Normalize feat patterns
        for pattern, replacement in FEAT_PATTERNS:
            title = re.sub(pattern, replacement, title, flags=re.IGNORECASE)

        # Then apply base normalization
        return self._normalize_text(title)

    def _calculate_similarity(
        self, track_1: dict[str, Any], track_2: dict[str, Any]
    ) -> float:
        """Calculate similarity score between two tracks.

        Score 0.0 - 1.0 based on:
        - Title match (normalized): 0.4
        - Artist match (normalized): 0.4
        - Duration within tolerance: 0.2

        Returns:
            Similarity score 0.0 - 1.0
        """
        score = 0.0

        # Title match (40%)
        title_1 = self._normalize_title(track_1["title"])
        title_2 = self._normalize_title(track_2["title"])
        if title_1 == title_2:
            score += 0.4

        # Artist match (40%)
        artist_1 = self._normalize_text(track_1["artist_name"])
        artist_2 = self._normalize_text(track_2["artist_name"])
        if artist_1 == artist_2:
            score += 0.4

        # Duration match with tolerance (20%)
        # Tracks within 5 seconds are considered matching
        duration_1 = track_1.get("duration_ms", 0)
        duration_2 = track_2.get("duration_ms", 0)
        if duration_1 > 0 and duration_2 > 0:
            diff_ms = abs(duration_1 - duration_2)
            if diff_ms < 5000:  # 5 seconds
                score += 0.2
            elif diff_ms < 10000:  # 10 seconds
                score += 0.1

        return score

    async def _store_candidate(
        self,
        session: Any,
        track_id_1: str,
        track_id_2: str,
        similarity_score: float,
        match_type: str,
    ) -> None:
        """Store a duplicate candidate pair in database.

        Args:
            session: DB session
            track_id_1: First track ID
            track_id_2: Second track ID
            similarity_score: Similarity score 0.0-1.0
            match_type: Detection method (metadata-hash, fingerprint, etc)
        """
        from sqlalchemy import insert

        from soulspot.infrastructure.persistence.models import DuplicateCandidateModel

        # Ensure consistent ordering (smaller ID first)
        if track_id_1 > track_id_2:
            track_id_1, track_id_2 = track_id_2, track_id_1

        # Check if this pair already exists
        from sqlalchemy import and_, select

        existing = await session.execute(
            select(DuplicateCandidateModel).where(
                and_(
                    DuplicateCandidateModel.track_id_1 == track_id_1,
                    DuplicateCandidateModel.track_id_2 == track_id_2,
                )
            )
        )
        if existing.scalar_one_or_none():
            return  # Already exists

        # Insert new candidate
        # Note: DB stores similarity as 0-100 int, we use 0.0-1.0 float
        stmt = insert(DuplicateCandidateModel).values(
            track_id_1=track_id_1,
            track_id_2=track_id_2,
            similarity_score=int(similarity_score * 100),  # Convert to 0-100
            match_type=match_type,
            status="pending",
        )
        await session.execute(stmt)

    async def trigger_scan_now(self) -> str:
        """Manually trigger a duplicate scan.

        Returns:
            Job ID of the scan job
        """
        job_id = await self._job_queue.enqueue(
            job_type=JobType.DUPLICATE_SCAN,
            payload={"trigger": "manual", "timestamp": datetime.now(UTC).isoformat()},
        )
        logger.info(f"Manual duplicate scan triggered, job_id={job_id}")

        # Run scan in background
        asyncio.create_task(self._run_scan())

        return job_id
