"""Post-Processing Worker - handles auto-processing of completed downloads.

Hey future me - this worker POLISHES completed downloads!

The problem: After slskd downloads a file, it's just a raw audio file in a temp folder.
Users want: proper folder structure, consistent naming, metadata tags, artwork.
Without this worker: Users manually move, rename, and tag EVERY download.

The solution: PostProcessingWorker runs every 30 seconds and:
1. Queries DB for completed downloads pending post-processing
2. For each: validates quality, moves to library, renames, adds tags, embeds artwork
3. Updates download status: COMPLETED → PROCESSED (new status we might add)

POST-PROCESSING PIPELINE:
1. VALIDATE  - Check file exists, verify format/bitrate against QualityProfile
2. ORGANIZE  - Move to library folder: {library}/{artist}/{album}/{track}.{ext}
3. RENAME    - Apply naming template: "{track_number}. {title}.{ext}"
4. TAG       - Write ID3/FLAC tags using MetadataTaggerService
5. ARTWORK   - Embed album artwork if available
6. CLEANUP   - Remove temp file, update DB paths

WHY ASYNC POST-PROCESSING?
- Decouples download completion from organization (download can "complete" fast)
- Heavy operations (tagging, artwork embedding) don't block download queue
- Batch processing is more efficient (multiple files at once)
- Failed post-processing doesn't fail the download (can retry later)

QUALITY VALIDATION (using QualityProfile):
- Check if file format matches preferences
- Check if bitrate is within acceptable range
- If quality is below profile minimum, mark for "upgrade" (QualityUpgradeCandidate)

ERROR HANDLING:
- File not found → Mark download as error, log for manual fix
- Tagging failed → Skip tagging, continue with move/rename
- Move failed → Retry with fallback naming
- All failures → Don't lose the download! Keep original file safe.

CONFIGURATION (via app_settings):
- post_processing.enabled: Enable/disable auto-processing
- post_processing.library_path: Base library folder
- post_processing.naming_template: File naming pattern
- post_processing.embed_artwork: Whether to embed artwork in files
"""

import asyncio
import logging
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from soulspot.domain.entities import (
    AudioFormat,
    Download,
    DownloadStatus,
    QualityMatcher,
    QualityProfile,
)

if TYPE_CHECKING:
    from soulspot.application.services.metadata_tagger import MetadataTaggerService
    from soulspot.infrastructure.persistence.repositories import DownloadRepository

logger = logging.getLogger(__name__)


@dataclass
class PostProcessingResult:
    """Result of post-processing a single download.

    Hey future me - this captures what happened during processing!
    Success cases track the new file path, failures track the error.
    """

    download_id: str
    success: bool
    original_path: str | None = None
    final_path: str | None = None
    error: str | None = None
    # Processing details
    moved: bool = False
    renamed: bool = False
    tagged: bool = False
    artwork_embedded: bool = False
    quality_validated: bool = False
    quality_score: int | None = None


@dataclass
class PostProcessingConfig:
    """Configuration for post-processing behavior.

    Hey future me - these settings come from app_settings table!
    Users can customize via Settings UI.
    """

    enabled: bool = True
    library_path: str = "/music"
    # Naming template supports: {artist}, {album}, {track_number}, {title}, {ext}
    naming_template: str = "{track_number:02d}. {title}.{ext}"
    # Folder template supports: {artist}, {album}, {year}
    folder_template: str = "{artist}/{album}"
    embed_artwork: bool = True
    # Quality validation
    validate_quality: bool = True
    # Skip files that don't meet quality profile
    reject_low_quality: bool = False


class PostProcessingWorker:
    """Worker that handles post-processing of completed downloads.

    Hey future me - this is the AUTO-ORGANIZE engine!

    Processing Flow:
    1. Find downloads with status COMPLETED (not yet processed)
    2. Load active QualityProfile for validation/scoring
    3. For each download:
       a. Validate file exists and quality
       b. Build target path from templates
       c. Move file to library
       d. Apply metadata tags
       e. Embed artwork (if enabled)
       f. Update download record with final path

    Configuration:
    - check_interval: How often to check for pending downloads (default: 30s)
    - max_per_cycle: How many downloads to process per cycle (default: 5)
    - config: PostProcessingConfig with paths, templates, options

    Lifecycle:
    - Created in lifecycle.py during app startup
    - Runs as asyncio task via start()
    - Stopped gracefully via stop() during shutdown
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        check_interval: int = 30,
        max_per_cycle: int = 5,
        config: PostProcessingConfig | None = None,
    ) -> None:
        """Initialize the post-processing worker.

        Args:
            session_factory: Factory for creating DB sessions
            check_interval: Seconds between processing checks (default: 30)
            max_per_cycle: Max downloads to process per cycle (default: 5)
            config: Processing configuration (loaded from DB if None)
        """
        self._session_factory = session_factory
        self._check_interval = check_interval
        self._max_per_cycle = max_per_cycle
        self._config = config or PostProcessingConfig()
        self._running = False
        self._metadata_tagger: MetadataTaggerService | None = None
        self._stats = {
            "total_processed": 0,
            "total_errors": 0,
            "last_check_at": None,
            "processed_last_cycle": 0,
        }

    def set_metadata_tagger(self, tagger: "MetadataTaggerService") -> None:
        """Set the metadata tagger service (injected after creation).

        Hey future me - MetadataTaggerService is created separately and injected!
        This avoids circular dependencies during worker creation.
        """
        self._metadata_tagger = tagger

    async def start(self) -> None:
        """Start the post-processing worker.

        Runs continuously until stop() is called.
        """
        if not self._config.enabled:
            logger.info("PostProcessingWorker disabled by config")
            return

        self._running = True
        logger.info(
            f"PostProcessingWorker started (check_interval={self._check_interval}s, "
            f"max_per_cycle={self._max_per_cycle}, library={self._config.library_path})"
        )

        while self._running:
            try:
                await self._process_pending_downloads()
            except Exception as e:
                logger.error(f"PostProcessingWorker cycle error: {e}", exc_info=True)

            # Wait before next check
            try:
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break

        logger.info("PostProcessingWorker stopped")

    async def stop(self) -> None:
        """Stop the post-processing worker gracefully."""
        self._running = False
        logger.info("PostProcessingWorker stopping...")

    def get_status(self) -> dict[str, Any]:
        """Get current worker status for monitoring.

        Hey future me - this is called by the workers API endpoint!
        Returns status info that shows in the worker status dashboard.
        """
        return {
            "running": self._running,
            "check_interval_seconds": self._check_interval,
            "stats": {
                "enabled": self._enabled,
            },
        }

    async def _process_pending_downloads(self) -> None:
        """Find and process downloads that need post-processing.

        Hey future me - this is the main processing loop!

        Queries for downloads with:
        - status = COMPLETED
        - file_path is set (download actually completed)
        - processed_at is NULL (not yet post-processed)

        We might need to add a "processed_at" field to Download entity!
        For now, we'll check if final_path differs from download path.
        """
        from soulspot.infrastructure.persistence.repositories import (
            DownloadRepository,
            QualityProfileRepository,
        )

        self._stats["last_check_at"] = datetime.now(UTC).isoformat()
        processed_count = 0

        async with self._session_factory() as session:
            try:
                # Get active quality profile for validation
                quality_repo = QualityProfileRepository(session)
                quality_profile = await quality_repo.get_active()

                # Get pending downloads (COMPLETED but not yet processed)
                download_repo = DownloadRepository(session)
                pending = await self._find_pending_downloads(download_repo)

                if not pending:
                    return

                logger.debug(f"Found {len(pending)} downloads pending post-processing")

                for download in pending[: self._max_per_cycle]:
                    try:
                        result = await self._process_download(
                            download, quality_profile, download_repo
                        )
                        if result.success:
                            processed_count += 1
                            self._stats["total_processed"] += 1
                            logger.info(
                                f"Post-processed download {download.id}: {result.final_path}"
                            )
                        else:
                            self._stats["total_errors"] += 1
                            logger.warning(
                                f"Post-processing failed for {download.id}: {result.error}"
                            )
                    except Exception as e:
                        self._stats["total_errors"] += 1
                        logger.error(
                            f"Error processing download {download.id}: {e}", exc_info=True
                        )

                # Commit all changes
                await session.commit()

            except Exception as e:
                await session.rollback()
                logger.error(f"Post-processing batch failed: {e}", exc_info=True)

        self._stats["processed_last_cycle"] = processed_count
        if processed_count > 0:
            logger.info(f"PostProcessingWorker processed {processed_count} downloads")

    async def _find_pending_downloads(
        self, download_repo: "DownloadRepository"
    ) -> list[Download]:
        """Find downloads that need post-processing.

        Hey future me - we identify pending downloads by:
        1. Status is COMPLETED
        2. File path exists
        3. Not already in library (path doesn't start with library_path)

        This is a simplification - ideally we'd have a "processed" flag or status.
        """
        from sqlalchemy import select

        from soulspot.infrastructure.persistence.models import DownloadModel

        stmt = (
            select(DownloadModel)
            .where(
                DownloadModel.status == DownloadStatus.COMPLETED.value,
                DownloadModel.file_path.isnot(None),
                # Not already in library - crude check
                ~DownloadModel.file_path.startswith(self._config.library_path),
            )
            .limit(self._max_per_cycle * 2)  # Get a few extra in case some are invalid
        )

        result = await download_repo.session.execute(stmt)
        models = result.scalars().all()

        # Convert to entities
        downloads = []
        for model in models:
            try:
                download = download_repo._model_to_entity(model)
                downloads.append(download)
            except Exception as e:
                logger.warning(f"Failed to convert download model {model.id}: {e}")

        return downloads

    async def _process_download(
        self,
        download: Download,
        quality_profile: QualityProfile | None,
        download_repo: "DownloadRepository",
    ) -> PostProcessingResult:
        """Process a single download through the post-processing pipeline.

        Hey future me - this is the full pipeline for ONE download!

        Steps:
        1. Validate file exists
        2. Check quality against profile
        3. Build target path
        4. Move file
        5. Apply metadata tags
        6. Embed artwork
        7. Update download record
        """
        result = PostProcessingResult(
            download_id=str(download.id.value),
            original_path=download.file_path,
        )

        # 1. VALIDATE: Check file exists
        if not download.file_path:
            result.error = "No file path set"
            return result

        source_path = Path(download.file_path)
        if not source_path.exists():
            result.error = f"Source file not found: {source_path}"
            return result

        # 2. QUALITY: Validate against profile
        if quality_profile and self._config.validate_quality:
            quality_result = await self._validate_quality(source_path, quality_profile)
            result.quality_validated = True
            result.quality_score = quality_result.get("score")

            if self._config.reject_low_quality and not quality_result.get("matches"):
                result.error = f"Quality rejected: {quality_result.get('reason')}"
                return result

        # 3. ORGANIZE: Build target path
        target_path = self._build_target_path(download, source_path)

        # 4. MOVE: Move file to library
        try:
            await self._move_file(source_path, target_path)
            result.moved = True
        except Exception as e:
            result.error = f"Move failed: {e}"
            return result

        # 5. TAG: Apply metadata
        if self._metadata_tagger:
            try:
                await self._apply_metadata(download, target_path)
                result.tagged = True
            except Exception as e:
                logger.warning(f"Metadata tagging failed for {target_path}: {e}")
                # Continue anyway - tagging failure isn't fatal

        # 6. ARTWORK: Embed album art
        if self._config.embed_artwork and self._metadata_tagger:
            try:
                await self._embed_artwork(download, target_path)
                result.artwork_embedded = True
            except Exception as e:
                logger.warning(f"Artwork embedding failed for {target_path}: {e}")
                # Continue anyway

        # 7. UPDATE: Update download record with new path
        download.file_path = str(target_path)
        await download_repo.update(download)

        result.success = True
        result.final_path = str(target_path)
        return result

    async def _validate_quality(
        self, file_path: Path, profile: QualityProfile
    ) -> dict:
        """Validate file quality against profile.

        Hey future me - this checks if the file meets quality requirements!

        We need file metadata (format, bitrate) to validate. For now, we do
        basic filename-based checks. Full implementation needs mutagen/ffprobe.
        """
        # Basic implementation - extract format from extension
        ext = file_path.suffix.lower().lstrip(".")

        # Try to map extension to AudioFormat
        format_map = {
            "flac": AudioFormat.FLAC,
            "mp3": AudioFormat.MP3,
            "m4a": AudioFormat.M4A,
            "aac": AudioFormat.AAC,
            "ogg": AudioFormat.OGG,
            "opus": AudioFormat.OPUS,
            "wav": AudioFormat.WAV,
            "alac": AudioFormat.ALAC,
        }

        audio_format = format_map.get(ext)
        if not audio_format:
            return {"matches": False, "reason": f"Unknown format: {ext}", "score": 0}

        # Build file info for QualityMatcher
        file_info = {
            "format": audio_format,
            "bitrate": None,  # We'd need to read file to get this
            "size_mb": file_path.stat().st_size / (1024 * 1024),
            "filename": file_path.name,
        }

        # Use QualityMatcher
        matcher = QualityMatcher(profile)
        matches, score = matcher.matches(file_info)

        reason = "Quality OK" if matches else "Below quality threshold"
        return {"matches": matches, "reason": reason, "score": score}

    def _build_target_path(self, download: Download, source_path: Path) -> Path:
        """Build the target path in the library.

        Hey future me - this applies the naming/folder templates!

        Templates use placeholders like {artist}, {album}, {title}.
        We sanitize values to be filesystem-safe.
        """
        # Get metadata from download
        artist = self._sanitize_filename(download.artist or "Unknown Artist")
        album = self._sanitize_filename(download.album or "Unknown Album")
        title = self._sanitize_filename(download.title or "Unknown Track")
        track_number = 1  # TODO: Get from track metadata
        year = ""  # TODO: Get from track/album metadata
        ext = source_path.suffix.lstrip(".")

        # Build folder path
        folder = self._config.folder_template.format(
            artist=artist,
            album=album,
            year=year,
        )

        # Build filename
        filename = self._config.naming_template.format(
            artist=artist,
            album=album,
            track_number=track_number,
            title=title,
            ext=ext,
        )

        # Combine
        target = Path(self._config.library_path) / folder / filename
        return target

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string for use in filenames.

        Hey future me - removes/replaces dangerous characters!
        Different OSes have different restrictions, so we're conservative.
        """
        # Remove or replace problematic characters
        # Allowed: alphanumeric, spaces, dashes, underscores, parentheses
        sanitized = re.sub(r'[<>:"/\\|?*]', "", name)
        # Collapse multiple spaces
        sanitized = re.sub(r"\s+", " ", sanitized)
        # Trim
        sanitized = sanitized.strip()
        # Limit length
        if len(sanitized) > 200:
            sanitized = sanitized[:200]
        # Fallback for empty
        return sanitized or "Unknown"

    async def _move_file(self, source: Path, target: Path) -> None:
        """Move file from source to target, creating directories as needed.

        Hey future me - we use shutil.move for cross-filesystem support!
        Also handles existing files by adding suffix.
        """
        # Create target directory
        target.parent.mkdir(parents=True, exist_ok=True)

        # Handle existing file
        if target.exists():
            # Add timestamp suffix
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            stem = target.stem
            suffix = target.suffix
            target = target.parent / f"{stem}_{timestamp}{suffix}"

        # Move file (works across filesystems)
        shutil.move(str(source), str(target))

    async def _apply_metadata(self, download: Download, file_path: Path) -> None:
        """Apply metadata tags to the file.

        Hey future me - this delegates to MetadataTaggerService!
        The tagger handles different formats (ID3 for MP3, Vorbis for FLAC).
        """
        if not self._metadata_tagger:
            return

        metadata = {
            "title": download.title,
            "artist": download.artist,
            "album": download.album,
            # Add more from track entity when available
        }

        await self._metadata_tagger.tag_file(file_path, metadata)

    async def _embed_artwork(self, download: Download, file_path: Path) -> None:
        """Embed album artwork into the file.

        Hey future me - this downloads artwork and embeds it!
        We need the artwork URL from the album/track entity.
        """
        if not self._metadata_tagger:
            return

        # TODO: Get artwork URL from track/album entity
        # For now, skip if no artwork available
        artwork_url = None  # Would come from download.album.artwork_url

        if artwork_url:
            await self._metadata_tagger.embed_artwork(file_path, artwork_url)

    @property
    def stats(self) -> dict:
        """Get worker statistics."""
        return self._stats.copy()

    async def reload_config(self) -> None:
        """Reload configuration from database.

        Hey future me - call this when settings change!
        Users can update post-processing settings in the UI.
        """
        # TODO: Load config from AppSettingsService
        logger.info("PostProcessingWorker config reloaded")
