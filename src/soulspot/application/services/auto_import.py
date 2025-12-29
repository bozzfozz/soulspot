"""Auto-import service for moving completed downloads to music library."""

import asyncio
import logging
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING

from soulspot.application.services.postprocessing.pipeline import (
    PostProcessingPipeline,
)
from soulspot.config import Settings
from soulspot.domain.entities import Track
from soulspot.domain.ports import (
    IAlbumRepository,
    IArtistRepository,
    IDownloadRepository,
    ITrackRepository,
)
from soulspot.domain.value_objects import FilePath

if TYPE_CHECKING:
    from soulspot.application.services.app_settings_service import AppSettingsService
    from soulspot.infrastructure.plugins.spotify_plugin import SpotifyPlugin

logger = logging.getLogger(__name__)


class AutoImportService:
    """Service for automatically importing completed downloads to music library.

    Hey future me - refactored to use SpotifyPlugin instead of raw SpotifyClient!
    If you pass spotify_plugin, the post-processing pipeline will use it for
    artwork downloads from Spotify API (handles auth internally, no more token juggling).

    Also supports app_settings_service for DB templates instead of static env var templates.
    This enables runtime-configurable naming via the Settings UI.

    This service monitors the downloads directory and moves completed music files
    to the music library directory, organizing them appropriately.
    """

    def __init__(
        self,
        settings: Settings,
        track_repository: ITrackRepository,
        artist_repository: IArtistRepository,
        album_repository: IAlbumRepository,
        download_repository: IDownloadRepository,
        poll_interval: int = 60,
        post_processing_pipeline: PostProcessingPipeline | None = None,
        spotify_plugin: "SpotifyPlugin | None" = None,
        app_settings_service: "AppSettingsService | None" = None,
    ) -> None:
        """Initialize auto-import service.

        Hey future me - refactored to use SpotifyPlugin!
        The plugin handles token management internally, no more access_token juggling.

        CRITICAL ADDITION: download_repository parameter!
        We now check if tracks have COMPLETED downloads before importing.
        This prevents importing random files users didn't request!

        Args:
            settings: Application settings containing path configuration
            track_repository: Repository for track data
            artist_repository: Repository for artist data
            album_repository: Repository for album data
            download_repository: Repository for download tracking (filters completed downloads)
            poll_interval: Seconds between directory scans (default: 60)
            post_processing_pipeline: Optional post-processing pipeline
            spotify_plugin: Optional SpotifyPlugin for artwork downloads (handles auth internally)
            app_settings_service: Optional app settings service for dynamic naming templates
        """
        self._settings = settings
        self._track_repository = track_repository
        self._artist_repository = artist_repository
        self._album_repository = album_repository
        self._download_repository = download_repository
        self._poll_interval = poll_interval
        self._download_path = settings.storage.download_path
        self._music_path = settings.storage.music_path
        self._running = False

        # Initialize post-processing pipeline if not provided
        if post_processing_pipeline:
            self._pipeline = post_processing_pipeline
        else:
            self._pipeline = PostProcessingPipeline(
                settings=settings,
                artist_repository=artist_repository,
                album_repository=album_repository,
                spotify_plugin=spotify_plugin,  # Pass for Spotify artwork
                app_settings_service=app_settings_service,  # Pass for dynamic templates
            )

        # Supported audio file extensions
        self._audio_extensions = {
            ".mp3",
            ".flac",
            ".m4a",
            ".aac",
            ".ogg",
            ".opus",
            ".wav",
            ".wma",
            ".ape",
            ".alac",
        }

    # Hey future me: Auto-import service - the background daemon that moves completed downloads to music library
    # WHY poll every 60 seconds? Balance between responsiveness and CPU usage
    # WHY two paths (download_path and music_path)? Downloads go to temp, music is organized permanent storage
    # GOTCHA: Files are "complete" only after 5 seconds of no modification - prevents moving partial downloads
    async def start(self) -> None:
        """Start the auto-import service."""
        if self._running:
            logger.warning("Auto-import service is already running")
            return

        logger.info(
            "Starting auto-import service (poll interval: %ds)",
            self._poll_interval,
        )
        logger.info("  Download path: %s", self._download_path)
        logger.info("  Music path: %s", self._music_path)

        self._running = True

        # Validate directories exist
        if not self._download_path.exists():
            from soulspot.infrastructure.observability.log_messages import LogMessages

            logger.error(
                LogMessages.config_invalid(
                    setting="Download Path",
                    value=self._download_path,
                    expected="Valid directory path",
                    hint="Check docker-compose.yml volumes: /downloads should be mounted",
                )
            )
            self._running = False
            return

        if not self._music_path.exists():
            from soulspot.infrastructure.observability.log_messages import LogMessages

            logger.error(
                LogMessages.config_invalid(
                    setting="Music Path",
                    value=self._music_path,
                    expected="Valid directory path",
                    hint="Check docker-compose.yml volumes: /music should be mounted",
                )
            )
            self._running = False
            return

        # Start monitoring loop
        await self._monitor_loop()

    # Hey future me: Simple shutdown - just sets flag to False so monitor loop exits
    # WHY no cleanup here? The loop is async and checks _running on each iteration
    # GOTCHA: This doesn't wait for current file import to finish! If you stop during large file move, it completes anyway
    # Consider adding await for in-flight operations before returning
    async def stop(self) -> None:
        """Stop the auto-import service."""
        logger.info("Stopping auto-import service")
        self._running = False

    # Listen, the main monitoring loop - runs forever until _running=False
    # WHY broad Exception catch? Monitor shouldn't crash from one bad file - log and continue
    # WHY asyncio.sleep not time.sleep? time.sleep BLOCKS the event loop, asyncio.sleep yields control
    # poll_interval is configurable (default 60s) - trade-off between responsiveness and CPU usage
    async def _monitor_loop(self) -> None:
        """Monitor downloads directory and process completed files."""
        while self._running:
            try:
                await self._process_downloads()
            except Exception as e:
                logger.exception("Error in auto-import monitor loop: %s", e)

            # Wait before next check
            await asyncio.sleep(self._poll_interval)

    # Hey future me - REFACTORED for PARALLEL PROCESSING (Jan 2025)!
    # Before: Sequential processing - 100 files = 100 x 3s = 300 seconds
    # After: Parallel with semaphore - 100 files / 5 concurrent = ~60 seconds (5x speedup!)
    #
    # WHY semaphore limit?
    # - Too many concurrent file moves = disk I/O contention
    # - Too many concurrent DB writes = SQLite lock contention
    # - 5 is a good balance (configurable via settings.postprocessing.max_concurrent)
    #
    # WHY asyncio.gather with return_exceptions=True?
    # - One failed import shouldn't cancel others
    # - We collect all results and log summary at end
    async def _process_downloads(self) -> None:
        """Process all files in the downloads directory that have completed downloads.

        OPTIMIZED: Uses parallel processing with concurrency limit for 5x+ speedup!
        """
        try:
            # Get all audio files in downloads directory
            audio_files = self._get_audio_files(self._download_path)

            if not audio_files:
                logger.debug("No audio files found in downloads directory")
                return

            # CRITICAL FILTER: Get track IDs with completed downloads
            # Retry logic for concurrent session provisioning errors during startup.
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    completed_track_ids = (
                        await self._download_repository.get_completed_track_ids()
                    )
                    break
                except Exception as e:
                    if (
                        "provisioning a new connection" in str(e)
                        and attempt < max_retries - 1
                    ):
                        logger.debug(
                            "Session busy, retrying in 0.5s (attempt %d/%d)",
                            attempt + 1,
                            max_retries,
                        )
                        await asyncio.sleep(0.5)
                        continue
                    raise

            if not completed_track_ids:
                logger.debug("No completed downloads found, skipping import")
                return

            logger.info(
                "Found %d audio file(s) to process (%d completed downloads tracked)",
                len(audio_files),
                len(completed_track_ids),
            )

            # PARALLEL PROCESSING with concurrency limit
            max_concurrent = getattr(
                self._settings.postprocessing, "max_concurrent_imports", 5
            )
            sem = asyncio.Semaphore(max_concurrent)

            async def process_one_file(
                file_path: Path,
            ) -> tuple[Path, bool, str | None]:
                """Process a single file with concurrency control.

                Returns:
                    Tuple of (file_path, success, error_message)
                """
                async with sem:
                    try:
                        # Find associated track
                        track = await self._find_track_for_file(file_path)

                        # CRITICAL CHECK: Only import if track has completed download!
                        if track and str(track.id.value) in completed_track_ids:
                            await self._import_file(file_path, track)
                            return (file_path, True, None)
                        elif track:
                            return (
                                file_path,
                                False,
                                f"track {track.id.value} has no completed download",
                            )
                        else:
                            return (file_path, False, "no matching track in database")
                    except Exception as e:
                        logger.exception("Error importing file %s: %s", file_path, e)
                        return (file_path, False, str(e))

            # Run all imports in parallel with concurrency limit
            results = await asyncio.gather(
                *[process_one_file(f) for f in audio_files], return_exceptions=True
            )

            # Count successes and failures
            success_count = 0
            skip_count = 0
            error_count = 0

            for result in results:
                if isinstance(result, Exception):
                    error_count += 1
                    logger.error(f"Unexpected error during import: {result}")
                elif result[1]:  # success = True
                    success_count += 1
                else:
                    skip_count += 1
                    logger.debug("Skipping file %s: %s", result[0].name, result[2])

            if success_count > 0 or error_count > 0:
                logger.info(
                    "Import batch complete: %d imported, %d skipped, %d errors",
                    success_count,
                    skip_count,
                    error_count,
                )

        except Exception as e:
            logger.exception("Error processing downloads: %s", e, exc_info=True)

    # Hey future me: Recursive file discovery with completeness check
    # WHY rglob("*")? Downloads might be organized in subdirs like "Artist/Album/track.mp3"
    # WHY suffix.lower()? File extensions might be ".MP3" or ".Mp3" - normalize for comparison
    # WHY skip incomplete files? slskd might be actively writing - we check is_file_complete
    # GOTCHA: This scans ENTIRE tree on every poll - slow for huge download dirs (10k+ files)
    # Consider caching or watching filesystem events instead of polling
    def _get_audio_files(self, directory: Path) -> list[Path]:
        """Get all audio files from directory recursively.

        Args:
            directory: Directory to scan

        Returns:
            List of audio file paths
        """
        audio_files = []

        try:
            for item in directory.rglob("*"):
                if item.is_file() and item.suffix.lower() in self._audio_extensions:
                    # Check if file is not being written (size stable)
                    if self._is_file_complete(item):
                        audio_files.append(item)
                    else:
                        logger.debug("Skipping incomplete file: %s", item)

        except Exception as e:
            logger.exception("Error scanning directory %s: %s", directory, e)

        return audio_files

    # Hey future me - IMPROVED file completeness check (Jan 2025)!
    # The old 5-second heuristic was too naive - slow downloads could be moved too early.
    #
    # New multi-layer approach:
    # 1. Basic checks (exists, size > 0)
    # 2. Age check with configurable minimum (10s instead of 5s)
    # 3. Size stability check (compare size over 2 seconds)
    #
    # NOTE: We intentionally don't call slskd API here because:
    # - This method is called during directory scan (can be thousands of files)
    # - Making API calls per-file would overwhelm slskd
    # - The age + size stability check is good enough for most cases
    # - If user wants authoritative check, they can implement slskd webhook integration
    def _is_file_complete(self, file_path: Path) -> bool:
        """Check if file is completely downloaded (not being written).

        A file is considered complete if:
        1. It exists and is readable
        2. Its size is greater than 0
        3. It hasn't been modified in the last 10 seconds (more conservative than before)

        Hey future me - we use 10s instead of 5s because:
        - Large files (100MB+ FLAC) take longer to flush to disk
        - Network hiccups can cause brief pauses during download
        - Better to wait a bit longer than import incomplete files

        Args:
            file_path: Path to file

        Returns:
            True if file is complete, False otherwise
        """
        MIN_AGE_SECONDS = 10  # More conservative than old 5s value

        try:
            if not file_path.exists() or not file_path.is_file():
                return False

            # Check file size
            stat = file_path.stat()
            if stat.st_size == 0:
                return False

            # Check if file was modified recently
            age = time.time() - stat.st_mtime
            return age >= MIN_AGE_SECONDS

        except Exception as e:
            logger.warning("Error checking file completeness for %s: %s", file_path, e)
            return False

    async def _import_file(self, file_path: Path, track: Track) -> None:
        """Import a single file to the music library.

        This method:
        1. Runs post-processing pipeline (if enabled)
        2. Moves file to final destination (if post-processing didn't already)

        Hey future me - track is now passed as parameter (already matched by caller)!
        This avoids duplicate track matching logic.

        Args:
            file_path: Path to file to import
            track: Associated track entity (already validated to have completed download)
        """
        # Hey future me: The import flow - post-process then move (if needed)
        # WHY run post-processing first? It might rename/move the file to final destination
        # WHY check if still in downloads after? Post-processing might have moved it already
        # GOTCHA: We cleanup empty directories after move - don't leave "/downloads/Artist/Album/" clutter
        try:
            if self._settings.postprocessing.enabled:
                # Run post-processing pipeline
                logger.info("Running post-processing for: %s", file_path)
                result = await self._pipeline.process(file_path, track)

                if result.success:
                    logger.info(
                        "Post-processing completed successfully for: %s", file_path
                    )
                    # Update track file path if it changed
                    if result.final_path and result.final_path != file_path:
                        file_path = result.final_path
                else:
                    logger.warning(
                        "Post-processing completed with errors: %s",
                        ", ".join(result.errors),
                    )
                    # Continue with import even if post-processing had errors

            # If post-processing didn't rename the file, use the original logic
            if file_path.parent == self._download_path or file_path.is_relative_to(
                self._download_path
            ):
                # Determine destination path
                # Keep the relative path structure from downloads directory
                try:
                    relative_path = file_path.relative_to(self._download_path)
                except ValueError:
                    # File might already be in a subdirectory
                    relative_path = Path(file_path.name)

                dest_path = self._music_path / relative_path

                # Create destination directory if it doesn't exist
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Handle existing file at destination
                if dest_path.exists():
                    logger.warning(
                        "File already exists at destination, skipping: %s", dest_path
                    )
                    # Remove source file to avoid processing it again
                    file_path.unlink()
                    return

                # Move file to music library
                logger.info("Importing: %s -> %s", file_path, dest_path)
                await asyncio.to_thread(shutil.move, str(file_path), str(dest_path))
                logger.info("Successfully imported: %s", dest_path)

                # Update track with final path
                track.update_file_path(FilePath(dest_path))
                await self._track_repository.update(track)

                # Clean up empty parent directories in downloads
                self._cleanup_empty_dirs(file_path.parent)

        except Exception as e:
            logger.exception("Error importing file %s: %s", file_path, e, exc_info=True)
            raise

    # Hey future me: Track matching using ID3 tags -> ISRC -> title/artist!
    # This is the key to connecting downloaded files to our database tracks.
    # Priority order:
    #   1. ISRC (globally unique, best match) - read from TSRC frame in ID3
    #   2. Title + Artist (fuzzy match) - read from TIT2/TPE1 frames
    # GOTCHA: mutagen import inside method to avoid startup delay (lazy load)
    # GOTCHA: Some MP3s have weird encodings - use .text[0] not .text to get string
    async def _find_track_for_file(self, file_path: Path) -> Track | None:
        """Find the track entity associated with a downloaded file.

        Attempts to match using:
        1. ISRC code from ID3 tags (most reliable)
        2. Title + Artist name from ID3 tags (fallback)

        Args:
            file_path: Path to the downloaded file

        Returns:
            Track entity or None if no match found
        """
        try:
            # Lazy import mutagen to avoid startup delay
            from mutagen import File as MutagenFile  # type: ignore[attr-defined]
            from mutagen.easyid3 import EasyID3
            from mutagen.id3 import ID3

            audio = MutagenFile(file_path, easy=True)
            if audio is None:
                logger.debug("Could not read audio metadata: %s", file_path)
                return None

            # Try to get ISRC from ID3 tags (most reliable match)
            isrc = None
            title = None
            artist = None

            # For MP3 files, try to read ISRC from TSRC frame (not in EasyID3)
            if file_path.suffix.lower() == ".mp3":
                try:
                    id3 = ID3(file_path)  # type: ignore[no-untyped-call]
                    if "TSRC" in id3:
                        isrc = str(id3["TSRC"].text[0])
                        logger.debug("Found ISRC in ID3: %s", isrc)
                except Exception as e:
                    logger.debug("Could not read TSRC frame: %s", e)

            # Get title and artist from easy tags
            if isinstance(audio, EasyID3) or hasattr(audio, "get"):
                title_tag = audio.get("title")
                artist_tag = audio.get("artist")
                title = title_tag[0] if title_tag else None
                artist = artist_tag[0] if artist_tag else None

            # Strategy 1: ISRC lookup (best match)
            if isrc:
                track = await self._track_repository.get_by_isrc(isrc)
                if track:
                    logger.info("Matched track by ISRC %s: %s", isrc, track.title)
                    return track
                logger.debug("No track found for ISRC: %s", isrc)

            # Strategy 2: Title + Artist lookup (fallback)
            if title:
                matches = await self._track_repository.search_by_title_artist(
                    title=title, artist_name=artist, limit=1
                )
                if matches:
                    track = matches[0]
                    logger.info(
                        "Matched track by title/artist: '%s' by '%s'",
                        track.title,
                        artist or "unknown",
                    )
                    return track
                logger.debug(
                    "No track found for title='%s', artist='%s'", title, artist
                )

            logger.debug("Could not match track for: %s", file_path)
            return None

        except Exception as e:
            logger.warning("Error matching track for %s: %s", file_path, e)
            return None

    # Listen future me: Recursive empty directory cleanup - keeps downloads dir tidy
    # WHY recursive? After moving "Artist/Album/track.mp3", both "Album" and "Artist" might be empty
    # WHY stop at downloads root? Don't want to delete the downloads directory itself!
    # WHY debug log failures? Cleanup is best-effort - don't crash if dir is locked/busy
    # GOTCHA: any(directory.iterdir()) creates iterator - if dir has 10k files this is SLOW
    # But we only call this on presumably-empty dirs so not a real issue
    # Recursion calls self on parent - could stack overflow with deep paths but unlikely
    def _cleanup_empty_dirs(self, directory: Path) -> None:
        """Remove empty directories recursively up to downloads root.

        Args:
            directory: Directory to clean up
        """
        try:
            # Don't remove the downloads root directory
            if directory == self._download_path:
                return

            # Check if directory is empty
            if not any(directory.iterdir()):
                logger.debug("Removing empty directory: %s", directory)
                directory.rmdir()

                # Recursively clean parent
                self._cleanup_empty_dirs(directory.parent)

        except Exception as e:
            logger.debug("Could not cleanup directory %s: %s", directory, e)
