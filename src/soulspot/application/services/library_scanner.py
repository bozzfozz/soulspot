"""Library scanner service for scanning and analyzing music library."""

import hashlib
import logging
from pathlib import Path
from typing import Any

from mutagen import File as MutagenFile  # type: ignore[attr-defined]

from soulspot.infrastructure.security import PathValidator

logger = logging.getLogger(__name__)

# Supported audio file extensions
AUDIO_EXTENSIONS = {".mp3", ".flac", ".m4a", ".ogg", ".opus", ".wav", ".aac"}


class FileInfo:
    """Information about a scanned file."""

    def __init__(
        self,
        path: Path,
        size: int,
        hash_value: str,
        hash_algorithm: str,
        is_valid: bool = True,
        error: str | None = None,
        bitrate: int | None = None,
        sample_rate: int | None = None,
        format: str | None = None,
        duration_ms: int | None = None,
        title: str | None = None,
        artist: str | None = None,
        album: str | None = None,
    ):
        """Initialize file info."""
        self.path = path
        self.size = size
        self.hash_value = hash_value
        self.hash_algorithm = hash_algorithm
        self.is_valid = is_valid
        self.error = error
        self.bitrate = bitrate
        self.sample_rate = sample_rate
        self.format = format
        self.duration_ms = duration_ms
        self.title = title
        self.artist = artist
        self.album = album


class LibraryScannerService:
    """Service for scanning and analyzing music library."""

    def __init__(self, hash_algorithm: str = "sha256") -> None:
        """Initialize library scanner service.

        Args:
            hash_algorithm: Hash algorithm to use (md5, sha1, sha256)
        """
        self.hash_algorithm = hash_algorithm

    def discover_audio_files(self, scan_path: Path) -> list[Path]:
        """Discover all audio files in the given path.

        Args:
            scan_path: Path to scan for audio files

        Returns:
            List of audio file paths

        Note:
            The scan is constrained to the provided scan_path directory.
            Files are validated to ensure they remain within the scan_path
            to prevent path traversal issues.
        """
        audio_files: list[Path] = []

        if not scan_path.exists():
            logger.warning(f"Scan path does not exist: {scan_path}")
            return audio_files

        if not scan_path.is_dir():
            logger.warning(f"Scan path is not a directory: {scan_path}")
            return audio_files

        # Resolve scan_path to absolute path for validation
        scan_path_resolved = scan_path.resolve()

        try:
            for file_path in scan_path.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in AUDIO_EXTENSIONS:
                    # Validate each discovered file is within scan_path
                    try:
                        validated_path = PathValidator.validate_audio_file_path(
                            file_path, scan_path_resolved, resolve=True
                        )
                        audio_files.append(validated_path)
                    except ValueError as e:
                        # Log but don't stop scanning if individual file validation fails
                        logger.warning(
                            f"Skipping file due to validation failure: {file_path}. "
                            f"Reason: {e}"
                        )
                        continue
        except Exception as e:
            logger.error(f"Error discovering files: {e}")

        return audio_files

    def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate hash of a file.

        Args:
            file_path: Path to file

        Returns:
            Hash value as hex string
        """
        hash_func = hashlib.new(self.hash_algorithm)

        try:
            with open(file_path, "rb") as f:
                # Read in chunks to handle large files efficiently
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_func.update(chunk)
            return hash_func.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return ""

    def validate_audio_file(self, file_path: Path) -> tuple[bool, str | None]:
        """Validate audio file integrity.

        Args:
            file_path: Path to audio file

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            audio = MutagenFile(file_path)
            if audio is None:
                return False, "Unsupported audio format"

            # Check if file has basic audio properties
            if hasattr(audio, "info") and audio.info.length <= 0:
                return False, "Invalid audio length"

            return True, None
        except Exception as e:
            return False, f"Audio validation error: {str(e)}"

    def extract_audio_metadata(self, file_path: Path) -> dict[str, Any]:
        """Extract audio metadata from file.

        Args:
            file_path: Path to audio file

        Returns:
            Dictionary with audio metadata
        """
        metadata: dict[str, Any] = {
            "bitrate": None,
            "sample_rate": None,
            "format": None,
            "duration_ms": None,
            "title": None,
            "artist": None,
            "album": None,
        }

        try:
            audio = MutagenFile(file_path)
            if audio is None:
                return metadata

            # Extract format-specific information
            metadata["format"] = file_path.suffix.lstrip(".").lower()

            if hasattr(audio, "info"):
                info = audio.info
                if hasattr(info, "bitrate"):
                    metadata["bitrate"] = info.bitrate
                if hasattr(info, "sample_rate"):
                    metadata["sample_rate"] = info.sample_rate
                if hasattr(info, "length"):
                    metadata["duration_ms"] = int(info.length * 1000)

            # Extract tags
            if hasattr(audio, "tags") and audio.tags:
                tags = audio.tags

                # Try different tag formats
                for title_key in ["TIT2", "title", "\xa9nam"]:
                    if title_key in tags:
                        val = tags[title_key]
                        metadata["title"] = (
                            str(val[0]) if isinstance(val, list) else str(val)
                        )
                        break

                for artist_key in ["TPE1", "artist", "\xa9ART"]:
                    if artist_key in tags:
                        val = tags[artist_key]
                        metadata["artist"] = (
                            str(val[0]) if isinstance(val, list) else str(val)
                        )
                        break

                for album_key in ["TALB", "album", "\xa9alb"]:
                    if album_key in tags:
                        val = tags[album_key]
                        metadata["album"] = (
                            str(val[0]) if isinstance(val, list) else str(val)
                        )
                        break

        except Exception as e:
            logger.warning(f"Error extracting metadata from {file_path}: {e}")

        return metadata

    def scan_file(self, file_path: Path) -> FileInfo:
        """Scan a single audio file.

        Args:
            file_path: Path to audio file

        Returns:
            FileInfo object with scan results
        """
        # Get file size
        file_size = file_path.stat().st_size

        # Calculate hash
        file_hash = self.calculate_file_hash(file_path)

        # Validate file
        is_valid, error = self.validate_audio_file(file_path)

        # Extract metadata
        metadata = self.extract_audio_metadata(file_path)

        return FileInfo(
            path=file_path,
            size=file_size,
            hash_value=file_hash,
            hash_algorithm=self.hash_algorithm,
            is_valid=is_valid,
            error=error,
            bitrate=metadata.get("bitrate"),
            sample_rate=metadata.get("sample_rate"),
            format=metadata.get("format"),
            duration_ms=metadata.get("duration_ms"),
            title=metadata.get("title"),
            artist=metadata.get("artist"),
            album=metadata.get("album"),
        )

    def detect_duplicates(
        self, file_infos: list[FileInfo]
    ) -> dict[str, list[FileInfo]]:
        """Detect duplicate files by hash.

        Args:
            file_infos: List of scanned file information

        Returns:
            Dictionary mapping hash to list of duplicate files
        """
        hash_map: dict[str, list[FileInfo]] = {}

        for file_info in file_infos:
            if file_info.hash_value:
                if file_info.hash_value not in hash_map:
                    hash_map[file_info.hash_value] = []
                hash_map[file_info.hash_value].append(file_info)

        # Filter to only actual duplicates (more than one file with same hash)
        return {
            hash_value: files
            for hash_value, files in hash_map.items()
            if len(files) > 1
        }

    def analyze_broken_files(self, file_infos: list[FileInfo]) -> list[FileInfo]:
        """Analyze and return broken files.

        Args:
            file_infos: List of scanned file information

        Returns:
            List of broken files
        """
        return [file_info for file_info in file_infos if not file_info.is_valid]
