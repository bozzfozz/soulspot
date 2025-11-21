"""Auto-import service for moving completed downloads to music library."""

import asyncio
import logging
import shutil
import time
from pathlib import Path

from soulspot.application.services.postprocessing.pipeline import (
    PostProcessingPipeline,
)
from soulspot.config import Settings
from soulspot.domain.entities import Track
from soulspot.domain.ports import IAlbumRepository, IArtistRepository, ITrackRepository
from soulspot.domain.value_objects import FilePath

logger = logging.getLogger(__name__)


class AutoImportService:
    """Service for automatically importing completed downloads to music library.

    This service monitors the downloads directory and moves completed music files
    to the music library directory, organizing them appropriately.
    """

    def __init__(
        self,
        settings: Settings,
        track_repository: ITrackRepository,
        artist_repository: IArtistRepository,
        album_repository: IAlbumRepository,
        poll_interval: int = 60,
        post_processing_pipeline: PostProcessingPipeline | None = None,
    ) -> None:
        """Initialize auto-import service.

        Args:
            settings: Application settings containing path configuration
            track_repository: Repository for track data
            artist_repository: Repository for artist data
            album_repository: Repository for album data
            poll_interval: Seconds between directory scans (default: 60)
            post_processing_pipeline: Optional post-processing pipeline
        """
        self._settings = settings
        self._track_repository = track_repository
        self._artist_repository = artist_repository
        self._album_repository = album_repository
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
            logger.error("Download path does not exist: %s", self._download_path)
            self._running = False
            return

        if not self._music_path.exists():
            logger.error("Music path does not exist: %s", self._music_path)
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

    # Yo this discovers and processes all audio files in downloads dir
    # WHY per-file exception handling? One corrupt file shouldn't stop processing others
    # WHY debug log for no files? Normal case, not an error - don't spam logs
    # GOTCHA: This processes files sequentially - if you have 100 files, could take minutes
    # Consider parallel processing with asyncio.gather() but watch for race conditions on file moves
    async def _process_downloads(self) -> None:
        """Process all files in the downloads directory."""
        try:
            # Get all audio files in downloads directory
            audio_files = self._get_audio_files(self._download_path)

            if not audio_files:
                logger.debug("No audio files found in downloads directory")
                return

            logger.info("Found %d audio file(s) to process", len(audio_files))

            for file_path in audio_files:
                try:
                    await self._import_file(file_path)
                except Exception as e:
                    logger.exception("Error importing file %s: %s", file_path, e)

        except Exception as e:
            logger.exception("Error processing downloads: %s", e)

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

    # Hey future me: File completeness check - prevents moving files that are still being written
    # WHY check modification time? slskd writes files incrementally, we need to wait for it to finish
    # WHY 5 seconds? Heuristic - if file hasn't changed in 5s, it's probably done
    # GOTCHA: If download is REALLY slow (1KB/sec), we might move it prematurely
    # Better approach: Check if file is locked or monitor slskd API for completion status
    def _is_file_complete(self, file_path: Path) -> bool:
        """Check if file is completely downloaded (not being written).

        A file is considered complete if:
        1. It exists and is readable
        2. Its size is greater than 0
        3. It hasn't been modified in the last 5 seconds

        Args:
            file_path: Path to file

        Returns:
            True if file is complete, False otherwise
        """
        try:
            if not file_path.exists() or not file_path.is_file():
                return False

            # Check file size
            size = file_path.stat().st_size
            if size == 0:
                return False

            # Check if file was modified recently (within last 5 seconds)
            mtime = file_path.stat().st_mtime
            age = time.time() - mtime
            return age >= 5

        except Exception as e:
            logger.warning("Error checking file completeness for %s: %s", file_path, e)
            return False

    async def _import_file(self, file_path: Path) -> None:
        """Import a single file to the music library.

        This method:
        1. Finds the associated track in the database
        2. Runs post-processing pipeline (if enabled)
        3. Moves file to final destination (if post-processing didn't already)

        Args:
            file_path: Path to file to import
        """
        # Hey future me: The import flow - post-process then move (if needed)
        # WHY run post-processing first? It might rename/move the file to final destination
        # WHY check if still in downloads after? Post-processing might have moved it already
        # GOTCHA: We cleanup empty directories after move - don't leave "/downloads/Artist/Album/" clutter
        try:
            # Try to find the associated track by file path
            # We need to search for tracks that don't have a file_path yet
            # or have a file_path matching this download location
            track = await self._find_track_for_file(file_path)

            if track and self._settings.postprocessing.enabled:
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
                if track:
                    track.update_file_path(FilePath(dest_path))
                    await self._track_repository.update(track)

                # Clean up empty parent directories in downloads
                self._cleanup_empty_dirs(file_path.parent)

        except Exception as e:
            logger.exception("Error importing file %s: %s", file_path, e)
            raise

    # Hey future me: Track matching is NOT IMPLEMENTED - this is a STUB!
    # WHY return None? We don't have a way to map file -> track_id yet
    # TODO: Options to implement this:
    #   1. slskd could write .nfo file with track_id alongside download
    #   2. Parse filename and fuzzy-match against DB tracks
    #   3. Use acoustic fingerprinting (AcoustID/Chromaprint)
    # GOTCHA: Without this, post-processing pipeline won't know track metadata
    # The import will still work (file gets moved) but tagging won't happen
    async def _find_track_for_file(self, file_path: Path) -> Track | None:
        """Find the track entity associated with a downloaded file.

        This is a simplified implementation. In production, you might:
        1. Store the track_id in the download metadata
        2. Use file naming patterns to match tracks
        3. Use audio fingerprinting

        Args:
            file_path: Path to the downloaded file

        Returns:
            Track entity or None
        """
        # For now, return None - in a real implementation,
        # we would need to track which download corresponds to which track
        # This could be done by adding metadata files or database lookups
        logger.debug("Track lookup not implemented for: %s", file_path)
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
