"""Auto-import service for moving completed downloads to music library."""

import asyncio
import logging
import shutil
from pathlib import Path

from soulspot.config import Settings

logger = logging.getLogger(__name__)


class AutoImportService:
    """Service for automatically importing completed downloads to music library.

    This service monitors the downloads directory and moves completed music files
    to the music library directory, organizing them appropriately.
    """

    def __init__(
        self,
        settings: Settings,
        poll_interval: int = 60,
    ) -> None:
        """Initialize auto-import service.

        Args:
            settings: Application settings containing path configuration
            poll_interval: Seconds between directory scans (default: 60)
        """
        self._settings = settings
        self._poll_interval = poll_interval
        self._download_path = settings.storage.download_path
        self._music_path = settings.storage.music_path
        self._running = False

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

    async def stop(self) -> None:
        """Stop the auto-import service."""
        logger.info("Stopping auto-import service")
        self._running = False

    async def _monitor_loop(self) -> None:
        """Monitor downloads directory and process completed files."""
        while self._running:
            try:
                await self._process_downloads()
            except Exception as e:
                logger.exception("Error in auto-import monitor loop: %s", e)

            # Wait before next check
            await asyncio.sleep(self._poll_interval)

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
            import time

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

        Args:
            file_path: Path to file to import
        """
        try:
            # Determine destination path
            # Keep the relative path structure from downloads directory
            relative_path = file_path.relative_to(self._download_path)
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
            shutil.move(str(file_path), str(dest_path))
            logger.info("Successfully imported: %s", dest_path)

            # Clean up empty parent directories in downloads
            self._cleanup_empty_dirs(file_path.parent)

        except Exception as e:
            logger.exception("Error importing file %s: %s", file_path, e)
            raise

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
