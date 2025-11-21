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

    # Hey future me: Template-based file renaming - like a mail merge for file paths
    # Template example: "{Artist CleanName}/{Album CleanTitle}/{track:02d} - {Track CleanTitle}"
    # Result: "Pink Floyd/The Dark Side of the Moon/01 - Speak to Me.mp3"
    # WHY support both old and new variable names? Backward compatibility with user templates
    # GOTCHA: Illegal chars in artist/album names (e.g., "AC/DC") need sanitization or paths break
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
            "Artist Disambiguation": "",  # TODO: Add disambiguation support - e.g., "The Band (US)" vs "The Band (UK)"
            "Track CleanTitle": self._clean_name(track.title),
            "Album CleanTitle": self._clean_name(album.title)
            if album
            else "Unknown Album",
            "Album Disambiguation": "",  # TODO: Add disambiguation support - use MusicBrainz release disambiguation
            "Album Type": "Album",  # TODO: Add album type detection - Album/Single/EP/Compilation from MusicBrainz
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

    # Hey name cleaning - replaces problematic chars with safe alternatives
    # WHY these replacements? Filesystem compatibility across Windows/Mac/Linux
    # "/" -> "-" because "/" is directory separator on Unix
    # ":" -> " -" because ":" is reserved on Windows
    # Multiple spaces collapsed to one for cleaner look
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

    # Hey future me: File system sanitization - WHY so paranoid about characters?
    # Windows: Can't use < > : " / \ | ? * or chars 0x00-0x1f (control chars)
    # macOS/Linux: Can't use / and NUL, but we sanitize more for cross-platform compatibility
    # Example: "Artist: The Band" becomes "Artist - The Band" so Windows doesn't crash
    # GOTCHA: We split on "/" first to handle path components separately - don't want to sanitize directory separators
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

    # Hey future me: The actual file move operation
    # WHY mkdir with parents=True? Template might create deep paths like "Artist/2023/Album/Disc 1/"
    # WHY handle existing files? Race condition - another process might have created same file
    # GOTCHA: We use rename() not copy - if source and dest are on different filesystems, this FAILS
    # TODO: Add fallback to copy+delete for cross-filesystem moves
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

    # Yo unique path generator - adds _1, _2, _3 suffix until path is unique
    # WHY needed? Race conditions or multiple downloads of same track
    # Infinite loop protection: unlikely but counter could overflow after 2^31 iterations
    # stem = filename without extension, suffix = extension with dot
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

    # Listen, template validator - checks if all variables in template are supported
    # WHY validate? User typos like "{Arist}" instead of "{Artist}" cause crashes at runtime
    # Formatter.parse() extracts all placeholders from template string
    # field.split(":")[0] handles format specs like "{track:02d}" - takes only variable name
    # Returns False on ANY unsupported variable - fail fast and clear
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
