"""File renaming service with template-based naming."""

import logging
import re
from pathlib import Path
from string import Formatter

from soulspot.config import Settings
from soulspot.domain.entities import Album, Artist, Track

logger = logging.getLogger(__name__)


class RenamingService:
    """Service for renaming files based on templates.

    This service:
    1. Generates file names from templates
    2. Sanitizes file names for filesystem compatibility
    3. Handles naming collisions
    4. Organizes files into directory structures
    """

    # Characters not allowed in filenames
    ILLEGAL_CHARS = r'[<>:"/\\|?*\x00-\x1f]'

    def __init__(self, settings: Settings) -> None:
        """Initialize renaming service.

        Args:
            settings: Application settings
        """
        self._settings = settings
        self._template = settings.postprocessing.file_naming_template

    def generate_filename(
        self,
        track: Track,
        artist: Artist,
        album: Album | None = None,
        extension: str = ".mp3",
    ) -> str:
        """Generate a filename from template.

        Args:
            track: Track entity
            artist: Artist entity
            album: Optional album entity
            extension: File extension (with dot)

        Returns:
            Generated filename (including path components)
        """
        # Prepare template variables with both old and new naming conventions
        variables = {
            # Legacy variables (for backward compatibility)
            "artist": artist.name,
            "title": track.title,
            "album": album.title if album else "Unknown Album",
            "track_number": track.track_number or 0,
            "disc_number": track.disc_number,
            "year": album.release_year if album else "",
            # New standardized variables
            "Artist CleanName": self._clean_name(artist.name),
            "Artist Disambiguation": "",  # TODO: Add disambiguation support
            "Track CleanTitle": self._clean_name(track.title),
            "Album CleanTitle": self._clean_name(album.title)
            if album
            else "Unknown Album",
            "Album Disambiguation": "",  # TODO: Add disambiguation support
            "Album Type": "Album",  # TODO: Add album type detection
            "Release Year": str(album.release_year)
            if album and album.release_year
            else "",
            "medium": track.disc_number,
            "track": track.track_number or 0,
        }

        # Format template
        try:
            filename = self._template.format(**variables)
        except KeyError as e:
            logger.warning("Invalid template variable: %s, using fallback", e)
            # Fallback to simple naming
            filename = f"{artist.name}/{track.title}"

        # Add extension
        filename = filename + extension

        # Sanitize filename
        filename = self._sanitize_filename(filename)

        return filename

    def _clean_name(self, name: str) -> str:
        """Clean a name for use in filenames.

        Removes or replaces characters that are problematic in filenames
        while keeping the name readable.

        Args:
            name: Name to clean

        Returns:
            Cleaned name
        """
        # Replace problematic characters with safe alternatives
        cleaned = name.replace("/", "-")
        cleaned = cleaned.replace("\\", "-")
        cleaned = cleaned.replace(":", " -")
        cleaned = cleaned.replace("?", "")
        cleaned = cleaned.replace("*", "")
        cleaned = cleaned.replace('"', "'")
        cleaned = cleaned.replace("<", "(")
        cleaned = cleaned.replace(">", ")")
        cleaned = cleaned.replace("|", "-")

        # Remove control characters
        cleaned = re.sub(r"[\x00-\x1f]", "", cleaned)

        # Collapse multiple spaces
        cleaned = re.sub(r"\s+", " ", cleaned)

        # Trim whitespace
        cleaned = cleaned.strip()

        return cleaned

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem compatibility.

        Args:
            filename: Raw filename

        Returns:
            Sanitized filename
        """
        # Split into path components to handle directories
        parts = filename.split("/")

        # Sanitize each part separately
        sanitized_parts = []
        for part in parts:
            # Replace illegal characters with underscore (except /)
            sanitized = re.sub(self.ILLEGAL_CHARS, "_", part)

            # Replace multiple underscores with single
            sanitized = re.sub(r"_+", "_", sanitized)

            # Remove leading/trailing spaces and dots
            sanitized = sanitized.strip(" .")

            sanitized_parts.append(sanitized)

        # Rejoin with /
        filename = "/".join(sanitized_parts)

        return filename

    async def rename_file(
        self,
        source_path: Path,
        track: Track,
        artist: Artist,
        album: Album | None = None,
    ) -> Path:
        """Rename and move a file based on template.

        Args:
            source_path: Current file path
            track: Track entity
            artist: Artist entity
            album: Optional album entity

        Returns:
            New file path
        """
        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        # Generate new filename
        extension = source_path.suffix
        relative_path = self.generate_filename(track, artist, album, extension)

        # Construct full destination path
        dest_path = self._settings.storage.music_path / relative_path

        # Create parent directories
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Handle existing file
        if dest_path.exists():
            logger.warning("File already exists: %s", dest_path)
            # Add numeric suffix
            dest_path = self._get_unique_path(dest_path)

        # Move file
        source_path.rename(dest_path)
        logger.info("Renamed file: %s -> %s", source_path, dest_path)

        return dest_path

    def _get_unique_path(self, path: Path) -> Path:
        """Get a unique path by adding numeric suffix.

        Args:
            path: Desired path

        Returns:
            Unique path
        """
        counter = 1
        stem = path.stem
        suffix = path.suffix
        parent = path.parent

        while path.exists():
            new_name = f"{stem}_{counter}{suffix}"
            path = parent / new_name
            counter += 1

        return path

    def validate_template(self, template: str) -> bool:
        """Validate a naming template.

        Args:
            template: Template string

        Returns:
            True if valid, False otherwise
        """
        try:
            # Check if all variables in template are supported
            formatter = Formatter()
            field_names = [
                field_name
                for _, field_name, _, _ in formatter.parse(template)
                if field_name is not None
            ]

            # Supported variables (both old and new naming conventions)
            supported = {
                # Legacy variables
                "artist",
                "title",
                "album",
                "track_number",
                "disc_number",
                "year",
                # New standardized variables
                "Artist CleanName",
                "Artist Disambiguation",
                "Track CleanTitle",
                "Album CleanTitle",
                "Album Disambiguation",
                "Album Type",
                "Release Year",
                "medium",
                "track",
            }

            for field in field_names:
                # Handle format specs (e.g., track:02d)
                field_base = field.split(":")[0]
                if field_base not in supported:
                    logger.warning("Unsupported template variable: %s", field_base)
                    return False

            return True

        except Exception as e:
            logger.exception("Error validating template: %s", e)
            return False
