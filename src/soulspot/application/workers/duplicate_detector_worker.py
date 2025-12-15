# Hey future me - dieser Worker findet DUPLIKATE in deiner Musiksammlung!
#
# Problem: Du hast denselben Song 3x runtergeladen von verschiedenen Sources,
# oder leicht unterschiedliche Versionen (Remaster, Radio Edit, etc).
# Das frisst Disk-Space und macht Playlists chaotisch.
#
# ZWEI-STUFEN-ANSATZ (Dec 2025):
#
# STUFE 1: SHA256 FILE-HASH Berechnung
# - Läuft NICHT beim Library-Scan (zu langsam, ~55% der Scan-Zeit!)
# - Stattdessen hier im Nightly Job
# - Berechnet nur für Tracks ohne file_hash (inkrementell)
# - ThreadPool für CPU-intensive I/O
#
# STUFE 2: METADATA-HASH für Duplicate Detection
# - Hash aus: artist_name + track_title (normalized)
# - Optional: + duration_ms (within tolerance)
# - Optional: + album_name
#
# NICHT implementiert (Phase 3): Audio-Fingerprinting
# - Chromaprint/AcoustID wäre genauer
# - Aber braucht externe Lib und ist CPU-intensiv
# - Für V1 reicht Metadata + FileHash
#
# Stolperfallen:
# - "feat." vs "ft." vs "(feat. " - alles normalisieren!
# - "The Beatles" vs "Beatles, The"
# - Remaster-Suffixe: "(2023 Remaster)" usw.
# - Live-Versionen sind eigentlich KEINE Duplikate!
"""Duplicate detector worker for finding duplicate tracks in library.

This worker performs TWO functions:
1. Computes SHA256 file hashes for tracks without them (nightly, incremental)
2. Detects duplicates using both metadata matching and file hash matching

The hash computation is separated from library scan for performance!
Library scan stays fast (~1s/file), hashing runs in nightly batch.
"""

import asyncio
import contextlib
import hashlib
import logging
import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
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

    This worker performs TWO functions (Dec 2025 update):

    1. SHA256 FILE HASH COMPUTATION (runs first):
       - Finds tracks without file_hash (empty or NULL)
       - Computes SHA256 in ThreadPool (non-blocking)
       - Updates tracks with computed hashes
       - Incremental: only processes tracks without hashes

    2. DUPLICATE DETECTION (runs after hashing):
       - Metadata-based: normalizes artist + title, groups by hash
       - File-based: groups tracks with identical file_hash
       - Creates duplicate candidates for user review

    The hash computation is separated from library scan for performance!
    Library scan stays fast (~1s/file), hashing runs in nightly batch.

    Results are stored in duplicate_candidates table for user review.
    The worker does NOT auto-delete - humans decide what's a real duplicate.

    UPDATE (Nov 2025): Now uses session_scope context manager instead of session_factory
    to fix "GC cleaning up non-checked-in connection" errors.
    """

    def __init__(
        self,
        job_queue: JobQueue,
        settings_service: AppSettingsService,
        session_scope: Any | None = None,
        # DEPRECATED: session_factory kept for backwards compatibility
        session_factory: Any | None = None,
    ) -> None:
        """Initialize duplicate detector worker.

        Args:
            job_queue: Job queue for creating scan jobs
            settings_service: Settings service for config
            session_scope: Async context manager factory for DB sessions (preferred)
            session_factory: DEPRECATED - Falls back to session_scope behavior if provided

        Raises:
            ValueError: If neither session_scope nor session_factory is provided
        """
        self._job_queue = job_queue
        self._settings = settings_service

        # Backwards compatibility: if only session_factory provided, use it as session_scope
        # Hey future me - session_factory was already a context manager in _run_scan!
        if session_scope is not None:
            self._session_scope = session_scope
        elif session_factory is not None:
            # Use session_factory as fallback (it was already used as context manager)
            self._session_scope = session_factory
        else:
            raise ValueError("Either session_scope or session_factory must be provided")

        self._running = False
        self._task: asyncio.Task[None] | None = None

        # ThreadPool for CPU-intensive SHA256 hash computation
        # Hey future me - this is the KEY performance optimization! SHA256 reads entire files,
        # which blocks I/O. Running in ThreadPool keeps the event loop responsive.
        self._executor = ThreadPoolExecutor(
            max_workers=min(4, max(2, os.cpu_count() or 2))
        )

        # Stats - values can be int, str, or None
        self._stats: dict[str, int | str | None] = {
            "scans_completed": 0,
            "duplicates_found": 0,
            "tracks_scanned": 0,
            "hashes_computed": 0,  # NEW: tracks with newly computed SHA256 hashes
            "hash_errors": 0,  # NEW: files that couldn't be hashed (missing, permission)
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
        from soulspot.infrastructure.observability.log_messages import LogMessages
        logger.info(
            LogMessages.worker_started(
                worker="Duplicate Detector",
                config={"weekly_scan": True, "disabled_by_default": True}
            )
        )

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
            "detection_method": "metadata-hash + file-hash",
            "stats": self._stats.copy(),
        }

    async def _run_loop(self) -> None:
        """Main worker loop.

        Hey future me - dieser Loop läuft selten! Default: 1x pro Woche.
        Duplicate Detection ist nicht zeitkritisch, aber CPU-intensiv
        wenn du viele Tracks hast. Deswegen nicht zu oft laufen lassen.

        UPDATE (Dec 2025): Now also computes SHA256 hashes for tracks that
        don't have them yet! This was moved OUT of library scan for performance.
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

        Hey future me - das ist der Hauptalgorithmus (Dec 2025 update):
        1. PHASE 1: Compute SHA256 hashes for tracks without them
        2. PHASE 2: Load all tracks for duplicate detection
        3. PHASE 3: Group by metadata hash (artist+title)
        4. PHASE 4: Group by file hash (exact duplicates)
        5. PHASE 5: Store candidates for user review
        """
        logger.info("Starting duplicate detection scan (with hash computation)")

        # Hey future me - using session_scope context manager ensures proper connection cleanup!
        async with self._session_scope() as session:
            # PHASE 1: Compute SHA256 hashes for tracks without them
            # This is the expensive I/O operation - runs in ThreadPool
            hashes_computed, hash_errors = await self._compute_missing_file_hashes(
                session
            )
            self._stats["hashes_computed"] = hashes_computed
            self._stats["hash_errors"] = hash_errors
            logger.info(
                f"Phase 1 complete: computed {hashes_computed} hashes, "
                f"{hash_errors} errors"
            )

            # PHASE 2: Load all tracks for duplicate detection
            tracks = await self._load_tracks(session)
            self._stats["tracks_scanned"] = len(tracks)

            if not tracks:
                logger.info("No tracks to scan for duplicates")
                return

            # PHASE 3: Group tracks by metadata hash (artist+title normalized)
            metadata_groups: dict[str, list[dict[str, Any]]] = {}
            for track in tracks:
                track_hash = self._compute_track_hash(track)
                if track_hash not in metadata_groups:
                    metadata_groups[track_hash] = []
                metadata_groups[track_hash].append(track)

            # Find groups with duplicates (metadata-based)
            metadata_duplicate_groups = {
                h: group for h, group in metadata_groups.items() if len(group) > 1
            }

            logger.info(
                f"Phase 3: Found {len(metadata_duplicate_groups)} metadata-based "
                f"duplicate groups from {len(tracks)} tracks"
            )

            # PHASE 4: Group by file hash (exact file duplicates)
            # Only for tracks that have file_hash computed
            file_hash_groups: dict[str, list[dict[str, Any]]] = {}
            for track in tracks:
                file_hash = track.get("file_hash")
                if file_hash:  # Only tracks with computed hash
                    if file_hash not in file_hash_groups:
                        file_hash_groups[file_hash] = []
                    file_hash_groups[file_hash].append(track)

            # Find exact file duplicates
            file_duplicate_groups = {
                h: group for h, group in file_hash_groups.items() if len(group) > 1
            }

            logger.info(
                f"Phase 4: Found {len(file_duplicate_groups)} exact file duplicate groups"
            )

            # PHASE 5: Store duplicate candidates
            candidates_added = 0

            # Store metadata-based duplicates
            for _hash_key, group in metadata_duplicate_groups.items():
                for i in range(len(group)):
                    for j in range(i + 1, len(group)):
                        track_1 = group[i]
                        track_2 = group[j]
                        score = self._calculate_similarity(track_1, track_2)
                        await self._store_candidate(
                            session,
                            track_1["id"],
                            track_2["id"],
                            score,
                            "metadata-hash",
                        )
                        candidates_added += 1

            # Store file-hash based duplicates (exact matches = 100% similarity)
            for _hash_key, group in file_duplicate_groups.items():
                for i in range(len(group)):
                    for j in range(i + 1, len(group)):
                        track_1 = group[i]
                        track_2 = group[j]
                        await self._store_candidate(
                            session,
                            track_1["id"],
                            track_2["id"],
                            1.0,  # Exact file match = 100% similarity
                            "file-hash",
                        )
                        candidates_added += 1

            await session.commit()
            dups = self._stats.get("duplicates_found")
            self._stats["duplicates_found"] = (
                int(dups) if dups else 0
            ) + candidates_added

            logger.info(f"Phase 5: Stored {candidates_added} duplicate candidates")

    async def _load_tracks(self, session: Any) -> list[dict[str, Any]]:
        """Load all tracks from database for duplicate detection.

        Args:
            session: DB session

        Returns:
            List of track dicts with id, title, artist_name, duration_ms, file_hash
        """
        # Import here to avoid circular deps
        from sqlalchemy import select

        from soulspot.infrastructure.persistence.models import TrackModel

        result = await session.execute(
            select(
                TrackModel.id,
                TrackModel.title,
                TrackModel.artist_id,
                TrackModel.duration_ms,
                TrackModel.file_hash,  # NEW: for file-based duplicate detection
            )
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
                "file_hash": row.file_hash or "",  # NEW: for file-based duplicates
            }
            for row in rows
        ]

    async def _compute_missing_file_hashes(self, session: Any) -> tuple[int, int]:
        """Compute SHA256 hashes for tracks that don't have them.

        Hey future me - this is the KEY performance optimization from Dec 2025!
        SHA256 hashing was removed from library scan (took ~55% of scan time).
        Instead, we compute hashes here in the nightly job, incrementally.

        Process:
        1. Query tracks WHERE file_hash IS NULL AND file_path IS NOT NULL
        2. Compute SHA256 in ThreadPool (non-blocking I/O)
        3. Batch update tracks with computed hashes
        4. Return (hashes_computed, errors_count)

        Args:
            session: DB session

        Returns:
            Tuple of (hashes_computed, errors_count)
        """
        from sqlalchemy import or_, select, update

        from soulspot.infrastructure.persistence.models import TrackModel

        # Find tracks without file_hash but with valid file_path
        result = await session.execute(
            select(TrackModel.id, TrackModel.file_path).where(
                or_(
                    TrackModel.file_hash.is_(None),
                    TrackModel.file_hash == "",
                ),
                TrackModel.file_path.isnot(None),
                TrackModel.file_path != "",
            )
        )
        tracks_to_hash = result.all()

        if not tracks_to_hash:
            logger.info("No tracks need hash computation")
            return 0, 0

        logger.info(f"Computing SHA256 hashes for {len(tracks_to_hash)} tracks")

        hashes_computed = 0
        errors = 0
        batch_size = 100  # Commit every N tracks to avoid huge transactions

        loop = asyncio.get_running_loop()

        for i, (track_id, file_path) in enumerate(tracks_to_hash):
            try:
                # Compute hash in ThreadPool (non-blocking)
                file_hash = await loop.run_in_executor(
                    self._executor, self._compute_sha256_sync, file_path
                )

                if file_hash:
                    # Update track with computed hash
                    await session.execute(
                        update(TrackModel)
                        .where(TrackModel.id == track_id)
                        .values(file_hash=file_hash, file_hash_algorithm="sha256")
                    )
                    hashes_computed += 1
                else:
                    errors += 1

            except Exception as e:
                logger.warning(f"Error computing hash for track {track_id}: {e}")
                errors += 1

            # Batch commit for memory efficiency
            if (i + 1) % batch_size == 0:
                await session.commit()
                logger.info(
                    f"Hash progress: {i + 1}/{len(tracks_to_hash)} "
                    f"(computed: {hashes_computed}, errors: {errors})"
                )

        # Final commit
        await session.commit()

        return hashes_computed, errors

    def _compute_sha256_sync(
        self, file_path: str, chunk_size: int = 8192
    ) -> str | None:
        """Compute SHA256 hash of a file (sync, for ThreadPool).

        Hey future me - this runs in ThreadPool! It's the same SHA256 computation
        that was removed from library scanner. Full file read is expensive (~55%
        of old scan time), but running in parallel threads keeps things responsive.

        Args:
            file_path: Path to the audio file
            chunk_size: Read chunk size (default 8KB)

        Returns:
            SHA256 hex digest, or None if file is inaccessible
        """
        try:
            path = Path(file_path)
            if not path.exists():
                logger.debug(f"File not found for hashing: {file_path}")
                return None

            sha256 = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()

        except PermissionError:
            logger.warning(f"Permission denied for hashing: {file_path}")
            return None
        except Exception as e:
            logger.warning(f"Error computing SHA256 for {file_path}: {e}")
            return None

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
        # Hey future me - NOW we use DuplicateCandidateRepository! Clean Architecture.
        from uuid import uuid4

        from soulspot.domain.entities import (
            DuplicateCandidate,
            DuplicateCandidateStatus,
            DuplicateMatchType,
        )
        from soulspot.infrastructure.persistence.repositories import (
            DuplicateCandidateRepository,
        )

        repo = DuplicateCandidateRepository(session)

        # Ensure consistent ordering (smaller ID first)
        if track_id_1 > track_id_2:
            track_id_1, track_id_2 = track_id_2, track_id_1

        # Check if this pair already exists
        if await repo.exists(track_id_1, track_id_2):
            return  # Already exists

        # Create candidate entity
        # Note: similarity_score is 0.0-1.0, but entity expects 0-100 int
        candidate = DuplicateCandidate(
            id=str(uuid4()),
            track_id_1=track_id_1,
            track_id_2=track_id_2,
            similarity_score=int(similarity_score * 100),  # Convert to 0-100
            match_type=DuplicateMatchType(match_type),
            status=DuplicateCandidateStatus.PENDING,
        )
        await repo.add(candidate)

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
